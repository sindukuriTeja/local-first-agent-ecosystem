"""Agent 8 — Compliance & Risk Agent.

From the architecture:
  Deadlines • limitation periods • filings • risks • alerts

Tracks compliance deadlines and limitation periods, flags risks, and
raises alerts. Receives deadline/risk input from domain agents (Tax
Intelligence #14, Land & Title #13) and feeds alerts/status to
Reporting & Analytics (#15) and unacknowledged alerts to the Voice
Notification Agent (#16).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class ComplianceRiskAgent(BaseAgent):
    agent_id = "agent_8_compliance_risk"
    name = "Compliance & Risk Agent"
    responsibility = (
        "Track deadlines, limitation periods, filings, and risks; raise "
        "alerts. Feed alerts to Reporting & Analytics and unacknowledged "
        "alerts to the Voice Notification Agent."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        # Gather deadline/risk inputs from state (fed by domain agents)
        # and from stored knowledge.
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        evidence = self._format_evidence(results)

        # Merge in any deadline/risk items passed by other agents
        incoming = ctx.state.get("compliance_inputs", []) or []

        system = self.system_prompt(
            "Assess compliance and risk. Respond with ONLY a JSON object: "
            "{\"deadlines\": [{\"item\": str, \"due_date\": str, "
            "\"type\": str, \"source\": str}], "
            "\"limitation_periods\": [{\"item\": str, \"expires\": str, "
            "\"source\": str}], \"filings\": [{\"item\": str, \"status\": "
            "str, \"source\": str}], \"risks\": [{\"risk\": str, "
            "\"severity\": one of low|medium|high|critical, \"source\": "
            "str}], \"alerts\": [{\"message\": str, \"severity\": str, "
            "\"requires_acknowledgement\": bool}], \"summary\": str}. "
            "Ground every item in the provided evidence or incoming inputs. "
            "Never invent dates or deadlines."
        )
        user = (
            f"Compliance/risk request: {ctx.request}\n\n"
            f"Incoming deadline/risk inputs from domain agents:\n{self._dump(incoming)}\n\n"
            f"Stored-knowledge evidence:\n{evidence or '(none)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed:
            return AgentResult(self.agent_id, "error",
                               error="compliance model returned no JSON")

        alerts = parsed.get("alerts", []) or []
        deadlines = parsed.get("deadlines", []) or []
        risks = parsed.get("risks", []) or []

        # Persist the compliance snapshot
        self.knowledge.add_document(
            title=f"Compliance snapshot: {ctx.request[:80]}",
            content=self._to_text(parsed),
            source="compliance_risk_agent",
            doc_type="compliance",
            sensitivity="confidential",
            tenant=ctx.identity.tenant,
            metadata={"deadlines": deadlines, "risks": risks,
                      "alerts": alerts,
                      "generated_at": datetime.now(timezone.utc).isoformat()},
        )

        # Route: alerts/status -> Reporting & Analytics (#15);
        # unacknowledged high-severity alerts -> Voice Notification (#16)
        unack = [a for a in alerts if a.get("requires_acknowledgement")]
        ctx.state["compliance_alerts"] = alerts
        ctx.state["compliance_deadlines"] = deadlines
        if unack:
            ctx.state["route_to_voice_notification"] = True
            ctx.state["voice_alerts"] = unack
            self._audit(ctx, "route_unacknowledged_alerts",
                        detail={"count": len(unack)},
                        result="routed_to_agent_16")
        ctx.state["route_to_reporting"] = True

        return AgentResult(
            self.agent_id, "ok",
            answer=self._to_text(parsed),
            data={
                "deadlines": deadlines,
                "limitation_periods": parsed.get("limitation_periods", []),
                "filings": parsed.get("filings", []),
                "risks": risks,
                "alerts": alerts,
                "unacknowledged": unack,
                "route_to_reporting": True,
                "route_to_voice_notification": bool(unack),
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
        lines = ["# Compliance & Risk", "", f"**Summary:** {parsed.get('summary', '')}", ""]
        lines.append("## Deadlines")
        for d in parsed.get("deadlines", []):
            lines.append(f"- {d.get('item', '')} — due {d.get('due_date', 'n/a')} "
                         f"({d.get('type', '')}; source: {d.get('source', 'n/a')})")
        if not parsed.get("deadlines"):
            lines.append("- (none)")
        lines += ["", "## Limitation Periods"]
        for l in parsed.get("limitation_periods", []):
            lines.append(f"- {l.get('item', '')} — expires {l.get('expires', 'n/a')} "
                         f"(source: {l.get('source', 'n/a')})")
        if not parsed.get("limitation_periods"):
            lines.append("- (none)")
        lines += ["", "## Filings"]
        for f in parsed.get("filings", []):
            lines.append(f"- {f.get('item', '')} — {f.get('status', '')} "
                         f"(source: {f.get('source', 'n/a')})")
        if not parsed.get("filings"):
            lines.append("- (none)")
        lines += ["", "## Risks"]
        for r in parsed.get("risks", []):
            lines.append(f"- [{r.get('severity', '')}] {r.get('risk', '')} "
                         f"(source: {r.get('source', 'n/a')})")
        if not parsed.get("risks"):
            lines.append("- (none)")
        lines += ["", "## Alerts"]
        for a in parsed.get("alerts", []):
            ack = " [ACK REQUIRED]" if a.get("requires_acknowledgement") else ""
            lines.append(f"- [{a.get('severity', '')}] {a.get('message', '')}{ack}")
        if not parsed.get("alerts"):
            lines.append("- (none)")
        return "\n".join(lines)