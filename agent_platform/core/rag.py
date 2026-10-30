"""Governed RAG service — the single documentation-retrieval path.

This is the "ask the documentation" layer. Every portal role (employee,
auditor, advocate/counsel, client, tenant, management, admin) reads
through the SAME governed knowledge store, and the SAME scope rules the
portal document lists already enforce:

  * sensitivity ceiling   (role -> max level)
  * document-type filter  (e.g. auditor only sees compliance/audit docs)
  * tenant isolation
  * matter / client / parcel scope (assigned work)

On top of the document store it also exposes the real-estate property
inventory (mirrored into the knowledge store as ``property`` documents),
so property questions are answered from the same RAG path as everything
else, with citations.

It answers groundedly: retrieve scoped chunks, then either (a) ask the
local model to answer from that evidence with citations, or (b) when the
local model is offline, return the best-matching evidence verbatim. This
is the same grounded pattern the learning engine's answerer uses, so the
RAG path and the eval path stay consistent.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .auth import PORTAL_DOC_TYPES
from .knowledge import RetrievalResult

# ---------------------------------------------------------------------------
# Scope rules — single source of truth
# ---------------------------------------------------------------------------


def _meta(doc) -> Dict[str, Any]:
    md = getattr(doc, "metadata", None) or {}
    if isinstance(md, str):
        try:
            md = json.loads(md)
        except (ValueError, TypeError):
            md = {}
    return md


def doc_in_scope(user, doc) -> bool:
    """Single source of truth for matter/client/parcel scoping.

    Mirrors the portal's per-role scope rules exactly, so a document the
    user can see in their portal list is the same document they can
    retrieve through RAG. Firm-wide roles (management / admin) see
    everything; the auditor is handled by its document-type filter;
    client / tenant / employee / counsel are scoped by assignment.
    """
    md = _meta(doc)
    if user.portal in ("management", "admin"):
        return True
    if user.portal == "auditor":
        # auditors only get explicitly compliance/audit-labelled docs
        return doc.doc_type in ("compliance", "audit", "case_analysis", "tax")
    if user.portal == "client":
        client = md.get("client")
        return (not client) or (not user.clients) or (client in user.clients)
    if user.portal == "tenant":
        parcel = md.get("parcel")
        return (not parcel) or (not user.parcels) or (parcel in user.parcels)
    # employee / counsel: matter + client assignment
    matter = md.get("matter")
    client = md.get("client")
    if matter and user.matters and matter not in user.matters:
        return False
    if client and user.clients and client not in user.clients:
        return False
    return True


# ---------------------------------------------------------------------------
# RAG service
# ---------------------------------------------------------------------------


class RAGService:
    """Scoped, grounded retrieval + answer over the governed knowledge
    store, including the mirrored property inventory."""

    def __init__(self, platform):
        self.p = platform
        # Cache the model-availability probe for the lifetime of the
        # service: an offline Ollama must not make every RAG query wait
        # out the full client timeout + retries.
        self._availability_cache: Optional[bool] = None

    # ---- scoping ---------------------------------------------------------
    def _doc_types_for(self, user) -> Optional[List[str]]:
        return PORTAL_DOC_TYPES.get(user.portal)

    def _model_available(self) -> bool:
        if self._availability_cache is None:
            try:
                self._availability_cache = bool(self.p.services.ollama.is_available())
            except Exception:
                self._availability_cache = False
        return self._availability_cache

    # ---- retrieval -------------------------------------------------------
    def search(self, user, query: str, top_k: Optional[int] = None,
               min_score: Optional[float] = None) -> List[RetrievalResult]:
        """Scoped hybrid retrieval. Returns only documents the user may
        read (sensitivity ceiling + doc-type filter + matter/client/parcel
        scope), in score order."""
        settings = self.p.settings
        top_k = top_k or settings.retrieval.top_k
        min_score = (settings.retrieval.min_score if min_score is None
                     else min_score)
        results = self.p.knowledge.search(
            query,
            tenant=user.tenant,
            sensitivity_max=user.max_sensitivity,
            top_k=top_k,
            keyword_weight=settings.retrieval.keyword_weight,
            vector_weight=settings.retrieval.vector_weight,
            min_score=min_score,
            doc_types=self._doc_types_for(user),
        )
        # Apply the assignment scope (matter/client/parcel). The doc-type
        # filter is already applied at the SQL level.
        return [r for r in results if doc_in_scope(user, r.record)]

    def _source_view(self, r: RetrievalResult) -> Dict[str, Any]:
        chunk = r.matched_chunks[0] if r.matched_chunks else r.record.content
        return {
            "source": r.record.source,
            "title": r.record.title,
            "doc_type": r.record.doc_type,
            "sensitivity": r.record.sensitivity,
            "score": round(r.score, 4),
            "excerpt": (chunk or "")[:320],
        }

    # ---- grounded answer -------------------------------------------------
    def answer(self, user, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """Answer a question grounded in the user's scoped documents.

        Returns a dict with the answer text, the cited sources, and flags
        describing how the answer was produced (``grounded`` = evidence
        found, ``model`` = a local model produced the answer vs. a
        verbatim evidence fallback when offline).
        """
        results = self.search(user, query, top_k)
        sources = [self._source_view(r) for r in results]
        if not results:
            return {
                "answer": "No matching documents found in your accessible scope.",
                "sources": [],
                "grounded": False,
                "model": False,
            }

        evidence_blocks = []
        for i, r in enumerate(results, 1):
            chunk = r.matched_chunks[0] if r.matched_chunks else r.record.content
            evidence_blocks.append(f"[{i}] (source: {r.record.source}) {chunk}")
        evidence = "\n\n".join(evidence_blocks)

        if not self._model_available():
            best = results[0]
            snippet = (best.matched_chunks[0] if best.matched_chunks
                       else best.record.content)
            return {
                "answer": snippet,
                "sources": sources,
                "grounded": True,
                "model": False,
            }

        system = (
            "You are a documentation assistant for a legal/compliance firm. "
            "Answer the user's question using ONLY the provided evidence from "
            "the firm's knowledge base. Be concise and factual. Cite the "
            "source(s) you used in parentheses, e.g. (source: seed-doc.txt). "
            "If the evidence does not contain the answer, say exactly: "
            "'Not found in the available documents.' Do not invent facts."
        )
        user_msg = f"Evidence:\n{evidence}\n\nQuestion: {query}"
        try:
            ans = self.p.services.ollama.chat(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user_msg}],
                model=self.p.services.registry.default_model,
                temperature=0.0,
                max_tokens=400,
            )
            return {"answer": ans, "sources": sources,
                    "grounded": True, "model": True}
        except Exception:
            best = results[0]
            snippet = (best.matched_chunks[0] if best.matched_chunks
                       else best.record.content)
            return {"answer": snippet, "sources": sources,
                    "grounded": True, "model": False}


# ---------------------------------------------------------------------------
# Property inventory mirror
# ---------------------------------------------------------------------------


def _property_to_text(prop: Dict[str, Any]) -> str:
    """Render a property row as natural-language text so keyword + vector
    retrieval match the way a person would ask about it."""
    price = prop.get("price_inr")
    price_str = f"INR {price:,}" if price else "price on request"
    per_sqft = prop.get("price_per_sqft")
    per_str = f" (INR {per_sqft:,} per sqft)" if per_sqft else ""
    beds = prop.get("bedrooms")
    beds_str = f"{beds} BHK, " if beds else ""
    baths = prop.get("bathrooms")
    baths_str = f"{baths} bathrooms, " if baths else ""
    return (
        f"Property {prop['property_code']}: {prop['title']}. "
        f"Type: {prop['type']}. Location: {prop['locality']}, {prop['city']}. "
        f"Area: {prop.get('area_sqft', 'N/A')} sqft. "
        f"Price: {price_str}{per_str}. "
        f"{beds_str}{baths_str}facing {prop.get('facing', 'N/A')}. "
        f"Ownership: {prop.get('ownership', 'N/A')}. "
        f"Status: {prop['status']}. "
        f"{prop.get('description', '')}"
    ).strip()


def sync_properties_to_knowledge(platform) -> int:
    """Mirror the property inventory into the knowledge store so property
    data is searchable through the same governed RAG path as every other
    document.

    Each property becomes a document with ``doc_type='property'`` and
    ``source='property:<code>'``. Upserted by source, so repeated syncs
    never duplicate a row. Sensitivity is ``internal`` (the inventory is
    internal firm data). Returns the number of documents written.
    """
    store = platform.properties
    if store is None:
        return 0
    count = 0
    for prop in store.list_properties(limit=100000):
        platform.knowledge.upsert_document(
            title=f"{prop['property_code']} — {prop['title']}",
            content=_property_to_text(prop),
            source=f"property:{prop['property_code']}",
            doc_type="property",
            sensitivity="internal",
            tenant="default",
            metadata={
                "property_code": prop["property_code"],
                "city": prop["city"],
                "locality": prop["locality"],
                "type": prop["type"],
                "status": prop["status"],
                "price_inr": prop.get("price_inr"),
                "area_sqft": prop.get("area_sqft"),
            },
        )
        count += 1
    return count