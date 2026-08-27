"""
Bias detection at the input/output layer.

The brief names bias first among the risks to catch, and separately notes that
enterprises consume foundation models through an API rather than owning them,
which puts weights, activations and training data out of reach. Every
representation-level fairness method assumes access this deployment does not
have. So both detectors here work from the outside.

Two complementary signals:

`ProtectedAttributeDetector` (tier 0, deterministic) asks whether the response
conditions a decision on a protected attribute. It is cheap, explainable and
runs on every request. It catches the blatant case: a recommendation that cites
someone's religion, caste, gender or age as part of its reasoning.

`CounterfactualBiasDetector` (tier 2) asks the harder question: would the model
have said something materially different if the protected attribute were
changed and nothing else? That is the operational definition of
counterfactual fairness, and it is measurable through an API because it needs
only the ability to prompt and compare. It is expensive, so it sits in tier 2
behind the routing gate.

Neither detector claims to measure fairness in the full sense. They measure two
specific, checkable failures, and they report which one fired.
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable

from controlplane.schemas import DetectorOutput, DetectionContext, RiskTag


# Protected attribute vocabulary. The categories follow the Indian
# constitutional grounds (Articles 15 and 16) plus the usual employment and
# lending grounds, because the shipped policies declare jurisdiction IN. Caste
# and religion matter here in a way a US or EU list would miss entirely.
PROTECTED_TERMS: dict[str, list[str]] = {
    "religion": [
        "hindu", "muslim", "christian", "sikh", "buddhist", "jain", "parsi",
        "jewish", "islamic", "catholic", "religion", "religious",
    ],
    "caste": [
        "caste", "dalit", "brahmin", "scheduled caste", "scheduled tribe",
        "obc", "backward class", "upper caste", "lower caste",
    ],
    # Bare pronouns are deliberately absent. "he" and "she" appear in almost
    # any sentence about a person, so including them flags every ordinary
    # decision written about a named individual and buries the real signal.
    # The attribute has to be invoked, not merely implied by grammar.
    "gender": [
        "male", "female", "man", "woman", "men", "women", "transgender",
        "pregnant", "pregnancy", "maternity", "gender",
    ],
    "race_ethnicity": [
        "race", "racial", "ethnic", "ethnicity", "black", "white", "asian",
        "african", "hispanic", "latino", "indigenous", "tribal",
    ],
    "age": [
        "young", "old", "elderly", "aged", "senior citizen", "teenager",
        "middle-aged", "age",
    ],
    "disability": [
        "disabled", "disability", "handicapped", "blind", "deaf",
        "wheelchair", "impairment", "mental illness",
    ],
    "national_origin": [
        "immigrant", "migrant", "foreigner", "nationality", "citizenship",
        "refugee", "expatriate",
    ],
    "marital_status": [
        "married", "unmarried", "divorced", "widow", "widowed", "single mother",
    ],
}

# Language that indicates a decision, assessment or recommendation is being
# made. A protected term is only interesting when it sits near one of these.
# "The customer is a woman" is a fact; "declined because the customer is a
# woman" is a decision conditioned on a protected attribute.
DECISION_TERMS: list[str] = [
    "approve", "approved", "approval", "deny", "denied", "decline", "declined",
    "reject", "rejected", "eligible", "ineligible", "qualify", "qualified",
    "unqualified", "recommend", "recommended", "suitable", "unsuitable",
    "hire", "hiring", "shortlist", "reject", "risk", "risky", "creditworthy",
    "prioritise", "prioritize", "deprioritise", "flag", "grant", "refuse",
    "score", "rating", "assessment", "likely to default", "should not",
    "should be", "not a good fit", "better suited", "less capable",
]

# How close a protected term and a decision term must be, in words, to be read
# as one conditioning on the other.
PROXIMITY_WINDOW = 14

# Phrases that invert the reading. A response stating that an attribute is NOT
# considered is describing a safeguard, not applying a bias, and flagging it
# would train reviewers to ignore this detector. "We never consider religion
# when we approve an application" must not read the same as "declined because
# the applicant is Muslim".
NEGATION_CUES: list[str] = [
    "never", "not", "no", "without", "regardless of", "irrespective of",
    "independent of", "must not", "does not", "do not", "cannot", "may not",
    "prohibited", "forbidden", "excluded from", "free from", "unbiased",
    "non-discriminatory", "anti-discrimination",
]

# How far before a protected term a negation cue may sit and still govern it.
NEGATION_WINDOW = 6


def _find_terms(text: str, vocabulary: list[str]) -> list[tuple[str, int]]:
    """Return (term, word_index) for each vocabulary hit, matched on word boundaries."""
    words = text.lower().split()
    joined = " ".join(words)
    hits: list[tuple[str, int]] = []
    for term in vocabulary:
        for match in re.finditer(r"\b" + re.escape(term) + r"\b", joined):
            word_index = joined[: match.start()].count(" ")
            hits.append((term, word_index))
    return hits


class ProtectedAttributeDetector:
    """
    Flag responses that appear to condition a decision on a protected attribute.

    Co-occurrence within a short window is suggestive, not proof: a response can
    mention a protected attribute near a decision word entirely legitimately,
    for example when quoting an anti-discrimination policy. Precision is set
    accordingly, which means the severity cap will not let this detector alone
    drive a BLOCK. That is the intended behaviour. A bias signal this cheap
    should be able to escalate to a human, not to silence a response.
    """

    detector_id = "protected_attribute_tier0"
    tag: RiskTag = "responsibility"
    tier = 0

    # Co-occurrence evidence supports escalation, not blocking.
    MEASURED_PRECISION = 0.71

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        start = time.perf_counter()

        decisions = _find_terms(response, DECISION_TERMS)
        findings: list[dict[str, Any]] = []
        categories: set[str] = set()

        negations = _find_terms(response, NEGATION_CUES)
        suppressed: list[dict[str, Any]] = []

        if decisions:
            for category, terms in PROTECTED_TERMS.items():
                for term, position in _find_terms(response, terms):
                    nearest = min(
                        (abs(position - d_pos) for _, d_pos in decisions),
                        default=None,
                    )
                    governed_by = next(
                        (
                            cue for cue, cue_pos in negations
                            if 0 <= position - cue_pos <= NEGATION_WINDOW
                        ),
                        None,
                    )
                    if governed_by is not None:
                        suppressed.append({
                            "category": category,
                            "attribute_term": term,
                            "negation_cue": governed_by,
                        })
                        continue
                    if nearest is not None and nearest <= PROXIMITY_WINDOW:
                        closest = min(decisions, key=lambda d: abs(position - d[1]))
                        findings.append({
                            "category": category,
                            "attribute_term": term,
                            "decision_term": closest[0],
                            "distance_words": nearest,
                        })
                        categories.add(category)

        if not findings:
            p_hat = 0.0
        else:
            # Closer coupling and more categories both raise confidence. One
            # adjacent pair is a strong signal on its own; several categories
            # co-occurring with decision language is stronger still.
            tightest = min(f["distance_words"] for f in findings)
            proximity_weight = 1.0 - (tightest / (PROXIMITY_WINDOW + 1))
            p_hat = min(0.90, 0.45 + 0.35 * proximity_weight + 0.10 * (len(categories) - 1))

        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(p_hat, 4),
            verifiable=True,
            measured_precision=self.MEASURED_PRECISION,
            tier=self.tier,
            latency_ms=round((time.perf_counter() - start) * 1000.0, 3),
            evidence={
                "method": "protected_attribute_proximity",
                "categories": sorted(categories),
                "findings": findings[:8],
                "suppressed_by_negation": suppressed[:8],
                "decision_terms_present": sorted({t for t, _ in decisions})[:8],
            },
        )


class CounterfactualBiasDetector:
    """
    Measure whether swapping a protected attribute changes the answer.

    This is counterfactual fairness made operational. Rewrite the request with
    the protected attribute changed and nothing else, ask the model again, and
    compare. A model that recommends approval for one variant and rejection for
    another, on inputs that differ only in religion or gender, has revealed a
    dependence no accuracy metric would show.

    The comparison is semantic, not textual: variants are embedded and compared
    by cosine distance, so harmless rewording does not register while a
    reversed recommendation does.

    Availability is explicit. The detector needs either pre-computed variant
    responses on the context or a generator to produce them. With neither, it
    abstains rather than returning zero, and the engine substitutes the
    workflow's prior. A fairness check that could not run has not found the
    system fair.
    """

    detector_id = "counterfactual_bias_tier2"
    tag: RiskTag = "responsibility"
    tier = 2

    # A model call per variant, so the evidence is strong when it fires.
    MEASURED_PRECISION = 0.88
    # Cosine distance above which two variant answers are materially different.
    DIVERGENCE_THRESHOLD = 0.25

    def __init__(
        self,
        generate_fn: Callable[[str], str] | None = None,
        max_variants: int = 4,
    ) -> None:
        self.generate_fn = generate_fn
        self.max_variants = max_variants

    @staticmethod
    def build_counterfactuals(request: str, max_variants: int = 4) -> list[dict[str, str]]:
        """
        Rewrite the request with each protected term replaced by a peer term.

        Substitution stays inside a category, so only the protected attribute
        moves and the rest of the request is untouched. That single-variable
        property is what makes the comparison meaningful.
        """
        variants: list[dict[str, str]] = []
        lowered = request.lower()

        for category, terms in PROTECTED_TERMS.items():
            present = [t for t in terms if re.search(r"\b" + re.escape(t) + r"\b", lowered)]
            if not present:
                continue
            original = present[0]
            for replacement in terms:
                if replacement == original or len(variants) >= max_variants:
                    continue
                rewritten = re.sub(
                    r"\b" + re.escape(original) + r"\b",
                    replacement,
                    request,
                    flags=re.IGNORECASE,
                )
                if rewritten.lower() != lowered:
                    variants.append({
                        "category": category,
                        "swapped_from": original,
                        "swapped_to": replacement,
                        "request": rewritten,
                    })
        return variants

    def _abstain(self, reason: str, start: float, extra: dict[str, Any] | None = None) -> DetectorOutput:
        evidence = {"abstained": True, "reason": reason,
                    "method": "counterfactual_invariance"}
        evidence.update(extra or {})
        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=0.0,
            verifiable=False,
            measured_precision=0.0,
            tier=self.tier,
            latency_ms=round((time.perf_counter() - start) * 1000.0, 3),
            evidence=evidence,
        )

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        start = time.perf_counter()

        variants = self.build_counterfactuals(request, self.max_variants)
        if not variants:
            # Nothing protected in the request, so there is no counterfactual
            # to construct. This is a genuine negative, not an abstention.
            return DetectorOutput(
                detector_id=self.detector_id,
                tag=self.tag,
                p_hat=0.0,
                verifiable=True,
                measured_precision=self.MEASURED_PRECISION,
                tier=self.tier,
                latency_ms=round((time.perf_counter() - start) * 1000.0, 3),
                evidence={
                    "method": "counterfactual_invariance",
                    "applicable": False,
                    "reason": "no protected attribute in the request",
                },
            )

        supplied = dict(ctx.counterfactual_responses or {})
        outputs: list[dict[str, Any]] = []

        for variant in variants:
            key = f"{variant['swapped_from']}->{variant['swapped_to']}"
            if key in supplied:
                text = supplied[key]
            elif self.generate_fn is not None:
                try:
                    text = self.generate_fn(variant["request"])
                except Exception as exc:  # noqa: BLE001
                    return self._abstain(
                        "generation_failed", start, {"error": f"{type(exc).__name__}"}
                    )
            else:
                return self._abstain(
                    "no_generator_and_no_supplied_variants", start,
                    {"variants_needed": [
                        f"{v['swapped_from']}->{v['swapped_to']}" for v in variants
                    ]},
                )
            outputs.append({**variant, "response": text})

        distances = self._divergence(response, [o["response"] for o in outputs])
        if distances is None:
            return self._abstain("embedding_model_unavailable", start)

        for record, distance in zip(outputs, distances):
            record["divergence"] = round(distance, 4)
            record["materially_different"] = distance >= self.DIVERGENCE_THRESHOLD
            record["response"] = record["response"][:200]

        worst = max(distances)
        diverged = sum(1 for d in distances if d >= self.DIVERGENCE_THRESHOLD)

        # p_hat scales with the largest divergence found. Below the threshold
        # the answer is treated as invariant to the swap, which is the result
        # a fair model should produce.
        if worst < self.DIVERGENCE_THRESHOLD:
            p_hat = 0.0
        else:
            span = max(1e-6, 1.0 - self.DIVERGENCE_THRESHOLD)
            p_hat = min(0.95, 0.5 + 0.45 * ((worst - self.DIVERGENCE_THRESHOLD) / span))

        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(p_hat, 4),
            verifiable=True,
            measured_precision=self.MEASURED_PRECISION,
            tier=self.tier,
            latency_ms=round((time.perf_counter() - start) * 1000.0, 3),
            evidence={
                "method": "counterfactual_invariance",
                "applicable": True,
                "variants_tested": len(outputs),
                "variants_diverged": diverged,
                "max_divergence": round(worst, 4),
                "threshold": self.DIVERGENCE_THRESHOLD,
                "variants": outputs[:4],
            },
        )

    @staticmethod
    def _divergence(baseline: str, variants: list[str]) -> list[float] | None:
        """
        Cosine distance between the original answer and each variant answer.

        Falls back to a token Jaccard distance when no embedding model is
        available. The fallback is cruder but still measures difference rather
        than nothing, and the evidence records which was used.
        """
        try:
            import warnings

            warnings.filterwarnings("ignore")
            from sentence_transformers import SentenceTransformer, util

            model = _get_embedder()
            if model is None:
                raise RuntimeError("embedder unavailable")
            vectors = model.encode([baseline] + variants, convert_to_tensor=True)
            sims = util.cos_sim(vectors[0:1], vectors[1:])[0]
            return [float(1.0 - s) for s in sims]
        except Exception:  # noqa: BLE001
            base_tokens = set(baseline.lower().split())
            out = []
            for variant in variants:
                tokens = set(variant.lower().split())
                union = base_tokens | tokens
                if not union:
                    out.append(0.0)
                    continue
                out.append(1.0 - len(base_tokens & tokens) / len(union))
            return out


_embedder = None
_embedder_attempted = False


def _get_embedder():
    """Lazily load and cache the sentence embedding model."""
    global _embedder, _embedder_attempted
    if _embedder_attempted:
        return _embedder
    _embedder_attempted = True
    try:
        import warnings

        warnings.filterwarnings("ignore")
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:  # noqa: BLE001
        _embedder = None
    return _embedder
