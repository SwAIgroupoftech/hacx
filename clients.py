"""Groq LLM Client for TrafficSense.

Uses openai/gpt-oss-120b (or configured model) with constrained JSON schema decoding,
disk caching, rate-limit exponential backoff, schema validation, and graceful fallback.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.llm.fallback import fallback_response
from src.llm.prompts import SYSTEM, user_message
from src.llm.schema import RESPONSE_SCHEMA
from src.llm.validation import ValidationError, validate_response

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


class GroqClient:
    """Client for Groq LLM API with caching, retry logic, and validation."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        load_dotenv(self.root / ".env")
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        self.model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "800"))
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self.cache_enabled = os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true"
        cache_dir_rel = os.getenv("LLM_CACHE_DIR", "outputs/llm_cache")
        self.cache_dir = self.root / cache_dir_rel
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._client = None
        if self.api_key and self.api_key != "your-api-key-here":
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key, timeout=self.timeout)
            except Exception as e:
                logger.warning("Failed to initialize Groq client: %s", e)

    def _cache_key(self, evidence: dict[str, Any]) -> str:
        serialized = json.dumps(evidence, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _get_from_cache(self, key: str, evidence: dict[str, Any]) -> dict[str, Any] | None:
        if not self.cache_enabled:
            return None
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                validated = validate_response(cached, evidence)
                validated["source"] = "groq (cached)"
                return validated
            except Exception as e:
                logger.warning("Invalid cache entry %s: %s", key, e)
        return None

    def _save_to_cache(self, key: str, response: dict[str, Any]) -> None:
        if not self.cache_enabled:
            return
        cache_file = self.cache_dir / f"{key}.json"
        try:
            cache_file.write_text(json.dumps(response, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save response to cache %s: %s", key, e)

    def generate(self, evidence: dict[str, Any]) -> dict[str, Any]:
        """Generate structured intelligence from an evidence packet."""
        cache_key = self._cache_key(evidence)
        cached = self._get_from_cache(cache_key, evidence)
        if cached is not None:
            return cached

        if not self._client:
            fb = fallback_response(evidence)
            fb["fallback_reason"] = "GROQ_API_KEY not configured or client initialization failed"
            return fb

        prompt = user_message(evidence)
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ]

        # Use Groq structured outputs with schema
        fmt_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "traffic_response",
                "schema": RESPONSE_SCHEMA,
            },
        }

        last_error = None
        for attempt in range(1, self.max_retries + 2):
            try:
                # Attempt strict schema decoding
                try:
                    resp = self._client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format=fmt_schema,
                    )
                except Exception as schema_err:
                    logger.info("json_schema format failed, falling back to json_object: %s", schema_err)
                    resp = self._client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format={"type": "json_object"},
                    )

                raw_text = resp.choices[0].message.content or "{}"
                parsed = json.loads(raw_text)
                validated = validate_response(parsed, evidence)
                validated["source"] = f"groq ({self.model})"
                self._save_to_cache(cache_key, validated)
                return validated
            except ValidationError as ve:
                logger.warning("Validation error on attempt %d: %s", attempt, ve)
                last_error = f"Validation failed: {ve}"
                break
            except Exception as exc:
                last_error = f"API error: {exc}"
                logger.warning("Groq API error on attempt %d: %s", attempt, exc)
                # If TPM limit exceeded (413), try high-throughput versatile model
                if "413" in str(exc):
                    logger.info("Token limit reached for %s, trying high-capacity model...", self.model)
                    try:
                        resp = self._client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=messages,
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                            response_format=fmt_schema,
                        )
                        raw_text = resp.choices[0].message.content or "{}"
                        parsed = json.loads(raw_text)
                        validated = validate_response(parsed, evidence)
                        validated["source"] = "groq (llama-3.3-70b-versatile)"
                        self._save_to_cache(cache_key, validated)
                        return validated
                    except Exception as alt_exc:
                        logger.warning("High-capacity model also failed: %s", alt_exc)

                if "429" in str(exc) or "rate" in str(exc).lower():
                    sleep_sec = 2.0 * attempt
                    logger.info("Rate limited. Backing off for %.1f seconds...", sleep_sec)
                    time.sleep(sleep_sec)
                elif attempt <= self.max_retries:
                    time.sleep(1.0 * attempt)

        # Fallback if calls failed
        fb = fallback_response(evidence)
        fb["fallback_reason"] = last_error or "Unknown failure"
        return fb

    def chat(self, user_query: str, chat_history: list[dict], context_summary: dict) -> str:
        """Answer a conversational question about the current traffic conditions."""
        if not self._client:
            return "AI Traffic Copilot is offline (GROQ_API_KEY not configured)."

        chat_system = (
            "You are TrafficSense Copilot, an intelligent, helpful traffic operations assistant.\n"
            "You help operators, city officials, and drivers understand what is happening on the roads.\n\n"
            "Guidelines:\n"
            "1. Speak in friendly, clear, plain English without jargon.\n"
            "2. DO NOT use confusing road segment IDs by themselves (e.g. avoid saying just 'R0360'). Always explain what the road is using the context, for example: 'the 2-lane arterial corridor (R0360)' or 'expressway feeder R0070'.\n"
            "3. Clearly explain current congestion, active accidents/lane closures, recommended diversions, and long-term improvements.\n"
            "4. Keep explanations concise, easy to read, with bullet points and bold highlights.\n"
            "5. Remind the user if asked that all advisories are simulated.\n\n"
            f"CURRENT SIMULATED NETWORK SNAPSHOT:\n{json.dumps(context_summary, default=str)}"
        )

        messages = [{"role": "system", "content": chat_system}]
        for msg in chat_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_query})

        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=600,
            )
            raw_res = resp.choices[0].message.content or "No response received."
            return _clean_unicode(raw_res)
        except Exception as exc:
            logger.warning("Chat error on primary model: %s", exc)
            try:
                resp = self._client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=600,
                )
                raw_res = resp.choices[0].message.content or "No response received."
                return _clean_unicode(raw_res)
            except Exception as e2:
                return f"Traffic Copilot unavailable at the moment ({e2}). Please consult the visual map and alerts."


def _clean_unicode(text: str) -> str:
    if not text:
        return text
    return (
        text.replace("\u202f", " ")
        .replace("\u00a0", " ")
        .replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "--")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def call_groq(evidence: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Convenience function to generate and return intelligence report for evidence."""
    client = GroqClient(root=root)
    return client.generate(evidence)


def chat_with_copilot(query: str, chat_history: list[dict], context_summary: dict, root: Path | None = None) -> str:
    """Convenience function for conversational traffic Q&A."""
    client = GroqClient(root=root)
    return client.chat(query, chat_history, context_summary)

