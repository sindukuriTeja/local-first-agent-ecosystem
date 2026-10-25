"""Grounded answerer — the platform's real answer path, used as the
"current model" that the verification gate and regression harness score.

It answers a question the same way the agents do: retrieve from the
local knowledge store (sensitivity-scoped), then ask the local model to
answer from that evidence with citations. This is what makes the
hold-out/regression tests meaningful — they measure the *actual* system,
not a stub.

`candidate_answer_fn` variants can be built by wrapping this with an
extra knowledge injection (e.g. a promoted skill) to measure whether the
candidate actually improves answers.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from ..core.base_agent import BaseAgent, AgentContext, PlatformServices
from ..core.policy import Identity


class GroundedAnswerer:
    def __init__(self, services: PlatformServices,
                 identity: Optional[Identity] = None,
                 extra_context: str = ""):
        self.sv = services
        self.identity = identity or Identity("admin", "admin")
        # extra_context is prepended to evidence (used to simulate a
        # candidate's effect, e.g. an injected learned skill).
        self.extra_context = extra_context

    def __call__(self, question: str) -> str:
        results = self.sv.knowledge.search(
            question,
            tenant=self.identity.tenant,
            sensitivity_max=self.identity.max_sensitivity,
            top_k=self.sv.settings.retrieval.top_k,
            keyword_weight=self.sv.settings.retrieval.keyword_weight,
            vector_weight=self.sv.settings.retrieval.vector_weight,
            min_score=0.0,  # for eval we want the best available evidence
        )
        # Fast path: if the local model is not reachable, skip the (long)
        # chat attempt and score lexically. Without this, an offline
        # Ollama makes each eval question wait out the full client
        # timeout + retries, which would stall a learning run for hours.
        if not self._model_available():
            return self._lexical(question, results)
        return self._answer(question, results)

    def _model_available(self) -> bool:
        try:
            return self.sv.ollama.is_available()
        except Exception:
            return False

    def _answer(self, question: str, results) -> str:
        evidence = self._format(results)
        if self.extra_context:
            evidence = f"Learned context:\n{self.extra_context}\n\n{evidence}"

        system = (
            "Answer the question using ONLY the provided evidence. Be "
            "concise and give the specific fact (number, date, name, or "
            "short phrase). Cite the source. If the evidence does not "
            "contain the answer, say 'UNKNOWN'."
        )
        user = f"Evidence:\n{evidence or '(none)'}\n\nQuestion: {question}"
        try:
            return self.sv.ollama.chat(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                model=self.sv.registry.spec_for("grounded_answerer").name,
                temperature=0.0,
                max_tokens=300,
            )
        except Exception:
            # If the model is unavailable, fall back to a lexical match so
            # the eval loop still functions (and tests stay deterministic).
            return self._lexical(question, results)

    def _lexical(self, question: str, results) -> str:
        """Deterministic fallback: return the best-matching evidence chunk
        text. Used when no model is reachable (tests, offline eval)."""
        if not results:
            return "UNKNOWN"
        best = results[0]
        snippet = best.matched_chunks[0] if best.matched_chunks else best.record.content
        return snippet[:400]

    @staticmethod
    def _format(results) -> str:
        blocks = []
        for i, r in enumerate(results, 1):
            chunk = r.matched_chunks[0] if r.matched_chunks else r.record.content
            blocks.append(f"[{i}] (source: {r.record.source}) {chunk}")
        return "\n\n".join(blocks)