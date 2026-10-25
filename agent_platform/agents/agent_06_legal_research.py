"""Agent 6 — Legal Research Agent.

From the architecture:
  Verified statutes, judgments and source-linked citations

Answers legal questions using stored, verified legal material (statutes,
judgments) from the knowledge base, and — when the internal store is
insufficient — a cleaned question may be routed to the External
Information Agent (Agent 3) to pull from official sources (court sites,
legislative portals). Every citation carries a source link + date.
Reusable research is saved back to stored knowledge.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class LegalResearchAgent(BaseAgent):
    agent_id = "agent_6_legal_research"
    name = "Legal Research Agent"
    responsibility = (
        "Provide verified statutes, judgments, and source-linked citations. "
        "Save reusable research to stored knowledge. Route cleaned questions "
        "to the External Information Agent when internal material is "
        "insufficient."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        # 1. Search stored legal material first
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        internal = [r for r in results
                    if r.record.doc_type in ("statute", "judgment", "legal_note",
                                             "external_research", "sourced_answer")]

        system = self.system_prompt(
            "Answer the legal question using ONLY the provided verified "
            "material. Respond with ONLY a JSON object: "
            "{\"answer\": str, \"citations\": [{\"authority\": str, "
            "\"provision\": str, \"source\": str, \"date\": str}], "
            "\"confidence\": float, \"needs_external\": bool, "
            "\"cleaned_question\": str}. "
            "If the material is insufficient to answer authoritatively, set "
            "needs_external=true and provide a cleaned_question (no internal "
            "identifiers) for external lookup. Never fabricate statutes, "
            "sections, or case citations."
        )
        evidence = self._format_evidence(results)
        user = (
            f"Legal question: {ctx.request}\n\n"
            f"Verified material:\n{evidence or '(no stored legal material found)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed:
            return AgentResult(self.agent_id, "error",
                               error="legal research model returned no JSON")

        citations = parsed.get("citations", []) or []
        needs_external = bool(parsed.get("needs_external", False))
        cleaned = parsed.get("cleaned_question", "") or ctx.request

        # 2. If internal material is insufficient, route a cleaned question
        #    to the External Information Agent.
        if needs_external:
            ctx.state["cleaned_question"] = cleaned
            ctx.state["route_to_external_information"] = True
            self._audit(ctx, "route_to_external",
                        detail={"cleaned_question": cleaned},
                        result="routed_to_agent_3")

        # 3. Save reusable research back to stored knowledge
        self.knowledge.add_document(
            title=f"Legal research: {ctx.request[:80]}",
            content=self._to_text(parsed),
            source="legal_research_agent",
            doc_type="legal_note",
            sensitivity="confidential",
            tenant=ctx.identity.tenant,
            metadata={"citations": citations,
                      "needs_external": needs_external,
                      "cited_sources": ctx.sources},
        )

        return AgentResult(
            self.agent_id, "ok",
            answer=self._to_text(parsed),
            data={
                "answer": parsed.get("answer", ""),
                "citations": citations,
                "confidence": parsed.get("confidence", 0.5),
                "needs_external": needs_external,
                "cleaned_question": cleaned,
                "route_to_external_information": needs_external,
            },
            sources=ctx.sources,
        )

    @staticmethod
    def _format_evidence(results) -> str:
        blocks = []
        for i, r in enumerate(results, 1):
            rec = r.record
            snippet = "\n".join(r.matched_chunks[:2]) or rec.content[:400]
            blocks.append(f"[{i}] (type: {rec.doc_type}, source: {rec.source or 'n/a'}, "
                          f"updated: {rec.updated_at})\n{snippet}")
        return "\n\n".join(blocks)

    @staticmethod
    def _to_text(parsed: Dict[str, Any]) -> str:
        lines = ["# Legal Research", "", f"**Answer:** {parsed.get('answer', '')}", "",
                 "## Citations"]
        for c in parsed.get("citations", []):
            lines.append(f"- {c.get('authority', '')} — {c.get('provision', '')} "
                         f"(source: {c.get('source', 'n/a')}, date: {c.get('date', 'n/a')})")
        if not parsed.get("citations"):
            lines.append("- (none)")
        lines += ["", f"Confidence: {parsed.get('confidence', 'n/a')}"]
        if parsed.get("needs_external"):
            lines.append(f"Needs external lookup. Cleaned question: {parsed.get('cleaned_question', '')}")
        return "\n".join(lines)