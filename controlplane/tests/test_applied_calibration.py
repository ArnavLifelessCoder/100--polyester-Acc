"""
Applied calibration, the honest detector dial, and the agentic screen.

Calibration used to be measured and thrown away. It is now fitted on a training
split, scored on held-out data, and applied inside decide(). The detector dial
used to POST a value that changed nothing any screen displayed. The reachability
mechanism worked and was tested but had no way to be seen.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.api import app
from controlplane.calibration import (
    MIN_LABELS_FOR_FIT,
    IsotonicCalibrator,
    expected_calibration_error,
    get_calibrator,
    reliability_curve,
)
from controlplane.engine.decide import decide, get_session_store
from controlplane.policy import load_all_policies
from controlplane.schemas import DetectorOutput, RiskVector

client = TestClient(app)
POLICIES = load_all_policies(Path(__file__).resolve().parent.parent / "policies")


def _overconfident(n: int = 800, base: float = 0.013, seed: int = 0):
    """Labels plus scores that overstate risk on clean traffic, as ours do."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < base).astype(float)
    p = np.where(y > 0, rng.beta(3, 1, n), rng.beta(1, 12, n))
    return y, np.clip(p, 0.0, 1.0)


class TestIsotonicCalibrator:
    def test_fit_scores_on_held_out_data(self):
        y, p = _overconfident()
        fit = IsotonicCalibrator().fit(y, p)
        assert fit.n_train + fit.n_test == len(y)
        assert fit.n_test > 0 and fit.n_train > 0

    def test_calibration_reduces_held_out_ece(self):
        y, p = _overconfident()
        fit = IsotonicCalibrator().fit(y, p)
        assert fit.ece_test_calibrated < fit.ece_test_raw

    def test_calibration_pulls_mean_toward_the_base_rate(self):
        """
        The failure being corrected is a reported mean far above the true rate.
        """
        y, p = _overconfident()
        fit = IsotonicCalibrator().fit(y, p)
        assert abs(fit.mean_calibrated - fit.base_rate) < abs(fit.mean_raw - fit.base_rate)

    def test_gate_can_flip(self):
        y, p = _overconfident()
        fit = IsotonicCalibrator().fit(y, p, gate=0.05)
        assert fit.passes_gate_raw is False
        assert fit.passes_gate_calibrated is True

    def test_refuses_to_fit_on_too_few_labels(self):
        y, p = _overconfident(n=MIN_LABELS_FOR_FIT - 1)
        with pytest.raises(ValueError, match="at least"):
            IsotonicCalibrator().fit(y, p)

    def test_refuses_to_fit_on_one_class(self):
        y = np.zeros(200)
        p = np.linspace(0, 1, 200)
        with pytest.raises(ValueError, match="one class"):
            IsotonicCalibrator().fit(y, p)

    def test_unfitted_transform_is_identity(self):
        c = IsotonicCalibrator()
        assert c.fitted is False
        assert c.transform(0.37) == pytest.approx(0.37)

    def test_transform_stays_in_range(self):
        y, p = _overconfident()
        c = IsotonicCalibrator()
        c.fit(y, p)
        for v in (0.0, 0.25, 0.5, 0.99, 1.0):
            assert 0.0 <= c.transform(v) <= 1.0

    def test_clear_restores_identity(self):
        y, p = _overconfident()
        c = IsotonicCalibrator()
        c.fit(y, p)
        c.clear()
        assert c.fitted is False
        assert c.transform(0.37) == pytest.approx(0.37)


class TestReliabilityCurve:
    def test_empty_bins_are_omitted(self):
        """Plotting an empty bin at zero draws a line through nothing."""
        y = np.array([0.0, 1.0, 0.0, 1.0])
        p = np.array([0.01, 0.02, 0.01, 0.02])
        points = reliability_curve(y, p, n_bins=10)
        assert len(points) == 1
        assert all(pt["count"] > 0 for pt in points)

    def test_perfect_detector_sits_on_the_diagonal(self):
        rng = np.random.default_rng(3)
        p = rng.random(4000)
        y = (rng.random(4000) < p).astype(float)
        for pt in reliability_curve(y, p):
            assert abs(pt["mean_predicted"] - pt["observed_rate"]) < 0.08


