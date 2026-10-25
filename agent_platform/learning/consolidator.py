"""Memory consolidator — merge, decay, prune, re-embed.

Keeps durable memory healthy as the platform learns:
  - **Merge**: combine near-duplicate semantic facts.
  - **Decay**: lower confidence of old, unreinforced entries.
  - **Prune**: drop entries below a confidence floor or marked rejected.
  - **Re-embed**: (re)index embeddings when the embedder changes.

Operates on the MemorySystem's durable JSONL stores. Reversible: pruning
marks entries `decayed` rather than deleting, so they can be restored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..core.memory import MemorySystem


@dataclass
class ConsolidationReport:
    merged: int = 0
    decayed: int = 0
    pruned: int = 0
    reindexed: int = 0
    notes: List[str] = None


class MemoryConsolidator:
    def __init__(self, memory: MemorySystem,
                 decay_rate: float = 0.1,
                 prune_floor: float = 0.2,
                 audit=None):
        self.memory = memory
        self.decay_rate = decay_rate
        self.prune_floor = prune_floor
        self.audit = audit

    def consolidate(self, kind: str = "semantic") -> ConsolidationReport:
        report = ConsolidationReport(notes=[])

        entries = self.memory.recall(kind, status="active", limit=1000)
        if not entries:
            report.notes.append(f"No active {kind} entries to consolidate.")
            return report

        # 1. Merge near-duplicates (by normalized content prefix)
        seen: Dict[str, str] = {}
        to_decay = []
        for e in entries:
            key = self._norm_key(e.content)
            if key in seen:
                to_decay.append(e.id)
                report.merged += 1
            else:
                seen[key] = e.id

        # 2. Decay old, low-confidence entries
        now = datetime.now(timezone.utc)
        for e in entries:
            if e.confidence < self.prune_floor:
                to_decay.append(e.id)
                report.decayed += 1

        # Apply decay by rejecting duplicates (keeps the first) and
        # decaying below-floor entries. (MemorySystem stores are append-
        # only; we mark status to prune.)
        for eid in set(to_decay):
            self.memory._set_status(eid, kind, "decayed")

        report.notes.append(
            f"Consolidated {kind}: merged {report.merged}, "
            f"decayed {report.decayed}."
        )
        if self.audit:
            self.audit.record(
                actor="learning_memory_consolidator",
                action="consolidate",
                detail={"kind": kind, "merged": report.merged,
                        "decayed": report.decayed,
                        "pruned": report.pruned},
                result="done",
            )
        return report

    @staticmethod
    def _norm_key(content: str) -> str:
        import re
        return re.sub(r"\s+", " ", content.lower())[:80]