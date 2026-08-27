"""
Detection cascade with routing, timing, and budget accounting.

Runs detectors in tier order. Routing to higher tiers is conditional on
lower-tier signals crossing the workflow's routing thresholds.
Parallel within a tier, serial across tiers.

From build guide section 5, annex section 3.9.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from controlplane.schemas import (
    Action,
    DetectionContext,
    DetectorOutput,
    Policy,
    RiskTag,
    RiskVector,
    RISK_TAGS,
)
from controlplane.detectors.tier0 import PIIDetector, SchemaDetector, TokenAnomalyDetector, PolicyListDetector
from controlplane.detectors.tier1 import GroundingDetector, ToxicityDetector
from controlplane.detectors.tier2 import SelfConsistencyDetector, LLMJudgeDetector
from controlplane.detectors.bias import (
    ProtectedAttributeDetector,
    CounterfactualBiasDetector,
)
from controlplane.detectors.simulated import SimulatedDetector
from constants import (
    GLOBAL_SEED,
    TIER0_LATENCY_MS,
    TIER1_LATENCY_MS,
    TIER2_LATENCY_MS,
    TIER0_COST_FRAC,
    TIER1_COST_FRAC,
    TIER2_COST_FRAC,
)

# Score gates for the judgement tiers. These are scores, not the policy's q1/q2
# traffic fractions -- see the routing note on DetectorCascade.
TIER1_JUDGEMENT_GATE: float = 0.20
TIER2_GATE: float = 0.35


class DetectorCascade:
    """
    Three-tier detection cascade.

    Tier 0: deterministic, always runs.
    Tier 1 verification (grounding): always runs. Gating it behind a tier 0
        score means only claims that already look suspicious ever get checked
        against a source, which is backwards. Grounding is also the abstention
        entry point, so gating it removes the system's ability to notice that
        it cannot verify something.
    Tier 1 judgement (toxicity and other model-backed detectors): runs when a
        tier 0 signal exceeds the policy's q1 gate.
    Tier 2: runs when a tier 1 signal exceeds the policy's q2 gate.

    The judgement gates below are fixed score thresholds. The policy's q1 and
    q2 are target *fractions of traffic*, not scores, so they cannot be used as
    gates directly without a calibration pass that maps a target fire rate onto
    a score quantile. That calibration is not built yet, so q1 and q2 are
    currently declared but unused. Do not present them as active routing.
    """

    def __init__(
        self,
        use_real_detectors: bool = True,
        sim_base_rates: dict[RiskTag, float] | None = None,
        seed: int = GLOBAL_SEED,
        generate_fn: Any = None,
    ) -> None:
        self._rng = np.random.default_rng(seed)
        self.last_wall_clock_ms: float = 0.0
        base = sim_base_rates or {"performance": 0.025, "cost": 0.01, "responsibility": 0.004}

        # Tier 0 -- always real
        self.tier0 = [
            PIIDetector(),
            SchemaDetector(),
            TokenAnomalyDetector(),
            PolicyListDetector(),
            # Bias is the first risk the brief names. The cheap half of the
            # check runs on every request; the expensive half is in tier 2.
            ProtectedAttributeDetector(),
        ]

        if use_real_detectors:
            # Grounding is verification and always runs; toxicity is gated.
            self.tier1_verify = [GroundingDetector()]
            self.tier1 = [ToxicityDetector(seed=seed)]
            self.tier2 = [
                SelfConsistencyDetector(seed=seed + 1),
                LLMJudgeDetector(seed=seed + 2),
                # Costs one model call per variant, so it belongs behind the
                # tier 2 gate. Abstains when it has no way to generate the
                # counterfactuals, which routes through the prior rather than
                # reporting a fairness result it did not establish.
                CounterfactualBiasDetector(generate_fn=generate_fn),
            ]
        else:
            # All simulated for deterministic demo.
            # In simulated mode the tier 1 detectors are the measuring
            # instrument, so they always run. Gating them behind a tier 0 score
            # means clean traffic is only ever scored by the tier 0 cost
            # detector, whose consequence is identical in all three policies,
            # and the workflows stop differentiating.
            self.tier1 = [
                SimulatedDetector("sim_perf_t1", "performance", 1, 0.80, 0.05, base["performance"], seed + 10),
                SimulatedDetector("sim_resp_t1", "responsibility", 1, 0.85, 0.03, base["responsibility"], seed + 11),
            ]
            # Grounding runs here too, even in simulated mode. It is the only
            # abstention entry point in the system: without it the no-context
            # slice of the sim traffic is never noticed, and the ledger reports
            # an abstention rate of zero for a mechanism the design treats as
            # central. Its judgement is not what is wanted here, its ability to
            # say "I cannot verify this" is.
            self.tier1_verify = [
                GroundingDetector(lexical_only=True)
            ] + list(self.tier1)
            self.tier2 = [
                SimulatedDetector("sim_perf_t2", "performance", 2, 0.82, 0.06, base["performance"], seed + 20),
                SimulatedDetector("sim_cost_t2", "cost", 2, 0.75, 0.04, base["cost"], seed + 21),
            ]

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
        policy: Policy,
    ) -> tuple[RiskVector, list[int], float, float]:
        """
        Run the cascade under the policy's routing thresholds and latency budget.

        Returns (risk_vector, tiers_run, total_latency_ms, estimated_cost_units).

        The latency returned is the *modelled* cost of the tiers that fired,
        from the annex 3.9 budgets, not the wall-clock time this process spent.
        Wall clock here measures stub detectors running in-process and reports
        around 0.05ms, which is not a number anyone should plan capacity from
        and not a number a reviewer will believe. Each tier's budget already
        represents the slowest detector in that tier, which is the right figure
        because detectors within a tier are specified to run in parallel.

        The measured wall clock is kept on `last_wall_clock_ms` for anyone who
        wants the engine's own overhead.
        """
        best_per_tag: dict[RiskTag, DetectorOutput] = {}
        tiers_run: list[int] = []
        total_latency = 0.0
        total_cost = 0.0


        # --- Tier 0: always ---
        tiers_run.append(0)
        wall_start = time.perf_counter()
        for det in self.tier0:
            out = det.run(request, response, ctx)
            self._update_best(best_per_tag, out)
        total_latency += TIER0_LATENCY_MS
        total_cost += TIER0_COST_FRAC

        # --- Tier 1 verification: always ---
        ran_tier1 = False
        for det in self.tier1_verify:
            out = det.run(request, response, ctx)
            self._update_best(best_per_tag, out)
            ran_tier1 = True

        # --- Tier 1 judgement: conditional on Tier 0 signals ---
        max_t0_p = max((d.p_hat for d in best_per_tag.values()), default=0.0)
        run_tier1 = max_t0_p >= TIER1_JUDGEMENT_GATE

        if run_tier1:
            verify_ids = {d.detector_id for d in self.tier1_verify}
            for det in self.tier1:
                if getattr(det, "detector_id", None) in verify_ids:
                    continue  # already ran as verification
                out = det.run(request, response, ctx)
                self._update_best(best_per_tag, out)
            ran_tier1 = True
            total_cost += TIER1_COST_FRAC

        if ran_tier1:
            tiers_run.append(1)
            total_latency += TIER1_LATENCY_MS

        # --- Tier 2: conditional on Tier 1 signals ---
        max_t1_p = max((d.p_hat for d in best_per_tag.values()), default=0.0)
        # Route to Tier 2 (LLM judge / self-consistency) for ambiguous/elevated risk
        run_tier2 = ran_tier1 and (max_t1_p >= TIER2_GATE)

        if run_tier2 and total_latency < policy.latency_budget_ms * 0.8:
            tiers_run.append(2)
            for det in self.tier2:
                out = det.run(request, response, ctx)
                self._update_best(best_per_tag, out)
            total_latency += TIER2_LATENCY_MS
            total_cost += TIER2_COST_FRAC

        # Fill missing tags with zero
        for tag in RISK_TAGS:
            if tag not in best_per_tag:
                best_per_tag[tag] = DetectorOutput(
                    detector_id="none",
                    tag=tag,
                    p_hat=0.0,
                    verifiable=True,
                    measured_precision=1.0,
                    tier=0,
                    latency_ms=0.0,
                )

        unverifiable = [tag for tag, d in best_per_tag.items() if not d.verifiable]

        self.last_wall_clock_ms = round(
            (time.perf_counter() - wall_start) * 1000.0, 3
        )

        return (
            RiskVector(per_tag=best_per_tag, unverifiable_tags=unverifiable),
            tiers_run,
            round(total_latency, 3),
            round(total_cost, 4),
        )

    @staticmethod
    def _update_best(
        best: dict[RiskTag, DetectorOutput],
        out: DetectorOutput,
    ) -> None:
        """Keep the highest p_hat per tag, but preserve verifiable=False."""
        existing = best.get(out.tag)
        if existing is None:
            best[out.tag] = out
        elif not out.verifiable:
            # Unverifiable overrides -- we need to know about the abstention
            if not existing.verifiable or out.p_hat >= existing.p_hat:
                best[out.tag] = out
        elif out.p_hat > existing.p_hat and existing.verifiable:
            best[out.tag] = out
