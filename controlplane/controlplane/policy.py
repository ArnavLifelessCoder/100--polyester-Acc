"""
Policy loader with load-time validation.

Reads YAML policy files, validates via the Policy schema, and provides
immutable snapshots. An invalid policy file raises PolicyError at load time,
never at decision time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from controlplane.schemas import Policy


class PolicyError(Exception):
    """Raised when a policy file is invalid or cannot be loaded."""


def _normalise_action_dict(raw: dict[str, Any]) -> dict[str, float]:
    """Ensure string keys are uppercased for action dicts."""
    return {k.upper(): float(v) for k, v in raw.items()}


def load_policy(path: Path | str) -> Policy:
    """
    Load and validate a single policy YAML file.

    Raises PolicyError on any validation failure, including:
    - Missing or out-of-range irreversibility
    - Missing prior, kappa, or action keys
    - Non-monotone residual across the action spectrum
    """
    path = Path(path)
    if not path.exists():
        raise PolicyError(f"policy file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise PolicyError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PolicyError(f"expected a mapping at top level in {path}")

    # Normalise action dict keys to uppercase
    for key in ("friction", "utility_loss", "residual"):
        if key in raw and isinstance(raw[key], dict):
            raw[key] = _normalise_action_dict(raw[key])

    # Normalise kappa keys to sorted order (overlap.py uses sorted pairs)
    if "kappa" in raw and isinstance(raw["kappa"], dict):
        raw["kappa"] = {
            "|".join(sorted(k.split("|"))): float(v)
            for k, v in raw["kappa"].items()
        }

    try:
        return Policy(**raw)
    except Exception as exc:
        raise PolicyError(f"validation failed for {path}: {exc}") from exc


def load_all_policies(directory: Path | str) -> dict[str, Policy]:
    """
    Load every .yaml file in `directory` and return a workflow_id -> Policy map.

    Raises PolicyError if any file fails validation.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise PolicyError(f"policy directory not found: {directory}")

    policies: dict[str, Policy] = {}
    for path in sorted(directory.glob("*.yaml")):
        policy = load_policy(path)
        if policy.workflow_id in policies:
            raise PolicyError(
                f"duplicate workflow_id '{policy.workflow_id}' "
                f"in {path} and existing policy"
            )
        policies[policy.workflow_id] = policy

    if not policies:
        raise PolicyError(f"no .yaml files found in {directory}")

    return policies
