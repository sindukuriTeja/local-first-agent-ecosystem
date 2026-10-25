"""Integration tests for the 16 agents, using the mock platform fixture."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestOrchestrator:
    def test_routes_internal_question(self, platform):
        result = platform.handle_request("admin", "What is the filing deadline for matter A?")
        assert result.status in ("ok", "needs_approval")
        assert result.agent_id == "agent_1_orchestrator"
        # It should have run the internal information agent
        steps = [s["agent"] for s in result.data.get("steps", [])]
        assert "agent_2_internal_information" in steps
        assert result.answer

    def test_unknown_user_denied(self, platform):
        result = platform.handle_request("ghost", "hello")
        assert result.status == "error"
        assert "Unknown user" in result.error

    def test_audit_trail_created(self, platform):
        platform.handle_request("admin", "What is the filing deadline for matter A?")
        entries = platform.audit_query(actor="agent_1_orchestrator")
        actions = {e["action"] for e in entries}
        assert "identify_user" in actions
        assert "classify_request" in actions
        assert "assign_agent" in actions


class TestInternalInformation:
    def test_finds_stored_knowledge(self, platform):
        result = platform.run_agent("agent_2_internal_information", "admin",
                                    "What is the filing deadline for matter A?")
        assert result.status == "ok"
        assert result.data.get("found") is True
        assert any("seed-doc" in s for s in result.sources)

    def test_missing_emits_cleaned_question(self, platform):
        result = platform.run_agent("agent_2_internal_information", "admin",
                                    "What is the weather in Tokyo?")
        assert result.status == "ok"
        assert result.data.get("found") is False
        assert "cleaned_question" in result.data

    def test_sensitivity_scoping_blocks_restricted(self, platform):
        platform.knowledge.add_document(
            "Secret", "The board's private salary figures are 999999.",
            source="secret.txt", sensitivity="restricted")
        # analyst (ceiling=internal) must not retrieve it
        result = platform.run_agent("agent_2_internal_information", "analyst",
                                    "What are the board salary figures?")
        assert "999999" not in result.answer


class TestExternalInformation:
    def test_no_cache_abstains(self, platform):
        result = platform.run_agent("agent_3_external_information", "admin",
                                    "cleaned question about statute",
                                    state={"cleaned_question": "statute amendment"})
        assert result.status in ("abstain", "ok")

    def test_uses_cache_when_present(self, platform, tmp_path):
        cache = platform.settings.resolve_path(
            os.path.join(platform.settings.storage.data_dir, "external_cache.json"))
        with open(cache, "w") as f:
            json.dump([{
                "title": "Statute X amendment",
                "url": "https://www.indiacode.nic.in/statute-x",
                "content": "Statute X Section 12 was amended in 2024 to cover matter A.",
                "collected_at": "2026-01-02",
            }], f)
        result = platform.run_agent("agent_3_external_information", "admin",
                                    "statute amendment",
                                    state={"cleaned_question": "statute X amendment matter A"})
        assert result.status == "ok"
        assert any("indiacode" in s for s in result.sources)

    def test_non_allowlisted_source_excluded(self, platform, tmp_path):
        cache = platform.settings.resolve_path(
            os.path.join(platform.settings.storage.data_dir, "external_cache.json"))
        with open(cache, "w") as f:
            json.dump([{
                "title": "Evil source",
                "url": "https://evil.example.com/x",
                "content": "statute amendment matter A evil content",
                "collected_at": "2026-01-02",
            }], f)
        result = platform.run_agent("agent_3_external_information", "admin",
                                    "statute amendment matter A",
                                    state={"cleaned_question": "statute amendment matter A"})
        assert result.status == "abstain"  # evil source filtered out


class TestDocumentIntake:
    def test_ingest_text_file(self, platform, tmp_path):
        doc = tmp_path / "notice.txt"
        doc.write_text("NOTICE dated 2026-01-01. Amount 500000. Party: TestCorp Ltd.")
        result = platform.run_agent("agent_4_document_intake_ocr", "admin",
                                    "ingest", state={"files": [str(doc)]})
        assert result.status == "ok"
        assert result.data.get("doc_id")
        assert result.data.get("extraction_method") == "text"
        # critical field (amount) flagged for review -> approval created
        assert result.approval_id is not None
        # original stored unchanged
        stored = platform.settings.resolve_path(
            os.path.join(platform.settings.storage.documents_dir,
                         result.data["sha256"][:16] + ".txt"))
        assert os.path.isfile(stored)

    def test_duplicate_detection(self, platform, tmp_path):
        doc = tmp_path / "dup.txt"
        doc.write_text("Same content here for duplicate test.")
        r1 = platform.run_agent("agent_4_document_intake_ocr", "admin",
                                "ingest", state={"files": [str(doc)]})
        r2 = platform.run_agent("agent_4_document_intake_ocr", "admin",
                                "ingest", state={"files": [str(doc)]})
        assert r1.status == "ok"
        assert r2.data.get("duplicate_of") == r1.data.get("doc_id")

    def test_no_file_errors(self, platform):
        result = platform.run_agent("agent_4_document_intake_ocr", "admin",
                                    "ingest this please")
        assert result.status == "error"


class TestCaseAnalysis:
    def test_produces_structure_and_routes_missing(self, platform):
        result = platform.run_agent("agent_5_case_analysis", "admin",
                                    "Analyze matter A")
        assert result.status == "ok"
        assert result.data.get("facts")
        assert result.data.get("missing_information")
        assert result.data.get("route_to_internal_information") is True


class TestLegalResearch:
    def test_returns_citations(self, platform):
        result = platform.run_agent("agent_6_legal_research", "admin",
                                    "Which section applies to matter A?")
        assert result.status == "ok"
        assert result.data.get("citations")


class TestDrafting:
    def test_draft_requires_approval(self, platform):
        result = platform.run_agent("agent_7_drafting", "admin",
                                    "Draft a notice for matter A")
        assert result.status == "needs_approval"
        assert result.approval_id is not None
        # pending approval exists
        pending = platform.pending_approvals("draft")
        assert any(a.id == result.approval_id for a in pending)

    def test_approval_flow(self, platform):
        result = platform.run_agent("agent_7_drafting", "admin",
                                    "Draft a notice for matter A")
        decision = platform.decide_approval(result.approval_id, "approved",
                                            "reviewer", "approved")
        assert decision.status == "approved"

    def test_analyst_cannot_approve(self, platform):
        result = platform.run_agent("agent_7_drafting", "admin",
                                    "Draft a notice for matter A")
        with pytest.raises(PermissionError):
            platform.decide_approval(result.approval_id, "approved", "analyst")


class TestCompliance:
    def test_produces_alerts_and_routes_voice(self, platform):
        result = platform.run_agent("agent_8_compliance_risk", "admin",
                                    "Check compliance for matter A")
        assert result.status == "ok"
        assert result.data.get("deadlines")
        assert result.data.get("route_to_voice_notification") is True


class TestBuildDocumentation:
    def test_records_version(self, platform):
        r1 = platform.run_agent("agent_9_build_documentation", "admin", "build")
        r2 = platform.run_agent("agent_9_build_documentation", "admin", "build")
        assert r1.data["version"] == 1
        assert r2.data["version"] == 2


class TestQuerySupport:
    def test_sourced_answer(self, platform):
        result = platform.run_agent("agent_10_query_support", "admin",
                                    "Summarize matter A")
        assert result.status == "ok"
        assert result.data.get("found") is True

    def test_abstains_without_sources(self, platform):
        result = platform.run_agent("agent_10_query_support", "admin",
                                    "quantum flux capacitor specs")
        assert result.status == "abstain"


class TestEntityIntelligence:
    def test_builds_profile_and_graph(self, platform):
        result = platform.run_agent("agent_11_entity_company_intelligence", "admin",
                                    "Company profile for TestCorp Ltd")
        assert result.status == "ok"
        assert result.data.get("entity") == "TestCorp Ltd"
        # entity stored in graph
        entities = platform.knowledge.entities()
        assert any(e["name"] == "TestCorp Ltd" for e in entities)


class TestDebtSettlement:
    def test_no_commitment_flag(self, platform):
        result = platform.run_agent("agent_12_debt_settlement", "admin",
                                    "Debt status for TestCorp")
        assert result.status == "ok"
        assert result.data.get("no_settlement_commitment") is True


class TestLandTitle:
    def test_feeds_compliance(self, platform):
        result = platform.run_agent("agent_13_land_title", "admin",
                                    "Title status for parcel P1")
        assert result.status == "ok"
        assert result.data.get("route_to_compliance") is True


class TestTaxIntelligence:
    def test_feeds_compliance(self, platform):
        result = platform.run_agent("agent_14_tax_intelligence", "admin",
                                    "Tax status for TestCorp")
        assert result.status == "ok"
        assert result.data.get("route_to_compliance") is True


class TestReporting:
    def test_generates_report(self, platform):
        result = platform.run_agent("agent_15_reporting_analytics", "admin",
                                    "Board report for matter A")
        assert result.status in ("ok", "needs_approval")
        assert result.data.get("report_id")
        assert os.path.isfile(result.data["report_path"])


class TestVoiceNotification:
    def test_no_message_blocked(self, platform):
        result = platform.run_agent("agent_16_voice_notification", "admin",
                                    "notify")
        assert result.status == "error"
        assert "approved message" in result.error

    def test_no_consent_skipped(self, platform):
        result = platform.run_agent(
            "agent_16_voice_notification", "admin", "notify",
            state={"voice_message": {"report_title": "R", "key_metrics": []},
                   "voice_recipients": ["+91-111"]})
        assert result.status == "ok"
        assert result.data["placed"] == 0
        assert result.data["skipped"] == 1

    def test_call_with_consent(self, platform):
        platform.knowledge.add_fact("+91-222", "voice_consent", "granted",
                                    confidence=1.0)
        result = platform.run_agent(
            "agent_16_voice_notification", "admin", "notify",
            state={"voice_message": {"report_title": "R", "key_metrics": []},
                   "voice_recipients": ["+91-222"]})
        assert result.status == "ok"
        assert result.data["placed"] == 1
        assert result.data["call_log"][0]["result"] == "simulated"

    def test_analyst_cannot_voice(self, platform):
        result = platform.run_agent(
            "agent_16_voice_notification", "analyst", "notify",
            state={"voice_message": {"report_title": "R", "key_metrics": []},
                   "voice_recipients": ["+91-222"]})
        assert result.status == "error"
        assert "not authorized" in result.error


class TestEndToEnd:
    def test_full_pipeline_with_approval(self, platform):
        # A request that the orchestrator routes to internal info
        result = platform.handle_request(
            "admin", "What is the filing deadline for matter A?")
        assert result.status in ("ok", "needs_approval")
        assert result.answer
        # audit log has entries from multiple agents
        all_entries = platform.audit_query(limit=500)
        actors = {e["actor"] for e in all_entries}
        assert "agent_1_orchestrator" in actors
        assert "agent_2_internal_information" in actors

    def test_all_16_agents_registered(self, platform):
        assert len(platform.agents) == 16
        for i in range(1, 17):
            ids = [a for a in platform.agents if a.startswith(f"agent_{i}_")]
            assert ids, f"missing agent {i}"