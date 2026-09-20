"""Flag congested, anomalous and likely-incident roads at one replay instant.

Uses only the FeatureBuilder row for timestamp t (no look-ahead). Reasons are
plain strings so they can go straight into the evidence JSON.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def robust_z(value: np.ndarray, typical: np.ndarray) -> np.ndarray:
    """(x - typical) / (1.4826 * MAD of (x-typical) across roads). MAD of 0 -> 0."""
    resid = value - typical
    mad = np.nanmedian(np.abs(resid - np.nanmedian(resid)))
    scale = 1.4826 * mad
    if not np.isfinite(scale) or scale < 1e-6:
        return np.zeros_like(resid, dtype="float32")
    return (resid / scale).astype("float32")


def flag_snapshot(frame: pd.DataFrame, cfg: dict, max_items: int = 8) -> pd.DataFrame:
    """Return the worst flagged roads at this instant, with a `reasons` column."""
    cong = cfg.get("congestion", {})
    anom = cfg.get("anomaly", {})
    inc = cfg.get("incident", {}).get("rules", {})
    ratio_th = float(cong.get("speed_ratio_threshold", 0.50))
    severe_th = float(cong.get("severe_speed_ratio_threshold", 0.30))
    z_th = float(anom.get("robust_z_threshold", 3.5))
    drop_ratio = float(inc.get("sudden_drop_ratio", 0.40))

    out = frame.copy()
    speed = out["speed"].to_numpy()
    hist = out["speed_hist_now"].to_numpy()
    ratio = out["ratio"].to_numpy()
    z = robust_z(speed, hist)
    out["speed_z"] = z

    # 10 minutes = 2 lag steps of 5 min; features.py stores speed_d2 as 10-min change
    drop10 = out["speed_d2"].to_numpy() if "speed_d2" in out else np.zeros(len(out))
    sudden = (drop10 <= -drop_ratio * np.clip(speed - drop10, 1.0, None)) & np.isfinite(drop10)

    rec_tol = float(anom.get("recurring_vs_nonrecurring_tolerance", 0.15))
    near_baseline = np.abs(speed - hist) <= rec_tol * np.clip(hist, 1.0, None)

    reasons = []
    scores = []
    for i, row in enumerate(out.itertuples()):
        r = []
        if np.isfinite(ratio[i]) and ratio[i] < severe_th:
            r.append("severe_congestion")
        elif np.isfinite(ratio[i]) and ratio[i] < ratio_th:
            r.append("congestion")
        if np.isfinite(z[i]) and z[i] <= -z_th:
            r.append("speed_anomaly")
        if sudden[i]:
            r.append("sudden_speed_drop")
        if row.inc_active > 0:
            r.append("labelled_incident")
        if row.roadwork > 0:
            r.append("roadworks")
        if "up_ratio_d3" in out.columns and np.isfinite(row.up_ratio_d3) and row.up_ratio_d3 < -0.15:
            r.append("upstream_queue_growth")
        if "up_ratio" in out.columns and np.isfinite(row.up_ratio) and row.up_ratio < ratio_th:
            r.append("upstream_congested")
        if r and "congestion" in r and near_baseline[i] and "labelled_incident" not in r:
            r.append("recurring_pattern")
        elif r and "congestion" in r and not near_baseline[i]:
            r.append("non_recurring")
        reasons.append(r)
        # rank: incidents and severe drops first
        score = (10 if "labelled_incident" in r else 0) + (6 if "severe_congestion" in r else 0)
        score += (4 if "sudden_speed_drop" in r else 0) + (3 if "speed_anomaly" in r else 0)
        score += (2 if "congestion" in r else 0) + (1 if "roadworks" in r else 0)
        scores.append(score if r else -1)

    out["reasons"] = reasons
    out["flag_score"] = scores
    flagged = out[out["flag_score"] >= 0].sort_values("flag_score", ascending=False)
    return flagged.head(int(max_items))


def classify_locally(reasons: list[str], rain: float, event_level: float) -> tuple[str, float]:
    """Rule-based incident class used as the LLM fallback."""
    if "labelled_incident" in reasons and "sudden_speed_drop" in reasons:
        return "blockage_or_crash", 0.75
    if "roadworks" in reasons:
        return "event_surge", 0.55
    if rain and rain >= 0.4:
        return "weather_effect", 0.6
    if event_level and event_level >= 1:
        return "event_surge", 0.6
    if "sudden_speed_drop" in reasons and "upstream_queue_growth" in reasons:
        return "blockage_or_crash", 0.65
    if "recurring_pattern" in reasons:
        return "unclassified_anomaly", 0.4
    if reasons:
        return "unclassified_anomaly", 0.5
    return "unclassified_anomaly", 0.2
