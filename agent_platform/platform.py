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
from .core.telephony import build_voice_provider
from .learning.answerer import GroundedAnswerer
from .learning.consolidator import MemoryConsolidator
from .learning.insight_miner import InsightMiner
from .learning.regression import RegressionHarness
from .learning.scheduler import LearningScheduler
from .learning.trajectory import TrajectoryStore
from .learning.verification import VerificationGate


@dataclass
class Platform:
    settings: Settings
    services: PlatformServices
    agents: Dict[str, BaseAgent]
    audit: AuditLog
    # Phase 2: self-learning engine components
    trajectory_store: Optional[TrajectoryStore] = None
    learning_scheduler: Optional[LearningScheduler] = None
    exam: List[Dict[str, Any]] = field(default_factory=list)
    # Multi-portal auth (demo users + sessions)
    auth: Optional[Any] = None
    # Real-time collaboration workflow engine (client -> management ->
    # employee -> stakeholders -> response), with a live event bus.
    workflow: Optional[Any] = None

    def __post_init__(self):
        # convenience
        self.knowledge = self.services.knowledge
        self.policy = self.services.policy
        self.approval = self.services.approval

    # ---------- identity ----------

    def identify(self, username: str, tenant: str = "default") -> Optional[Identity]:
        """Resolve a username to an identity.

        Checks the config policy users first, then the multi-portal auth
        directory (so portal demo users like employee1/manager1 work too).
        """
        ident = self.policy.identify(username, tenant)
        if ident is not None:
            return ident
        if self.auth is not None:
            u = self.auth.get_user(username)
            if u is not None and u.enabled:
                return Identity(username=username, role=u.role,
                                tenant=u.tenant or tenant)
        return None

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
        agents_run = [s["agent"] for s in result.data.get("steps", [])]
        ctx.state["agents_run"] = agents_run
        ctx.state["intent"] = result.data.get("intent")

        # Phase 2: capture the task as an anonymized trajectory for the
        # self-learning engine (only if the engine is wired up).
        if self.trajectory_store is not None:
            self.trajectory_store.record(
                task_id=task_id,
                request=request,
                agents_run=agents_run,
                final_status=result.status,
                sources=result.sources,
                user=username,
            )

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

    # ---------- Phase 2: self-learning ----------

    def learn(self) -> Dict[str, Any]:
        """Run one budgeted self-learning pass.

        Mines candidate insights/skills from captured trajectories,
        verifies each (replay + hold-out + review), runs the regression
        harness, and promotes survivors reversibly. Returns the run
        report. No-op (with a clear note) if the engine is not wired.
        """
        if self.learning_scheduler is None:
            return {"error": "learning engine not wired. "
                             "Pass exam/enable learning in create_platform."}
        baseline = GroundedAnswerer(self.services)
        report = self.learning_scheduler.run(baseline_answer_fn=baseline)
        return report.to_dict()

    def learning_dashboard(self) -> Dict[str, Any]:
        if self.learning_scheduler is None:
            return {"error": "learning engine not wired."}
        return self.learning_scheduler.dashboard()

    def review_learning_candidate(self, candidate_id: str, decision: str,
                                  decided_by: str = "reviewer") -> bool:
        """Record a human review decision for a learning candidate that
        passed verification + regression (only used when
        `learning.require_human_review` is enabled). `decision` is
        approved | rejected | edited."""
        if self.learning_scheduler is None:
            raise PermissionError("learning engine not wired.")
        identity = self.identify(decided_by)
        if identity is None:
            raise PermissionError(f"Unknown user '{decided_by}'.")
        if not self.policy.can_approve(identity):
            raise PermissionError(
                f"Role '{identity.role}' is not an approver.")
        return self.learning_scheduler.review(candidate_id, decision,
                                              reviewer=decided_by)

    def seed_dataset(self, dataset_dir: str) -> int:
        """Load a generated dataset (documents.json) into the knowledge
        store. Returns the number of documents added. Idempotent-ish:
        skips documents whose source already exists."""
        import json
        docs_path = os.path.join(dataset_dir, "documents.json")
        if not os.path.isfile(docs_path):
            raise FileNotFoundError(f"No documents.json in {dataset_dir}")
        with open(docs_path, "r", encoding="utf-8") as f:
            docs = json.load(f)
        added = 0
        for d in docs:
            # skip if a doc with the same source already exists
            existing = self.knowledge._conn.execute(
                "SELECT id FROM documents WHERE source = ? LIMIT 1",
                (d.get("source", ""),),
            ).fetchone()
            if existing:
                continue
            self.knowledge.add_document(
                title=d.get("title", "untitled"),
                content=d.get("content", ""),
                source=d.get("source", ""),
                doc_type=d.get("doc_type", "note"),
                sensitivity=d.get("sensitivity", "internal"),
                metadata={k: v for k, v in d.items()
                          if k not in ("title", "content", "source",
                                       "doc_type", "sensitivity")},
            )
            added += 1
        self.audit.record(actor="platform", action="seed_dataset",
                          detail={"dir": dataset_dir, "added": added},
                          result="done")
        return added

    def close(self):
        self.knowledge.close()


