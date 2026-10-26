"""Tests for the multi-portal web app: auth, sessions, and per-role portals."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from agent_platform.server import create_app


@pytest.fixture()
def client(platform):
    c = TestClient(create_app(platform=platform))
    c.platform = platform
    return c


def _login(client, username, password):
    return client.post("/api/auth/login",
                       json={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_login_success(client):
    r = _login(client, "employee1", "employee123")
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["user"]["portal"] == "employee"
    assert body["user"]["role"] == "employee"


def test_login_wrong_password(client):
    r = _login(client, "employee1", "wrongpass")
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = _login(client, "ghost", "whatever")
    assert r.status_code == 401


def test_demo_logins_lists_all_portals(client):
    r = client.get("/api/auth/demo")
    assert r.status_code == 200
    logins = r.json()["logins"]
    portals = {l["portal"] for l in logins}
    assert portals == {"employee", "management", "counsel", "client",
                       "tenant", "auditor", "admin"}
    # every demo login actually works
    for l in logins:
        lr = _login(client, l["username"], l["password"])
        assert lr.status_code == 200, l["portal"]


def test_portals_listing(client):
    r = client.get("/api/portals")
    assert r.status_code == 200
    assert len(r.json()) == 7


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
    tok = _login(client, "admin", "admin123").json()["token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "admin"


def test_logout(client):
    tok = _login(client, "admin", "admin123").json()["token"]
    r = client.post("/api/auth/logout",
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    # token no longer valid
    r2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# Portal data (scoped per role)
# ---------------------------------------------------------------------------

def _tok(client, username, password):
    return _login(client, username, password).json()["token"]


def test_employee_portal(client):
    tok = _tok(client, "employee1", "employee123")
    r = client.get("/api/portal", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["portal"] == "employee"
    assert "cases" in body and "tax_matters" in body
    assert "ai_tasks" in body and body["ai_tasks"]


def test_management_portal(client):
    tok = _tok(client, "manager1", "manager123")
    r = client.get("/api/portal", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["portal"] == "management"
    assert "kpi" in body and "workload" in body and "risk_alerts" in body


def test_client_portal(client):
    tok = _tok(client, "client1", "client123")
    r = client.get("/api/portal", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["portal"] == "client"
    assert "cases" in body and "reports" in body and "my_requests" in body


def test_tenant_portal(client):
    tok = _tok(client, "tenant1", "tenant123")
    r = client.get("/api/portal", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["portal"] == "tenant"
    assert "parcels" in body


def test_auditor_portal_scoped_to_compliance(client):
    tok = _tok(client, "auditor1", "auditor123")
    r = client.get("/api/portal", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["portal"] == "auditor"
    assert "compliance_records" in body and "audit_trail" in body
    # auditor must NOT see debt (restricted) or arbitrary doc types
    for rec in body["compliance_records"]:
        assert rec["doc_type"] in ("compliance", "audit", "case_analysis", "tax")


def test_admin_portal(client):
    tok = _tok(client, "admin", "admin123")
    r = client.get("/api/portal", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["portal"] == "admin"
    assert "agents" in body and "kpi" in body


def test_portal_requires_auth(client):
    assert client.get("/api/portal").status_code == 401


# ---------------------------------------------------------------------------
# Portal actions
# ---------------------------------------------------------------------------

def test_client_submit_request(client):
    tok = _tok(client, "client1", "client123")
    r = client.post("/api/portal/request",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"subject": "Need an update",
                          "message": "Please share the latest status."})
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"
    # it now appears in the client portal
    body = client.get("/api/portal",
                      headers={"Authorization": f"Bearer {tok}"}).json()
    assert any(req["subject"] == "Need an update"
               for req in body["my_requests"])


def test_ai_task_through_portal(client):
    tok = _tok(client, "employee1", "employee123")
    r = client.post("/api/portal/ai",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"prompt": "What is the filing deadline for matter M-100?"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "needs_approval")
    assert body["answer"]


def test_approval_role_gating(client):
    # employee cannot approve
    platform = client.platform
    req = platform.approval.request("draft", "gate test", {}, requested_by="admin")
    emp_tok = _tok(client, "employee1", "employee123")
    r = client.post("/api/portal/approve",
                    headers={"Authorization": f"Bearer {emp_tok}"},
                    json={"approval_id": req.id, "decision": "approved"})
    assert r.status_code == 403
    # manager can approve
    mgr_tok = _tok(client, "manager1", "manager123")
    r2 = client.post("/api/portal/approve",
                     headers={"Authorization": f"Bearer {mgr_tok}"},
                     json={"approval_id": req.id, "decision": "approved"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------

def test_admin_users_listing(client):
    admin_tok = _tok(client, "admin", "admin123")
    r = client.get("/api/admin/users",
                   headers={"Authorization": f"Bearer {admin_tok}"})
    assert r.status_code == 200
    usernames = {u["username"] for u in r.json()["users"]}
    assert {"admin", "employee1", "manager1", "client1"} <= usernames


def test_admin_users_forbidden_for_non_admin(client):
    emp_tok = _tok(client, "employee1", "employee123")
    r = client.get("/api/admin/users",
                   headers={"Authorization": f"Bearer {emp_tok}"})
    assert r.status_code == 403


def test_admin_create_and_disable_user(client):
    admin_tok = _tok(client, "admin", "admin123")
    r = client.post("/api/admin/users",
                    headers={"Authorization": f"Bearer {admin_tok}"},
                    json={"username": "tempuser", "password": "temp123",
                          "role": "employee", "display_name": "Temp User"})
    assert r.status_code == 200
    # new user can log in
    assert _login(client, "tempuser", "temp123").status_code == 200
    # disable them
    r2 = client.post("/api/admin/users/enable",
                     headers={"Authorization": f"Bearer {admin_tok}"},
                     json={"username": "tempuser", "enabled": False})
    assert r2.status_code == 200
    # now login fails
    assert _login(client, "tempuser", "temp123").status_code == 401


# ---------------------------------------------------------------------------
# Legacy API still works (regression)
# ---------------------------------------------------------------------------

def test_legacy_ask_still_works(client):
    r = client.post("/ask", json={"user": "admin",
                                  "request": "What is the filing deadline?"})
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "needs_approval")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["agents"] == 16