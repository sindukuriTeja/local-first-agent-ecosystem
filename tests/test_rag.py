"""Tests for the governed RAG service: scoped documentation retrieval,
the property-inventory mirror, the scope-leak fix, and the per-role
RAG endpoints (employee / auditor / advocate / all)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from agent_platform.server import create_app
from agent_platform.core.rag import doc_in_scope


@pytest.fixture()
def client(platform):
    c = TestClient(create_app(platform=platform))
    c.platform = platform
    return c


def _tok(client, username, password):
    r = client.post("/api/auth/login",
                    json={"username": username, "password": password})
    return r.json()["token"]


# ---------------------------------------------------------------------------
# Property inventory mirror
# ---------------------------------------------------------------------------

def test_properties_are_mirrored_into_knowledge(platform):
    """The property inventory is mirrored into the knowledge store as
    ``property`` documents, so it is searchable through the RAG path."""
    prop_docs = platform.knowledge.list_documents(doc_types=["property"])
    assert len(prop_docs) == 16  # the seeded demo inventory
    # every mirrored doc is internal + has a property: source
    for d in prop_docs:
        assert d.sensitivity == "internal"
        assert d.source.startswith("property:")
        assert d.doc_type == "property"


def test_property_mirror_is_idempotent(platform):
    """Re-syncing must not duplicate rows (upserted by source)."""
    before = len(platform.knowledge.list_documents(doc_types=["property"]))
    platform.sync_properties()
    after = len(platform.knowledge.list_documents(doc_types=["property"]))
    assert before == after == 16


def test_upsert_document_updates_in_place(platform):
    doc_id, updated = platform.knowledge.upsert_document(
        title="First", content="hello world", source="upsert-test",
        doc_type="note", sensitivity="internal")
    assert updated is False  # first insert
    doc_id2, updated2 = platform.knowledge.upsert_document(
        title="Second", content="updated world", source="upsert-test",
        doc_type="note", sensitivity="internal")
    assert updated2 is True  # second call updates in place
    assert doc_id == doc_id2  # same doc, not duplicated
    rec = platform.knowledge.get_document(doc_id)
    assert rec.title == "Second"
    assert "updated world" in rec.content


# ---------------------------------------------------------------------------
# Scope-leak fix: RAG search must apply matter/client/parcel scope
# ---------------------------------------------------------------------------

def _seed_scoped_docs(platform):
    # A distinctive shared token ("zephyr") so both match on keyword.
    platform.knowledge.add_document(
        title="In-scope matter",
        content="Matter M-100 zephyr alpha. Client TestCorp Ltd.",
        source="rag-scope-a", doc_type="case_analysis",
        sensitivity="internal", tenant="default",
        metadata={"matter": "M-100", "client": "TestCorp Ltd"})
    platform.knowledge.add_document(
        title="Out-of-scope matter",
        content="Matter M-999 zephyr beta. Client OtherCorp Ltd.",
        source="rag-scope-b", doc_type="case_analysis",
        sensitivity="internal", tenant="default",
        metadata={"matter": "M-999", "client": "OtherCorp Ltd"})


def test_rag_search_applies_matter_scope(platform):
    _seed_scoped_docs(platform)
    # employee1 is assigned M-100 / M-101, clients TestCorp / Acme.
    results = platform.rag_search("employee1", "zephyr")
    sources = {r["source"] for r in results}
    assert "rag-scope-a" in sources          # in-scope matter
    assert "rag-scope-b" not in sources      # out-of-scope matter excluded

    # The raw (unscoped) knowledge search WOULD return both — proving the
    # RAG layer adds the scope the document list already enforced.
    raw = platform.knowledge.search("zephyr", top_k=10)
    raw_sources = {r.record.source for r in raw}
    assert "rag-scope-b" in raw_sources


def test_rag_search_applies_sensitivity_ceiling(platform):
    platform.knowledge.add_document(
        title="Restricted doc",
        content="Zephyr restricted secret content.",
        source="rag-restricted", doc_type="note",
        sensitivity="restricted", tenant="default",
        metadata={})
    # employee ceiling is confidential -> restricted doc must be hidden
    results = platform.rag_search("employee1", "zephyr restricted")
    assert all(r["sensitivity"] != "restricted" for r in results)
    # admin ceiling is restricted -> visible
    admin_results = platform.rag_search("admin", "zephyr restricted")
    assert any(r["source"] == "rag-restricted" for r in admin_results)


def test_rag_search_auditor_scoped_to_compliance_types(platform):
    platform.knowledge.add_document(
        title="A compliance record",
        content="Zephyr compliance deadline MGT-7.",
        source="rag-compliance", doc_type="compliance",
        sensitivity="confidential", tenant="default", metadata={})
    platform.knowledge.add_document(
        title="A private note",
        content="Zephyr private note content.",
        source="rag-note", doc_type="note",
        sensitivity="internal", tenant="default", metadata={})
    results = platform.rag_search("auditor1", "zephyr")
    sources = {r["source"] for r in results}
    assert "rag-compliance" in sources
    assert "rag-note" not in sources  # auditor only sees compliance/audit/etc


def test_doc_in_scope_rules():
    from agent_platform.core.auth import PortalUser
    emp = PortalUser(username="e", role="employee", display_name="E",
                     portal="employee", matters=["M-100"], clients=["TC"])
    mgr = PortalUser(username="m", role="manager", display_name="M",
                     portal="management")
    aud = PortalUser(username="a", role="auditor", display_name="A",
                     portal="auditor")

    class _D:
        def __init__(self, dt, md):
            self.doc_type = dt
            self.metadata = md

    assert doc_in_scope(mgr, _D("note", {"matter": "M-999"})) is True
    assert doc_in_scope(emp, _D("note", {"matter": "M-100"})) is True
    assert doc_in_scope(emp, _D("note", {"matter": "M-999"})) is False
    assert doc_in_scope(emp, _D("note", {"client": "TC"})) is True
    assert doc_in_scope(emp, _D("note", {"client": "Other"})) is False
    assert doc_in_scope(aud, _D("compliance", {})) is True
    assert doc_in_scope(aud, _D("note", {})) is False


# ---------------------------------------------------------------------------
# Grounded answer
# ---------------------------------------------------------------------------

def test_rag_answer_grounded_with_sources(platform):
    _seed_scoped_docs(platform)
    res = platform.rag_answer("employee1", "zephyr")
    assert res["grounded"] is True
    assert res["sources"]
    assert res["answer"]
    # every cited source must be within the user's scope
    assert all(s["source"] != "rag-scope-b" for s in res["sources"])


def test_rag_answer_no_match(platform):
    res = platform.rag_answer("employee1", "qqqqzzzz notpresenttoken")
    assert res["grounded"] is False
    assert res["sources"] == []


def test_rag_answer_offline_verbatim_fallback(platform):
    """When the local model is unavailable, the answer is the best-matching
    evidence verbatim (model=False), still grounded + cited."""
    _seed_scoped_docs(platform)
    platform.rag._availability_cache = False  # force offline path
    res = platform.rag_answer("employee1", "zephyr alpha")
    assert res["grounded"] is True
    assert res["model"] is False
    assert res["answer"]  # verbatim chunk text
    assert res["sources"]


# ---------------------------------------------------------------------------
# Endpoints: available to EVERY role (not just approvers)
# ---------------------------------------------------------------------------

def test_rag_status_for_employee(client):
    tok = _tok(client, "employee1", "employee123")
    r = client.get("/api/rag", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["suggested_queries"]


def test_rag_search_endpoint_for_employee(client):
    """The employee can now search the documentation (previously only
    approvers could reach the search endpoint)."""
    client.platform.knowledge.add_document(
        title="Employee searchable doc",
        content="Gachibowli land plot zephyr employee search.",
        source="rag-emp-search", doc_type="note",
        sensitivity="internal", tenant="default", metadata={})
    tok = _tok(client, "employee1", "employee123")
    r = client.post("/api/rag/search",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"query": "gachibowli zephyr"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert any(x["source"] == "rag-emp-search" for x in body["results"])


def test_rag_search_endpoint_for_auditor(client):
    """The auditor can search the documentation."""
    client.platform.knowledge.add_document(
        title="Auditor compliance doc",
        content="Zephyr compliance audit record for auditor.",
        source="rag-aud-search", doc_type="compliance",
        sensitivity="confidential", tenant="default", metadata={})
    tok = _tok(client, "auditor1", "auditor123")
    r = client.post("/api/rag/search",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"query": "zephyr compliance"})
    assert r.status_code == 200
    body = r.json()
    assert any(x["source"] == "rag-aud-search" for x in body["results"])


def test_rag_search_endpoint_for_advocate(client):
    """The advocate / counsel can search the documentation."""
    client.platform.knowledge.add_document(
        title="Advocate statute doc",
        content="Zephyr statute section 12 for advocate counsel.",
        source="rag-counsel-search", doc_type="statute",
        sensitivity="confidential", tenant="default",
        metadata={"matter": "M-100"})
    tok = _tok(client, "counsel1", "counsel123")
    r = client.post("/api/rag/search",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"query": "zephyr statute"})
    assert r.status_code == 200
    body = r.json()
    assert any(x["source"] == "rag-counsel-search" for x in body["results"])


def test_rag_ask_endpoint(client):
    client.platform.knowledge.add_document(
        title="Ask doc",
        content="Zephyr answer token for the ask endpoint.",
        source="rag-ask-doc", doc_type="note",
        sensitivity="internal", tenant="default", metadata={})
    tok = _tok(client, "employee1", "employee123")
    r = client.post("/api/rag/ask",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"query": "zephyr answer"})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is True
    assert body["answer"]


def test_rag_requires_auth(client):
    assert client.get("/api/rag").status_code == 401
    assert client.post("/api/rag/search",
                       json={"query": "x"}).status_code == 401
    assert client.post("/api/rag/ask",
                       json={"query": "x"}).status_code == 401


def test_rag_property_searchable_by_employee(client):
    """Property inventory is reachable through the RAG search for an
    employee (mirrored into the knowledge store)."""
    tok = _tok(client, "employee1", "employee123")
    r = client.post("/api/rag/search",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"query": "Gachibowli land plot"})
    assert r.status_code == 200
    body = r.json()
    assert any(x["doc_type"] == "property" for x in body["results"])


def test_portal_payload_includes_rag_block(client):
    tok = _tok(client, "employee1", "employee123")
    r = client.get("/api/portal", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert "rag" in r.json()
    assert r.json()["rag"]["available"] is True