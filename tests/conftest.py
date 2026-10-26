"""Shared test fixtures: a platform wired with MockOllamaClient."""

from __future__ import annotations

import json
import os
import sys

import pytest

# Make the project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_platform.core.ollama import MockOllamaClient
from agent_platform.platform import create_platform

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mock_client(tmp_path):
    """A mock Ollama client with canned JSON responses for each agent's
    expected prompt content."""
    responses = {
        # Orchestrator classification
        "Classify the user's request": json.dumps({
            "intent": "internal question",
            "agents": ["agent_2_internal_information"],
            "reason": "simple internal question",
        }),
        # Orchestrator combine (multi-agent)
        "combining specialist agent outputs": "Combined answer with sources.",
        # Internal Information
        "Answer ONLY from the provided stored-knowledge evidence": (
            "The matter is active. (source: seed-doc.txt, date: 2026-01-01)"
        ),
        # External Information
        "Answer using ONLY the provided public-source facts": (
            "Per the public source, the statute was amended in 2024. "
            "(source: https://www.indiacode.nic.in, collected: 2026-01-02)"
        ),
        # Case Analysis
        "Analyze the matter": json.dumps({
            "facts": ["Fact A from evidence"],
            "timeline": [{"date": "2025-01-01", "event": "Event A"}],
            "evidence": [{"item": "Doc A", "source": "seed-doc.txt"}],
            "conflicts": [],
            "missing_information": ["Missing item X"],
        }),
        # Legal Research
        "Answer the legal question using ONLY the provided verified": json.dumps({
            "answer": "The applicable provision is Section 12.",
            "citations": [{"authority": "Statute X", "provision": "Sec 12",
                           "source": "indiacode", "date": "2024-05-01"}],
            "confidence": 0.8,
            "needs_external": False,
            "cleaned_question": "",
        }),
        # Drafting
        "Draft the requested document": json.dumps({
            "title": "Test Notice",
            "body": "DRAFT NOTICE: This is a draft requiring approval.",
            "sources": ["seed-doc.txt"],
            "key_fields": [{"name": "date", "value": "2026-01-01",
                            "verified": True}],
            "disclaimers": ["Draft - Needs Approval"],
        }),
        # Compliance
        "Assess compliance and risk": json.dumps({
            "deadlines": [{"item": "Filing D", "due_date": "2026-12-01",
                           "type": "filing", "source": "seed-doc.txt"}],
            "limitation_periods": [],
            "filings": [],
            "risks": [{"risk": "Risk R", "severity": "medium",
                       "source": "seed-doc.txt"}],
            "alerts": [{"message": "Deadline approaching", "severity": "high",
                        "requires_acknowledgement": True}],
            "summary": "One deadline, one risk.",
        }),
        # Query & Support
        "Answer the question or produce the summary using ONLY": json.dumps({
            "answer": "Sourced summary. (source: seed-doc.txt)",
            "sources": ["seed-doc.txt"],
        }),
        # Entity Intelligence
        "Produce an entity/company intelligence profile": json.dumps({
            "entity": "TestCorp Ltd",
            "profile": "A test company.",
            "group_structure": [{"entity": "SubCo", "relation": "subsidiary",
                                 "parent": "TestCorp Ltd"}],
            "directors": ["Dir A"],
            "shareholding": [{"holder": "Holder A", "percentage": "51%",
                              "source": "mca"}],
            "sources": ["mca"],
        }),
        # Debt
        "Summarize debt and settlement status": json.dumps({
            "facilities": [{"name": "Fac F", "amount": "1000000",
                            "status": "active", "source": "seed-doc.txt"}],
            "claims": [],
            "offers": [],
            "payments": [],
            "security_release": [{"item": "Security S", "status": "held",
                                  "source": "seed-doc.txt"}],
            "flags": [],
            "summary": "One facility, no commitment made.",
        }),
        # Land & Title
        "Produce a land & title status": json.dumps({
            "parcels": [{"parcel": "P1", "location": "Loc", "area": "1000",
                         "status": "clear", "source": "seed-doc.txt"}],
            "title_chain": [{"owner": "Owner A", "date": "2020-01-01",
                             "instrument": "Sale deed", "source": "seed"}],
            "mortgages": [],
            "disputes": [],
            "approvals": [],
            "due_dates": [{"item": "Registration", "due_date": "2026-11-01",
                           "source": "seed-doc.txt"}],
            "summary": "One parcel, one due date.",
        }),
        # Tax
        "Produce a tax intelligence summary": json.dumps({
            "notices": [{"notice": "Notice N", "date": "2026-01-01",
                         "status": "open", "source": "seed-doc.txt"}],
            "demands": [],
            "due_dates": [{"item": "Payment P", "due_date": "2026-10-31",
                           "source": "seed-doc.txt"}],
            "appeals": [],
            "payments": [],
            "pre_deposits": [],
            "summary": "One notice, one due date.",
        }),
        # Reporting
        "Produce a report from VERIFIED/LABELLED data only": json.dumps({
            "title": "Board Report",
            "format": "board_view",
            "sections": [{"heading": "Overview", "content": "All clear.",
                          "data_label": "verified"}],
            "key_metrics": [{"metric": "Open deadlines", "value": "1",
                             "source": "compliance"}],
            "sources": ["compliance"],
            "requires_external_sharing": False,
        }),
        # Sensitivity classification (Agent 4)
        "Classify the sensitivity of this document": json.dumps({
            "sensitivity": "confidential", "reason": "matter specifics",
        }),
        # Field extraction (Agent 4)
        "You are a document field extractor": json.dumps({
            "fields": [
                {"name": "date", "value": "2026-01-01", "confidence": 0.9},
                {"name": "amount", "value": "500000", "confidence": 0.6},
            ]
        }),
    }
    return MockOllamaClient(responses=responses)


