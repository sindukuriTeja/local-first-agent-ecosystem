"""Trajectory store — captures anonymized task traces + outcomes.

This is the raw fuel for the learning engine. Every completed task is
recorded as a trajectory: what was asked, which agents ran, what the
outcome was, and (optionally) user feedback. Personal identifiers are
stripped before storage so the learning loop never persists PII.

The audit log already records who/what/when for governance; the
trajectory store is the *learning* view — structured for the insight
miner to find patterns across many tasks.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Patterns that look like personal identifiers / amounts to strip.
_PII_PATTERNS = [
    (re.compile(r"\b\d{10,12}\b"), "[phone]"),                      # phone numbers
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[email]"),       # emails
    (re.compile(r"\b(?:matter|case|file)[\s_-]*[\w-]{2,}\b", re.I), "[matter]"),
    (re.compile(r"\b[A-Z]{2}\d{2,}\b"), "[id]"),                     # CIN-like
    (re.compile(r"[\d,]+(?:\.\d+)?\s*(?:lakh|crore|million|billion|₹|rs\.?|inr)\b", re.I), "[amount]"),
]


def anonymize(text: str) -> str:
    """Strip personal identifiers from a string before it is stored."""
    if not text:
        return ""
    out = text
    for pattern, repl in _PII_PATTERNS:
        out = pattern.sub(repl, out)
    return out


@dataclass
class Trajectory:
    id: str
    task_id: str
    request: str                 # anonymized
    agents_run: List[str] = field(default_factory=list)
    final_status: str = ""       # ok | needs_approval | error | abstain
    outcome: str = "unknown"     # success | failure | needs_approval | abstain
    sources: List[str] = field(default_factory=list)
    user: str = ""
    feedback: Optional[str] = None   # None | "good" | "bad" | rating
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class TrajectoryStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        if not os.path.isfile(path):
            open(path, "w").close()

    def record(
        self,
        task_id: str,
        request: str,
        agents_run: List[str],
        final_status: str,
        sources: Optional[List[str]] = None,
        user: str = "",
    ) -> str:
        """Record a completed task as an anonymized trajectory."""
        outcome = self._infer_outcome(final_status)
        traj = Trajectory(
            id=uuid.uuid4().hex[:12],
            task_id=task_id,
            request=anonymize(request),
            agents_run=list(agents_run),
            final_status=final_status,
            outcome=outcome,
            sources=list(sources or []),
            user=user,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(traj.to_dict(), ensure_ascii=False) + "\n")
        return traj.id

    def set_feedback(self, traj_id: str, feedback: str) -> bool:
        """Attach user feedback (good/bad/rating) to a trajectory."""
        lines = []
        changed = False
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d.get("id") == traj_id:
                    d["feedback"] = feedback
                    d["outcome"] = "success" if feedback in ("good", "up", "1") else \
                                   ("failure" if feedback in ("bad", "down", "0") else d.get("outcome"))
                    changed = True
                lines.append(json.dumps(d, ensure_ascii=False))
        if changed:
            with self._lock:
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
        return changed

    def all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        return rows[-limit:] if limit else rows

    def by_outcome(self, outcome: str) -> List[Dict[str, Any]]:
        return [t for t in self.all() if t.get("outcome") == outcome]

    def failures(self) -> List[Dict[str, Any]]:
        return self.by_outcome("failure")

    def needs_review(self) -> List[Dict[str, Any]]:
        """Trajectories that ended in needs_approval or abstain — these are
        the ones most likely to yield a learnable insight (a missing
        skill, a recurring gap)."""
        return [t for t in self.all()
                if t.get("outcome") in ("needs_approval", "abstain")]

    @staticmethod
    def _infer_outcome(status: str) -> str:
        return {
            "ok": "success",
            "needs_approval": "needs_approval",
            "abstain": "abstain",
            "error": "failure",
        }.get(status, "unknown")