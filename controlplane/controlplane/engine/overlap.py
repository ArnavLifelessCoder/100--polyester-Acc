"""
Overlap model for correlated risk tags.

Implements P_def and C_eff from annex section 3.4. Tags are not mutually
exclusive, so naive summing or maxing both mislead. The kappa parameter
controls assumed independence between tag pairs.
"""

from __future__ import annotations

from controlplane.schemas import ConsequenceModel, RiskTag, RISK_TAGS


def _kappa_key(tag_a: RiskTag, tag_b: RiskTag) -> str:
    """Canonical key for a tag pair -- order-independent."""
    return "|".join(sorted([tag_a, tag_b]))


def p_def(
    p_hats: dict[RiskTag, float],
    kappa: dict[str, float],
) -> float:
    """
    Composite defect probability under the overlap model.

    m = argmax tag by p_hat
    P = p_m + (1 - p_m) * (1 - prod_{d != m} (1 - kappa(m,d) * p_d))

    At kappa=0 for all pairs: returns max(p_hats).
    At kappa=1 for all pairs: returns 1 - prod(1 - p_d).
    """
    if not p_hats:
        return 0.0

    # Find the dominant tag
    m = max(p_hats, key=lambda t: p_hats[t])
    p_m = p_hats[m]

    # Product over non-dominant tags
    product = 1.0
    for d in p_hats:
        if d == m:
            continue
        k = kappa.get(_kappa_key(m, d), 0.0)
        product *= 1.0 - k * p_hats[d]

    return p_m + (1.0 - p_m) * (1.0 - product)


def c_eff(
    p_hats: dict[RiskTag, float],
    consequence: ConsequenceModel,
    lam: float,
    trigger_threshold: float = 0.05,
) -> float:
    """
    Effective consequence under the overlap model.

    C = C_m + lam * sum(C_d for d != m where p_hat[d] > trigger_threshold)

    The trigger threshold prevents near-zero tags from adding consequence.
    """
    if not p_hats:
        return 0.0

    c_map = consequence.as_dict()
    m = max(p_hats, key=lambda t: p_hats[t])
    c_m = c_map[m]

    additional = 0.0
    for d in p_hats:
        if d == m:
            continue
        if p_hats[d] > trigger_threshold:
            additional += c_map[d]

    return c_m + lam * additional
