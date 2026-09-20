"""Reject or sanitize LLM answers that cite unknown roads or impossible speeds."""
from __future__ import annotations

import re
from typing import Any

from src.llm.schema import ALLOWED_CLASSES, HORIZONS


class ValidationError(ValueError):
    pass


def _flatten_strings(val: Any) -> list[str]:
    res = []
    if isinstance(val, str):
        return [val]
    if isinstance(val, (list, tuple)):
        for item in val:
            if isinstance(item, (list, tuple)):
                res.extend(_flatten_strings(item))
            elif item is not None:
                res.append(str(item))
    return res


def _clean_segment_tokens(val: Any) -> list[str]:
    raw_list = _flatten_strings(val)
    out = []
    for item in raw_list:
        # Split tokens if model passed concatenated paths like R001->R002 or R001, R002
        parts = re.split(r"->|>|,|\s+", str(item))
        for p in parts:
            clean = p.strip().strip("'\"[]()")
            if clean:
                out.append(clean)
    return out


def validate_response(resp: dict, evidence: dict) -> dict:
    if not isinstance(resp, dict):
        raise ValidationError("response is not an object")
    for key in ("forecasts", "incidents", "advisories", "infrastructure", "summary"):
        if key not in resp:
            raise ValidationError(f"missing {key}")

    known = set()
    for f in evidence.get("flagged", []):
        if "segment_id" in f and f["segment_id"] is not None:
            known.add(str(f["segment_id"]))
    for b in evidence.get("bottlenecks", []):
        if "segment_id" in b and b["segment_id"] is not None:
            known.add(str(b["segment_id"]))
    for d in evidence.get("diversions", []):
        if "blocked_segment" in d and d["blocked_segment"] is not None:
            known.add(str(d["blocked_segment"]))

    ff = {str(f["segment_id"]): f.get("free_flow_kmh") for f in evidence.get("flagged", [])}

    for row in resp.get("forecasts", []):
        sid = str(row.get("segment_id")).strip()
        row["segment_id"] = sid
        if sid not in known:
            raise ValidationError(f"unknown forecast segment {sid}")
        if row.get("horizon_min") not in HORIZONS:
            raise ValidationError(f"bad horizon {row.get('horizon_min')}")
        spd, cap = row.get("speed_kmh"), ff.get(sid)
        if spd is None or spd < 0:
            raise ValidationError("speed must be >= 0")
        if cap and spd > cap * 1.15:
            # Clip safely if model slightly overshot free-flow
            row["speed_kmh"] = round(float(cap), 2)
        conf = row.get("confidence")
        if conf is None or not (0 <= conf <= 1):
            row["confidence"] = 0.5

    for row in resp.get("incidents", []):
        sid = str(row.get("segment_id")).strip()
        row["segment_id"] = sid
        if sid not in known:
            raise ValidationError(f"unknown incident segment {sid}")
        if row.get("incident_class") not in ALLOWED_CLASSES:
            row["incident_class"] = "unclassified_anomaly"
        conf = row.get("confidence")
        if conf is None or not (0 <= conf <= 1):
            row["confidence"] = 0.5

    allowed_via = set()
    for d in evidence.get("diversions", []):
        for alt in d.get("alternates", []):
            for v in (alt.get("via") or []):
                for token in _clean_segment_tokens(v):
                    allowed_via.add(token)
        if d.get("blocked_segment"):
            allowed_via.add(str(d["blocked_segment"]).strip())

    for row in resp.get("advisories", []):
        aff_clean = _clean_segment_tokens(row.get("affected_segments"))
        div_clean = _clean_segment_tokens(row.get("diversion"))

        # Keep only segments that are valid roads
        row["affected_segments"] = [s for s in aff_clean if s in known or s in allowed_via]
        if not row["affected_segments"] and aff_clean:
            raise ValidationError(f"advisory cites unknown segment {aff_clean}")

        if allowed_via:
            row["diversion"] = [s for s in div_clean if s in allowed_via or s in known]
        else:
            row["diversion"] = div_clean

    known_plan = {str(p["candidate_id"]) for p in evidence.get("infrastructure_candidates", [])}
    for row in resp.get("infrastructure", []):
        cid = str(row.get("candidate_id")).strip()
        row["candidate_id"] = cid
        if known_plan and cid not in known_plan:
            raise ValidationError(f"unknown candidate_id {cid}")

    return resp
