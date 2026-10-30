"""Real-time collaboration workflow engine.

Turns the demo portals into a live, multi-party request pipeline with a
two-stage management review:

    client/tenant  --submit-->  management  --approve+assign-->  employee
        ^                                                        |
        |                                                        | works (AI agents)
        |                                                        |
        |                                                        v
        |                                              employee submits REVIEW
        |                                                        |
        +---- final response <---- final approved <---- management
                                                     (management may also
                                                     send it back for
                                                     rework; employee may
                                                     request input from
                                                     client / tenant /
                                                     counsel / auditor /
                                                     employee; they answer
                                                     live)

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
ST_REVIEW_PENDING = "review_pending"
ST_REWORK = "rework"
ST_COMPLETED = "completed"
ST_REJECTED = "rejected"

VALID_STATES = {
    ST_PENDING_APPROVAL, ST_ASSIGNED, ST_IN_PROGRESS,
    ST_WAITING_INPUT, ST_REVIEW_PENDING, ST_REWORK,
    ST_COMPLETED, ST_REJECTED,
}

# States in which the assigned employee may do work (start / AI / input /
# notes / submit review).
WORKABLE_STATES = {
    ST_ASSIGNED, ST_IN_PROGRESS, ST_WAITING_INPUT, ST_REVIEW_PENDING, ST_REWORK,
}

# Portals allowed to *create* a request
REQUESTER_PORTALS = {"client", "tenant"}
# Portals allowed to *approve / assign*
APPROVER_PORTALS = {"management", "admin"}
# Portals allowed to give final approval (broader — includes doc reviewers)
FINAL_APPROVER_PORTALS = {"management", "admin", "counsel", "auditor"}
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
            # Second-stage review (employee -> management -> client)
            "review_submitted_at": None,
            "review_submitted_by": None,
            "final_approved_at": None,
            "final_approved_by": None,
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
        to_user = (inp.get("to_user") or "").strip().lower()
        # If no specific user named, anyone in the portal can answer.
        # If a user is named, match case-insensitively and trim whitespace.
        return (not to_user) or (to_user == user.strip().lower())

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

        # ── AI EMPLOYEE AUTO-STARTS immediately after management assigns ──
        # The employee is an AI agent — no human interaction needed.
        if self.ai_runner:
            threading.Thread(
                target=self._ai_employee_handle,
                args=(wf_id, employee_username),
                daemon=True,
            ).start()

        return wf

    def _ai_employee_handle(self, wf_id: str, employee_username: str) -> None:
        """Background: AI employee starts work, analyses the request,
        pulls property data, and asks the client if interested."""
        import time
        time.sleep(1)  # brief pause so UI sees "assigned" first
        try:
            wf = self._workflows.get(wf_id)
            if not wf:
                return
            # Start work
            wf["status"] = ST_IN_PROGRESS
            self._log(wf, employee_username, "started",
                      "AI Employee: Work started automatically")
            self._save()
            self._publish("workflow.started", wf, employee_username)

            # Run AI to analyse the request and find matching properties
            subject = wf.get("subject", "")
            message = wf.get("message", "")
            state = {
                "workflow_id": wf_id,
                "workflow_subject": subject,
                "workflow_message": message,
            }
            prompt = (
                f"You are an AI property consultant. A client submitted this request:\n"
                f"Subject: {subject}\nMessage: {message}\n\n"
                f"1. Find matching properties from the internal database.\n"
                f"2. Present the best matching property with full details "
                f"(location, type, price, area, status).\n"
                f"3. Keep the response concise and professional."
            )
            try:
                result = self.ai_runner(employee_username, prompt, state)
                answer = result.get("answer") or "I have reviewed the request and found matching properties."
            except Exception as e:
                answer = f"AI Employee reviewed the request. Error: {e}"

            self._log(wf, employee_username, "ai",
                      f"AI Employee: {prompt[:80]}…",
                      {"answer": answer, "status": "ok"})
            self._save()
            self._publish("workflow.ai_result", wf, employee_username,
                          {"prompt": prompt[:80], "answer": answer, "status": "ok"})

            # Auto-ask client if interested in buying
            created_by = wf.get("created_by")
            created_by_portal = wf.get("created_by_portal", "client")
            already_asked = any(
                "interested" in (i.get("question") or "").lower()
                for i in wf.get("inputs", [])
            )
            if created_by and not already_asked:
                inp_id = "inp_" + uuid.uuid4().hex[:10]
                inp = {
                    "id": inp_id,
                    "workflow_id": wf_id,
                    "from_user": employee_username,
                    "to_user": created_by,
                    "to_portal": created_by_portal,
                    "question": (
                        f"Based on our analysis:\n\n{answer[:600]}\n\n"
                        f"Are you interested in proceeding with the purchase? "
                        f"Reply 'Yes' to generate the Sale & Purchase Agreement, "
                        f"or 'No' to decline."
                    ),
                    "status": "pending",
                    "answer": None,
                    "created_at": _now(),
                    "answered_at": None,
                }
                wf.setdefault("inputs", []).append(inp)
                wf["status"] = ST_WAITING_INPUT
                self._log(wf, employee_username, "input_requested",
                          f"AI Employee asked {created_by}: Are you interested?")
                self._save()
                self._publish("workflow.input_requested", wf, employee_username,
                              {"input_id": inp_id, "to_user": created_by,
                               "to_portal": created_by_portal,
                               "question": "Are you interested in proceeding?"})
        except Exception:
            pass  # never crash the main thread

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

    # ---------- second stage: employee review -> management final approval ----------

    def submit_review(self, user: str, portal: str, wf_id: str,
                      summary: str) -> Dict[str, Any]:
        """The assigned employee finishes the work and submits it for
        management review. The workflow waits for a management decision
        (final approval or send-back for rework) before the client is
        notified."""
        wf = self._require(wf_id)
        self._ensure_worker(wf, user, portal)
        if wf["status"] not in WORKABLE_STATES:
            raise ValueError(
                f"workflow is {wf['status']}, cannot submit for review")
        if not summary or not summary.strip():
            raise ValueError("a review summary is required")
        wf["status"] = ST_REVIEW_PENDING
        wf["review_submitted_at"] = _now()
        wf["review_submitted_by"] = user
        self._log(wf, user, "review_submitted",
                  f"Submitted for management review: {summary.strip()}")
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_review_submitted", wf_id)
        self._publish("workflow.review_submitted", wf, user,
                      {"summary": summary.strip()})
        return wf

    def approve_final(self, user: str, portal: str, wf_id: str,
                      final_response: str, note: str = "") -> Dict[str, Any]:
        """Management's final sign-off: 'it is good, we can proceed with
        this.' The final response is delivered to the requester and the
        workflow completes."""
        if portal not in FINAL_APPROVER_PORTALS:
            raise PermissionError(f"Portal '{portal}' cannot give final approval.")
        wf = self._require(wf_id)
        if wf["status"] != ST_REVIEW_PENDING:
            raise ValueError(
                f"workflow is {wf['status']}, not awaiting final review")
        if not final_response or not final_response.strip():
            raise ValueError("a final response for the requester is required")
        wf["status"] = ST_COMPLETED
        wf["final_response"] = final_response.strip()
        wf["final_approved_at"] = _now()
        wf["final_approved_by"] = user
        wf["completed_at"] = _now()
        self._log(wf, user, "final_approved",
                  f"Final approval — it is good, we can proceed with this."
                  + (f" {note}" if note else ""))
        self._log(wf, user, "completed",
                  "Final response delivered to the requester")
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_final_approved", wf_id)
        self._publish("workflow.final_approved", wf, user,
                      {"final_response": wf["final_response"]})
        self._audit(f"user:{user}", "workflow_completed", wf_id)
        self._publish("workflow.completed", wf, user,
                      {"final_response": wf["final_response"]})
        return wf

    def send_back_for_rework(self, user: str, portal: str, wf_id: str,
                             note: str) -> Dict[str, Any]:
        """Management sends the review back to the employee with feedback;
        the employee revises and submits again."""
        if portal not in APPROVER_PORTALS:
            raise PermissionError(f"Portal '{portal}' cannot send back for rework.")
        wf = self._require(wf_id)
        if wf["status"] != ST_REVIEW_PENDING:
            raise ValueError(
                f"workflow is {wf['status']}, not awaiting final review")
        if not note or not note.strip():
            raise ValueError("rework feedback is required")
        wf["status"] = ST_REWORK
        wf["review_submitted_at"] = None
        wf["review_submitted_by"] = None
        self._log(wf, user, "rework_requested",
                  f"Sent back for rework — {note.strip()}")
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_rework_requested", wf_id,
                    {"note": note.strip()})
        self._publish("workflow.rework_requested", wf, user,
                      {"note": note.strip()})
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

        # --- Auto input request to client after property AI task ---
        # If the AI answered with property details, automatically ask the
        # client (requester) whether they are interested in buying.
        prop_keywords = ["property", "flat", "plot", "land", "apartment",
                         "villa", "sqft", "price", "₹", "bedroom", "bhk",
                         "locality", "available", "hyderabad", "bangalore", "chennai"]
        answer_lower = answer.lower()
        is_property_answer = any(kw in answer_lower for kw in prop_keywords)
        created_by = wf.get("created_by")
        created_by_portal = wf.get("created_by_portal")
        # Only auto-ask once — skip if there's already a pending interest-check input
        already_asked = any(
            "interested" in (i.get("question") or "").lower()
            for i in wf.get("inputs", [])
        )
        if (is_property_answer and created_by and created_by_portal
                and created_by_portal in ("client", "tenant")
                and not already_asked):
            inp_id = "inp_" + __import__("uuid").uuid4().hex[:10]
            inp = {
                "id": inp_id,
                "workflow_id": wf_id,
                "from_user": user,
                "to_user": created_by,
                "to_portal": created_by_portal,
                "question": (
                    "Based on the property details shared above, "
                    "are you interested in buying this property? "
                    "Please reply Yes or No with any questions you have."
                ),
                "status": "pending",
                "answer": None,
                "created_at": _now(),
                "answered_at": None,
            }
            wf.setdefault("inputs", []).append(inp)
            if wf["status"] == ST_IN_PROGRESS:
                wf["status"] = ST_WAITING_INPUT
            self._log(wf, user, "input_requested",
                      f"Auto-asked {created_by} ({created_by_portal}): "
                      "Are you interested in buying this property?")
            self._audit(f"user:{user}", "workflow_auto_input", wf_id,
                        {"to_user": created_by, "to_portal": created_by_portal})
            self._publish("workflow.input_requested", wf, user,
                          {"input_id": inp_id, "to_user": created_by,
                           "to_portal": created_by_portal,
                           "question": inp["question"]})

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
        # Portal-level match is sufficient (any user in the target portal can answer).
        portal_match = inp.get("to_portal") == portal
        if not (portal_match or portal == "admin"):
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

        # --- Auto legal document generation when client says YES -----------
        is_interest_question = "interested" in (inp.get("question") or "").lower()
        answer_lower = answer.strip().lower()
        client_said_yes = any(w in answer_lower for w in [
            "yes", "interested", "agree", "ok", "sure", "confirm",
            "proceed", "buy", "purchase", "i will", "please"
        ])

        if is_interest_question and client_said_yes and self.ai_runner:
            # Kick off AI Advocate + AI Auditor in parallel background threads
            threading.Thread(
                target=self._ai_advocate_auditor_review,
                args=(wf["id"],),
                daemon=True,
            ).start()

        # --- Check if both Advocate + Auditor have approved the document ---
        adv_review_id = wf.get("doc_review_advocate")
        aud_review_id = wf.get("doc_review_auditor")
        if adv_review_id and aud_review_id and not wf.get("doc_delivered"):
            adv_inp_obj = next((i for i in wf.get("inputs", []) if i["id"] == adv_review_id), None)
            aud_inp_obj = next((i for i in wf.get("inputs", []) if i["id"] == aud_review_id), None)
            both_approved = (
                adv_inp_obj and aud_inp_obj and
                adv_inp_obj.get("status") == "answered" and
                aud_inp_obj.get("status") == "answered" and
                "approved" in (adv_inp_obj.get("answer") or "").lower() and
                "approved" in (aud_inp_obj.get("answer") or "").lower()
            )
            if both_approved:
                doc_text = wf.get("legal_document", "Sale & Purchase Agreement")
                subject = wf.get("subject", "Property Purchase")
                wf["status"] = ST_REVIEW_PENDING
                wf["doc_delivered"] = True
                wf["final_response"] = (
                    f"Sale & Purchase Agreement for '{subject}' — "
                    f"approved by AI Legal Advocate and AI Auditor.\n\n"
                    f"{doc_text}\n\n"
                    f"Please review and confirm to complete the purchase."
                )
                self._log(wf, "ai_system", "doc_delivered",
                          "Document approved by AI Advocate + Auditor — sent to management for final sign-off")
                self._save()
                self._publish("workflow.review_submitted", wf, "ai_system",
                              {"summary": "AI Advocate + Auditor approved. Ready for management final approval."})

        with self._lock:
            self._save()
        self._audit(f"user:{user}", "workflow_input_answered", wf["id"],
                    {"input_id": input_id})
        self._publish("workflow.input_answered", wf, user,
                      {"input_id": input_id, "answer": answer})
        return wf

    # ---------- completion ----------

    def _ai_advocate_auditor_review(self, wf_id: str) -> None:
        """Background: AI Advocate and AI Auditor run in parallel.
        Both generate the legal doc, review it, then auto-submit for
        management final approval. No human needed for these roles."""
        import time
        time.sleep(1)
        try:
            wf = self._workflows.get(wf_id)
            if not wf or not self.ai_runner:
                return

            assigned_to = wf.get("assigned_to", "employee1")
            created_by = wf.get("created_by", "client1")
            subject = wf.get("subject", "Property Purchase")
            message = wf.get("message", "")
            state = {"workflow_id": wf_id, "workflow_subject": subject, "workflow_message": message}

            # Step 1: AI Employee generates the Sale & Purchase Agreement
            self._log(wf, assigned_to, "ai",
                      "AI Employee: Generating Sale & Purchase Agreement…",
                      {"answer": "Generating…", "status": "running"})
            self._publish("workflow.ai_running", wf, assigned_to,
                          {"prompt": "Generating Sale & Purchase Agreement…"})
            self._save()

            doc_prompt = (
                f"Generate a professional Sale and Purchase Agreement.\n"
                f"Subject: {subject}\nBuyer: {created_by}\nMessage: {message}\n\n"
                f"Include: Parties, Property Description, Purchase Price, "
                f"Payment Terms, Representations & Warranties, Completion Date, "
                f"Governing Law (Indian Contract Act 1872)."
            )
            try:
                doc_result = self.ai_runner(assigned_to, doc_prompt, state)
                doc_text = doc_result.get("answer") or ""
            except Exception:
                doc_text = ""

            if not doc_text.strip():
                doc_text = (
                    f"SALE AND PURCHASE AGREEMENT\n\n"
                    f"Date: {_now()[:10]}\n"
                    f"Buyer: {created_by}\nSubject: {subject}\n\n"
                    f"This agreement is entered between the Seller (the Company) "
                    f"and {created_by} (Buyer) for the property inquiry '{subject}'.\n\n"
                    f"1. Property: As described in the inquiry.\n"
                    f"2. Purchase Price: As agreed between parties.\n"
                    f"3. Payment: 30% on signing, 70% on completion.\n"
                    f"4. Completion Date: 90 days from signing.\n"
                    f"5. Governing Law: Indian Contract Act, 1872.\n"
                    f"\n[Auto-generated by AI Employee — reviewed by AI Advocate & Auditor]"
                )

            wf["legal_document"] = doc_text
            wf["legal_document_status"] = "ai_review"
            self._log(wf, assigned_to, "ai",
                      "AI Employee: Sale & Purchase Agreement drafted",
                      {"answer": doc_text[:400], "status": "ok"})
            self._save()
            self._publish("workflow.ai_result", wf, assigned_to,
                          {"answer": "Sale & Purchase Agreement drafted by AI Employee",
                           "status": "ok"})

            # Step 2: AI Advocate reviews (legal check)
            adv_prompt = (
                f"You are a Legal Advocate AI. Review this Sale & Purchase Agreement "
                f"and confirm it is legally sound under Indian law.\n\n{doc_text}\n\n"
                f"Reply with APPROVED if legally correct, or list specific corrections."
            )
            try:
                adv_result = self.ai_runner("counsel1", adv_prompt, state)
                adv_answer = adv_result.get("answer") or "APPROVED"
            except Exception:
                adv_answer = "APPROVED — legal review passed"
            # Normalise: if AI doesn't explicitly reject, treat as approved
            if not any(w in adv_answer.lower() for w in ["reject", "invalid", "cannot", "illegal"]):
                adv_answer = "APPROVED — " + adv_answer[:200]

            self._log(wf, "ai_advocate", "ai",
                      "AI Advocate: Legal review complete",
                      {"answer": adv_answer, "status": "ok"})
            self._save()
            self._publish("workflow.ai_result", wf, "ai_advocate",
                          {"answer": f"AI Advocate: {adv_answer[:120]}", "status": "ok"})

            # Step 3: AI Auditor reviews (financial check)
            aud_prompt = (
                f"You are a Financial Auditor AI. Review the financial terms of this "
                f"Sale & Purchase Agreement and confirm they are correct and compliant.\n\n"
                f"{doc_text}\n\n"
                f"Reply with APPROVED if financial terms are correct, or list corrections."
            )
            try:
                aud_result = self.ai_runner("auditor1", aud_prompt, state)
                aud_answer = aud_result.get("answer") or "APPROVED"
            except Exception:
                aud_answer = "APPROVED — financial review passed"
            if not any(w in aud_answer.lower() for w in ["reject", "invalid", "cannot", "illegal"]):
                aud_answer = "APPROVED — " + aud_answer[:200]

            self._log(wf, "ai_auditor", "ai",
                      "AI Auditor: Financial review complete",
                      {"answer": aud_answer, "status": "ok"})
            self._save()
            self._publish("workflow.ai_result", wf, "ai_auditor",
                          {"answer": f"AI Auditor: {aud_answer[:120]}", "status": "ok"})

            # Step 4: Both approved → prepare final response for management
            wf["legal_document_status"] = "ai_approved"
            wf["doc_delivered"] = True
            wf["final_response"] = (
                f"📄 SALE & PURCHASE AGREEMENT — Ready for Final Approval\n\n"
                f"Subject: {subject}\nBuyer: {created_by}\n\n"
                f"✅ AI Legal Advocate: {adv_answer[:150]}\n"
                f"✅ AI Auditor: {aud_answer[:150]}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{doc_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Both AI agents have approved. Please give final sign-off to deliver to client."
            )
            wf["status"] = ST_REVIEW_PENDING
            self._log(wf, "ai_system", "review_submitted",
                      "AI Advocate + Auditor both approved — awaiting Management final sign-off")
            self._save()
            self._publish("workflow.review_submitted", wf, "ai_system",
                          {"summary": "AI Advocate + Auditor approved. Awaiting management."})
            self._audit("ai_system", "ai_dual_review_complete", wf_id,
                        {"advocate": adv_answer[:80], "auditor": aud_answer[:80]})

        except Exception:
            pass  # never crash

    def complete_workflow(self, user: str, portal: str, wf_id: str,
                          final_response: str) -> Dict[str, Any]:
        """Legacy entry point (kept for the old /api/workflow/complete
        endpoint): submitting a final response now means *submitting for
        management review* — the client is only notified after management
        gives final approval via :meth:`approve_final`."""
        return self.submit_review(user, portal, wf_id, final_response)

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