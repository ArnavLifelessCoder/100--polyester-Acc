"""
Feedback loop, outcome metrics, calibration, and agentic reachability.

These four were all written and then never connected to anything:
  - calibration.py was imported by no module
  - the adjudicate endpoint accepted a human label and discarded it
  - /v1/metrics reported the intervention rate under the name EDR and
    hardcoded UIR to 0.0
  - engine/reachability.py was dead code, and the API accepted a tool_graph
    and dropped it

Each test here covers the wiring, not just the function.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.api import app
from controlplane.calibration import expected_calibration_error
from controlplane.engine.decide import decide, get_session_store
from controlplane.ledger import Ledger
from controlplane.policy import load_all_policies
from controlplane.schemas import DetectorOutput, RiskVector

client = TestClient(app)
POLICIES = load_all_policies(Path(__file__).resolve().parent.parent / "policies")


def _risk(p: float, precision: float = 0.99) -> RiskVector:
    def det(tag, p_hat):
        return DetectorOutput(
            detector_id=f"t_{tag}", tag=tag, p_hat=p_hat, verifiable=True,
            measured_precision=precision, tier=1, latency_ms=1.0,
        )
    return RiskVector(per_tag={
        "performance": det("performance", p),
        "cost": det("cost", 0.0),
        "responsibility": det("responsibility", 0.0),
    })


TOOL_GRAPH = {
    "refund_api": {
        "consequence": 250000.0,
        "iota": 1.0,
        "reachable_from": ["plan_step"],
        "p_reach": 0.6,
    },
    "draft_note": {
        "consequence": 500.0,
        "iota": 0.2,
        "reachable_from": ["plan_step", "other_step"],
        "p_reach": 0.9,
    },
}


class TestReachability:
    """An agent step is adjudicated at the consequence of what it can reach."""

    def test_no_tool_graph_uses_policy_consequence(self):
        get_session_store().clear()
        d = decide(_risk(0.05), POLICIES["internal_copilot"], session_id=None)
        assert d.c_eff == 800.0
        assert "REACHABILITY_CONSEQUENCE" not in d.reason_codes

    def test_reachable_tool_overrides_consequence(self):
        get_session_store().clear()
        d = decide(
            _risk(0.05), POLICIES["internal_copilot"], session_id=None,
            tool_graph=TOOL_GRAPH, step="plan_step",
        )
        # max over reachable terminals of C * p_reach * iota
        assert d.c_eff == pytest.approx(250000.0 * 0.6 * 1.0)
        assert "REACHABILITY_CONSEQUENCE" in d.reason_codes

    def test_reaching_a_dangerous_tool_changes_the_action(self):
        """
        The claim worth demonstrating: identical text, identical risk vector,
        different verdict because of what the step can cause.
        """
        get_session_store().clear()
        plain = decide(_risk(0.05), POLICIES["internal_copilot"], session_id=None)
        get_session_store().clear()
        agentic = decide(
            _risk(0.05), POLICIES["internal_copilot"], session_id=None,
            tool_graph=TOOL_GRAPH, step="plan_step",
        )
        assert plain.action == "ALLOW"
        assert agentic.action != "ALLOW"

    def test_step_reaching_nothing_falls_through(self):
        get_session_store().clear()
        d = decide(
            _risk(0.05), POLICIES["internal_copilot"], session_id=None,
            tool_graph=TOOL_GRAPH, step="unconnected_step",
        )
        assert d.c_eff == 800.0

    def test_low_consequence_tool_does_not_inflate(self):
        get_session_store().clear()
        d = decide(
            _risk(0.05), POLICIES["internal_copilot"], session_id=None,
            tool_graph=TOOL_GRAPH, step="other_step",
        )
        assert d.c_eff == pytest.approx(500.0 * 0.9 * 0.2)
        assert "REACHABLE_TOOL_DOMINATES" not in d.reason_codes

    def test_api_accepts_and_uses_tool_graph(self):
        body = {
            "request": "plan a refund",
            "response": "I will process the refund now.",
            "workflow_id": "internal_copilot",
            "tool_graph": TOOL_GRAPH,
            "step": "plan_step",
        }
        resp = client.post("/v1/adjudicate", json=body)
        assert resp.status_code == 200
        assert "REACHABILITY_CONSEQUENCE" in resp.json()["reason_codes"]


class TestLabelPersistence:
    def _seed_decision(self) -> str:
        resp = client.post("/v1/adjudicate", json={
            "request": "q", "response": "an ordinary answer",
            "workflow_id": "support_chatbot",
        })
        assert resp.status_code == 200
        return resp.json()["decision_id"]

    def test_label_is_persisted(self):
        did = self._seed_decision()
        resp = client.post(
            f"/v1/decisions/{did}/adjudicate",
            json={"actually_defective": True, "note": "hallucinated the policy"},
        )
        assert resp.status_code == 200
        assert resp.json()["actually_defective"] is True

    def test_label_survives_a_reread(self):
        """The old endpoint returned success and stored nothing."""
        did = self._seed_decision()
        client.post(
            f"/v1/decisions/{did}/adjudicate",
            json={"actually_defective": True, "note": "n"},
        )
        # The same database the API writes to. conftest points this at a
        # throwaway copy so the suite never mutates the seeded ledger.
        ledger = Ledger(os.environ["CONTROLPLANE_DB"])
        try:
            stored = ledger.get_label(did)
        finally:
            ledger.close()
        assert stored is not None
        assert stored["actually_defective"] is True

    def test_label_does_not_break_the_hash_chain(self):
        """
        A verdict must not mutate the decision it refers to. If labels were
        columns on the decision row, writing one would invalidate every hash
        after it.
        """
        did = self._seed_decision()
        client.post(
            f"/v1/decisions/{did}/adjudicate",
            json={"actually_defective": False, "note": "fine"},
        )
        assert client.get("/v1/chain/verify").json()["valid"] is True

    def test_unknown_decision_is_rejected(self):
        resp = client.post(
            "/v1/decisions/does-not-exist/adjudicate",
            json={"actually_defective": True, "note": ""},
        )
        assert resp.status_code == 404

    def test_outcome_is_named(self):
        did = self._seed_decision()
        resp = client.post(
            f"/v1/decisions/{did}/adjudicate",
            json={"actually_defective": True, "note": ""},
        )
        assert resp.json()["outcome"] in {
            "escaped_defect", "unnecessary_intervention",
            "correct_intervention", "correct_allow",
        }


class TestOutcomeMetrics:
    @pytest.fixture(scope="class")
    def metrics(self):
        resp = client.get("/v1/metrics")
        assert resp.status_code == 200
        return resp.json()

    def test_traffic_and_quality_are_separated(self, metrics):
        assert "traffic" in metrics and "quality" in metrics

    def test_edr_and_uir_always_travel_together(self, metrics):
        for block in [metrics["quality"]] + [
            w["quality"] for w in metrics["per_workflow"].values()
        ]:
            assert ("edr" in block) and ("uir" in block)

    def test_uir_is_not_hardcoded_zero(self, metrics):
        """It was literally `uir=0.0,  # needs human labels`."""
        assert metrics["quality"]["uir"] is None or metrics["quality"]["uir"] > 0.0

    def test_edr_is_not_the_intervention_rate(self, metrics):
        """
        EDR counts escaped defects, which requires a label. The old code
        reported interventions/total under the name EDR, so it moved with
        friction rather than with error.
        """
        q, t = metrics["quality"], metrics["traffic"]
        if q["labelled_count"]:
            assert q["edr"] != round(t["intervention_rate"] * 10000, 1)

    def test_unlabelled_reports_none_not_zero(self):
        """Claiming a perfect EDR on no evidence is worse than reporting nothing."""
        from controlplane.api import _rate_metrics
        empty = _rate_metrics([])
        assert empty["edr"] is None and empty["uir"] is None
        assert empty["labelled_count"] == 0

    def test_latency_is_modelled_not_wall_clock(self, metrics):
        t = metrics["traffic"]
        assert t["latency_source"] == "modelled_tier_budgets"
        # Wall clock on in-process stubs reads about 0.05ms, which is not a
        # number anyone can plan capacity from.
        assert t["p50_latency_ms"] >= 10.0

    def test_telemetry_covers_the_brief(self, metrics):
        t = metrics["traffic"]
        for field in (
            "p50_latency_ms", "p95_latency_ms", "p99_latency_ms",
            "tier_fire_rate", "estimated_cost_units_per_decision",
            "action_distribution", "abstention_rate", "cap_bind_rate",
        ):
            assert field in t


class TestCalibration:
    def test_reports_calibration_from_labels(self):
        data = client.get("/v1/calibration").json()
        if not data["sufficient"]:
            pytest.skip("ledger has too few labels; run python -m sim.seed_data")
        assert 0.0 <= data["ece_raw"] <= 1.0
        assert "passes_enforcing_gate" in data

    def test_isotonic_reduces_ece(self):
        """Build guide step 14: the fit must improve calibration."""
        data = client.get("/v1/calibration").json()
        if not data["sufficient"]:
            pytest.skip("ledger has too few labels")
        assert data["ece_isotonic"] <= data["ece_raw"]

    def test_gate_matches_the_threshold(self):
        data = client.get("/v1/calibration").json()
        if not data["sufficient"]:
            pytest.skip("ledger has too few labels")
        assert data["passes_enforcing_gate"] == (data["ece_raw"] < data["ece_gate"])

    def test_insufficient_labels_is_stated_not_faked(self):
        data = client.get("/v1/calibration?workflow_id=internal_copilot").json()
        assert "sufficient" in data
        if not data["sufficient"]:
            assert "ece_raw" not in data

    def test_ece_detects_overconfidence(self):
        """A detector reporting 0.5 on traffic that is 1% defective is not calibrated."""
        y_true = np.zeros(1000)
        y_true[:10] = 1.0
        confident = np.full(1000, 0.5)
        honest = np.full(1000, 0.01)
        assert expected_calibration_error(y_true, confident) > 0.4
        assert expected_calibration_error(y_true, honest) < 0.02