@pytest.fixture()
def platform(tmp_path):
    """A full platform with a mock Ollama client and a seeded knowledge
    store. Config points at a temp data dir."""
    import yaml

    config = {
        "platform": {"name": "Test Platform", "phase": 1},
        "ollama": {
            "base_url": "http://127.0.0.1:11434",
            "default_model": "llama3.1:8b",
            "embedding_model": "nomic-embed-text",
            "embedding_dim": 768,
        },
        "storage": {
            "data_dir": str(tmp_path / "data"),
            "database": str(tmp_path / "data" / "knowledge.db"),
            "documents_dir": str(tmp_path / "data" / "documents"),
            "audit_log": str(tmp_path / "data" / "audit_log.jsonl"),
            "build_docs_dir": str(tmp_path / "data" / "build_docs"),
        },
        "retrieval": {"top_k": 6, "keyword_weight": 0.4,
                      "vector_weight": 0.6, "min_score": 0.2},
        "policy": {
            "users": [
                {"username": "admin", "role": "admin"},
                {"username": "reviewer", "role": "reviewer"},
                {"username": "analyst", "role": "analyst"},
                {"username": "employee1", "role": "employee"},
                {"username": "manager1", "role": "manager"},
                {"username": "counsel1", "role": "counsel"},
                {"username": "client1", "role": "client"},
                {"username": "tenant1", "role": "tenant"},
                {"username": "auditor1", "role": "auditor"},
            ],
            "approver_roles": ["admin", "reviewer", "manager", "counsel"],
            "voice_roles": ["admin", "reviewer", "manager"],
            "permitted_external_sources": ["https://www.indiacode.nic.in"],
        },
        "agents": {
            "enabled": {},
            "external": {"fetcher": "cache"},
            "voice": {"provider": "simulated"},
        },
        "learning": {"enabled": True, "budget_per_run": 10,
                     "min_accuracy": 0.6,
                     "exam_path": str(tmp_path / "dataset" / "exam.json")},
        "orchestrator": {"max_hops": 8, "allow_parallel": False},
    }
    config_path = tmp_path / "settings.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)

    # Generate the synthetic dataset into the temp dir and point the
    # learning engine's exam at it.
    dataset_dir = tmp_path / "dataset"
    from scripts.generate_dataset import generate as _gen
    _gen(str(dataset_dir), seed=42)

    p = create_platform(config_path=str(config_path),
                        ollama_client=_mock_client(tmp_path),
                        enable_learning=True,
                        dataset_dir=str(dataset_dir))

    # Also seed a simple matter doc for the Phase 1 retrieval tests.
    p.knowledge.add_document(
        title="Seed Matter Document",
        content=("Matter M-100 is active. The client is TestCorp Ltd. "
                 "The filing deadline is 2026-12-01. Section 12 of Statute X "
                 "applies to this matter. Amount in dispute is 500000."),
        source="seed-doc.txt",
        doc_type="note",
        sensitivity="internal",
        tenant="default",
    )
    return p