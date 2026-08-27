"""Tests for policy loading and validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the repo root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.policy import load_policy, load_all_policies, PolicyError


POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"


class TestPolicyLoading:
    def test_load_decision_support(self):
        p = load_policy(POLICIES_DIR / "decision_support.yaml")
        assert p.workflow_id == "decision_support"
        assert p.consequence.performance == 50000
        assert p.irreversibility == 0.9
        assert p.fail_mode == "closed"
        assert p.intervention_mode == "gated"

    def test_load_support_chatbot(self):
        p = load_policy(POLICIES_DIR / "support_chatbot.yaml")
        assert p.workflow_id == "support_chatbot"
        assert p.consequence.performance == 3000
        assert p.irreversibility == 0.6
        assert p.fail_mode == "open"

    def test_load_internal_copilot(self):
        p = load_policy(POLICIES_DIR / "internal_copilot.yaml")
        assert p.workflow_id == "internal_copilot"
        assert p.consequence.performance == 800
        assert p.irreversibility == 0.2
        assert p.fail_mode == "open"

    def test_load_all_policies(self):
        policies = load_all_policies(POLICIES_DIR)
        assert len(policies) == 3
        assert "decision_support" in policies
        assert "support_chatbot" in policies
        assert "internal_copilot" in policies

    def test_residual_monotone(self):
        """Residual must be non-increasing across the action spectrum."""
        policies = load_all_policies(POLICIES_DIR)
        for wid, p in policies.items():
            from controlplane.schemas import ACTIONS
            vals = [p.residual[a] for a in ACTIONS]
            for i in range(len(vals) - 1):
                assert vals[i] >= vals[i + 1], (
                    f"{wid}: residual[{ACTIONS[i]}]={vals[i]} "
                    f"< residual[{ACTIONS[i+1]}]={vals[i+1]}"
                )

    def test_invalid_irreversibility(self, tmp_path):
        """Irreversibility outside (0,1] must raise PolicyError."""
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "workflow_id: bad\n"
            "version: v1\n"
            "jurisdiction: IN\n"
            "consequence: {performance: 100, cost: 100, responsibility: 100}\n"
            "irreversibility: 1.5\n"
            "latency_budget_ms: 100\n"
            "intervention_mode: gated\n"
            "fail_mode: open\n"
            "prior: {performance: 0.01, cost: 0.01, responsibility: 0.01}\n"
            "kappa: {}\n"
            "lam: 0.3\n"
            "stage: shadow\n"
            "routing: {q1: 0.1, q2: 0.01}\n"
            "friction: {ALLOW: 0, HOLD: 5, CONSTRAIN: 15, ESCALATE: 120, BLOCK: 50}\n"
            "utility_loss: {ALLOW: 0, HOLD: 20, CONSTRAIN: 80, ESCALATE: 200, BLOCK: 200}\n"
            "residual: {ALLOW: 1.0, HOLD: 0.5, CONSTRAIN: 0.3, ESCALATE: 0.1, BLOCK: 0.0}\n"
        )
        with pytest.raises(PolicyError):
            load_policy(bad)

    def test_missing_action_key(self, tmp_path):
        """Missing an action key in friction must raise PolicyError."""
        bad = tmp_path / "bad2.yaml"
        bad.write_text(
            "workflow_id: bad2\n"
            "version: v1\n"
            "jurisdiction: IN\n"
            "consequence: {performance: 100, cost: 100, responsibility: 100}\n"
            "irreversibility: 0.5\n"
            "latency_budget_ms: 100\n"
            "intervention_mode: gated\n"
            "fail_mode: open\n"
            "prior: {performance: 0.01, cost: 0.01, responsibility: 0.01}\n"
            "kappa: {}\n"
            "lam: 0.3\n"
            "stage: shadow\n"
            "routing: {q1: 0.1, q2: 0.01}\n"
            "friction: {ALLOW: 0, HOLD: 5}\n"
            "utility_loss: {ALLOW: 0, HOLD: 20, CONSTRAIN: 80, ESCALATE: 200, BLOCK: 200}\n"
            "residual: {ALLOW: 1.0, HOLD: 0.5, CONSTRAIN: 0.3, ESCALATE: 0.1, BLOCK: 0.0}\n"
        )
        with pytest.raises(PolicyError):
            load_policy(bad)

    def test_nonmonotone_residual_rejected(self, tmp_path):
        """Non-monotone residual must raise PolicyError."""
        bad = tmp_path / "bad3.yaml"
        bad.write_text(
            "workflow_id: bad3\n"
            "version: v1\n"
            "jurisdiction: IN\n"
            "consequence: {performance: 100, cost: 100, responsibility: 100}\n"
            "irreversibility: 0.5\n"
            "latency_budget_ms: 100\n"
            "intervention_mode: gated\n"
            "fail_mode: open\n"
            "prior: {performance: 0.01, cost: 0.01, responsibility: 0.01}\n"
            "kappa: {}\n"
            "lam: 0.3\n"
            "stage: shadow\n"
            "routing: {q1: 0.1, q2: 0.01}\n"
            "friction: {ALLOW: 0, HOLD: 5, CONSTRAIN: 15, ESCALATE: 120, BLOCK: 50}\n"
            "utility_loss: {ALLOW: 0, HOLD: 20, CONSTRAIN: 80, ESCALATE: 200, BLOCK: 200}\n"
            "residual: {ALLOW: 0.5, HOLD: 0.8, CONSTRAIN: 0.3, ESCALATE: 0.1, BLOCK: 0.0}\n"
        )
        with pytest.raises(PolicyError):
            load_policy(bad)
