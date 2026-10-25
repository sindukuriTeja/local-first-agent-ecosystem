"""Agent 10 — Query & Support Agent.

From the architecture:
  Answers and summaries with source links

General query and support: answers questions and produces summaries,
always with source links. Grounded in stored knowledge; abstains when
there is no source.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class QuerySupportAgent(BaseAgent):
    agent_id = "agent_10_query_support"
    name = "Query & Support Agent"
    responsibility = (
        "Answer questions and produce summaries with source links. Ground "
        "every answer in stored knowledge; abstain when there is no source."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        if not results:
            self._audit(ctx, "no_sources", result="abstain")
            return AgentResult(
                self.agent_id, "abstain",
                answer="I could not find a sourced answer in stored knowledge. "
                       "No source links are available, so I am abstaining "
                       "rather than guessing.",
                data={"found": False},
            )

        evidence = self._format_evidence(results)
        system = self.system_prompt(
            "Answer the question or produce the summary using ONLY the "
            "provided evidence. Respond with ONLY a JSON object: "
            "{\"answer\": str, \"sources\": [str]}. Cite a source for every "
            "claim. If the evidence is insufficient, say so in the answer."
        )
        user = f"Question / request: {ctx.request}\n\nEvidence:\n{evidence}"
        parsed = self.ask_model_json(system, user)
        if not parsed or "answer" not in parsed:
            return AgentResult(self.agent_id, "error",
                               error="query model returned no usable answer")

        sources = parsed.get("sources", []) or []
        for s in sources:
            ctx.add_source(s)

        return AgentResult(
            self.agent_id, "ok",
            answer=parsed["answer"],
            data={"found": True, "sources": sources},
            sources=ctx.sources,
        )

    @staticmethod
    def _format_evidence(results) -> str:
        blocks = []
        for i, r in enumerate(results, 1):
            rec = r.record
            snippet = "\n".join(r.matched_chunks[:2]) or rec.content[:400]
            blocks.append(f"[{i}] (source: {rec.source or 'n/a'}, "
                          f"updated: {rec.updated_at})\n{snippet}")
        return "\n\n".join(blocks)