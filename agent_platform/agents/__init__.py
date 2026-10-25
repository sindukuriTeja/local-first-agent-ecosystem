"""The 16 agents of Phase 1.

Import order matters: orchestrator imports the others for routing, so
the registry is built in `registry.py` to avoid circular imports.
"""

from .registry import build_agents, AGENT_IDS

__all__ = ["build_agents", "AGENT_IDS"]