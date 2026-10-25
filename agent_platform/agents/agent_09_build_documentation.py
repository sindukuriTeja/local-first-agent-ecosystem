"""Agent 9 — Build Documentation Agent.

From the architecture:
  Build activity • prompt/config • version history • change log

Observes build activity (dotted line from the Orchestrator — it watches,
it does not control). Maintains a version history and change log of
prompts, configs, and approved versions. Feeds approved versions /
reviewer changes back to the human reviewer.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class BuildDocumentationAgent(BaseAgent):
    agent_id = "agent_9_build_documentation"
    name = "Build Documentation Agent"
    responsibility = (
        "Observe build activity; maintain prompt/config version history and "
        "change log; feed approved versions and reviewer changes back to the "
        "human reviewer."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        build_dir = self.settings.resolve_path(self.settings.storage.build_docs_dir)
        os.makedirs(build_dir, exist_ok=True)
        change_log = os.path.join(build_dir, "change_log.jsonl")
        version_history = os.path.join(build_dir, "version_history.json")

        # Capture the current build activity from context state
        activity = {
            "task_id": ctx.task_id,
            "user": ctx.identity.username,
            "request": ctx.request,
            "intent": ctx.state.get("intent"),
            "agents_run": ctx.state.get("agents_run", []),
            "approvals": ctx.state.get("approvals", []),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        # Append to change log
        with open(change_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(activity, ensure_ascii=False) + "\n")

        # Bump version history
        version = 1
        if os.path.isfile(version_history):
            try:
                with open(version_history, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                version = int(hist.get("version", 0)) + 1
            except (json.JSONDecodeError, ValueError):
                version = 1
        hist = {
            "version": version,
            "updated_at": activity["recorded_at"],
            "change_log_entries": self._count_lines(change_log),
            "last_activity": activity,
        }
        with open(version_history, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)

        self._audit(ctx, "build_documentation_recorded",
                    detail={"version": version, "change_log": change_log},
                    result="recorded")

        return AgentResult(
            self.agent_id, "ok",
            answer=(
                f"Build activity recorded (version {version}). Change log and "
                f"version history updated. Approved versions and reviewer "
                f"changes are available to the human reviewer."
            ),
            data={
                "version": version,
                "change_log": change_log,
                "version_history": version_history,
                "activity": activity,
            },
            sources=ctx.sources,
        )

    @staticmethod
    def _count_lines(path: str) -> int:
        if not os.path.isfile(path):
            return 0
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)