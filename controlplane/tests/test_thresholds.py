"""
Tests for derived thresholds -- golden vectors from build guide section 7.

With H=120, a_h=0.9, F_b=50, U=200:
  internal_copilot  (C=800):   p*_esc=0.166667, p*_block=0.250000
  support_chatbot   (C=3000):  p*_esc=0.044444, p*_block=0.078125
  decision_support  (C=50000): p*_esc=0.002667, p*_block=0.004980
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.engine.thresholds import p_star_escalate, p_star_block


class TestThresholdGolden:
    VECTORS = [
        ("internal_copilot", 800, 0.166667, 0.250000),
        ("support_chatbot", 3000, 0.044444, 0.078125),
        ("decision_support", 50000, 0.002667, 0.004980),
    ]

    def test_escalation_thresholds(self):
        for name, c, expected_esc, _ in self.VECTORS:
            result = p_star_escalate(c)
            assert abs(result - expected_esc) < 1e-6, (
                f"{name}: p*_esc expected {expected_esc}, got {result}"
            )

    def test_block_thresholds(self):
        for name, c, _, expected_block in self.VECTORS:
            result = p_star_block(c)
            assert abs(result - expected_block) < 1e-6, (
                f"{name}: p*_block expected {expected_block}, got {result}"
            )

    def test_escalation_always_below_block(self):
        """p*_esc < p*_block in every workflow -- not a design choice, a consequence."""
        for name, c, _, _ in self.VECTORS:
            esc = p_star_escalate(c)
            blk = p_star_block(c)
            assert esc < blk, f"{name}: p*_esc={esc} >= p*_block={blk}"
