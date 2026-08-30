"""
The decision function -- entry point for the engine.

Implements the constrained expected-loss minimisation from annex section 3.1
and build guide section 5.6. This is the core mechanism.

Flow:
  1. Abstention substitution for unverifiable tags
  2. P_def via overlap model
  3. C_eff via overlap model
  4. Session carry -> P_eff
  5. L(a) for each action
  6. Unconstrained argmin (ties to lower severity)
  7. Severity cap from driving tag's precision
  8. Constrained argmin over the permitted set
  9. Update session state
  10. Mark shadow if not enforcing
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from controlplane.schemas import (
    Action,
    ACTIONS,
    Decision,
    DetectorOutput,
    Policy,
    RiskTag,
    RiskVector,
    RISK_TAGS,
)
from controlplane.engine.overlap import p_def as compute_p_def, c_eff as compute_c_eff
from controlplane.engine.reachability import consequence_by_reachability
from controlplane.calibration import get_calibrator
from controlplane.engine.session import SessionStore, effective_p, update_session
from controlplane.engine.severity import (
    SEVERITY_ORDER,
    severity_index,
    severity_max,
)


# Module-level session store for the prototype
_session_store = SessionStore()


def get_session_store() -> SessionStore:
    return _session_store


def decide(
    risk: RiskVector,
    policy: Policy,
    session_id: str | None = None,
    request_id: str | None = None,
    tiers_run: list[int] | None = None,
    total_latency_ms: float = 0.0,
    estimated_cost_units: float = 0.0,
    tool_graph: dict[str, dict[str, Any]] | None = None,
    step: str | None = None,
) -> Decision:
    """
    Run the full decision function on a risk vector under a policy.

    Returns a Decision with all intermediate values filled in for the UI.

    When the request declares a tool graph, the consequence of an agent step is
    what that step can reach, not what it says. A reasoning step that can emit
    a refund call is adjudicated at the refund's consequence even though it is
    only text. See engine/reachability.py.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    if tiers_run is None:
        tiers_run = []

    reason_codes: list[str] = []
    reason_codes.append(f"POLICY_{policy.workflow_id}_{policy.version}")

    # ---- 1. Abstention substitution ----
    p_hats: dict[RiskTag, float] = {}
    unverifiable: list[RiskTag] = list(risk.unverifiable_tags)

    for tag in RISK_TAGS:
        if tag not in risk.per_tag:
            # Tag not evaluated -- treat as zero
            p_hats[tag] = 0.0
            continue

        det = risk.per_tag[tag]

        if not det.verifiable:
            # Substitute prior, mark unverifiable
            p_hats[tag] = policy.prior[tag]
            if tag not in unverifiable:
                unverifiable.append(tag)
            reason_codes.append(f"ABSTAIN_{tag.upper()}")
        else:
            p_hats[tag] = det.p_hat

    # ---- 2. P_def ----
    p_def_val = compute_p_def(p_hats, policy.kappa)

    # ---- 2b. Applied calibration ----
    # The arithmetic below is only as good as this number. An overconfident
    # detector under a large consequence will justify holding traffic that
    # should pass, and the correct repair is the probability, not the
    # threshold: moving thresholds to compensate would break the consequence
    # model that derives them. The map is fitted on adjudicated decisions and
    # is identity until one exists.
    calibrator = get_calibrator()
    if calibrator.fitted:
        p_def_raw = p_def_val
        p_def_val = calibrator.transform(p_def_val)
        if abs(p_def_val - p_def_raw) > 1e-9:
            reason_codes.append("CALIBRATED")

    # ---- 3. C_eff ----
    c_eff_val = compute_c_eff(p_hats, policy.consequence, policy.lam)

    # ---- 3b. Reachability override for agentic steps ----
    reachable_c = consequence_by_reachability(tool_graph, step, policy)
    if reachable_c is not None:
        policy_c_eff = c_eff_val
        c_eff_val = reachable_c
        reason_codes.append("REACHABILITY_CONSEQUENCE")
        if reachable_c > policy_c_eff:
            reason_codes.append("REACHABLE_TOOL_DOMINATES")

    # ---- 4. Session carry ----
    s_prev = _session_store.get(session_id)
    p_eff = effective_p(p_def_val, s_prev)

    if s_prev > 0.0:
        reason_codes.append("SESSION_CARRY")

    # ---- 5. L(a) for each action ----
    iota = policy.irreversibility
    losses: dict[Action, float] = {}

    for a in ACTIONS:
        rho = policy.residual[a]
        f = policy.friction[a]
        u = policy.utility_loss[a]

        loss = rho * p_eff * c_eff_val * iota + f + (1.0 - p_eff) * u
        losses[a] = round(loss, 2)

    # ---- 6. Unconstrained argmin (ties to lower severity) ----
    min_loss = min(losses.values())
    candidates = [a for a in ACTIONS if losses[a] == min_loss]
    # Ties resolve to the lowest severity
    unconstrained = min(candidates, key=severity_index)

    # ---- 7. Severity cap from driving tag ----
    # The driving tag is the argmax of p_hats
    driving_tag = max(p_hats, key=lambda t: p_hats[t])

    if driving_tag in risk.per_tag:
        driving_det = risk.per_tag[driving_tag]
        driving_precision = driving_det.measured_precision
        driving_verifiable = driving_det.verifiable
    else:
        # No detector ran for this tag
        driving_precision = 0.0
        driving_verifiable = False

    cap, cap_reason = severity_max(driving_precision, driving_verifiable)

    # If any tag is unverifiable, the cap must also consider that
    for tag in unverifiable:
        if tag in risk.per_tag:
            tag_cap, tag_cap_reason = severity_max(
                risk.per_tag[tag].measured_precision,
                risk.per_tag[tag].verifiable,
            )
            if severity_index(tag_cap) < severity_index(cap):
                cap = tag_cap
                cap_reason = tag_cap_reason

    # ---- 8. Constrained argmin over the permitted set ----
    # The cap defines a feasible set, not a clamp. Walking the unconstrained
    # winner down the ladder with min(unc_idx, cap_idx) can land on an action
    # that costs more than another the cap also permits: under internal_copilot
    # an ESCALATE at 136 was selected over a CONSTRAIN at 63 because BLOCK won
    # unconstrained and ESCALATE was the next rung down. Re-minimising over the
    # feasible set is what section 3.1 says the engine does, and the two agree
    # wherever the loss ordering happens to follow the severity ladder.
    cap_idx = severity_index(cap)
    feasible = [a for a in ACTIONS if severity_index(a) <= cap_idx]
    feasible_min = min(losses[a] for a in feasible)
    feasible_candidates = [a for a in feasible if losses[a] == feasible_min]
    action = min(feasible_candidates, key=severity_index)

    if action != unconstrained:
        reason_codes.append(f"CAP_{cap_reason.upper()}" if cap_reason else "CAP_APPLIED")

    # High p_hat reason codes
    for tag in RISK_TAGS:
        if p_hats.get(tag, 0.0) > 0.1:
            reason_codes.append(f"TAG_{tag.upper()}_HIGH")

    if iota >= 0.8:
        reason_codes.append("IRREVERSIBLE_ACTION")

    # ---- 9. Update session ----
    rho_action = policy.residual[action]
    s_after = update_session(s_prev, rho_action, p_eff)
    _session_store.set(session_id, s_after)

    # ---- 10. Shadow mode ----
    shadow = policy.stage != "enforcing"

    return Decision(
        decision_id=str(uuid.uuid4()),
        request_id=request_id,
        session_id=session_id,
        workflow_id=policy.workflow_id,
        policy_version=policy.version,
        action=action,
        p_def=round(p_def_val, 6),
        p_def_effective=round(p_eff, 6),
        c_eff=round(c_eff_val, 2),
        losses=losses,
        unconstrained_action=unconstrained,
        severity_cap=cap,
        cap_reason=cap_reason,
        reason_codes=reason_codes,
        risk_vector=RiskVector(per_tag=risk.per_tag, unverifiable_tags=unverifiable),
        session_risk_before=round(s_prev, 6),
        session_risk_after=round(s_after, 6),
        tiers_run=tiers_run,
        total_latency_ms=total_latency_ms,
        estimated_cost_units=estimated_cost_units,
        shadow=shadow,
        timestamp=datetime.now(timezone.utc),
    )
