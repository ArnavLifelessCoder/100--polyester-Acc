"""
Tests for the overlap model -- golden vectors from build guide section 7.

p_hats = {performance: 0.4, responsibility: 0.3}:
  kappa=0.0  -> P_def = 0.4000
  kappa=0.4  -> P_def = 0.4720
  kappa=1.0  -> P_def = 0.5800 (must equal 1 - (1-0.4)(1-0.3) to 6dp)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.engine.overlap import p_def, c_eff
from controlplane.schemas import ConsequenceModel


class TestPDefGolden:
    P_HATS = {"performance": 0.4, "cost": 0.0, "responsibility": 0.3}

    def test_kappa_zero(self):
        """Fully nested tags -- P_def equals max."""
        kappa = {"performance|responsibility": 0.0, "cost|performance": 0.0, "cost|responsibility": 0.0}
        result = p_def(self.P_HATS, kappa)
        assert abs(result - 0.4000) < 1e-6, f"expected 0.4000, got {result}"

    def test_kappa_0_4(self):
        """Partial correlation."""
        kappa = {"performance|responsibility": 0.4, "cost|performance": 0.0, "cost|responsibility": 0.0}
        result = p_def(self.P_HATS, kappa)
        assert abs(result - 0.4720) < 1e-6, f"expected 0.4720, got {result}"

    def test_kappa_one(self):
        """Fully independent tags -- must equal 1 - prod(1-p_d) to 6dp."""
        kappa = {"performance|responsibility": 1.0, "cost|performance": 1.0, "cost|responsibility": 1.0}
        result = p_def(self.P_HATS, kappa)
        expected = 1.0 - (1.0 - 0.4) * (1.0 - 0.3)  # cost is 0.0 so contributes nothing
        assert abs(result - 0.5800) < 1e-6, f"expected 0.5800, got {result}"
        assert abs(result - expected) < 1e-6

    def test_empty_returns_zero(self):
        assert p_def({}, {}) == 0.0

    def test_single_tag(self):
        result = p_def({"performance": 0.7}, {})
        assert abs(result - 0.7) < 1e-6


class TestCEff:
    def test_golden_support(self):
        """From the golden decision: p_hats={perf:0.30, cost:0.02, resp:0.10}."""
        p_hats = {"performance": 0.30, "cost": 0.02, "responsibility": 0.10}
        consequence = ConsequenceModel(performance=3000, cost=400, responsibility=3000)
        result = c_eff(p_hats, consequence, lam=0.3, trigger_threshold=0.05)
        # m=performance (0.30), cost (0.02) < 0.05 so excluded, resp (0.10) > 0.05
        # C_eff = 3000 + 0.3 * 3000 = 3900.0
        assert abs(result - 3900.0) < 1e-6, f"expected 3900.0, got {result}"

    def test_all_below_threshold(self):
        """Only the dominant tag contributes when others are below threshold."""
        p_hats = {"performance": 0.10, "cost": 0.01, "responsibility": 0.01}
        consequence = ConsequenceModel(performance=3000, cost=400, responsibility=3000)
        result = c_eff(p_hats, consequence, lam=0.3, trigger_threshold=0.05)
        assert abs(result - 3000.0) < 1e-6

    def test_empty_returns_zero(self):
        consequence = ConsequenceModel(performance=3000, cost=400, responsibility=3000)
        assert c_eff({}, consequence, 0.3) == 0.0
