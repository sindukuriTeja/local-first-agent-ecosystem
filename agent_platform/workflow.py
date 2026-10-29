"""Real-time collaboration workflow engine.

Turns the demo portals into a live, multi-party request pipeline:

    client/tenant  --submit-->  management  --approve+assign-->  employee
        ^                                                        |
        |                                                        | works (AI agents)
        |                                                        |
        +---- final response <---- completed <------------------+
                                                     (employee may request
                                                     input from client /
                                                     tenant / counsel /
                                                     auditor / employee;
                                                     they answer live)

Every state change is (a) persisted to a JSONL store, (b) written to the
append-only audit log, and (c) published to a real-time event bus that the
WebSocket layer fans out to connected portal clients. Nothing here calls an
external model; AI work is delegated to an injected ``ai_runner`` (the
governed orchestrator) so the platform's local-first + audit guarantees are
preserved.

This module is transport-agnostic: it does not import FastAPI. The server
wires a :class:`RealtimeBus` subscriber to each live WebSocket and calls the
engine's public methods from its REST endpoints.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Real-time event bus (in-process pub/sub)
# ---------------------------------------------------------------------------
class RealtimeBus:
    """Thread-safe in-process publish/subscribe bus.

    Subscribers are plain callables ``cb(event: dict) -> None``. The engine
    publishes from whatever thread performed the mutation; subscribers are
    responsible for delivering the event to their transport (e.g. scheduling
    a WebSocket send onto the event loop).
    """

    def __init__(self) -> None:
        self._subs: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._lock = threading.Lock()

    def subscribe(self, cb: Callable[[Dict[str, Any]], None]) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self._subs[sid] = cb
        return sid

    def unsubscribe(self, sid: str) -> None:
        with self._lock:
            self._subs.pop(sid, None)

    def publish(self, event: Dict[str, Any]) -> None:
        with self._lock:
            cbs = list(self._subs.values())
        for cb in cbs:
            try:
                cb(event)
            except Exception:  # noqa: BLE001 - never let one bad sub break others
                pass

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)


# ---------------------------------------------------------------------------
# Workflow states
# ---------------------------------------------------------------------------
ST_PENDING_APPROVAL = "pending_approval"
ST_ASSIGNED = "assigned"
ST_IN_PROGRESS = "in_progress"
ST_WAITING_INPUT = "waiting_input"
ST_COMPLETED = "completed"
ST_REJECTED = "rejected"

VALID_STATES = {
    ST_PENDING_APPROVAL, ST_ASSIGNED, ST_IN_PROGRESS,
    ST_WAITING_INPUT, ST_COMPLETED, ST_REJECTED,
}

# Portals allowed to *create* a request
REQUESTER_PORTALS = {"client", "tenant"}
# Portals allowed to *approve / assign*
APPROVER_PORTALS = {"management", "admin"}
# Portals allowed to *work* on an assigned request
WORKER_PORTALS = {"employee", "counsel"}
# Portals that may be asked for input (any stakeholder)
INPUT_TARGET_PORTALS = {"client", "tenant", "counsel", "auditor", "employee"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class WorkflowEngine:
    def __init__(
        self,
        store_path: str,
        audit=None,
        bus: Optional[RealtimeBus] = None,
        ai_runner: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        """
        Args:
            store_path: JSONL file holding all workflow records.
            audit: optional AuditLog (append-only) to mirror every action.
            bus: optional RealtimeBus to publish events to.
            ai_runner: optional callable ``ai_runner(username, prompt, state)
                -> dict`` used by :meth:`run_ai`. The server injects a wrapper
                around ``platform.handle_request`` so AI work stays governed.
        """
        self.store_path = store_path
        self.audit = audit
        self.bus = bus or RealtimeBus()
        self.ai_runner = ai_runner
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(store_path) or ".", exist_ok=True)
        if not os.path.isfile(store_path):
            with open(self.store_path, "w", encoding="utf-8") as f:
                f.write("")
        self._workflows: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ---------- persistence ----------

    def _load(self) -> None:
        with open(self.store_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    wf = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._workflows[wf["id"]] = wf

    def _save(self) -> None:
        tmp = self.store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for wf in self._workflows.values():
                f.write(json.dumps(wf, ensure_ascii=False) + "\n")
        os.replace(tmp, self.store_path)

    # ---------- event helpers ----------

    def _publish(self, event_type: str, wf: Dict[str, Any],
                 actor: str, extra: Optional[Dict[str, Any]] = None) -> None:
        event = {
            "type": event_type,
            "ts": _now(),
            "workflow_id": wf["id"],
            "status": wf["status"],
            "subject": wf.get("subject"),
            "actor": actor,
            "workflow": self._public(wf),
        }
        if extra:
            event.update(extra)
        self.bus.publish(event)

    def _audit(self, actor: str, action: str, wf_id: str,
               detail: Optional[Dict[str, Any]] = None, result: str = "ok") -> None:
        if self.audit is not None:
            self.audit.record(actor=actor, action=action,
                              detail={"workflow_id": wf_id, **(detail or {})},
                              user=actor, result=result)

    @staticmethod
    def _public(wf: Dict[str, Any]) -> Dict[str, Any]:
        """A client-safe view of a workflow (all fields are already
        non-sensitive; we just return a copy)."""
        return json.loads(json.dumps(wf))

    def _log(self, wf: Dict[str, Any], actor: str, kind: str, text: str,
             data: Optional[Dict[str, Any]] = None) -> None:
        wf.setdefault("activity", []).append({
            "actor": actor,
            "kind": kind,
            "text": text,
            "data": data or {},
            "ts": _now(),
        })
        wf["updated_at"] = _now()

    # ---------- creation ----------

    def create_workflow(self, user: str, portal: str, subject: str,
                        message: str, matter: Optional[str] = None,
                        tenant: str = "default") -> Dict[str, Any]:
        if portal not in REQUESTER_PORTALS:
            raise PermissionError(f"Portal '{portal}' cannot submit a request.")
        wf_id = "wf_" + uuid.uuid4().hex[:12]
        wf: Dict[str, Any] = {
            "id": wf_id,
            "subject": subject,
            "message": message,
            "matter": matter,
            "tenant": tenant,
            "created_by": user,
            "created_by_portal": portal,
            "status": ST_PENDING_APPROVAL,
            "assigned_to": None,
            "assigned_by": None,
            "assigned_at": None,
            "final_response": None,
            "completed_at": None,
            "inputs": [],
            "activity": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        self._log(wf, user, "created",
                  f"{portal} submitted request: {subject}")
        with self._lock:
            self._workflows[wf_id] = wf
            self._save()
        self._audit(f"user:{user}", "workflow_created", wf_id,
                    {"subject": subject, "portal": portal})
        self._publish("workflow.created", wf, user)
        return wf

    # ---------- listing / reading ----------

    def list_workflows(self, user: str, portal: str) -> List[Dict[str, Any]]:
        wfs = [self._public(w) for w in self._workflows.values()
               if self._visible_to(w, portal, user)]
        wfs.sort(key=lambda w: w.get("updated_at", ""), reverse=True)
        return wfs

    def get_workflow(self, wf_id: str, user: str, portal: str) -> Dict[str, Any]:
        wf = self._workflows.get(wf_id)
        if wf is None:
            raise KeyError(f"workflow not found: {wf_id}")
        if not self._visible_to(wf, portal, user):
            raise PermissionError("workflow not visible to this role")
        return self._public(wf)

    @staticmethod
    def _input_addressed_to(inp: Dict[str, Any], portal: str, user: str) -> bool:
        """True if an input request is addressed to this user.

        When a specific ``to_user`` is named, only that user (or an admin)
        may see/answer it; otherwise anyone in the target portal can."""
        if inp.get("to_portal") != portal:
            return False
        to_user = inp.get("to_user")
        return (not to_user) or (to_user == user)

    @classmethod
    def _visible_to(cls, wf: Dict[str, Any], portal: str, user: str) -> bool:
        if portal in ("management", "admin"):
            return True
        # The creator always sees their own request (user-level, not portal-level).
        if wf.get("created_by") == user:
            return True
        if portal == "employee":
            return wf.get("assigned_to") == user
        # counsel / auditor / other stakeholders: visible if they have an
        # input request addressed to them
        for inp in wf.get("inputs", []):
            if cls._input_addressed_to(inp, portal, user):
                return True
        return False

    # ---------- management: approve / reject ----------

    def approve_and_assign(self, user: str, portal: str, wf_id: str,
                           employee_username: str,
                           note: str = "") -> Dict[str, Any]:
        if portal not in APPROVER_PORTALS:
            raise PermissionError(f"Portal '{portal}' cannot approve.")
        wf = self._require(wf_id)
        if wf["status"] != ST_PENDING_APPROVAL:
            raise ValueError(f"workflow is {wf['status']}, not pending_approval")
        wf["status"] = ST_ASSIGNED
        wf["assigned_to"] = employee_username
        wf["assigned_by"] = user
        wf["assigned_at"] = _now()
        self._log(wf, user, "approved",
                  f"Approved and assigned to {employee_username}"
                  + (f" — {note}" if note else ""))
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_approved", wf_id,
                    {"assigned_to": employee_username})
        self._publish("workflow.assigned", wf, user,
                      {"assigned_to": employee_username})
        return wf

    def reject(self, user: str, portal: str, wf_id: str,
               note: str = "") -> Dict[str, Any]:
        if portal not in APPROVER_PORTALS:
            raise PermissionError(f"Portal '{portal}' cannot reject.")
        wf = self._require(wf_id)
        if wf["status"] != ST_PENDING_APPROVAL:
            raise ValueError(f"workflow is {wf['status']}, not pending_approval")
        wf["status"] = ST_REJECTED
        self._log(wf, user, "rejected",
                  f"Rejected" + (f" — {note}" if note else ""))
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_rejected", wf_id,
                    {"note": note})
        self._publish("workflow.rejected", wf, user, {"note": note})
        return wf

    # ---------- employee: work ----------

    def start_work(self, user: str, portal: str, wf_id: str) -> Dict[str, Any]:
        wf = self._require(wf_id)
        self._ensure_worker(wf, user, portal)
        if wf["status"] == ST_ASSIGNED:
            wf["status"] = ST_IN_PROGRESS
            self._log(wf, user, "started", "Work started")
            with self._lock:
                self._save()
            self._audit(f"user:{user}", "workflow_started", wf_id)
            self._publish("workflow.started", wf, user)
        return wf

    def add_activity(self, user: str, portal: str, wf_id: str,
                     kind: str, text: str,
                     data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        wf = self._require(wf_id)
        self._ensure_worker(wf, user, portal)
        self._log(wf, user, kind, text, data)
        with self._lock:
            self._save()
        self._audit(f"user:{user}", f"workflow_{kind}", wf_id, {"text": text})
        self._publish("workflow.activity", wf, user, {"kind": kind, "text": text})
        return wf

    def run_ai(self, user: str, portal: str, wf_id: str,
               prompt: str) -> Dict[str, Any]:
        """Run a governed AI task in the context of this workflow and record
        the answer as activity + a real-time event."""
        wf = self._require(wf_id)
        self._ensure_worker(wf, user, portal)
        if self.ai_runner is None:
            raise RuntimeError("AI runner is not configured on this platform")
        if wf["status"] == ST_ASSIGNED:
            wf["status"] = ST_IN_PROGRESS
        state = {
            "workflow_id": wf_id,
            "workflow_subject": wf.get("subject"),
            "workflow_message": wf.get("message"),
            "matter": wf.get("matter"),
        }
        # Publish a "running" event first so the UI shows live progress.
        self._publish("workflow.ai_running", wf, user, {"prompt": prompt})
        try:
            result = self.ai_runner(user, prompt, state)
        except Exception as e:  # noqa: BLE001
            result = {"status": "error", "answer": "", "error": str(e)}
        answer = result.get("answer") or result.get("error") or "(no answer)"
        self._log(wf, user, "ai", f"AI: {prompt}",
                  {"answer": answer, "agent_id": result.get("agent_id"),
                   "status": result.get("status"),
                   "sources": result.get("sources") or []})
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_ai", wf_id,
                    {"prompt": prompt, "agent_id": result.get("agent_id")})
        self._publish("workflow.ai_result", wf, user,
                      {"prompt": prompt, "answer": answer,
                       "agent_id": result.get("agent_id"),
                       "status": result.get("status")})
        return wf

    # ---------- input requests (employee <-> stakeholder) ----------

    def request_input(self, user: str, portal: str, wf_id: str,
                      to_user: str, to_portal: str,
                      question: str) -> Dict[str, Any]:
        wf = self._require(wf_id)
        self._ensure_worker(wf, user, portal)
        if to_portal not in INPUT_TARGET_PORTALS:
            raise PermissionError(f"Cannot request input from portal '{to_portal}'")
        inp_id = "inp_" + uuid.uuid4().hex[:10]
        inp = {
            "id": inp_id,
            "workflow_id": wf_id,
            "from_user": user,
            "to_user": to_user,
            "to_portal": to_portal,
            "question": question,
            "status": "pending",
            "answer": None,
            "created_at": _now(),
            "answered_at": None,
        }
        wf.setdefault("inputs", []).append(inp)
        if wf["status"] in (ST_ASSIGNED, ST_IN_PROGRESS):
            wf["status"] = ST_WAITING_INPUT
        self._log(wf, user, "input_requested",
                  f"Requested input from {to_user} ({to_portal}): {question}")
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_input_requested", wf_id,
                    {"to_user": to_user, "to_portal": to_portal})
        self._publish("workflow.input_requested", wf, user,
                      {"input_id": inp_id, "to_user": to_user,
                       "to_portal": to_portal, "question": question})
        return wf

    def answer_input(self, user: str, portal: str, input_id: str,
                     answer: str) -> Dict[str, Any]:
        wf = None
        for w in self._workflows.values():
            for inp in w.get("inputs", []):
                if inp["id"] == input_id:
                    wf = w
                    break
            if wf is not None:
                break
        if wf is None:
            raise KeyError(f"input not found: {input_id}")
        inp = next(i for i in wf["inputs"] if i["id"] == input_id)
        # Only the addressed stakeholder (or an admin) may answer.
        if not (self._input_addressed_to(inp, portal, user) or portal == "admin"):
            raise PermissionError("You are not the stakeholder this input is addressed to")
        if inp["status"] != "pending":
            raise ValueError("input already answered")
        inp["status"] = "answered"
        inp["answer"] = answer
        inp["answered_at"] = _now()
        # If no other pending inputs remain, move back to in_progress.
        if all(i["status"] != "pending" for i in wf.get("inputs", [])):
            if wf["status"] == ST_WAITING_INPUT:
                wf["status"] = ST_IN_PROGRESS
        self._log(wf, user, "input_answered",
                  f"{user} answered: {answer}", {"input_id": input_id})
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_input_answered", wf["id"],
                    {"input_id": input_id})
        self._publish("workflow.input_answered", wf, user,
                      {"input_id": input_id, "answer": answer})
        return wf

    # ---------- completion ----------

    def complete_workflow(self, user: str, portal: str, wf_id: str,
                          final_response: str) -> Dict[str, Any]:
        wf = self._require(wf_id)
        self._ensure_worker(wf, user, portal)
        wf["status"] = ST_COMPLETED
        wf["final_response"] = final_response
        wf["completed_at"] = _now()
        self._log(wf, user, "completed",
                  "Submitted final response to the requester")
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_completed", wf_id)
        self._publish("workflow.completed", wf, user,
                      {"final_response": final_response})
        return wf

    # ---------- guards ----------

    def _require(self, wf_id: str) -> Dict[str, Any]:
        wf = self._workflows.get(wf_id)
        if wf is None:
            raise KeyError(f"workflow not found: {wf_id}")
        return wf

    @staticmethod
    def _ensure_worker(wf: Dict[str, Any], user: str, portal: str) -> None:
        if portal not in WORKER_PORTALS:
            raise PermissionError(f"Portal '{portal}' cannot work on a request")
        if wf.get("assigned_to") and wf["assigned_to"] != user \
                and portal != "admin":
            raise PermissionError(
                f"This request is assigned to {wf['assigned_to']}, not {user}")

    # ---------- introspection (for admin / tests) ----------

    def stats(self) -> Dict[str, Any]:
        by: Dict[str, int] = {}
        for w in self._workflows.values():
            by[w["status"]] = by.get(w["status"], 0) + 1
        return {"total": len(self._workflows), "by_status": by,
                "subscribers": self.bus.subscriber_count}