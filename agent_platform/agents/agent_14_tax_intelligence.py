"""Agent 14 — Tax Intelligence Agent.

From the architecture:
  Notices • demands • due dates • appeals • payments • pre-deposits

Tracks tax notices, demands, due dates, appeals, payments, and
pre-deposits. Feeds deadline/risk items to the Compliance & Risk Agent
(#8).
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class TaxIntelligenceAgent(BaseAgent):
    agent_id = "agent_14_tax_intelligence"
    name = "Tax Intelligence Agent"
    responsibility = (
        "Track notices, demands, due dates, appeals, payments, and "
        "pre-deposits. Feed deadline/risk items to Compliance & Risk."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        evidence = self._format_evidence(results)

        system = self.system_prompt(
            "Produce a tax intelligence summary. Respond with ONLY a JSON "
            "object: {\"notices\": [{\"notice\": str, \"date\": str, "
            "\"status\": str, \"source\": str}], \"demands\": [{\"demand\": "
            "str, \"amount\": str, \"status\": str, \"source\": str}], "
            "\"due_dates\": [{\"item\": str, \"due_date\": str, \"source\": "
            "str}], \"appeals\": [{\"appeal\": str, \"status\": str, "
            "\"source\": str}], \"payments\": [{\"payment\": str, "
            "\"amount\": str, \"date\": str, \"source\": str}], "
            "\"pre_deposits\": [{\"item\": str, \"amount\": str, "
            "\"status\": str, \"source\": str}], \"summary\": str}. "
            "Ground every item in the evidence; never invent amounts, "
            "notices, or dates."
        )
        user = (
            f"Tax request: {ctx.request}\n\n"
            f"Evidence:\n{evidence or '(none)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed:
            return AgentResult(self.agent_id, "error",
                               error="tax model returned no JSON")

        due_dates = parsed.get("due_dates", []) or []
        demands = parsed.get("demands", []) or []
        # Feed deadline/risk to Compliance & Risk (#8)
        compliance_inputs = []
        for d in due_dates:
            compliance_inputs.append({"item": d.get("item", ""),
                                      "due_date": d.get("due_date", ""),
                                      "type": "tax", "source": d.get("source", "")})
        for dm in demands:
            compliance_inputs.append({"item": f"Tax demand: {dm.get('demand', '')}",
                                      "due_date": dm.get("status", ""),
                                      "type": "tax_demand",
                                      "source": dm.get("source", "")})
        if compliance_inputs:
            ctx.state.setdefault("compliance_inputs", []).extend(compliance_inputs)
            ctx.state["route_to_compliance"] = True
            self._audit(ctx, "feed_deadline_risk_to_compliance",
                        detail={"count": len(compliance_inputs)},
                        result="routed_to_agent_8")

        self.knowledge.add_document(
            title=f"Tax intelligence: {ctx.request[:80]}",
            content=self._to_text(parsed),
            source="tax_intelligence_agent",
            doc_type="tax",
            sensitivity="restricted",
            tenant=ctx.identity.tenant,
            metadata={"due_dates": due_dates},
        )

        return AgentResult(
            self.agent_id, "ok",
            answer=self._to_text(parsed),
            data={
                "notices": parsed.get("notices", []),
                "demands": demands,
                "due_dates": due_dates,
                "appeals": parsed.get("appeals", []),
                "payments": parsed.get("payments", []),
                "pre_deposits": parsed.get("pre_deposits", []),
                "route_to_compliance": bool(compliance_inputs),
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
        lines = ["# Tax Intelligence", "", f"**Summary:** {parsed.get('summary', '')}", ""]
        for section, key in [("Notices", "notices"), ("Demands", "demands"),
                             ("Due Dates", "due_dates"), ("Appeals", "appeals"),
                             ("Payments", "payments"), ("Pre-deposits", "pre_deposits")]:
            lines.append(f"## {section}")
            items = parsed.get(key, []) or []
            if not items:
                lines.append("- (none)")
            for it in items:
                lines.append(f"- {it}")
            lines.append("")
        return "\n".join(lines)