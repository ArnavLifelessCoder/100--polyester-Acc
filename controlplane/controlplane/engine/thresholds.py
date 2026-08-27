"""
Threshold reference values.

Two families live here and they are not interchangeable.

`p_star_escalate` and `p_star_block` are the closed forms from annex section
3.2. They are retained because the annex quotes them, but they are an
approximation: neither contains the irreversibility factor iota, and neither
contains the (1 - p) * U(a) term that the engine actually minimises. They must
not be used to describe what the engine will do.

`action_thresholds` derives the real switching points directly from the same
L(a) the engine minimises in decide.py, so the two agree by construction.
This is what the UI, the README, and the demo screens must quote.

The gap between the two families is wide enough to matter. For support_chatbot
the closed form puts the block point at 0.078 while the engine actually blocks
at 0.265.
"""

from __future__ import annotations

from controlplane.schemas import ACTIONS, Action, Policy
from controlplane.engine.severity import severity_index
from constants import (
    HUMAN_REVIEW_COST,
    HUMAN_CATCH_RATE,
    FRICTION_BLOCK,
    UTILITY_LOSS_BLOCK,
)


def p_star_escalate(
    c: float,
    h: float = HUMAN_REVIEW_COST,
    a_h: float = HUMAN_CATCH_RATE,
) -> float:
    """
    Annex 3.2 closed form: p*_esc = H / (a_h * C).

    Reference only. Ignores iota and the utility-loss term, so it does not
    predict the engine's escalation point. Use `action_thresholds`.
    """
    if c <= 0 or a_h <= 0:
        raise ValueError("consequence and catch rate must be positive")
    return h / (a_h * c)


def p_star_block(
    c: float,
    f_b: float = FRICTION_BLOCK,
    u: float = UTILITY_LOSS_BLOCK,
) -> float:
    """
    Annex 3.2 closed form: p*_block = (F_b + U) / (C + U).

    Reference only. Same caveat as `p_star_escalate`.
    """
    if (c + u) <= 0:
        raise ValueError("C + U must be positive")
    return (f_b + u) / (c + u)


def loss_line(policy: Policy, action: Action, c_eff: float) -> tuple[float, float]:
    """
    Return (slope, intercept) of L(a) as a function of p.

    The engine computes
        L(a) = rho(a) * p * C_eff * iota + F(a) + (1 - p) * U(a)
    which is linear in p:
        L(a) = p * (rho(a) * C_eff * iota - U(a)) + (F(a) + U(a))

    Keeping this in one place is what lets the thresholds agree with decide().
    """
    rho = policy.residual[action]
    f = policy.friction[action]
    u = policy.utility_loss[action]
    slope = rho * c_eff * policy.irreversibility - u
    intercept = f + u
    return slope, intercept


def _argmin_at(policy: Policy, c_eff: float, p: float) -> Action:
    """Argmin of L(a) at a single p, with ties resolved to lower severity."""
    losses = {}
    for a in ACTIONS:
        slope, intercept = loss_line(policy, a, c_eff)
        losses[a] = slope * p + intercept
    lowest = min(losses.values())
    tied = [a for a in ACTIONS if losses[a] <= lowest + 1e-12]
    return min(tied, key=severity_index)


def action_thresholds(
    policy: Policy,
    c_eff: float | None = None,
) -> list[tuple[float, Action]]:
    """
    Exact switching points of the engine's argmin over p in [0, 1].

    Returns an ordered list of (p_start, action): the action is the argmin for
    every p from p_start up to the next entry's p_start. The first entry always
    starts at 0.0.

    Because every L(a) is linear in p, the argmin is the lower envelope of five
    lines and every switching point is a pairwise crossing. Those are computed
    exactly rather than scanned, so this cannot drift from decide().

    `c_eff` defaults to the policy's own dominant consequence, which is the
    single-tag case the reference tables describe.
    """
    if c_eff is None:
        c_eff = max(policy.consequence.as_dict().values())

    lines = {a: loss_line(policy, a, c_eff) for a in ACTIONS}

    # Candidate breakpoints: every pairwise crossing that lands inside (0, 1).
    breaks: set[float] = set()
    for i, a in enumerate(ACTIONS):
        for b in ACTIONS[i + 1:]:
            m_a, b_a = lines[a]
            m_b, b_b = lines[b]
            if abs(m_a - m_b) < 1e-15:
                continue
            p = (b_b - b_a) / (m_a - m_b)
            if 0.0 < p < 1.0:
                breaks.add(p)

    edges = [0.0] + sorted(breaks) + [1.0]

    segments: list[tuple[float, Action]] = []
    for start, end in zip(edges, edges[1:]):
        mid = (start + end) / 2.0
        action = _argmin_at(policy, c_eff, mid)
        if not segments or segments[-1][1] != action:
            segments.append((start, action))

    return segments


def first_p_for_action(
    policy: Policy,
    action: Action,
    c_eff: float | None = None,
) -> float | None:
    """
    Lowest p at which `action` becomes the engine's argmin, or None if it never
    does. An action that never appears is dominated under this policy's
    economics, which is a fact worth surfacing rather than hiding.
    """
    for p_start, act in action_thresholds(policy, c_eff):
        if act == action:
            return p_start
    return None
