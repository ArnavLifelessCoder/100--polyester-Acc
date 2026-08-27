"""
Tier 2 detectors -- LLM judge and self-consistency.

Optional. Falls back to SimulatedDetector if unavailable.
From build guide section 6.4.
"""

from __future__ import annotations

from controlplane.schemas import DetectorOutput, DetectionContext, RiskTag
from controlplane.detectors.simulated import SimulatedDetector


class SelfConsistencyDetector:
    """
    Stub: in production, samples k=5 generations, clusters by embedding
    cosine, computes semantic entropy. Here, falls back to simulated.
    """

    detector_id = "self_consistency_tier2"
    tag: RiskTag = "performance"
    tier = 2

    def __init__(self, seed: int = 42, base_rate: float = 0.025) -> None:
        self._fallback = SimulatedDetector(
            detector_id=self.detector_id,
            tag=self.tag,
            tier=self.tier,
            tpr=0.75,
            fpr=0.08,
            base_rate=base_rate,
            seed=seed,
        )

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        result = self._fallback.run(request, response, ctx)
        result.evidence["simulated"] = True
        result.evidence["note"] = "self-consistency stub, k=5 not actually run"
        return result


class LLMJudgeDetector:
    """
    Stub: in production, calls an LLM with a structured verdict prompt.
    Here, falls back to simulated.
    """

    detector_id = "llm_judge_tier2"
    tag: RiskTag = "performance"
    tier = 2

    def __init__(self, seed: int = 42, base_rate: float = 0.025) -> None:
        self._fallback = SimulatedDetector(
            detector_id=self.detector_id,
            tag=self.tag,
            tier=self.tier,
            tpr=0.82,
            fpr=0.06,
            base_rate=base_rate,
            seed=seed,
        )

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        result = self._fallback.run(request, response, ctx)
        result.evidence["simulated"] = True
        result.evidence["note"] = "LLM judge stub, no actual model call"
        return result
