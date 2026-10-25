"""Agent 15 — Reporting & Analytics Agent.

From the architecture:
  Verified / labelled data only • Dashboards • Board view
  PDF / Word / Excel reports

Produces dashboards, board views, and reports (PDF/Word/Excel) using
ONLY verified/labelled data. External sharing requires approval from the
authorized human reviewer. Feeds approved messages to the Voice
Notification Agent (#16).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class ReportingAnalyticsAgent(BaseAgent):
    agent_id = "agent_15_reporting_analytics"
    name = "Reporting & Analytics Agent"
    responsibility = (
        "Produce dashboards, board views, and PDF/Word/Excel reports using "
        "only verified/labelled data. External sharing requires human "
        "approval. Feed approved messages to Voice Notification."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        # Only verified/labelled data: pull from compliance + domain state
        # and from stored knowledge (verified doc types only).
        results = self.grounded_retrieval(ctx, ctx.request, top_k=10)
        verified = [r for r in results
                    if r.record.doc_type in ("compliance", "case_analysis", "tax",
                                             "land_title", "debt", "entity_profile",
                                             "legal_note", "external_research")]
        evidence = self._format_evidence(verified)

        # Merge in domain-agent state (compliance alerts, etc.)
        domain_state = {
            "compliance_alerts": ctx.state.get("compliance_alerts", []),
            "compliance_deadlines": ctx.state.get("compliance_deadlines", []),
        }

        system = self.system_prompt(
            "Produce a report from VERIFIED/LABELLED data only. Respond with "
            "ONLY a JSON object: {\"title\": str, \"format\": one of "
            "\"dashboard\"|\"board_view\"|\"pdf\"|\"word\"|\"excel\", "
            "\"sections\": [{\"heading\": str, \"content\": str, "
            "\"data_label\": str}], \"key_metrics\": [{\"metric\": str, "
            "\"value\": str, \"source\": str}], \"sources\": [str], "
            "\"requires_external_sharing\": bool}. Use ONLY the provided "
            "verified data. Label every figure with its data_label and "
            "source. Never invent metrics."
        )
        user = (
            f"Report request: {ctx.request}\n\n"
            f"Domain state (verified):\n{self._dump(domain_state)}\n\n"
            f"Verified/labelled evidence:\n{evidence or '(none)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed or "title" not in parsed:
            return AgentResult(self.agent_id, "error",
                               error="reporting model returned no JSON")

        # Write the report to the build docs directory
        build_dir = self.settings.resolve_path(self.settings.storage.build_docs_dir)
        os.makedirs(build_dir, exist_ok=True)
        report_id = f"report_{ctx.task_id[:8]}"
        report_path = os.path.join(build_dir, f"{report_id}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)

        sources = parsed.get("sources", []) or []
        for s in sources:
            ctx.add_source(s)

        # External sharing requires approval
        approval_id = None
        requires_sharing = bool(parsed.get("requires_external_sharing", False))
        if requires_sharing:
            req = self.approval.request(
                kind="external_share",
                title=f"External sharing approval: {parsed.get('title', 'report')}",
                payload={"report_id": report_id, "title": parsed.get("title"),
                         "format": parsed.get("format"),
                         "key_metrics": parsed.get("key_metrics", [])},
                requested_by=ctx.identity.username,
            )
            approval_id = req.id

        # Feed approved message to Voice Notification (#16)
        ctx.state["route_to_voice_notification"] = True
        ctx.state["voice_message"] = {
            "report_title": parsed.get("title"),
            "key_metrics": parsed.get("key_metrics", []),
        }

        self._audit(ctx, "report_generated",
                    detail={"report_id": report_id,
                            "format": parsed.get("format"),
                            "requires_sharing": requires_sharing,
                            "approval_id": approval_id},
                    result="generated")

        return AgentResult(
            self.agent_id, "needs_approval" if requires_sharing else "ok",
            answer=self._to_text(parsed),
            data={
                "report_id": report_id,
                "report_path": report_path,
                "title": parsed.get("title"),
                "format": parsed.get("format"),
                "sections": parsed.get("sections", []),
                "key_metrics": parsed.get("key_metrics", []),
                "requires_external_sharing": requires_sharing,
                "route_to_voice_notification": True,
            },
            approval_id=approval_id,
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
    def _dump(obj: Any) -> str:
        if not obj:
            return "(none)"
        try:
            return json.dumps(obj, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(obj)

    @staticmethod
    def _to_text(parsed: Dict[str, Any]) -> str:
        lines = [f"# {parsed.get('title', 'Report')}",
                 f"Format: {parsed.get('format', 'n/a')}", ""]
        for s in parsed.get("sections", []):
            lines.append(f"## {s.get('heading', '')}")
            lines.append(s.get("content", ""))
            if s.get("data_label"):
                lines.append(f"_(data label: {s.get('data_label')})_")
            lines.append("")
        lines.append("## Key Metrics")
        for m in parsed.get("key_metrics", []):
            lines.append(f"- {m.get('metric', '')}: {m.get('value', '')} "
                         f"(source: {m.get('source', 'n/a')})")
        if not parsed.get("key_metrics"):
            lines.append("- (none)")
        if parsed.get("requires_external_sharing"):
            lines += ["", "NOTE: External sharing requires human approval."]
        return "\n".join(lines)