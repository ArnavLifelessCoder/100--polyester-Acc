"""Tests for the hash-chained ledger."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controlplane.ledger import Ledger
from controlplane.schemas import (
    Decision,
    DetectorOutput,
    RiskVector,
)


def _make_decision(action: str = "ALLOW", workflow: str = "test") -> Decision:
    """Factory for a minimal valid Decision."""
    return Decision(
        decision_id=f"d-{action}-{workflow}",
        request_id="r-1",
        session_id="s-1",
        workflow_id=workflow,
        policy_version="v1",
        action=action,
        p_def=0.1,
        p_def_effective=0.1,
        c_eff=3000.0,
        losses={"ALLOW": 300, "HOLD": 200, "CONSTRAIN": 150, "ESCALATE": 180, "BLOCK": 100},
        unconstrained_action="BLOCK",
        severity_cap="CONSTRAIN",
        cap_reason="low_precision",
        reason_codes=["TAG_PERFORMANCE_HIGH"],
        risk_vector=RiskVector(
            per_tag={
                "performance": DetectorOutput(
                    detector_id="sim",
                    tag="performance",
                    p_hat=0.3,
                    verifiable=True,
                    measured_precision=0.55,
                    tier=1,
                    latency_ms=10.0,
                )
            }
        ),
        session_risk_before=0.0,
        session_risk_after=0.1,
        tiers_run=[0, 1],
        total_latency_ms=50.0,
        estimated_cost_units=0.02,
        shadow=False,
    )


class TestLedger:
    def test_append_and_get(self):
        ledger = Ledger()
        d = _make_decision()
        ledger.append(d)
        result = ledger.get(d.decision_id)
        assert result is not None
        assert result["decision_id"] == d.decision_id
        assert result["action"] == "ALLOW"

    def test_allow_decisions_present(self):
        """ALLOW decisions must be recorded, not just interventions."""
        ledger = Ledger()
        d = _make_decision(action="ALLOW")
        ledger.append(d)
        assert ledger.count() == 1
        result = ledger.get(d.decision_id)
        assert result["action"] == "ALLOW"

    def test_hash_chain_verifies(self):
        ledger = Ledger()
        for i in range(10):
            d = _make_decision(action="ALLOW", workflow=f"w{i}")
            d.decision_id = f"d-{i}"
            ledger.append(d)
        valid, count = ledger.verify_chain()
        assert valid
        assert count == 10

    def test_content_tamper_detection(self):
        """
        Editing what a decision says must break verification.

        This is the case that matters and the one the chain used to miss.
        verify_chain only compared prev_hash against the previous row_hash, so
        it proved the rows were in the order they were written and nothing
        about their contents. Rewriting an action from BLOCK to ALLOW left
        every link intact and the ledger reported valid.
        """
        ledger = Ledger()
        for i in range(5):
            d = _make_decision(action="BLOCK", workflow=f"w{i}")
            d.decision_id = f"d-{i}"
            ledger.append(d)
        assert ledger.verify_chain() == (True, 5)

        ledger._conn.execute(
            "UPDATE decisions SET action = 'ALLOW' WHERE decision_id = 'd-2'"
        )
        ledger._conn.commit()

        valid, count = ledger.verify_chain()
        assert not valid, "an edited action was not detected"
        assert count == 2

    @pytest.mark.parametrize(
        "column, value",
        [
            ("action", "'ALLOW'"),
            ("p_def", "0.0"),
            ("c_eff", "1.0"),
            ("unconstrained_action", "'ALLOW'"),
            ("severity_cap", "'BLOCK'"),
            ("cap_reason", "'none'"),
            ("reason_codes_json", "'[]'"),
            ("losses_json", "'{}'"),
            ("risk_vector_json", "'{}'"),
            ("session_risk_after", "0.0"),
            ("workflow_id", "'other'"),
            ("shadow", "1"),
            ("timestamp", "'2020-01-01T00:00:00+00:00'"),
        ],
    )
    def test_every_hashed_column_is_covered(self, column, value):
        """
        A field left out of the hash payload can be edited undetected, so each
        one is checked individually rather than trusting the list.
        """
        ledger = Ledger()
        for i in range(4):
            d = _make_decision(action="BLOCK", workflow="w")
            d.decision_id = f"d-{i}"
            ledger.append(d)

        ledger._conn.execute(
            f"UPDATE decisions SET {column} = {value} WHERE decision_id = 'd-2'"
        )
        ledger._conn.commit()

        valid, _ = ledger.verify_chain()
        assert not valid, f"tampering with {column} went undetected"

    def test_tamper_detection(self):
        """Modifying a row's link hash should also break the chain."""
        ledger = Ledger()
        for i in range(5):
            d = _make_decision(action="ALLOW", workflow=f"w{i}")
            d.decision_id = f"d-{i}"
            ledger.append(d)

        # Tamper with the second row's prev_hash
        ledger._conn.execute(
            "UPDATE decisions SET prev_hash = 'tampered' WHERE decision_id = 'd-2'"
        )
        ledger._conn.commit()

        valid, count = ledger.verify_chain()
        assert not valid
        assert count == 2  # chain breaks at row 2

    def test_query_by_workflow(self):
        ledger = Ledger()
        for w in ["support_chatbot", "internal_copilot", "support_chatbot"]:
            d = _make_decision(workflow=w)
            d.decision_id = f"d-{w}-{id(d)}"
            ledger.append(d)
        results = ledger.query(workflow_id="support_chatbot")
        assert len(results) == 2

    def test_query_by_action(self):
        ledger = Ledger()
        for a in ["ALLOW", "BLOCK", "ALLOW", "ESCALATE"]:
            d = _make_decision(action=a)
            d.decision_id = f"d-{a}-{id(d)}"
            ledger.append(d)
        results = ledger.query(action="ALLOW")
        assert len(results) == 2

    def test_concurrent_appends_keep_the_chain_intact(self, tmp_path):
        """
        Two writers on one database each held their own idea of the chain head,
        so both could write rows claiming the same predecessor and break
        verification for everyone. The previous hash is now read inside the
        write transaction.
        """
        import threading

        ledger = Ledger(tmp_path / "concurrent.db")
        errors: list[Exception] = []

        def worker(n: int) -> None:
            try:
                for i in range(40):
                    d = _make_decision(action="ALLOW")
                    d.decision_id = f"w{n}-{i}"
                    ledger.append(d)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"append raised under concurrency: {errors[:2]}"
        assert ledger.count() == 160
        valid, checked = ledger.verify_chain()
        assert valid, f"chain broke after concurrent appends at row {checked}"
        assert checked == 160
        ledger.close()

    def test_empty_chain_verifies(self):
        ledger = Ledger()
        valid, count = ledger.verify_chain()
        assert valid
        assert count == 0
