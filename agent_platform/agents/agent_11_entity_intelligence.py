"""Agent 11 — Entity & Company Intelligence Agent.

From the architecture:
  Company profiles • group structure • directors • shareholding

Builds and maintains company/entity profiles: group structure, directors,
and shareholding. Uses the knowledge-graph tables (entities + relations)
for structured relationships and the document store for narrative
profiles.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class EntityCompanyIntelligenceAgent(BaseAgent):
    agent_id = "agent_11_entity_company_intelligence"
    name = "Entity & Company Intelligence Agent"
    responsibility = (
        "Maintain company profiles, group structure, directors, and "
        "shareholding. Use the knowledge graph for structured relationships."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        # Retrieve narrative knowledge
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        evidence = self._format_evidence(results)

        # Also pull structured entity data
        entity_name = ctx.state.get("entity_name") or self._guess_entity(ctx.request)
        entities = self.knowledge.entities(tenant=ctx.identity.tenant) if entity_name else []

        system = self.system_prompt(
            "Produce an entity/company intelligence profile. Respond with "
            "ONLY a JSON object: {\"entity\": str, \"profile\": str, "
            "\"group_structure\": [{\"entity\": str, \"relation\": str, "
            "\"parent\": str}], \"directors\": [str], \"shareholding\": "
            "[{\"holder\": str, \"percentage\": str, \"source\": str}], "
            "\"sources\": [str]}. Ground every item in the provided "
            "evidence or structured entity data. Never invent directors, "
            "percentages, or relationships."
        )
        user = (
            f"Entity/company request: {ctx.request}\n\n"
            f"Target entity (if identifiable): {entity_name or '(unknown)'}\n\n"
            f"Structured entity records:\n{self._dump(entities[:20])}\n\n"
            f"Narrative evidence:\n{evidence or '(none)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed or "entity" not in parsed:
            return AgentResult(self.agent_id, "error",
                               error="entity intelligence model returned no JSON")

        # Persist structured relationships into the knowledge graph
        entity_id = None
        if parsed.get("entity"):
            entity_id = self.knowledge.add_entity(
                name=parsed["entity"], kind="company",
                tenant=ctx.identity.tenant,
                metadata={"profile": parsed.get("profile", "")[:500]},
            )
            for rel in parsed.get("group_structure", []) or []:
                target = rel.get("parent") or rel.get("entity")
                if target:
                    self.knowledge.add_relation(
                        source_entity=entity_id,
                        relation=rel.get("relation", "related_to"),
                        target_entity=target,
                        metadata={"source": ctx.sources},
                    )
            for sh in parsed.get("shareholding", []) or []:
                self.knowledge.add_fact(
                    subject=parsed["entity"],
                    predicate="shareholding",
                    object_=f"{sh.get('holder', '')}: {sh.get('percentage', '')}",
                    source_doc=sh.get("source", ""),
                    sensitivity="confidential",
                    tenant=ctx.identity.tenant,
                )

        sources = parsed.get("sources", []) or []
        for s in sources:
            ctx.add_source(s)

        # Save narrative profile
        self.knowledge.add_document(
            title=f"Entity profile: {parsed.get('entity', 'unknown')}",
            content=self._to_text(parsed),
            source="entity_company_intelligence_agent",
            doc_type="entity_profile",
            sensitivity="confidential",
            tenant=ctx.identity.tenant,
            metadata={"entity_id": entity_id, "sources": sources},
        )

        return AgentResult(
            self.agent_id, "ok",
            answer=self._to_text(parsed),
            data={
                "entity": parsed.get("entity"),
                "entity_id": entity_id,
                "profile": parsed.get("profile", ""),
                "group_structure": parsed.get("group_structure", []),
                "directors": parsed.get("directors", []),
                "shareholding": parsed.get("shareholding", []),
            },
            sources=ctx.sources,
        )

    @staticmethod
    def _guess_entity(request: str) -> str:
        import re
        m = re.search(r"\b(?:company|entity|firm|corpn?|ltd|llc|pvt|inc)\.?\s+([A-Z][\w&]+)",
                      request, re.I)
        return m.group(0) if m else ""

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
    def _dump(obj: Any) -> str:
        import json
        if not obj:
            return "(none)"
        try:
            return json.dumps(obj, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(obj)

    @staticmethod
    def _to_text(parsed: Dict[str, Any]) -> str:
        lines = [f"# Entity Profile: {parsed.get('entity', 'unknown')}", "",
                 f"**Profile:** {parsed.get('profile', '')}", "", "## Group Structure"]
        for g in parsed.get("group_structure", []):
            lines.append(f"- {g.get('entity', '')} — {g.get('relation', '')} — "
                         f"parent: {g.get('parent', 'n/a')}")
        if not parsed.get("group_structure"):
            lines.append("- (none)")
        lines += ["", "## Directors"]
        lines += [f"- {d}" for d in parsed.get("directors", [])] or ["- (none)"]
        lines += ["", "## Shareholding"]
        for s in parsed.get("shareholding", []):
            lines.append(f"- {s.get('holder', '')}: {s.get('percentage', '')} "
                         f"(source: {s.get('source', 'n/a')})")
        if not parsed.get("shareholding"):
            lines.append("- (none)")
        return "\n".join(lines)