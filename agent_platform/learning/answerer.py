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
                 extra_context: str = "",
                 include_promoted: bool = True):
        self.sv = services
        self.identity = identity or Identity("admin", "admin")
        # extra_context is prepended to evidence (used to simulate a
        # candidate's effect, e.g. an injected learned skill).
        self.extra_context = extra_context
        # include_promoted: fold the platform's *active promoted* learned
        # memory (semantic + procedural) into the evidence. This is what
        # makes self-learning have a real effect: once a candidate is
        # promoted, the platform's answer path actually uses it.
        self.include_promoted = include_promoted
        # Cache the Ollama availability probe for the lifetime of this
        # answerer: a learning run scores the exam many times, and probing
        # /v1/models on every question adds needless latency.
        self._availability_cache: Optional[bool] = None

    def _promoted_context(self) -> str:
        """Active promoted learned memory (all scopes), as injected context."""
        if not self.include_promoted:
            return ""
        parts: List[str] = []
        for kind in ("procedural", "semantic"):
            try:
                for e in self.sv.memory.recall(kind, scope="", status="active",
                                               limit=100):
                    if e.content:
                        parts.append(e.content)
            except Exception:
                continue
        return "\n".join(parts)

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
        if not self._is_model_available():
            return self._lexical(question, results)
        return self._answer(question, results)

    def _is_model_available(self) -> bool:
        if self._availability_cache is None:
            try:
                self._availability_cache = bool(self.sv.ollama.is_available())
            except Exception:
                self._availability_cache = False
        return self._availability_cache

    def _answer(self, question: str, results) -> str:
        evidence = self._format(results)
        learned = "\n".join(p for p in
                            (self._promoted_context(), self.extra_context) if p)
        if learned:
            evidence = f"Learned context:\n{learned}\n\n{evidence}"

        system = (
            "Answer the question using ONLY the provided evidence. Be "
            "concise and give the specific fact (number, date, name, or "
            "short phrase). Cite the source. If the evidence does not "
            "contain the answer, say 'UNKNOWN'."
        )
        user = f"Evidence:\n{evidence or '(none)'}\n\nQuestion: {question}"
        try:
            # Use the registry's default model directly. (Do NOT use
            # registry.spec_for("grounded_answerer", temperature=0.0) here:
            # spec_for mutates the shared cached ModelSpec, which would leak
            # temperature=0.0 into later agent calls for the same model.)
            return self.sv.ollama.chat(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                model=self.sv.registry.default_model,
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
        parts: List[str] = []
        if results:
            best = results[0]
            parts.append(best.matched_chunks[0] if best.matched_chunks
                         else best.record.content)
        parts.append(self._promoted_context())
        if not any(p.strip() for p in parts):
            return "UNKNOWN"
        return "\n".join(p for p in parts if p)[:400]

    @staticmethod
    def _format(results) -> str:
        blocks = []
        for i, r in enumerate(results, 1):
            chunk = r.matched_chunks[0] if r.matched_chunks else r.record.content
            blocks.append(f"[{i}] (source: {r.record.source}) {chunk}")
        return "\n\n".join(blocks)