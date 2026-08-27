"""
Detector protocol -- the contract all detectors implement.

From build guide section 6.1.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from controlplane.schemas import DetectorOutput, DetectionContext, RiskTag


@runtime_checkable
class Detector(Protocol):
    """Every detector exposes these three attributes and a run() method."""

    detector_id: str
    tag: RiskTag
    tier: int

    def run(
        self,
        request: str,
        response: str,
        ctx: DetectionContext,
    ) -> DetectorOutput:
        ...
