"""
The severity cap is a feasible set, not a clamp.

Regression test for the case where the two formulations disagree. Clamping the
unconstrained winner down the ladder, action = min(unc_idx, cap_idx), stops on
the first rung at or below the cap regardless of what it costs. When the loss
ordering does not follow the severity ladder, that rung can cost more than
another action the cap also permits.

This is reachable in the shipped policies. Under internal_copilot, C = 800 and
ESCALATE carries friction 120, so escalation costs more than the defect it
prevents. A grounded contradiction there produced

    ALLOW 160 | HOLD 85 | CONSTRAIN 63 | ESCALATE 136 | BLOCK 50

with the precision cap at ESCALATE. BLOCK wins unconstrained, the clamp walks
it to ESCALATE at 136, and CONSTRAIN at 63 is left on the table even though the
cap allows it. The engine is specified as a constrained minimisation, so the
argmin is re-taken over the permitted set and CONSTRAIN is selected.

Under decision_support the loss ordering happens to follow the ladder, so the
two formulations agree and the discrepancy never surfaces. That is why this
needs its own test rather than relying on the golden vector.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.schemas import (
    ConsequenceModel,
    DetectorOutput,
    Policy,
    RiskVector,
)
from controlplane.engine.decide import decide, get_session_store
from controlplane.engine.severity import severity_index


def _copilot_policy() -> Policy:
    """internal_copilot as shipped in policies/internal_copilot.yaml."""
    return Policy(
        workflow_id="internal_copilot",
        version="v1",
        jurisdiction="IN",
        consequence=ConsequenceModel(performance=800, cost=200, responsibility=800),
        irreversibility=0.2,
        latency_budget_ms=500,
        intervention_mode="monitored",
        fail_mode="open",
        prior={"performance": 0.02, "cost": 0.008, "responsibility": 0.004},
        kappa={
            "cost|performance": 0.4,
            "performance|responsibility": 0.4,
            "cost|responsibility": 0.4,
        },
        lam=0.3,
        stage="enforcing",
        routing={"q1": 0.05, "q2": 0.01},
        friction={"ALLOW": 0, "HOLD": 5, "CONSTRAIN": 15, "ESCALATE": 120, "BLOCK": 50},
        utility_loss={"ALLOW": 0, "HOLD": 20, "CONSTRAIN": 80, "ESCALATE": 40, "BLOCK": 200},
        residual={"ALLOW": 1.0, "HOLD": 0.5, "CONSTRAIN": 0.3, "ESCALATE": 0.1, "BLOCK": 0.0},
    )


def _certain_grounding_failure() -> RiskVector:
    """
    A grounded contradiction: p_hat = 1.0 on performance, at the entailment
    detector's measured precision, which sits in the 0.70-0.95 ESCALATE band.
    """
    return RiskVector(
        per_tag={
            "performance": DetectorOutput(
                detector_id="grounding_nli",
                tag="performance",
                p_hat=1.0,
                verifiable=True,
                measured_precision=0.80,
                tier=1,
                latency_ms=50.0,
            ),
            "cost": DetectorOutput(
                detector_id="test_cost",
                tag="cost",
                p_hat=0.0,
                verifiable=True,
                measured_precision=0.90,
                tier=0,
                latency_ms=5.0,
            ),
            "responsibility": DetectorOutput(
                detector_id="test_resp",
                tag="responsibility",
                p_hat=0.0,
                verifiable=True,
                measured_precision=0.90,
                tier=0,
                latency_ms=5.0,
            ),
        },
        unverifiable_tags=[],
    )


class TestConstrainedArgmin:
    def setup_method(self):
        get_session_store().clear()

    def test_ladder_and_loss_ordering_actually_disagree(self):
        """
        Guard the premise. If a policy change ever makes ESCALATE cheaper than
        CONSTRAIN here, this scenario stops exercising the disagreement and the
        assertions below would pass for the wrong reason.
        """
        decision = decide(_certain_grounding_failure(), _copilot_policy(), session_id=None)
        assert decision.severity_cap == "ESCALATE"
        assert decision.unconstrained_action == "BLOCK"
        assert decision.losses["ESCALATE"] > decision.losses["CONSTRAIN"], (
            "scenario no longer disagrees with the severity ladder: "
            f"ESCALATE={decision.losses['ESCALATE']} "
            f"CONSTRAIN={decision.losses['CONSTRAIN']}"
        )

    def test_selects_cheapest_permitted_action_not_the_next_rung_down(self):
        decision = decide(_certain_grounding_failure(), _copilot_policy(), session_id=None)
        assert decision.action == "CONSTRAIN", (
            f"expected the cheapest permitted action, got {decision.action} "
            f"(losses: {decision.losses}, cap: {decision.severity_cap})"
        )

    def test_chosen_action_is_minimal_over_the_permitted_set(self):
        """The general invariant, not just this scenario's expected answer."""
        decision = decide(_certain_grounding_failure(), _copilot_policy(), session_id=None)
        cap_idx = severity_index(decision.severity_cap)
        permitted = {
            a: loss
            for a, loss in decision.losses.items()
            if severity_index(a) <= cap_idx
        }
        assert decision.losses[decision.action] == min(permitted.values())

    def test_cap_never_exceeded(self):
        decision = decide(_certain_grounding_failure(), _copilot_policy(), session_id=None)
        assert severity_index(decision.action) <= severity_index(decision.severity_cap)

    def test_cap_reason_still_recorded(self):
        """A capped decision must remain auditable as capped."""
        decision = decide(_certain_grounding_failure(), _copilot_policy(), session_id=None)
        assert decision.action != decision.unconstrained_action
        assert decision.cap_reason == "low_precision"
        assert "CAP_LOW_PRECISION" in decision.reason_codes

    def test_uncapped_decision_matches_unconstrained_argmin(self):
        """
        When precision permits the full spectrum, the constrained argmin and the
        unconstrained argmin must agree -- the change must not alter the
        uncapped path.
        """
        risk = _certain_grounding_failure()
        risk.per_tag["performance"].measured_precision = 0.98  # BLOCK band
        decision = decide(risk, _copilot_policy(), session_id=None)
        assert decision.severity_cap == "BLOCK"
        assert decision.action == decision.unconstrained_action == "BLOCK"
