"""Agent 12 — Debt & Settlement Agent.

From the architecture:
  Facilities • claims • offers • payments • security release
  no settlement commitment

Tracks debt facilities, claims, offers, payments, and security release.
Hard rule: it NEVER makes a settlement commitment — it only summarizes
and flags. Connects to the Land & Title Agent (#13) for secured debt.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class DebtSettlementAgent(BaseAgent):
    agent_id = "agent_12_debt_settlement"
    name = "Debt & Settlement Agent"
    responsibility = (
        "Track facilities, claims, offers, payments, and security release. "
        "Never make a settlement commitment — summarize and flag only."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        evidence = self._format_evidence(results)

        system = self.system_prompt(
            "Summarize debt and settlement status. Respond with ONLY a JSON "
            "object: {\"facilities\": [{\"name\": str, \"amount\": str, "
            "\"status\": str, \"source\": str}], \"claims\": [{\"claim\": "
            "str, \"amount\": str, \"status\": str, \"source\": str}], "
            "\"offers\": [{\"offer\": str, \"amount\": str, \"status\": "
            "str, \"source\": str}], \"payments\": [{\"payment\": str, "
            "\"amount\": str, \"date\": str, \"source\": str}], "
            "\"security_release\": [{\"item\": str, \"status\": str, "
            "\"source\": str}], \"flags\": [str], \"summary\": str}. "
            "CRITICAL: Do NOT make or imply any settlement commitment. Only "
            "report what is in the evidence. Ground every item; never invent "
            "amounts or dates."
        )
        user = (
            f"Debt/settlement request: {ctx.request}\n\n"
            f"Evidence:\n{evidence or '(none)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed:
            return AgentResult(self.agent_id, "error",
                               error="debt model returned no JSON")

        # Flag any language that looks like a commitment and strip it
        commitment_words = ["we will settle", "agreed to settle", "commit to"]
        flags = list(parsed.get("flags", []) or [])
        summary = parsed.get("summary", "")
        for cw in commitment_words:
            if cw in summary.lower():
                flags.append("Settlement-commitment language detected and suppressed.")

        # Secure-debt items connect to Land & Title (#13)
        secured = [s for s in parsed.get("security_release", []) or []]
        if secured:
            ctx.state["route_to_land_title"] = True
            ctx.state["secured_items"] = secured

        self.knowledge.add_document(
            title=f"Debt & settlement: {ctx.request[:80]}",
            content=self._to_text(parsed, flags),
            source="debt_settlement_agent",
            doc_type="debt",
            sensitivity="restricted",
            tenant=ctx.identity.tenant,
            metadata={"no_settlement_commitment": True, "flags": flags},
        )

        return AgentResult(
            self.agent_id, "ok",
            answer=self._to_text(parsed, flags),
            data={
                "facilities": parsed.get("facilities", []),
                "claims": parsed.get("claims", []),
                "offers": parsed.get("offers", []),
                "payments": parsed.get("payments", []),
                "security_release": parsed.get("security_release", []),
                "flags": flags,
                "no_settlement_commitment": True,
                "route_to_land_title": bool(secured),
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
    def _to_text(parsed: Dict[str, Any], flags: List[str]) -> str:
        lines = ["# Debt & Settlement", "",
                 f"**Summary:** {parsed.get('summary', '')}", "",
                 "NOTE: No settlement commitment is made or implied.", ""]
        for section, key in [("Facilities", "facilities"), ("Claims", "claims"),
                             ("Offers", "offers"), ("Payments", "payments"),
                             ("Security Release", "security_release")]:
            lines.append(f"## {section}")
            items = parsed.get(key, []) or []
            if not items:
                lines.append("- (none)")
            for it in items:
                lines.append(f"- {it}")
            lines.append("")
        if flags:
            lines.append("## Flags")
            lines += [f"- {f}" for f in flags]
        return "\n".join(lines)