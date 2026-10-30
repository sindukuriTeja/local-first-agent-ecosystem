"""Real-estate property database (local-first).

A small, self-contained SQLite store holding the firm's *sellable* property
inventory — land, plots, flats and apartments across Hyderabad, Chennai and
Bangalore. It is deliberately separate from the governed knowledge store
(``data/knowledge.db``) so the property catalogue can be queried, shared and
re-priced without touching document retrieval.

Design goals (matching the platform's local-first + audit ethos):

  * **Local-first** — a single SQLite file (``data/properties.db``), no
    network, no external DB.
  * **Query, don't hardcode** — employees read live rows through
    :meth:`PropertyStore.list_properties` / :meth:`get_property`, filtered by
    city / type / status.
  * **Share** — an employee can send a property's details to a *client* or to
    *management/executive*; every share is recorded and audited.
  * **Governed re-pricing** — an employee can never change a price directly.
    A price change is filed as a *request* that sits in the management queue
    until a manager approves (price applied) or rejects it. Every step is
    written to the audit log.

The store is seeded with demo inventory on first open so every portal is
populated out of the box.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Canonical catalogue values (used for validation + UI filters).
PROPERTY_TYPES = ["land", "plot", "flat", "apartment"]
CITIES = ["Hyderabad", "Chennai", "Bangalore"]
STATUSES = ["available", "reserved", "sold"]
SHARABLE_PORTALS = ["client", "management"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    id               TEXT PRIMARY KEY,
    property_code    TEXT UNIQUE NOT NULL,
    type             TEXT NOT NULL,
    city             TEXT NOT NULL,
    locality         TEXT NOT NULL,
    title            TEXT NOT NULL,
    area_sqft        REAL,
    price_inr        INTEGER,
    price_per_sqft   INTEGER,
    bedrooms         INTEGER,
    bathrooms        INTEGER,
    facing           TEXT,
    age_years        REAL,
    ownership        TEXT,
    status           TEXT NOT NULL DEFAULT 'available',
    description      TEXT,
    created_at       TEXT,
    updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS property_shares (
    id           TEXT PRIMARY KEY,
    property_id  TEXT NOT NULL,
    to_username  TEXT,
    to_portal    TEXT NOT NULL,
    shared_by    TEXT,
    shared_at    TEXT,
    note         TEXT,
    status       TEXT NOT NULL DEFAULT 'sent'
);

CREATE TABLE IF NOT EXISTS price_change_requests (
    id               TEXT PRIMARY KEY,
    property_id      TEXT NOT NULL,
    current_price    INTEGER,
    requested_price  INTEGER,
    reason           TEXT,
    requested_by     TEXT,
    requested_at     TEXT,
    status           TEXT NOT NULL DEFAULT 'pending',
    decided_by       TEXT,
    decided_at       TEXT,
    note             TEXT
);

CREATE TABLE IF NOT EXISTS purchase_requests (
    id                 TEXT PRIMARY KEY,
    property_id        TEXT NOT NULL,
    buyer_name         TEXT NOT NULL,
    buyer_contact      TEXT,
    buyer_email        TEXT,
    buyer_id_proof     TEXT,
    requested_by       TEXT,
    requested_at       TEXT,
    status             TEXT NOT NULL DEFAULT 'pending',
    advocate_review    TEXT NOT NULL DEFAULT 'pending',
    advocate_note      TEXT,
    advocate_reviewed_at TEXT,
    auditor_review     TEXT NOT NULL DEFAULT 'pending',
    auditor_note       TEXT,
    auditor_reviewed_at TEXT,
    agreement_id       TEXT,
    agreement_text     TEXT,
    agreed_at          TEXT,
    rejected_by        TEXT,
    rejection_reason   TEXT
);

CREATE INDEX IF NOT EXISTS idx_properties_city   ON properties(city);
CREATE INDEX IF NOT EXISTS idx_properties_type   ON properties(type);
CREATE INDEX IF NOT EXISTS idx_shares_property   ON property_shares(property_id);
CREATE INDEX IF NOT EXISTS idx_price_status      ON price_change_requests(status);
CREATE INDEX IF NOT EXISTS idx_purchase_status   ON purchase_requests(status);
CREATE INDEX IF NOT EXISTS idx_purchase_property ON purchase_requests(property_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------------------
# Demo inventory (seeded on first open). Prices in INR, areas in sqft.
# ---------------------------------------------------------------------------
_DEMO_PROPERTIES: List[Dict[str, Any]] = [
    # ---------------- Hyderabad ----------------
    {"property_code": "HYD-LND-001", "type": "land", "city": "Hyderabad",
     "locality": "Gachibowli", "title": "Corner residential land plot, Gachibowli",
     "area_sqft": 2400, "price_inr": 115000000, "price_per_sqft": 47917,
     "bedrooms": None, "bathrooms": None, "facing": "North-East",
     "age_years": None, "ownership": "Freehold", "status": "available",
     "description": "Clear-title 2,400 sqft corner land in Gachibowli, 400 m from "
                    "the ORR. Gated-community ready, RERA-registered layout, "
                    "immediate possession."},
    {"property_code": "HYD-PLT-002", "type": "plot", "city": "Hyderabad",
     "locality": "Kondapur", "title": "Gated community plot, Kondapur",
     "area_sqft": 1800, "price_inr": 78000000, "price_per_sqft": 43333,
     "bedrooms": None, "bathrooms": None, "facing": "West",
     "age_years": None, "ownership": "Freehold", "status": "available",
     "description": "1,800 sqft plot in a 32-plot gated layout, Kondapur. "
                    "Clubhouse, 24x7 security, approved by GHMC."},
    {"property_code": "HYD-FLT-003", "type": "flat", "city": "Hyderabad",
     "locality": "HITEC City", "title": "3 BHK premium flat, HITEC City",
     "area_sqft": 1650, "price_inr": 16500000, "price_per_sqft": 10000,
     "bedrooms": 3, "bathrooms": 3, "facing": "East",
     "age_years": 2, "ownership": "Freehold", "status": "available",
     "description": "3 BHK + study, 1,650 sqft super built-up, 3rd floor. "
                    "Modular kitchen, 2 covered car parks, 5-min walk to "
                    "Financial District."},
    {"property_code": "HYD-APT-004", "type": "apartment", "city": "Hyderabad",
     "locality": "Manikonda", "title": "2 BHK apartment, Manikonda",
     "area_sqft": 1180, "price_inr": 9200000, "price_per_sqft": 7797,
     "bedrooms": 2, "bathrooms": 2, "facing": "South",
     "age_years": 4, "ownership": "Freehold", "status": "reserved",
     "description": "2 BHK, 1,180 sqft, 7th floor with lake view. "
                    "Reserve-amount received; token on file."},
    {"property_code": "HYD-APT-005", "type": "apartment", "city": "Hyderabad",
     "locality": "Jubilee Hills", "title": "4 BHK luxury apartment, Jubilee Hills",
     "area_sqft": 2850, "price_inr": 34000000, "price_per_sqft": 11930,
     "bedrooms": 4, "bathrooms": 5, "facing": "North",
     "age_years": 1, "ownership": "Freehold", "status": "available",
     "description": "4 BHK duplex-style apartment, 2,850 sqft, private lift "
                    "lobby, 3 car parks. Premium fittings throughout."},

    # ---------------- Chennai ----------------
    {"property_code": "CHN-LND-006", "type": "land", "city": "Chennai",
     "locality": "OMR (Thoraipakkam)", "title": "Layout land, OMR",
     "area_sqft": 3000, "price_inr": 90000000, "price_per_sqft": 30000,
     "bedrooms": None, "bathrooms": None, "facing": "East",
     "age_years": None, "ownership": "Freehold", "status": "available",
     "description": "3,000 sqft layout land on OMR, 800 m from the IT corridor. "
                    "DTCP layout, clear patta, ready for construction."},
    {"property_code": "CHN-PLT-007", "type": "plot", "city": "Chennai",
     "locality": "Velachery", "title": "Approved layout plot, Velachery",
     "area_sqft": 2100, "price_inr": 63000000, "price_per_sqft": 30000,
     "bedrooms": None, "bathrooms": None, "facing": "North",
     "age_years": None, "ownership": "Freehold", "status": "available",
     "description": "2,100 sqft plot in a 40-unit DTCP layout, Velachery. "
                    "Near metro Phase-1 corridor, all approvals in place."},
    {"property_code": "CHN-FLT-008", "type": "flat", "city": "Chennai",
     "locality": "Adyar", "title": "3 BHK flat, Adyar",
     "area_sqft": 1520, "price_inr": 14200000, "price_per_sqft": 9342,
     "bedrooms": 3, "bathrooms": 3, "facing": "East",
     "age_years": 6, "ownership": "Freehold", "status": "available",
     "description": "3 BHK, 1,520 sqft, 5th floor, Adyar. Close to IT park and "
                    "lakes; society with clubhouse and power backup."},
    {"property_code": "CHN-APT-009", "type": "apartment", "city": "Chennai",
     "locality": "Anna Nagar", "title": "2 BHK apartment, Anna Nagar",
     "area_sqft": 1050, "price_inr": 10500000, "price_per_sqft": 10000,
     "bedrooms": 2, "bathrooms": 2, "facing": "West",
     "age_years": 8, "ownership": "Freehold", "status": "sold",
     "description": "2 BHK, 1,050 sqft, Anna Nagar West. Recently transacted; "
                    "kept in the catalogue for reference."},
    {"property_code": "CHN-APT-010", "type": "apartment", "city": "Chennai",
     "locality": "T. Nagar", "title": "3 BHK premium apartment, T. Nagar",
     "area_sqft": 1700, "price_inr": 21000000, "price_per_sqft": 12353,
     "bedrooms": 3, "bathrooms": 3, "facing": "North-East",
     "age_years": 3, "ownership": "Freehold", "status": "available",
     "description": "3 BHK, 1,700 sqft in a high-rise, T. Nagar. Skyline view, "
                    "amphitheatre, dedicated service lift."},

    # ---------------- Bangalore ----------------
    {"property_code": "BLR-LND-011", "type": "land", "city": "Bangalore",
     "locality": "Sarjapur Road", "title": "Commercial land parcel, Sarjapur Road",
     "area_sqft": 5000, "price_inr": 150000000, "price_per_sqft": 30000,
     "bedrooms": None, "bathrooms": None, "facing": "South",
     "age_years": None, "ownership": "Freehold", "status": "available",
     "description": "5,000 sqft commercial-zoned land on Sarjapur Road, 500 m "
                    "from the flyover. Suitable for a small office park or "
                    "retail frontage."},
    {"property_code": "BLR-PLT-012", "type": "plot", "city": "Bangalore",
     "locality": "Hebbal", "title": "Gated layout plot, Hebbal",
     "area_sqft": 2600, "price_inr": 104000000, "price_per_sqft": 40000,
     "bedrooms": None, "bathrooms": None, "facing": "East",
     "age_years": None, "ownership": "Freehold", "status": "available",
     "description": "2,600 sqft plot in a 24-plot gated layout, Hebbal. "
                    "BDA-approved, clubhouse and internal roads done."},
    {"property_code": "BLR-FLT-013", "type": "flat", "city": "Bangalore",
     "locality": "Koramangala", "title": "3 BHK flat, Koramangala",
     "area_sqft": 1480, "price_inr": 18500000, "price_per_sqft": 12500,
     "bedrooms": 3, "bathrooms": 3, "facing": "West",
     "age_years": 5, "ownership": "Freehold", "status": "available",
     "description": "3 BHK, 1,480 sqft, 8th floor, Koramangala 5th Block. "
                    "Walk to the commercial street; society with gym and pool."},
    {"property_code": "BLR-APT-014", "type": "apartment", "city": "Bangalore",
     "locality": "Whitefield", "title": "2 BHK apartment, Whitefield",
     "area_sqft": 1100, "price_inr": 8800000, "price_per_sqft": 8000,
     "bedrooms": 2, "bathrooms": 2, "facing": "North",
     "age_years": 2, "ownership": "Freehold", "status": "available",
     "description": "2 BHK, 1,100 sqft, Whitefield (ITPL side). Newer tower, "
                    "RERA-registered, ready possession."},
    {"property_code": "BLR-APT-015", "type": "apartment", "city": "Bangalore",
     "locality": "HSR Layout", "title": "4 BHK luxury apartment, HSR Layout",
     "area_sqft": 2400, "price_inr": 30000000, "price_per_sqft": 12500,
     "bedrooms": 4, "bathrooms": 4, "facing": "East",
     "age_years": 1, "ownership": "Freehold", "status": "reserved",
     "description": "4 BHK, 2,400 sqft, HSR Layout Sector 2. Private garden, "
                    "2 car parks; reserve-amount received."},
    {"property_code": "BLR-FLT-016", "type": "flat", "city": "Bangalore",
     "locality": "Electronic City", "title": "2 BHK flat, Electronic City",
     "area_sqft": 1150, "price_inr": 7600000, "price_per_sqft": 6609,
     "bedrooms": 2, "bathrooms": 2, "facing": "South",
     "age_years": 7, "ownership": "Freehold", "status": "available",
     "description": "2 BHK, 1,150 sqft, Electronic City Phase 1. Close to "
                    "the metro; good rental demand."},
]


class PropertyStore:
    """SQLite-backed property inventory with share + governed re-pricing."""

    def __init__(self, db_path: str, audit=None):
        self.db_path = db_path
        self.audit = audit
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_schema()
        self._seed_if_empty()

    # ---------- connection helpers ---------------------------------------
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _audit(self, actor: str, action: str, detail: Dict[str, Any],
               result: str = "ok", user: Optional[str] = None) -> None:
        if self.audit is not None:
            try:
                self.audit.record(actor=actor, action=action, detail=detail,
                                  user=user, result=result)
            except Exception:
                pass

    # ---------- schema + seed --------------------------------------------
    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _seed_if_empty(self) -> None:
        with self._conn() as conn:
            n = conn.execute("SELECT COUNT(*) AS c FROM properties").fetchone()["c"]
            if n:
                return
            now = _now()
            for p in _DEMO_PROPERTIES:
                conn.execute(
                    """INSERT INTO properties
                       (id, property_code, type, city, locality, title,
                        area_sqft, price_inr, price_per_sqft, bedrooms,
                        bathrooms, facing, age_years, ownership, status,
                        description, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        _new_id("prop"), p["property_code"], p["type"],
                        p["city"], p["locality"], p["title"], p["area_sqft"],
                        p["price_inr"], p["price_per_sqft"], p["bedrooms"],
                        p["bathrooms"], p["facing"], p["age_years"],
                        p["ownership"], p["status"], p["description"], now, now,
                    ),
                )
        self._audit("property_store", "properties_seeded",
                    {"count": len(_DEMO_PROPERTIES)})

    # ---------- row -> dict ----------------------------------------------
    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        # Convenience derived fields for the UI.
        d["price_display"] = _inr(d.get("price_inr"))
        d["type_label"] = _type_label(d.get("type"))
        return d

    # ---------- queries ---------------------------------------------------
    def list_properties(self, city: Optional[str] = None,
                        ptype: Optional[str] = None,
                        status: Optional[str] = None,
                        search: Optional[str] = None,
                        limit: int = 200) -> List[Dict[str, Any]]:
        """Live query of the inventory. All filters are optional."""
        sql = "SELECT * FROM properties WHERE 1=1"
        args: List[Any] = []
        if city:
            sql += " AND city = ?"
            args.append(city)
        if ptype:
            sql += " AND type = ?"
            args.append(ptype)
        if status:
            sql += " AND status = ?"
            args.append(status)
        if search:
            sql += " AND (title LIKE ? OR locality LIKE ? OR property_code LIKE ?)"
            like = f"%{search}%"
            args.extend([like, like, like])
        sql += " ORDER BY city, type, property_code LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_property(self, property_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM properties WHERE id = ?", (property_id,)
            ).fetchone()
        if row is None:
            return None
        d = self._row_to_dict(row)
        d["shares"] = self.shares_for_property(property_id)
        d["price_requests"] = self.price_requests_for_property(property_id)
        d["purchase_requests"] = self.purchase_requests_for_property(property_id)
        return d

    def stats(self) -> Dict[str, Any]:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM properties").fetchone()["c"]
            by_city = {r["city"]: r["c"] for r in conn.execute(
                "SELECT city, COUNT(*) c FROM properties GROUP BY city")}
            by_type = {r["type"]: r["c"] for r in conn.execute(
                "SELECT type, COUNT(*) c FROM properties GROUP BY type")}
            by_status = {r["status"]: r["c"] for r in conn.execute(
                "SELECT status, COUNT(*) c FROM properties GROUP BY status")}
            pending_price = conn.execute(
                "SELECT COUNT(*) c FROM price_change_requests WHERE status='pending'"
            ).fetchone()["c"]
        pending_purchase = conn.execute(
            "SELECT COUNT(*) c FROM purchase_requests WHERE status='pending'"
        ).fetchone()["c"]
        return {
            "total": total,
            "by_city": by_city,
            "by_type": by_type,
            "by_status": by_status,
            "pending_price_requests": pending_price,
            "pending_purchase_requests": pending_purchase,
            "cities": CITIES,
            "types": PROPERTY_TYPES,
            "statuses": STATUSES,
        }

    # ---------- sharing (employee -> client / management) ----------------
    def share_property(self, property_id: str, to_portal: str,
                       to_username: Optional[str] = None,
                       note: str = "", shared_by: str = "") -> Optional[Dict[str, Any]]:
        """Record that an employee sent a property to a client or management."""
        if to_portal not in SHARABLE_PORTALS:
            raise ValueError(f"to_portal must be one of {SHARABLE_PORTALS}")
        with self._conn() as conn:
            prop = conn.execute(
                "SELECT property_code, title FROM properties WHERE id=?",
                (property_id,)).fetchone()
            if prop is None:
                return None
            sid = _new_id("shr")
            now = _now()
            conn.execute(
                """INSERT INTO property_shares
                   (id, property_id, to_username, to_portal, shared_by,
                    shared_at, note, status)
                   VALUES (?,?,?,?,?,?,?, 'sent')""",
                (sid, property_id, to_username, to_portal, shared_by, now, note),
            )
        self._audit(f"user:{shared_by}", "property_shared",
                    {"property_id": property_id, "property_code": prop["property_code"],
                     "to_portal": to_portal, "to_username": to_username,
                     "share_id": sid},
                    result="sent", user=shared_by)
        return {"share_id": sid, "property_id": property_id,
                "to_portal": to_portal, "to_username": to_username,
                "status": "sent"}

    def shares_for_property(self, property_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM property_shares WHERE property_id=? "
                "ORDER BY shared_at DESC", (property_id,)).fetchall()
        return [dict(r) for r in rows]

    def shares_for_portal(self, portal: str,
                          username: Optional[str] = None) -> List[Dict[str, Any]]:
        """Properties shared to a portal (optionally a specific user).

        Returns the FULL property row (all listing details) alongside the
        share metadata (shared_by / shared_at / note) so receiving portals
        — e.g. the client portal — can render the complete listing card.
        """
        sql = ("SELECT s.*, p.property_code, p.title, p.city, p.locality, "
               "p.type, p.area_sqft, p.price_inr, p.price_per_sqft, "
               "p.bedrooms, p.bathrooms, p.facing, p.age_years, "
               "p.ownership, p.status, p.description, p.created_at, "
               "p.updated_at "
               "FROM property_shares s JOIN properties p ON p.id=s.property_id "
               "WHERE s.to_portal=?")
        args: List[Any] = [portal]
        if username:
            sql += " AND (s.to_username IS NULL OR s.to_username=?)"
            args.append(username)
        sql += " ORDER BY s.shared_at DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d.pop("price_display", None)
            d["price_display"] = _inr(d.get("price_inr"))
            d["type_label"] = _type_label(d.get("type"))
            out.append(d)
        return out

    def shares_by_user(self, shared_by: str) -> List[Dict[str, Any]]:
        """All shares made by a given employee (to client or management)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT s.*, p.property_code, p.title, p.city, p.locality,
                          p.type, p.area_sqft, p.price_inr
                   FROM property_shares s JOIN properties p ON p.id=s.property_id
                   WHERE s.shared_by=?
                   ORDER BY s.shared_at DESC""", (shared_by,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["price_display"] = _inr(d.get("price_inr"))
            d["type_label"] = _type_label(d.get("type"))
            out.append(d)
        return out

    # ---------- governed price changes -----------------------------------
    def request_price_change(self, property_id: str, requested_price: int,
                             reason: str = "",
                             requested_by: str = "") -> Optional[Dict[str, Any]]:
        """File a price-change request (NOT applied). Returns the request.

        The request stays ``pending`` until a manager decides it via
        :meth:`decide_price_change`.
        """
        requested_price = int(requested_price)
        with self._conn() as conn:
            prop = conn.execute(
                "SELECT property_code, price_inr FROM properties WHERE id=?",
                (property_id,)).fetchone()
            if prop is None:
                return None
            if requested_price <= 0:
                raise ValueError("requested_price must be positive")
            rid = _new_id("pcr")
            now = _now()
            conn.execute(
                """INSERT INTO price_change_requests
                   (id, property_id, current_price, requested_price, reason,
                    requested_by, requested_at, status)
                   VALUES (?,?,?,?,?,?,?, 'pending')""",
                (rid, property_id, prop["price_inr"], requested_price,
                 reason, requested_by, now),
            )
        self._audit(f"user:{requested_by}", "property_price_change_requested",
                    {"property_id": property_id,
                     "property_code": prop["property_code"],
                     "current_price": prop["price_inr"],
                     "requested_price": requested_price, "request_id": rid},
                    result="pending", user=requested_by)
        return self.get_price_request(rid)

    def get_price_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM price_change_requests WHERE id=?",
                (request_id,)).fetchone()
        return dict(row) if row else None

    def pending_price_requests(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT r.*, p.property_code, p.title, p.city, p.locality,
                          p.type
                   FROM price_change_requests r
                   JOIN properties p ON p.id=r.property_id
                   WHERE r.status='pending'
                   ORDER BY r.requested_at DESC""").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["current_price_display"] = _inr(d.get("current_price"))
            d["requested_price_display"] = _inr(d.get("requested_price"))
            out.append(d)
        return out

    def price_requests_for_property(self, property_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM price_change_requests WHERE property_id=? "
                "ORDER BY requested_at DESC", (property_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["current_price_display"] = _inr(d.get("current_price"))
            d["requested_price_display"] = _inr(d.get("requested_price"))
            out.append(d)
        return out

    def price_requests_by_user(self, username: str) -> List[Dict[str, Any]]:
        """All price-change requests filed by a given user (any status)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT r.*, p.property_code, p.title, p.city, p.locality
                   FROM price_change_requests r
                   JOIN properties p ON p.id=r.property_id
                   WHERE r.requested_by=?
                   ORDER BY r.requested_at DESC""", (username,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["current_price_display"] = _inr(d.get("current_price"))
            d["requested_price_display"] = _inr(d.get("requested_price"))
            out.append(d)
        return out

    def decide_price_change(self, request_id: str, decision: str,
                            decided_by: str, note: str = "") -> Optional[Dict[str, Any]]:
        """Approve or reject a pending price-change request.

        ``approved`` -> the property's price is updated to the requested price.
        ``rejected`` -> nothing changes.
        """
        if decision not in ("approved", "rejected"):
            raise ValueError("decision must be approved | rejected")
        now = _now()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM price_change_requests WHERE id=?",
                (request_id,)).fetchone()
            if row is None:
                return None
            if row["status"] != "pending":
                raise ValueError(f"request already {row['status']}")
            conn.execute(
                """UPDATE price_change_requests
                   SET status=?, decided_by=?, decided_at=?, note=?
                   WHERE id=?""",
                (decision, decided_by, now, note, request_id),
            )
            applied_price = None
            if decision == "approved":
                applied_price = row["requested_price"]
                conn.execute(
                    "UPDATE properties SET price_inr=?, updated_at=? WHERE id=?",
                    (row["requested_price"], now, row["property_id"]),
                )
        self._audit(f"user:{decided_by}", "property_price_change_decided",
                    {"request_id": request_id,
                     "property_id": row["property_id"],
                     "decision": decision,
                     "applied_price": applied_price},
                    result=decision, user=decided_by)
        return self.get_price_request(request_id)

    # ---------- purchase requests (Buy This flow) ------------------------
    def request_purchase(self, property_id: str, buyer_name: str,
                         buyer_contact: str = "", buyer_email: str = "",
                         buyer_id_proof: str = "",
                         requested_by: str = "") -> Optional[Dict[str, Any]]:
        """File a purchase (Buy This) request for a property.

        The request starts ``pending`` and is routed to the advocate and the
        auditor for review. It becomes ``approved`` only when BOTH reviewers
        approve; the first rejection closes it as ``rejected``. On approval a
        purchase agreement is generated and the property is marked ``sold``.
        """
        buyer_name = (buyer_name or "").strip()
        if not buyer_name:
            raise ValueError("buyer_name is required")
        with self._conn() as conn:
            prop = conn.execute(
                "SELECT property_code, title, status FROM properties WHERE id=?",
                (property_id,)).fetchone()
            if prop is None:
                return None
            if prop["status"] == "sold":
                raise ValueError("property is already sold")
            open_req = conn.execute(
                """SELECT 1 FROM purchase_requests
                   WHERE property_id=? AND status='pending' LIMIT 1""",
                (property_id,)).fetchone()
            if open_req is not None:
                raise ValueError("a purchase request for this property is already in review")
            rid = _new_id("prq")
            now = _now()
            conn.execute(
                """INSERT INTO purchase_requests
                   (id, property_id, buyer_name, buyer_contact, buyer_email,
                    buyer_id_proof, requested_by, requested_at, status)
                   VALUES (?,?,?,?,?,?,?,?, 'pending')""",
                (rid, property_id, buyer_name, buyer_contact, buyer_email,
                 buyer_id_proof, requested_by, now),
            )
        self._audit(f"user:{requested_by}", "property_purchase_requested",
                    {"request_id": rid, "property_id": property_id,
                     "property_code": prop["property_code"],
                     "buyer_name": buyer_name},
                    result="pending", user=requested_by)
        return self.get_purchase_request(rid)

    def get_purchase_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT r.*, p.property_code, p.title, p.city, p.locality,
                          p.type, p.area_sqft, p.price_inr, p.price_per_sqft,
                          p.ownership, p.description
                   FROM purchase_requests r
                   JOIN properties p ON p.id=r.property_id
                   WHERE r.id=?""", (request_id,)).fetchone()
        return dict(row) if row else None

    def pending_purchase_requests(self) -> List[Dict[str, Any]]:
        """Open purchase requests (any role can list; review is role-gated)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT r.*, p.property_code, p.title, p.city, p.locality,
                          p.type, p.price_inr
                   FROM purchase_requests r
                   JOIN properties p ON p.id=r.property_id
                   WHERE r.status='pending'
                   ORDER BY r.requested_at DESC""").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["price_display"] = _inr(d.get("price_inr"))
            out.append(d)
        return out

    def purchase_requests_for_property(self, property_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM purchase_requests WHERE property_id=? "
                "ORDER BY requested_at DESC", (property_id,)).fetchall()
        return [dict(r) for r in rows]

    def purchase_requests_by_user(self, username: str) -> List[Dict[str, Any]]:
        """Purchase requests filed by a user, joined with property details."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT r.*, p.property_code, p.title, p.city, p.locality,
                          p.type, p.price_inr
                   FROM purchase_requests r
                   JOIN properties p ON p.id=r.property_id
                   WHERE r.requested_by=?
                   ORDER BY r.requested_at DESC""", (username,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["price_display"] = _inr(d.get("price_inr"))
            out.append(d)
        return out

    def decide_purchase_review(self, request_id: str, reviewer_role: str,
                               decision: str, decided_by: str,
                               note: str = "") -> Optional[Dict[str, Any]]:
        """Record an advocate or auditor review of a pending purchase request.

        ``reviewer_role`` must be ``advocate`` or ``auditor``.
        ``approved`` -> that reviewer's column is set; when BOTH are approved
        the request is finalized: an agreement is generated, the property is
        marked ``sold`` and the status becomes ``approved``.
        ``rejected`` -> the request is closed as ``rejected`` immediately.
        """
        if reviewer_role not in ("advocate", "auditor"):
            raise ValueError("reviewer_role must be advocate | auditor")
        if decision not in ("approved", "rejected"):
            raise ValueError("decision must be approved | rejected")
        now = _now()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM purchase_requests WHERE id=?",
                (request_id,)).fetchone()
            if row is None:
                return None
            if row["status"] != "pending":
                raise ValueError(f"request already {row['status']}")
            if row[reviewer_role + "_review"] != "pending":
                raise ValueError(f"already reviewed by {reviewer_role}")

            if decision == "rejected":
                conn.execute(
                    f"""UPDATE purchase_requests
                        SET status='rejected', {reviewer_role}_review='rejected',
                            {reviewer_role}_note=?, {reviewer_role}_reviewed_at=?,
                            rejected_by=?, rejection_reason=?
                        WHERE id=?""",
                    (note, now, decided_by, note, request_id))
            else:
                conn.execute(
                    f"""UPDATE purchase_requests
                        SET {reviewer_role}_review='approved',
                            {reviewer_role}_note=?, {reviewer_role}_reviewed_at=?
                        WHERE id=?""",
                    (note, now, request_id))
                updated = conn.execute(
                    "SELECT * FROM purchase_requests WHERE id=?",
                    (request_id,)).fetchone()
                if updated["advocate_review"] == "approved" and \
                        updated["auditor_review"] == "approved":
                    # Both reviewers approved -> generate agreement + mark sold.
                    prop = conn.execute(
                        "SELECT * FROM properties WHERE id=?",
                        (row["property_id"],)).fetchone()
                    agr_id = _new_id("agr")
                    agreement_text = _build_purchase_agreement(updated, prop,
                                                               agr_id, now)
                    conn.execute(
                        """UPDATE purchase_requests
                           SET status='approved', agreement_id=?,
                               agreement_text=?, agreed_at=?
                           WHERE id=?""",
                        (agr_id, agreement_text, now, request_id))
                    conn.execute(
                        "UPDATE properties SET status='sold', updated_at=? "
                        "WHERE id=?", (now, row["property_id"]))
        self._audit(f"user:{decided_by}", "property_purchase_reviewed",
                    {"request_id": request_id, "reviewer_role": reviewer_role,
                     "decision": decision, "note": note},
                    result=decision, user=decided_by)
        return self.get_purchase_request(request_id)

    # ---------- demo data export (for delivery) --------------------------
    def demo_data(self) -> List[Dict[str, Any]]:
        """Return the seeded demo inventory as plain dicts."""
        return [
            {k: p[k] for k in (
                "property_code", "type", "city", "locality", "title",
                "area_sqft", "price_inr", "price_per_sqft", "bedrooms",
                "bathrooms", "facing", "age_years", "ownership", "status",
                "description")}
            for p in _DEMO_PROPERTIES
        ]


