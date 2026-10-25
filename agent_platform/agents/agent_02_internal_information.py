"""Agent 2 — Internal Information Agent.

The ONLY internal information desk (from the architecture):
  - checks stored knowledge first
  - checks requester access
  - routes internal questions
  - saves sourced answers
  - returns source, date, status

If the answer is not in stored knowledge, it emits a *cleaned* question
(no internal details) that the Orchestrator may hand to Agent 3
(External Information). It never lets raw internal data flow outward.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class InternalInformationAgent(BaseAgent):
    agent_id = "agent_2_internal_information"
    name = "Internal Information Agent"
    responsibility = (
        "Only internal information desk: check stored knowledge first, check "
        "requester access, route internal questions, save sourced answers, "
        "return source/date/status. Emit a cleaned question if info is missing."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        # 1. Check requester access (sensitivity ceiling)
        self._audit(ctx, "check_access",
                    detail={"role": ctx.identity.role,
                            "max_sensitivity": ctx.identity.max_sensitivity},
                    result="access_checked")

        # 2. Check stored knowledge first (hybrid retrieval)
        results = self.grounded_retrieval(ctx, ctx.request, top_k=6)
        self._audit(ctx, "retrieve_internal",
                    detail={"hits": len(results)},
                    result="found" if results else "not_found")

        if not results:
            # Nothing internal — emit a cleaned question for external lookup.
            cleaned = self._clean_question(ctx.request)
            self._audit(ctx, "emit_cleaned_question",
                        detail={"cleaned_question": cleaned},
                        result="missing_internally")
            return AgentResult(
                agent_id=self.agent_id,
                status="ok",
                answer=(
                    "No matching information found in stored internal knowledge. "
                    "A cleaned question has been prepared for external lookup."
                ),
                data={"found": False, "cleaned_question": cleaned},
                sources=ctx.sources,
            )

        # 3. Build a sourced answer from the retrieved records
        evidence = self._format_evidence(results)
        system = self.system_prompt(
            "Answer ONLY from the provided stored-knowledge evidence. Cite each "
            "claim with its source and date. If the evidence does not fully "
            "answer the question, say exactly what is missing."
        )
        user = (
            f"Question: {ctx.request}\n\n"
            f"Stored-knowledge evidence:\n{evidence}\n\n"
            "Answer with sources, dates, and status for each fact."
        )
        answer = self.ask_model(system, user)

        # 4. Save the sourced answer back to stored knowledge
        self.knowledge.add_document(
            title=f"Sourced answer: {ctx.request[:80]}",
            content=answer,
            source="internal_information_agent",
            doc_type="sourced_answer",
            sensitivity=self.policy.effective_sensitivity(
                *[r.record.sensitivity for r in results]
            ),
            tenant=ctx.identity.tenant,
            metadata={"question": ctx.request,
                      "cited_sources": ctx.sources},
        )
        self._audit(ctx, "save_sourced_answer",
                    detail={"cited_sources": ctx.sources},
                    result="saved")

        return AgentResult(
            agent_id=self.agent_id,
            status="ok",
            answer=answer,
            data={
                "found": True,
                "cited_sources": ctx.sources,
                "records": [
                    {"id": r.record.id, "title": r.record.title,
                     "sensitivity": r.record.sensitivity, "score": r.score}
                    for r in results
                ],
            },
            sources=ctx.sources,
        )

    # ---------- helpers ----------

    def _clean_question(self, raw: str) -> str:
        """Produce a sanitized question safe to send to external sources.

        Phase 1 heuristic: strip anything that looks like an internal
        matter id, amount, or name, and rephrase as a generic public
        question. A local model can refine this later.
        """
        import re
        q = raw
        # Remove things that look like internal identifiers / amounts
        q = re.sub(r"\b(?:matter|case|file)[\s_-]*\w{2,}\b", "[reference]", q, flags=re.I)
        q = re.sub(r"[\d,]+(?:\.\d+)?\s*(?:lakh|crore|million|billion|₹|rs\.?|inr)\b",
                   "[amount]", q, flags=re.I)
        return q.strip()

    @staticmethod
    def _format_evidence(results) -> str:
        blocks = []
        for i, r in enumerate(results, 1):
            rec = r.record
            snippet = "\n".join(r.matched_chunks[:2]) or rec.content[:400]
            blocks.append(
                f"[{i}] (source: {rec.source or 'n/a'}, "
                f"updated: {rec.updated_at}, sensitivity: {rec.sensitivity})\n{snippet}"
            )
        return "\n\n".join(blocks)