"""Tests for the FastAPI server endpoints (using TestClient)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from agent_platform import server


@pytest.fixture()
def client(platform):
    from agent_platform.server import create_app
    c = TestClient(create_app(platform=platform))
    c.platform = platform  # attach for tests that need the platform object
    return c


def _client_platform(client):
    return client.platform


def _login(client, username="admin", password="admin123"):
    """Log in and return an Authorization header for the reviewer routes."""
    r = client.post("/api/auth/login",
                    json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


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
    # create an approval directly on the platform, then decide via API
    platform = _client_platform(client)
    req = platform.approval.request("draft", "API test draft",
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
    platform = _client_platform(client)
    req = platform.approval.request("draft", "perm test", {},
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


# ---------------------------------------------------------------------------
# Reviewer web UI + Phase 2 endpoints
# ---------------------------------------------------------------------------

def test_reviewer_page(client):
    r = client.get("/reviewer")
    assert r.status_code == 200
    assert "Reviewer Console" in r.text
    assert "Self-Learning" in r.text
    # No external CDN / script src (fully local, self-contained)
    assert "cdn." not in r.text.lower()
    assert "<script src" not in r.text


def test_documents_endpoint(client):
    r = client.get("/documents", params={"limit": 50}, headers=_login(client))
    assert r.status_code == 200
    docs = r.json()
    assert isinstance(docs, list)
    assert len(docs) >= 20  # dataset seeded in the fixture
    assert all(d["id"] and d["title"] for d in docs)


def test_search_endpoint(client):
    r = client.get("/search", params={"q": "books of account retention"},
                   headers=_login(client))
    assert r.status_code == 200
    results = r.json()
    assert isinstance(results, list)
    # Each result carries a score and a record id
    if results:
        assert "score" in results[0]
        assert "id" in results[0]


def test_learning_dashboard_endpoint(client):
    r = client.get("/learning", headers=_login(client))
    assert r.status_code == 200
    body = r.json()
    assert "total_runs" in body
    assert "holdout_accuracy" in body


def test_learn_endpoint(client):
    # Generate a couple of trajectories so the run has something to process.
    for i in range(3):
        client.post("/ask", json={"user": "admin", "request": f"query {i}"})
    r = client.post("/learn", headers=_login(client))
    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body
    assert "trajectories_processed" in body
    assert "candidates_mined" in body


# ---------------------------------------------------------------------------
# Reviewer console access control (Phase 2 hardening)
# ---------------------------------------------------------------------------

def test_reviewer_routes_require_auth(client):
    # Unauthenticated data calls are rejected before any data is exposed.
    for method, path in [("get", "/documents"), ("get", "/learning"),
                         ("get", "/search?q=x"), ("post", "/learn")]:
        r = client.request(method, path)
        assert r.status_code == 401, (path, r.status_code)


def test_reviewer_routes_forbid_non_approvers(client):
    # A valid session with a non-approver role (employee) is still rejected.
    h = _login(client, "employee1", "employee123")
    r = client.get("/documents", headers=h)
    assert r.status_code == 403
    r = client.post("/learn", headers=h)
    assert r.status_code == 403


def test_reviewer_page_stays_open(client):
    # The page itself must render (so the login form shows) without a token.
    r = client.get("/reviewer")
    assert r.status_code == 200
    assert "Reviewer Console" in r.text


def test_health_includes_counts(client):
    r = client.get("/health")
    body = r.json()
    assert "pending_approvals" in body
    assert "documents" in body
    assert body["documents"] >= 20