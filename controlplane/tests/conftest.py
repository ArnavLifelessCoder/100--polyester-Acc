"""
Test isolation for the ledger.

The API opens its SQLite ledger at import time. Without this file every test
that posts a decision or writes a human verdict mutates the same
`controlplane.db` the demo screens read from, which is a problem in three ways:

  - the seeded audit sample grows on every test run, so the numbers on Screen 5
    drift between runs and no demo figure is reproducible
  - tests that deliberately label a benign response as defective corrupt the
    calibration data those screens depend on, and were observed to invert the
    measured effect of calibration
  - a run of the test suite silently changes what a reviewer sees next

Tests get a copy of the seeded database instead. The copy carries the seeded
decisions and audit labels, so calibration and metrics tests have real data to
work with, and anything they write is discarded with the temp directory.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

# Must be set before controlplane.api is imported anywhere. pytest loads
# conftest before collecting test modules, so this runs first.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SEEDED_DB = _REPO_ROOT / "controlplane.db"

_tmp_dir = Path(tempfile.mkdtemp(prefix="controlplane-tests-"))
_test_db = _tmp_dir / "controlplane.db"

if _SEEDED_DB.exists():
    shutil.copy2(_SEEDED_DB, _test_db)
    # WAL and shared-memory sidecars hold committed pages that have not been
    # checkpointed into the main file yet. Copying the database without them
    # loses recent writes, which here would mean losing the audit sample.
    for suffix in ("-wal", "-shm"):
        sidecar = _SEEDED_DB.with_name(_SEEDED_DB.name + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, _test_db.with_name(_test_db.name + suffix))

os.environ["CONTROLPLANE_DB"] = str(_test_db)

# Force the recorded path for the whole suite.
#
# With a provider key present, /demo/live generates a fresh answer on every
# call. That makes assertions about what the model said non-deterministic, and
# it spends the developer's quota on every test run. Two bias tests failed for
# exactly this reason once a key was configured: the live model declined to
# produce the biased answer the recorded fixture contains, which is good
# behaviour from the model and a broken test either way.
#
# Tests that specifically need a live provider should set this back themselves.
# Set to empty rather than removed. load_dotenv(override=False) only skips a
# variable that is already present, so deleting it would let .env.local put the
# real key straight back. An empty value is present, so the file cannot
# override it, and _api_key() reads empty as unconfigured.
os.environ["CONTROLPLANE_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
