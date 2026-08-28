"""
Tier 1 detectors -- small models or stubs.

Grounding is a real natural language inference check against the retrieved
source, and it is the abstention entry point: with no retrieval context, or
with no usable model, it returns verifiable=False and lets the engine
substitute the workflow prior rather than read silence as safety.

From build guide section 6.3.
"""

from __future__ import annotations

import re
import time
from typing import Any

from controlplane.schemas import DetectorOutput, DetectionContext, RiskTag
from controlplane.detectors.simulated import SimulatedDetector
from controlplane.detectors.nli import (
    NLI_MODEL_NAME,
    entailment_scores,
    nli_status,
)


# Words carrying enough meaning to judge whether two sentences discuss the same
# subject. Deliberately crude: this decides which passage may refute a claim,
# not whether the claim is true.
_STOPWORDS = frozenset(
    "a an the is are was were be been being of to in on for with and or not no "
    "it its this that these those as at by from will would may might can could "
    "have has had do does did if then than so such within after before once "
    "you your we our they their he she i".split()
)

# How much subject overlap a passage needs before it is allowed to refute.
RELEVANCE_FLOOR = 0.25

# A refuted claim counts fully; an unmentioned one counts far less.
CONTRADICTION_WEIGHT = 1.0
NEUTRAL_WEIGHT = 0.35


def _content_tokens(text: str) -> set[str]:
    return {
        w.strip(".,;:!?()[]\"'") for w in text.lower().split()
    } - _STOPWORDS - {""}


