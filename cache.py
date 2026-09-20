"""Disk cache keyed by a hash of the evidence packet + model name."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class DiskCache:
    def __init__(self, directory: Path, enabled: bool = True):
        self.directory = Path(directory)
        self.enabled = enabled
        if enabled:
            self.directory.mkdir(parents=True, exist_ok=True)

    def key(self, evidence: dict, model: str) -> str:
        blob = json.dumps({"model": model, "evidence": evidence}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]

    def get(self, evidence: dict, model: str) -> dict | None:
        if not self.enabled:
            return None
        p = self.directory / f"{self.key(evidence, model)}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def put(self, evidence: dict, model: str, response: dict) -> None:
        if not self.enabled:
            return
        p = self.directory / f"{self.key(evidence, model)}.json"
        p.write_text(json.dumps(response, indent=2, default=str), encoding="utf-8")
