"""
Simulated detector with dial-controlled TPR and FPR.

Build this first, before any real detector. Everything downstream develops
against it. The dashboard exposes tpr and fpr sliders.

From build guide section 6.5:
  If label is True:  p_hat ~ Beta shaped to give P(p_hat > 0.5) = tpr
  If label is False: p_hat ~ Beta shaped to give P(p_hat > 0.5) = fpr
  measured_precision computed analytically from (tpr, fpr, workflow base rate)
"""

from __future__ import annotations

import time

import numpy as np

from controlplane.schemas import DetectorOutput, DetectionContext, RiskTag


class SimulatedDetector:
    """
    Reads the injected ground-truth label and emits a probability consistent
    with configurable TPR and FPR.

    The rng is seeded per-instance for determinism. The p_hat distribution
    uses a shifted Beta that concentrates mass above or below 0.5 according
    to the label and the dial settings.
    """

    def __init__(
        self,
        detector_id: str,
        tag: RiskTag,
        tier: int = 1,
        tpr: float = 0.80,
        fpr: float = 0.05,
        base_rate: float = 0.025,
        seed: int = 42,
    ) -> None:
        self.detector_id = detector_id
        self.tag = tag
        self.tier = tier
        self.tpr = tpr
        self.fpr = fpr
        self.base_rate = base_rate
        self._rng = np.random.default_rng(seed)

    @property
    def measured_precision(self) -> float:
        """Analytical precision from (tpr, fpr, base_rate)."""
        tp = self.tpr * self.base_rate
        fp = self.fpr * (1.0 - self.base_rate)
        denom = tp + fp
        if denom == 0:
            return 0.0
        return tp / denom

    def set_dial(self, tpr: float, fpr: float) -> None:
        """Update the detector's operating point."""
        self.tpr = max(0.0, min(1.0, tpr))
        self.fpr = max(0.0, min(1.0, fpr))

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        start = time.perf_counter()

        is_defective = ctx.ground_truth_label is True and self.tag in ctx.ground_truth_tags

        # Each branch draws from a Beta shaped to sit in the correct half of the
        # unit interval, so P(p_hat > 0.5) is exactly tpr or fpr as configured.
        #
        # The shapes matter as much as the split. Drawing the below-0.5 cases
        # uniformly, as an earlier version did, gives clean traffic a mean score
        # of 0.25 against a base rate near 0.02. That is not a detector with a
        # 5% false positive rate, it is a detector that is uncalibrated by an
        # order of magnitude, and every threshold study run on top of it reports
        # an unnecessary intervention rate near 100%. True negatives concentrate
        # near zero instead, which is what a calibrated probability looks like.
        if is_defective:
            if float(self._rng.random()) < self.tpr:
                # True positive: confident, concentrated near 1.
                p_hat = 0.5 + 0.5 * float(self._rng.beta(3.0, 1.0))
            else:
                # False negative: missed, so the score sits mid-to-low.
                p_hat = 0.5 * float(self._rng.beta(2.0, 2.0))
        else:
            if float(self._rng.random()) < self.fpr:
                # False positive: over 0.5 but rarely emphatic.
                p_hat = 0.5 + 0.5 * float(self._rng.beta(1.0, 3.0))
            else:
                # True negative: concentrated near zero, close to the base rate.
                p_hat = 0.5 * float(self._rng.beta(1.0, 30.0))

        p_hat = max(0.0, min(1.0, p_hat))

        elapsed = (time.perf_counter() - start) * 1000.0

        return DetectorOutput(
            detector_id=self.detector_id,
            tag=self.tag,
            p_hat=round(p_hat, 6),
            verifiable=True,
            measured_precision=round(self.measured_precision, 4),
            tier=self.tier,
            latency_ms=round(elapsed, 3),
            evidence={
                "simulated": True,
                "tpr": self.tpr,
                "fpr": self.fpr,
                "ground_truth": is_defective,
            },
        )
