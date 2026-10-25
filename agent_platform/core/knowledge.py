"""Local knowledge store (L3 in the architecture).

Structured store (SQLite) + vector index (numpy) + keyword index
(BM25-style scoring) + knowledge-graph-lite (entity/relation tables).

Everything is access-scoped: every record carries a sensitivity level
and a tenant, and retrieval is filtered by the caller's permissions.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import yaml  # noqa: F401  (ensures dependency present for config)
except ImportError:  # pragma: no cover
    pass

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT,
    doc_type TEXT,
    sensitivity TEXT DEFAULT 'internal',
    tenant TEXT DEFAULT 'default',
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    source_doc TEXT,
    confidence REAL DEFAULT 1.0,
    sensitivity TEXT DEFAULT 'internal',
    tenant TEXT DEFAULT 'default',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT,
    tenant TEXT DEFAULT 'default',
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS relations (
    id TEXT PRIMARY KEY,
    source_entity TEXT NOT NULL,
    relation TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
CREATE INDEX IF NOT EXISTS idx_docs_tenant ON documents(tenant);
"""


@dataclass
class KnowledgeRecord:
    id: str
    title: str
    content: str
    source: str = ""
    doc_type: str = "note"
    sensitivity: str = "internal"
    tenant: str = "default"
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    record: KnowledgeRecord
    score: float
    matched_chunks: List[str] = field(default_factory=list)
    source: str = ""


