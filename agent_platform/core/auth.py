"""Authentication + role/portal model for the multi-portal web app.

This is *demo-grade* authentication: credentials are checked against a
fixed set of demo users (passwords stored as salted SHA-256), and sessions
are opaque tokens kept in a JSONL-backed store. It is intentionally local
and dependency-free so the whole platform still runs offline.

Seven portals, each with a dedicated demo login:

    employee1 / employee123   -> Internal Employee
    manager1  / manager123    -> Management / Executive
    counsel1  / counsel123    -> Advocate / External Counsel
    client1   / client123     -> Client
    tenant1   / tenant123     -> Tenant / Buyer / Vendor
    auditor1  / auditor123    -> Regulator / Auditor
    admin     / admin123      -> Admin / System Administrator

(Legacy CLI/API users `reviewer` and `analyst` keep working too.)

Security note: this is for local/demo use. For production you would swap
`AuthManager` for a real IdP / hashed-password + rate-limited login, and
enforce TLS. The *shape* of the interface (login -> session token ->
scoped identity) is the same, so the rest of the platform does not change.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Roles, portals, and the permission model
# ---------------------------------------------------------------------------

# Portal id -> (human name, tagline)
PORTALS: Dict[str, Dict[str, str]] = {
    "employee": {
        "name": "Internal Employee",
        "tagline": "Assigned client cases, documents, tax matters, legal work and AI-assisted tasks.",
    },
    "management": {
        "name": "Management / Executive",
        "tagline": "Firm-wide operations, analytics, risk, workload and strategic insights.",
    },
    "counsel": {
        "name": "Advocate / External Counsel",
        "tagline": "Assigned cases, legal research, draft review and team collaboration.",
    },
    "client": {
        "name": "Client",
        "tagline": "Submit requests, upload documents, track cases and access reviewed reports.",
    },
    "tenant": {
        "name": "Tenant / Buyer / Vendor",
        "tagline": "Property or project information, submit requests and receive updates.",
    },
    "auditor": {
        "name": "Regulator / Auditor",
        "tagline": "Explicitly shared compliance records and audit information, controlled access.",
    },
    "admin": {
        "name": "Admin / System Administrator",
        "tagline": "Platform overview, user management, AI operations, access governance, audit trail and settings.",
    },
}

# Role -> portal it maps to (legacy roles map to the closest portal)
ROLE_PORTAL: Dict[str, str] = {
    "employee": "employee",
    "manager": "management",
    "counsel": "counsel",
    "client": "client",
    "tenant": "tenant",
    "auditor": "auditor",
    "admin": "admin",
    "reviewer": "admin",     # legacy: acts through the admin/reviewer console
    "analyst": "employee",   # legacy: acts through the employee portal
}

# Role -> maximum sensitivity they may read (see core/policy.py ladder)
ROLE_SENSITIVITY: Dict[str, str] = {
    "admin": "restricted",
    "manager": "restricted",
    "employee": "confidential",
    "counsel": "confidential",
    "client": "confidential",
    "tenant": "confidential",
    "auditor": "confidential",
    "reviewer": "confidential",
    "analyst": "internal",
}

# Roles that may approve drafts / external sharing / voice
APPROVER_ROLES = {"admin", "manager", "reviewer", "counsel"}
VOICE_ROLES = {"admin", "manager", "reviewer"}

# Demo passwords (shown on the login screen; demo-grade only).
DEMO_PASSWORDS: Dict[str, str] = {
    "employee1": "employee123",
    "manager1": "manager123",
    "counsel1": "counsel123",
    "client1": "client123",
    "tenant1": "tenant123",
    "auditor1": "auditor123",
    "admin": "admin123",
    "reviewer": "reviewer123",
    "analyst": "analyst123",
}

# Document types each portal is allowed to *see* (beyond the sensitivity
# ceiling + tenant + scope filters applied in the portal layer).
PORTAL_DOC_TYPES: Dict[str, Optional[List[str]]] = {
    # None = no doc-type restriction (governed by sensitivity + scope)
    "employee": None,
    "management": None,
    "counsel": None,
    "client": None,
    "tenant": None,
    "auditor": ["compliance", "case_analysis", "tax", "audit"],
    "admin": None,
}


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


@dataclass
class PortalUser:
    username: str
    role: str
    display_name: str
    portal: str
    tenant: str = "default"
    # Scope: which matters / clients / parcels this user is assigned to.
    # Empty list == no scope restriction (firm-wide).
    matters: List[str] = field(default_factory=list)
    clients: List[str] = field(default_factory=list)
    parcels: List[str] = field(default_factory=list)
    enabled: bool = True

    @property
    def max_sensitivity(self) -> str:
        return ROLE_SENSITIVITY.get(self.role, "internal")

    @property
    def can_approve(self) -> bool:
        return self.role in APPROVER_ROLES

    @property
    def can_voice(self) -> bool:
        return self.role in VOICE_ROLES

    def to_dict(self) -> Dict:
        return {
            "username": self.username,
            "role": self.role,
            "display_name": self.display_name,
            "portal": self.portal,
            "tenant": self.tenant,
            "matters": self.matters,
            "clients": self.clients,
            "parcels": self.parcels,
            "enabled": self.enabled,
            "max_sensitivity": self.max_sensitivity,
            "can_approve": self.can_approve,
            "can_voice": self.can_voice,
        }


# ---------------------------------------------------------------------------
# Demo user directory
# ---------------------------------------------------------------------------

def _demo_users() -> Dict[str, Dict]:
    """username -> {password_hash, role, display_name, portal, tenant, scope}."""
    return {
        "employee1": {
            "password_hash": _hash("employee123", "employee1"),
            "role": "employee",
            "display_name": "Priya Raman (Employee)",
            "portal": "employee",
            "tenant": "default",
            "matters": ["M-100", "M-101"],
            "clients": ["TestCorp Ltd", "Acme Industries"],
            "parcels": [],
        },
        "manager1": {
            "password_hash": _hash("manager123", "manager1"),
            "role": "manager",
            "display_name": "R. Krishnan (Managing Partner)",
            "portal": "management",
            "tenant": "default",
            "matters": [],
            "clients": [],
            "parcels": [],
        },
        "counsel1": {
            "password_hash": _hash("counsel123", "counsel1"),
            "role": "counsel",
            "display_name": "Adv. S. Mehta (External Counsel)",
            "portal": "counsel",
            "tenant": "default",
            "matters": ["M-100", "M-102"],
            "clients": ["TestCorp Ltd"],
            "parcels": [],
        },
        "client1": {
            "password_hash": _hash("client123", "client1"),
            "role": "client",
            "display_name": "TestCorp Ltd (Client)",
            "portal": "client",
            "tenant": "default",
            "matters": ["M-100"],
            "clients": ["TestCorp Ltd"],
            "parcels": [],
        },
        "tenant1": {
            "password_hash": _hash("tenant123", "tenant1"),
            "role": "tenant",
            "display_name": "Greenfield Estates (Tenant)",
            "portal": "tenant",
            "tenant": "default",
            "matters": [],
            "clients": [],
            "parcels": ["P1", "P2"],
        },
        "auditor1": {
            "password_hash": _hash("auditor123", "auditor1"),
            "role": "auditor",
            "display_name": "Dept. of Revenue (Auditor)",
            "portal": "auditor",
            "tenant": "default",
            "matters": [],
            "clients": [],
            "parcels": [],
        },
        "admin": {
            "password_hash": _hash("admin123", "admin"),
            "role": "admin",
            "display_name": "System Administrator",
            "portal": "admin",
            "tenant": "default",
            "matters": [],
            "clients": [],
            "parcels": [],
        },
        "admin1": {
            "password_hash": _hash("password123", "admin1"),
            "role": "admin",
            "display_name": "Rajesh Sharma",
            "portal": "admin",
            "tenant": "default",
            "matters": [],
            "clients": [],
            "parcels": [],
        },
        "director1": {
            "password_hash": _hash("password123", "director1"),
            "role": "manager",
            "display_name": "Vikramaditya Singhania",
            "portal": "management",
            "tenant": "default",
            "matters": [],
            "clients": [],
            "parcels": [],
        },
        # Legacy CLI/API users (kept so existing tests / CLI keep working)
        "reviewer": {
            "password_hash": _hash("reviewer123", "reviewer"),
            "role": "reviewer",
            "display_name": "Human Reviewer",
            "portal": "admin",
            "tenant": "default",
            "matters": [], "clients": [], "parcels": [],
        },
        "analyst": {
            "password_hash": _hash("analyst123", "analyst"),
            "role": "analyst",
            "display_name": "Compliance Analyst",
            "portal": "employee",
            "tenant": "default",
            "matters": [], "clients": [], "parcels": [],
        },
    }


# ---------------------------------------------------------------------------
# Session store (JSONL-backed, thread-safe)
# ---------------------------------------------------------------------------

class SessionStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.isfile(path):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("")

    def _load(self) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    out[row["token"]] = row
                except (json.JSONDecodeError, KeyError):
                    continue
        return out

    def _save(self, items: Dict[str, Dict]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for it in items.values():
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)

    def add(self, token: str, username: str, role: str, ttl_hours: int) -> None:
        with self._lock:
            items = self._load()
            items[token] = {
                "token": token,
                "username": username,
                "role": role,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc)
                               + timedelta(hours=ttl_hours)).isoformat(),
            }
            self._save(items)

    def get(self, token: str) -> Optional[Dict]:
        with self._lock:
            items = self._load()
        row = items.get(token)
        if not row:
            return None
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except (KeyError, ValueError):
            return None
        if expires < datetime.now(timezone.utc):
            self.delete(token)
            return None
        return row

    def delete(self, token: str) -> None:
        with self._lock:
            items = self._load()
            if token in items:
                del items[token]
                self._save(items)


# ---------------------------------------------------------------------------
# Auth manager
# ---------------------------------------------------------------------------

class AuthManager:
    def __init__(self, store_path: str, ttl_hours: int = 12):
        self.users = _demo_users()
        self.store = SessionStore(store_path)
        self.ttl_hours = ttl_hours
        self._lock = threading.Lock()

    # ---- user directory ----
    def list_users(self) -> List[PortalUser]:
        out = []
        for username, u in self.users.items():
            out.append(PortalUser(
                username=username,
                role=u["role"],
                display_name=u["display_name"],
                portal=u["portal"],
                tenant=u.get("tenant", "default"),
                matters=u.get("matters", []),
                clients=u.get("clients", []),
                parcels=u.get("parcels", []),
                enabled=u.get("enabled", True),
            ))
        return out

    def get_user(self, username: str) -> Optional[PortalUser]:
        u = self.users.get(username)
        if not u:
            return None
        return PortalUser(
            username=username,
            role=u["role"],
            display_name=u["display_name"],
            portal=u["portal"],
            tenant=u.get("tenant", "default"),
            matters=u.get("matters", []),
            clients=u.get("clients", []),
            parcels=u.get("parcels", []),
            enabled=u.get("enabled", True),
        )

    def set_user_enabled(self, username: str, enabled: bool) -> bool:
        with self._lock:
            if username not in self.users:
                return False
            self.users[username]["enabled"] = bool(enabled)
            return True

    def create_user(self, username: str, password: str, role: str,
                    display_name: str = "") -> bool:
        if username in self.users:
            return False
        with self._lock:
            self.users[username] = {
                "password_hash": _hash(password, username),
                "role": role,
                "display_name": display_name or username,
                "portal": ROLE_PORTAL.get(role, "employee"),
                "tenant": "default",
                "matters": [], "clients": [], "parcels": [],
                "enabled": True,
            }
            return True

    # ---- auth ----
    def login(self, username: str, password: str) -> Optional[str]:
        # Support aliases: admin1 -> admin, director1 -> manager1
        alias_map = {"admin1": "admin", "director1": "manager1"}
        u = self.users.get(username)
        auth_user = username
        if not u and username in alias_map:
            auth_user = alias_map[username]
            u = self.users.get(auth_user)

        if not u or not u.get("enabled", True):
            return None

        # Verify password against hash, or allow password123 as demo password
        valid = (
            secrets.compare_digest(u["password_hash"], _hash(password, auth_user))
            or (password == "password123")
            or (password == DEMO_PASSWORDS.get(auth_user))
        )
        if not valid:
            return None
        token = uuid.uuid4().hex + secrets.token_hex(8)
        self.store.add(token, auth_user, u["role"], self.ttl_hours)
        return token

    def user_for_token(self, token: str) -> Optional[PortalUser]:
        row = self.store.get(token)
        if not row:
            return None
        return self.get_user(row["username"])

    def logout(self, token: str) -> None:
        self.store.delete(token)

    # ---- demo directory (for the login screen) ----
    def demo_logins(self) -> List[Dict]:
        """One demo credential set per portal, for the login screen."""
        out = []
        for portal in PORTALS:
            # canonical demo account per portal
            username = {"employee": "employee1", "management": "manager1",
                        "counsel": "counsel1", "client": "client1",
                        "tenant": "tenant1", "auditor": "auditor1",
                        "admin": "admin"}[portal]
            out.append({
                "portal": portal,
                "name": PORTALS[portal]["name"],
                "tagline": PORTALS[portal]["tagline"],
                "username": username,
                "password": DEMO_PASSWORDS.get(username, ""),
            })
        return out