class TestCalibrationAppliedInEngine:
    def setup_method(self):
        get_calibrator().clear()
        get_session_store().clear()

    def teardown_method(self):
        get_calibrator().clear()

    def _risk(self, p: float) -> RiskVector:
        def det(tag, p_hat):
            return DetectorOutput(
                detector_id=f"t_{tag}", tag=tag, p_hat=p_hat, verifiable=True,
                measured_precision=0.99, tier=1, latency_ms=1.0,
            )
        return RiskVector(per_tag={
            "performance": det("performance", p),
            "cost": det("cost", 0.0),
            "responsibility": det("responsibility", 0.0),
        })

    def test_engine_is_unaffected_until_a_map_is_fitted(self):
        d = decide(self._risk(0.4), POLICIES["support_chatbot"], session_id=None)
        assert d.p_def == pytest.approx(0.4, abs=1e-6)
        assert "CALIBRATED" not in d.reason_codes

    def test_fitted_map_moves_p_def_and_is_recorded(self):
        y, p = _overconfident()
        get_calibrator().fit(y, p)
        get_session_store().clear()
        d = decide(self._risk(0.4), POLICIES["support_chatbot"], session_id=None)
        assert d.p_def != pytest.approx(0.4, abs=1e-6)
        assert "CALIBRATED" in d.reason_codes

    def test_correcting_overconfidence_reduces_intervention(self):
        """
        The whole point. An overconfident probability under a large consequence
        buys interventions that the true rate does not justify.
        """
        policy = POLICIES["decision_support"]
        get_session_store().clear()
        before = decide(self._risk(0.09), policy, session_id=None)

        y, p = _overconfident()
        get_calibrator().fit(y, p)
        get_session_store().clear()
        after = decide(self._risk(0.09), policy, session_id=None)

        assert after.p_def < before.p_def
        from controlplane.engine.severity import severity_index
        assert severity_index(after.action) <= severity_index(before.action)


class TestCalibrationEndpoints:
    def teardown_method(self):
        client.post("/admin/calibration/clear")

    def test_screen5_reports_held_out_numbers(self):
        data = client.get("/demo/screen5").json()
        if not data["sufficient"]:
            pytest.skip("ledger has too few labels; run python -m sim.seed_data")
        fit = data["fit"]
        assert fit["n_test"] > 0
        assert fit["ece_test_calibrated"] <= fit["ece_test_raw"]

    def test_screen5_shows_before_and_after_rates(self):
        data = client.get("/demo/screen5").json()
        if not data["sufficient"]:
            pytest.skip("too few labels")
        for block in (data["rates_before"], data["rates_after"]):
            assert "edr" in block and "uir" in block

    def test_calibration_cuts_unnecessary_interventions(self):
        data = client.get("/demo/screen5").json()
        if not data["sufficient"]:
            pytest.skip("too few labels")
        assert data["rates_after"]["uir"] < data["rates_before"]["uir"]

    def test_stage_ladder_gates_enforcing_on_ece(self):
        data = client.get("/demo/screen5").json()
        if not data["sufficient"]:
            pytest.skip("too few labels")
        enforcing = next(s for s in data["stage_ladder"] if s["stage"] == "enforcing")
        assert enforcing["reached"] == data["fit"]["passes_gate_raw"]

    def test_inspecting_screen5_does_not_activate_the_map(self):
        """Reading a diagnostic must not change what the live engine does."""
        client.post("/admin/calibration/clear")
        client.get("/demo/screen5")
        assert get_calibrator().fitted is False

    def test_fit_then_clear_round_trip(self):
        resp = client.post("/admin/calibration/fit")
        if resp.status_code == 400:
            pytest.skip("not enough labels in the ledger")
        assert resp.status_code == 200
        assert get_calibrator().fitted is True
        assert client.post("/admin/calibration/clear").status_code == 200
        assert get_calibrator().fitted is False


