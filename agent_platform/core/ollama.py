"""Local inference runtime (L1 in the architecture).

Wraps Ollama's OpenAI-compatible API for chat and embeddings, plus a
ModelRegistry that maps task -> model + config + version.

Everything stays on the local machine. If Ollama is not reachable, the
client raises OllamaUnavailableError with a clear message — the platform
does NOT silently fall back to any external model.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import urllib.request
    import urllib.error
except ImportError:  # pragma: no cover
    pass


class OllamaUnavailableError(RuntimeError):
    pass


@dataclass
class ModelSpec:
    name: str
    temperature: float = 0.2
    max_tokens: int = 2048
    version: str = "1"


class ModelRegistry:
    """task -> model + config + version.

    The learning engine (future phase) promotes models here with
    provenance; for now it is populated from settings.
    """

    def __init__(self, default_model: str, temperature: float = 0.2,
                 overrides: Optional[Dict[str, str]] = None):
        self.default_model = default_model
        self.default_temperature = temperature
        self.overrides = overrides or {}
        self._specs: Dict[str, ModelSpec] = {}

    def spec_for(self, task: str, temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None) -> ModelSpec:
        model = self.overrides.get(task, self.default_model)
        spec = self._specs.get(model)
        if spec is None:
            spec = ModelSpec(
                name=model,
                temperature=self.default_temperature,
                version="1",
            )
            self._specs[model] = spec
        if temperature is not None:
            spec.temperature = temperature
        if max_tokens is not None:
            spec.max_tokens = max_tokens
        return spec

    def register(self, task: str, spec: ModelSpec) -> None:
        self._specs[spec.name] = spec
        self.overrides[task] = spec.name


class OllamaClient:
    """Thin client over Ollama's OpenAI-compatible /v1 endpoints."""

    def __init__(self, base_url: str, timeout: int = 300, max_retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    # ---------- low-level ----------

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/v1{path}"
        data = json.dumps(payload).encode("utf-8")
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                last_err = OllamaUnavailableError(f"HTTP {e.code} from Ollama: {body[:300]}")
                if 400 <= e.code < 500:
                    break  # client error, retrying won't help
            except Exception as e:  # URLError, timeout, etc.
                last_err = OllamaUnavailableError(f"Cannot reach Ollama at {self.base_url}: {e}")
            if attempt < self.max_retries:
                time.sleep(1.0 * (attempt + 1))
        raise last_err  # type: ignore[misc]

    # ---------- public API ----------

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/v1/models")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.base_url}/v1/models")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [m.get("id", "") for m in data.get("data", [])]
        except Exception:
            return []

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = self._post("/chat/completions", payload)
        return data["choices"][0]["message"]["content"]

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        data = self._post("/embeddings", {"model": model, "input": texts})
        # Ollama OpenAI-compat returns {"data": [{"embedding": [...]}, ...]}
        return [d["embedding"] for d in data["data"]]

    def embed_one(self, text: str, model: str) -> List[float]:
        return self.embed([text], model)[0]


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Robustly pull a JSON object out of a model response.

    Handles bare JSON, JSON fenced in ```json blocks, and JSON embedded
    in surrounding prose.
    """
    text = text.strip()
    # direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fenced block
    if "```" in text:
        start = text.find("```")
        rest = text[start + 3:]
        if rest.startswith("json"):
            rest = rest[4:]
        end = rest.find("```")
        if end != -1:
            candidate = rest[:end].strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    # first { ... last }
    lb, rb = text.find("{"), text.rfind("}")
    if lb != -1 and rb > lb:
        try:
            return json.loads(text[lb : rb + 1])
        except json.JSONDecodeError:
            pass
    return None


class MockOllamaClient:
    """Test double that mimics OllamaClient without any network.

    Returns canned responses; useful for unit tests and for running the
    platform in a dry-run mode before pulling models.
    """

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {}
        self.calls: List[Dict[str, Any]] = []

    def is_available(self) -> bool:
        return True

    def list_models(self) -> List[str]:
        return ["llama3.1:8b", "nomic-embed-text"]

    def chat(self, messages, model, temperature=0.2, max_tokens=2048, json_mode=False):
        self.calls.append({"model": model, "messages": messages, "json_mode": json_mode})
        # Match canned responses against the full prompt (system + user),
        # since agents put their instructions in the system message.
        full = " ".join(m.get("content", "") for m in messages)
        for key, resp in self.responses.items():
            if key in full:
                return resp
        if json_mode:
            return json.dumps({"answer": "mock answer", "confidence": 0.5})
        return "mock answer"

    def embed(self, texts, model):
        import hashlib
        import math
        out = []
        for t in texts:
            # Deterministic pseudo-embedding: derive a signed, centered
            # vector from the text so that unrelated texts have ~0 cosine
            # similarity (like real embeddings), while identical texts have
            # ~1.0. This keeps tests deterministic without a real model.
            h = hashlib.sha256(t.encode("utf-8")).digest()
            vec = []
            counter = 0
            while len(vec) < 768:
                hh = hashlib.sha256(h + counter.to_bytes(4, "big")).digest()
                for b in hh:
                    if len(vec) >= 768:
                        break
                    # map byte to [-1, 1]
                    vec.append((b / 255.0) * 2.0 - 1.0)
                counter += 1
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out

    def embed_one(self, text, model):
        return self.embed([text], model)[0]