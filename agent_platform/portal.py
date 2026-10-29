"""Portal layer: turns the platform's data into per-role portal payloads.

Every portal reads through the *same* governed knowledge store, but each
role only sees what its scope allows:

  - sensitivity ceiling  (role -> max level)
  - document-type filter (e.g. auditor only sees compliance/audit docs)
  - tenant               (multi-tenant isolation)
  - matter / client / parcel scope (assigned work)

This keeps the "controlled access" guarantee consistent with the agent
path: the portal never bypasses the sensitivity ladder.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .core.auth import PortalUser, PORTAL_DOC_TYPES
from .core.base_agent import AgentContext, AgentResult
from .platform import Platform

_LEVELS = ["public", "internal", "confidential", "restricted"]


def _meta(doc) -> Dict[str, Any]:
    md = doc.metadata or {}
    if isinstance(md, str):
        try:
            md = json.loads(md)
        except (ValueError, TypeError):
            md = {}
    return md


def _doc_view(doc, include_content: bool = True) -> Dict[str, Any]:
    md = _meta(doc)
    v = {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "sensitivity": doc.sensitivity,
        "tenant": doc.tenant,
        "status": doc.status,
        "source": doc.source,
        "updated_at": doc.updated_at,
        "created_at": doc.created_at,
        "matter": md.get("matter"),
        "client": md.get("client"),
        "parcel": md.get("parcel"),
        "subject": md.get("subject"),
        "company": md.get("company"),
        "deadline": md.get("deadline") or md.get("due"),
        "amount": md.get("amount") or md.get("outstanding"),
        "summary": (doc.content or "")[:280],
    }
    if include_content:
        v["content"] = doc.content
    return v


class PortalService:
    def __init__(self, platform: Platform):
        self.p = platform

    # ------------------------------------------------------------------
    # scoped retrieval
    # ------------------------------------------------------------------
    def scoped_documents(self, user: PortalUser,
                         doc_types: Optional[List[str]] = None,
                         limit: int = 200) -> List[Any]:
        """Documents visible to `user` under sensitivity + type + scope."""
        if doc_types is None:
            doc_types = PORTAL_DOC_TYPES.get(user.portal)
        docs = self.p.knowledge.list_documents(
            tenant=user.tenant,
            sensitivity_max=user.max_sensitivity,
            limit=limit,
        )
        out = []
        for d in docs:
            if doc_types and d.doc_type not in doc_types:
                continue
            if not self._in_scope(user, d):
                continue
            out.append(d)
        return out

    def _in_scope(self, user: PortalUser, doc) -> bool:
        """Matter/client/parcel scoping. Firm-wide roles see everything."""
        md = _meta(doc)
        if user.portal in ("management", "admin"):
            return True
        if user.portal == "auditor":
            # auditors only get explicitly compliance/audit-labelled docs
            return doc.doc_type in ("compliance", "audit", "case_analysis", "tax")
        if user.portal == "client":
            client = md.get("client")
            return (not client) or (not user.clients) or (client in user.clients)
        if user.portal == "tenant":
            parcel = md.get("parcel")
            return (not parcel) or (not user.parcels) or (parcel in user.parcels)
        # employee / counsel: matter + client assignment
        matter = md.get("matter")
        client = md.get("client")
        if matter and user.matters and matter not in user.matters:
            return False
        if client and user.clients and client not in user.clients:
            return False
        return True

    # ------------------------------------------------------------------
    # per-portal payloads
    # ------------------------------------------------------------------
    def portal_data(self, user: PortalUser) -> Dict[str, Any]:
        docs = self.scoped_documents(user)
        by_type: Dict[str, List[Any]] = {}
        for d in docs:
            by_type.setdefault(d.doc_type, []).append(d)

        data: Dict[str, Any] = {
            "user": user.to_dict(),
            "portal": user.portal,
            "portal_name": None,
            "counts": {
                "documents": len(docs),
                "cases": len(by_type.get("case_analysis", [])),
                "tax": len(by_type.get("tax", [])),
                "land": len(by_type.get("land_title", [])),
                "debt": len(by_type.get("debt", [])),
                "entities": len(by_type.get("entity_profile", [])),
                "compliance": len(by_type.get("compliance", [])),
                "drafts": len(by_type.get("draft", [])),
                "requests": len(by_type.get("request", [])),
            },
        }

        # Real-time collaboration workflow queue (all roles)
        data["workflow"] = self.workflow_data(user)

        if user.portal == "employee":
            data.update(self._employee(user, docs, by_type))
        elif user.portal == "management":
            data.update(self._management(user, docs, by_type))
        elif user.portal == "counsel":
            data.update(self._counsel(user, docs, by_type))
        elif user.portal == "client":
            data.update(self._client(user, docs, by_type))
        elif user.portal == "tenant":
            data.update(self._tenant(user, docs, by_type))
        elif user.portal == "auditor":
            data.update(self._auditor(user, docs, by_type))
        elif user.portal == "admin":
            data.update(self._admin(user, docs, by_type))
        return data

    # ---- employee ----------------------------------------------------
    def _employee(self, user, docs, by_type):
        cases = [_doc_view(d, include_content=False) for d in by_type.get("case_analysis", [])]
        tax = [_doc_view(d, include_content=False) for d in by_type.get("tax", [])]
        legal = [_doc_view(d, include_content=False) for d in
                 (by_type.get("statute", []) + by_type.get("judgment", []))]
        drafts = [_doc_view(d, include_content=False) for d in by_type.get("draft", [])]
        return {
            "cases": cases,
            "tax_matters": tax,
            "legal_work": legal,
            "drafts": drafts,
            "documents": [_doc_view(d, include_content=False) for d in docs[:60]],
            "ai_tasks": self._ai_task_prompts(user),
        }

    # ---- management --------------------------------------------------
    def _management(self, user, docs, by_type):
        p = self.p
        pending = p.pending_approvals()
        # workload by matter (from case docs)
        workload: Dict[str, Dict[str, Any]] = {}
        for d in by_type.get("case_analysis", []):
            m = _meta(d).get("matter") or "unassigned"
            workload.setdefault(m, {"matter": m, "client": _meta(d).get("client"),
                                    "deadline": _meta(d).get("deadline"),
                                    "items": 0})
            workload[m]["items"] += 1
        # risk from latest compliance snapshot
        risks = []
        for d in by_type.get("compliance", [])[:3]:
            risks.append({"title": d.title, "summary": (d.content or "")[:300]})
        # sensitivity distribution
        sens_dist: Dict[str, int] = {}
        for d in docs:
            sens_dist[d.sensitivity] = sens_dist.get(d.sensitivity, 0) + 1
        return {
            "kpi": {
                "documents": len(docs),
                "open_cases": len(by_type.get("case_analysis", [])),
                "pending_approvals": len(pending),
                "tax_matters": len(by_type.get("tax", [])),
                "land_parcels": len(by_type.get("land_title", [])),
                "entities": len(by_type.get("entity_profile", [])),
            },
            "workload": list(workload.values()),
            "risk_alerts": risks,
            "sensitivity_distribution": sens_dist,
            "pending_approvals": [
                {"id": a.id, "kind": a.kind, "title": a.title,
                 "requested_by": a.requested_by, "requested_at": a.requested_at}
                for a in pending
            ],
            "recent_audit": p.audit_query(limit=12),
            "learning": p.learning_dashboard() if p.learning_scheduler else None,
        }

    # ---- counsel -----------------------------------------------------
    def _counsel(self, user, docs, by_type):
        cases = [_doc_view(d, include_content=False) for d in by_type.get("case_analysis", [])]
        drafts = [_doc_view(d, include_content=False) for d in by_type.get("draft", [])]
        research = [_doc_view(d, include_content=False) for d in
                    (by_type.get("legal_note", []) + by_type.get("statute", []) +
                     by_type.get("judgment", []))]
        return {
            "cases": cases,
            "drafts_to_review": drafts,
            "research": research,
            "documents": [_doc_view(d, include_content=False) for d in docs[:60]],
            "ai_tasks": self._ai_task_prompts(user),
        }

    # ---- client ------------------------------------------------------
    def _client(self, user, docs, by_type):
        cases = [_doc_view(d, include_content=False) for d in by_type.get("case_analysis", [])]
        reports = [_doc_view(d, include_content=False) for d in
                   (by_type.get("compliance", []) + by_type.get("report", []))]
        requests = [_doc_view(d, include_content=False) for d in by_type.get("request", [])]
        return {
            "cases": cases,
            "reports": reports,
            "my_requests": requests,
            "documents": [_doc_view(d, include_content=False) for d in docs[:60]],
        }

    # ---- tenant ------------------------------------------------------
    def _tenant(self, user, docs, by_type):
        parcels = [_doc_view(d, include_content=False) for d in by_type.get("land_title", [])]
        requests = [_doc_view(d, include_content=False) for d in by_type.get("request", [])]
        updates = [_doc_view(d, include_content=False) for d in
                   (by_type.get("compliance", []) + by_type.get("note", []))[:20]]
        return {
            "parcels": parcels,
            "my_requests": requests,
            "updates": updates,
        }

    # ---- auditor -----------------------------------------------------
    def _auditor(self, user, docs, by_type):
        records = [_doc_view(d, include_content=True) for d in docs]
        return {
            "compliance_records": records,
            "audit_trail": self.p.audit_query(limit=200),
            "note": "You see only explicitly shared compliance/audit records "
                    "(controlled access).",
        }

    # ---- admin -------------------------------------------------------
    def _admin(self, user, docs, by_type):
        p = self.p
        from .core.auth import AuthManager  # local import to avoid cycle
        return {
            "kpi": {
                "documents": len(docs),
                "agents": len(p.agents),
                "pending_approvals": len(p.pending_approvals()),
                "users": len(p.auth.list_users()) if hasattr(p, "auth") else 0,
                "ollama_available": p.services.ollama.is_available(),
            },
            "agents": [
                {"id": aid, "name": a.name, "enabled": p.settings.is_agent_enabled(aid)}
                for aid, a in p.agents.items()
            ],
            "pending_approvals": [
                {"id": a.id, "kind": a.kind, "title": a.title,
                 "requested_by": a.requested_by, "requested_at": a.requested_at}
                for a in p.pending_approvals()
            ],
            "learning": p.learning_dashboard() if p.learning_scheduler else None,
            "recent_audit": p.audit_query(limit=30),
        }

    # ------------------------------------------------------------------
    # real-time collaboration workflow (client -> management -> employee)
    # ------------------------------------------------------------------
    def workflow_data(self, user: PortalUser) -> Dict[str, Any]:
        """Live workflow queue for this role + pending input requests."""
        wf = self.p.workflow
        if wf is None:
            return {"available": False}
        items = wf.list_workflows(user.username, user.portal)
        pending_inputs = []
        if wf is not None:
            for w in items:
                for inp in w.get("inputs", []):
                    if inp.get("status") == "pending" and (
                            inp.get("to_user") == user.username
                            or inp.get("to_portal") == user.portal):
                        pending_inputs.append({
                            "input_id": inp["id"],
                            "workflow_id": w["id"],
                            "subject": w.get("subject"),
                            "from_user": inp.get("from_user"),
                            "question": inp.get("question"),
                        })
        return {
            "available": True,
            "workflows": items,
            "pending_inputs": pending_inputs,
        }

    # ------------------------------------------------------------------
    # AI-assisted task prompts (per portal)
    # ------------------------------------------------------------------
    @staticmethod
    def _ai_task_prompts(user: PortalUser) -> List[Dict[str, str]]:
        base = {
            "employee": [
                {"label": "Summarize my cases", "prompt": "Summarize the status of my assigned cases and any upcoming deadlines."},
                {"label": "Draft a client notice", "prompt": "Draft a notice to the client about the current case status."},
                {"label": "Check compliance deadlines", "prompt": "List all compliance deadlines and risks for my matters."},
            ],
            "counsel": [
                {"label": "Research a legal question", "prompt": "Research the applicable statute and case law for my assigned matter."},
                {"label": "Review a draft", "prompt": "Review the latest draft for accuracy and flag any unverified fields."},
                {"label": "Summarize evidence", "prompt": "Summarize the evidence and timeline for my assigned case."},
            ],
        }
        return base.get(user.portal, [])

    # ------------------------------------------------------------------
    # AI task execution (through the governed orchestrator)
    # ------------------------------------------------------------------
    def run_ai_task(self, user: PortalUser, prompt: str,
                    state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = self.p.handle_request(user.username, prompt, user.tenant,
                                       state or {})
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

    # ------------------------------------------------------------------
    # client / tenant request + document submission
    # ------------------------------------------------------------------
    def submit_request(self, user: PortalUser, subject: str,
                       message: str) -> Dict[str, Any]:
        doc_id = self.p.knowledge.add_document(
            title=f"Request: {subject}",
            content=message,
            source=f"portal_request:{user.username}",
            doc_type="request",
            sensitivity="internal",
            tenant=user.tenant,
            metadata={"from": user.username, "portal": user.portal,
                      "subject": subject},
        )
        self.p.audit.record(actor=f"user:{user.username}", action="request_submitted",
                            detail={"subject": subject, "doc_id": doc_id},
                            user=user.username, result="submitted")
        return {"doc_id": doc_id, "subject": subject, "status": "submitted"}

    def upload_document(self, user: PortalUser, filename: str, data: bytes,
                        sensitivity: str = "internal") -> Dict[str, Any]:
        result = self.p.run_agent(
            "agent_4_document_intake_ocr", user.username,
            f"Ingest document {filename}", user.tenant,
            state={"files": [None], "sensitivity": sensitivity,
                   "inline_bytes": data, "inline_name": filename},
        )
        return {
            "agent_id": result.agent_id,
            "status": result.status,
            "answer": result.answer,
            "data": result.data,
            "approval_id": result.approval_id,
            "error": result.error,
        }

    # ------------------------------------------------------------------
    # approvals (role-gated)
    # ------------------------------------------------------------------
    def decide_approval(self, user: PortalUser, approval_id: str,
                        decision: str, note: str = ""):
        if not user.can_approve:
            raise PermissionError(f"Role '{user.role}' is not an approver.")
        return self.p.decide_approval(approval_id, decision, user.username, note)


# ---------------------------------------------------------------------------
# Demo content seeding (makes every portal populated on first run)
# ---------------------------------------------------------------------------

def seed_demo_content(p: Platform) -> int:
    """Add a few portal-specific demo records if not already present."""
    added = 0

    def has(source_prefix: str) -> bool:
        rows = p.knowledge._conn.execute(
            "SELECT 1 FROM documents WHERE source LIKE ? LIMIT 1",
            (source_prefix + "%",)).fetchone()
        return rows is not None

    if not has("demo:"):
        # Client request
        p.knowledge.add_document(
            title="Request: Updated matter status",
            content="Please provide an updated status on matter M-100 and the "
                    "next steps. Also confirm the filing deadline.",
            source="demo:client_request", doc_type="request",
            sensitivity="internal", tenant="default",
            metadata={"from": "client1", "portal": "client",
                      "subject": "Updated matter status"})
        added += 1
        # Case note
        p.knowledge.add_document(
            title="Case note — M-100 evidence review",
            content="Reviewed the contract and correspondence for M-100. The "
                    "client TestCorp Ltd is active. Key deadline 2026-12-01. "
                    "Amount in dispute 500000. Section 12 of Statute X applies.",
            source="demo:case_note", doc_type="case_analysis",
            sensitivity="confidential", tenant="default",
            metadata={"matter": "M-100", "client": "TestCorp Ltd",
                      "deadline": "2026-12-01", "amount": "500000"})
        added += 1
        # Compliance snapshot
        p.knowledge.add_document(
            title="Compliance snapshot — firm-wide",
            content="Deadlines: MGT-7 annual return due 2026-12-01 (M-100). "
                    "Risks: [medium] limitation period expiring on M-102. "
                    "Alerts: [high] filing deadline approaching (ack required).",
            source="demo:compliance", doc_type="compliance",
            sensitivity="confidential", tenant="default",
            metadata={"deadlines": [{"item": "MGT-7", "due_date": "2026-12-01"}],
                      "risks": [{"risk": "limitation expiring", "severity": "medium"}],
                      "alerts": [{"message": "filing deadline approaching",
                                  "severity": "high",
                                  "requires_acknowledgement": True}]})
        added += 1
        # Tenant update
        p.knowledge.add_document(
            title="Property update — P1",
            content="Title search for parcel P1 is clear. Registration due "
                    "2026-11-01. No active disputes on record.",
            source="demo:tenant_update", doc_type="note",
            sensitivity="internal", tenant="default",
            metadata={"parcel": "P1"})
        added += 1
        p.knowledge._conn.commit()
    return added