"""Minimal client for an OpenAI-compatible local server, with an on-disk cache.

Answers are constrained with a JSON schema, and caching makes re-runs cheap: the key
covers the model, the prompt, the schema, and the sampling settings.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests


class LLMError(RuntimeError):
    """Raised when the server cannot produce a usable answer."""


class LLMClient:
    def __init__(self, settings: dict, cache_dir: Path):
        self.base_url = settings["base_url"].rstrip("/")
        self.model_id = settings["model_id"]
        self.model_file = settings.get("gguf_file", "")
        self.temperature = settings["temperature"]
        self.seed = settings["seed"]
        self.max_tokens = settings["max_tokens"]
        self.timeout = settings["request_timeout_s"]
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.generation_seconds = 0.0

    def is_available(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/models", timeout=5).ok
        except requests.RequestException:
            return False

    def _cache_path(self, payload: dict) -> Path:
        key = json.dumps({"model_file": self.model_file, **payload}, sort_keys=True)
        return self.cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}.json"

    def complete_json(self, system: str, user: str, schema: dict, name: str = "answer") -> dict:
        """Return the parsed JSON answer. Reads from the cache when possible."""
        payload = {
            "model": self.model_id,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self.temperature,
            "seed": self.seed,
            "max_tokens": self.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "schema": schema, "strict": True},
            },
        }
        cache_file = self._cache_path(payload)
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))

        began = time.perf_counter()
        try:
            response = requests.post(f"{self.base_url}/chat/completions", json=payload, timeout=self.timeout)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            answer = json.loads(content)
        except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as error:
            raise LLMError(f"LLM request failed: {error}") from error
        self.generation_seconds += time.perf_counter() - began

        cache_file.write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding="utf-8")
        return answer
