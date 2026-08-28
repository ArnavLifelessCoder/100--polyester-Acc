"""
ControlPlane, a consequence-aware AI intervention layer.

Importing this package loads local environment files first, before any module
reads os.environ. `providers.py` and `detectors/nli.py` both resolve their
configuration at import time, so loading any later would silently have no
effect.

Precedence, highest first:

  1. Variables already set in the real environment. A shell export, a CI secret,
     or the test suite's own override always wins, so a stray file on a laptop
     can never quietly redirect a pipeline.
  2. .env.local, which holds real keys and is gitignored.
  3. .env, if a project ever adds shared non-secret defaults.

python-dotenv is optional. Without it the files are simply not read and every
setting falls back to the real environment, which is the behaviour every
deployment target already relies on.
"""

from __future__ import annotations

import os
from pathlib import Path

__version__ = "0.1.0"

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_env_files() -> list[str]:
    """Load .env.local then .env, never overriding what is already set."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return []

    loaded: list[str] = []
    # Order matters: with override=False the first value to arrive wins, so
    # .env.local must be read before .env for it to take precedence.
    for name in (".env.local", ".env"):
        path = _REPO_ROOT / name
        if path.is_file():
            load_dotenv(path, override=False)
            loaded.append(name)
    return loaded


ENV_FILES_LOADED = _load_env_files()
