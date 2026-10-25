"""Memory system (L2 in the architecture).

Four memory types, all access-scoped and versioned:
  - Working memory:  the current task's scratchpad (ephemeral, per-run)
  - Semantic memory: consolidated facts + insights (durable)
  - Episodic memory: past experiences + outcomes (durable)
  - Procedural memory: versioned skills / learned procedures (durable)

Semantic/episodic/procedural are persisted as JSONL so the platform can
learn across sessions without a heavyweight database. Working memory is
in-memory and cleared when a task completes.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    id: str
    kind: str            # semantic | episodic | procedural
    content: str
    provenance: str = "" # where this came from (doc id, task id, ...)
    scope: str = "default"
    version: int = 1
    confidence: float = 1.0
    status: str = "active"  # active | candidate | rejected | decayed
    created_at: str = ""
    updated_at: str = ""


class MemorySystem:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._lock = threading.Lock()
        # Working memory: task_id -> dict of scratch state
        self.working: Dict[str, Dict[str, Any]] = {}

    def _path(self, kind: str) -> str:
        return os.path.join(self.data_dir, f"memory_{kind}.jsonl")

    # ---------- working memory ----------

    def start_task(self, task_id: str, initial: Optional[Dict[str, Any]] = None) -> None:
        self.working[task_id] = initial or {"task_id": task_id}

    def update_working(self, task_id: str, **kv: Any) -> None:
        if task_id not in self.working:
            self.start_task(task_id)
        self.working[task_id].update(kv)

    def get_working(self, task_id: str) -> Dict[str, Any]:
        return self.working.get(task_id, {})

    def clear_task(self, task_id: str) -> None:
        self.working.pop(task_id, None)

    # ---------- durable memory ----------

    def store(
        self,
        kind: str,
        content: str,
        provenance: str = "",
        scope: str = "default",
        confidence: float = 1.0,
        status: str = "active",
    ) -> str:
        now = datetime.now(timezone.utc).isoformat()
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            content=content,
            provenance=provenance,
            scope=scope,
            confidence=confidence,
            status=status,
            created_at=now,
            updated_at=now,
        )
        line = json.dumps(entry.__dict__, ensure_ascii=False)
        with self._lock:
            with open(self._path(kind), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return entry.id

    def recall(
        self,
        kind: str,
        scope: str = "default",
        status: str = "active",
        limit: int = 50,
    ) -> List[MemoryEntry]:
        path = self._path(kind)
        if not os.path.isfile(path):
            return []
        out: List[MemoryEntry] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if scope and d.get("scope") != scope:
                    continue
                if status and d.get("status") != status:
                    continue
                out.append(MemoryEntry(**d))
        return out[-limit:]

    def promote(self, entry_id: str, kind: str) -> bool:
        """Move a candidate entry to active (after verification)."""
        path = self._path(kind)
        if not os.path.isfile(path):
            return False
        lines = []
        changed = False
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d.get("id") == entry_id and d.get("status") == "candidate":
                    d["status"] = "active"
                    d["updated_at"] = datetime.now(timezone.utc).isoformat()
                    changed = True
                lines.append(json.dumps(d, ensure_ascii=False))
        if changed:
            with self._lock:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
        return changed

    def reject(self, entry_id: str, kind: str) -> bool:
        return self._set_status(entry_id, kind, "rejected")

    def _set_status(self, entry_id: str, kind: str, status: str) -> bool:
        path = self._path(kind)
        if not os.path.isfile(path):
            return False
        lines = []
        changed = False
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d.get("id") == entry_id:
                    d["status"] = status
                    d["updated_at"] = datetime.now(timezone.utc).isoformat()
                    changed = True
                lines.append(json.dumps(d, ensure_ascii=False))
        if changed:
            with self._lock:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
        return changed