"""
Core data models for the ControlPlane decision engine.

Every schema here maps directly to section 3 of the build guide.
Pydantic v2 models with strict validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


RiskTag = Literal["performance", "cost", "responsibility"]
Action = Literal["ALLOW", "HOLD", "CONSTRAIN", "ESCALATE", "BLOCK"]

RISK_TAGS: list[RiskTag] = ["performance", "cost", "responsibility"]
ACTIONS: list[Action] = ["ALLOW", "HOLD", "CONSTRAIN", "ESCALATE", "BLOCK"]


class DetectorOutput(BaseModel):
    """Output from a single detector run."""

    detector_id: str
    tag: RiskTag
    p_hat: float = Field(ge=0.0, le=1.0)
    verifiable: bool
    measured_precision: float = Field(ge=0.0, le=1.0)
    tier: int = Field(ge=0, le=3)
    latency_ms: float = Field(ge=0.0)
    evidence: dict[str, Any] = Field(default_factory=dict)


class RiskVector(BaseModel):
    """Aggregated risk signal across all tags."""

    per_tag: dict[RiskTag, DetectorOutput]
    unverifiable_tags: list[RiskTag] = Field(default_factory=list)


class ConsequenceModel(BaseModel):
    """Per-workflow consequence estimates in INR."""

    performance: float = Field(gt=0)
    cost: float = Field(gt=0)
    responsibility: float = Field(gt=0)

    def as_dict(self) -> dict[RiskTag, float]:
        return {
            "performance": self.performance,
            "cost": self.cost,
            "responsibility": self.responsibility,
        }


class Policy(BaseModel):
    """
    Immutable policy snapshot for a single workflow.

    Loaded from YAML, validated at load time. Every field consumed by the
    decision engine is present here -- no config is read elsewhere.
    """

    workflow_id: str
    version: str
    jurisdiction: str
    consequence: ConsequenceModel
    irreversibility: float = Field(gt=0.0, le=1.0)
    latency_budget_ms: int = Field(gt=0)
    intervention_mode: Literal["gated", "buffered", "monitored"]
    fail_mode: Literal["open", "closed"]
    prior: dict[RiskTag, float]
    kappa: dict[str, float]
    lam: float = Field(ge=0.0, le=1.0)
    stage: Literal["shadow", "advisory", "enforcing"]
    routing: dict[str, float]
    friction: dict[Action, float]
    utility_loss: dict[Action, float]
    residual: dict[Action, float]

    @field_validator("prior")
    @classmethod
    def _validate_prior(cls, v: dict[RiskTag, float]) -> dict[RiskTag, float]:
        for tag in RISK_TAGS:
            if tag not in v:
                raise ValueError(f"prior missing tag: {tag}")
            if not 0.0 <= v[tag] <= 1.0:
                raise ValueError(f"prior[{tag}] must be in [0,1], got {v[tag]}")
        return v

    @field_validator("kappa")
    @classmethod
    def _validate_kappa(cls, v: dict[str, float]) -> dict[str, float]:
        for key, val in v.items():
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"kappa[{key}] must be in [0,1], got {val}")
        return v

    @field_validator("friction", "utility_loss", "residual")
    @classmethod
    def _validate_action_dicts(
        cls, v: dict[Action, float]
    ) -> dict[Action, float]:
        for action in ACTIONS:
            if action not in v:
                raise ValueError(f"missing action key: {action}")
        return v

    @field_validator("residual")
    @classmethod
    def _validate_residual_monotone(
        cls, v: dict[Action, float]
    ) -> dict[Action, float]:
        # Residual must be monotonically non-increasing across ALLOW -> BLOCK
        vals = [v[a] for a in ACTIONS]
        for i in range(len(vals) - 1):
            if vals[i] < vals[i + 1]:
                raise ValueError(
                    f"residual must be non-increasing across the spectrum. "
                    f"{ACTIONS[i]}={vals[i]} < {ACTIONS[i+1]}={vals[i+1]}"
                )
        return v


class Decision(BaseModel):
    """
    Immutable record of a single adjudication decision.

    Written to the ledger for every response, including ALLOWs.
    """

    decision_id: str
    request_id: str
    session_id: str | None = None
    workflow_id: str
    policy_version: str
    action: Action
    p_def: float
    p_def_effective: float
    c_eff: float
    losses: dict[Action, float]
    unconstrained_action: Action
    severity_cap: Action
    cap_reason: str | None = None
    reason_codes: list[str]
    risk_vector: RiskVector
    session_risk_before: float = 0.0
    session_risk_after: float = 0.0
    tiers_run: list[int] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    estimated_cost_units: float = 0.0
    shadow: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DetectionContext(BaseModel):
    """Context passed to detectors alongside the request/response pair."""

    retrieval_context: str | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    model_tier: str | None = None
    prior_turns: list[dict[str, str]] = Field(default_factory=list)
    # Defaults are the workflow baseline from constants.TOKEN_BASELINE_*.
    # A zero mean with unit sigma makes the rolling z-score equal the raw token
    # count, which saturates the cost tag at p_hat=1.0 for any normal response.
    rolling_token_mu: float = 50.0
    rolling_token_sigma: float = 20.0
    ground_truth_label: bool | None = None  # for simulated detector
    ground_truth_tags: list[RiskTag] = Field(default_factory=list)
    # Pre-computed counterfactual variant responses, keyed "from->to", for the
    # counterfactual bias detector. Supplied when the variants were generated
    # ahead of time; otherwise the detector generates or abstains.
    counterfactual_responses: dict[str, str] = Field(default_factory=dict)
