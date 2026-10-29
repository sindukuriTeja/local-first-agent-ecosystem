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
    from fastapi import (Depends, FastAPI, File, Header, HTTPException,
                         UploadFile, WebSocket, WebSocketDisconnect)
    from fastapi.middleware.cors import CORSMiddleware
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


# ---- workflow (real-time collaboration) request models -------------------
class WorkflowCreate(BaseModel):
    subject: str
    message: str
    matter: Optional[str] = None


class WorkflowAssign(BaseModel):
    workflow_id: str
    employee_username: str
    note: str = ""


class WorkflowReject(BaseModel):
    workflow_id: str
    note: str = ""


class WorkflowAction(BaseModel):
    workflow_id: str
    text: str = ""
    kind: str = "note"


class WorkflowAi(BaseModel):
    workflow_id: str
    prompt: str


class WorkflowInput(BaseModel):
    workflow_id: str
    to_user: str
    to_portal: str
    question: str


class WorkflowInputAnswer(BaseModel):
    input_id: str
    answer: str


class WorkflowComplete(BaseModel):
    workflow_id: str
    final_response: str

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _project_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def _frontend_dist() -> str:
    return os.path.join(_project_root(), "frontend", "dist")


def _frontend_dir() -> str:
    root = _project_root()
    frontend_path = os.path.join(root, "frontend")
    if os.path.isdir(frontend_path):
        return frontend_path
    dist_path = os.path.join(frontend_path, "dist")
    if os.path.isdir(dist_path):
        return dist_path
    return root


