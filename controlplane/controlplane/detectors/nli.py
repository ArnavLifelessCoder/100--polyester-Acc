"""
Shared NLI model loading for the grounding detector.

The model is loaded lazily and cached process-wide. Importing this module must
stay cheap: the API, the test suite and the sim seeder all import the detector
package, and none of them should pay a model load they may never use.

Loading is attempted exactly once. If it fails, for any reason, the failure is
recorded and every later caller is told immediately rather than retrying a
download on each request. A detector that cannot load its model must degrade to
an honest "I cannot verify this", never to a silent zero.
"""

from __future__ import annotations

import os
import threading
from typing import Any

# cross-encoder/nli-deberta-v3-xsmall is ~70MB and returns three logits in the
# order (contradiction, entailment, neutral). Small enough to run on CPU inside
# a per-request latency budget, real enough to be a genuine entailment check.
NLI_MODEL_NAME = os.environ.get(
    "CONTROLPLANE_NLI_MODEL", "cross-encoder/nli-deberta-v3-xsmall"
)

# Set CONTROLPLANE_DISABLE_NLI=1 to force the lexical fallback. Used by the test
# suite so unit tests do not depend on a model download, and available as an
# escape hatch on a machine with no network.
NLI_DISABLED = os.environ.get("CONTROLPLANE_DISABLE_NLI", "").strip() not in ("", "0")

_lock = threading.Lock()
_model: Any = None
_load_attempted = False
_load_error: str | None = None


def nli_available() -> bool:
    """True when a real entailment model is loaded and usable."""
    return get_nli_model() is not None


def nli_status() -> dict[str, Any]:
    """Reportable state, so the UI can say which detector actually ran."""
    get_nli_model()
    return {
        "model": NLI_MODEL_NAME,
        "loaded": _model is not None,
        "disabled": NLI_DISABLED,
        "error": _load_error,
    }


def get_nli_model() -> Any:
    """
    Return the cached cross-encoder, or None if it is unavailable.

    Thread-safe and attempted only once. Callers must handle None.
    """
    global _model, _load_attempted, _load_error

    if NLI_DISABLED:
        _load_error = "disabled by CONTROLPLANE_DISABLE_NLI"
        return None
    if _load_attempted:
        return _model

    with _lock:
        if _load_attempted:
            return _model
        _load_attempted = True
        try:
            import warnings

            warnings.filterwarnings("ignore")
            from sentence_transformers import CrossEncoder

            _model = CrossEncoder(NLI_MODEL_NAME)
        except Exception as exc:  # noqa: BLE001 - any failure degrades the same way
            _model = None
            _load_error = f"{type(exc).__name__}: {exc}"
        return _model


def entailment_scores(pairs: list[tuple[str, str]]) -> list[dict[str, float]] | None:
    """
    Score (premise, hypothesis) pairs. Returns None when no model is available.

    Each result carries the softmaxed probability of contradiction, entailment
    and neutral. Contradiction is kept separate from neutral on purpose: a claim
    the source refutes is a different failure from a claim the source simply
    does not mention, and the grounding detector weights them differently.
    """
    model = get_nli_model()
    if model is None or not pairs:
        return None

    import numpy as np

    logits = np.asarray(model.predict(pairs))
    if logits.ndim == 1:
        logits = logits.reshape(1, -1)

    exp = np.exp(logits - logits.max(axis=1, keepdims=True))
    probs = exp / exp.sum(axis=1, keepdims=True)

    return [
        {
            "contradiction": float(row[0]),
            "entailment": float(row[1]),
            "neutral": float(row[2]),
        }
        for row in probs
    ]
