"""Template advisories used when Groq is missing or a response fails validation."""
from __future__ import annotations

from src.detection.flags import classify_locally
from src.llm.schema import HORIZONS


def fallback_response(evidence: dict) -> dict:
    rain = (evidence.get("context") or {}).get("rain_intensity") or 0
    event = (evidence.get("context") or {}).get("event_level") or 0
    forecasts, incidents, advisories = [], [], []
    for f in evidence.get("flagged", []):
        seg = f["segment_id"]
        loc = f.get("forecast_local") or {}
        for h in HORIZONS:
            rec = loc.get(str(h)) or {}
            forecasts.append({
                "segment_id": seg,
                "horizon_min": h,
                "speed_kmh": rec.get("chosen") if rec.get("chosen") is not None else f.get("speed_kmh"),
                "confidence": 0.45,
                "rationale": f"Local {rec.get('chosen_model', 'persistence')} forecast from evidence.",
            })
        klass, conf = classify_locally(f.get("reasons") or [], rain, event)
        incidents.append({
            "segment_id": seg,
            "incident_class": klass,
            "confidence": conf,
            "rationale": "Rule-based class from flags: " + ", ".join(f.get("reasons") or []),
        })

    for d in evidence.get("diversions", []):
        alts = [a for a in d.get("alternates") or [] if a.get("usable")]
        via = (alts[0]["via"] if alts else [])
        save = alts[0]["expected_saving_min"] if alts else 0
        advisories.append({
            "title": f"Divert around {d['blocked_segment']}",
            "action": "Advise drivers onto the first feasible alternate; do not change signals.",
            "affected_segments": [d["blocked_segment"]],
            "diversion": via,
            "expected_saving_min": save,
            "confidence": 0.5 if via else 0.3,
            "evidence": f"Reasons: {', '.join(d.get('reasons') or [])}",
        })

    infra = []
    for p in evidence.get("infrastructure_candidates", [])[:5]:
        before, after = p.get("delay_before_min") or 0, p.get("delay_after_min") or 0
        pct = (100 * (before - after) / before) if before else 0
        infra.append({
            "candidate_id": p["candidate_id"],
            "segment_id": p["segment_id"],
            "intervention": p.get("intervention_type") or "capacity_upgrade",
            "rationale": "BPR estimate from local code; simulated only.",
            "estimated_delay_reduction_pct": round(pct, 1),
        })

    n = len(evidence.get("flagged", []))
    return {
        "summary": (
            f"Template fallback (no LLM or validation failed): {n} flagged roads. "
            "ADVISORY ONLY - SIMULATED."
        ),
        "forecasts": forecasts,
        "incidents": incidents,
        "advisories": advisories,
        "infrastructure": infra,
        "source": "fallback",
    }