# ---------------------------------------------------------------------------
# purchase agreement generation
# ---------------------------------------------------------------------------
def _inr_words(value: Optional[int]) -> str:
    """Convert an INR amount to Indian-English words (e.g. 1,15,00,000 ->
    'Rupees One Crore Fifteen Lakh Only')."""
    if not value:
        return "Rupees Nil"
    n = int(value)
    if n == 0:
        return "Rupees Nil"

    def _below_100(v: int) -> str:
        units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
                 "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
                 "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen",
                 "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
                "Eighty", "Ninety"]
        if v < 20:
            return units[v]
        return (tens[v // 10] + (" " + units[v % 10] if v % 10 else "")).strip()

    parts: List[str] = []
    for scale, name in ((10000000, "Crore"), (100000, "Lakh"), (1000, "Thousand")):
        if n >= scale:
            parts.append(f"{_below_100(n // scale)} {name}")
            n %= scale
    if n >= 100:
        parts.append(f"{_below_100(n // 100)} Hundred")
        n %= 100
    if n:
        parts.append(_below_100(n))
    return "Rupees " + " ".join(parts) + " Only"


def _build_purchase_agreement(req: sqlite3.Row, prop: sqlite3.Row,
                              agreement_id: str, agreed_at: str = "") -> str:
    """Render the sale & purchase agreement text for an approved request."""
    price = prop["price_inr"]
    price_words = _inr_words(price)
    per_sqft = prop["price_per_sqft"] or (
        int(price / prop["area_sqft"]) if prop["area_sqft"] else None)
    beds = prop["bedrooms"]
    detail_lines = [
        f"Property Code : {prop['property_code']}",
        f"Description   : {prop['title']}",
        f"Location      : {prop['locality']}, {prop['city']}",
        f"Type          : {_type_label(prop['type'])}",
    ]
    if prop["area_sqft"]:
        detail_lines.append(f"Area          : {prop['area_sqft']:,.0f} sqft")
    if beds is not None:
        detail_lines.append(
            f"Configuration : {beds} BHK"
            + (f" / {prop['bathrooms']} Bath" if prop["bathrooms"] else ""))
    if prop["ownership"]:
        detail_lines.append(f"Ownership     : {prop['ownership']}")
    if per_sqft:
        detail_lines.append(f"Rate          : INR {per_sqft:,} per sqft")
    detail_block = "\n".join(detail_lines)
    return f"""SALE AND PURCHASE AGREEMENT
(Generated by the Local-First Agent Ecosystem — Property Desk)

Agreement ID : {agreement_id}
Date         : {(agreed_at or req['agreed_at'] or '')[:10]}

BETWEEN

The Firm (Seller)
Property inventory record {prop['property_code']}, managed through the
governed property desk of the firm.

AND

The Buyer (Purchaser)
Name   : {req['buyer_name']}
Contact: {req['buyer_contact'] or '—'}
Email  : {req['buyer_email'] or '—'}
ID Proof on file : {req['buyer_id_proof'] or '—'}

1. PROPERTY
{detail_block}

2. CONSIDERATION
The agreed sale price is {price_words} (INR {price:,}), inclusive of all
taxes and charges unless stated otherwise.

3. TITLE & POSSESSION
The Seller warrants that it holds clear and marketable title to the
property, free from encumbrances, and that possession shall be handed over
on receipt of the full consideration, subject to the terms of this
agreement.

4. APPROVALS & COMPLIANCE
This sale has been reviewed and approved by the firm's Advocate (legal
review) and Auditor (compliance review) as a condition of execution.
Advocate review : approved {req['advocate_reviewed_at'][:10] if req['advocate_reviewed_at'] else ''}
Auditor review  : approved {req['auditor_reviewed_at'][:10] if req['auditor_reviewed_at'] else ''}

5. PAYMENT & REGISTRATION
The Buyer shall pay the consideration as agreed, and the parties shall
complete registration of the sale deed in accordance with the applicable
local registration laws.

6. GOVERNING LAW
This agreement shall be governed by the laws of India.

7. ACKNOWLEDGEMENT
By execution of this agreement, both parties confirm that they have read,
understood and agreed to the terms above.

____________________________          ____________________________
Seller (authorized signatory)               Buyer: {req['buyer_name']}

This document was generated automatically after dual review
(Advocate + Auditor) and is recorded in the platform audit log.
"""


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------
def _inr(value: Optional[int]) -> str:
    """Format an INR amount as a compact Indian-style string."""
    if value is None:
        return "—"
    v = int(value)
    if v >= 10000000:
        cr = v / 10000000
        return f"₹{cr:.2f} Cr"
    if v >= 100000:
        lk = v / 100000
        return f"₹{lk:.2f} L"
    return f"₹{v:,}"


def _type_label(t: Optional[str]) -> str:
    return {
        "land": "Land", "plot": "Plot", "flat": "Flat",
        "apartment": "Apartment",
    }.get(t, t or "—")