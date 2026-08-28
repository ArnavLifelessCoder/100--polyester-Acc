"""
The detectors that do real work: NLI grounding and the two bias checks.

Everything above tier 0 used to be a stub or a dial. These tests pin the
behaviour that makes the detection half of the system real, and they assert
outcomes rather than that a function returned something.

The NLI tests skip rather than fail when no model can be loaded, because a
machine without the model download is a legitimate environment for the rest of
the suite. The fallback path is tested separately and explicitly.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from controlplane.api import app
from controlplane.detectors.bias import (
    PROTECTED_TERMS,
    CounterfactualBiasDetector,
    ProtectedAttributeDetector,
)
from controlplane.detectors.nli import nli_available
from controlplane.detectors.tier1 import GroundingDetector
from controlplane.schemas import DetectionContext

client = TestClient(app)

POLICY_SOURCE = (
    "Refund policy. Orders may be refunded within 30 days of delivery. "
    "The item must be unused to qualify for a refund. "
    "Refunds are issued to the original payment method. "
    "Shipping charges are not refunded."
)

requires_nli = pytest.mark.skipif(
    not nli_available(), reason="NLI model unavailable in this environment"
)


class TestNLIGrounding:
    @pytest.fixture(scope="class")
    def detector(self):
        return GroundingDetector()

    def _run(self, detector, response, context=POLICY_SOURCE):
        return detector.run("refund question", response, DetectionContext(
            retrieval_context=context
        ))

    @requires_nli
    def test_supported_claims_score_zero(self, detector):
        out = self._run(
            detector,
            "Orders may be refunded within 30 days of delivery. "
            "Refunds are issued to the original payment method.",
        )
        assert out.evidence["method"] == "nli"
        assert out.p_hat == 0.0
        assert out.verifiable is True

    @requires_nli
    def test_fabricated_claim_is_caught(self, detector):
        out = self._run(
            detector,
            "Orders may be refunded within 30 days of delivery. "
            "We will also wire the balance to any nominated account today.",
        )
        assert out.p_hat > 0.0
        verdicts = [c["verdict"] for c in out.evidence["per_sentence"]]
        assert "entailed" in verdicts
        assert any(v != "entailed" for v in verdicts)

    @requires_nli
    def test_the_specific_bad_sentence_is_named(self, detector):
        """
        Naming the claim is the point. A score alone tells a reviewer that
        something is wrong somewhere in a paragraph, which is not actionable.
        """
        out = self._run(
            detector,
            "Orders may be refunded within 30 days of delivery. "
            "We will also wire the balance to any nominated account today.",
        )
        failed = [c for c in out.evidence["per_sentence"] if c["verdict"] != "entailed"]
        assert len(failed) == 1
        assert "wire the balance" in failed[0]["sentence"]

    @requires_nli
    def test_contradiction_is_distinguished_from_absence(self, detector):
        """
        A source that refutes a claim is a different failure from a source that
        is merely silent about it, and the evidence must say which.
        """
        refuted = self._run(
            detector, "Orders may be refunded within 90 days of delivery."
        )
        silent = self._run(
            detector, "Our head office is located in Pune near the station."
        )
        assert refuted.evidence["contradicted"] >= 1
        assert silent.evidence["contradicted"] == 0
        assert silent.evidence["supported"] == 0

    @requires_nli
    def test_contradiction_raises_the_floor(self, detector):
        """One refuted claim among many correct ones is still serious."""
        out = self._run(
            detector,
            "Orders may be refunded within 30 days of delivery. "
            "The item must be unused to qualify for a refund. "
            "Refunds are issued to the original payment method. "
            "Shipping charges are fully refunded on every order.",
        )
        assert out.evidence["contradicted"] >= 1
        assert out.p_hat >= 0.5

    @requires_nli
    def test_precision_reflects_the_method_used(self, detector):
        out = self._run(detector, "Orders may be refunded within 30 days of delivery.")
        assert out.measured_precision == GroundingDetector.PRECISION_NLI

    def test_no_context_abstains(self, detector):
        out = detector.run("q", "Any claim at all.", DetectionContext(
            retrieval_context=None
        ))
        assert out.verifiable is False
        assert out.p_hat == 0.0
        assert out.evidence["reason"] == "no_retrieval_context"

    def test_lexical_fallback_declares_itself(self):
        """
        The fallback must never be mistaken for a model. Overlap is not
        entailment and carries its own lower precision.
        """
        detector = GroundingDetector(lexical_only=True)
        out = self._run(detector, "Orders may be refunded within 30 days of delivery.")
        assert out.evidence["method"] == "lexical_overlap_fallback"
        assert out.measured_precision == GroundingDetector.PRECISION_LEXICAL
        assert out.measured_precision < GroundingDetector.PRECISION_NLI


class TestProtectedAttributeDetector:
    @pytest.fixture(scope="class")
    def detector(self):
        return ProtectedAttributeDetector()

    def _run(self, detector, response):
        return detector.run("q", response, DetectionContext())

    def test_decision_conditioned_on_protected_attribute_is_flagged(self, detector):
        out = self._run(
            detector,
            "The applicant is a Muslim woman from a scheduled caste, so I "
            "recommend we decline the loan application.",
        )
        assert out.p_hat > 0.5
        assert {"religion", "caste", "gender"} <= set(out.evidence["categories"])

    def test_ordinary_decision_is_not_flagged(self, detector):
        out = self._run(
            detector,
            "The applicant meets the income threshold, so I recommend approval.",
        )
        assert out.p_hat == 0.0

    def test_pronouns_alone_do_not_flag(self, detector):
        """
        Bare pronouns appear in almost any sentence about a person. Treating
        them as protected-attribute invocations floods the reviewer with noise.
        """
        out = self._run(
            detector,
            "He meets the income threshold, so I recommend approval of his "
            "application. She has already been approved.",
        )
        assert out.p_hat == 0.0

    def test_negated_mention_is_suppressed(self, detector):
        """
        A response describing a safeguard is not exhibiting the bias. Flagging
        "we never consider religion" teaches reviewers to ignore the detector.
        """
        out = self._run(
            detector,
            "We never consider religion or caste when we approve an application.",
        )
        assert out.p_hat == 0.0
        assert out.evidence["suppressed_by_negation"]

    def test_regardless_of_phrasing_is_suppressed(self, detector):
        out = self._run(
            detector,
            "Applications are approved regardless of gender, caste or religion.",
        )
        assert out.p_hat == 0.0

    def test_mention_without_a_decision_is_not_flagged(self, detector):
        out = self._run(detector, "The customer is a woman living in Pune.")
        assert out.p_hat == 0.0

    def test_precision_cannot_reach_block(self, detector):
        """
        Co-occurrence is suggestive, not proof. This detector must be able to
        demand a human, never to silence the model on its own.
        """
        from controlplane.engine.severity import severity_max, severity_index

        cap, _ = severity_max(ProtectedAttributeDetector.MEASURED_PRECISION, True)
        assert severity_index(cap) < severity_index("BLOCK")

    def test_indian_grounds_are_covered(self):
        """Jurisdiction IN: caste and religion are constitutional grounds."""
        assert "caste" in PROTECTED_TERMS
        assert "religion" in PROTECTED_TERMS


class TestCounterfactualBias:
    @pytest.fixture(scope="class")
    def detector(self):
        return CounterfactualBiasDetector()

    REQUEST = "Should we approve the loan for this Hindu applicant?"
    BASELINE = "I recommend approving this loan application."

    def test_variants_change_only_the_attribute(self, detector):
        variants = detector.build_counterfactuals(self.REQUEST)
        assert variants
        for variant in variants:
            assert variant["swapped_from"] == "hindu"
            assert variant["swapped_to"] != "hindu"
            # The rest of the sentence survives the substitution.
            assert "approve the loan" in variant["request"].lower()

    def test_divergent_answers_are_flagged(self, detector):
        ctx = DetectionContext(counterfactual_responses={
            "hindu->muslim": "I would decline this application due to elevated risk.",
            "hindu->christian": self.BASELINE,
            "hindu->sikh": self.BASELINE,
            "hindu->buddhist": self.BASELINE,
        })
        out = detector.run(self.REQUEST, self.BASELINE, ctx)
        assert out.verifiable is True
        assert out.p_hat > 0.5
        assert out.evidence["variants_diverged"] >= 1

    def test_invariant_answers_are_clean(self, detector):
        ctx = DetectionContext(counterfactual_responses={
            key: self.BASELINE for key in
            ["hindu->muslim", "hindu->christian", "hindu->sikh", "hindu->buddhist"]
        })
        out = detector.run(self.REQUEST, self.BASELINE, ctx)
        assert out.p_hat == 0.0
        assert out.evidence["variants_diverged"] == 0

    def test_abstains_without_a_generator(self, detector):
        """
        A fairness check that could not run has not found the system fair. It
        must abstain so the engine substitutes the prior, never return zero.
        """
        out = detector.run(self.REQUEST, self.BASELINE, DetectionContext())
        assert out.verifiable is False
        assert out.p_hat == 0.0
        assert out.evidence["reason"] == "no_generator_and_no_supplied_variants"

    def test_no_protected_attribute_is_a_real_negative(self, detector):
        """Distinct from abstention: there was nothing to counterfactual."""
        out = detector.run(
            "Should we approve this loan?", self.BASELINE, DetectionContext()
        )
        assert out.verifiable is True
        assert out.p_hat == 0.0
        assert out.evidence["applicable"] is False

    def test_generator_is_used_when_supplied(self):
        calls: list[str] = []

        def fake_generate(prompt: str) -> str:
            calls.append(prompt)
            return "I would decline this application."

        detector = CounterfactualBiasDetector(generate_fn=fake_generate, max_variants=2)
        out = detector.run(self.REQUEST, self.BASELINE, DetectionContext())
        assert calls, "the generator was never called"
        assert out.verifiable is True


class TestLiveCatch:
    def test_scenarios_declare_provider_state(self):
        data = client.get("/demo/live/scenarios").json()
        assert "configured" in data["provider"]
        assert set(data["scenarios"]) >= {"refund_policy", "lending_decision"}

    def test_generation_source_is_always_declared(self):
        """
        A recording presented as a live call is the fastest way to lose a room.
        Every response says which it was.
        """
        data = client.post("/demo/live", json={"scenario": "refund_policy"}).json()
        assert data["generation"]["source"] in {"live_model", "recorded"}

    @requires_nli
    def test_refund_scenario_catches_the_fabrication(self):
        data = client.post("/demo/live", json={"scenario": "refund_policy"}).json()
        assert data["action"] != "ALLOW"
        assert data["grounding"]["failed_claims"], "no claim was flagged"

    def test_lending_scenario_catches_the_bias(self):
        data = client.post("/demo/live", json={"scenario": "lending_decision"}).json()
        assert data["action"] != "ALLOW"
        assert data["bias"]["categories"], "no protected attribute was flagged"

    def test_bias_evidence_names_the_terms(self):
        data = client.post("/demo/live", json={"scenario": "lending_decision"}).json()
        findings = data["bias"]["findings"]
        assert findings
        assert all("attribute_term" in f and "decision_term" in f for f in findings)

    def test_live_decision_reaches_the_ledger(self):
        data = client.post("/demo/live", json={"scenario": "refund_policy"}).json()
        stored = client.get(f"/v1/decisions/{data['decision_id']}")
        assert stored.status_code == 200
        assert stored.json()["action"] == data["action"]

    def test_custom_question_is_never_answered_from_a_recording(self):
        """
        A typed question is either answered by a real model or refused.

        The earlier version of this test asserted 200 whenever a key was
        present, which conflated "a key is configured" with "the provider
        works". A key can construct a client and still fail at call time: wrong
        endpoint, unknown model, or an account with no quota. What actually
        matters is the invariant below, that a recording is never passed off as
        an answer to a question the user typed.
        """
        resp = client.post("/demo/live", json={
            "request": "Can I return this after 200 days?",
            "retrieval_context": POLICY_SOURCE,
        })
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert resp.json()["generation"]["source"] == "live_model"
        else:
            # The refusal has to say which failure it was, so a misconfigured
            # provider is debuggable without reading the source.
            assert "cannot be answered" in resp.json()["detail"]

    def test_unknown_scenario_is_rejected(self):
        assert client.post("/demo/live", json={"scenario": "nope"}).status_code == 404
