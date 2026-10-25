"""Append-only audit log.

Every agent action in the platform is recorded here: who, what, when,
sources used, result. The log is append-only JSONL — entries are never
modified or deleted (retention/right-to-forget is handled at the
knowledge-store level, not by rewriting history).
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional


class AuditLog:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()

    def record(
        self,
        actor: str,
        action: str,
        detail: Optional[Dict[str, Any]] = None,
        sources: Optional[List[str]] = None,
        result: Optional[str] = None,
        user: Optional[str] = None,
    ) -> str:
        """Append one audit entry. Returns the entry id."""
        entry_id = uuid.uuid4().hex[:12]
        entry = {
            "id": entry_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,          # agent id or "user:<name>"
            "action": action,        # e.g. "route", "retrieve", "draft", "approve"
            "user": user,
            "detail": detail or {},
            "sources": sources or [],
            "result": result,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return entry_id

    def entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read the most recent `limit` entries (newest last)."""
        if not os.path.isfile(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out = []
        for line in lines[-limit:]:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def iter_all(self) -> Iterator[Dict[str, Any]]:
        if not os.path.isfile(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    def query(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        user: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Filter audit entries by actor / action / user."""
        out = []
        for e in self.iter_all():
            if actor and e.get("actor") != actor:
                continue
            if action and e.get("action") != action:
                continue
            if user and e.get("user") != user:
                continue
            out.append(e)
            if len(out) >= limit:
                break
        return out