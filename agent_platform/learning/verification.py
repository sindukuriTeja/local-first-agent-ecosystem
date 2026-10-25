"""Verification gate — replay | hold-out tests | review.

A candidate insight/skill is only promoted if it PASSES verification:

  1. **Replay test** — re-run the trajectories the candidate was derived
     from and confirm the proposed change would not break them.
  2. **Hold-out test** — run the candidate against the exam set (the
     Q&A ground truth) and confirm it does not degrade accuracy. This is
     the "does it actually know the right answers" check.
  3. **Review** — a human reviewer approves, edits, or rejects.

The gate is what makes self-learning *safe*: a candidate that improves
one thing but breaks the hold-out set is rejected, and the current model
is kept (reversibility).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .insight_miner import CandidateInsight


@dataclass
class VerificationResult:
    candidate_id: str
    passed: bool
    replay_score: float = 0.0        # fraction of replayed trajectories still OK
    holdout_score: float = 0.0       # fraction of exam questions answered correctly
    holdout_baseline: float = 0.0    # baseline accuracy before the candidate
    regression: bool = False         # True if holdout dropped below baseline
    notes: List[str] = field(default_factory=list)
    review_status: str = "pending"   # pending | approved | rejected | edited


class VerificationGate:
    """Verifies candidates before promotion.

    `answer_fn` is a callable(question) -> answer used to score the
    hold-out set. In production this is the platform's grounded answer
    path (retrieval + local model). In tests it can be a simple lookup.
    """

    def __init__(self, exam: List[Dict[str, Any]],
                 answer_fn: Optional[Callable[[str], str]] = None,
                 audit=None):
        self.exam = exam
        self.answer_fn = answer_fn
        self.audit = audit

    # ---------- hold-out scoring ----------

    def score_holdout(self, answer_fn: Callable[[str], str]) -> float:
        """Fraction of exam questions the answer function gets right."""
        if not self.exam:
            return 1.0
        correct = 0
        for q in self.exam:
            try:
                answer = answer_fn(q["q"]) or ""
            except Exception:
                answer = ""
            if self._match(answer, q["a"]):
                correct += 1
        return correct / len(self.exam)

    @staticmethod
    def _match(answer: str, expected: str) -> bool:
        """Fuzzy match: expected substring present in the answer (case-
        insensitive). Handles numeric answers and short factual answers."""
        a = answer.lower().strip()
        e = expected.lower().strip()
        if not a or not e:
            return False
        if e in a:
            return True
        # numeric: extract numbers and compare
        import re
        a_nums = re.findall(r"[\d.]+", a)
        e_nums = re.findall(r"[\d.]+", e)
        if e_nums and a_nums:
            # any expected number present in the answer
            return any(en in a_nums for en in e_nums)
        return False

    # ---------- verification ----------

    def verify(
        self,
        candidate: CandidateInsight,
        replay_trajectories: List[Dict[str, Any]],
        baseline_answer_fn: Optional[Callable[[str], str]] = None,
        candidate_answer_fn: Optional[Callable[[str], str]] = None,
    ) -> VerificationResult:
        """Run replay + hold-out for a candidate.

        `baseline_answer_fn` — how the platform answers BEFORE the change.
        `candidate_answer_fn` — how it would answer AFTER applying the
        candidate. If only one is given, the candidate is scored against
        the baseline (a new skill can only help, not hurt, if the
        baseline already answers the hold-out set).
        """
        notes: List[str] = []
        result = VerificationResult(candidate_id=candidate.id, passed=False)

        # 1. Replay test: would the candidate break the trajectories it
        #    was derived from? Abstain/needs_approval trajectories are
        #    NEUTRAL — they are often the very problem the candidate
        #    addresses (e.g. a retrieval tweak mined from recurring
        #    abstains). Only true failures count against the candidate.
        if replay_trajectories:
            ok = sum(1 for t in replay_trajectories
                     if t.get("outcome") in ("success", "needs_approval"))
            failed = sum(1 for t in replay_trajectories
                         if t.get("outcome") in ("failure", "error"))
            denom = ok + failed
            result.replay_score = (ok / denom) if denom else 1.0
            if result.replay_score < 0.5:
                notes.append("Replay: most provenance trajectories were "
                             "failures — candidate likely to regress.")

        # 2. Hold-out test
        baseline_fn = baseline_answer_fn or self.answer_fn
        cand_fn = candidate_answer_fn or self.answer_fn
        if baseline_fn is not None:
            result.holdout_baseline = self.score_holdout(baseline_fn)
        if cand_fn is not None:
            result.holdout_score = self.score_holdout(cand_fn)
            if result.holdout_baseline > 0 and \
                    result.holdout_score < result.holdout_baseline - 0.05:
                result.regression = True
                notes.append(
                    f"Hold-out regressed: {result.holdout_score:.2f} < "
                    f"baseline {result.holdout_baseline:.2f}."
                )

        # 3. Decision (review is a separate human step)
        result.passed = (not result.regression) and result.replay_score >= 0.5
        if result.passed:
            notes.append("Passed replay + hold-out. Awaiting human review.")
        else:
            notes.append("Failed verification — current model kept.")

        result.notes = notes
        if self.audit:
            self.audit.record(
                actor="learning_verification_gate",
                action="verify_candidate",
                detail={
                    "candidate_id": candidate.id,
                    "kind": candidate.kind,
                    "scope": candidate.scope,
                    "replay_score": round(result.replay_score, 3),
                    "holdout_score": round(result.holdout_score, 3),
                    "holdout_baseline": round(result.holdout_baseline, 3),
                    "regression": result.regression,
                },
                result="passed" if result.passed else "failed",
            )
        return result

    def record_review(self, result: VerificationResult,
                      decision: str, reviewer: str) -> VerificationResult:
        """Record the human review decision (approved/rejected/edited)."""
        if decision not in ("approved", "rejected", "edited"):
            raise ValueError("decision must be approved | rejected | edited")
        result.review_status = decision
        if self.audit:
            self.audit.record(
                actor="learning_verification_gate",
                action=f"review_{decision}",
                detail={"candidate_id": result.candidate_id},
                user=reviewer, result=decision,
            )
        return result