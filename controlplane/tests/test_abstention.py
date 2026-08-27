"""
Abstention test -- build guide step 12.

Identical unverifiable input must escalate in decision_support and allow
in internal_copilot, with no workflow-name branching anywhere in the code path.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.schemas import DetectorOutput, RiskVector
from controlplane.engine.decide import decide, get_session_store
from controlplane.policy import load_policy


POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"


def _make_unverifiable_risk() -> RiskVector:
    """
    Risk vector where the performance tag is unverifiable.
    This simulates the grounding detector having no retrieval context.
    """
    return RiskVector(
        per_tag={
            "performance": DetectorOutput(
                detector_id="grounding_tier1",
                tag="performance",
                p_hat=0.0,  # will be replaced by prior
                verifiable=False,  # this triggers abstention
                measured_precision=0.0,
                tier=1,
                latency_ms=5.0,
                evidence={"abstained": True},
            ),
            "cost": DetectorOutput(
                detector_id="token_anomaly_tier0",
                tag="cost",
                p_hat=0.0,
                verifiable=True,
                measured_precision=0.85,
                tier=0,
                latency_ms=2.0,
            ),
            "responsibility": DetectorOutput(
                detector_id="pii_tier0",
                tag="responsibility",
                p_hat=0.0,
                verifiable=True,
                measured_precision=0.97,
                tier=0,
                latency_ms=1.0,
            ),
        },
        unverifiable_tags=["performance"],
    )


class TestAbstention:
    def setup_method(self):
        get_session_store().clear()

    def test_same_input_different_outcomes(self):
        """
        The same unverifiable input must escalate under decision_support
        (high consequence, prior pushes past threshold) and allow under
        internal_copilot (low consequence, prior stays below threshold).

        No workflow-name branching in the code path -- the difference comes
        entirely from the consequence model and derived thresholds.
        """
        risk = _make_unverifiable_risk()

        # Decision support: prior_perf=0.009, p*_esc for C=50000 is ~0.0027
        # 0.009 > 0.0027 => should escalate (or constrain, since unverifiable caps at CONSTRAIN)
        ds_policy = load_policy(POLICIES_DIR / "decision_support.yaml")
        ds_decision = decide(risk, ds_policy, session_id=None)

        # Internal copilot: prior_perf=0.018, p*_esc for C=800 is ~0.1667
        # 0.018 < 0.1667 => should allow
        cp_policy = load_policy(POLICIES_DIR / "internal_copilot.yaml")
        cp_decision = decide(risk, cp_policy, session_id=None)

        # Decision support should NOT allow -- it should escalate or constrain
        assert ds_decision.action != "ALLOW", (
            f"decision_support should not ALLOW an unverifiable claim, "
            f"got action={ds_decision.action}"
        )

        # Internal copilot should allow
        assert cp_decision.action == "ALLOW", (
            f"internal_copilot should ALLOW an unverifiable claim with low prior, "
            f"got action={cp_decision.action}"
        )

    def test_abstention_reason_codes(self):
        """Abstention must produce ABSTAIN_PERFORMANCE reason code."""
        risk = _make_unverifiable_risk()
        policy = load_policy(POLICIES_DIR / "decision_support.yaml")
        decision = decide(risk, policy, session_id=None)
        assert "ABSTAIN_PERFORMANCE" in decision.reason_codes

    def test_prior_substituted(self):
        """p_hat should be replaced by the prior, not left at 0."""
        risk = _make_unverifiable_risk()
        policy = load_policy(POLICIES_DIR / "decision_support.yaml")
        decision = decide(risk, policy, session_id=None)
        # P_def should reflect the prior, not 0
        assert decision.p_def > 0.0, "P_def should not be zero after prior substitution"

    def test_severity_capped_for_unverifiable(self):
        """Unverifiable signal must cap at CONSTRAIN, never BLOCK."""
        risk = _make_unverifiable_risk()
        policy = load_policy(POLICIES_DIR / "decision_support.yaml")
        decision = decide(risk, policy, session_id=None)
        assert decision.action in ("ALLOW", "HOLD", "CONSTRAIN"), (
            f"unverifiable signal should not produce ESCALATE or BLOCK, "
            f"got {decision.action}"
        )
