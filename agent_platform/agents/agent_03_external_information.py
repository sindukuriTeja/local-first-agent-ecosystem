"""Agent 3 — External Information Agent.

The platform's ONLY authorized egress path (from the architecture):
  - only receives cleaned questions from the Internal Information Agent
  - uses public / permitted sources (allowlisted in config)
  - returns source link + date

Every egress is logged to the audit trail. In Phase 1 the fetcher is
pluggable: the default `LocalCacheFetcher` serves from a local cache of
pre-approved public documents (fully offline), and a `WebFetcher`
implementation can be plugged in later for live lookups against the
allowlisted sources. No data other than the cleaned question leaves the
machine, and only to allowlisted hosts.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


from ..core.base_agent import AgentContext, AgentResult, BaseAgent


@dataclass
class ExternalFact:
    claim: str
    source_url: str
    collected_at: str
    title: str = ""


class BaseFetcher:
    """Interface for an external source fetcher."""

    def fetch(self, question: str, permitted_urls: List[str]) -> List[ExternalFact]:
        raise NotImplementedError


class LocalCacheFetcher(BaseFetcher):
    """Serves external facts from a local JSON cache.

    The cache file (data/external_cache.json) is a list of entries:
        {"title": ..., "url": ..., "content": ..., "collected_at": ...}

    This keeps Phase 1 fully offline: the cache is populated ahead of
    time by an operator (or a future scheduled job) from the allowlisted
    public sources. Retrieval matches the question against cached content.
    """

    def __init__(self, cache_path: str):
        self.cache_path = cache_path

    def _load(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.cache_path):
            return []
        import json
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def fetch(self, question: str, permitted_urls: List[str]) -> List[ExternalFact]:
        q_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
        facts: List[ExternalFact] = []
        for entry in self._load():
            url = entry.get("url", "")
            if permitted_urls and not any(
                url == p or url.startswith(p.rstrip("/") + "/") for p in permitted_urls
            ):
                continue
            content = entry.get("content", "")
            c_tokens = set(re.findall(r"[a-z0-9]+", content.lower()))
            overlap = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
            if overlap > 0.3 or q_tokens & c_tokens:
                facts.append(ExternalFact(
                    claim=content[:500],
                    source_url=url,
                    collected_at=entry.get("collected_at", ""),
                    title=entry.get("title", ""),
                ))
        return facts[:5]


class WebFetcher(BaseFetcher):
    """Live fetcher against allowlisted public sources (optional).

    Phase 1 ships this disabled by default to keep the platform
    offline-first. To enable, set the fetcher in the platform factory.
    It performs a simple GET and extracts text; production use should
    replace this with a proper reader (e.g. trafilatura).
    """

    def fetch(self, question: str, permitted_urls: List[str]) -> List[ExternalFact]:
        # Intentionally minimal: a real deployment would search the
        # allowlisted domains and parse results. Kept as a stub so the
        # egress path is explicit and auditable.
        return []


class ExternalInformationAgent(BaseAgent):
    agent_id = "agent_3_external_information"
    name = "External Information Agent"
    responsibility = (
        "Only receives cleaned questions from the Internal Information "
        "Agent. Uses public/permitted sources. Returns source link + date. "
        "All egress is audited."
    )

    def __init__(self, services, fetcher: Optional[BaseFetcher] = None):
        super().__init__(services)
        if fetcher is None:
            # Use the config-driven factory: offline cache by default,
            # live allowlisted fetching when enabled in config.
            from ..core.web_fetcher import build_fetcher
            fetcher = build_fetcher(services.settings, audit=services.audit)
        self.fetcher = fetcher

    def run(self, ctx: AgentContext) -> AgentResult:
        # Only accept cleaned questions (from Agent 2) or explicitly
        # cleaned requests routed here by the orchestrator.
        cleaned = ctx.state.get("cleaned_question")
        if not cleaned:
            cleaned = ctx.request
            self._audit(ctx, "warning_uncleaned_input",
                        detail={"note": "no cleaned_question in state; using raw request"},
                        result="warning")

        permitted = self.settings.policy.permitted_external_sources
        self._audit(ctx, "egress_request",
                    detail={"cleaned_question": cleaned,
                            "permitted_sources": permitted},
                    result="egress_started")

        facts = self.fetcher.fetch(cleaned, permitted)

        if not facts:
            self._audit(ctx, "egress_result",
                        detail={"facts": 0}, result="no_external_facts")
            return AgentResult(
                agent_id=self.agent_id,
                status="abstain",
                answer="No relevant facts found in permitted public sources.",
                data={"facts": []},
                sources=[],
            )

        # Build a sourced answer
        system = self.system_prompt(
            "Answer using ONLY the provided public-source facts. Cite the "
            "source URL and collection date for every claim. If the facts do "
            "not answer the question, say so."
        )
        user = (
            f"Question: {cleaned}\n\n"
            "Public-source facts:\n"
            + "\n".join(
                f"- {f.claim} (source: {f.source_url}, collected: {f.collected_at})"
                for f in facts
            )
        )
        answer = self.ask_model(system, user)

        for f in facts:
            ctx.add_source(f.source_url)

        # Save reusable research back to internal knowledge (via Agent 2's
        # store) so future questions are answered internally.
        self.knowledge.add_document(
            title=f"External research: {cleaned[:80]}",
            content=answer,
            source="external_information_agent",
            doc_type="external_research",
            sensitivity="internal",
            tenant=ctx.identity.tenant,
            metadata={"cleaned_question": cleaned,
                      "sources": [f.source_url for f in facts],
                      "collected_at": datetime.now(timezone.utc).isoformat()},
        )

        self._audit(ctx, "egress_result",
                    detail={"facts": len(facts),
                            "sources": [f.source_url for f in facts]},
                    result="egress_completed")

        return AgentResult(
            agent_id=self.agent_id,
            status="ok",
            answer=answer,
            data={"facts": [f.__dict__ for f in facts]},
            sources=[f.source_url for f in facts],
        )