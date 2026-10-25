"""Human approval gate.

Drafts (Agent 7), external sharing (Agent 15), and voice notifications
(Agent 16) all require an authorized human reviewer to approve before
they leave the platform. This module manages the approval lifecycle:

    pending -> approved | rejected | corrected

Approvals are recorded in the audit log and persisted so they can be
retrieved later. In Phase 1 the "human" acts via the API/CLI; a real UI
can plug into the same interface.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .audit import AuditLog


@dataclass
class ApprovalRequest:
    id: str
    kind: str                    # draft | external_share | voice | other
    title: str
    payload: Dict[str, Any] = field(default_factory=dict)
    requested_by: str = ""
    requested_at: str = ""
    status: str = "pending"      # pending | approved | rejected | corrected
    decided_by: str = ""
    decided_at: str = ""
    decision_note: str = ""
    corrected_payload: Dict[str, Any] = field(default_factory=dict)


class ApprovalGate:
    def __init__(self, store_path: str, audit: AuditLog):
        self.store_path = store_path
        self.audit = audit
        os.makedirs(os.path.dirname(store_path) or ".", exist_ok=True)
        if not os.path.isfile(store_path):
            with open(self.store_path, "w", encoding="utf-8") as f:
                f.write("")

    def _load(self) -> List[Dict[str, Any]]:
        out = []
        with open(self.store_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return out

    def _save(self, items: List[Dict[str, Any]]) -> None:
        with open(self.store_path, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")

    def request(
        self,
        kind: str,
        title: str,
        payload: Optional[Dict[str, Any]] = None,
        requested_by: str = "",
    ) -> ApprovalRequest:
        now = datetime.now(timezone.utc).isoformat()
        req = ApprovalRequest(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            title=title,
            payload=payload or {},
            requested_by=requested_by,
            requested_at=now,
        )
        items = self._load()
        items.append(req.__dict__)
        self._save(items)
        self.audit.record(
            actor="approval_gate", action="approval_requested",
            detail={"approval_id": req.id, "kind": kind, "title": title},
            user=requested_by, result="pending",
        )
        return req

    def decide(
        self,
        approval_id: str,
        decision: str,
        decided_by: str,
        note: str = "",
        corrected_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[ApprovalRequest]:
        if decision not in ("approved", "rejected", "corrected"):
            raise ValueError("decision must be approved | rejected | corrected")
        items = self._load()
        target = None
        for it in items:
            if it.get("id") == approval_id:
                it["status"] = decision
                it["decided_by"] = decided_by
                it["decided_at"] = datetime.now(timezone.utc).isoformat()
                it["decision_note"] = note
                if corrected_payload:
                    it["corrected_payload"] = corrected_payload
                target = it
                break
        if target is None:
            return None
        self._save(items)
        self.audit.record(
            actor="approval_gate", action=f"approval_{decision}",
            detail={"approval_id": approval_id, "note": note},
            user=decided_by, result=decision,
        )
        return ApprovalRequest(**target)

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        for it in self._load():
            if it.get("id") == approval_id:
                return ApprovalRequest(**it)
        return None

    def pending(self, kind: Optional[str] = None) -> List[ApprovalRequest]:
        out = []
        for it in self._load():
            if it.get("status") != "pending":
                continue
            if kind and it.get("kind") != kind:
                continue
            out.append(ApprovalRequest(**it))
        return out

    def history(self, limit: int = 100) -> List[ApprovalRequest]:
        items = self._load()
        return [ApprovalRequest(**it) for it in items[-limit:]]