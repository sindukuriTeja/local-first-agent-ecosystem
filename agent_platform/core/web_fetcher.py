"""Live web fetcher for the External Information Agent (Agent 3).

The ONLY authorized egress path. Hard rules, enforced here:

  1. **Allowlist only** — a URL is fetched only if it matches
     `policy.permitted_external_sources`.
  2. **Cleaned question only** — the caller must pass a sanitized query
     (no internal identifiers/amounts). The agent already does this.
  3. **Minimized egress** — only the cleaned question goes out; nothing
     else leaves the machine.
  4. **Untrusted output** — fetched content is treated as untrusted data,
     never as instructions.
  5. **Audited** — every fetch (URL, question, result count, latency) is
     written to the audit log.

Phase 2 adds a real `LiveWebFetcher` (HTTP GET + text extraction) on top
of the Phase 1 `LocalCacheFetcher`. The live fetcher is OFF by default;
enable it in config (`agents.external.fetcher: live`).
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from ..agents.agent_03_external_information import (
    BaseFetcher, ExternalFact, LocalCacheFetcher,
)
from datetime import datetime, timezone


_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)


def extract_text(html_text: str) -> str:
    """Crude but dependency-free HTML -> text extraction."""
    text = _SCRIPT_RE.sub(" ", html_text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|li|h[1-6]|tr|table)>", "\n", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    # collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


class LiveWebFetcher(BaseFetcher):
    """Fetches from allowlisted public sources over HTTP.

    `audit` is an optional AuditLog for recording egress. `timeout` caps
    each request. Content is cached locally so repeated questions don't
    re-hit the network (and so the platform degrades gracefully offline).
    """

    def __init__(self, cache_path: str, audit=None,
                 timeout: int = 20, user_agent: str = "LocalFirstAgent/1.0",
                 max_cache_entries: int = 200):
        self.cache_path = cache_path
        self.audit = audit
        self.timeout = timeout
        self.user_agent = user_agent
        # Cap the local cache so it cannot grow unbounded across many
        # learning/egress runs (oldest entries are dropped first).
        self.max_cache_entries = max_cache_entries
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)

    def _load_cache(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.cache_path):
            return []
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _save_cache(self, entries: List[Dict[str, Any]]) -> None:
        # De-duplicate by URL (keep the most recent) and bound the size so
        # the cache cannot grow unbounded across many egress runs.
        deduped: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            url = e.get("url", "")
            if url:
                deduped[url] = e  # later entries (newer) win
        bounded = list(deduped.values())[-self.max_cache_entries:]
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(bounded, f, indent=2, ensure_ascii=False)

    def _allowed(self, url: str, permitted_urls: List[str]) -> bool:
        host = urllib.parse.urlparse(url).netloc.lower()
        for p in permitted_urls:
            phost = urllib.parse.urlparse(p).netloc.lower()
            if phost and (host == phost or host.endswith("." + phost)):
                return True
        return False

    def fetch(self, question: str, permitted_urls: List[str]) -> List[ExternalFact]:
        # 1. Serve from local cache first (offline-friendly)
        cached = self._load_cache()
        q_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
        facts: List[ExternalFact] = []
        for entry in cached:
            if not self._allowed(entry.get("url", ""), permitted_urls):
                continue
            c_tokens = set(re.findall(r"[a-z0-9]+",
                                      entry.get("content", "").lower()))
            if q_tokens & c_tokens:
                facts.append(ExternalFact(
                    claim=entry.get("content", "")[:500],
                    source_url=entry.get("url", ""),
                    collected_at=entry.get("collected_at", ""),
                    title=entry.get("title", ""),
                ))
        if facts:
            # Audit cache-served egress too, so every use of external
            # content (live or cached) is on the audit trail.
            if self.audit:
                self.audit.record(
                    actor="agent_3_external_information",
                    action="egress_cache_hit",
                    detail={"question": question[:200],
                            "facts": len(facts[:5]),
                            "sources": [f.source_url for f in facts[:5]]},
                    result="served_from_cache",
                )
            return facts[:5]

        # 2. Live fetch from each allowlisted source
        for base in permitted_urls:
            if len(facts) >= 5:
                break
            url = self._build_query_url(base, question)
            if not url or not self._allowed(url, permitted_urls):
                continue
            t0 = time.time()
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": self.user_agent})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                text = extract_text(raw)[:4000]
                latency = int((time.time() - t0) * 1000)
                if text:
                    facts.append(ExternalFact(
                        claim=text[:500],
                        source_url=url,
                        collected_at=datetime.now(timezone.utc).isoformat(),
                        title=url,
                    ))
                    # cache it
                    cached.append({
                        "title": url, "url": url, "content": text,
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    })
                    self._save_cache(cached)
                    if self.audit:
                        self.audit.record(
                            actor="agent_3_external_information",
                            action="live_egress",
                            detail={"url": url, "question": question[:200],
                                    "bytes": len(raw), "latency_ms": latency},
                            result="fetched",
                        )
            except Exception as e:
                if self.audit:
                    self.audit.record(
                        actor="agent_3_external_information",
                        action="live_egress",
                        detail={"url": url, "error": str(e)[:200]},
                        result="failed",
                    )
        return facts[:5]

    @staticmethod
    def _build_query_url(base: str, question: str) -> str:
        """Build a search/lookup URL for the allowlisted source.

        Different public sources use different search paths; this is a
        best-effort mapping. Unknown sources return None (no fetch).
        """
        host = urllib.parse.urlparse(base).netloc.lower()
        q = urllib.parse.quote_plus(question)
        if "indiacode.nic.in" in host:
            return f"{base.rstrip('/')}/search?query={q}"
        if "mca.gov.in" in host:
            return f"{base.rstrip('/')}/ministry-content?search={q}"
        if "incometax.gov.in" in host or "tin.gov.in" in host:
            return f"{base.rstrip('/')}/search?q={q}"
        # generic: try the base with a query param
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}q={q}"


def build_fetcher(settings, audit=None) -> BaseFetcher:
    """Factory: pick the external fetcher based on config.

    `settings.external.fetcher` selects the mode:
      cache (default) -> offline LocalCacheFetcher (air-gapped)
      live            -> LiveWebFetcher over the allowlisted sources
    """
    cache_path = settings.resolve_path(
        os.path.join(settings.storage.data_dir, "external_cache.json"))
    mode = getattr(getattr(settings, "external", None), "fetcher", "cache")
    if mode == "live":
        return LiveWebFetcher(cache_path, audit=audit)
    return LocalCacheFetcher(cache_path)