def _workflow_ai_runner(platform: "Platform", user: str, prompt: str,
                        state: Dict[str, Any]) -> Dict[str, Any]:
    """Governed AI runner for workflow tasks: routes the prompt through the
    Orchestrator with the workflow's context (subject/matter) injected so the
    agents retrieve the right records. Returns a plain dict for the engine."""
    enriched = prompt
    if state.get("workflow_subject"):
        enriched = (
            f"[Workflow context: subject='{state['workflow_subject']}', "
            f"matter={state.get('matter') or 'n/a'}]\n{prompt}"
        )
    result = platform.handle_request(user, enriched,
                                     state.get("tenant", "default"),
                                     state=dict(state))
    return {
        "agent_id": result.agent_id,
        "status": result.status,
        "answer": result.answer,
        "sources": result.sources,
        "error": result.error,
    }


def create_platform(config_path: Optional[str] = None,
                    ollama_client=None,
                    enable_learning: Optional[bool] = None,
                    dataset_dir: Optional[str] = None,
                    seed: bool = True) -> Platform:
    """Build the full platform.

    Args:
        config_path: path to settings.yaml (defaults to config/settings.yaml).
        ollama_client: inject a custom OllamaClient (e.g. MockOllamaClient
            for tests). If None, a real client is created from settings.
        enable_learning: wire up the Phase 2 self-learning engine.
            Defaults to the `learning.enabled` config value.
        dataset_dir: if given, seed the knowledge store from this dataset
            directory (containing documents.json).
        seed: if True and the knowledge store is empty, auto-generate the
            synthetic demo dataset so the platform is populated out of the
            box (used by the server / Docker). Pass False in tests that
            seed their own data.
    """
    settings = load_settings(config_path or os.environ.get("LFAE_CONFIG") or None)
    # Env override so containers can point at a different Ollama host
    # (e.g. the sibling `ollama` service in docker-compose) without editing
    # settings.yaml.
    if os.environ.get("LFAE_OLLAMA_URL"):
        settings.ollama.base_url = os.environ["LFAE_OLLAMA_URL"]
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

    platform = Platform(settings=settings, services=services,
                        agents=agents, audit=audit)

    # Multi-portal auth (demo users + session store)
    from .core.auth import AuthManager
    auth_path = settings.resolve_path(
        os.path.join(settings.storage.data_dir, "sessions.jsonl")
    )
    platform.auth = AuthManager(auth_path)

    # Real-time collaboration workflow engine.
    from .workflow import WorkflowEngine
    wf_path = settings.resolve_path(
        os.path.join(settings.storage.data_dir, "workflows.jsonl")
    )
    platform.workflow = WorkflowEngine(
        store_path=wf_path,
        audit=audit,
        ai_runner=lambda user, prompt, state: _workflow_ai_runner(
            platform, user, prompt, state),
    )

    # Seed the knowledge store from a dataset if requested.
    if dataset_dir:
        platform.seed_dataset(dataset_dir)

    # Auto-seed the demo dataset so the platform is populated out of the box
    # (server / Docker). Done BEFORE wiring learning so the exam set is
    # available. Skipped when the store already has data or when a custom
    # dataset_dir was supplied, and disabled for tests via seed=False.
    if seed and not dataset_dir:
        try:
            if not platform.knowledge.list_documents(limit=1):
                _auto_seed(platform, settings)
        except Exception:
            pass

    # Phase 2: wire the self-learning engine (default from config).
    if enable_learning is None:
        enable_learning = settings.learning.enabled
    if enable_learning:
        _wire_learning_engine(platform, settings, services, memory,
                              registry, audit)

    return platform


def _auto_seed(platform: Platform, settings: Settings) -> None:
    """Generate the synthetic demo dataset into data/dataset and load it."""
    from scripts.generate_dataset import generate as _gen
    from .portal import seed_demo_content
    data_dir = settings.resolve_path(settings.storage.data_dir)
    out_dir = os.path.join(data_dir, "dataset")
    _gen(out_dir, seed=42)
    platform.seed_dataset(out_dir)
    seed_demo_content(platform)


def _wire_learning_engine(platform: Platform, settings: Settings,
                          services: PlatformServices,
                          memory: MemorySystem, registry: ModelRegistry,
                          audit: AuditLog) -> None:
    """Build the trajectory store, miner, verification gate, regression
    harness, consolidator, and scheduler; attach to the platform."""
    import json as _json
    data_dir = settings.resolve_path(settings.storage.data_dir)

    traj_path = os.path.join(data_dir, "trajectories.jsonl")
    traj_store = TrajectoryStore(traj_path)

    # Exam set: from the configured path (generated dataset) if present.
    exam: List[Dict[str, Any]] = []
    exam_path = settings.resolve_path(settings.learning.exam_path)
    if os.path.isfile(exam_path):
        with open(exam_path, "r", encoding="utf-8") as f:
            exam = _json.load(f)

    miner = InsightMiner(ollama=services.ollama)
    baseline = GroundedAnswerer(services)
    verification = VerificationGate(exam=exam, answer_fn=baseline, audit=audit)
    regression = RegressionHarness(exam=exam,
                                   min_accuracy=settings.learning.min_accuracy,
                                   audit=audit)
    consolidator = MemoryConsolidator(memory, audit=audit)

    state_path = os.path.join(data_dir, "learning_state.json")
    scheduler = LearningScheduler(
        trajectory_store=traj_store,
        miner=miner,
        verification=verification,
        regression=regression,
        consolidator=consolidator,
        registry=registry,
        memory=memory,
        audit=audit,
        budget_per_run=settings.learning.budget_per_run,
        min_accuracy=settings.learning.min_accuracy,
        state_path=state_path,
        require_human_review=settings.learning.require_human_review,
    )

    platform.trajectory_store = traj_store
    platform.learning_scheduler = scheduler
    platform.exam = exam


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