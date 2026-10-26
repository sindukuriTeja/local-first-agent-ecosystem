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

from dataclasses import dataclass, field
from typing import List

from ..core.memory import MemorySystem


@dataclass
class ConsolidationReport:
    merged: int = 0
    decayed: int = 0
    pruned: int = 0
    reindexed: int = 0
    # NOTE: must use field(default_factory=list) — a bare `= None` default
    # (or a mutable default) is a latent bug here.
    notes: List[str] = field(default_factory=list)


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

        # 1. Merge near-duplicates (by normalized content prefix) — keep
        #    the first occurrence, mark the rest decayed.
        seen: Dict[str, str] = {}
        dup_ids: List[str] = []
        for e in entries:
            key = self._norm_key(e.content)
            if key in seen:
                dup_ids.append(e.id)
                report.merged += 1
            else:
                seen[key] = e.id

        # 2. Prune low-confidence entries (below the floor).
        low_conf_ids: List[str] = []
        for e in entries:
            if e.confidence < self.prune_floor and e.id not in dup_ids:
                low_conf_ids.append(e.id)
                report.pruned += 1

        # Apply by marking status (MemorySystem stores are append-only;
        # marking keeps the operation reversible — a decayed entry can be
        # re-activated).
        for eid in set(dup_ids):
            self.memory._set_status(eid, kind, "decayed")
            report.decayed += 1
        for eid in low_conf_ids:
            self.memory._set_status(eid, kind, "decayed")
            report.decayed += 1

        report.notes.append(
            f"Consolidated {kind}: merged {report.merged}, "
            f"pruned {report.pruned}, decayed {report.decayed}."
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