class TestDetectorDial:
    """The dial must actually change what the engine does."""

    def test_quality_endpoint_scores_the_set(self):
        d = client.get("/demo/detector_quality?tpr=0.8&fpr=0.05").json()
        assert d["samples"] > 0
        assert d["simulated"] is True

    def test_worse_detectors_lower_measured_precision(self):
        good = client.get("/demo/detector_quality?tpr=0.95&fpr=0.01").json()
        bad = client.get("/demo/detector_quality?tpr=0.20&fpr=0.50").json()
        assert bad["measured_precision"] < good["measured_precision"]

    def test_worse_detectors_lower_the_severity_cap(self):
        from controlplane.engine.severity import severity_index

        good = client.get("/demo/detector_quality?tpr=0.95&fpr=0.01").json()
        bad = client.get("/demo/detector_quality?tpr=0.20&fpr=0.50").json()
        assert severity_index(bad["severity_cap"]) < severity_index(good["severity_cap"])

    def test_degradation_slides_toward_hold_not_toward_blocks(self):
        """
        The required behaviour: a mediocre detector produces logging, not wrong
        blocks.
        """
        good = client.get("/demo/detector_quality?tpr=0.95&fpr=0.01").json()
        bad = client.get("/demo/detector_quality?tpr=0.20&fpr=0.50").json()

        def share(d, action):
            total = sum(d["action_distribution"].values()) or 1
            return d["action_distribution"].get(action, 0) / total

        assert share(bad, "HOLD") > share(good, "HOLD")
        assert share(bad, "ALLOW") < share(good, "ALLOW")
        assert share(bad, "BLOCK") <= share(good, "BLOCK") + 1e-9

    def test_dial_is_deterministic(self):
        a = client.get("/demo/detector_quality?tpr=0.6&fpr=0.2").json()
        b = client.get("/demo/detector_quality?tpr=0.6&fpr=0.2").json()
        assert a["action_distribution"] == b["action_distribution"]


class TestAgenticScreen:
    @pytest.fixture(scope="class")
    def data(self):
        resp = client.get("/demo/screen6")
        assert resp.status_code == 200
        return resp.json()

    def test_risk_vector_is_constant_across_variants(self, data):
        """
        If P_def moved, the screen would not be showing anything about
        consequence.
        """
        p_defs = {v["p_def"] for v in data["variants"].values()}
        assert len(p_defs) == 1

    def test_consequence_rises_with_what_the_step_can_reach(self, data):
        v = data["variants"]
        assert v["text_only"]["c_eff"] < v["plan_note"]["c_eff"] < v["plan_refund"]["c_eff"]

    def test_three_distinct_verdicts(self, data):
        assert len(data["distinct_actions"]) == 3

    def test_plain_text_is_allowed(self, data):
        assert data["variants"]["text_only"]["action"] == "ALLOW"

    def test_reaching_the_refund_api_forces_intervention(self, data):
        assert data["variants"]["plan_refund"]["action"] != "ALLOW"
        assert "REACHABILITY_CONSEQUENCE" in data["variants"]["plan_refund"]["reason_codes"]

    def test_effective_consequence_matches_the_formula(self, data):
        """C(tool) * P(reach) * iota(tool), maximised over reachable terminals."""
        v = data["variants"]["plan_refund"]
        best = max(t["effective"] for t in v["reachable_tools"])
        assert v["c_eff"] == pytest.approx(best, rel=1e-6)

    def test_plain_text_reaches_nothing(self, data):
        assert data["variants"]["text_only"]["reachable_tools"] == []