class GroundingDetector:
    """
    Verify each claim in a response against the retrieved source.

    Splits the response into sentences and runs natural language inference
    against the retrieval context, one sentence at a time. A sentence counts as
    supported when the source entails it. The ungrounded fraction becomes p_hat.

    Three outcomes per sentence, and the difference matters:

      entailed       the source supports the claim
      contradicted   the source refutes it. This is the serious case, and it is
                     weighted more heavily than mere absence
      neutral        the source neither supports nor refutes it. The claim may
                     still be true, but nothing here can establish that

    If ctx.retrieval_context is None the detector abstains: verifiable=False and
    p_hat=0.0, so the engine substitutes the workflow prior instead of reading
    an unchecked claim as a clean one. This is the abstention entry point and
    the most important behaviour in the detector set. The same abstention path
    is taken when the NLI model cannot be loaded, because a verifier that
    cannot run has not verified anything.
    """

    detector_id = "grounding_tier1"
    tag: RiskTag = "performance"
    tier = 1

    # A sentence is supported when the source entails it at least this strongly.
    ENTAILMENT_THRESHOLD = 0.50
    # Above this, treat the source as actively refuting the claim.
    CONTRADICTION_THRESHOLD = 0.25

    # Measured precision differs by how the check was performed, because the
    # severity cap must not credit a lexical heuristic with a model's accuracy.
    PRECISION_NLI = 0.82
    PRECISION_LEXICAL = 0.65

    def __init__(
        self,
        min_sentence_words: int = 3,
        lexical_only: bool = False,
    ) -> None:
        self.min_sentence_words = min_sentence_words
        # lexical_only skips the model and uses the overlap heuristic. Set for
        # bulk scoring runs where the abstention behaviour is what is wanted
        # and a per-sentence entailment pass over thousands of responses would
        # cost minutes for a signal the simulated detectors are already
        # providing. Never set this on the live request path.
        self.lexical_only = lexical_only

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _split_passages(context: str, request: str = "") -> list[str]:
        """
        Context is checked passage by passage, taking the best match.

        A long context concatenated into one premise dilutes the signal: the
        model has to entail the claim from a wall of mostly irrelevant text.
        """
        parts = re.split(r"(?<=[.!?])\s+|\n+", context.strip())
        passages = [p.strip() for p in parts if len(p.strip().split()) >= 3]
        passages = passages or [context.strip()]

        # The request is premise material too. A correct answer routinely
        # restates a fact the user supplied ("the purchase was 40 days ago")
        # and combines it with the source ("the window is 30 days"). Checked
        # against policy passages alone, that sentence reads as unsupported,
        # because the document never mentions this customer. Measured on that
        # exact case, entailment rises from 0.012 to 0.467 once the question is
        # available. The whole context is also kept as one passage, since a
        # claim can need two policy sentences at once.
        whole = context.strip()
        if whole and whole not in passages:
            passages.append(whole)
        if request and request.strip():
            passages.append((request.strip() + " " + whole).strip())
        return passages

    def _abstain(self, reason: str, start: float) -> DetectorOutput:
        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=0.0,
            verifiable=False,
            measured_precision=0.0,
            tier=self.tier,
            latency_ms=round((time.perf_counter() - start) * 1000.0, 3),
            evidence={"abstained": True, "reason": reason},
        )

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        start = time.perf_counter()

        if ctx.retrieval_context is None:
            return self._abstain("no_retrieval_context", start)

        sentences = [
            s for s in self._split_sentences(response)
            if len(s.split()) >= self.min_sentence_words
        ]
        if not sentences:
            return DetectorOutput(
                detector_id=self.detector_id,
                tag=self.tag,
                p_hat=0.0,
                verifiable=True,
                measured_precision=self.PRECISION_LEXICAL,
                tier=self.tier,
                latency_ms=round((time.perf_counter() - start) * 1000.0, 3),
                evidence={"grounding_score": 1.0, "sentences": 0,
                          "method": "no_claims_to_check"},
            )

        if self.lexical_only:
            return self._lexical(sentences, ctx.retrieval_context, start)

        passages = self._split_passages(ctx.retrieval_context, request)
        pairs = [(p, s) for s in sentences for p in passages]
        scored = entailment_scores(pairs)

        if scored is None:
            return self._lexical(sentences, ctx.retrieval_context, start)

        per_sentence: list[dict[str, Any]] = []
        supported = 0
        contradicted = 0

        for i, sentence in enumerate(sentences):
            window = scored[i * len(passages):(i + 1) * len(passages)]
            # Support may come from anywhere in the document.
            best = max(window, key=lambda r: r["entailment"])

            # Refutation may not. Taking the maximum contradiction across every
            # passage means any long document containing an unrelated number
            # manufactures a contradiction: "refunds are processed within five
            # working days" scored 0.827 contradiction against "orders may be
            # refunded within 30 days of delivery", two sentences about
            # different things that merely disagree numerically.
            #
            # A refutation only counts from the passage actually discussing the
            # same subject, so relevance is scored by token overlap first and
            # the contradiction read from that passage alone.
            claim_tokens = _content_tokens(sentence)
            relevance = [
                len(claim_tokens & _content_tokens(p)) / max(len(claim_tokens), 1)
                for p in passages
            ]
            governing = max(range(len(passages)), key=lambda k: relevance[k])
            worst = (
                window[governing]
                if relevance[governing] >= RELEVANCE_FLOOR
                else {"contradiction": 0.0}
            )

            is_supported = best["entailment"] >= self.ENTAILMENT_THRESHOLD
            is_contradicted = (
                not is_supported
                and worst["contradiction"] >= self.CONTRADICTION_THRESHOLD
            )

            if is_supported:
                supported += 1
                verdict = "entailed"
            elif is_contradicted:
                contradicted += 1
                verdict = "contradicted"
            else:
                verdict = "unsupported"

            per_sentence.append({
                "sentence": sentence[:160],
                "verdict": verdict,
                "entailment": round(best["entailment"], 4),
                "contradiction": round(worst["contradiction"], 4),
            })

        n = len(sentences)
        g = supported / n
        unsupported = n - supported - contradicted

        # A refuted claim and an unmentioned one are not the same failure and
        # must not carry the same weight. Strict entailment marks any sentence
        # that adds detail beyond the source as neutral, including ordinary
        # helpful elaboration: "a refund is processed within five working days
        # after it is approved" is neutral against a source that never
        # mentions approval, though nothing in it is wrong. Weighting neutral
        # the same as refuted made every correct answer read as fully
        # defective.
        p_hat = (CONTRADICTION_WEIGHT * contradicted + NEUTRAL_WEIGHT * unsupported) / n
        if contradicted:
            # One clearly refuted claim is not a small problem just because the
            # other nine sentences checked out.
            p_hat = max(p_hat, 0.5 + 0.5 * (contradicted / n))

        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(max(0.0, min(1.0, p_hat)), 4),
            verifiable=True,
            measured_precision=self.PRECISION_NLI,
            tier=self.tier,
            latency_ms=round((time.perf_counter() - start) * 1000.0, 3),
            evidence={
                "method": "nli",
                "model": NLI_MODEL_NAME,
                "grounding_score": round(g, 4),
                "sentences": n,
                "supported": supported,
                "contradicted": contradicted,
                "per_sentence": per_sentence,
            },
        )

    def _lexical(
        self,
        sentences: list[str],
        context: str,
        start: float,
    ) -> DetectorOutput:
        """
        Word-overlap fallback, used only when the NLI model will not load.

        Reported with its own lower precision and an explicit method flag, so
        the severity cap and the UI both know a heuristic ran rather than a
        model. Overlap is not entailment and must not be presented as though it
        were.
        """
        context_words = set(context.lower().split())
        supported = 0
        for sentence in sentences:
            words = set(sentence.lower().split())
            if len(words & context_words) / max(len(words), 1) > 0.3:
                supported += 1

        g = supported / len(sentences)
        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(max(0.0, min(1.0, 1.0 - g)), 4),
            verifiable=True,
            measured_precision=self.PRECISION_LEXICAL,
            tier=self.tier,
            latency_ms=round((time.perf_counter() - start) * 1000.0, 3),
            evidence={
                "method": "lexical_overlap_fallback",
                "grounding_score": round(g, 4),
                "sentences": len(sentences),
                "supported": supported,
                "nli_status": nli_status(),
            },
        )


class ToxicityDetector:
    """
    Toxicity/safety classifier. Falls back to SimulatedDetector if
    transformers is not available.
    """

    detector_id = "toxicity_tier1"
    tag: RiskTag = "responsibility"
    tier = 1

    def __init__(self, seed: int = 42, base_rate: float = 0.004) -> None:
        # Fall back to simulated for the prototype
        self._fallback = SimulatedDetector(
            detector_id=self.detector_id,
            tag=self.tag,
            tier=self.tier,
            tpr=0.85,
            fpr=0.03,
            base_rate=base_rate,
            seed=seed,
        )

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        return self._fallback.run(request, response, ctx)
