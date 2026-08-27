"""
End-to-end test: POST a completion, get a decision, find it in the ledger.
Build guide step 13.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from controlplane.api import app


client = TestClient(app)


class TestEndToEnd:
    def test_adjudicate_returns_decision(self):
        resp = client.post("/v1/adjudicate", json={
            "request": "What is the refund policy?",
            "response": "Based on our policy, refunds are available within 30 days of purchase.",
            "workflow_id": "support_chatbot",
            "retrieval_context": "Refund policy: 30-day window from purchase date.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "decision_id" in data
        assert data["action"] in ["ALLOW", "HOLD", "CONSTRAIN", "ESCALATE", "BLOCK"]
        assert "losses" in data
        assert len(data["losses"]) == 5

    def test_decision_in_ledger(self):
        resp = client.post("/v1/adjudicate", json={
            "request": "test query",
            "response": "test response",
            "workflow_id": "internal_copilot",
        })
        assert resp.status_code == 200
        decision_id = resp.json()["decision_id"]

        ledger_resp = client.get(f"/v1/decisions/{decision_id}")
        assert ledger_resp.status_code == 200
        assert ledger_resp.json()["decision_id"] == decision_id

    def test_decisions_list(self):
        client.post("/v1/adjudicate", json={
            "request": "q", "response": "r", "workflow_id": "support_chatbot",
        })
        resp = client.get("/v1/decisions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_metrics(self):
        resp = client.get("/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_decisions" in data["traffic"]
        # EDR and UIR are never returned one without the other.
        assert "edr" in data["quality"]
        assert "uir" in data["quality"]

    def test_chain_verify(self):
        resp = client.get("/v1/chain/verify")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_policy_get(self):
        resp = client.get("/admin/policy/support_chatbot")
        assert resp.status_code == 200
        assert resp.json()["workflow_id"] == "support_chatbot"

    def test_policies_list(self):
        resp = client.get("/admin/policies")
        assert resp.status_code == 200
        assert "support_chatbot" in resp.json()
        assert "internal_copilot" in resp.json()
        assert "decision_support" in resp.json()

    def test_unknown_workflow_404(self):
        resp = client.post("/v1/adjudicate", json={
            "request": "q", "response": "r", "workflow_id": "nonexistent",
        })
        assert resp.status_code == 404

    def test_demo_screen1(self):
        resp = client.get("/demo/screen1")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["columns"]) == {
            "support_chatbot", "internal_copilot", "decision_support"
        }

    def test_demo_screen3(self):
        resp = client.get("/demo/screen3")
        assert resp.status_code == 200
        assert len(resp.json()["panes"]) == 6

    def test_demo_screen4(self):
        resp = client.get("/demo/screen4")
        assert resp.status_code == 200
        data = resp.json()
        assert data["primary"] in data["tracks"]
        for track in data["tracks"].values():
            assert len(track["turns"]) == 4
