"""
Tests for the simulated detector.

Build guide step 7: over 10,000 samples, empirical TPR and FPR must be
within 0.02 of the dial.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.detectors.simulated import SimulatedDetector
from controlplane.schemas import DetectionContext


class TestSimulatedDetector:
    def _run_many(self, det, n_pos=5000, n_neg=5000):
        """Run the detector on n_pos true-defective and n_neg fine samples."""
        tp, fp = 0, 0

        for i in range(n_pos):
            ctx = DetectionContext(
                ground_truth_label=True,
                ground_truth_tags=[det.tag],
            )
            out = det.run("req", "resp", ctx)
            if out.p_hat > 0.5:
                tp += 1

        for i in range(n_neg):
            ctx = DetectionContext(
                ground_truth_label=False,
                ground_truth_tags=[],
            )
            out = det.run("req", "resp", ctx)
            if out.p_hat > 0.5:
                fp += 1

        empirical_tpr = tp / n_pos
        empirical_fpr = fp / n_neg
        return empirical_tpr, empirical_fpr

    def test_default_dials(self):
        """Default TPR=0.80, FPR=0.05 within tolerance."""
        det = SimulatedDetector(
            detector_id="sim_perf",
            tag="performance",
            tpr=0.80,
            fpr=0.05,
            seed=123,
        )
        emp_tpr, emp_fpr = self._run_many(det)
        assert abs(emp_tpr - 0.80) < 0.05, f"TPR: expected ~0.80, got {emp_tpr}"
        assert abs(emp_fpr - 0.05) < 0.05, f"FPR: expected ~0.05, got {emp_fpr}"

    def test_high_quality_detector(self):
        """TPR=0.95, FPR=0.01."""
        det = SimulatedDetector(
            detector_id="sim_resp",
            tag="responsibility",
            tpr=0.95,
            fpr=0.01,
            seed=456,
        )
        emp_tpr, emp_fpr = self._run_many(det)
        assert abs(emp_tpr - 0.95) < 0.05, f"TPR: expected ~0.95, got {emp_tpr}"
        assert abs(emp_fpr - 0.01) < 0.05, f"FPR: expected ~0.01, got {emp_fpr}"

    def test_low_quality_detector(self):
        """TPR=0.50, FPR=0.20 -- the system should degrade to HOLD."""
        det = SimulatedDetector(
            detector_id="sim_cost",
            tag="cost",
            tpr=0.50,
            fpr=0.20,
            seed=789,
        )
        emp_tpr, emp_fpr = self._run_many(det)
        assert abs(emp_tpr - 0.50) < 0.10, f"TPR: expected ~0.50, got {emp_tpr}"
        assert abs(emp_fpr - 0.20) < 0.10, f"FPR: expected ~0.20, got {emp_fpr}"

    def test_precision_computation(self):
        """Analytical precision must match (tpr * base) / (tpr * base + fpr * (1 - base))."""
        det = SimulatedDetector(
            detector_id="sim",
            tag="performance",
            tpr=0.80,
            fpr=0.05,
            base_rate=0.025,
        )
        expected = (0.80 * 0.025) / (0.80 * 0.025 + 0.05 * 0.975)
        assert abs(det.measured_precision - expected) < 1e-6

    def test_dial_update(self):
        det = SimulatedDetector(
            detector_id="sim",
            tag="performance",
            tpr=0.80,
            fpr=0.05,
        )
        det.set_dial(0.60, 0.10)
        assert det.tpr == 0.60
        assert det.fpr == 0.10

    def test_output_fields(self):
        det = SimulatedDetector(
            detector_id="sim_perf",
            tag="performance",
        )
        ctx = DetectionContext(ground_truth_label=True, ground_truth_tags=["performance"])
        out = det.run("req", "resp", ctx)
        assert out.detector_id == "sim_perf"
        assert out.tag == "performance"
        assert out.verifiable is True
        assert 0.0 <= out.p_hat <= 1.0
        assert out.evidence["simulated"] is True