_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Minimal English stopword list for keyword scoring. Removing these from
# query/document terms prevents common words ("the", "is", "for") from
# dominating BM25 scores and producing false-positive matches.
_STOPWORDS = frozenset("""
a an and are as at be but by for from had has have he her his i if in is it
its me my no nor not of on or our she so that the their them they this to
was we were what when where which who will with you your
""".split())


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _tokenize_no_stop(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class KnowledgeStore:
    """SQLite-backed store with hybrid (vector + keyword) retrieval."""

    def __init__(self, db_path: str, embedding_dim: int = 768, embedder=None):
        self.db_path = db_path
        self.embedding_dim = embedding_dim
        self.embedder = embedder  # callable(text) -> np.ndarray | None
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ---------- write path ----------

    def add_document(
        self,
        title: str,
        content: str,
        source: str = "",
        doc_type: str = "note",
        sensitivity: str = "internal",
        tenant: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "active",
    ) -> str:
        now = datetime.now(timezone.utc).isoformat()
        doc_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents (id, title, content, source, doc_type, "
                "sensitivity, tenant, status, created_at, updated_at, metadata) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (doc_id, title, content, source, doc_type, sensitivity, tenant,
                 status, now, now, json.dumps(metadata or {})),
            )
            # Chunk and index
            chunks = self._chunk(content)
            for i, chunk_text in enumerate(chunks):
                chunk_id = uuid.uuid4().hex
                embedding = None
                if self.embedder is not None:
                    try:
                        vec = self.embedder(chunk_text)
                        if vec is not None:
                            embedding = np.asarray(vec, dtype=np.float32).tobytes()
                    except Exception:
                        embedding = None
                self._conn.execute(
                    "INSERT INTO chunks (id, document_id, chunk_index, content, embedding) "
                    "VALUES (?,?,?,?,?)",
                    (chunk_id, doc_id, i, chunk_text, embedding),
                )
            self._conn.commit()
        return doc_id

    @staticmethod
    def _chunk(text: str, max_chars: int = 800, overlap: int = 100) -> List[str]:
        text = text.strip()
        if not text:
            return [""]
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            # try to break at a sentence boundary
            if end < len(text):
                cut = text.rfind(". ", start, end)
                if cut > start + max_chars // 2:
                    end = cut + 1
            chunks.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return [c for c in chunks if c]

    def add_fact(
        self,
        subject: str,
        predicate: str,
        object_: str,
        source_doc: str = "",
        confidence: float = 1.0,
        sensitivity: str = "internal",
        tenant: str = "default",
    ) -> str:
        fact_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO facts (id, subject, predicate, object, source_doc, "
                "confidence, sensitivity, tenant, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (fact_id, subject, predicate, object_, source_doc, confidence,
                 sensitivity, tenant, now),
            )
            self._conn.commit()
        return fact_id

    def add_entity(self, name: str, kind: str = "", tenant: str = "default",
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        eid = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO entities (id, name, kind, tenant, metadata) VALUES (?,?,?,?,?)",
                (eid, name, kind, tenant, json.dumps(metadata or {})),
            )
            self._conn.commit()
        return eid

    def add_relation(self, source_entity: str, relation: str, target_entity: str,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        rid = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO relations (id, source_entity, relation, target_entity, metadata) "
                "VALUES (?,?,?,?,?)",
                (rid, source_entity, relation, target_entity, json.dumps(metadata or {})),
            )
            self._conn.commit()
        return rid

    # ---------- read path ----------

    def get_document(self, doc_id: str) -> Optional[KnowledgeRecord]:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def list_documents(
        self,
        tenant: str = "default",
        sensitivity_max: str = "restricted",
        limit: int = 100,
    ) -> List[KnowledgeRecord]:
        levels = ["public", "internal", "confidential", "restricted"]
        max_idx = levels.index(sensitivity_max) if sensitivity_max in levels else len(levels) - 1
        allowed = levels[: max_idx + 1]
        placeholders = ",".join("?" * len(allowed))
        rows = self._conn.execute(
            f"SELECT * FROM documents WHERE tenant = ? AND sensitivity IN ({placeholders}) "
            f"AND status = 'active' ORDER BY updated_at DESC LIMIT ?",
            [tenant, *allowed, limit],
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def search(
        self,
        query: str,
        tenant: str = "default",
        sensitivity_max: str = "restricted",
        top_k: int = 6,
        keyword_weight: float = 0.4,
        vector_weight: float = 0.6,
        min_score: float = 0.25,
    ) -> List[RetrievalResult]:
        """Hybrid retrieval: keyword (BM25-style) + dense vector cosine."""
        levels = ["public", "internal", "confidential", "restricted"]
        max_idx = levels.index(sensitivity_max) if sensitivity_max in levels else len(levels) - 1
        allowed = levels[: max_idx + 1]
        placeholders = ",".join("?" * len(allowed))

        rows = self._conn.execute(
            f"SELECT d.*, c.content AS chunk_content, c.embedding FROM documents d "
            f"JOIN chunks c ON c.document_id = d.id "
            f"WHERE d.tenant = ? AND d.sensitivity IN ({placeholders}) AND d.status = 'active'",
            [tenant, *allowed],
        ).fetchall()

        if not rows:
            return []

        # Group chunks by document
        docs: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            d = docs.setdefault(r["id"], {
                "row": r,
                "chunks": [],
                "chunk_embeddings": [],
            })
            d["chunks"].append(r["chunk_content"])
            emb = r["embedding"] if "embedding" in r.keys() else None
            d["chunk_embeddings"].append(
                np.frombuffer(emb, dtype=np.float32) if emb else None
            )

        query_tokens = _tokenize_no_stop(query)
        # Document frequency for BM25
        n_docs = len(docs)
        df: Dict[str, int] = {}
        doc_tokens: Dict[str, List[str]] = {}
        for did, d in docs.items():
            toks = _tokenize_no_stop(" ".join(d["chunks"]))
            doc_tokens[did] = toks
            for t in set(toks):
                df[t] = df.get(t, 0) + 1

        avgdl = (sum(len(t) for t in doc_tokens.values()) / max(n_docs, 1)) or 1.0
        k1, b = 1.5, 0.75

        results: List[RetrievalResult] = []
        query_vec = None
        if self.embedder is not None:
            try:
                query_vec = np.asarray(self.embedder(query), dtype=np.float32)
            except Exception:
                query_vec = None

        for did, d in docs.items():
            toks = doc_tokens[did]
            # BM25
            bm25 = 0.0
            for q in query_tokens:
                if q not in df:
                    continue
                idf = math.log(1 + (n_docs - df[q] + 0.5) / (df[q] + 0.5))
                tf = toks.count(q)
                denom = tf + k1 * (1 - b + b * len(toks) / avgdl)
                bm25 += idf * (tf * (k1 + 1)) / denom
            norm_bm25 = bm25 / (1 + bm25) if bm25 > 0 else 0.0

            # Vector
            vec_score = 0.0
            if query_vec is not None:
                best = 0.0
                for emb in d["chunk_embeddings"]:
                    if emb is None or emb.size == 0:
                        continue
                    denom = (np.linalg.norm(query_vec) * np.linalg.norm(emb))
                    if denom > 0:
                        cos = float(np.dot(query_vec, emb) / denom)
                        best = max(best, cos)
                vec_score = max(0.0, best)

            # Adaptive weighting: when no vector is available (no embedder
            # or no stored embedding), the keyword score stands alone
            # instead of being scaled down by keyword_weight.
            if query_vec is None or vec_score == 0.0:
                score = norm_bm25
            else:
                score = keyword_weight * norm_bm25 + vector_weight * vec_score
            if score >= min_score:
                row = d["row"]
                rec = self._row_to_record(row)
                matched = [c for c in d["chunks"] if any(q in c.lower() for q in query_tokens)][:3]
                results.append(RetrievalResult(
                    record=rec, score=round(score, 4), matched_chunks=matched,
                    source=rec.source,
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def facts_for(self, subject: str, tenant: str = "default") -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE subject = ? AND tenant = ? ORDER BY created_at DESC",
            (subject, tenant),
        ).fetchall()
        return [dict(r) for r in rows]

    def entities(self, tenant: str = "default") -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM entities WHERE tenant = ?", (tenant,)
        ).fetchall()
        return [dict(r) for r in rows]

    def relations_for(self, entity_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM relations WHERE source_entity = ? OR target_entity = ?",
            (entity_id, entity_id),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- governance ----------

    def invalidate_document(self, doc_id: str) -> int:
        """Right-to-forget: mark a document and its chunks as deleted.

        Provenance-based propagation: any fact citing this document is
        also invalidated. Returns the number of affected facts.
        """
        with self._lock:
            self._conn.execute(
                "UPDATE documents SET status = 'deleted', updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), doc_id),
            )
            cur = self._conn.execute(
                "UPDATE facts SET confidence = 0.0 WHERE source_doc = ?", (doc_id,)
            )
            self._conn.commit()
            return cur.rowcount

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> KnowledgeRecord:
        return KnowledgeRecord(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            source=row["source"] or "",
            doc_type=row["doc_type"] or "note",
            sensitivity=row["sensitivity"] or "internal",
            tenant=row["tenant"] or "default",
            status=row["status"] or "active",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def close(self):
        self._conn.close()