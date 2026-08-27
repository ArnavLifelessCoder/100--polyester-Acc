"""Tests for severity cap and ladder -- build guide section 5.3."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.engine.severity import (
    severity_max,
    severity_index,
    cap_action,
    SEVERITY_ORDER,
)


class TestSeverityMax:
    def test_high_precision_allows_block(self):
        action, reason = severity_max(0.97, verifiable=True)
        assert action == "BLOCK"
        assert reason is None

    def test_medium_high_caps_at_escalate(self):
        action, reason = severity_max(0.80, verifiable=True)
        assert action == "ESCALATE"
        assert reason == "low_precision"

    def test_medium_caps_at_constrain(self):
        action, reason = severity_max(0.55, verifiable=True)
        assert action == "CONSTRAIN"
        assert reason == "low_precision"

    def test_low_caps_at_hold(self):
        action, reason = severity_max(0.30, verifiable=True)
        assert action == "HOLD"
        assert reason == "low_precision"

    def test_unverifiable_always_caps_at_constrain(self):
        """Unverifiable signal must not block, regardless of precision."""
        for prec in [0.99, 0.80, 0.50, 0.10]:
            action, reason = severity_max(prec, verifiable=False)
            assert action == "CONSTRAIN", f"precision={prec}"
            assert reason == "unverifiable"

    def test_boundary_0_95(self):
        action, _ = severity_max(0.95, verifiable=True)
        assert action == "BLOCK"

    def test_boundary_0_70(self):
        action, _ = severity_max(0.70, verifiable=True)
        assert action == "ESCALATE"

    def test_boundary_0_40(self):
        action, _ = severity_max(0.40, verifiable=True)
        assert action == "CONSTRAIN"


class TestCapAction:
    def test_cap_reduces_severity(self):
        assert cap_action("BLOCK", "ESCALATE") == "ESCALATE"
        assert cap_action("BLOCK", "CONSTRAIN") == "CONSTRAIN"

    def test_cap_at_or_above_has_no_effect(self):
        assert cap_action("ESCALATE", "BLOCK") == "ESCALATE"
        assert cap_action("ALLOW", "BLOCK") == "ALLOW"

    def test_same_action(self):
        for a in SEVERITY_ORDER:
            assert cap_action(a, a) == a


class TestSeverityOrder:
    def test_order(self):
        assert SEVERITY_ORDER == ["ALLOW", "HOLD", "CONSTRAIN", "ESCALATE", "BLOCK"]

    def test_indices(self):
        assert severity_index("ALLOW") == 0
        assert severity_index("BLOCK") == 4
