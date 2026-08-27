"""
Tests for cascade latency and cost budget accounting.
Build guide step 10.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.cascade import DetectorCascade
from controlplane.policy import load_policy
from controlplane.schemas import DetectionContext
from sim.generator import generate_traffic


POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"


class TestCascadeBudget:
    def test_routing_and_budget(self):
        policy = load_policy(POLICIES_DIR / "support_chatbot.yaml")
        # Use simulated cascade with known base rates for deterministic statistics
        cascade = DetectorCascade(use_real_detectors=False, seed=42)

        n_samples = 3000
        traffic = generate_traffic(n_total=n_samples, seed=42)

        tier2_fires = 0
        total_latency = 0.0

        for sample in traffic:
            ctx = sample.to_detection_context()
            risk, tiers_run, lat, cost = cascade.run(
                sample.request, sample.response, ctx, policy
            )
            if 2 in tiers_run:
                tier2_fires += 1
            total_latency += lat

        fire_rate_tier2 = tier2_fires / n_samples
        mean_latency = total_latency / n_samples

        # Tier 2 fire rate should be bounded and controlled
        assert fire_rate_tier2 < 0.15, f"tier 2 fired too frequently: {fire_rate_tier2}"
        # Mean latency should be under workflow budget
        assert mean_latency < policy.latency_budget_ms, (
            f"mean latency {mean_latency}ms exceeded budget {policy.latency_budget_ms}ms"
        )
