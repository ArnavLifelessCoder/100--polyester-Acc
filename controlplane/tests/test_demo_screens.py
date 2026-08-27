"""
Regression tests for the four demo screens.

Each screen exists to demonstrate one specific claim. A screen that runs
without error but no longer shows its claim is worse than a broken one,
because nothing fails until someone is standing in front of an audience.
Every test here asserts the claim, not the shape of the response.

The failures these lock down were all real:
  - screen 1 returned CONSTRAIN in all three columns
  - screen 3 returned the same action with and without retrieval context
  - screen 4 never changed action across the conversation
  - screen 2 did not call the engine at all
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.api import app
from controlplane.engine.severity import severity_index

client = TestClient(app)

WORKFLOWS = ("support_chatbot", "internal_copilot", "decision_support")


class TestScreen1SameResponseThreeVerdicts:
    """One risk vector, three consequence models, three different verdicts."""

    @pytest.fixture(scope="class")
    def data(self):
        resp = client.get("/demo/screen1")
        assert resp.status_code == 200
        return resp.json()

    def test_all_three_workflows_present(self, data):
        assert set(data["columns"]) == set(WORKFLOWS)

    def test_verdicts_are_not_all_identical(self, data):
        """The whole point of the screen. It used to fail this."""
        actions = [c["action"] for c in data["columns"].values()]
        assert len(set(actions)) > 1, (
            f"screen 1 shows the same verdict in every column: {actions}. "
            "It is meant to show that consequence alone changes the outcome."
        )

    def test_three_distinct_verdicts(self, data):
        assert len(data["distinct_actions"]) == 3, (
            f"expected three distinct actions, got {data['distinct_actions']}"
        )

    def test_risk_vector_is_shared_across_columns(self, data):
        """
        If the columns disagreed on the evidence, the screen would prove
        nothing about consequence. The cascade runs once for this reason.
        """
        vectors = [c["risk_vector"] for c in data["columns"].values()]
        for other in vectors[1:]:
            assert other == vectors[0]

    def test_p_def_identical_across_columns(self, data):
        p_defs = {c["p_def"] for c in data["columns"].values()}
        assert len(p_defs) == 1, f"P_def must not vary across columns: {p_defs}"

    def test_severity_orders_with_consequence(self, data):
        """Higher consequence must not produce a laxer action."""
        by_consequence = sorted(
            data["columns"].values(),
            key=lambda c: max(c["consequence"].values()),
        )
        indices = [severity_index(c["action"]) for c in by_consequence]
        assert indices == sorted(indices), (
            f"action severity must be monotone in consequence, got {indices}"
        )

    def test_cap_binds_somewhere(self, data):
        """
        The precision cap is half the thesis. At least one column must show
        the engine wanting a more severe action than the evidence supports.
        """
        assert any(c["cap_binds"] for c in data["columns"].values())

    def test_grounding_actually_ran(self, data):
        """Tier 1 verification must run, or the performance tag is never scored."""
        assert 1 in data["tiers_run"]


class TestScreen3Abstention:
    """Stripping the source changes the decision, and differently per workflow."""

    @pytest.fixture(scope="class")
    def panes(self):
        resp = client.get("/demo/screen3")
        assert resp.status_code == 200
        return resp.json()["panes"]

    def test_all_panes_present(self, panes):
        assert len(panes) == 6

    def test_with_context_verifies(self, panes):
        for wid in WORKFLOWS:
            pane = panes[f"with_context_{wid}"]
            assert pane["unverifiable_tags"] == []
            assert pane["action"] == "ALLOW"

    def test_without_context_abstains(self, panes):
        for wid in WORKFLOWS:
            pane = panes[f"without_context_{wid}"]
            assert "performance" in pane["unverifiable_tags"]
            assert pane["cap_reason"] == "unverifiable"
            assert any(
                rc == "ABSTAIN_PERFORMANCE" for rc in pane["reason_codes"]
            )

    def test_prior_substituted_not_zero(self, panes):
        """Never substitute zero. The prior is the whole mechanism."""
        for wid in WORKFLOWS:
            pane = panes[f"without_context_{wid}"]
            assert pane["prior_substituted"]["performance"] > 0.0
            assert pane["p_def"] > 0.0

    def test_same_input_diverges_by_workflow(self, panes):
        """
        Identical unverifiable input must intervene under decision_support and
        allow under internal_copilot, with no branching on workflow name.
        """
        assert panes["without_context_decision_support"]["action"] != "ALLOW"
        assert panes["without_context_internal_copilot"]["action"] == "ALLOW"

    def test_unverifiable_never_blocks(self, panes):
        """Build guide 5.3: an unverifiable signal caps at CONSTRAIN."""
        for wid in WORKFLOWS:
            pane = panes[f"without_context_{wid}"]
            assert severity_index(pane["action"]) <= severity_index("CONSTRAIN")

    def test_stripping_context_changes_the_decision(self, panes):
        before = panes["with_context_decision_support"]["action"]
        after = panes["without_context_decision_support"]["action"]
        assert before != after, (
            "removing the source left the decision unchanged, so the screen "
            "demonstrates nothing"
        )


class TestScreen4Compounding:
    """Constant per-turn risk, changing action."""

    @pytest.fixture(scope="class")
    def data(self):
        resp = client.get("/demo/screen4")
        assert resp.status_code == 200
        return resp.json()

    def test_per_turn_risk_is_constant(self, data):
        """
        If P_def moved between turns the screen would prove nothing about
        compounding, only that the third turn happened to be riskier.
        """
        for track in data["tracks"].values():
            p_defs = {t["p_def"] for t in track["turns"]}
            assert len(p_defs) == 1, f"per-turn P_def varied: {p_defs}"

    def test_effective_risk_rises(self, data):
        for track in data["tracks"].values():
            p_effs = [t["p_def_effective"] for t in track["turns"]]
            assert p_effs[1] > p_effs[0]
            assert p_effs[2] > p_effs[1]

    def test_session_risk_carries_between_turns(self, data):
        for track in data["tracks"].values():
            turns = track["turns"]
            assert turns[0]["session_risk_before"] == 0.0
            for prev, curr in zip(turns, turns[1:]):
                assert curr["session_risk_before"] > 0.0
                assert curr["session_risk_before"] == pytest.approx(
                    prev["session_risk_after"], abs=1e-9
                )

    def test_action_changes_from_carry_alone(self, data):
        """The demonstrable claim: the action escalates without the turn getting riskier."""
        for wid, track in data["tracks"].items():
            actions = [t["action"] for t in track["turns"]]
            assert len(set(actions)) > 1, (
                f"{wid} never changed action across the conversation: {actions}"
            )

    def test_crossing_is_on_turn_three(self, data):
        """Turns 1 and 2 clear their bar individually; turn 3 does not."""
        for wid, track in data["tracks"].items():
            assert track["first_action_change_turn"] == 3, (
                f"{wid} changed action on turn "
                f"{track['first_action_change_turn']}, expected turn 3"
            )

    def test_severity_only_rises(self, data):
        for track in data["tracks"].values():
            indices = [severity_index(t["action"]) for t in track["turns"]]
            assert indices == sorted(indices)

    def test_decision_support_reaches_a_human(self, data):
        """Compounding must be able to reach ESCALATE, not just HOLD."""
        actions = [t["action"] for t in data["tracks"]["decision_support"]["turns"]]
        assert "ESCALATE" in actions


class TestScreen2ThresholdComparison:
    """Both operating points measured on the same labelled set by the real engine."""

    @pytest.fixture(scope="class")
    def data(self):
        resp = client.get("/demo/screen2?global_threshold=0.08")
        assert resp.status_code == 200
        return resp.json()

    def test_full_sim_set_scored(self, data):
        assert data["total_sim_samples"] == 3000
        assert data["defect_count"] > 0

    def test_curve_is_a_real_frontier(self, data):
        """
        EDR must rise and UIR must fall as the threshold rises. The old
        implementation substituted a two-point stand-in for the detector, which
        produced a step function with no tradeoff anywhere along it.
        """
        curve = data["curve"]
        edrs = [r["edr"] for r in curve]
        uirs = [r["uir"] for r in curve]
        assert edrs == sorted(edrs), "EDR must be non-decreasing in threshold"
        assert uirs == sorted(uirs, reverse=True), "UIR must be non-increasing"
        assert edrs[-1] > edrs[0], "EDR never moved across the whole sweep"
        assert uirs[0] > uirs[-1], "UIR never moved across the whole sweep"

    def test_curve_has_real_resolution(self, data):
        """A frontier needs more than a couple of distinct operating points."""
        distinct = {(r["edr"], r["uir"]) for r in data["curve"]}
        assert len(distinct) >= 8, (
            f"only {len(distinct)} distinct operating points, the curve is "
            "degenerate rather than a frontier"
        )

    def test_both_metrics_always_reported(self, data):
        """EDR and UIR are never displayed alone."""
        for point in (
            data["global_operating_point"],
            data["derived_operating_point"],
            data["edr_matched_global_point"],
        ):
            assert "edr" in point and "uir" in point
        for row in data["curve"]:
            assert "edr" in row and "uir" in row

    def test_uir_is_not_hardcoded_zero(self, data):
        assert data["global_operating_point"]["uir"] > 0.0

    def test_derived_reallocates_toward_consequence(self, data):
        """
        The actual mechanism. Per workflow, derived thresholds must spend fewer
        unnecessary interventions on the low-consequence copilot and more on
        high-consequence decision support than one global threshold does.
        """
        per_wf = data["per_workflow"]
        copilot = per_wf["internal_copilot"]
        decision = per_wf["decision_support"]
        assert copilot["derived"]["uir"] < copilot["global"]["uir"]
        assert decision["derived"]["uir"] > decision["global"]["uir"]

    def test_detectors_labelled_as_simulated(self, data):
        assert data["detectors"] == "simulated"

    def test_scoring_is_deterministic(self):
        a = client.get("/demo/screen2?global_threshold=0.13").json()
        b = client.get("/demo/screen2?global_threshold=0.13").json()
        assert a["curve"] == b["curve"]
        assert a["derived_operating_point"] == b["derived_operating_point"]
