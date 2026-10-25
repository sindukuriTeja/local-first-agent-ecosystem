"""Agent 13 — Land & Title Agent.

From the architecture:
  Parcels • title chain • mortgages • disputes • approvals

Tracks land parcels, title chains, mortgages, disputes, and approvals.
Receives secured-debt items from the Debt & Settlement Agent (#12) and
feeds due dates to the Compliance & Risk Agent (#8).
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class LandTitleAgent(BaseAgent):
    agent_id = "agent_13_land_title"
    name = "Land & Title Agent"
    responsibility = (
        "Track parcels, title chain, mortgages, disputes, and approvals. "
        "Receive secured items from Debt & Settlement; feed due dates to "
        "Compliance & Risk."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        evidence = self._format_evidence(results)

        # Secured items routed from Debt & Settlement (#12)
        secured = ctx.state.get("secured_items", []) or []

        system = self.system_prompt(
            "Produce a land & title status. Respond with ONLY a JSON object: "
            "{\"parcels\": [{\"parcel\": str, \"location\": str, \"area\": "
            "str, \"status\": str, \"source\": str}], \"title_chain\": "
            "[{\"owner\": str, \"date\": str, \"instrument\": str, "
            "\"source\": str}], \"mortgages\": [{\"lender\": str, "
            "\"amount\": str, \"status\": str, \"source\": str}], "
            "\"disputes\": [{\"dispute\": str, \"status\": str, "
            "\"source\": str}], \"approvals\": [{\"item\": str, \"status\": "
            "str, \"source\": str}], \"due_dates\": [{\"item\": str, "
            "\"due_date\": str, \"source\": str}], \"summary\": str}. "
            "Ground every item in the evidence or secured inputs; never "
            "invent parcels, owners, or dates."
        )
        user = (
            f"Land & title request: {ctx.request}\n\n"
            f"Secured items from Debt & Settlement:\n{self._dump(secured)}\n\n"
            f"Evidence:\n{evidence or '(none)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed:
            return AgentResult(self.agent_id, "error",
                               error="land & title model returned no JSON")

        due_dates = parsed.get("due_dates", []) or []
        # Feed due dates to Compliance & Risk (#8)
        if due_dates:
            ctx.state.setdefault("compliance_inputs", []).extend(
                [{"item": d.get("item", ""), "due_date": d.get("due_date", ""),
                  "type": "land_title", "source": d.get("source", "")}
                 for d in due_dates]
            )
            ctx.state["route_to_compliance"] = True
            self._audit(ctx, "feed_due_dates_to_compliance",
                        detail={"count": len(due_dates)},
                        result="routed_to_agent_8")

        self.knowledge.add_document(
            title=f"Land & title: {ctx.request[:80]}",
            content=self._to_text(parsed),
            source="land_title_agent",
            doc_type="land_title",
            sensitivity="confidential",
            tenant=ctx.identity.tenant,
            metadata={"due_dates": due_dates},
        )

        return AgentResult(
            self.agent_id, "ok",
            answer=self._to_text(parsed),
            data={
                "parcels": parsed.get("parcels", []),
                "title_chain": parsed.get("title_chain", []),
                "mortgages": parsed.get("mortgages", []),
                "disputes": parsed.get("disputes", []),
                "approvals": parsed.get("approvals", []),
                "due_dates": due_dates,
                "route_to_compliance": bool(due_dates),
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
        lines = ["# Land & Title", "", f"**Summary:** {parsed.get('summary', '')}", ""]
        for section, key in [("Parcels", "parcels"), ("Title Chain", "title_chain"),
                             ("Mortgages", "mortgages"), ("Disputes", "disputes"),
                             ("Approvals", "approvals"), ("Due Dates", "due_dates")]:
            lines.append(f"## {section}")
            items = parsed.get(key, []) or []
            if not items:
                lines.append("- (none)")
            for it in items:
                lines.append(f"- {it}")
            lines.append("")
        return "\n".join(lines)