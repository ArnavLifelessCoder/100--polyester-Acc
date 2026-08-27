"""
Append-only, hash-chained decision ledger.

SQLite in WAL mode. Every decision is recorded including ALLOWs.
Tampering with any row is detectable via the hash chain.

From build guide section 8, step 8.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from controlplane.schemas import Decision


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    session_id TEXT,
    workflow_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    action TEXT NOT NULL,
    p_def REAL NOT NULL,
    p_def_effective REAL NOT NULL,
    c_eff REAL NOT NULL,
    losses_json TEXT NOT NULL,
    unconstrained_action TEXT NOT NULL,
    severity_cap TEXT NOT NULL,
    cap_reason TEXT,
    reason_codes_json TEXT NOT NULL,
    risk_vector_json TEXT NOT NULL,
    session_risk_before REAL NOT NULL,
    session_risk_after REAL NOT NULL,
    tiers_run_json TEXT NOT NULL,
    total_latency_ms REAL NOT NULL,
    estimated_cost_units REAL NOT NULL,
    shadow INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    row_hash TEXT NOT NULL
);
"""

# Human adjudications live in their own table rather than as mutable columns on
# the decision. A decision row is append-only and hash-chained; a label arrives
# later and must not alter the record it refers to, or every hash after it
# breaks. Keeping them separate lets the audit trail stay immutable while the
# feedback loop still writes.
_CREATE_LABELS = """
CREATE TABLE IF NOT EXISTS labels (
    decision_id TEXT PRIMARY KEY,
    actually_defective INTEGER NOT NULL,
    note TEXT,
    labelled_at TEXT NOT NULL
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_workflow ON decisions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_action ON decisions(action);
CREATE INDEX IF NOT EXISTS idx_session ON decisions(session_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON decisions(timestamp);
"""


# Columns that are covered by the row hash, in a fixed order. Every field that
# an auditor would care about must appear here: a column left out of this list
# can be edited without breaking the chain.
_HASHED_COLUMNS: tuple[str, ...] = (
    "decision_id",
    "request_id",
    "session_id",
    "workflow_id",
    "policy_version",
    "action",
    "p_def",
    "p_def_effective",
    "c_eff",
    "losses_json",
    "unconstrained_action",
    "severity_cap",
    "cap_reason",
    "reason_codes_json",
    "risk_vector_json",
    "session_risk_before",
    "session_risk_after",
    "tiers_run_json",
    "total_latency_ms",
    "estimated_cost_units",
    "shadow",
    "timestamp",
)

# Fixed-precision formatting per column, so a float that round-trips through
# SQLite serialises identically on write and on verify.
_COLUMN_FORMAT: dict[str, str] = {
    "p_def": ".6f",
    "p_def_effective": ".6f",
    "c_eff": ".2f",
    "session_risk_before": ".6f",
    "session_risk_after": ".6f",
    "total_latency_ms": ".3f",
    "estimated_cost_units": ".4f",
}


def _canonical_row_data(values: dict[str, Any]) -> str:
    """
    Deterministic serialisation of a ledger row.

    Both `append` and `verify_chain` go through this function, which is what
    makes tampering detectable. If verification rebuilt the payload by a
    different route, the two could disagree and the chain would only be
    checking its own links.
    """
    parts: list[str] = []
    for col in _HASHED_COLUMNS:
        value = values[col]
        if col == "shadow":
            parts.append(str(int(value)))
        elif value is None:
            parts.append("")
        elif col in _COLUMN_FORMAT:
            parts.append(format(float(value), _COLUMN_FORMAT[col]))
        else:
            parts.append(str(value))
    return "|".join(parts)


