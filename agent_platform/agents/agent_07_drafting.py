"""Agent 7 — Drafting Agent.

From the architecture:
  Source-linked draft • Draft - Needs Approval

Produces source-linked drafts (letters, notices, opinions, filings) from
case-analysis inputs and verified legal research. Every draft is
source-linked and MUST pass the mandatory human reviewer before it can
be finalized or shared. The agent verifies key fields back through the
Internal Information Agent (Agent 2) and then raises an approval
request.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


class DraftingAgent(BaseAgent):
    agent_id = "agent_7_drafting"
    name = "Drafting Agent"
    responsibility = (
        "Produce source-linked drafts from case-analysis inputs and verified "
        "research. Verify key fields via the Internal Information Agent. "
        "Every draft is 'Draft - Needs Approval' and requires mandatory "
        "human review."
    )

    def run(self, ctx: AgentContext) -> AgentResult:
        # Gather inputs: case analysis + legal research (if present in state)
        case_analysis = ctx.state.get("case_analysis") or {}
        legal_research = ctx.state.get("legal_research") or {}

        # Retrieve supporting knowledge
        results = self.grounded_retrieval(ctx, ctx.request, top_k=8)
        evidence = self._format_evidence(results)

        # Verify key fields back through the Internal Information Agent
        # (Agent 2 is the only internal information desk). We query the
        # store directly here; in a full deployment this is a routed call.
        key_fields = self._collect_key_fields(case_analysis, legal_research)
        verified_fields = self._verify_fields(key_fields, ctx)

        system = self.system_prompt(
            "Draft the requested document. Respond with ONLY a JSON object: "
            "{\"title\": str, \"body\": str, \"sources\": [str], "
            "\"key_fields\": [{\"name\": str, \"value\": str, \"verified\": bool}], "
            "\"disclaimers\": [str]}. "
            "The body must be a complete, professional draft. Cite sources "
            "inline where a fact is used. Mark any unverified key field. "
            "Add a disclaimer that this is a draft requiring human approval. "
            "Never invent facts, amounts, dates, or legal provisions."
        )
        user = (
            f"Drafting request: {ctx.request}\n\n"
            f"Case analysis inputs:\n{self._dump(case_analysis)}\n\n"
            f"Verified legal research:\n{self._dump(legal_research)}\n\n"
            f"Verified key fields:\n{self._dump(verified_fields)}\n\n"
            f"Supporting knowledge:\n{evidence or '(none)'}"
        )
        parsed = self.ask_model_json(system, user)
        if not parsed or "body" not in parsed:
            return AgentResult(self.agent_id, "error",
                               error="drafting model returned no usable draft")

        title = parsed.get("title", "Untitled draft")
        body = parsed.get("body", "")
        sources = parsed.get("sources", []) or []
        for s in sources:
            ctx.add_source(s)

        # Persist the draft as 'unreviewed' / 'needs_approval'
        doc_id = self.knowledge.add_document(
            title=f"DRAFT: {title}",
            content=body,
            source="drafting_agent",
            doc_type="draft",
            sensitivity="confidential",
            tenant=ctx.identity.tenant,
            status="unreviewed",
            metadata={
                "sources": sources,
                "key_fields": parsed.get("key_fields", []),
                "disclaimers": parsed.get("disclaimers", []),
                "status": "needs_approval",
            },
        )

        # MANDATORY human review — raise an approval request
        req = self.approval.request(
            kind="draft",
            title=f"Draft needs approval: {title}",
            payload={
                "document_id": doc_id,
                "title": title,
                "body": body,
                "sources": sources,
                "key_fields": parsed.get("key_fields", []),
                "disclaimers": parsed.get("disclaimers", []),
            },
            requested_by=ctx.identity.username,
        )

        self._audit(ctx, "draft_created",
                    detail={"doc_id": doc_id, "title": title,
                            "sources": sources,
                            "approval_id": req.id},
                    result="needs_approval")

        return AgentResult(
            self.agent_id, "needs_approval",
            answer=(
                f"Draft '{title}' created (status: Draft - Needs Approval). "
                f"It has been sent to the authorized human reviewer and cannot "
                f"be finalized or shared until approved.\n\n{body}"
            ),
            data={
                "doc_id": doc_id,
                "title": title,
                "body": body,
                "sources": sources,
                "key_fields": parsed.get("key_fields", []),
                "disclaimers": parsed.get("disclaimers", []),
                "status": "needs_approval",
            },
            approval_id=req.id,
            sources=ctx.sources,
        )

    # ---------- helpers ----------

    @staticmethod
    def _collect_key_fields(case_analysis: Dict, legal_research: Dict) -> List[str]:
        fields: List[str] = []
        for f in case_analysis.get("facts", []) or []:
            fields.append(f)
        for c in legal_research.get("citations", []) or []:
            fields.append(f"{c.get('authority', '')} {c.get('provision', '')}".strip())
        return fields[:20]

    def _verify_fields(self, fields: List[str], ctx: AgentContext) -> Dict[str, Any]:
        """Check each key field against stored knowledge. Returns a map of
        field -> verified(bool)."""
        verified: Dict[str, bool] = {}
        for f in fields:
            hits = self.grounded_retrieval(ctx, f, top_k=1)
            verified[f] = bool(hits)
        return verified

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