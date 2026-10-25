"""Agent registry: builds all 16 agents and wires the orchestrator.

Imported by the platform factory. The orchestrator receives the full
agent map so it can route; the other agents only need the shared
services bundle.
"""

from __future__ import annotations

from typing import Dict

from ..core.base_agent import BaseAgent, PlatformServices
from .agent_01_orchestrator import OrchestratorAgent
from .agent_02_internal_information import InternalInformationAgent
from .agent_03_external_information import ExternalInformationAgent
from .agent_04_document_intake_ocr import DocumentIntakeOcrAgent
from .agent_05_case_analysis import CaseAnalysisAgent
from .agent_06_legal_research import LegalResearchAgent
from .agent_07_drafting import DraftingAgent
from .agent_08_compliance_risk import ComplianceRiskAgent
from .agent_09_build_documentation import BuildDocumentationAgent
from .agent_10_query_support import QuerySupportAgent
from .agent_11_entity_intelligence import EntityCompanyIntelligenceAgent
from .agent_12_debt_settlement import DebtSettlementAgent
from .agent_13_land_title import LandTitleAgent
from .agent_14_tax_intelligence import TaxIntelligenceAgent
from .agent_15_reporting import ReportingAnalyticsAgent
from .agent_16_voice_notification import VoiceNotificationAgent

AGENT_IDS = [
    "agent_1_orchestrator",
    "agent_2_internal_information",
    "agent_3_external_information",
    "agent_4_document_intake_ocr",
    "agent_5_case_analysis",
    "agent_6_legal_research",
    "agent_7_drafting",
    "agent_8_compliance_risk",
    "agent_9_build_documentation",
    "agent_10_query_support",
    "agent_11_entity_company_intelligence",
    "agent_12_debt_settlement",
    "agent_13_land_title",
    "agent_14_tax_intelligence",
    "agent_15_reporting_analytics",
    "agent_16_voice_notification",
]


def build_agents(services: PlatformServices) -> Dict[str, BaseAgent]:
    """Instantiate all 16 agents. The orchestrator is wired last so it
    can hold references to every other agent."""
    agents: Dict[str, BaseAgent] = {}
    agents["agent_2_internal_information"] = InternalInformationAgent(services)
    agents["agent_3_external_information"] = ExternalInformationAgent(services)
    agents["agent_4_document_intake_ocr"] = DocumentIntakeOcrAgent(services)
    agents["agent_5_case_analysis"] = CaseAnalysisAgent(services)
    agents["agent_6_legal_research"] = LegalResearchAgent(services)
    agents["agent_7_drafting"] = DraftingAgent(services)
    agents["agent_8_compliance_risk"] = ComplianceRiskAgent(services)
    agents["agent_9_build_documentation"] = BuildDocumentationAgent(services)
    agents["agent_10_query_support"] = QuerySupportAgent(services)
    agents["agent_11_entity_company_intelligence"] = EntityCompanyIntelligenceAgent(services)
    agents["agent_12_debt_settlement"] = DebtSettlementAgent(services)
    agents["agent_13_land_title"] = LandTitleAgent(services)
    agents["agent_14_tax_intelligence"] = TaxIntelligenceAgent(services)
    agents["agent_15_reporting_analytics"] = ReportingAnalyticsAgent(services)
    agents["agent_16_voice_notification"] = VoiceNotificationAgent(services)
    # Orchestrator last — it routes to all of the above.
    agents["agent_1_orchestrator"] = OrchestratorAgent(services, agents=agents)
    return agents