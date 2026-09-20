"""Rank recurring bottlenecks from history up to (and including) as_of."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rank_bottlenecks(speed: pd.DataFrame, flow: pd.DataFrame, net: pd.DataFrame,
                     as_of, cfg: dict, incidents: pd.DataFrame | None = None) -> list[dict]:
    as_of = pd.Timestamp(as_of)
    hist_s = speed.loc[:as_of]
    hist_f = flow.reindex(hist_s.index)
    netx = net.set_index("segment_id")
    ff = netx["free_flow_speed_kmh"].reindex(hist_s.columns)
    cap = netx["capacity_vph"].reindex(hist_s.columns)
    ratio = hist_s.div(ff, axis=1)
    th = float(cfg.get("congestion", {}).get("speed_ratio_threshold", 0.50))
    weights = cfg.get("bottleneck", {}).get("ranking_weights",
                                            {"frequency": 0.3, "duration": 0.3, "severity": 0.4})
    min_occ = int(cfg.get("bottleneck", {}).get("min_occurrences_for_recurring", 5))
    top_n = int(cfg.get("bottleneck", {}).get("top_n", 5))

    congested = ratio < th
    freq = congested.mean()  # fraction of intervals
    # mean run length (duration)
    durations = []
    severities = []
    vhd = []
    for col in hist_s.columns:
        flag = congested[col].fillna(False).to_numpy()
        runs, n = [], 0
        for v in flag:
            if v:
                n += 1
            elif n:
                runs.append(n); n = 0
        if n:
            runs.append(n)
        durations.append(float(np.mean(runs)) if runs else 0.0)
        # severity: 1 - ratio when congested
        sev = (1.0 - ratio[col][congested[col]]).mean()
        severities.append(float(sev) if np.isfinite(sev) else 0.0)
        # vehicle-hours delay ≈ flow * (ff/speed - 1) * 5/60 when slow
        spd = hist_s[col].clip(lower=3.0)
        delay_h = (hist_f[col].fillna(0) * (ff[col] / spd - 1.0).clip(lower=0) * (5.0 / 60.0)).sum()
        vhd.append(float(delay_h) if np.isfinite(delay_h) else 0.0)

    dur = pd.Series(durations, index=hist_s.columns)
    sev = pd.Series(severities, index=hist_s.columns)
    vhd_s = pd.Series(vhd, index=hist_s.columns)
    score = (weights.get("frequency", 0.3) * freq
             + weights.get("duration", 0.3) * (dur / max(float(dur.max()), 1.0))
             + weights.get("severity", 0.4) * sev)
    occ = congested.sum()
    keep = occ >= min_occ
    # always keep structural flags
    if "structural_bottleneck" in netx.columns:
        keep = keep | (netx["structural_bottleneck"].reindex(keep.index).fillna(0) > 0)

    ranked = score[keep].sort_values(ascending=False).head(top_n)
    rows = []
    for seg, sc in ranked.items():
        rows.append({
            "segment_id": str(seg),
            "score": round(float(sc), 4),
            "congested_fraction": round(float(freq[seg]), 3),
            "mean_run_intervals": round(float(dur[seg]), 2),
            "mean_severity": round(float(sev[seg]), 3),
            "vehicle_hours_delay": round(float(vhd_s[seg]), 1),
            "structural": int(netx.loc[seg, "structural_bottleneck"]) if seg in netx.index else 0,
            "road_class": str(netx.loc[seg, "road_class"]) if seg in netx.index else None,
            "lanes": int(netx.loc[seg, "lanes"]) if seg in netx.index else None,
        })
    return rows
