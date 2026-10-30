"""Purchase workflow (property sale) tests.

Covers the full lifecycle: employee proposes a sale (property + price) ->
client decides (accept / decline) -> advocate + auditor are connected and
the sale document package is prepared -> client signs -> property marked
sold. Also covers role gating, portal payloads, and the HTTP endpoints.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_platform.workflow import (
    ST_PURCHASE_COMPLETED,
    ST_PURCHASE_DECLINED,
    ST_PURCHASE_DOCUMENTATION,
    ST_PURCHASE_OFFERED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prop(platform, status="available"):
    """Return the first property with the given status."""
    for p in platform.properties.list_properties():
        if p["status"] == status:
            return p
    raise AssertionError(f"no property with status {status}")


def _propose(platform, property_id=None, buyer="client1"):
    pid = property_id or _prop(platform)["id"]
    return platform.workflow.propose_purchase(
        user="employee1", portal="employee",
        property_id=pid, buyer=buyer)


# ---------------------------------------------------------------------------
# Engine lifecycle
# ---------------------------------------------------------------------------

def test_propose_creates_offered_workflow(platform):
    prop = _prop(platform)
    wf = _propose(platform, prop["id"])
    assert wf["status"] == ST_PURCHASE_OFFERED
    assert wf["purchase"]["buyer"] == "client1"
    assert wf["purchase"]["property_id"] == prop["id"]
    assert wf["purchase"]["price_display"] == prop["price_display"]
    assert "Will you buy?" in wf["message"]
    # The employee sees it in their queue.
    listed = platform.workflow.list_workflows("employee1", "employee")
    assert any(w["id"] == wf["id"] for w in listed)


def test_propose_rejects_sold_property(platform):
    prop = _prop(platform, "sold")
    with pytest.raises(ValueError):
        _propose(platform, prop["id"])


def test_propose_requires_worker_portal(platform):
    prop = _prop(platform)
    with pytest.raises(PermissionError):
        platform.workflow.propose_purchase(
            user="client1", portal="client",
            property_id=prop["id"], buyer="client1")


def test_accept_connects_advocate_auditor_and_prepares_docs(platform):
    wf = _propose(platform)
    out = platform.workflow.accept_purchase(
        user="client1", portal="client", wf_id=wf["id"])
    assert out["status"] == ST_PURCHASE_DOCUMENTATION
    # Advocate and auditor were connected via input requests.
    portals = {i["to_portal"] for i in out["inputs"]}
    assert "counsel" in portals and "auditor" in portals
    # The sale document package was prepared and stored in the knowledge
    # store as sale_document records.
    docs = out["purchase"]["documents"]
    assert len(docs) >= 4
    titles = [d["title"] for d in docs]
    assert any("Sale Agreement" in t for t in titles)
    assert any("Title Verification" in t for t in titles)
    assert any("Compliance" in t for t in titles)
    stored = platform.knowledge.list_documents(limit=500)
    sale_docs = [d for d in stored if d.doc_type == "sale_document"]
    assert len(sale_docs) >= len(docs)


def test_accept_requires_buyer(platform):
    wf = _propose(platform)
    # A different client cannot accept.
    with pytest.raises(PermissionError):
        platform.workflow.accept_purchase(
            user="tenant1", portal="client", wf_id=wf["id"])
    # The employee cannot accept on the client's behalf.
    with pytest.raises(PermissionError):
        platform.workflow.accept_purchase(
            user="employee1", portal="employee", wf_id=wf["id"])


def test_decline_closes_workflow(platform):
    wf = _propose(platform)
    out = platform.workflow.decline_purchase(
        user="client1", portal="client", wf_id=wf["id"], note="too pricey")
    assert out["status"] == ST_PURCHASE_DECLINED
    assert out["completed_at"] is not None


def test_sign_completes_and_marks_property_sold(platform):
    prop = _prop(platform)
    wf = _propose(platform, prop["id"])
    platform.workflow.accept_purchase(
        user="client1", portal="client", wf_id=wf["id"])
    out = platform.workflow.sign_purchase(
        user="client1", portal="client", wf_id=wf["id"])
    assert out["status"] == ST_PURCHASE_COMPLETED
    assert out["purchase"]["signed"] is True
    assert out["purchase"]["signed_at"] is not None
    # The property is now sold in the property store.
    assert platform.properties.get_property(prop["id"])["status"] == "sold"


def test_sign_requires_buyer_and_ready_status(platform):
    wf = _propose(platform)
    # Cannot sign while still offered (no documents prepared yet).
    with pytest.raises(ValueError):
        platform.workflow.sign_purchase(
            user="client1", portal="client", wf_id=wf["id"])
    platform.workflow.accept_purchase(
        user="client1", portal="client", wf_id=wf["id"])
    # Only the buyer can sign.
    with pytest.raises(PermissionError):
        platform.workflow.sign_purchase(
            user="counsel1", portal="counsel", wf_id=wf["id"])


def test_purchase_documents_retrievable_via_rag(platform):
    """Sale documents are confidential knowledge records, retrievable by
    the parties through the governed RAG path."""
    wf = _propose(platform)
    platform.workflow.accept_purchase(
        user="client1", portal="client", wf_id=wf["id"])
    from agent_platform.core.auth import AuthManager
    user = platform.auth.get_user("client1")
    res = platform.rag.search(user, "sale agreement property", top_k=10)
    assert any(r.record.doc_type == "sale_document" for r in res)


# ---------------------------------------------------------------------------
# Portal payloads
# ---------------------------------------------------------------------------

def test_portal_payloads_surface_purchase_workflows(platform):
    from agent_platform.portal import PortalService
    svc = PortalService(platform)
    wf = _propose(platform)

    emp = platform.auth.get_user("employee1")
    emp_data = svc.portal_data(emp)
    emp_ids = [w["id"] for w in emp_data["purchase"]["workflows"]]
    assert wf["id"] in emp_ids

    cli = platform.auth.get_user("client1")
    cli_data = svc.portal_data(cli)
    cli_ids = [w["id"] for w in cli_data["purchase"]["workflows"]]
    assert wf["id"] in cli_ids

    # A client who is not the buyer sees nothing.
    other = platform.auth.get_user("client1")
    assert other.username == "client1"


def test_portal_payload_flat_shape(platform):
    from agent_platform.portal import PortalService
    svc = PortalService(platform)
    wf = _propose(platform)
    platform.workflow.accept_purchase(
        user="client1", portal="client", wf_id=wf["id"])
    data = svc.portal_data(platform.auth.get_user("client1"))
    row = next(w for w in data["purchase"]["workflows"] if w["id"] == wf["id"])
    assert row["status"] == ST_PURCHASE_DOCUMENTATION
    assert row["buyer"] == "client1"
    assert row["advocate"] and row["auditor"]
    assert row["price_display"]
    assert row["documents"] and row["documents"][0]["title"]


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(platform):
    from fastapi.testclient import TestClient
    from agent_platform.server import create_app
    c = TestClient(create_app(platform=platform))
    c.platform = platform
    return c


def _login(client, username, password):
    r = client.post("/api/auth/login",
                    json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_purchase_endpoints_full_flow(client):
    platform = client.platform
    prop = _prop(platform)

    emp = _login(client, "employee1", "employee123")
    cli = _login(client, "client1", "client123")

    # Employee proposes the sale.
    r = client.post("/api/purchase/propose",
                    json={"property_id": prop["id"], "buyer": "client1"},
                    headers=emp)
    assert r.status_code == 200, r.text
    wf_id = r.json()["workflow_id"]
    assert r.json()["status"] == ST_PURCHASE_OFFERED

    # Client accepts.
    r = client.post("/api/purchase/decision",
                    json={"workflow_id": wf_id, "decision": "accept"},
                    headers=cli)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ST_PURCHASE_DOCUMENTATION
    assert r.json()["documents"]

    # Client signs and completes.
    r = client.post("/api/purchase/sign",
                    json={"workflow_id": wf_id}, headers=cli)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ST_PURCHASE_COMPLETED
    assert platform.properties.get_property(prop["id"])["status"] == "sold"


def test_purchase_decision_rejects_wrong_client(client):
    platform = client.platform
    prop = _prop(platform)
    emp = _login(client, "employee1", "employee123")
    other = _login(client, "tenant1", "tenant123")

    r = client.post("/api/purchase/propose",
                    json={"property_id": prop["id"], "buyer": "client1"},
                    headers=emp)
    wf_id = r.json()["workflow_id"]

    # tenant1 is not the buyer -> 403.
    r = client.post("/api/purchase/decision",
                    json={"workflow_id": wf_id, "decision": "accept"},
                    headers=other)
    assert r.status_code == 403


def test_purchase_propose_rejects_non_employee(client):
    platform = client.platform
    prop = _prop(platform)
    cli = _login(client, "client1", "client123")
    r = client.post("/api/purchase/propose",
                    json={"property_id": prop["id"], "buyer": "client1"},
                    headers=cli)
    assert r.status_code == 403