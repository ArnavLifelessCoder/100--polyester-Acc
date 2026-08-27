"""
The action spectrum must actually have five actions in it, and the thresholds
the UI quotes must be the ones the engine uses.

Two defects motivated this file.

First, ESCALATE was unreachable. With U(ESCALATE) == U(BLOCK) == 200 and
F(BLOCK) < F(ESCALATE), the difference

    L(ESCALATE) - L(BLOCK) = 0.1 * p * C * iota + 70

is positive for every p and every workflow, so BLOCK dominated ESCALATE
unconditionally and the argmin never chose it. A seeded run of 3,011 decisions
contained zero escalations. The pitch describes a five-action spectrum with a
human-review tier; the engine had four actions and no way to reach a human.

Second, thresholds.py and decide.py disagreed. The closed forms omit iota and
the utility-loss term, so the p*_block they publish is 2.3x to 3.7x below the
point at which the engine actually blocks.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.policy import load_all_policies
from controlplane.engine.decide import decide, get_session_store
from controlplane.engine.severity import SEVERITY_ORDER, severity_index
from controlplane.engine.thresholds import (
    action_thresholds,
    first_p_for_action,
    loss_line,
)
from controlplane.schemas import ACTIONS, DetectorOutput, RiskVector

POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"
POLICIES = load_all_policies(POLICIES_DIR)


def _risk(p: float, precision: float = 0.99) -> RiskVector:
    """A single-tag risk vector, so the driving tag and C_eff are unambiguous."""
    def det(tag, p_hat, prec):
        return DetectorOutput(
            detector_id=f"test_{tag}", tag=tag, p_hat=p_hat, verifiable=True,
            measured_precision=prec, tier=1, latency_ms=1.0,
        )
    return RiskVector(per_tag={
        "performance": det("performance", p, precision),
        "cost": det("cost", 0.0, 0.99),
        "responsibility": det("responsibility", 0.0, 0.99),
    })


class TestEscalateIsReachable:
    def test_escalate_is_not_dominated_by_block(self):
        """
        Algebraic check, independent of any sweep: there must be some p at which
        L(ESCALATE) is strictly below L(BLOCK).
        """
        for wid, policy in POLICIES.items():
            c = max(policy.consequence.as_dict().values())
            m_e, b_e = loss_line(policy, "ESCALATE", c)
            m_b, b_b = loss_line(policy, "BLOCK", c)
            beats = any(
                m_e * (i / 1000) + b_e < m_b * (i / 1000) + b_b
                for i in range(1001)
            )
            assert beats, (
                f"{wid}: ESCALATE is dominated by BLOCK at every p. "
                "Check U(ESCALATE) against U(BLOCK) in the policy."
            )

    def test_escalate_wins_somewhere_in_a_high_consequence_workflow(self):
        assert first_p_for_action(POLICIES["decision_support"], "ESCALATE") is not None
        assert first_p_for_action(POLICIES["support_chatbot"], "ESCALATE") is not None

    def test_escalate_reachable_through_the_engine(self):
        """Not just in the threshold algebra: the engine must actually return it."""
        policy = POLICIES["decision_support"]
        p_start = first_p_for_action(policy, "ESCALATE")
        assert p_start is not None
        get_session_store().clear()
        decision = decide(_risk(p_start + 0.001), policy, session_id=None)
        assert decision.unconstrained_action == "ESCALATE"

    def test_escalation_costs_less_utility_than_a_block(self):
        """
        Escalation delays a response, a block destroys it. Encoding them as the
        same utility loss is what made ESCALATE unreachable.
        """
        for wid, policy in POLICIES.items():
            assert policy.utility_loss["ESCALATE"] < policy.utility_loss["BLOCK"], (
                f"{wid}: U(ESCALATE) must be below U(BLOCK)"
            )

    def test_every_action_is_reachable_somewhere(self):
        """No action in the published spectrum may be dead across all workflows."""
        reachable = set()
        for policy in POLICIES.values():
            reachable.update(a for _, a in action_thresholds(policy))
        missing = set(ACTIONS) - reachable
        assert not missing, f"actions unreachable in every workflow: {missing}"


class TestThresholdsAgreeWithTheEngine:
    """
    The build guide requires the reference thresholds and the argmin to agree.
    They are now derived from the same L(a), so this test checks that the
    derivation was not bypassed rather than that two formulas coincide.
    """

    @pytest.mark.parametrize("workflow_id", sorted(POLICIES))
    def test_thresholds_predict_the_engine(self, workflow_id):
        policy = POLICIES[workflow_id]
        segments = action_thresholds(policy)

        for i, (p_start, expected) in enumerate(segments):
            p_end = segments[i + 1][0] if i + 1 < len(segments) else 1.0
            # Sample inside the segment, away from both boundaries.
            for frac in (0.25, 0.5, 0.75):
                p = p_start + (p_end - p_start) * frac
                get_session_store().clear()
                decision = decide(_risk(p), policy, session_id=None)
                assert decision.unconstrained_action == expected, (
                    f"{workflow_id}: threshold table says {expected} at "
                    f"p={p:.6f}, engine chose {decision.unconstrained_action}"
                )

    @pytest.mark.parametrize("workflow_id", sorted(POLICIES))
    def test_segments_are_ordered_and_monotone(self, workflow_id):
        segments = action_thresholds(POLICIES[workflow_id])
        assert segments[0][0] == 0.0
        starts = [p for p, _ in segments]
        assert starts == sorted(starts)
        indices = [severity_index(a) for _, a in segments]
        assert indices == sorted(indices), (
            f"{workflow_id}: severity must not decrease as risk rises: {indices}"
        )

    def test_closed_forms_are_not_used_for_routing(self):
        """
        Guards against quietly reverting to the annex closed form. The two
        disagree by a wide margin and the engine follows the derived value.
        """
        from controlplane.engine.thresholds import p_star_block
        policy = POLICIES["support_chatbot"]
        c = max(policy.consequence.as_dict().values())
        closed = p_star_block(c)
        derived = first_p_for_action(policy, "BLOCK")
        assert derived is not None
        assert abs(derived - closed) > 0.1, (
            "the closed form and the engine happen to agree here; if that is "
            "intentional this test needs revisiting"
        )
        get_session_store().clear()
        # At the closed form's block point the engine must not yet be blocking.
        assert decide(_risk(closed), policy, session_id=None).unconstrained_action != "BLOCK"
