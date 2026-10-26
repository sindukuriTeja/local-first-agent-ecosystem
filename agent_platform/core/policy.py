"""Data-boundary policy engine.

Enforces identity, tenant, and sensitivity scoping. Every retrieval and
every external egress passes through here. The sensitivity model is a
simple ordered ladder; a caller may only read at or below their allowed
sensitivity ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import PolicyConfig, Settings

# Ordered lowest -> highest
_SENSITIVITY_ORDER = ["public", "internal", "confidential", "restricted"]

# Role -> max sensitivity they may read
_ROLE_CEILING = {
    "admin": "restricted",
    "manager": "restricted",
    "reviewer": "confidential",
    "analyst": "internal",
    # Multi-portal roles
    "employee": "confidential",
    "counsel": "confidential",
    "client": "confidential",
    "tenant": "confidential",
    "auditor": "confidential",
}


@dataclass
class Identity:
    username: str
    role: str
    tenant: str = "default"

    @property
    def max_sensitivity(self) -> str:
        return _ROLE_CEILING.get(self.role, "internal")


class PolicyEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.policy = settings.policy

    def identify(self, username: str, tenant: str = "default") -> Optional[Identity]:
        """Resolve a username to an identity, or None if unknown."""
        for u in self.policy.users:
            if u.username == username:
                return Identity(username=username, role=u.role, tenant=tenant)
        return None

    def can_read(self, identity: Identity, sensitivity: str) -> bool:
        if sensitivity not in _SENSITIVITY_ORDER:
            sensitivity = "internal"
        ceiling = _SENSITIVITY_ORDER.index(identity.max_sensitivity)
        return _SENSITIVITY_ORDER.index(sensitivity) <= ceiling

    def can_approve(self, identity: Identity) -> bool:
        return identity.role in self.policy.approver_roles

    def can_voice(self, identity: Identity) -> bool:
        return identity.role in self.policy.voice_roles

    def is_source_permitted(self, url: str) -> bool:
        """Only allowlisted external sources may be used by Agent 3."""
        for allowed in self.policy.permitted_external_sources:
            if url == allowed or url.startswith(allowed.rstrip("/") + "/") or url.startswith(allowed):
                return True
        return False

    def sensitivity_rank(self, sensitivity: str) -> int:
        if sensitivity in _SENSITIVITY_ORDER:
            return _SENSITIVITY_ORDER.index(sensitivity)
        return 1  # default to internal

    def effective_sensitivity(self, *sensitivities: str) -> str:
        """Return the highest sensitivity among the given values."""
        best = 0
        for s in sensitivities:
            best = max(best, self.sensitivity_rank(s))
        return _SENSITIVITY_ORDER[best]