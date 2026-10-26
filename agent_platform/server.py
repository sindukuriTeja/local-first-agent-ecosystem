"""Local FastAPI server for the platform.

Binds to 127.0.0.1 only (local-first). Two surfaces:

  * Legacy API  — /ask, /ingest, /agents, /models, /approvals, /audit,
    /health, plus the reviewer UI routes (/reviewer, /documents, /search,
    /learning, /learn).
  * Multi-portal web app — real (demo-grade) session login, one portal per
    role, served as a static SPA from frontend/dist with a /api/* backend:

        POST /api/auth/login        {username, password} -> {token, user}
        POST /api/auth/logout       (Bearer token)
        GET  /api/auth/me           (Bearer token) -> user
        GET  /api/auth/demo         demo credentials for the login screen
        GET  /api/portals           list the 7 portals
        GET  /api/portal            (Bearer token) -> this user's portal data
        POST /api/portal/ai         (Bearer token) {prompt} -> AI-assisted task
        POST /api/portal/request    (Bearer token) {subject, message}
        POST /api/portal/upload     (Bearer token) multipart file
        POST /api/portal/approve    (Bearer token) {approval_id, decision, note}
        GET  /api/admin/users       (admin) user directory
        POST /api/admin/users       (admin) create user
        POST /api/admin/users/enable (admin) enable/disable a user

Run:
    python -m agent_platform.server
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from fastapi import (Depends, FastAPI, File, Header, HTTPException, UploadFile)
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "FastAPI is required for the server: pip install fastapi uvicorn python-multipart"
    ) from e

Dep = Depends  # shorthand used below for readability

from .platform import create_platform
from .portal import PortalService, seed_demo_content
from .reviewer import make_reviewer_routes

# ---------------------------------------------------------------------------
# Request models (module-level so FastAPI can resolve the annotations even
# with `from __future__ import annotations`).
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class AiTaskRequest(BaseModel):
    prompt: str
    state: Dict[str, Any] = {}


class RequestSubmit(BaseModel):
    subject: str
    message: str


class ApproveRequest(BaseModel):
    approval_id: str
    decision: str  # approved | rejected | corrected
    note: str = ""
    corrected_payload: Dict[str, Any] = {}
    # Legacy /approvals/decide identifies the approver in the body; the
    # portal endpoint (/api/portal/approve) uses the session user instead.
    user: Optional[str] = None


class CreateUser(BaseModel):
    username: str
    password: str
    role: str
    display_name: str = ""


class EnableUser(BaseModel):
    username: str
    enabled: bool


class AskRequest(BaseModel):
    user: str
    request: str
    tenant: str = "default"
    state: Dict[str, Any] = {}

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _project_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def _frontend_dist() -> str:
    return os.path.join(_project_root(), "frontend", "dist")


def create_app(platform=None) -> FastAPI:
    """Build the FastAPI app. Pass a pre-built platform to inject a mock
    (used by tests); otherwise the real platform is created lazily."""
    app = FastAPI(
        title="Local-First Agent Ecosystem — Multi-Portal",
        description="16-agent legal/compliance platform, local Ollama inference, "
                    "self-learning engine, 7-role portal web app.",
    )
    state: Dict[str, Any] = {"platform": platform}
    seeded = {"done": False}

    def get_platform():
        p = state["platform"]
        if p is None:
            p = create_platform()
            state["platform"] = p
        if not seeded["done"] and p.knowledge.list_documents(limit=1):
            # First real use: make sure portal demo content exists.
            try:
                seed_demo_content(p)
            except Exception:
                pass
            seeded["done"] = True
        return p

    def svc() -> PortalService:
        return PortalService(get_platform())

    # ---- auth dependency ------------------------------------------------
    def current_user(authorization: Optional[str] = Header(default=None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        p = get_platform()
        user = p.auth.user_for_token(token)
        if user is None:
            raise HTTPException(status_code=401, detail="invalid or expired session")
        return user

    # ---- request models (module-level, see top of file) ----------------

    # ---- auth endpoints -------------------------------------------------
    @app.post("/api/auth/login")
    def login(req: LoginRequest):
        p = get_platform()
        token = p.auth.login(req.username, req.password)
        if not token:
            raise HTTPException(status_code=401, detail="invalid credentials")
        user = p.auth.get_user(req.username)
        p.audit.record(actor=f"user:{req.username}", action="login",
                       detail={"portal": user.portal}, user=req.username,
                       result="ok")
        return {"token": token, "user": user.to_dict()}

    @app.post("/api/auth/logout")
    def logout(user=Header(default=None, alias="Authorization")):
        p = get_platform()
        if user and user.lower().startswith("bearer "):
            p.auth.logout(user.split(" ", 1)[1].strip())
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(user=Dep(current_user)):
        return {"user": user.to_dict()}

    @app.get("/api/auth/demo")
    def demo():
        p = get_platform()
        return {"logins": p.auth.demo_logins()}

    # ---- portal endpoints ----------------------------------------------
    @app.get("/api/portals")
    def portals():
        from .core.auth import PORTALS
        return [
            {"id": pid, "name": v["name"], "tagline": v["tagline"]}
            for pid, v in PORTALS.items()
        ]

    @app.get("/api/portal")
    def portal_data(user=Dep(current_user)):
        return svc().portal_data(user)

    @app.post("/api/portal/ai")
    def portal_ai(req: AiTaskRequest, user=Dep(current_user)):
        return svc().run_ai_task(user, req.prompt, req.state or None)

    @app.post("/api/portal/request")
    def portal_request(req: RequestSubmit, user=Dep(current_user)):
        return svc().submit_request(user, req.subject, req.message)

    @app.post("/api/portal/upload")
    async def portal_upload(file: UploadFile = File(...),
                            sensitivity: str = "internal",
                            user=Dep(current_user)):
        data = await file.read()
        return svc().upload_document(user, file.filename or "upload", data,
                                     sensitivity)

    @app.post("/api/portal/approve")
    def portal_approve(req: ApproveRequest, user=Dep(current_user)):
        try:
            decision = svc().decide_approval(user, req.approval_id,
                                             req.decision, req.note)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        if decision is None:
            raise HTTPException(status_code=404, detail="approval not found")
        return decision.__dict__

    # ---- admin endpoints ------------------------------------------------
    @app.get("/api/admin/users")
    def admin_users(user=Dep(current_user)):
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="admin only")
        p = get_platform()
        return {"users": [u.to_dict() for u in p.auth.list_users()]}

    @app.post("/api/admin/users")
    def admin_create_user(req: CreateUser, user=Dep(current_user)):
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="admin only")
        p = get_platform()
        ok = p.auth.create_user(req.username, req.password, req.role,
                                req.display_name)
        if not ok:
            raise HTTPException(status_code=409, detail="user already exists")
        return {"ok": True, "username": req.username}

    @app.post("/api/admin/users/enable")
    def admin_enable_user(req: EnableUser, user=Dep(current_user)):
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="admin only")
        p = get_platform()
        ok = p.auth.set_user_enabled(req.username, req.enabled)
        if not ok:
            raise HTTPException(status_code=404, detail="user not found")
        return {"ok": True, "username": req.username, "enabled": req.enabled}

    # -------------------------------------------------------------------
    # Legacy API (unchanged behaviour for CLI / existing tests)
    # -------------------------------------------------------------------
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

    # Reviewer web UI + Phase 2 endpoints (/reviewer, /documents, /search,
    # /learning, /learn).
    make_reviewer_routes(app, get_platform)

    # -------------------------------------------------------------------
    # Static multi-portal SPA (frontend/dist). Served LAST so every
    # /api/* and legacy route above takes precedence.
    # -------------------------------------------------------------------
    dist = _frontend_dist()
    if os.path.isdir(dist):
        app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")),
                  name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            # Serve an existing file if present, else fall back to index.html
            # (client-side routing).
            if path:
                candidate = os.path.join(dist, path)
                if os.path.isfile(candidate):
                    return FileResponse(candidate)
            return FileResponse(os.path.join(dist, "index.html"))

    return app


# Backwards-compatible module-level app (imported by tests / CLI).
# Created lazily so importing the module never builds a real platform or
# triggers auto-seeding.
_app = None


def get_app():
    global _app
    if _app is None:
        _app = create_app()
    return _app


# `app` is a lazy proxy: attribute access / uvicorn.run both work, and the
# real app is built on first use.
class _LazyApp:
    def __getattr__(self, item):
        return getattr(get_app(), item)

    def __call__(self, *args, **kwargs):
        # ASGI entrypoint: forward to the real app.
        return get_app()(*args, **kwargs)


app = _LazyApp()


def run(host: Optional[str] = None, port: Optional[int] = None):
    import uvicorn
    # Defaults are env-overridable so the same entrypoint works locally and
    # inside Docker (which needs 0.0.0.0 to be reachable from the host).
    host = host or os.environ.get("LFAE_HOST", "127.0.0.1")
    port = port or int(os.environ.get("LFAE_PORT", "8000"))
    uvicorn.run(get_app(), host=host, port=port)


if __name__ == "__main__":
    run()