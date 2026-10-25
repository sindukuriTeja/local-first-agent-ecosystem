# Local-First Agent Ecosystem — Phase 1

A **16-agent legal/compliance AI platform** that runs entirely on your own
hardware. All inference is local (Ollama), all knowledge is stored locally,
every action is audited, and nothing leaves the machine except through a
single, allowlisted, audited egress path.

> **Private data stays inside.** Single entry/exit point. Mandatory human
> review. Full audit trail.

## Design principles

| Principle | How it's enforced |
|---|---|
| **Local-first** | Ollama for all chat + embedding inference. No external model calls. |
| **Single entry/exit** | Agent 1 (Orchestrator) is the only public entry point and the only thing that talks to the user. |
| **Internal-first retrieval** | Agent 2 always checks stored knowledge before any external lookup. |
| **Cleaned egress only** | Only Agent 3 may touch external sources, only with a *cleaned* question, only against an allowlist. |
| **Mandatory human review** | Drafts (Agent 7), external sharing (Agent 15), and voice (Agent 16) require an authorized reviewer. |
| **Full audit** | Every agent run, retrieval, egress, and approval is written to an append-only audit log. |
| **Access-scoped memory** | Every record has a sensitivity level; retrieval is filtered by the caller's role ceiling. |

## The 16 agents

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | **Orchestrator** | Single entry/exit. Identifies user, classifies, assigns agents, controls order, waits for approval, combines the final sourced answer. |
| 2 | **Internal Information** | Only internal information desk. Checks stored knowledge first, checks access, saves sourced answers, returns source/date/status. Emits a *cleaned* question if info is missing. |
| 3 | **External Information** | Only receives cleaned questions. Uses official/permitted public sources (allowlisted). Returns source link + date. All egress audited. |
| 4 | **Document Intake & OCR** | Ingests scans/PDFs/photos/emails. Keeps originals unchanged. OCR + field extraction with confidence. Marks *Unreviewed*. Flags duplicates. Routes the document. |
| 5 | **Case Analysis** | Facts, timeline, evidence, conflicts, missing information. Routes missing items to Agent 2. |
| 6 | **Legal Research** | Verified statutes, judgments, source-linked citations. Saves reusable research. Routes cleaned questions to Agent 3. |
| 7 | **Drafting** | Source-linked drafts. Verifies key fields via Agent 2. Every draft is *Draft – Needs Approval* (mandatory human review). |
| 8 | **Compliance & Risk** | Deadlines, limitation periods, filings, risks, alerts. Feeds Reporting (#15) and Voice (#16). |
| 9 | **Build Documentation** | Observes build activity. Maintains prompt/config version history and change log. |
| 10 | **Query & Support** | Answers and summaries with source links. Abstains when there's no source. |
| 11 | **Entity & Company Intelligence** | Company profiles, group structure, directors, shareholding (knowledge graph). |
| 12 | **Debt & Settlement** | Facilities, claims, offers, payments, security release. **No settlement commitment.** |
| 13 | **Land & Title** | Parcels, title chain, mortgages, disputes, approvals. Feeds due dates to Compliance (#8). |
| 14 | **Tax Intelligence** | Notices, demands, due dates, appeals, payments, pre-deposits. Feeds deadline/risk to Compliance (#8). |
| 15 | **Reporting & Analytics** | Dashboards, board view, PDF/Word/Excel reports from **verified/labelled data only**. External sharing needs approval. |
| 16 | **Voice Notification** | Approved message only. Consent + calling hours + identity check + acknowledgement. Simulated provider in Phase 1. |

## Architecture

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the full component
diagram, data flows, and how each box in the Phase 1 design maps to code.

```
User ──> Agent 1 Orchestrator ──> specialist agents (2–16)
              │                          │
              │  (task + policy)         ▼
              │                  Local Knowledge Store
              │                  (SQLite + vector + BM25 + graph)
              ▼                          ▲
       Ollama (local inference) ─────────┘
              │
              ▼
       Append-only Audit Log  +  Approval Gate (human review)
```

## Quick start

### 1. Prerequisites

- **Python 3.10+**
- **[Ollama](https://ollama.com)** running locally

### 2. Pull the models

```bash
ollama pull llama3.1:8b        # default chat/reasoning model
ollama pull nomic-embed-text   # local embedding model (hybrid retrieval)
```

### 3. Install & run

```bash
cd local-first-agent-ecosystem
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# List the agents
python -m agent_platform.cli agents

# Confirm Ollama is reachable
python -m agent_platform.cli models

# Ask a question (routed through the Orchestrator)
python -m agent_platform.cli ask --user admin "What is the filing deadline for matter A?"

# Ingest a document (Agent 4)
python -m agent_platform.cli ingest --user admin --file path/to/notice.pdf
```

### 4. Run the API server (optional)

```bash
python -m agent_platform.server
# -> http://127.0.0.1:8000  (docs at /docs)
```

Key endpoints: `POST /ask`, `POST /ingest`, `GET /agents`, `GET /models`,
`GET /approvals`, `POST /approvals/decide`, `GET /audit`, `GET /health`.

### 5. Run the tests

Tests use a mocked Ollama client, so **no model is needed** to run them:

```bash
python -m pytest tests/ -q
```

## Configuration

Everything lives in **[`config/settings.yaml`](config/settings.yaml)**:

- **`ollama`** — base URL, default model, per-agent model overrides, embedding model.
- **`policy`** — users + roles, approver/voice roles, sensitivity ladder, **permitted external sources** (the egress allowlist).
- **`agents.enabled`** — toggle any of the 16 agents on/off.
- **`agents.voice`** — calling hours, consent/identity/ack requirements, provider.
- **`retrieval`** — hybrid search weights (keyword vs. vector), top-k, min score.

## Security model

- **Identity & role ceilings** — each role can only read up to a sensitivity
  level (`analyst`→internal, `reviewer`→confidential, `admin`→restricted).
- **Egress allowlist** — Agent 3 can only use URLs in
  `policy.permitted_external_sources`. Everything else is blocked.
- **Cleaned questions** — internal identifiers/amounts are stripped before any
  external lookup.
- **Approval gate** — drafts, external sharing, and voice notifications cannot
  complete without an authorized reviewer's decision.
- **Append-only audit** — who/what/when/sources/result for every action.
- **Right-to-forget** — invalidating a document propagates to its derived facts.

## Project layout

```
local-first-agent-ecosystem/
├── config/settings.yaml          # all configuration
├── agent_platform/
│   ├── core/                     # shared services
│   │   ├── config.py             # settings loader
│   │   ├── ollama.py             # local inference client + model registry
│   │   ├── knowledge.py          # SQLite + vector + BM25 + graph store
│   │   ├── memory.py             # working/semantic/episodic/procedural memory
│   │   ├── policy.py             # identity, sensitivity, egress allowlist
│   │   ├── approval.py           # human approval gate
│   │   ├── audit.py              # append-only audit log
│   │   └── base_agent.py         # BaseAgent + context/result types
│   ├── agents/                   # the 16 agents
│   │   ├── agent_01_orchestrator.py
│   │   ├── ... (agent_02 .. agent_16)
│   │   └── registry.py           # builds + wires all agents
│   ├── platform.py               # factory: wires services + agents
│   ├── server.py                 # FastAPI local server
│   └── cli.py                    # command-line interface
├── tests/                        # pytest suite (mocked Ollama)
├── docs/ARCHITECTURE.md          # full architecture reference
├── requirements.txt
└── data/                         # runtime data (gitignored)
```

## Phase 1 scope & future work

**In Phase 1:** all 16 agents, local Ollama inference, hybrid retrieval,
document intake with OCR + field extraction, the full approval + audit +
policy layer, and a simulated voice provider.

**Intentionally deferred (later phases):**
- The **self-learning engine** (trajectory store → insight miner →
  verification gate → model promotion) from the full ecosystem diagram.
- A **real telephony provider** for Agent 16 (currently simulated/logged).
- **Live web fetching** for Agent 3 (currently served from a local cache of
  pre-approved public documents to stay fully offline).
- A **rich UI** for the human reviewer (the API/CLI cover the same flows).

## License

MIT — see [LICENSE](LICENSE).