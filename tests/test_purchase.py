"""Tests for the Buy This purchase flow: employee request -> advocate +
auditor review -> agreement generated + property marked sold."""

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


def _auth(client, username, password):
    tok = _login(client, username, password).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def _available_property(client, headers):
    r = client.get("/api/properties", headers=headers)
    assert r.status_code == 200
    props = r.json()["properties"]
    avail = [p for p in props if p["status"] == "available"]
    assert avail, "no available properties in seeded inventory"
    return avail[0]


# ---------------------------------------------------------------------------
# Store-level flow
# ---------------------------------------------------------------------------

def test_purchase_flow_store(platform):
    store = platform.properties
    props = [p for p in store.list_properties() if p["status"] == "available"]
    target = props[0]

    req = store.request_purchase(target["id"], "Ravi Kumar",
                                 "9876543210", "r@x.com", "PAN123",
                                 requested_by="employee1")
    assert req["status"] == "pending"
    assert req["advocate_review"] == "pending"
    assert req["auditor_review"] == "pending"

    # duplicate blocked
    with pytest.raises(ValueError):
        store.request_purchase(target["id"], "Other", requested_by="employee1")

    # one approval is not enough
    r = store.decide_purchase_review(req["id"], "advocate", "approved",
                                     "counsel1", "ok")
    assert r["status"] == "pending"
    assert r["agreement_text"] in (None, "")
    assert store.get_property(target["id"])["status"] == "available"

    # double review by same role blocked
    with pytest.raises(ValueError):
        store.decide_purchase_review(req["id"], "advocate", "approved",
                                     "counsel1")

    # second reviewer completes it
    r = store.decide_purchase_review(req["id"], "auditor", "approved",
                                     "auditor1", "ok")
    assert r["status"] == "approved"
    assert r["agreement_id"]
    assert "SALE AND PURCHASE AGREEMENT" in r["agreement_text"]
    assert "Ravi Kumar" in r["agreement_text"]
    assert store.get_property(target["id"])["status"] == "sold"


def test_purchase_rejection_store(platform):
    store = platform.properties
    target = [p for p in store.list_properties()
              if p["status"] == "available"][0]
    req = store.request_purchase(target["id"], "Sita", requested_by="employee1")
    r = store.decide_purchase_review(req["id"], "auditor", "rejected",
                                     "auditor1", "missing KYC")
    assert r["status"] == "rejected"
    assert r["rejected_by"] == "auditor1"
    assert r["rejection_reason"] == "missing KYC"
    assert store.get_property(target["id"])["status"] == "available"
    # a rejected request cannot be re-decided
    with pytest.raises(ValueError):
        store.decide_purchase_review(req["id"], "advocate", "approved",
                                     "counsel1")


def test_purchase_sold_property_blocked(platform):
    store = platform.properties
    sold = [p for p in store.list_properties() if p["status"] == "sold"]
    if not sold:
        pytest.skip("no sold property seeded")
    with pytest.raises(ValueError):
        store.request_purchase(sold[0]["id"], "Buyer", requested_by="employee1")


# ---------------------------------------------------------------------------
# Portal role gating
# ---------------------------------------------------------------------------

def test_purchase_role_gates(client):
    emp = _auth(client, "employee1", "employee123")
    counsel = _auth(client, "counsel1", "counsel123")
    auditor = _auth(client, "auditor1", "auditor123")
    client_h = _auth(client, "client1", "client123")

    prop = _available_property(client, emp)
    r = client.post(f"/api/properties/{prop['id']}/purchase",
                    json={"buyer_name": "Ravi Kumar",
                          "buyer_contact": "9876543210"},
                    headers=emp)
    assert r.status_code == 200, r.text
    req = r.json()
    assert req["status"] == "pending"

    # employee cannot review
    r = client.post(f"/api/properties/purchase-requests/{req['id']}/decide",
                    json={"decision": "approved"}, headers=emp)
    assert r.status_code == 403
    # client cannot review
    r = client.post(f"/api/properties/purchase-requests/{req['id']}/decide",
                    json={"decision": "approved"}, headers=client_h)
    assert r.status_code == 403

    # counsel (advocate) approves
    r = client.post(f"/api/properties/purchase-requests/{req['id']}/decide",
                    json={"decision": "approved"}, headers=counsel)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"

    # counsel cannot record the auditor review
    r = client.post(f"/api/properties/purchase-requests/{req['id']}/decide",
                    json={"decision": "approved"}, headers=counsel)
    assert r.status_code == 404  # already reviewed by advocate

    # auditor completes
    r = client.post(f"/api/properties/purchase-requests/{req['id']}/decide",
                    json={"decision": "approved"}, headers=auditor)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body["agreement_text"]

    # property now sold
    r = client.get(f"/api/properties/{prop['id']}", headers=emp)
    assert r.json()["status"] == "sold"

    # agreement retrievable
    r = client.get(f"/api/properties/purchase-requests/{req['id']}",
                   headers=emp)
    assert r.status_code == 200
    assert "SALE AND PURCHASE AGREEMENT" in r.json()["agreement_text"]


# ---------------------------------------------------------------------------
# Portal payload wiring
# ---------------------------------------------------------------------------

def test_purchase_portal_payloads(client):
    emp = _auth(client, "employee1", "employee123")
    counsel = _auth(client, "counsel1", "counsel123")
    auditor = _auth(client, "auditor1", "auditor123")

    prop = _available_property(client, emp)
    client.post(f"/api/properties/{prop['id']}/purchase",
                json={"buyer_name": "Ravi Kumar"}, headers=emp)

    # employee sees it under my_purchase_requests + purchase_requests.mine
    data = client.get("/api/portal", headers=emp).json()
    assert data["properties"]["my_purchase_requests"], "employee block missing"
    assert data["purchase_requests"]["available"] is True
    assert data["purchase_requests"]["reviewer_role"] is None
    assert len(data["purchase_requests"]["mine"]) == 1

    # counsel (advocate) sees it in the review queue
    data = client.get("/api/portal", headers=counsel).json()
    q = data["purchase_requests"]["queue"]
    assert len(q) == 1
    assert data["purchase_requests"]["reviewer_role"] == "advocate"
    assert q[0]["advocate_review"] == "pending"

    # auditor sees it in the review queue too
    data = client.get("/api/portal", headers=auditor).json()
    q = data["purchase_requests"]["queue"]
    assert len(q) == 1
    assert data["purchase_requests"]["reviewer_role"] == "auditor"
    assert q[0]["auditor_review"] == "pending"

    # stats reflect the pending purchase
    stats = client.get("/api/properties", headers=emp).json()["stats"]
    assert stats["pending_purchase_requests"] == 1