"""
Calibration module -- isotonic regression, ECE, and kappa/lambda estimation.

Calibration is fitted per workflow-detector pair. ECE < 0.05 is the gate
before a policy may move from advisory to enforcing.

From build guide section 8, step 14.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

# Below this many adjudicated decisions a fit is not attempted. A monotone map
# estimated from a handful of labels will track their noise.
MIN_LABELS_FOR_FIT: int = 50


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Compute Expected Calibration Error.

    ECE = sum_b (n_b / N) * |acc(b) - conf(b)|
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    n = len(y_true)
    if n == 0:
        return 0.0

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        mask = (y_prob > bins[i]) & (y_prob <= bins[i + 1])
        if i == 0:
            mask = (y_prob >= bins[i]) & (y_prob <= bins[i + 1])
        n_b = np.sum(mask)
        if n_b == 0:
            continue
        acc = np.mean(y_true[mask])
        conf = np.mean(y_prob[mask])
        ece += (n_b / n) * abs(acc - conf) 

    return float(ece)


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """BS = (1/N) * sum((p_i - y_i)^2)"""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    return float(np.mean((y_prob - y_true) ** 2))


def isotonic_calibrate(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> Any:
    """
    Fit isotonic regression for calibration.

    Returns a fitted IsotonicRegression object that can transform
    raw probabilities to calibrated ones.
    """
    try:
        from sklearn.isotonic import IsotonicRegression
    except ImportError:
        # Fallback: return identity
        class Identity:
            def transform(self, x):
                return np.asarray(x)
        return Identity()

    ir = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    ir.fit(y_prob, y_true)
    return ir


def estimate_kappa(
    labels: np.ndarray,
    tag_a_flags: np.ndarray,
    tag_b_flags: np.ndarray,
) -> float:
    """
    Estimate kappa (independence factor) from observed co-occurrence.

    kappa = clip(observed_co_occurrence / expected_under_independence, 0, 1)
    """
    n = len(labels)
    if n == 0:
        return 0.5

    p_a = np.mean(tag_a_flags)
    p_b = np.mean(tag_b_flags)
    expected_joint = p_a * p_b

    if expected_joint == 0:
        return 0.0

    observed_joint = np.mean(tag_a_flags & tag_b_flags)
    return float(np.clip(observed_joint / expected_joint, 0.0, 1.0))


def estimate_lambda(
    incident_costs: list[float],
    single_tag_costs: list[float],
) -> float:
    """
    Estimate lambda (joint consequence discount) from adjudicated incident costs.

    lambda is the fraction of the second tag's cost that applies when
    both tags fire together. Estimated from comparing joint incidents
    to single-tag incidents.
    """
    if not incident_costs or not single_tag_costs:
        return 0.3  # default from A9

    avg_joint = np.mean(incident_costs)
    avg_single = np.mean(single_tag_costs)

    if avg_single == 0:
        return 0.3

    # lambda approximation: joint cost / (2 * single cost) - 0.5
    # clamped to [0, 1]
    ratio = avg_joint / (2 * avg_single)
    return float(np.clip(ratio, 0.0, 1.0))


# --- Applied calibration ---
#
# Everything above measures calibration. This section applies it.
#
# The engine's arithmetic is only as good as the probabilities fed into it. A
# detector reporting 0.086 on traffic that is 1.3% defective will, under a large
# consequence, justify holding almost everything. The fix is not to move the
# thresholds, which would break the consequence model. The fix is to correct the
# probability.


@dataclass
class CalibrationFit:
    """What a fit learned, and how well it did on data it did not see."""

    fitted: bool
    n_train: int
    n_test: int
    ece_train_raw: float
    ece_test_raw: float
    ece_test_calibrated: float
    brier_test_raw: float
    brier_test_calibrated: float
    base_rate: float
    mean_raw: float
    mean_calibrated: float
    gate: float
    passes_gate_raw: bool
    passes_gate_calibrated: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class IsotonicCalibrator:
    """
    Monotone map from reported probability to corrected probability.

    Isotonic regression is used rather than Platt scaling because it assumes
    only that a higher reported score means a higher true defect rate, which is
    the one property a detector must have to be usable at all. It does not
    assume any particular shape.

    Fitting and scoring are always on disjoint splits. A calibration map
    evaluated on the data it was fitted to reports its own training error, which
    for isotonic regression is close to zero by construction and means nothing.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self.fit_info: CalibrationFit | None = None

    @property
    def fitted(self) -> bool:
        return self._model is not None

    def fit(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        test_fraction: float = 0.3,
        seed: int = 42,
        gate: float = 0.05,
    ) -> CalibrationFit:
        """
        Fit on a training split and report performance on the held-out split.

        Returns the fit summary. Raises ValueError when there is not enough
        labelled data, or when the labels contain only one class, in which case
        there is nothing for a monotone map to learn.
        """
        y_true = np.asarray(y_true, dtype=float)
        y_prob = np.asarray(y_prob, dtype=float)
        n = len(y_true)

        if n < MIN_LABELS_FOR_FIT:
            raise ValueError(
                f"need at least {MIN_LABELS_FOR_FIT} labelled decisions to fit, got {n}"
            )
        if len(np.unique(y_true)) < 2:
            raise ValueError(
                "labelled data contains only one class, so calibration cannot be fitted"
            )

        rng = np.random.default_rng(seed)
        order = rng.permutation(n)
        n_test = max(1, int(round(n * test_fraction)))
        test_idx, train_idx = order[:n_test], order[n_test:]

        y_train, p_train = y_true[train_idx], y_prob[train_idx]
        y_test, p_test = y_true[test_idx], y_prob[test_idx]

        model = isotonic_calibrate(y_train, p_train)
        p_test_cal = np.asarray(model.transform(p_test), dtype=float)

        ece_test_raw = expected_calibration_error(y_test, p_test)
        ece_test_cal = expected_calibration_error(y_test, p_test_cal)

        info = CalibrationFit(
            fitted=True,
            n_train=int(len(train_idx)),
            n_test=int(len(test_idx)),
            ece_train_raw=round(expected_calibration_error(y_train, p_train), 4),
            ece_test_raw=round(ece_test_raw, 4),
            ece_test_calibrated=round(ece_test_cal, 4),
            brier_test_raw=round(brier_score(y_test, p_test), 4),
            brier_test_calibrated=round(brier_score(y_test, p_test_cal), 4),
            base_rate=round(float(y_true.mean()), 4),
            mean_raw=round(float(p_test.mean()), 4),
            mean_calibrated=round(float(p_test_cal.mean()), 4),
            gate=gate,
            passes_gate_raw=bool(ece_test_raw < gate),
            passes_gate_calibrated=bool(ece_test_cal < gate),
        )

        self._model = model
        self.fit_info = info
        return info

    def transform(self, p: float) -> float:
        """Correct one probability. Identity when nothing is fitted."""
        if self._model is None:
            return float(p)
        value = float(np.asarray(self._model.transform([float(p)]))[0])
        return float(min(1.0, max(0.0, value)))

    def transform_many(self, probs: np.ndarray) -> np.ndarray:
        if self._model is None:
            return np.asarray(probs, dtype=float)
        out = np.asarray(self._model.transform(np.asarray(probs, dtype=float)))
        return np.clip(out, 0.0, 1.0)

    def clear(self) -> None:
        self._model = None
        self.fit_info = None

    def status(self) -> dict[str, Any]:
        return {
            "fitted": self.fitted,
            "fit": self.fit_info.as_dict() if self.fit_info else None,
        }


def reliability_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> list[dict[str, float]]:
    """
    Points for a reliability diagram.

    Each bin reports the mean reported probability against the observed defect
    rate for the decisions in it. A perfectly calibrated detector puts every
    point on the diagonal. A point above the diagonal means the detector claimed
    more risk than the data contained, which is the overconfidence that drives
    unnecessary intervention.

    Empty bins are omitted rather than plotted at zero, which would draw a line
    through territory no decision occupies.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) == 0:
        return []

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    points: list[dict[str, float]] = []

    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob > lo) & (y_prob <= hi) if i else (y_prob >= lo) & (y_prob <= hi)
        count = int(np.sum(mask))
        if count == 0:
            continue
        points.append({
            "bin_lower": round(float(lo), 4),
            "bin_upper": round(float(hi), 4),
            "mean_predicted": round(float(np.mean(y_prob[mask])), 4),
            "observed_rate": round(float(np.mean(y_true[mask])), 4),
            "count": count,
        })

    return points


# Process-wide active calibrator. The engine consults this when adjudicating.
_active = IsotonicCalibrator()


def get_calibrator() -> IsotonicCalibrator:
    return _active
