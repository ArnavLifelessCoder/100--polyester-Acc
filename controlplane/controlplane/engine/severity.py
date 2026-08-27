"""
Severity ladder and precision-bounded caps.

The cap ensures that action severity never exceeds what detector precision
can support. A mediocre detector degrades the system toward logging rather
than producing wrong blocks.

From annex section 3.3 and build guide section 5.3.
"""

from __future__ import annotations

from controlplane.schemas import Action
from constants import PRECISION_BLOCK, PRECISION_ESCALATE, PRECISION_CONSTRAIN


SEVERITY_ORDER: list[Action] = ["ALLOW", "HOLD", "CONSTRAIN", "ESCALATE", "BLOCK"]


def severity_index(action: Action) -> int:
    """Return the position of an action in the severity ladder (0=ALLOW, 4=BLOCK)."""
    return SEVERITY_ORDER.index(action)


def severity_max(
    measured_precision: float,
    verifiable: bool,
) -> tuple[Action, str | None]:
    """
    Maximum permitted action given detector precision and verifiability.

    If not verifiable: cap at CONSTRAIN (unverifiable signal must not block).
    Otherwise, precision bands from annex 3.3:
      >= 0.95  -> BLOCK
      >= 0.70  -> ESCALATE
      >= 0.40  -> CONSTRAIN
      <  0.40  -> HOLD
    """
    if not verifiable:
        return "CONSTRAIN", "unverifiable"

    if measured_precision >= PRECISION_BLOCK:
        return "BLOCK", None
    if measured_precision >= PRECISION_ESCALATE:
        return "ESCALATE", "low_precision"
    if measured_precision >= PRECISION_CONSTRAIN:
        return "CONSTRAIN", "low_precision"
    return "HOLD", "low_precision"


def cap_action(
    unconstrained: Action,
    cap: Action,
) -> Action:
    """
    Apply a severity cap to an unconstrained action.

    Returns the lower-severity of the two.
    """
    unc_idx = severity_index(unconstrained)
    cap_idx = severity_index(cap)
    return SEVERITY_ORDER[min(unc_idx, cap_idx)]
