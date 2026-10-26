"""Configuration loading for the platform.

Reads config/settings.yaml (or a path passed in) into a typed
Settings object. Paths in the config are resolved relative to the
project root (the directory containing config/).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a hard dependency
    raise ImportError("PyYAML is required: pip install pyyaml")


@dataclass
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    default_model: str = "llama3.1:8b"
    request_timeout_seconds: int = 300
    max_retries: int = 2
    model_overrides: Dict[str, str] = field(default_factory=dict)
    temperature: float = 0.2
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768


@dataclass
class StorageConfig:
    data_dir: str = "data"
    database: str = "data/knowledge.db"
    documents_dir: str = "data/documents"
    audit_log: str = "data/audit_log.jsonl"
    build_docs_dir: str = "data/build_docs"


@dataclass
class RetrievalConfig:
    top_k: int = 6
    keyword_weight: float = 0.4
    vector_weight: float = 0.6
    min_score: float = 0.25


@dataclass
class UserConfig:
    username: str
    role: str


@dataclass
class PolicyConfig:
    users: List[UserConfig] = field(default_factory=list)
    approver_roles: List[str] = field(default_factory=lambda: ["admin", "reviewer"])
    voice_roles: List[str] = field(default_factory=lambda: ["admin", "reviewer"])
    sensitivity_levels: List[str] = field(
        default_factory=lambda: ["public", "internal", "confidential", "restricted"]
    )
    permitted_external_sources: List[str] = field(default_factory=list)


@dataclass
class VoiceConfig:
    consent_required: bool = True
    calling_hours: Dict[str, str] = field(
        default_factory=lambda: {"start": "09:00", "end": "18:00", "timezone": "Asia/Calcutta"}
    )
    identity_check_required: bool = True
    acknowledgement_required: bool = True
    provider: str = "simulated"


@dataclass
class ExternalConfig:
    fetcher: str = "cache"  # cache | live


@dataclass
class LearningConfig:
    enabled: bool = True
    budget_per_run: int = 10
    min_accuracy: float = 0.6
    exam_path: str = "data/dataset/exam.json"
    # When True, verified candidates are queued for an explicit human
    # review (scheduler.review) instead of being auto-promoted.
    require_human_review: bool = False


@dataclass
class Settings:
    platform_name: str = "Local-First Agent Ecosystem"
    phase: int = 1
    description: str = ""
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    agents_enabled: Dict[str, bool] = field(default_factory=dict)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    external: ExternalConfig = field(default_factory=ExternalConfig)
    learning: LearningConfig = field(default_factory=LearningConfig)
    orchestrator_max_hops: int = 8
    orchestrator_allow_parallel: bool = False
    project_root: str = "."

    def is_agent_enabled(self, agent_id: str) -> bool:
        return self.agents_enabled.get(agent_id, True)

    def resolve_path(self, path: str) -> str:
        """Resolve a possibly-relative path against the project root."""
        if os.path.isabs(path):
            return path
        return os.path.join(self.project_root, path)

    def ensure_storage_dirs(self) -> None:
        for p in (
            self.storage.data_dir,
            self.storage.documents_dir,
            self.storage.build_docs_dir,
        ):
            full = self.resolve_path(p)
            os.makedirs(full, exist_ok=True)


def _build(data: Dict[str, Any], project_root: str) -> Settings:
    o = data.get("ollama", {}) or {}
    s = data.get("storage", {}) or {}
    r = data.get("retrieval", {}) or {}
    p = data.get("policy", {}) or {}
    a = data.get("agents", {}) or {}
    v = (a.get("voice") or {})
    ext = (a.get("external") or {})
    learn = data.get("learning", {}) or {}
    orch = data.get("orchestrator", {}) or {}
    plat = data.get("platform", {}) or {}

    users = [UserConfig(username=u["username"], role=u.get("role", "analyst"))
             for u in p.get("users", []) or []]

    return Settings(
        platform_name=plat.get("name", "Local-First Agent Ecosystem"),
        phase=int(plat.get("phase", 1)),
        description=plat.get("description", ""),
        ollama=OllamaConfig(
            base_url=o.get("base_url", "http://127.0.0.1:11434"),
            default_model=o.get("default_model", "llama3.1:8b"),
            request_timeout_seconds=int(o.get("request_timeout_seconds", 300)),
            max_retries=int(o.get("max_retries", 2)),
            model_overrides=dict(o.get("model_overrides", {}) or {}),
            temperature=float(o.get("temperature", 0.2)),
            embedding_model=o.get("embedding_model", "nomic-embed-text"),
            embedding_dim=int(o.get("embedding_dim", 768)),
        ),
        storage=StorageConfig(
            data_dir=s.get("data_dir", "data"),
            database=s.get("database", "data/knowledge.db"),
            documents_dir=s.get("documents_dir", "data/documents"),
            audit_log=s.get("audit_log", "data/audit_log.jsonl"),
            build_docs_dir=s.get("build_docs_dir", "data/build_docs"),
        ),
        retrieval=RetrievalConfig(
            top_k=int(r.get("top_k", 6)),
            keyword_weight=float(r.get("keyword_weight", 0.4)),
            vector_weight=float(r.get("vector_weight", 0.6)),
            min_score=float(r.get("min_score", 0.25)),
        ),
        policy=PolicyConfig(
            users=users,
            approver_roles=list(p.get("approver_roles", ["admin", "reviewer"])),
            voice_roles=list(p.get("voice_roles", ["admin", "reviewer"])),
            sensitivity_levels=list(
                p.get("sensitivity_levels", ["public", "internal", "confidential", "restricted"])
            ),
            permitted_external_sources=list(p.get("permitted_external_sources", [])),
        ),
        agents_enabled={k: bool(v) for k, v in (a.get("enabled", {}) or {}).items()},
        voice=VoiceConfig(
            consent_required=bool(v.get("consent_required", True)),
            calling_hours=dict(v.get("calling_hours", {"start": "09:00", "end": "18:00"})),
            identity_check_required=bool(v.get("identity_check_required", True)),
            acknowledgement_required=bool(v.get("acknowledgement_required", True)),
            provider=v.get("provider", "simulated"),
        ),
        external=ExternalConfig(fetcher=ext.get("fetcher", "cache")),
        learning=LearningConfig(
            enabled=bool(learn.get("enabled", True)),
            budget_per_run=int(learn.get("budget_per_run", 10)),
            min_accuracy=float(learn.get("min_accuracy", 0.6)),
            exam_path=learn.get("exam_path", "data/dataset/exam.json"),
            require_human_review=bool(learn.get("require_human_review", False)),
        ),
        orchestrator_max_hops=int(orch.get("max_hops", 8)),
        orchestrator_allow_parallel=bool(orch.get("allow_parallel", False)),
        project_root=project_root,
    )


def load_settings(config_path: Optional[str] = None) -> Settings:
    """Load settings from YAML.

    If config_path is None, look for config/settings.yaml relative to
    the current working directory, then relative to this package's
    project root.
    """
    candidates = []
    if config_path:
        candidates.append(config_path)
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(here))
        candidates.append(os.path.join(os.getcwd(), "config", "settings.yaml"))
        candidates.append(os.path.join(project_root, "config", "settings.yaml"))

    for cand in candidates:
        if os.path.isfile(cand):
            with open(cand, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(cand)))
            return _build(data, project_root)

    raise FileNotFoundError(
        "settings.yaml not found. Pass config_path explicitly or run from the project root."
    )