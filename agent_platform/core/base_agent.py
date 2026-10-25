"""Base agent + shared context/result types.

Every agent in the platform subclasses BaseAgent. The base class gives
each agent:
  - access to the shared services (knowledge, memory, audit, policy,
    approval, ollama) via a PlatformServices bundle
  - a standard run() contract returning an AgentResult
  - automatic audit logging of every run (who/what/when/result)
  - a helper to build grounded prompts (system + user) and to call the
    local model with JSON mode
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .audit import AuditLog
from .approval import ApprovalGate
from .knowledge import KnowledgeStore
from .memory import MemorySystem
from .ollama import OllamaClient, ModelRegistry, extract_json
from .policy import Identity, PolicyEngine


@dataclass
class PlatformServices:
    """The shared services bundle handed to every agent."""
    settings: Any
    knowledge: KnowledgeStore
    memory: MemorySystem
    audit: AuditLog
    policy: PolicyEngine
    approval: ApprovalGate
    ollama: OllamaClient
    registry: ModelRegistry


@dataclass
class AgentContext:
    """Per-request context passed through the agent graph."""
    task_id: str
    identity: Identity
    request: str
    # Free-form working state shared across agents for this task
    state: Dict[str, Any] = field(default_factory=dict)
    # Accumulated provenance: which docs/sources were used
    sources: List[str] = field(default_factory=list)
    # Hop counter (orchestrator increments)
    hop: int = 0

    def add_source(self, source: str) -> None:
        if source and source not in self.sources:
            self.sources.append(source)


@dataclass
class AgentResult:
    agent_id: str
    status: str                      # ok | needs_approval | error | abstain
    answer: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    approval_id: Optional[str] = None
    error: Optional[str] = None
    latency_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class BaseAgent:
    #: unique id, e.g. "agent_5_case_analysis"
    agent_id: str = "base"
    #: human name, e.g. "Case Analysis Agent"
    name: str = "Base Agent"
    #: one-line responsibility (used in orchestrator routing prompts)
    responsibility: str = ""

    def __init__(self, services: PlatformServices):
        self.sv = services
        self.audit = services.audit
        self.knowledge = services.knowledge
        self.memory = services.memory
        self.policy = services.policy
        self.approval = services.approval
        self.ollama = services.ollama
        self.registry = services.registry
        self.settings = services.settings

    # ---------- helpers ----------

    def model_for(self, temperature: Optional[float] = None) -> str:
        spec = self.registry.spec_for(self.agent_id, temperature=temperature)
        return spec.name

    def ask_model(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        model = self.model_for(temperature)
        return self.ollama.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model,
            temperature=temperature if temperature is not None else self.settings.ollama.temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    def ask_model_json(self, system: str, user: str, **kw: Any) -> Optional[Dict[str, Any]]:
        raw = self.ask_model(system, user, json_mode=True, **kw)
        return extract_json(raw)

    def grounded_retrieval(self, ctx: AgentContext, query: str, top_k: Optional[int] = None):
        """Retrieve from the local knowledge store respecting the caller's
        sensitivity ceiling. Adds matched sources to ctx.sources."""
        top_k = top_k or self.settings.retrieval.top_k
        results = self.knowledge.search(
            query,
            tenant=ctx.identity.tenant,
            sensitivity_max=ctx.identity.max_sensitivity,
            top_k=top_k,
            keyword_weight=self.settings.retrieval.keyword_weight,
            vector_weight=self.settings.retrieval.vector_weight,
            min_score=self.settings.retrieval.min_score,
        )
        for r in results:
            if r.source:
                ctx.add_source(r.source)
        return results

    def _audit(self, ctx: AgentContext, action: str, detail: Optional[Dict[str, Any]] = None,
               result: Optional[str] = None, sources: Optional[List[str]] = None) -> None:
        self.audit.record(
            actor=self.agent_id,
            action=action,
            detail=detail or {},
            sources=sources if sources is not None else ctx.sources,
            result=result,
            user=ctx.identity.username,
        )

    # ---------- contract ----------

    def handle(self, ctx: AgentContext) -> AgentResult:
        """Run the agent on the given context. Subclasses override `run`."""
        t0 = time.time()
        try:
            res = self.run(ctx)
        except Exception as e:  # noqa: BLE001
            res = AgentResult(agent_id=self.agent_id, status="error", error=str(e))
        res.latency_ms = int((time.time() - t0) * 1000)
        self._audit(ctx, "run", detail={"status": res.status}, result=res.status)
        return res

    def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError

    # ---------- prompt scaffolding ----------

    def system_prompt(self, extra: str = "") -> str:
        base = (
            f"You are the {self.name} (id: {self.agent_id}) in a local-first "
            f"legal/compliance agent platform. Your responsibility: {self.responsibility}. "
            f"Rules: (1) Cite sources for every factual claim; if you have no source, "
            f"say so explicitly. (2) Never invent facts, statutes, case numbers, dates, "
            f"or amounts. (3) If the request is outside your responsibility, say "
            f"'OUT_OF_SCOPE' and explain which agent should handle it. "
            f"(4) Keep answers concise and structured. "
            f"(5) All data stays local; do not reference external services unless "
            f"explicitly permitted. " + extra
        )
        return base