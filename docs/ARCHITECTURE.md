# Architecture Reference — Phase 1

This document maps the **Phase 1 architecture diagram** ("AI Agent Platform —
Phase 1 Architecture Design") to the implementation in this repository, and
explains how it fits the larger **Self-Learning, Local-First Agent Ecosystem**.

## 1. System overview

```
                        ┌─────────────────────────────────────────────┐
                        │        Internal platform — private data     │
                        │                 stays inside                │
                        └─────────────────────────────────────────────┘

  User ──request/upload──> ┌──────────────────────┐ <──final answer w/ sources── User
                           │ 1. ORCHESTRATOR AGENT │ <──scheduled alert── (scheduler)
                           │ single entry & exit   │
                           └──────────┬───────────┘
        assigns matter work    assigns research/drafting    assigns query/domain work
              │                        │                            │
   ┌──────────▼─────────┐   ┌──────────▼──────────┐        ┌────────▼─────────┐
   │ 2. INTERNAL INFO   │   │ 6. LEGAL RESEARCH   │        │ 10. QUERY &      │
   │ (only internal     │   │ 7. DRAFTING         │        │ SUPPORT          │
   │  information desk) │   │ 5. CASE ANALYSIS    │        │ 11–14 DOMAIN     │
   └──────────┬─────────┘   └──────────┬──────────┘        │ AGENTS           │
   stored     │  if missing:           │ mandatory review  └────────┬─────────┘
   knowledge  │  cleaned question      ▼                            │
   (store)    │           ┌────────────┴───────────┐                │
   ┌──────────▼──┐        │ AUTHORIZED HUMAN       │                │
   │ 3. EXTERNAL │<───────│ REVIEWER               │<─── alerts ────┤
   │ INFORMATION │cleaned │ approve/verify/        │                │
   └──────┬──────┘        │ correct/reject         │                │
          │               └────────────────────────┘                │
          ▼                                                         ▼
  Official/permitted                              ┌─────────────────────────────┐
  public sources                                  │ 8. COMPLIANCE & RISK       │
  (allowlisted)                                   │ 15. REPORTING & ANALYTICS   │
                                                  │ 16. VOICE NOTIFICATION      │
                                                  └─────────────────────────────┘
   4. DOCUMENT INTAKE & OCR ──> Stored knowledge (searchable text, fields, metadata)
   9. BUILD DOCUMENTATION ──observes build activity──> version history / change log

   EVERY agent + store ──────────────────────────────> AUDIT LOG (who/what/when, sources, result)
```

## 2. Component → code mapping

| Diagram component | Code | Notes |
|---|---|---|
| User | CLI (`cli.py`) / API client (`server.py`) | Identified by username in `policy.users` |
| 1. Orchestrator Agent | `agents/agent_01_orchestrator.py` | Classify → assign → run in order → combine. Max-hop guard. |
| 2. Internal Information Agent | `agents/agent_02_internal_information.py` | Retrieval-first; emits `cleaned_question` when missing. |
| 3. External Information Agent | `agents/agent_03_external_information.py` | Only egress path. Allowlist + cleaned question + audit. `LocalCacheFetcher` (offline) or pluggable `WebFetcher`. |
| 4. Document Intake & OCR Agent | `agents/agent_04_document_intake_ocr.py` | Originals kept unchanged (SHA-256), text/PDF/email extraction, pluggable OCR, field extraction w/ confidence, duplicate flag, `unreviewed` status, critical fields → approval. |
| 5. Case Analysis Agent | `agents/agent_05_case_analysis.py` | Facts/timeline/evidence/conflicts/missing; routes missing → Agent 2. |
| 6. Legal Research Agent | `agents/agent_06_legal_research.py` | Verified material + citations; saves reusable research; routes cleaned question → Agent 3. |
| 7. Drafting Agent | `agents/agent_07_drafting.py` | Source-linked draft; verifies key fields via Agent 2's store; **always** raises a `draft` approval. |
| 8. Compliance & Risk Agent | `agents/agent_08_compliance_risk.py` | Deadlines/limitation/filings/risks/alerts; routes unacknowledged alerts → Agent 16, status → Agent 15. |
| 9. Build Documentation Agent | `agents/agent_09_build_documentation.py` | Observes build activity; `change_log.jsonl` + `version_history.json`. |
| 10. Query & Support Agent | `agents/agent_10_query_support.py` | Sourced answers/summaries; abstains without sources. |
| 11. Entity & Company Intelligence | `agents/agent_11_entity_intelligence.py` | Profiles + knowledge-graph entities/relations + shareholding facts. |
| 12. Debt & Settlement Agent | `agents/agent_12_debt_settlement.py` | Facilities/claims/offers/payments/security; **no settlement commitment** (commitment language is detected and flagged). |
| 13. Land & Title Agent | `agents/agent_13_land_title.py` | Parcels/title chain/mortgages/disputes/approvals; due dates → Agent 8. |
| 14. Tax Intelligence Agent | `agents/agent_14_tax_intelligence.py` | Notices/demands/due dates/appeals/payments/pre-deposits; deadline/risk → Agent 8. |
| 15. Reporting & Analytics Agent | `agents/agent_15_reporting.py` | Verified/labelled data only; report artifacts in `data/build_docs/`; external sharing → `external_share` approval; message → Agent 16. |
| 16. Voice Notification Agent | `agents/agent_16_voice_notification.py` | Gates: approved message → role → calling hours → consent → identity check → call (simulated) → call log back to Agent 8. |
| Stored knowledge + source records + extracted fields + matter records | `core/knowledge.py` (SQLite: `documents`, `chunks`, `facts`, `entities`, `relations`) | Sensitivity + tenant scoped. |
| Official/permitted public sources | `config/settings.yaml → policy.permitted_external_sources` | Egress allowlist. |
| Authorized human reviewer | `core/approval.py` + `POST /approvals/decide` / `cli approve` | Role-restricted (`approver_roles`). |
| Audit log | `core/audit.py` (`data/audit_log.jsonl`) | Append-only; who/what/when/sources/result. |
| Approved recipients/channels | `voice_recipients` in request state + consent facts in store | Phase 1: simulated provider. |
| Scheduled alert | `POST /ask` with a scheduled trigger (platform-level) | Wire to a scheduler in deployment. |

## 3. Core services (the "L0–L3" substrate)

| Ecosystem layer | Phase 1 implementation |
|---|---|
| **L0 Orchestration** | Orchestrator (planner/router) + shared state (`AgentContext.state`) as the blackboard. |
| **L1 Local inference runtime** | `core/ollama.py`: Ollama OpenAI-compatible client + `ModelRegistry` (task → model + config + version, per-agent overrides in config). |
| **L2 Memory system** | `core/memory.py`: working (per-task, ephemeral), semantic/episodic/procedural (JSONL, versioned, candidate→active promotion). |
| **L3 Local knowledge substrate** | `core/knowledge.py`: hybrid Retrieval API (dense vector + BM25 keyword + graph/SQL filters), structured store, knowledge graph. |
| **L7 Governance** | `core/policy.py` (data-boundary policy engine), `core/approval.py` (human approval UI backend), egress allowlist (air-gap by default — no network unless a fetcher is plugged in), `core/audit.py` (append-only signed-by-timestamp audit). |

## 4. Request lifecycle

1. **Entry** — `platform.handle_request(user, request)` resolves the
   identity via the policy engine (unknown user → denied + audited).
2. **Classify** — the Orchestrator asks the local model to classify the
   request and pick the minimum agent set (validated against the route
   table; unknown ids are dropped).
3. **Route** — each selected agent runs in order with the shared
   `AgentContext` (task + policy context travels with the task).
   Upstream results are propagated into `ctx.state` so downstream agents
   consume them (e.g. Case Analysis → Drafting; Internal Info's
   `cleaned_question` → External Info).
4. **Ground** — every answering agent retrieves from the local knowledge
   store *before* answering from parametric knowledge, filtered by the
   caller's sensitivity ceiling. Agents cite sources and may abstain.
5. **Approve** — drafts / external sharing / voice raise approval
   requests; the run returns `needs_approval` with the approval id.
6. **Combine** — the Orchestrator synthesizes a single sourced answer
   (or returns the single agent's answer).
7. **Audit** — every step (identify, classify, assign, run, retrieve,
   egress, approve) is written to the append-only audit log.

## 5. Egress control (the only path out)

```
Agent 2 (missing internally)
   → cleaned_question (identifiers/amounts stripped)
Agent 3
   → policy.is_source_permitted(url)   [allowlist]
   → fetcher (LocalCacheFetcher offline / WebFetcher optional)
   → audit: egress_request + egress_result (question, sources, count)
   → result saved back to stored knowledge (future questions stay internal)
```

With the default `LocalCacheFetcher` the platform is **fully offline**:
the cache (`data/external_cache.json`) is populated ahead of time by an
operator from the allowlisted sources.

## 6. Human approval lifecycle

```
pending ──decide──> approved | rejected | corrected
```

- Kinds: `draft` (Agent 7), `external_share` (Agent 15),
  `document_review` (Agent 4 critical fields), `other`.
- Only roles in `policy.approver_roles` may decide (enforced in
  `platform.decide_approval` and the API, 403 otherwise).
- Every request/decision is audited; decisions are persisted in
  `data/approvals.jsonl`.

## 7. Data model (SQLite, `data/knowledge.db`)

- **documents** — id, title, content, source, doc_type, sensitivity,
  tenant, status (`active`/`unreviewed`/`deleted`), timestamps, metadata.
- **chunks** — document_id, chunk_index, content, embedding (float32 blob).
- **facts** — subject/predicate/object, source_doc, confidence, sensitivity.
- **entities / relations** — knowledge graph (entity intelligence, group
  structure, shareholding).

**Right-to-forget:** `invalidate_document` marks the document `deleted` and
zeroes the confidence of every fact citing it (provenance-based
propagation).

## 8. Sensitivity ladder & roles

| Role | Read ceiling | Approve | Voice |
|---|---|---|---|
| analyst | internal | ✗ | ✗ |
| reviewer | confidential | ✓ | ✓ |
| admin | restricted | ✓ | ✓ |

Sensitivities: `public < internal < confidential < restricted`. Agent 4
auto-classifies ingested documents (local model, best-effort); operators
can override at ingest time.

## 9. Relationship to the full ecosystem

Phase 1 implements the **operating platform** (agents, knowledge,
governance). The layers from the complete ecosystem diagram that are
**scaffolded but not yet active**:

- **L4 Learning Engine** — the trajectory store (audit log + episodic
  memory) already captures task traces; the insight miner, verification
  gate, and model-promotion pipeline are the next phase. The
  `ModelRegistry` is already versioned and promotion-ready.
- **Air-gap switch** — Phase 1 is air-gapped by default (no fetcher
  network access). The egress gateway is the allowlist + audit in Agent 3.
- **Evaluation dashboard** — the audit log + approval history are the raw
  inputs; a dashboard is a later phase.

## 10. Extending the platform

- **Add an agent**: subclass `BaseAgent`, implement `run(ctx)`, register it
  in `agents/registry.py` and in the Orchestrator's `ROUTE_TABLE`, enable
  it in config.
- **Swap the LLM**: change `ollama.default_model` or per-agent
  `model_overrides` in `config/settings.yaml` (e.g. `qwen2.5:7b` for
  reasoning-heavy agents).
- **Real OCR**: pass an `ocr_fn` to `DocumentIntakeOcrAgent` (e.g.
  Tesseract) or install `pytesseract` + `Pillow`.
- **Real telephony**: implement `VoiceProvider` and pass it to
  `VoiceNotificationAgent`.
- **Live egress**: implement `BaseFetcher` in Agent 3 with a proper reader
  against the allowlisted domains.