"""Agent 4 — Document Intake & OCR Agent.

From the architecture:
  - receives scans, PDFs, photos, emails
  - keeps the original unchanged
  - OCR and field extraction
  - confidence + Unreviewed status
  - duplicate flag
  - routes the document

Phase 1 implementation:
  - Originals are stored untouched in data/documents/ (SHA-256 hash
    recorded for integrity + duplicate detection).
  - Text extraction: .txt/.md/.csv/.json directly; .pdf via pypdf when
    installed; images (.png/.jpg) via a pluggable OCR function (local
    model or Tesseract when available) — otherwise marked
    'ocr_unavailable' and routed for human review.
  - Field extraction uses the local model with JSON mode; every
    extracted field carries a confidence score.
  - Every ingested document starts with status 'unreviewed' and is
    flagged for human review of critical fields.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.base_agent import AgentContext, AgentResult, BaseAgent


@dataclass
class ExtractedField:
    name: str
    value: str
    confidence: float
    needs_review: bool = False


# Fields considered critical for a legal/compliance document
CRITICAL_FIELDS = {
    "party_name", "amount", "date", "deadline", "statute", "case_number",
    "account", "address", "signature",
}

TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".log", ".html", ".htm"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


class DocumentIntakeOcrAgent(BaseAgent):
    agent_id = "agent_4_document_intake_ocr"
    name = "Document Intake & OCR Agent"
    responsibility = (
        "Ingest scans/PDFs/photos/emails; keep originals unchanged; OCR and "
        "extract fields with confidence; mark Unreviewed; flag duplicates; "
        "route the document."
    )

    def __init__(self, services, ocr_fn=None):
        super().__init__(services)
        # ocr_fn: callable(bytes, ext) -> str  (pluggable: Tesseract, etc.)
        self.ocr_fn = ocr_fn

    # ---------- public entry ----------

    def ingest_file(self, file_path: str, ctx: AgentContext,
                    sensitivity: str = "internal",
                    doc_type: str = "upload") -> AgentResult:
        """Ingest a single file. `ctx.request` may carry extra instructions."""
        if not os.path.isfile(file_path):
            return AgentResult(self.agent_id, "error",
                               error=f"file not found: {file_path}")

        original_bytes = open(file_path, "rb").read()
        sha256 = hashlib.sha256(original_bytes).hexdigest()
        ext = os.path.splitext(file_path)[1].lower()
        name = os.path.basename(file_path)

        # 1. Duplicate check (by content hash)
        dup = self._find_duplicate(sha256, ctx)
        if dup:
            self._audit(ctx, "duplicate_detected",
                        detail={"file": name, "sha256": sha256,
                                "existing_doc": dup},
                        result="duplicate")
            return AgentResult(
                self.agent_id, "ok",
                answer=f"Duplicate document: identical content already stored as {dup}.",
                data={"duplicate_of": dup, "sha256": sha256, "routed": "none"},
            )

        # 2. Keep the original unchanged
        docs_dir = self.settings.resolve_path(self.settings.storage.documents_dir)
        os.makedirs(docs_dir, exist_ok=True)
        stored_name = f"{sha256[:16]}{ext}"
        stored_path = os.path.join(docs_dir, stored_name)
        with open(stored_path, "wb") as f:
            f.write(original_bytes)

        # 3. Extract text (OCR where needed)
        text, extraction_method, ocr_confidence = self._extract_text(
            original_bytes, ext, name
        )

        # 4. Field extraction (local model, JSON mode)
        fields = self._extract_fields(text, ctx)

        # 5. Classify sensitivity + provenance (local model, best-effort)
        sensitivity = self._classify_sensitivity(text, ctx, default=sensitivity)

        # 6. Store in knowledge base with status 'unreviewed'
        doc_id = self.knowledge.add_document(
            title=name,
            content=text[:20000],
            source=name,
            doc_type=doc_type,
            sensitivity=sensitivity,
            tenant=ctx.identity.tenant,
            status="unreviewed",
            metadata={
                "original_path": stored_path,
                "sha256": sha256,
                "extraction_method": extraction_method,
                "ocr_confidence": ocr_confidence,
                "fields": [f.__dict__ for f in fields],
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ctx.add_source(name)

        # 7. Critical fields -> human review
        critical = [f for f in fields if f.needs_review]
        approval_id = None
        if critical:
            req = self.approval.request(
                kind="document_review",
                title=f"Critical fields in {name} need review",
                payload={
                    "document_id": doc_id,
                    "fields": [f.__dict__ for f in critical],
                    "ocr_confidence": ocr_confidence,
                },
                requested_by=ctx.identity.username,
            )
            approval_id = req.id

        self._audit(ctx, "document_ingested",
                    detail={"doc_id": doc_id, "file": name,
                            "method": extraction_method,
                            "fields": len(fields),
                            "critical_fields": len(critical),
                            "sensitivity": sensitivity},
                    result="unreviewed")

        return AgentResult(
            self.agent_id, "ok",
            answer=(
                f"Document '{name}' ingested (status: unreviewed). "
                f"{len(fields)} fields extracted, {len(critical)} critical "
                f"field(s) flagged for review."
            ),
            data={
                "doc_id": doc_id,
                "sha256": sha256,
                "stored_path": stored_path,
                "extraction_method": extraction_method,
                "fields": [f.__dict__ for f in fields],
                "sensitivity": sensitivity,
                "routed": "stored_knowledge",
                "needs_review": bool(critical),
            },
            approval_id=approval_id,
            sources=[name],
        )

    # ---------- agent contract ----------

    def run(self, ctx: AgentContext) -> AgentResult:
        """When routed by the orchestrator, ingest files listed in
        ctx.state['files'] (paths), or answer a question about a file
        named in the request."""
        files: List[str] = ctx.state.get("files", [])
        if not files:
            # Try to find a file path inside the request text
            m = re.search(r"[\w./\\-]+\.(?:pdf|png|jpe?g|txt|md|csv|json|html|tif|tiff|bmp)",
                          ctx.request, re.I)
            if m:
                files = [m.group(0)]
        if not files:
            return AgentResult(
                self.agent_id, "error",
                error="No file provided. Pass file paths via state['files'] "
                      "or include a file path in the request.",
            )
        results = []
        for f in files:
            results.append(self.ingest_file(f, ctx))
        if len(results) == 1:
            return results[0]
        answers = "\n".join(r.answer or (r.error or "") for r in results)
        return AgentResult(
            self.agent_id,
            "ok" if all(r.ok for r in results) else "error",
            answer=answers,
            data={"documents": [r.data for r in results]},
            approval_id=results[0].approval_id,
        )

    # ---------- internals ----------

    def _find_duplicate(self, sha256: str, ctx: AgentContext) -> Optional[str]:
        rows = self.knowledge._conn.execute(
            "SELECT id, title FROM documents WHERE metadata LIKE ?",
            (f'%"sha256": "{sha256}"%',),
        ).fetchall()
        return rows[0]["id"] if rows else None

    def _extract_text(self, data: bytes, ext: str, name: str):
        """Returns (text, method, ocr_confidence)."""
        if ext in TEXT_EXTS:
            try:
                return data.decode("utf-8", errors="replace"), "text", 1.0
            except Exception:
                pass
        if ext == ".pdf":
            text = self._extract_pdf(data)
            if text:
                return text, "pdf_text", 0.95
            # Scanned PDF -> OCR path
            return self._ocr_fallback(data, ext, name)
        if ext in IMAGE_EXTS:
            return self._ocr_fallback(data, ext, name)
        # Email (.eml) — parse headers + body crudely
        if ext == ".eml":
            try:
                import email
                from email import policy
                msg = email.message_from_bytes(data, policy=policy.default)
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body += part.get_content()
                else:
                    body = msg.get_content()
                header = f"From: {msg.get('From')}\nTo: {msg.get('To')}\n" \
                         f"Date: {msg.get('Date')}\nSubject: {msg.get('Subject')}\n\n"
                return header + body, "email", 0.95
            except Exception:
                pass
        # Unknown binary
        return "", "unextractable", 0.0

    def _extract_pdf(self, data: bytes) -> str:
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n\n".join((p.extract_text() or "") for p in reader.pages)
        except ImportError:
            return ""
        except Exception:
            return ""

    def _ocr_fallback(self, data: bytes, ext: str, name: str):
        if self.ocr_fn is not None:
            try:
                text = self.ocr_fn(data, ext)
                if text:
                    return text, "ocr", 0.8
            except Exception:
                pass
        # Tesseract, if installed
        try:
            import pytesseract
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(data))
            text = pytesseract.image_to_string(img)
            if text.strip():
                return text, "ocr_tesseract", 0.8
        except Exception:
            pass
        return (
            f"[OCR UNAVAILABLE] Image document '{name}' could not be read "
            f"locally. Install an OCR engine (e.g. tesseract) or provide an "
            f"ocr_fn in the platform factory. Document is routed for manual review."
        ), "ocr_unavailable", 0.0

    def _extract_fields(self, text: str, ctx: AgentContext) -> List[ExtractedField]:
        if not text or text.startswith("[OCR UNAVAILABLE]"):
            return []
        system = (
            "You are a document field extractor for legal/compliance "
            "documents. Extract the fields present in the document. Respond "
            "with ONLY a JSON object: {\"fields\": [{\"name\": str, "
            "\"value\": str, \"confidence\": float 0..1}]}. Only extract "
            "fields actually present; do not invent values. Use names like: "
            "party_name, date, amount, deadline, case_number, statute, "
            "address, account, subject, reference."
        )
        parsed = self.ask_model_json(system, text[:12000])
        fields: List[ExtractedField] = []
        if parsed and isinstance(parsed.get("fields"), list):
            for f in parsed["fields"]:
                if not isinstance(f, dict) or "name" not in f or "value" not in f:
                    continue
                name = str(f["name"]).strip().lower()
                value = str(f["value"]).strip()
                try:
                    conf = max(0.0, min(1.0, float(f.get("confidence", 0.5))))
                except (TypeError, ValueError):
                    conf = 0.5
                needs_review = (
                    name in CRITICAL_FIELDS
                    or conf < 0.75
                )
                fields.append(ExtractedField(name=name, value=value,
                                             confidence=conf,
                                             needs_review=needs_review))
        return fields

    def _classify_sensitivity(self, text: str, ctx: AgentContext,
                              default: str) -> str:
        system = (
            "Classify the sensitivity of this document. Respond with ONLY a "
            "JSON object: {\"sensitivity\": one of \"public\", \"internal\", "
            "\"confidential\", \"restricted\", \"reason\": str}. "
            "Restricted = personal data, financial details, privileged legal "
            "material. Confidential = client/matter specifics. Internal = "
            "general business. Public = already public."
        )
        parsed = self.ask_model_json(system, text[:4000])
        if parsed and parsed.get("sensitivity") in self.settings.policy.sensitivity_levels:
            return parsed["sensitivity"]
        return default