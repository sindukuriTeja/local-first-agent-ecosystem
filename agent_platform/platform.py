"""Platform factory: wires all core services + 16 agents into one object.

This is the single entry point for using the platform programmatically:

    from agent_platform.platform import create_platform
    platform = create_platform()
    result = platform.handle_request("admin", "What is the status of matter X?")
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .agents.registry import build_agents
from .core.approval import ApprovalGate
from .core.audit import AuditLog
from .core.base_agent import AgentContext, AgentResult, BaseAgent, PlatformServices
from .core.config import Settings, load_settings
from .core.knowledge import KnowledgeStore
from .core.memory import MemorySystem
from .core.ollama import OllamaClient, ModelRegistry
from .core.policy import Identity, PolicyEngine


@dataclass
class Platform:
    settings: Settings
    services: PlatformServices
    agents: Dict[str, BaseAgent]
    audit: AuditLog

    def __post_init__(self):
        # convenience
        self.knowledge = self.services.knowledge
        self.policy = self.services.policy
        self.approval = self.services.approval

    # ---------- identity ----------

    def identify(self, username: str, tenant: str = "default") -> Optional[Identity]:
        return self.policy.identify(username, tenant)

    # ---------- main entry ----------

    def handle_request(
        self,
        username: str,
        request: str,
        tenant: str = "default",
        state: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Route a user request through the Orchestrator (Agent 1)."""
        identity = self.identify(username, tenant)
        if identity is None:
            self.audit.record(
                actor="platform", action="unknown_user",
                detail={"username": username}, result="denied",
            )
            return AgentResult(
                agent_id="platform", status="error",
                error=f"Unknown user '{username}'. Add them to config policy.users.",
            )

        task_id = uuid.uuid4().hex[:12]
        ctx = AgentContext(
            task_id=task_id,
            identity=identity,
            request=request,
            state=state or {},
        )
        # Start working memory for this task
        self.services.memory.start_task(task_id, {"request": request, "user": username})

        orchestrator = self.agents["agent_1_orchestrator"]
        result = orchestrator.handle(ctx)

        # Record which agents ran (for Agent 9 build documentation)
        ctx.state["agents_run"] = [s["agent"] for s in result.data.get("steps", [])]
        ctx.state["intent"] = result.data.get("intent")

        # Clear working memory when the task completes
        self.services.memory.clear_task(task_id)
        return result

    # ---------- direct agent access (advanced) ----------

    def run_agent(
        self,
        agent_id: str,
        username: str,
        request: str,
        tenant: str = "default",
        state: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Run a single specialist agent directly (bypasses the orchestrator)."""
        identity = self.identify(username, tenant)
        if identity is None:
            return AgentResult(agent_id, "error",
                               error=f"Unknown user '{username}'.")
        agent = self.agents.get(agent_id)
        if agent is None:
            return AgentResult(agent_id, "error",
                               error=f"Unknown agent '{agent_id}'.")
        task_id = uuid.uuid4().hex[:12]
        ctx = AgentContext(task_id=task_id, identity=identity,
                           request=request, state=state or {})
        self.services.memory.start_task(task_id, {"request": request})
        result = agent.handle(ctx)
        self.services.memory.clear_task(task_id)
        return result

    # ---------- governance helpers ----------

    def pending_approvals(self, kind: Optional[str] = None) -> List[Any]:
        return self.approval.pending(kind)

    def decide_approval(self, approval_id: str, decision: str,
                        decided_by: str, note: str = "",
                        corrected_payload: Optional[Dict[str, Any]] = None):
        identity = self.identify(decided_by)
        if identity is None:
            raise PermissionError(f"Unknown user '{decided_by}'.")
        if not self.policy.can_approve(identity):
            raise PermissionError(
                f"Role '{identity.role}' is not an approver."
            )
        return self.approval.decide(approval_id, decision, decided_by, note,
                                    corrected_payload)

    def audit_query(self, actor: Optional[str] = None,
                    action: Optional[str] = None,
                    user: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        return self.audit.query(actor=actor, action=action, user=user, limit=limit)

    def close(self):
        self.knowledge.close()


def create_platform(config_path: Optional[str] = None,
                    ollama_client=None) -> Platform:
    """Build the full platform.

    Args:
        config_path: path to settings.yaml (defaults to config/settings.yaml).
        ollama_client: inject a custom OllamaClient (e.g. MockOllamaClient
            for tests). If None, a real client is created from settings.
    """
    settings = load_settings(config_path)
    settings.ensure_storage_dirs()

    audit_path = settings.resolve_path(settings.storage.audit_log)
    audit = AuditLog(audit_path)

    db_path = settings.resolve_path(settings.storage.database)
    if ollama_client is None:
        ollama = OllamaClient(
            base_url=settings.ollama.base_url,
            timeout=settings.ollama.request_timeout_seconds,
            max_retries=settings.ollama.max_retries,
        )
    else:
        ollama = ollama_client

    # Embedder: use the local embedding model if available, else None
    # (keyword-only retrieval). The embedder is lazy so a missing model
    # does not break startup.
    embedder = _make_embedder(ollama, settings)

    knowledge = KnowledgeStore(db_path,
                               embedding_dim=settings.ollama.embedding_dim,
                               embedder=embedder)

    memory_dir = settings.resolve_path(
        os.path.join(settings.storage.data_dir, "memory")
    )
    memory = MemorySystem(memory_dir)

    policy = PolicyEngine(settings)

    approval_path = settings.resolve_path(
        os.path.join(settings.storage.data_dir, "approvals.jsonl")
    )
    approval = ApprovalGate(approval_path, audit)

    registry = ModelRegistry(
        default_model=settings.ollama.default_model,
        temperature=settings.ollama.temperature,
        overrides=settings.ollama.model_overrides,
    )

    services = PlatformServices(
        settings=settings,
        knowledge=knowledge,
        memory=memory,
        audit=audit,
        policy=policy,
        approval=approval,
        ollama=ollama,
        registry=registry,
    )

    agents = build_agents(services)

    return Platform(settings=settings, services=services, agents=agents, audit=audit)


def _make_embedder(ollama, settings):
    """Return a callable embedder or None.

    Uses the local embedding model. If the model is not pulled yet, the
    first call will fail gracefully and we fall back to keyword-only
    retrieval (embedder=None) so the platform still works.
    """
    model = settings.ollama.embedding_model

    def embed(text: str):
        try:
            return ollama.embed_one(text, model)
        except Exception:
            return None

    # Probe once; if it fails, disable vector retrieval for this session.
    try:
        probe = ollama.embed_one("probe", model)
        if probe:
            return embed
    except Exception:
        pass
    return None