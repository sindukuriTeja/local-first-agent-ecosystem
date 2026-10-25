"""Agent 1 — Orchestrator Agent.

Single entry and exit point. Responsibilities (from the architecture):
  - identifies user and permissions
  - classifies the request
  - assigns agents
  - controls order / parallel work
  - waits for approval
  - combines the final answer

The orchestrator is a router, not a doer: it classifies the incoming
request (via the local model), maps it to one or more specialist agents,
runs them in sequence (Phase 1 is sequential; parallel is a config flag),
and combines their outputs into a single sourced answer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.base_agent import AgentContext, AgentResult, BaseAgent
from ..core.ollama import extract_json


# Canonical routing table: agent_id -> (name, responsibility blurb)
# Kept in sync with registry.py. The orchestrator uses this to build its
# routing prompt and to validate model output.
ROUTE_TABLE = {
    "agent_2_internal_information": "Internal Information Agent — answer from stored internal knowledge; the only internal information desk.",
    "agent_3_external_information": "External Information Agent — fetch from official/permitted public sources; only receives cleaned questions.",
    "agent_4_document_intake_ocr": "Document Intake & OCR Agent — ingest scans/PDFs/photos/emails, OCR, extract fields.",
    "agent_5_case_analysis": "Case Analysis Agent — facts, timeline, evidence, conflicts, missing information.",
    "agent_6_legal_research": "Legal Research Agent — verified statutes, judgments, source-linked citations.",
    "agent_7_drafting": "Drafting Agent — produce source-linked drafts (needs approval).",
    "agent_8_compliance_risk": "Compliance & Risk Agent — deadlines, limitation periods, filings, risks, alerts.",
    "agent_9_build_documentation": "Build Documentation Agent — build activity, prompt/config, version history, change log.",
    "agent_10_query_support": "Query & Support Agent — answers and summaries with source links.",
    "agent_11_entity_company_intelligence": "Entity & Company Intelligence Agent — company profiles, group structure, directors, shareholding.",
    "agent_12_debt_settlement": "Debt & Settlement Agent — facilities, claims, offers, payments, security release (no settlement commitment).",
    "agent_13_land_title": "Land & Title Agent — parcels, title chain, mortgages, disputes, approvals.",
    "agent_14_tax_intelligence": "Tax Intelligence Agent — notices, demands, due dates, appeals, payments, pre-deposits.",
    "agent_15_reporting_analytics": "Reporting & Analytics Agent — dashboards, board view, PDF/Word/Excel reports from verified data.",
    "agent_16_voice_notification": "Voice Notification Agent — approved voice messages to consented recipients.",
}


class OrchestratorAgent(BaseAgent):
    agent_id = "agent_1_orchestrator"
    name = "Orchestrator Agent"
    responsibility = (
        "Single entry/exit point: identify user & permissions, classify the "
        "request, assign specialist agents, control order, wait for approval, "
        "combine the final sourced answer."
    )

    def __init__(self, services, agents: Optional[Dict[str, BaseAgent]] = None):
        super().__init__(services)
        # agents is injected by the registry to avoid circular imports
        self.agents: Dict[str, BaseAgent] = agents or {}

    # ---------- classification ----------

    def classify(self, ctx: AgentContext) -> Dict[str, Any]:
        """Use the local model to classify the request and pick agents."""
        table = "\n".join(f"- {aid}: {desc}" for aid, desc in ROUTE_TABLE.items())
        system = (
            "You are the Orchestrator of a legal/compliance agent platform. "
            "Classify the user's request and decide which specialist agent(s) "
            "should handle it, in order. Respond with ONLY a JSON object: "
            '{"intent": "<short intent>", "agents": ["<agent_id>", ...], '
            '"reason": "<one line>"} '
            f"Available agents:\n{table}\n"
            "Rules: pick the minimum set of agents that covers the request. "
            "If it is a simple internal question, use only agent_2. "
            "If documents must be read first, put agent_4 first. "
            "If drafting is requested, agent_7 must be included and will "
            "require human approval. Never invent agent ids."
        )
        parsed = self.ask_model_json(system, ctx.request)
        if not parsed or "agents" not in parsed:
            # Fallback: default to internal information
            return {"intent": "unknown", "agents": ["agent_2_internal_information"],
                    "reason": "classification failed; defaulting to internal information"}
        # Validate agent ids against the table
        valid = [a for a in parsed.get("agents", []) if a in ROUTE_TABLE]
        if not valid:
            valid = ["agent_2_internal_information"]
        return {"intent": parsed.get("intent", ""), "agents": valid,
                "reason": parsed.get("reason", "")}

    # ---------- run ----------

    def run(self, ctx: AgentContext) -> AgentResult:
        max_hops = self.settings.orchestrator_max_hops

        # 1. Identify user & permissions (already done by the caller, but
        #    re-assert the ceiling here for the audit trail).
        self._audit(ctx, "identify_user",
                    detail={"role": ctx.identity.role,
                            "max_sensitivity": ctx.identity.max_sensitivity},
                    result="identified")

        # 2. Classify
        plan = self.classify(ctx)
        self._audit(ctx, "classify_request",
                    detail={"intent": plan["intent"], "agents": plan["agents"],
                            "reason": plan["reason"]},
                    result="classified")

        # 3. Assign + run in order
        combined: Dict[str, Any] = {}
        steps: List[Dict[str, Any]] = []
        needs_approval = False
        approval_id: Optional[str] = None

        for agent_id in plan["agents"]:
            if ctx.hop >= max_hops:
                steps.append({"agent": agent_id, "status": "skipped",
                              "reason": "max hops reached"})
                break
            agent = self.agents.get(agent_id)
            if agent is None:
                steps.append({"agent": agent_id, "status": "skipped",
                              "reason": "agent not available"})
                continue
            if not self.settings.is_agent_enabled(agent_id):
                steps.append({"agent": agent_id, "status": "skipped",
                              "reason": "agent disabled in config"})
                continue

            self._audit(ctx, "assign_agent", detail={"agent": agent_id},
                        result="assigned")
            sub = agent.handle(ctx)
            steps.append({
                "agent": agent_id,
                "status": sub.status,
                "answer": sub.answer,
                "data": sub.data,
                "sources": sub.sources,
            })
            for s in sub.sources:
                ctx.add_source(s)
            combined[agent_id] = sub
            # Propagate upstream results into shared state so downstream
            # agents (e.g. Drafting) can consume them.
            ctx.state[agent_id] = sub.data
            if agent_id == "agent_5_case_analysis":
                ctx.state["case_analysis"] = sub.data
            if agent_id == "agent_6_legal_research":
                ctx.state["legal_research"] = sub.data
            if agent_id == "agent_2_internal_information":
                # Pass the cleaned question forward so Agent 3 only ever
                # sees a sanitized query.
                if sub.data.get("cleaned_question"):
                    ctx.state["cleaned_question"] = sub.data["cleaned_question"]

            if sub.status == "needs_approval":
                needs_approval = True
                approval_id = sub.approval_id

        # 4. Combine final answer
        final_answer = self._combine(ctx, plan, steps, combined)

        status = "needs_approval" if needs_approval else "ok"
        return AgentResult(
            agent_id=self.agent_id,
            status=status,
            answer=final_answer,
            data={
                "intent": plan["intent"],
                "plan": plan,
                "steps": steps,
                "combined": {k: v.answer for k, v in combined.items()},
            },
            sources=ctx.sources,
            approval_id=approval_id,
        )

    def _combine(self, ctx: AgentContext, plan: Dict[str, Any],
                 steps: List[Dict[str, Any]], combined: Dict[str, BaseAgent]) -> str:
        """Combine specialist outputs into one sourced answer.

        If only one agent ran, return its answer directly. Otherwise use
        the local model to synthesize, always preserving source citations.
        """
        answers = {s["agent"]: s["answer"] for s in steps if s.get("answer")}
        if len(answers) == 0:
            return "No specialist agent produced an answer for this request."
        if len(answers) == 1:
            return list(answers.values())[0]

        system = (
            "You are the Orchestrator combining specialist agent outputs into "
            "one clear, sourced answer for the user. Preserve every source "
            "citation. Do not add facts that are not in the inputs. If a "
            "section requires human approval, note that it is pending approval."
        )
        user = (
            f"Request: {ctx.request}\n\n"
            + "\n\n".join(f"[{aid}]\n{text}" for aid, text in answers.items())
        )
        try:
            return self.ask_model(system, user, max_tokens=2048)
        except Exception:
            # Fallback: concatenate
            return "\n\n".join(f"## {aid}\n{text}" for aid, text in answers.items())