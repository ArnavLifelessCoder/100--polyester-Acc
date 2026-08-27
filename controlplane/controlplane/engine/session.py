"""
Session risk state for multi-turn and agentic compounding.

Risk allowed through at turn t contaminates the context that later turns
condition on. Three marginal turns that each individually clear the threshold
will together push the fourth over it.

From annex section 3.6 and build guide section 5.5.
"""

from __future__ import annotations

from constants import GAMMA, BETA


def effective_p(
    p_def_now: float,
    s_prev: float,
    beta: float = BETA,
) -> float:
    """
    Effective defect probability including carried session risk.

    P_eff = 1 - (1 - P_def) * (1 - beta * s_prev)
    """
    return 1.0 - (1.0 - p_def_now) * (1.0 - beta * s_prev)


def update_session(
    s_prev: float,
    rho_action: float,
    p_eff: float,
    gamma: float = GAMMA,
) -> float:
    """
    Update session risk state after a decision.

    s_t = 1 - (1 - gamma * s_prev) * (1 - rho(action) * P_eff)

    An ALLOWed risky turn contributes fully (rho=1).
    A BLOCKed turn contributes nothing (rho=0).
    """
    return 1.0 - (1.0 - gamma * s_prev) * (1.0 - rho_action * p_eff)


class SessionStore:
    """
    In-memory session risk state store.

    Keyed by session_id. Adequate for the prototype.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, float] = {}

    def get(self, session_id: str | None) -> float:
        if session_id is None:
            return 0.0
        return self._sessions.get(session_id, 0.0)

    def set(self, session_id: str | None, value: float) -> None:
        if session_id is not None:
            self._sessions[session_id] = value

    def clear(self) -> None:
        self._sessions.clear()
