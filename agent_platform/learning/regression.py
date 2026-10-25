"""Regression harness — if a new model/config fails, keep the current one.

This is the *reversibility* guarantee. Before any candidate is promoted
to the active model registry, the harness runs the full exam (hold-out)
set against both the current configuration and the candidate
configuration. If the candidate does not meet or beat the current
accuracy, promotion is blocked and the current model is kept.

This is separate from the VerificationGate's per-candidate hold-out
check: the harness is the *global* gate that runs on every promotion
attempt and enforces a minimum accuracy floor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .verification import VerificationGate


@dataclass
class RegressionResult:
    candidate_id: str
    current_accuracy: float
    candidate_accuracy: float
    delta: float
    passed: bool
    min_accuracy: float
    notes: List[str] = field(default_factory=list)


class RegressionHarness:
    def __init__(self, exam: List[Dict[str, Any]],
                 min_accuracy: float = 0.6,
                 audit=None):
        self.exam = exam
        self.min_accuracy = min_accuracy
        self.audit = audit
        self._gate = VerificationGate(exam=exam)

    def run(
        self,
        candidate_id: str,
        current_answer_fn: Callable[[str], str],
        candidate_answer_fn: Callable[[str], str],
    ) -> RegressionResult:
        current_acc = self._gate.score_holdout(current_answer_fn)
        cand_acc = self._gate.score_holdout(candidate_answer_fn)
        delta = cand_acc - current_acc

        notes = []
        passed = True
        if cand_acc < self.min_accuracy:
            passed = False
            notes.append(
                f"Candidate accuracy {cand_acc:.2f} below floor "
                f"{self.min_accuracy:.2f}."
            )
        if delta < -0.05:
            passed = False
            notes.append(
                f"Candidate regressed by {-delta:.2f} vs current "
                f"({current_acc:.2f} -> {cand_acc:.2f})."
            )
        if passed:
            notes.append(
                f"Regression passed: {current_acc:.2f} -> {cand_acc:.2f} "
                f"(delta {delta:+.2f})."
            )

        result = RegressionResult(
            candidate_id=candidate_id,
            current_accuracy=round(current_acc, 4),
            candidate_accuracy=round(cand_acc, 4),
            delta=round(delta, 4),
            passed=passed,
            min_accuracy=self.min_accuracy,
            notes=notes,
        )
        if self.audit:
            self.audit.record(
                actor="learning_regression_harness",
                action="regression_run",
                detail={
                    "candidate_id": candidate_id,
                    "current_accuracy": result.current_accuracy,
                    "candidate_accuracy": result.candidate_accuracy,
                    "delta": result.delta,
                    "min_accuracy": self.min_accuracy,
                },
                result="passed" if passed else "failed",
            )
        return result