"""Insight miner — batch analysis of trajectories to find patterns.

Takes the anonymized trajectory store and produces *candidate* insights
and skills. Each candidate carries provenance (which trajectories it
came from), scope (which agent/task class it applies to), and a version.

Two mining modes:
  - **model-driven**: the local model reads a digest of recent
    trajectories and proposes insights/skills as JSON.
  - **heuristic**: deterministic pattern detection (recurring abstentions,
    recurring missing-information, repeated agent sequences) — works even
    with a weak model and is fully testable.

Candidates are NEVER applied directly. They go to the VerificationGate.
"""

from __future__ import annotations

import json
import zlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class CandidateInsight:
    id: str
    kind: str                    # fact | skill | prompt_tweak | retrieval_tweak
    statement: str               # the insight / skill description
    scope: str                   # which agent(s) / task class it applies to
    provenance: List[str]        # trajectory ids it was derived from
    confidence: float = 0.5
    version: int = 1
    status: str = "candidate"    # candidate | verified | promoted | rejected
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class InsightMiner:
    def __init__(self, ollama=None, agent_id: str = "learning_insight_miner"):
        self.ollama = ollama
        self.agent_id = agent_id

    # ---------- heuristic mining (deterministic, always on) ----------

    def mine_heuristic(self, trajectories: List[Dict[str, Any]]) -> List[CandidateInsight]:
        """Find recurring patterns without a model.

        - Repeated abstentions on similar requests  -> retrieval gap
        - Repeated needs_approval                   -> process/skill gap
        - A recurring agent sequence that succeeds  -> reusable skill
        """
        candidates: List[CandidateInsight] = []
        now = datetime.now(timezone.utc).isoformat()

        # 1. Recurring abstentions -> retrieval/knowledge gap
        abstain_agents = Counter(
            t.get("agents_run", [])[-1] if t.get("agents_run") else "unknown"
            for t in trajectories if t.get("outcome") == "abstain"
        )
        for agent, count in abstain_agents.items():
            if count >= 2:
                candidates.append(CandidateInsight(
                    id=f"cand_abstain_{agent[:20]}_{count}",
                    kind="retrieval_tweak",
                    statement=(
                        f"Agent '{agent}' abstained {count} times on similar "
                        f"requests. Likely a knowledge/retrieval gap — consider "
                        f"adding source material or lowering the retrieval "
                        f"min-score for this task class."
                    ),
                    scope=agent,
                    provenance=[t["id"] for t in trajectories
                                if t.get("outcome") == "abstain"][:10],
                    confidence=min(0.9, 0.4 + 0.1 * count),
                    created_at=now,
                ))

        # 2. Recurring needs_approval -> process/skill gap
        approval_agents = Counter(
            t.get("agents_run", [])[-1] if t.get("agents_run") else "unknown"
            for t in trajectories if t.get("outcome") == "needs_approval"
        )
        for agent, count in approval_agents.items():
            if count >= 2:
                candidates.append(CandidateInsight(
                    id=f"cand_approval_{agent[:20]}_{count}",
                    kind="skill",
                    statement=(
                        f"Agent '{agent}' produced {count} drafts/items needing "
                        f"approval. Consider a reusable skill/checklist to "
                        f"improve first-pass quality for this task class."
                    ),
                    scope=agent,
                    provenance=[t["id"] for t in trajectories
                                if t.get("outcome") == "needs_approval"][:10],
                    confidence=min(0.8, 0.3 + 0.1 * count),
                    created_at=now,
                ))

        # 3. Recurring successful agent sequences -> reusable skill
        seq_counter = Counter(
            tuple(t.get("agents_run", []))
            for t in trajectories if t.get("outcome") == "success"
        )
        for seq, count in seq_counter.items():
            if count >= 2 and len(seq) >= 2:
                candidates.append(CandidateInsight(
                    id=f"cand_skill_{'_'.join(s[-8:] for s in seq)}_{count}",
                    kind="skill",
                    statement=(
                        f"Agent sequence {' -> '.join(seq)} succeeded {count} "
                        f"times. Candidate reusable skill for this workflow."
                    ),
                    scope="orchestration",
                    provenance=[t["id"] for t in trajectories
                                if tuple(t.get("agents_run", [])) == seq][:10],
                    confidence=min(0.85, 0.4 + 0.1 * count),
                    created_at=now,
                ))

        return candidates

    # ---------- model-driven mining (optional, needs a local model) ----------

    def mine_with_model(self, trajectories: List[Dict[str, Any]],
                        max_digest: int = 40) -> List[CandidateInsight]:
        """Ask the local model to propose insights from a trajectory digest."""
        if self.ollama is None:
            return []
        digest = self._digest(trajectories[-max_digest:])
        system = (
            "You are the insight miner in a self-learning agent platform. "
            "Analyze the anonymized task trajectories and propose candidate "
            "insights or skills. Respond with ONLY a JSON object: "
            "{\"candidates\": [{\"kind\": one of fact|skill|prompt_tweak|"
            "\"retrieval_tweak\", \"statement\": str, \"scope\": str, "
            "\"confidence\": float}]}. Only propose insights actually "
            "supported by the trajectories. Do not invent facts."
        )
        try:
            raw = self.ollama.chat(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": digest}],
                model=self.ollama.default_model if hasattr(self.ollama, "default_model") else "llama3.1:8b",
                temperature=0.2, json_mode=True,
            )
            from ..core.ollama import extract_json
            parsed = extract_json(raw)
        except Exception:
            return []
        if not parsed or "candidates" not in parsed:
            return []
        now = datetime.now(timezone.utc).isoformat()
        out = []
        # Provenance: the trajectories the model actually saw (the digest
        # window), not an arbitrary first-10 slice — this keeps the
        # replay test meaningful for model-mined candidates.
        digest_ids = [t["id"] for t in trajectories[-max_digest:]][:10]
        for i, c in enumerate(parsed.get("candidates", []) or []):
            if not isinstance(c, dict) or "statement" not in c:
                continue
            out.append(CandidateInsight(
                # unique, deterministic id (index + crc32 of the statement)
                # so two model candidates in one run never collide and the
                # id is stable across runs.
                id=f"cand_model_{i}_{zlib.crc32(str(c['statement']).encode('utf-8')) % 100000}",
                kind=c.get("kind", "fact"),
                statement=str(c["statement"]),
                scope=c.get("scope", "general"),
                provenance=digest_ids,
                confidence=float(c.get("confidence", 0.5)),
                created_at=now,
            ))
        return out

    def mine(self, trajectories: List[Dict[str, Any]]) -> List[CandidateInsight]:
        """Run both miners and de-duplicate by (kind, scope)."""
        cands = self.mine_heuristic(trajectories)
        if self.ollama is not None:
            cands.extend(self.mine_with_model(trajectories))
        seen = set()
        deduped = []
        for c in cands:
            key = (c.kind, c.scope)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        return deduped

    @staticmethod
    def _digest(trajectories: List[Dict[str, Any]]) -> str:
        lines = []
        for t in trajectories:
            lines.append(
                f"- [{t.get('outcome')}] agents={t.get('agents_run')} "
                f"request=\"{t.get('request', '')[:120]}\""
            )
        return "Trajectories:\n" + "\n".join(lines)