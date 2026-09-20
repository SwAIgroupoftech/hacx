"""Incident detection and classification module.

Combines physical traffic signals (sudden speed drop, upstream queueing,
downstream flow starvation, stuck sensor detection) with environmental context
(weather, scheduled events) and labelled logs to classify incidents.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.detection.flags import classify_locally


def active_incidents(incidents_df: pd.DataFrame | None, ts: pd.Timestamp) -> pd.DataFrame:
    """Return ground-truth labelled incidents active at time ts."""
    if incidents_df is None or incidents_df.empty:
        return pd.DataFrame(columns=["incident_id", "segment_id", "incident_type", "severity", "lanes_blocked"])
    ts = pd.Timestamp(ts)
    mask = (incidents_df["start_time"] <= ts) & (incidents_df["end_time"] >= ts)
    return incidents_df[mask].copy()


def detect_incidents(
    flagged_df: pd.DataFrame,
    context: dict | None = None,
    labelled_inc: pd.DataFrame | None = None,
) -> list[dict]:
    """Extract and classify candidate incidents from flagged snapshot roads.

    Returns a list of incident candidate dicts ready for inclusion in the
    evidence packet and LLM reasoning.
    """
    if flagged_df.empty:
        return []

    context = context or {}
    rain = float(context.get("rain_intensity", 0.0) or 0.0)
    event_level = float(context.get("event_level", 0.0) or 0.0)

    # Index labelled incidents by segment_id if available
    lab_map = {}
    if labelled_inc is not None and not labelled_inc.empty:
        for r in labelled_inc.itertuples():
            lab_map[str(r.segment_id)] = r

    candidates = []
    for row in flagged_df.itertuples():
        seg = str(row.Index[1] if isinstance(row.Index, tuple) else row.Index)
        reasons = list(getattr(row, "reasons", []))
        speed = float(getattr(row, "speed", 0.0))
        free_flow = float(getattr(row, "free_flow", 60.0))
        ratio = speed / max(free_flow, 1.0)

        # Baseline rule-based classification
        default_class, default_conf = classify_locally(reasons, rain, event_level)

        item = {
            "segment_id": seg,
            "speed_kmh": round(speed, 1),
            "free_flow_kmh": round(free_flow, 1),
            "speed_ratio": round(ratio, 2),
            "reasons": reasons,
            "rule_based_class": default_class,
            "rule_based_confidence": default_conf,
        }

        # Correlate with labelled incidents if present
        if seg in lab_map:
            lab = lab_map[seg]
            item["labelled_incident"] = {
                "incident_id": str(getattr(lab, "incident_id", "")),
                "incident_type": str(getattr(lab, "incident_type", "")),
                "severity": int(getattr(lab, "severity", 1)),
                "lanes_blocked": int(getattr(lab, "lanes_blocked", 1)),
            }

        candidates.append(item)

    return candidates
