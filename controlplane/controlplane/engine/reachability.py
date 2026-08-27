"""
Agentic consequence by reachability.

An agent step's consequence is not what it says, it is what it can cause.
A reasoning step that can emit a refund API call carries the refund's
consequence, even though it is only text.

From annex section 3.6 and build guide section 5.7.
"""

from __future__ import annotations

from typing import Any

from controlplane.schemas import Policy


def consequence_by_reachability(
    tool_graph: dict[str, dict[str, Any]] | None,
    step: str | None,
    policy: Policy,
) -> float | None:
    """
    Compute effective consequence from the tool graph's reachable terminal actions.

    C_eff(step) = max over reachable terminal tools of
                  C(tool) * P(reach) * iota(tool)

    Tool graph format:
        {tool_name: {"consequence": float,
                     "iota": float,
                     "reachable_from": [step_ids],
                     "p_reach": float}}

    Returns None when no tool graph is supplied, letting the caller fall
    through to the standard policy consequence.
    """
    if tool_graph is None or step is None:
        return None

    max_c = 0.0
    found = False

    for tool_name, tool_info in tool_graph.items():
        reachable_from = tool_info.get("reachable_from", [])
        if step not in reachable_from:
            continue

        found = True
        c_tool = float(tool_info.get("consequence", 0.0))
        iota_tool = float(tool_info.get("iota", policy.irreversibility))
        p_reach = float(tool_info.get("p_reach", 1.0))

        effective = c_tool * p_reach * iota_tool
        max_c = max(max_c, effective)

    return max_c if found else None
