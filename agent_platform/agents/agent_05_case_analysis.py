"""Agent 5 — Case Analysis Agent.

From the architecture:
  Facts • timeline • evidence • conflicts • missing information

Analyzes a matter/case from stored knowledge and ingested documents,
producing a structured fact set, a chronological timeline, identified
evidence, detected conflicts, and a list of missing information.
Missing items are routed back to the Internal Information Agent (Agent 2)
for follow-up.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class CaseAnalysisAgent(BaseAgent):
    agent_id = "agent_5_case_analysis"
    name = "Case Analysis Agent"
    responsibility = (
        "Produce facts, timeline, evidence, conflicts, and missing "
        "information for a matter. Route missing items to the Internal "
        "Information Agent."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        # Gather evidence from stored knowledge
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        evidence = self._format_evidence(results)

        system = self.system_prompt(
            "Analyze the matter. Respond with ONLY a JSON object: "
            "{\"facts\": [str], \"timeline\": [{\"date\": str, \"event\": str}], "
            "\"evidence\": [{\"item\": str, \"source\": str}], "
            "\"conflicts\": [str], \"missing_information\": [str]}. "
            "Ground every fact in the provided evidence; cite sources. "
            "If something is not in the evidence, list it under "
            "missing_information rather than inventing it."
        )
        user = (
            f"Matter / request: {ctx.request}\n\n"
            f"Stored-knowledge evidence:\n{evidence or '(no stored evidence found)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed:
            return AgentResult(self.agent_id, "error",
                               error="case analysis model returned no JSON")

        missing: List[str] = parsed.get("missing_information", []) or []
        # Route missing items to the Internal Information Agent
        if missing:
            ctx.state["missing_information"] = missing
            ctx.state["route_to_internal_information"] = True
            self._audit(ctx, "route_missing_information",
                        detail={"missing": missing},
                        result="routed_to_agent_2")

        facts = parsed.get("facts", []) or []
        timeline = parsed.get("timeline", []) or []
        conflicts = parsed.get("conflicts", []) or []
        evidence_items = parsed.get("evidence", []) or []

        # Persist the analysis as a sourced document
        self.knowledge.add_document(
            title=f"Case analysis: {ctx.request[:80]}",
            content=self._to_text(parsed),
            source="case_analysis_agent",
            doc_type="case_analysis",
            sensitivity="confidential",
            tenant=ctx.identity.tenant,
            metadata={"missing_information": missing,
                      "cited_sources": ctx.sources},
        )

        answer = self._to_text(parsed)
        return AgentResult(
            self.agent_id, "ok",
            answer=answer,
            data={
                "facts": facts,
                "timeline": timeline,
                "evidence": evidence_items,
                "conflicts": conflicts,
                "missing_information": missing,
                "route_to_internal_information": bool(missing),
            },
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

    @staticmethod
    def _to_text(parsed: Dict[str, Any]) -> str:
        lines = ["# Case Analysis", ""]
        lines.append("## Facts")
        lines += [f"- {f}" for f in parsed.get("facts", [])] or ["- (none)"]
        lines += ["", "## Timeline"]
        for t in parsed.get("timeline", []):
            lines.append(f"- {t.get('date', 'n/a')}: {t.get('event', '')}")
        if not parsed.get("timeline"):
            lines.append("- (none)")
        lines += ["", "## Evidence"]
        for e in parsed.get("evidence", []):
            lines.append(f"- {e.get('item', '')} (source: {e.get('source', 'n/a')})")
        if not parsed.get("evidence"):
            lines.append("- (none)")
        lines += ["", "## Conflicts"]
        lines += [f"- {c}" for c in parsed.get("conflicts", [])] or ["- (none)"]
        lines += ["", "## Missing Information"]
        lines += [f"- {m}" for m in parsed.get("missing_information", [])] or ["- (none)"]
        return "\n".join(lines)