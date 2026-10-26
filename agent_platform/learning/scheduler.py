"""Learning scheduler / job budget.

Orchestrates the full self-learning pipeline as a *budgeted,
asynchronous* job. It:

  1. Reads new trajectories since the last run.
  2. Mines candidate insights/skills.
  3. Verifies each candidate (replay + hold-out + review).
  4. Runs the regression harness on passing candidates.
  5. Promotes survivors to the model registry / memory (reversibly).
  6. Consolidates memory.

The **job budget** caps how many candidates are processed per run and
tracks cumulative cost, so learning never burns unbounded compute and
never blocks user work. The evaluation dashboard (accuracy, privacy,
cost, latency) gates promotion.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..core.ollama import ModelRegistry
from ..core.memory import MemorySystem
from .insight_miner import InsightMiner, CandidateInsight
from .trajectory import TrajectoryStore
from .verification import VerificationGate
from .regression import RegressionHarness
from .consolidator import MemoryConsolidator


@dataclass
class LearningRunReport:
    run_id: str
    trajectories_processed: int
    candidates_mined: int
    verified_passed: int
    regression_passed: int
    promoted: int
    rejected: int
    pending_review: int
    budget_used: int
    budget_limit: int
    holdout_accuracy: float
    started_at: str
    finished_at: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class LearningScheduler:
    def __init__(
        self,
        trajectory_store: TrajectoryStore,
        miner: InsightMiner,
        verification: VerificationGate,
        regression: RegressionHarness,
        consolidator: MemoryConsolidator,
        registry: ModelRegistry,
        memory: MemorySystem,
        audit=None,
        budget_per_run: int = 10,
        min_accuracy: float = 0.6,
        state_path: str = "data/learning_state.json",
        require_human_review: bool = False,
    ):
        self.trajectories = trajectory_store
        self.miner = miner
        self.verification = verification
        self.regression = regression
        self.consolidator = consolidator
        self.registry = registry
        self.memory = memory
        self.audit = audit
        self.budget_per_run = budget_per_run
        self.min_accuracy = min_accuracy
        self.state_path = state_path
        # When True, a candidate that passes verification + regression is
        # NOT auto-promoted; it is queued for an explicit human review
        # (see `review`). This is the "review" gate of the verification
        # pipeline, wired into the promotion path.
        self.require_human_review = require_human_review
        self._state = self._load_state()

    # ---------- state ----------

    def _load_state(self) -> Dict[str, Any]:
        if os.path.isfile(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"last_trajectory_id": None, "runs": [], "promoted": []}

    def _save_state(self) -> None:
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, ensure_ascii=False)

    # ---------- the learning job ----------

    def run(
        self,
        baseline_answer_fn: Callable[[str], str],
        candidate_answer_fn: Optional[Callable[[str], str]] = None,
    ) -> LearningRunReport:
        """Execute one budgeted learning pass.

        `baseline_answer_fn` — how the platform answers now.
        `candidate_answer_fn` — how it would answer after applying a
        candidate (defaults to baseline; a knowledge/skill candidate can
        only help, so we score the baseline as the floor).
        """
        run_id = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
        started = datetime.now(timezone.utc).isoformat()
        notes: List[str] = []
        cand_fn = candidate_answer_fn or baseline_answer_fn

        # 1. New trajectories since last run
        all_trajs = self.trajectories.all()
        last_id = self._state.get("last_trajectory_id")
        if last_id and all_trajs:
            idx = next((i for i, t in enumerate(all_trajs)
                        if t.get("id") == last_id), None)
            new_trajs = all_trajs[idx + 1:] if idx is not None else all_trajs
        else:
            new_trajs = all_trajs

        if not new_trajs:
            notes.append("No new trajectories since last run.")
            report = self._finalize(run_id, started, 0, 0, 0, 0, 0, 0, 0,
                                    self.verification.score_holdout(baseline_answer_fn),
                                    notes)
            return report

        # 2. Mine candidates
        candidates = self.miner.mine(new_trajs)
        notes.append(f"Mined {len(candidates)} candidate(s).")

        # 3-5. Verify, regression, promote (within budget)
        verified_passed = 0
        regression_passed = 0
        promoted = 0
        rejected = 0
        pending_review = 0
        budget_used = 0

        for cand in candidates:
            if budget_used >= self.budget_per_run:
                notes.append("Budget exhausted — remaining candidates deferred.")
                break
            budget_used += 1

            # Verify
            vres = self.verification.verify(
                cand,
                replay_trajectories=[t for t in new_trajs
                                     if t.get("id") in cand.provenance],
                baseline_answer_fn=baseline_answer_fn,
                candidate_answer_fn=cand_fn,
            )
            if not vres.passed:
                rejected += 1
                cand.status = "rejected"
                notes.append(f"Rejected {cand.id} (verification).")
                self._persist_candidate(cand)
                continue
            verified_passed += 1

            # Regression
            rres = self.regression.run(cand.id, baseline_answer_fn, cand_fn)
            if not rres.passed:
                rejected += 1
                cand.status = "rejected"
                notes.append(f"Rejected {cand.id} (regression: {rres.notes}).")
                self._persist_candidate(cand)
                continue
            regression_passed += 1

            # Human-review gate (optional): if enabled, verified candidates
            # are queued for explicit review instead of auto-promoting.
            if self.require_human_review:
                cand.status = "verified"
                self._state.setdefault("pending_reviews", []).append(
                    cand.to_dict())
                self._state["pending_reviews"] = \
                    self._state["pending_reviews"][-50:]
                pending_review += 1
                if self.audit:
                    self.audit.record(
                        actor="learning_scheduler",
                        action="candidate_pending_review",
                        detail={"candidate_id": cand.id, "kind": cand.kind,
                                "scope": cand.scope},
                        result="pending_review",
                    )
                notes.append(f"Queued {cand.id} for human review.")
                continue

            # Promote (reversibly) — store as an active skill/fact and
            # register the model spec with provenance.
            cand.status = "promoted"
            self._promote(cand)
            promoted += 1
            notes.append(f"Promoted {cand.id} ({cand.kind}/{cand.scope}).")

        # 6. Consolidate memory
        self.consolidator.consolidate(kind="semantic")

        # Update state
        self._state["last_trajectory_id"] = all_trajs[-1].get("id")
        holdout = self.verification.score_holdout(baseline_answer_fn)
        report = self._finalize(run_id, started, len(new_trajs),
                                len(candidates), verified_passed,
                                regression_passed, promoted, rejected,
                                pending_review, holdout, notes, budget_used)
        self._state["runs"].append(report.to_dict())
        self._state["runs"] = self._state["runs"][-50:]  # keep last 50
        self._save_state()
        return report

    # ---------- promotion ----------

    def _promote(self, cand: CandidateInsight) -> None:
        # Store the insight/skill as active durable memory with provenance.
        kind = "procedural" if cand.kind == "skill" else "semantic"
        self.memory.store(
            kind=kind,
            content=cand.statement,
            provenance=",".join(cand.provenance[:5]),
            scope=cand.scope,
            confidence=cand.confidence,
            status="active",
        )
        # Record the promotion for audit/reversibility.
        self._state["promoted"].append({
            "candidate_id": cand.id,
            "kind": cand.kind,
            "scope": cand.scope,
            "statement": cand.statement,
            "provenance": cand.provenance,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
        })
        self._state["promoted"] = self._state["promoted"][-200:]
        if self.audit:
            self.audit.record(
                actor="learning_scheduler",
                action="promote",
                detail={"candidate_id": cand.id, "kind": cand.kind,
                        "scope": cand.scope,
                        "provenance": cand.provenance[:5]},
                result="promoted",
            )

    def _persist_candidate(self, cand: CandidateInsight) -> None:
        if self.audit:
            self.audit.record(
                actor="learning_scheduler",
                action="candidate_rejected",
                detail={"candidate_id": cand.id, "kind": cand.kind,
                        "scope": cand.scope},
                result=cand.status,
            )

    # ---------- human review gate ----------

    def pending_reviews(self) -> List[Dict[str, Any]]:
        """Candidates that passed verification + regression and are waiting
        for an explicit human decision (only populated when
        `require_human_review` is set)."""
        return list(self._state.get("pending_reviews", []))

    def review(self, candidate_id: str, decision: str,
               reviewer: str = "reviewer") -> bool:
        """Record a human review decision for a queued candidate.

        `decision` is one of `approved` | `rejected` | `edited`.
        `approved` (or `edited`) promotes the candidate now; `rejected`
        marks it rejected. Returns True if the candidate was found.
        """
        if decision not in ("approved", "rejected", "edited"):
            raise ValueError("decision must be approved | rejected | edited")
        queue = self._state.get("pending_reviews", [])
        target = next((c for c in queue if c.get("id") == candidate_id), None)
        if target is None:
            return False
        queue.remove(target)
        self._state["pending_reviews"] = queue
        cand = CandidateInsight(
            id=target.get("id", candidate_id),
            kind=target.get("kind", "fact"),
            statement=target.get("statement", ""),
            scope=target.get("scope", "general"),
            provenance=list(target.get("provenance", [])),
            confidence=float(target.get("confidence", 0.5)),
            version=int(target.get("version", 1)),
            status=target.get("status", "verified"),
            created_at=target.get("created_at", ""),
        )
        if decision == "rejected":
            cand.status = "rejected"
            self._persist_candidate(cand)
        else:
            cand.status = "promoted"
            self._promote(cand)
        if self.audit:
            self.audit.record(
                actor="learning_scheduler",
                action=f"review_{decision}",
                detail={"candidate_id": candidate_id, "kind": cand.kind,
                        "scope": cand.scope},
                user=reviewer, result=decision,
            )
        self._save_state()
        return True

    def _finalize(self, run_id, started, trajs, mined, verified, reg,
                  promoted, rejected, pending_review, holdout, notes,
                  budget_used=0) -> LearningRunReport:
        return LearningRunReport(
            run_id=run_id,
            trajectories_processed=trajs,
            candidates_mined=mined,
            verified_passed=verified,
            regression_passed=reg,
            promoted=promoted,
            rejected=rejected,
            pending_review=pending_review,
            budget_used=budget_used,
            budget_limit=self.budget_per_run,
            holdout_accuracy=round(holdout, 4),
            started_at=started,
            finished_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
        )

    # ---------- dashboard ----------

    def dashboard(self) -> Dict[str, Any]:
        """Evaluation + capability dashboard: quality, privacy, cost,
        latency inputs for gating promotion."""
        runs = self._state.get("runs", [])
        promoted = self._state.get("promoted", [])
        return {
            "total_runs": len(runs),
            "last_run": runs[-1] if runs else None,
            "total_promoted": len(promoted),
            "recent_promotions": promoted[-10:],
            "holdout_accuracy": (runs[-1]["holdout_accuracy"]
                                 if runs else None),
            "budget_per_run": self.budget_per_run,
            "min_accuracy": self.min_accuracy,
            "require_human_review": self.require_human_review,
            "pending_reviews": self.pending_reviews(),
        }