def _compute_hash(data: str, prev_hash: str) -> str:
    """SHA-256 of the row data concatenated with the previous hash."""
    payload = prev_hash + data
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Ledger:
    """Append-only, hash-chained decision store backed by SQLite."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        # Serialises appends within this process. Across processes the
        # BEGIN IMMEDIATE in append() does the same job at the database level.
        self._write_lock = threading.Lock()
        self._conn = sqlite3.connect(
            self._db_path, check_same_thread=False, isolation_level=None
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_CREATE_TABLE + _CREATE_LABELS + _CREATE_INDEX)
        self._prev_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        """Load the hash of the last row, or return the genesis hash."""
        row = self._conn.execute(
            "SELECT row_hash FROM decisions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if row:
            return row[0]
        return "0" * 64  # genesis

    def append(self, decision: Decision) -> str:
        """
        Append a decision to the ledger. Returns the row hash.

        This is the only write operation. There is no update or delete.
        """
        losses_json = json.dumps(decision.losses)
        reason_codes_json = json.dumps(decision.reason_codes)
        risk_vector_json = decision.risk_vector.model_dump_json()
        tiers_run_json = json.dumps(decision.tiers_run)
        ts = decision.timestamp.isoformat()

        row_data = _canonical_row_data({
            "decision_id": decision.decision_id,
            "request_id": decision.request_id,
            "session_id": decision.session_id,
            "workflow_id": decision.workflow_id,
            "policy_version": decision.policy_version,
            "action": decision.action,
            "p_def": decision.p_def,
            "p_def_effective": decision.p_def_effective,
            "c_eff": decision.c_eff,
            "losses_json": losses_json,
            "unconstrained_action": decision.unconstrained_action,
            "severity_cap": decision.severity_cap,
            "cap_reason": decision.cap_reason,
            "reason_codes_json": reason_codes_json,
            "risk_vector_json": risk_vector_json,
            "session_risk_before": decision.session_risk_before,
            "session_risk_after": decision.session_risk_after,
            "tiers_run_json": tiers_run_json,
            "total_latency_ms": decision.total_latency_ms,
            "estimated_cost_units": decision.estimated_cost_units,
            "shadow": decision.shadow,
            "timestamp": ts,
        })

        # The previous hash is read inside the write transaction rather than
        # taken from memory. Two writers on the same database file each hold
        # their own idea of the chain head, and if both trust it they produce
        # two rows claiming the same predecessor, which breaks verification for
        # everyone. BEGIN IMMEDIATE takes the write lock before the read, so
        # the value cannot change between reading it and inserting.
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                prev_hash = self._load_last_hash()
                row_hash = _compute_hash(row_data, prev_hash)
                self._insert_row(decision, prev_hash, row_hash, losses_json,
                                 reason_codes_json, risk_vector_json,
                                 tiers_run_json, ts)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        self._prev_hash = row_hash
        return row_hash

    def _insert_row(
        self,
        decision: Decision,
        prev_hash: str,
        row_hash: str,
        losses_json: str,
        reason_codes_json: str,
        risk_vector_json: str,
        tiers_run_json: str,
        ts: str,
    ) -> None:
        self._conn.execute(
            """INSERT INTO decisions (
                decision_id, request_id, session_id, workflow_id,
                policy_version, action, p_def, p_def_effective, c_eff,
                losses_json, unconstrained_action, severity_cap, cap_reason,
                reason_codes_json, risk_vector_json,
                session_risk_before, session_risk_after,
                tiers_run_json, total_latency_ms, estimated_cost_units,
                shadow, timestamp, prev_hash, row_hash
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                decision.decision_id,
                decision.request_id,
                decision.session_id,
                decision.workflow_id,
                decision.policy_version,
                decision.action,
                decision.p_def,
                decision.p_def_effective,
                decision.c_eff,
                losses_json,
                decision.unconstrained_action,
                decision.severity_cap,
                decision.cap_reason,
                reason_codes_json,
                risk_vector_json,
                decision.session_risk_before,
                decision.session_risk_after,
                tiers_run_json,
                decision.total_latency_ms,
                decision.estimated_cost_units,
                int(decision.shadow),
                ts,
                prev_hash,
                row_hash,
            ),
        )

    def get(self, decision_id: str) -> dict[str, Any] | None:
        """Retrieve a single decision by ID."""
        row = self._conn.execute(
            "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def query(
        self,
        workflow_id: str | None = None,
        action: str | None = None,
        session_id: str | None = None,
        since: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query ledger with filters. Returns newest-first."""
        conditions = []
        params: list[Any] = []

        if workflow_id:
            conditions.append("workflow_id = ?")
            params.append(workflow_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = " AND ".join(conditions)
        if where:
            where = "WHERE " + where

        params.extend([limit, offset])
        rows = self._conn.execute(
            f"SELECT * FROM decisions {where} ORDER BY rowid DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()

        return [self._row_to_dict(r) for r in rows]

    def count(self, workflow_id: str | None = None) -> int:
        if workflow_id:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM decisions WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM decisions").fetchone()
        return row[0] if row else 0

    def verify_chain(self) -> tuple[bool, int]:
        """
        Verify the entire hash chain. Returns (valid, rows_checked).

        Two things are checked per row, and both matter:

        1. The link: prev_hash equals the previous row's row_hash.
        2. The content: row_hash recomputes from the row's own stored fields.

        Check 2 is the one that catches an edited decision. Verifying only the
        links proves the rows are in the order they were written, not that any
        of them still says what it said. Rewriting an action from BLOCK to
        ALLOW leaves every link intact.

        `rows_checked` counts rows that verified, so it is also the index of
        the first bad row when the result is False.
        """
        rows = self._conn.execute(
            f"SELECT {', '.join(_HASHED_COLUMNS)}, prev_hash, row_hash "
            "FROM decisions ORDER BY rowid ASC"
        ).fetchall()

        if not rows:
            return True, 0

        expected_prev = "0" * 64  # genesis
        checked = 0

        for row in rows:
            values = dict(zip(_HASHED_COLUMNS, row))
            prev_hash, row_hash = row[-2], row[-1]

            if prev_hash != expected_prev:
                return False, checked
            if _compute_hash(_canonical_row_data(values), prev_hash) != row_hash:
                return False, checked

            expected_prev = row_hash
            checked += 1

        return True, checked

    def _row_to_dict(self, row: tuple) -> dict[str, Any]:
        """Convert a raw sqlite row to a dict."""
        cols = [
            "decision_id", "request_id", "session_id", "workflow_id",
            "policy_version", "action", "p_def", "p_def_effective", "c_eff",
            "losses_json", "unconstrained_action", "severity_cap", "cap_reason",
            "reason_codes_json", "risk_vector_json",
            "session_risk_before", "session_risk_after",
            "tiers_run_json", "total_latency_ms", "estimated_cost_units",
            "shadow", "timestamp", "prev_hash", "row_hash",
        ]
        d = dict(zip(cols, row))
        d["losses"] = json.loads(d.pop("losses_json"))
        d["reason_codes"] = json.loads(d.pop("reason_codes_json"))
        d["risk_vector"] = json.loads(d.pop("risk_vector_json"))
        d["tiers_run"] = json.loads(d.pop("tiers_run_json"))
        d["shadow"] = bool(d["shadow"])
        return d

    # --- Human adjudication ---

    def add_label(
        self,
        decision_id: str,
        actually_defective: bool,
        note: str = "",
    ) -> bool:
        """
        Record a human verdict on a decision. Returns False if no such decision.

        Re-labelling the same decision overwrites the previous verdict, which is
        what a correction is. The decision row itself is never touched.
        """
        if self.get(decision_id) is None:
            return False
        self._conn.execute(
            "INSERT OR REPLACE INTO labels "
            "(decision_id, actually_defective, note, labelled_at) "
            "VALUES (?,?,?,?)",
            (
                decision_id,
                int(actually_defective),
                note,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return True

    def get_label(self, decision_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT decision_id, actually_defective, note, labelled_at "
            "FROM labels WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "decision_id": row[0],
            "actually_defective": bool(row[1]),
            "note": row[2],
            "labelled_at": row[3],
        }

    def labelled_decisions(
        self,
        workflow_id: str | None = None,
        limit: int = 100000,
    ) -> list[dict[str, Any]]:
        """
        Every decision that carries a human verdict, with the verdict attached.

        This is the join that EDR, UIR, override rate and calibration all read
        from. Without labels none of those four can be computed, and reporting
        a zero for them is worse than reporting nothing.
        """
        sql = (
            "SELECT d.*, l.actually_defective, l.note, l.labelled_at "
            "FROM decisions d JOIN labels l ON d.decision_id = l.decision_id"
        )
        params: list[Any] = []
        if workflow_id:
            sql += " WHERE d.workflow_id = ?"
            params.append(workflow_id)
        sql += " ORDER BY d.rowid DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        out = []
        for row in rows:
            record = self._row_to_dict(row[:24])
            record["actually_defective"] = bool(row[24])
            record["label_note"] = row[25]
            record["labelled_at"] = row[26]
            out.append(record)
        return out

    def label_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