def create_app(platform=None) -> FastAPI:
    """Build the FastAPI app. Pass a pre-built platform to inject a mock
    (used by tests); otherwise the real platform is created lazily."""
    app = FastAPI(
        title="Local-First Agent Ecosystem — Multi-Portal",
        description="16-agent legal/compliance platform, local Ollama inference, "
                    "self-learning engine, 7-role portal web app.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    # ---- real-time collaboration workflow ------------------------------
    def _wf(p):
        if p.workflow is None:
            raise HTTPException(status_code=503, detail="workflow engine not available")
        return p.workflow

    def _wf_call(fn, user, *args, **kwargs):
        """Run a workflow mutation, mapping engine errors to HTTP codes."""
        try:
            return fn(*args, **kwargs)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @app.get("/api/workflow")
    def workflow_list(user=Dep(current_user)):
        return {"workflows": _wf(get_platform()).list_workflows(user.username, user.portal)}

    @app.post("/api/workflow")
    def workflow_create(req: WorkflowCreate, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).create_workflow,
                      user, user.username, user.portal,
                      req.subject, req.message, req.matter, user.tenant)
        return {"workflow_id": wf["id"], "status": wf["status"]}

    @app.post("/api/workflow/approve")
    def workflow_approve(req: WorkflowAssign, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).approve_and_assign,
                      user, user.username, user.portal,
                      req.workflow_id, req.employee_username, req.note)
        return {"workflow_id": wf["id"], "status": wf["status"],
                "assigned_to": wf["assigned_to"]}

    @app.post("/api/workflow/reject")
    def workflow_reject(req: WorkflowReject, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).reject,
                      user, user.username, user.portal,
                      req.workflow_id, req.note)
        return {"workflow_id": wf["id"], "status": wf["status"]}

    @app.post("/api/workflow/start")
    def workflow_start(req: WorkflowAction, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).start_work,
                      user, user.username, user.portal, req.workflow_id)
        return {"workflow_id": wf["id"], "status": wf["status"]}

    @app.post("/api/workflow/activity")
    def workflow_activity(req: WorkflowAction, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).add_activity,
                      user, user.username, user.portal,
                      req.workflow_id, req.kind, req.text)
        return {"workflow_id": wf["id"], "status": wf["status"]}

    @app.post("/api/workflow/ai")
    def workflow_ai(req: WorkflowAi, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).run_ai,
                      user, user.username, user.portal,
                      req.workflow_id, req.prompt)
        # Return the latest AI activity for immediate UI feedback.
        ai = [a for a in wf.get("activity", []) if a.get("kind") == "ai"]
        last = ai[-1] if ai else {}
        return {"workflow_id": wf["id"], "status": wf["status"],
                "answer": last.get("data", {}).get("answer"),
                "agent_id": last.get("data", {}).get("agent_id")}

    @app.post("/api/workflow/input")
    def workflow_input(req: WorkflowInput, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).request_input,
                      user, user.username, user.portal,
                      req.workflow_id, req.to_user, req.to_portal, req.question)
        return {"workflow_id": wf["id"], "status": wf["status"]}

    @app.post("/api/workflow/input/answer")
    def workflow_input_answer(req: WorkflowInputAnswer, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).answer_input,
                      user, user.username, user.portal,
                      req.input_id, req.answer)
        return {"workflow_id": wf["id"], "status": wf["status"]}

    @app.post("/api/workflow/complete")
    def workflow_complete(req: WorkflowComplete, user=Dep(current_user)):
        wf = _wf_call(_wf(get_platform()).complete_workflow,
                      user, user.username, user.portal,
                      req.workflow_id, req.final_response)
        return {"workflow_id": wf["id"], "status": wf["status"],
                "final_response": wf["final_response"]}

    # ---- real-time event stream (WebSocket) ----------------------------
    @app.websocket("/ws/workflow")
    async def workflow_ws(ws: WebSocket, token: str = ""):
        # Authenticate via query token (browsers can't set WS headers).
        await ws.accept()
        p = get_platform()
        user = p.auth.user_for_token(token) if token else None
        if user is None:
            await ws.close(code=4401)
            return
        import asyncio
        loop = asyncio.get_running_loop()
        closed = {"flag": False}

        def _deliver(event):
            # Runs on whatever thread performed the mutation. Schedule the
            # actual WebSocket send onto the event loop thread-safely.
            if closed["flag"]:
                return
            # Only deliver events for workflows this user may see (same
            # visibility rules as the REST list/get endpoints).
            wf = event.get("workflow") or {}
            if wf and not p.workflow._visible_to(wf, user.portal, user.username):
                return
            try:
                asyncio.run_coroutine_threadsafe(ws.send_json(event), loop)
            except Exception:
                closed["flag"] = True

        sid = p.workflow.bus.subscribe(_deliver)
        try:
            await ws.send_json({"type": "connected", "user": user.username,
                                "portal": user.portal})
            # Keep the socket alive; the client drives all actions over REST.
            while True:
                try:
                    await ws.receive_text()
                except Exception:
                    break
        except WebSocketDisconnect:
            pass
        finally:
            closed["flag"] = True
            p.workflow.bus.unsubscribe(sid)

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
    # Static multi-portal web app (frontend). Served LAST so every
    # /api/* and legacy route above takes precedence.
    # -------------------------------------------------------------------
    frontend_dir = _frontend_dir()
    if os.path.isdir(frontend_dir):
        # Mount static asset directories
        for sub in ["src", "css", "js", "mock-data"]:
            subpath = os.path.join(frontend_dir, sub)
            if os.path.isdir(subpath):
                app.mount(f"/{sub}", StaticFiles(directory=subpath), name=sub)

        dist_assets = os.path.join(frontend_dir, "dist", "assets")
        if os.path.isdir(dist_assets):
            app.mount("/assets", StaticFiles(directory=dist_assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            clean = path.strip("/")
            if clean:
                candidate = os.path.join(frontend_dir, clean)
                if os.path.isfile(candidate):
                    return FileResponse(candidate)
                if os.path.isfile(candidate + ".html"):
                    return FileResponse(candidate + ".html")
            return FileResponse(os.path.join(frontend_dir, "index.html"))

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