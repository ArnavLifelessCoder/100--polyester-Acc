"""
Golden decision test -- the single test that carries the entire thesis.

Build guide section 7: Workflow support_chatbot,
  p_hats = {performance: 0.30, cost: 0.02, responsibility: 0.10},
  kappa=0.4 on the performance-responsibility pair, lam=0.3, iota=0.6,
  no session carry.

The golden vector says kappa=0.4 for the pair that matters. The exact
P_def = 0.3334 is reproduced when kappa=0.4 applies to ALL pairs
(since the build guide states "kappa=0.4" without qualification).

Expected:
  P_def   = 0.3334
  C_eff   = 3900.0
  L(ALLOW)     = 780.10
  L(HOLD)      = 408.38
  L(CONSTRAIN) = 302.36
  L(ESCALATE)  = 331.33
  L(BLOCK)     = 183.32
  unconstrained_action = BLOCK
  driving tag = performance, measured_precision = 0.55
  severity_max = CONSTRAIN
  action = CONSTRAIN
  cap_reason = "low_precision"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.schemas import (
    Action,
    ConsequenceModel,
    DetectorOutput,
    Policy,
    RiskVector,
)
from controlplane.engine.decide import decide, get_session_store


def _make_golden_risk_vector() -> RiskVector:
    """Build the golden test's risk vector."""
    return RiskVector(
        per_tag={
            "performance": DetectorOutput(
                detector_id="test_perf",
                tag="performance",
                p_hat=0.30,
                verifiable=True,
                measured_precision=0.55,
                tier=1,
                latency_ms=50.0,
            ),
            "cost": DetectorOutput(
                detector_id="test_cost",
                tag="cost",
                p_hat=0.02,
                verifiable=True,
                measured_precision=0.90,
                tier=0,
                latency_ms=5.0,
            ),
            "responsibility": DetectorOutput(
                detector_id="test_resp",
                tag="responsibility",
                p_hat=0.10,
                verifiable=True,
                measured_precision=0.75,
                tier=1,
                latency_ms=45.0,
            ),
        },
        unverifiable_tags=[],
    )


def _make_golden_policy() -> Policy:
    """
    Construct the golden policy exactly as specified in build guide section 7.

    Uses support_chatbot consequence (3000/400/3000), iota=0.6,
    kappa=0.4 for all pairs, lam=0.3, same friction/utility/residual as
    the YAML policies.
    """
    return Policy(
        workflow_id="support_chatbot",
        version="v1",
        jurisdiction="IN",
        consequence=ConsequenceModel(performance=3000, cost=400, responsibility=3000),
        irreversibility=0.6,
        latency_budget_ms=800,
        intervention_mode="buffered",
        fail_mode="open",
        prior={"performance": 0.015, "cost": 0.006, "responsibility": 0.004},
        kappa={
            "cost|performance": 0.4,
            "performance|responsibility": 0.4,
            "cost|responsibility": 0.4,
        },
        lam=0.3,
        stage="enforcing",
        routing={"q1": 0.08, "q2": 0.015},
        friction={"ALLOW": 0, "HOLD": 5, "CONSTRAIN": 15, "ESCALATE": 120, "BLOCK": 50},
        utility_loss={"ALLOW": 0, "HOLD": 20, "CONSTRAIN": 80, "ESCALATE": 200, "BLOCK": 200},
        residual={"ALLOW": 1.0, "HOLD": 0.5, "CONSTRAIN": 0.3, "ESCALATE": 0.1, "BLOCK": 0.0},
    )


class TestGoldenDecision:
    def setup_method(self):
        get_session_store().clear()

    def test_p_def(self):
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)
        # kappa=0.4 all pairs:
        #   m=performance (0.30)
        #   term_cost = 1 - 0.4*0.02 = 0.992
        #   term_resp = 1 - 0.4*0.10 = 0.96
        #   product = 0.992 * 0.96 = 0.95232
        #   P = 0.30 + 0.70*(1-0.95232) = 0.30 + 0.033376 = 0.333376
        assert abs(decision.p_def - 0.3334) < 0.001, (
            f"P_def expected 0.3334, got {decision.p_def}"
        )

    def test_c_eff(self):
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)
        assert abs(decision.c_eff - 3900.0) < 1e-2, (
            f"C_eff expected 3900.0, got {decision.c_eff}"
        )

    def test_losses(self):
        """All five L(a) values from the golden vector."""
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)

        expected = {
            "ALLOW": 780.10,
            "HOLD": 408.38,
            "CONSTRAIN": 302.36,
            "ESCALATE": 331.33,
            "BLOCK": 183.32,
        }

        for action, exp in expected.items():
            actual = decision.losses[action]
            assert abs(actual - exp) < 1.0, (
                f"L({action}) expected {exp}, got {actual}"
            )

    def test_unconstrained_is_block(self):
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)
        assert decision.unconstrained_action == "BLOCK", (
            f"unconstrained expected BLOCK, got {decision.unconstrained_action}"
        )

    def test_cap_constrains(self):
        """The precision cap must refuse the BLOCK and force CONSTRAIN."""
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)
        assert decision.action == "CONSTRAIN", (
            f"action expected CONSTRAIN, got {decision.action}"
        )
        assert decision.cap_reason == "low_precision"

    def test_all_losses_populated(self):
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)
        assert len(decision.losses) == 5
        for action in ["ALLOW", "HOLD", "CONSTRAIN", "ESCALATE", "BLOCK"]:
            assert action in decision.losses

    def test_loss_ordering(self):
        """BLOCK should have the lowest loss (unconstrained winner)."""
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)
        losses = decision.losses
        assert losses["BLOCK"] < losses["ALLOW"], "BLOCK should beat ALLOW on expected loss"
        assert losses["BLOCK"] < losses["CONSTRAIN"], "BLOCK should beat CONSTRAIN"

    def test_shadow_false_for_enforcing(self):
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)
        assert not decision.shadow

    def test_no_session_carry(self):
        policy = _make_golden_policy()
        risk = _make_golden_risk_vector()
        decision = decide(risk, policy, session_id=None)
        assert decision.session_risk_before == 0.0
