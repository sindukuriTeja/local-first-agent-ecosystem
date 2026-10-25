"""Tests for the FastAPI server endpoints (using TestClient)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from agent_platform import server


@pytest.fixture()
def client(platform, monkeypatch):
    monkeypatch.setattr(server, "_platform", platform)
    return TestClient(server.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["agents"] == 16
    assert body["ollama_available"] is True  # mock client


def test_agents_listing(client):
    r = client.get("/agents")
    assert r.status_code == 200
    agents = r.json()
    assert len(agents) == 16
    assert all(a["id"] for a in agents)


def test_ask_endpoint(client):
    r = client.post("/ask", json={
        "user": "admin",
        "request": "What is the filing deadline for matter A?",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "needs_approval")
    assert body["answer"]


def test_ask_unknown_user(client):
    r = client.post("/ask", json={"user": "ghost", "request": "hi"})
    assert r.status_code == 200
    assert r.json()["status"] == "error"


def test_approvals_flow(client):
    # create a draft via /ask -> run drafting agent directly through /ask?
    # Simpler: use the platform fixture to create an approval, then decide via API
    r = client.get("/approvals")
    assert r.status_code == 200

    # create an approval directly on the platform
    req = server._platform.approval.request("draft", "API test draft",
                                            {}, requested_by="admin")
    r = client.post("/approvals/decide", json={
        "approval_id": req.id,
        "user": "reviewer",
        "decision": "approved",
        "note": "ok",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_approve_permission_denied(client):
    req = server._platform.approval.request("draft", "perm test", {},
                                            requested_by="admin")
    r = client.post("/approvals/decide", json={
        "approval_id": req.id,
        "user": "analyst",
        "decision": "approved",
    })
    assert r.status_code == 403


def test_audit_endpoint(client):
    r = client.get("/audit", params={"limit": 10})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_models_endpoint(client):
    r = client.get("/models")
    assert r.status_code == 200
    assert "llama3.1:8b" in r.json()["models"]


def test_ingest_endpoint(client, tmp_path):
    doc = tmp_path / "upload.txt"
    doc.write_text("INVOICE dated 2026-02-02. Amount 750000. Party: Acme Ltd.")
    with open(doc, "rb") as f:
        r = client.post(
            "/ingest?user=admin&sensitivity=internal",
            files={"file": ("upload.txt", f, "text/plain")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["data"]["doc_id"]