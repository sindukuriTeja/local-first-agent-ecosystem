"""Local FastAPI server for the platform.

Binds to 127.0.0.1 only (local-first). Endpoints:

    POST /ask              route a request through the Orchestrator
    POST /ingest           ingest a document (multipart upload)
    GET  /agents           list agents
    GET  /models           list Ollama models
    GET  /approvals        list pending approvals
    POST /approvals/decide decide an approval
    GET  /audit            query the audit log
    GET  /health           liveness + Ollama availability

Run:
    python -m agent_platform.server
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "FastAPI is required for the server: pip install fastapi uvicorn python-multipart"
    ) from e

from .platform import create_platform
from .reviewer import make_reviewer_routes

app = FastAPI(title="Local-First Agent Ecosystem — Phase 1+2",
              description="16-agent legal/compliance platform, local Ollama inference, "
                          "self-learning engine, reviewer UI.")

# Lazily-created platform (so import works without Ollama running)
_platform = None


def get_platform():
    global _platform
    if _platform is None:
        _platform = create_platform()
    return _platform


class AskRequest(BaseModel):
    user: str
    request: str
    tenant: str = "default"
    state: Dict[str, Any] = {}


class ApproveRequest(BaseModel):
    approval_id: str
    user: str
    decision: str  # approved | rejected | corrected
    note: str = ""
    corrected_payload: Dict[str, Any] = {}


@app.get("/health")
def health():
    p = get_platform()
    return {
        "status": "ok",
        "platform": p.settings.platform_name,
        "phase": p.settings.phase,
        "ollama_available": p.services.ollama.is_available(),
        "default_model": p.settings.ollama.default_model,
        "agents": len(p.agents),
        "pending_approvals": len(p.pending_approvals()),
        "documents": len(p.knowledge.list_documents(limit=10000)),
    }


@app.post("/ask")
def ask(req: AskRequest):
    p = get_platform()
    result = p.handle_request(req.user, req.request, req.tenant, req.state)
    return {
        "agent_id": result.agent_id,
        "status": result.status,
        "answer": result.answer,
        "data": result.data,
        "sources": result.sources,
        "approval_id": result.approval_id,
        "error": result.error,
        "latency_ms": result.latency_ms,
    }


@app.post("/ingest")
async def ingest(file: UploadFile = File(...), user: str = "admin",
                 sensitivity: str = "internal", tenant: str = "default"):
    p = get_platform()
    # Save upload to a temp path, then ingest
    import tempfile
    suffix = os.path.splitext(file.filename or "upload")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = p.run_agent(
            "agent_4_document_intake_ocr", user,
            f"Ingest document {file.filename}",
            tenant, state={"files": [tmp_path], "sensitivity": sensitivity},
        )
    finally:
        os.unlink(tmp_path)
    return {
        "agent_id": result.agent_id,
        "status": result.status,
        "answer": result.answer,
        "data": result.data,
        "approval_id": result.approval_id,
        "error": result.error,
    }


@app.get("/agents")
def agents():
    p = get_platform()
    return [
        {"id": aid, "name": a.name, "responsibility": a.responsibility,
         "enabled": p.settings.is_agent_enabled(aid)}
        for aid, a in p.agents.items()
    ]


@app.get("/models")
def models():
    p = get_platform()
    return {"models": p.services.ollama.list_models()}


@app.get("/approvals")
def approvals(kind: Optional[str] = None):
    p = get_platform()
    return [a.__dict__ for a in p.pending_approvals(kind)]


@app.post("/approvals/decide")
def decide(req: ApproveRequest):
    p = get_platform()
    try:
        decision = p.decide_approval(req.approval_id, req.decision, req.user,
                                     req.note, req.corrected_payload or None)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if decision is None:
        raise HTTPException(status_code=404, detail="approval not found")
    return decision.__dict__


@app.get("/audit")
def audit(actor: Optional[str] = None, action: Optional[str] = None,
          user: Optional[str] = None, limit: int = 100):
    p = get_platform()
    return p.audit_query(actor, action, user, limit)


# Reviewer web UI + the extra endpoints it needs (/reviewer, /documents,
# /search, /learning, /learn).
make_reviewer_routes(app, get_platform)


def run(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()