"""Groq chat client for openai/gpt-oss-120b with schema, cache, retries, fallback."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from src.llm.cache import DiskCache
from src.llm.fallback import fallback_response
from src.llm.prompts import SYSTEM, user_message
from src.llm.schema import RESPONSE_SCHEMA
from src.llm.validation import ValidationError, validate_response


class GroqAnalyst:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else Path(".")
        self.model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "3500"))
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        self.retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self.max_calls = int(os.getenv("LLM_MAX_CALLS_PER_RUN", "20"))
        self.calls = 0
        cache_dir = Path(os.getenv("LLM_CACHE_DIR", str(self.root / "outputs" / "llm_cache")))
        enabled = os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true"
        self.cache = DiskCache(cache_dir, enabled)
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self._client = None

    def available(self) -> bool:
        return bool(self.api_key) and self.api_key != "your-api-key-here"

    def _client_obj(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key, timeout=self.timeout)
        return self._client

    def analyse(self, evidence: dict, use_llm: bool = True) -> dict:
        cached = self.cache.get(evidence, self.model)
        if cached:
            cached = dict(cached)
            cached["source"] = "cache"
            return cached

        if not use_llm or not self.available() or self.calls >= self.max_calls:
            return fallback_response(evidence)

        last_err = None
        for attempt in range(self.retries + 1):
            try:
                raw = self._complete(evidence)
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                validated = validate_response(parsed, evidence)
                validated["source"] = "llm"
                self.cache.put(evidence, self.model, validated)
                return validated
            except ValidationError as exc:
                last_err = exc
                break
            except Exception as exc:  # 429 / timeout / parse
                last_err = exc
                wait = _retry_after(exc, default=2 ** attempt)
                time.sleep(wait)
        fb = fallback_response(evidence)
        fb["fallback_reason"] = str(last_err)
        return fb

    def _complete(self, evidence: dict) -> str:
        self.calls += 1
        client = self._client_obj()
        kwargs = dict(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_message(evidence)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "traffic_sense_report",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
        )
        # gpt-oss reasoning: keep it low so one scenario stays inside free-tier tokens
        try:
            completion = client.chat.completions.create(
                **kwargs, reasoning_effort="low",
            )
        except TypeError:
            completion = client.chat.completions.create(**kwargs)
        return completion.choices[0].message.content or "{}"


def _retry_after(exc, default: float) -> float:
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) or {}
    val = headers.get("retry-after") or headers.get("Retry-After")
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default
