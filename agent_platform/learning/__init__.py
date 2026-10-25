"""Self-learning engine (L4 in the ecosystem diagram).

Asynchronous, budgeted, reversible. The pipeline:

    Trajectory store  ->  Insight miner  ->  Candidate insights/skills
          (anonymized        (local model       (provenance + scope +
           task traces +      batch analysis)     version)
           outcomes)
                                          |
                                          v
    Model registry  <---  Verification gate  <---  Regression harness
    (promote w/        (replay | hold-out     (if new model fails,
     provenance)         tests | review)        keep current model)

    Memory consolidator (merge, decay, prune, re-embed)
    Retrieval/index reframer (re-cluster, rewrite indexes)
    Learning scheduler / job budget (gates promotion, caps cost)

Every promotion is reversible and provenance-tracked. Nothing self-
modifies silently: candidates go through verification AND regression
before they reach the active model registry, and the evaluation
dashboard gates promotion.
"""

from .trajectory import TrajectoryStore
from .insight_miner import InsightMiner, CandidateInsight
from .verification import VerificationGate, VerificationResult
from .regression import RegressionHarness, RegressionResult
from .consolidator import MemoryConsolidator
from .scheduler import LearningScheduler

__all__ = [
    "TrajectoryStore",
    "InsightMiner", "CandidateInsight",
    "VerificationGate", "VerificationResult",
    "RegressionHarness", "RegressionResult",
    "MemoryConsolidator",
    "LearningScheduler",
]