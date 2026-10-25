"""Tests for core services: knowledge store, audit, memory, policy, approval."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_platform.core.audit import AuditLog
from agent_platform.core.approval import ApprovalGate
from agent_platform.core.config import load_settings
from agent_platform.core.knowledge import KnowledgeStore
from agent_platform.core.memory import MemorySystem
from agent_platform.core.ollama import MockOllamaClient, extract_json
from agent_platform.core.policy import PolicyEngine


class TestKnowledgeStore:
    def test_add_and_get(self, tmp_path):
        ks = KnowledgeStore(str(tmp_path / "k.db"), embedder=None)
        doc_id = ks.add_document("Title", "Some content here.",
                                 source="s1", sensitivity="internal")
        rec = ks.get_document(doc_id)
        assert rec is not None
        assert rec.title == "Title"
        assert rec.sensitivity == "internal"
        ks.close()

    def test_hybrid_search_finds_relevant(self, tmp_path):
        ks = KnowledgeStore(str(tmp_path / "k.db"), embedder=None)
        ks.add_document("Matter A", "The filing deadline for matter A is 2026-12-01.",
                        source="docA", sensitivity="internal")
        ks.add_document("Matter B", "Matter B concerns a land dispute in Pune.",
                        source="docB", sensitivity="internal")
        results = ks.search("filing deadline matter A", top_k=3)
        assert len(results) >= 1
        assert results[0].record.title == "Matter A"
        ks.close()

    def test_sensitivity_scoping(self, tmp_path):
        ks = KnowledgeStore(str(tmp_path / "k.db"), embedder=None)
        ks.add_document("Public note", "hello world public",
                        source="p", sensitivity="public")
        ks.add_document("Restricted note", "salary details restricted",
                        source="r", sensitivity="restricted")
        # Analyst ceiling = internal -> cannot see restricted
        results = ks.search("salary details", sensitivity_max="internal")
        titles = [r.record.title for r in results]
        assert "Restricted note" not in titles
        # Admin ceiling = restricted -> can see it
        results = ks.search("salary details", sensitivity_max="restricted")
        titles = [r.record.title for r in results]
        assert "Restricted note" in titles
        ks.close()

    def test_right_to_forget(self, tmp_path):
        ks = KnowledgeStore(str(tmp_path / "k.db"), embedder=None)
        doc_id = ks.add_document("Doc", "content to forget", source="d")
        ks.add_fact("Subject", "predicate", "object", source_doc=doc_id)
        affected = ks.invalidate_document(doc_id)
        assert affected == 1
        # Deleted docs no longer returned by list
        docs = ks.list_documents()
        assert all(d.status != "deleted" for d in docs)
        ks.close()

    def test_facts_and_entities(self, tmp_path):
        ks = KnowledgeStore(str(tmp_path / "k.db"), embedder=None)
        ks.add_fact("TestCorp", "has_director", "Dir A")
        facts = ks.facts_for("TestCorp")
        assert len(facts) == 1
        eid = ks.add_entity("TestCorp", kind="company")
        ks.add_relation(eid, "parent_of", "SubCo")
        rels = ks.relations_for(eid)
        assert len(rels) == 1
        ks.close()


class TestAuditLog:
    def test_record_and_query(self, tmp_path):
        al = AuditLog(str(tmp_path / "audit.jsonl"))
        al.record(actor="agent_1", action="route", user="admin",
                  detail={"x": 1}, result="ok")
        al.record(actor="agent_2", action="retrieve", user="admin",
                  result="found")
        al.record(actor="agent_1", action="classify", user="analyst",
                  result="classified")
        assert len(al.entries()) == 3
        assert len(al.query(actor="agent_1")) == 2
        assert len(al.query(user="analyst")) == 1
        assert len(al.query(action="retrieve")) == 1

    def test_append_only_lines_are_json(self, tmp_path):
        path = str(tmp_path / "audit.jsonl")
        al = AuditLog(path)
        al.record(actor="a", action="b")
        with open(path) as f:
            line = f.readline().strip()
        parsed = json.loads(line)
        assert parsed["actor"] == "a"


class TestMemorySystem:
    def test_working_memory(self, tmp_path):
        ms = MemorySystem(str(tmp_path))
        ms.start_task("t1", {"a": 1})
        ms.update_working("t1", b=2)
        assert ms.get_working("t1") == {"a": 1, "b": 2, "task_id": "t1"} or \
               ms.get_working("t1").get("b") == 2
        ms.clear_task("t1")
        assert ms.get_working("t1") == {}

    def test_durable_store_and_recall(self, tmp_path):
        ms = MemorySystem(str(tmp_path))
        ms.store("semantic", "Fact: deadline is 2026-12-01",
                 provenance="doc1", scope="default")
        entries = ms.recall("semantic")
        assert len(entries) == 1
        assert entries[0].content.startswith("Fact:")

    def test_candidate_promote_reject(self, tmp_path):
        ms = MemorySystem(str(tmp_path))
        eid = ms.store("procedural", "Skill: how to file X",
                       status="candidate")
        active = [e for e in ms.recall("procedural", status="active")]
        assert len(active) == 0
        assert ms.promote(eid, "procedural") is True
        active = [e for e in ms.recall("procedural", status="active")]
        assert len(active) == 1
        assert ms.reject(eid, "procedural") is True
        rejected = [e for e in ms.recall("procedural", status="rejected")]
        assert len(rejected) == 1


class TestPolicyEngine:
    def test_identify_and_ceiling(self):
        settings = _settings()
        pe = PolicyEngine(settings)
        admin = pe.identify("admin")
        assert admin is not None
        assert admin.max_sensitivity == "restricted"
        analyst = pe.identify("analyst")
        assert analyst.max_sensitivity == "internal"
        assert pe.identify("nobody") is None

    def test_can_read(self):
        settings = _settings()
        pe = PolicyEngine(settings)
        analyst = pe.identify("analyst")
        assert pe.can_read(analyst, "internal") is True
        assert pe.can_read(analyst, "restricted") is False
        admin = pe.identify("admin")
        assert pe.can_read(admin, "restricted") is True

    def test_approver_and_voice_roles(self):
        settings = _settings()
        pe = PolicyEngine(settings)
        assert pe.can_approve(pe.identify("reviewer")) is True
        assert pe.can_approve(pe.identify("analyst")) is False
        assert pe.can_voice(pe.identify("admin")) is True

    def test_source_allowlist(self):
        settings = _settings()
        pe = PolicyEngine(settings)
        assert pe.is_source_permitted("https://www.indiacode.nic.in/act") is True
        assert pe.is_source_permitted("https://evil.example.com") is False


class TestApprovalGate:
    def test_lifecycle(self, tmp_path):
        al = AuditLog(str(tmp_path / "audit.jsonl"))
        gate = ApprovalGate(str(tmp_path / "approvals.jsonl"), al)
        req = gate.request("draft", "Test draft", {"body": "x"},
                           requested_by="analyst")
        assert req.status == "pending"
        assert len(gate.pending()) == 1
        decided = gate.decide(req.id, "approved", "reviewer", "looks good")
        assert decided.status == "approved"
        assert decided.decided_by == "reviewer"
        assert len(gate.pending()) == 0
        # audit trail has both events
        actions = [e["action"] for e in al.entries()]
        assert "approval_requested" in actions
        assert "approval_approved" in actions

    def test_invalid_decision(self, tmp_path):
        al = AuditLog(str(tmp_path / "audit.jsonl"))
        gate = ApprovalGate(str(tmp_path / "approvals.jsonl"), al)
        req = gate.request("draft", "t")
        with pytest.raises(ValueError):
            gate.decide(req.id, "maybe", "reviewer")


class TestOllamaHelpers:
    def test_extract_json_bare(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_extract_json_fenced(self):
        assert extract_json('here you go:\n```json\n{"a": 2}\n```\nthanks') == {"a": 2}

    def test_extract_json_embedded(self):
        assert extract_json('The result is {"a": 3} as requested.') == {"a": 3}

    def test_extract_json_invalid(self):
        assert extract_json("no json here") is None

    def test_mock_client(self):
        mc = MockOllamaClient(responses={"classify": '{"agents": ["x"]}'})
        out = mc.chat([{"role": "user", "content": "please classify"}],
                      model="llama3.1:8b")
        assert extract_json(out) == {"agents": ["x"]}
        vec = mc.embed_one("hello", "nomic-embed-text")
        assert len(vec) == 768


def _settings():
    """Minimal settings for policy tests (no file IO)."""
    from agent_platform.core.config import Settings, PolicyConfig, UserConfig
    return Settings(policy=PolicyConfig(
        users=[UserConfig("admin", "admin"),
               UserConfig("reviewer", "reviewer"),
               UserConfig("analyst", "analyst")],
        approver_roles=["admin", "reviewer"],
        voice_roles=["admin", "reviewer"],
        permitted_external_sources=["https://www.indiacode.nic.in"],
    ))