"""
Tests for session state compounding -- golden vectors from build guide section 7.

internal_copilot, four turns each with P_def = 0.10, gamma=0.85, beta=0.5:
  Turn 1: s_prev=0.0000, P_eff=0.1000, action=ALLOW
  Turn 2: s_prev=0.1000, P_eff=0.1450, action=ALLOW
  Turn 3: s_prev=0.2177 (approx), P_eff=0.1980 (approx), action=ESCALATE

Turn 3 crosses the copilot's p*_esc=0.16667 purely from carried risk.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.engine.session import effective_p, update_session, SessionStore


class TestEffectiveP:
    def test_no_carry(self):
        """With no prior session risk, P_eff equals P_def."""
        result = effective_p(0.10, 0.0)
        assert abs(result - 0.10) < 1e-6

    def test_turn2(self):
        """Turn 2: s_prev=0.10, P_def=0.10."""
        result = effective_p(0.10, 0.10, beta=0.5)
        # 1 - (1-0.10)(1 - 0.5*0.10) = 1 - 0.90 * 0.95 = 1 - 0.855 = 0.145
        assert abs(result - 0.145) < 1e-6, f"expected 0.145, got {result}"


class TestUpdateSession:
    def test_turn1_allow(self):
        """Turn 1: s_prev=0, rho=1.0 (ALLOW), p_eff=0.10."""
        s1 = update_session(0.0, rho_action=1.0, p_eff=0.10, gamma=0.85)
        # 1 - (1 - 0.85*0)(1 - 1.0*0.10) = 1 - 1.0*0.90 = 0.10
        assert abs(s1 - 0.10) < 1e-6, f"expected 0.10, got {s1}"

    def test_turn2_allow(self):
        """Turn 2: s_prev=0.10, rho=1.0 (ALLOW), p_eff computed from turn 2."""
        p_eff_2 = effective_p(0.10, 0.10, beta=0.5)
        s2 = update_session(0.10, rho_action=1.0, p_eff=p_eff_2, gamma=0.85)
        # 1 - (1 - 0.85*0.10)(1 - 1.0*0.145) = 1 - 0.915 * 0.855
        expected = 1.0 - (1.0 - 0.85 * 0.10) * (1.0 - 1.0 * p_eff_2)
        assert abs(s2 - expected) < 1e-6, f"expected {expected}, got {s2}"


class TestSessionCompounding:
    """Full four-turn golden sequence."""

    def test_compounding_crosses_threshold(self):
        P_DEF = 0.10
        gamma = 0.85
        beta = 0.5
        p_star_esc_copilot = 0.166667

        s_prev = 0.0

        # Turn 1
        p_eff_1 = effective_p(P_DEF, s_prev, beta)
        assert abs(p_eff_1 - 0.10) < 1e-6
        assert p_eff_1 < p_star_esc_copilot, "turn 1 should ALLOW"
        s1 = update_session(s_prev, rho_action=1.0, p_eff=p_eff_1, gamma=gamma)
        assert abs(s1 - 0.10) < 1e-4

        # Turn 2
        p_eff_2 = effective_p(P_DEF, s1, beta)
        assert abs(p_eff_2 - 0.145) < 1e-4
        assert p_eff_2 < p_star_esc_copilot, "turn 2 should ALLOW"
        s2 = update_session(s1, rho_action=1.0, p_eff=p_eff_2, gamma=gamma)

        # Turn 3 -- must cross threshold purely from carried risk
        p_eff_3 = effective_p(P_DEF, s2, beta)
        assert p_eff_3 > p_star_esc_copilot, (
            f"turn 3 P_eff={p_eff_3:.6f} should exceed "
            f"p*_esc={p_star_esc_copilot} from carried risk alone"
        )


class TestSessionStore:
    def test_get_default(self):
        store = SessionStore()
        assert store.get("nonexistent") == 0.0

    def test_get_none(self):
        store = SessionStore()
        assert store.get(None) == 0.0

    def test_set_and_get(self):
        store = SessionStore()
        store.set("sess1", 0.42)
        assert abs(store.get("sess1") - 0.42) < 1e-10

    def test_clear(self):
        store = SessionStore()
        store.set("sess1", 0.42)
        store.clear()
        assert store.get("sess1") == 0.0
