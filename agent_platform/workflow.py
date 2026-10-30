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

# Purchase workflow states (employee offers a property -> client decides ->
# advocate + auditor connected -> documents prepared -> client signs -> sold)
ST_PURCHASE_OFFERED = "purchase_offered"
ST_PURCHASE_DOCUMENTATION = "purchase_documentation"
ST_PURCHASE_SIGNING = "purchase_signing"
ST_PURCHASE_COMPLETED = "purchase_completed"
ST_PURCHASE_DECLINED = "purchase_declined"

VALID_STATES = {
    ST_PENDING_APPROVAL, ST_ASSIGNED, ST_IN_PROGRESS,
    ST_WAITING_INPUT, ST_REVIEW_PENDING, ST_REWORK,
    ST_COMPLETED, ST_REJECTED,
    ST_PURCHASE_OFFERED, ST_PURCHASE_DOCUMENTATION, ST_PURCHASE_SIGNING,
    ST_PURCHASE_COMPLETED, ST_PURCHASE_DECLINED,
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
        stakeholder_resolver: Optional[Callable[[str], str]] = None,
        properties=None,
        knowledge=None,
    ) -> None:
        """
        Args:
            store_path: JSONL file holding all workflow records.
            audit: optional AuditLog (append-only) to mirror every action.
            bus: optional RealtimeBus to publish events to.
            ai_runner: optional callable ``ai_runner(username, prompt, state)
                -> dict`` used by :meth:`run_ai`. The server injects a wrapper
                around ``platform.handle_request`` so AI work stays governed.
            stakeholder_resolver: optional callable ``portal -> username``
                used by the purchase flow to auto-connect the advocate and
                auditor. Falls back to the demo defaults when absent.
            properties: optional PropertyStore; a completed purchase marks
                the property ``sold``.
            knowledge: optional KnowledgeStore; the sale document package is
                stored here as ``sale_document`` records.
        """
        self.store_path = store_path
        self.audit = audit
        self.bus = bus or RealtimeBus()
        self.ai_runner = ai_runner
        self.stakeholder_resolver = stakeholder_resolver
        self.properties = properties
        self.knowledge = knowledge
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

    # ---------- purchase workflow (property sale) ----------
    #
    # employee offers a property -> client accepts/declines -> advocate +
    # auditor are connected (auto input requests) -> document package is
    # prepared -> client signs -> sale completed (property marked sold).
    #
    # Reuses the same JSONL store, audit log, real-time bus, and visibility
    # rules as the request workflow. ``stakeholder_resolver`` (injected by
    # the server) maps a portal to a concrete username so the advocate and
    # auditor are auto-connected; it falls back to the demo defaults.

    def _resolve_stakeholder(self, portal: str) -> str:
        if self.stakeholder_resolver is not None:
            try:
                name = self.stakeholder_resolver(portal)
                if name:
                    return name
            except Exception:  # noqa: BLE001
                pass
        return {"counsel": "counsel1", "auditor": "auditor1"}.get(portal, portal + "1")

    @staticmethod
    def _purchase_docs(property_id: str, subject: str, buyer: str,
                       price_inr: Optional[int], price_display: str,
                       property_code: str, locality: str, city: str) -> List[Dict[str, str]]:
        """Build the sale document package for a property purchase.

        Every document is stored as a ``sale_document`` knowledge record
        (sensitivity confidential) so it is retrievable through the
        governed RAG path by the parties involved.
        """
        price_line = price_display or "as per the agreed terms"
        return [
            {
                "title": f"Sale Agreement — {property_code}",
                "content": (
                    f"SALE AGREEMENT for property {property_code} "
                    f"({locality}, {city}).\n\n"
                    f"Parties: the Firm (seller) and {buyer} (buyer).\n"
                    f"Agreed price: {price_line}.\n\n"
                    f"1. The seller agrees to transfer and the buyer agrees "
                    f"to purchase the property described above, free of all "
                    f"encumbrances.\n"
                    f"2. Payment shall be made as per the Payment Schedule "
                    f"document accompanying this agreement.\n"
                    f"3. Transfer of title is subject to the Title "
                    f"Verification and Compliance Clearance documents.\n"
                    f"4. Stamp duty and registration charges are payable as "
                    f"per the Stamp Duty & Registration document.\n\n"
                    f"Execution: signed by both parties in the presence of "
                    f"two witnesses."
                ),
            },
            {
                "title": f"Title Verification — {property_code}",
                "content": (
                    f"TITLE VERIFICATION for property {property_code} "
                    f"({locality}, {city}).\n\n"
                    f"Prepared by the Advocate (external counsel).\n\n"
                    f"- Chain of title reviewed; seller's ownership verified.\n"
                    f"- No active mortgages or liens on record.\n"
                    f"- No pending litigation affecting title.\n"
                    f"- Encumbrance certificate clear for the last 30 years.\n\n"
                    f"Conclusion: title is clear and marketable. "
                    f"Registration may proceed."
                ),
            },
            {
                "title": f"Compliance & RERA Clearance — {property_code}",
                "content": (
                    f"COMPLIANCE & RERA CLEARANCE for property {property_code} "
                    f"({locality}, {city}).\n\n"
                    f"Prepared by the Auditor.\n\n"
                    f"- RERA registration status: verified and active.\n"
                    f"- All statutory approvals in place (DTCP / building "
                    f"plan / occupancy).\n"
                    f"- No outstanding compliance notices.\n\n"
                    f"Conclusion: property is compliant for sale and "
                    f"registration."
                ),
            },
            {
                "title": f"Stamp Duty & Registration — {property_code}",
                "content": (
                    f"STAMP DUTY & REGISTRATION for property {property_code} "
                    f"({locality}, {city}).\n\n"
                    f"Agreed price: {price_line}.\n\n"
                    f"- Applicable stamp duty computed on the agreed price "
                    f"per the state schedule.\n"
                    f"- Registration to be filed with the Sub-Registrar's "
                    f"office within the statutory period.\n"
                    f"- Registration fee and court fees payable at filing.\n\n"
                    f"Next step: submit the signed Sale Agreement for "
                    f"registration."
                ),
            },
            {
                "title": f"Payment Schedule — {property_code}",
                "content": (
                    f"PAYMENT SCHEDULE for property {property_code} "
                    f"({locality}, {city}).\n\n"
                    f"Agreed price: {price_line}.\n\n"
                    f"1. Token / advance: payable on signing.\n"
                    f"2. Balance: payable on registration, against receipt "
                    f"and transfer of title documents.\n\n"
                    f"All payments to be made through traceable bank "
                    f"transfer to the firm's account."
                ),
            },
        ]

    def propose_purchase(self, user: str, portal: str, property_id: str,
                         buyer: str, note: str = "") -> Dict[str, Any]:
        """Employee offers a property to a client: 'will you buy?'

        The property details + price are attached, the buyer is named, and
        the workflow enters ``purchase_offered`` awaiting the client's
        decision.
        """
        if portal not in WORKER_PORTALS:
            raise PermissionError(f"Portal '{portal}' cannot propose a purchase.")
        if self.properties is None:
            raise RuntimeError("property store is not configured")
        prop = self.properties.get_property(property_id)
        if prop is None:
            raise KeyError(f"property not found: {property_id}")
        if prop.get("status") == "sold":
            raise ValueError(f"property {property_id} is already sold")
        if not buyer:
            raise ValueError("a buyer (client) is required")

        wf_id = "wf_" + uuid.uuid4().hex[:12]
        subject = f"Purchase offer: {prop.get('property_code', property_id)}"
        message = (
            f"Property {prop.get('property_code', property_id)} — "
            f"{prop.get('title', '')}, {prop.get('locality', '')}, "
            f"{prop.get('city', '')}. Asking price: "
            f"{prop.get('price_display', '—')}. "
            f"Will you buy?"
        )
        wf: Dict[str, Any] = {
            "id": wf_id,
            "subject": subject,
            "message": message,
            "matter": None,
            "tenant": "default",
            "created_by": user,
            "created_by_portal": portal,
            "status": ST_PURCHASE_OFFERED,
            "assigned_to": user,
            "assigned_by": user,
            "assigned_at": _now(),
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
            "purchase": {
                "property_id": property_id,
                "property_code": prop.get("property_code"),
                "title": prop.get("title"),
                "locality": prop.get("locality"),
                "city": prop.get("city"),
                "price_inr": prop.get("price_inr"),
                "price_display": prop.get("price_display"),
                "buyer": buyer,
                "offer_note": note,
                "documents": [],
                "signed": False,
                "signed_at": None,
            },
        }
        self._log(wf, user, "purchase_offered",
                  f"Offered {prop.get('property_code', property_id)} to "
                  f"{buyer} at {prop.get('price_display', '—')}. Will you buy?")
        with self._lock:
            self._workflows[wf_id] = wf
            self._save()
        self._audit(f"user:{user}", "purchase_offered", wf_id,
                    {"property_id": property_id, "buyer": buyer})
        self._publish("workflow.purchase_offered", wf, user,
                      {"property_id": property_id, "buyer": buyer})
        return wf

    def accept_purchase(self, user: str, portal: str, wf_id: str,
                        note: str = "") -> Dict[str, Any]:
        """The client says 'yes, I will buy'. The advocate and auditor are
        connected (auto input requests) and the sale document package is
        prepared. The workflow moves to ``purchase_documentation``."""
        wf = self._require(wf_id)
        purchase = wf.get("purchase")
        if not purchase:
            raise ValueError("workflow is not a purchase")
        if wf["status"] != ST_PURCHASE_OFFERED:
            raise ValueError(
                f"purchase is {wf['status']}, not offered")
        if portal != "client" or purchase.get("buyer") != user:
            raise PermissionError(
                "Only the buyer (client) can accept a purchase offer")

        # Connect the advocate and the auditor.
        advocate = self._resolve_stakeholder("counsel")
        auditor = self._resolve_stakeholder("auditor")
        prop_code = purchase.get("property_code", purchase.get("property_id"))
        self._add_purchase_input(wf, "counsel", advocate,
            f"Title verification & sale agreement for {prop_code}. Please "
            f"confirm the title is clear and prepare the Sale Agreement.")
        self._add_purchase_input(wf, "auditor", auditor,
            f"Compliance & RERA clearance for {prop_code}. Please confirm "
            f"the property is compliant for sale and registration.")

        # Prepare the document package (stored as sale_document records).
        docs = self._purchase_docs(
            purchase.get("property_id"), wf.get("subject") or "",
            user, purchase.get("price_inr"),
            purchase.get("price_display"), prop_code,
            purchase.get("locality", ""), purchase.get("city", ""))
        doc_ids = []
        if self.knowledge is not None:
            for d in docs:
                doc_id, _ = self.knowledge.upsert_document(
                    title=d["title"], content=d["content"],
                    source=f"purchase:{wf_id}:{d['title']}",
                    doc_type="sale_document", sensitivity="confidential",
                    tenant="default",
                    metadata={"workflow_id": wf_id,
                              "property_id": purchase.get("property_id"),
                              "buyer": user})
                doc_ids.append(doc_id)
        purchase["documents"] = [
            {"title": d["title"], "doc_id": doc_ids[i]}
            for i, d in enumerate(docs)
        ]

        wf["status"] = ST_PURCHASE_DOCUMENTATION
        self._log(wf, user, "purchase_accepted",
                  f"{user} accepted the purchase. Advocate ({advocate}) and "
                  f"auditor ({auditor}) connected; {len(docs)} sale documents "
                  f"prepared.")
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "purchase_accepted", wf_id,
                    {"advocate": advocate, "auditor": auditor,
                     "documents": len(docs)})
        self._publish("workflow.purchase_accepted", wf, user,
                      {"advocate": advocate, "auditor": auditor,
                       "documents": purchase["documents"]})
        return wf

    def decline_purchase(self, user: str, portal: str, wf_id: str,
                         note: str = "") -> Dict[str, Any]:
        """The client says 'no'. The workflow closes as declined."""
        wf = self._require(wf_id)
        purchase = wf.get("purchase")
        if not purchase:
            raise ValueError("workflow is not a purchase")
        if wf["status"] != ST_PURCHASE_OFFERED:
            raise ValueError(
                f"purchase is {wf['status']}, not offered")
        if portal != "client" or purchase.get("buyer") != user:
            raise PermissionError(
                "Only the buyer (client) can decline a purchase offer")
        wf["status"] = ST_PURCHASE_DECLINED
        wf["completed_at"] = _now()
        self._log(wf, user, "purchase_declined",
                  f"{user} declined the purchase"
                  + (f" — {note}" if note else ""))
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "purchase_declined", wf_id,
                    {"note": note})
        self._publish("workflow.purchase_declined", wf, user, {"note": note})
        return wf

    def sign_purchase(self, user: str, portal: str, wf_id: str,
                      note: str = "") -> Dict[str, Any]:
        """The client signs the sale documents. The sale completes and the
        property is marked ``sold``."""
        wf = self._require(wf_id)
        purchase = wf.get("purchase")
        if not purchase:
            raise ValueError("workflow is not a purchase")
        if wf["status"] not in (ST_PURCHASE_DOCUMENTATION,
                                ST_PURCHASE_SIGNING):
            raise ValueError(
                f"purchase is {wf['status']}, not ready for signing")
        if portal != "client" or purchase.get("buyer") != user:
            raise PermissionError(
                "Only the buyer (client) can sign the purchase documents")
        purchase["signed"] = True
        purchase["signed_at"] = _now()
        wf["status"] = ST_PURCHASE_COMPLETED
        wf["completed_at"] = _now()
        wf["final_response"] = (
            f"Sale of {purchase.get('property_code', 'property')} completed. "
            f"Documents signed by {user}.")

        # Mark the property sold (best-effort; the workflow still completes
        # if the property store is unavailable).
        if self.properties is not None:
            try:
                self.properties.update_status(
                    purchase.get("property_id"), "sold", actor=user)
            except Exception:  # noqa: BLE001
                pass

        self._log(wf, user, "purchase_signed",
                  f"{user} signed the sale documents. Sale completed.")
        with self._lock:
            self._save()
        self._audit(f"user:{user}", "purchase_signed", wf_id,
                    {"property_id": purchase.get("property_id")})
        self._publish("workflow.purchase_completed", wf, user,
                      {"property_id": purchase.get("property_id"),
                       "final_response": wf["final_response"]})
        return wf

    def _add_purchase_input(self, wf: Dict[str, Any], to_portal: str,
                            to_user: str, question: str) -> None:
        """Add an input request to a purchase workflow (advocate/auditor).
        Purchase workflows are not 'workable' in the classic sense, so this
        bypasses the worker guard used by request_input."""
        inp_id = "inp_" + uuid.uuid4().hex[:10]
        inp = {
            "id": inp_id,
            "workflow_id": wf["id"],
            "from_user": wf.get("created_by"),
            "to_user": to_user,
            "to_portal": to_portal,
            "question": question,
            "status": "pending",
            "answer": None,
            "created_at": _now(),
            "answered_at": None,
        }
        wf.setdefault("inputs", []).append(inp)
        self._log(wf, wf.get("created_by"), "input_requested",
                  f"Connected {to_user} ({to_portal}): {question}")
        self._publish("workflow.input_requested", wf, wf.get("created_by"),
                      {"input_id": inp_id, "to_user": to_user,
                       "to_portal": to_portal, "question": question})

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
        # Purchase workflows: the buyer (client) is a first-class participant
        # and sees the offer, documents and signing even though they did not
        # create the workflow.
        purchase = wf.get("purchase")
        if purchase and portal == "client" \
                and purchase.get("buyer") == user:
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
        if portal not in APPROVER_PORTALS:
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