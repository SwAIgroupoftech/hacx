"""BPR volume-delay impact for planning candidates (simulated estimate only)."""
from __future__ import annotations

import pandas as pd


def bpr_minutes(length_km, free_flow_kmh, flow_vph, capacity_vph,
                alpha: float = 0.15, beta: float = 4.0) -> float:
    t0 = (float(length_km) / max(float(free_flow_kmh), 1.0)) * 60.0
    vc = float(flow_vph) / max(float(capacity_vph), 1.0)
    return t0 * (1.0 + alpha * (vc ** beta))


def evaluate_candidates(flagged_ids: list[str], bottlenecks: list[dict],
                        planning: pd.DataFrame | None, net: pd.DataFrame,
                        speed: pd.Series, flow: pd.Series, cfg: dict) -> list[dict]:
    if planning is None or planning.empty:
        return []
    impact = cfg.get("impact", {})
    alpha = float(impact.get("bpr_alpha", 0.15))
    beta = float(impact.get("bpr_beta", 4.0))
    label = impact.get("label", "SIMULATED ESTIMATE - NOT A CONSTRUCTION RECOMMENDATION")
    netx = net.set_index("segment_id")
    targets = set(flagged_ids) | {b["segment_id"] for b in bottlenecks}
    rows = []
    for r in planning.itertuples():
        seg = str(r.target_segment)
        if seg not in targets or seg not in netx.index:
            continue
        meta = netx.loc[seg]
        cap = float(meta["capacity_vph"])
        fl = float(flow.get(seg, 0.0) or 0.0)
        before = bpr_minutes(meta["length_km"], meta["free_flow_speed_kmh"], fl, cap, alpha, beta)
        new_cap = cap + float(r.capacity_delta_vph)
        after = bpr_minutes(meta["length_km"], meta["free_flow_speed_kmh"], fl, new_cap, alpha, beta)
        # sensitivity band at +/-10% demand
        after_hi = bpr_minutes(meta["length_km"], meta["free_flow_speed_kmh"], fl * 1.1, new_cap, alpha, beta)
        after_lo = bpr_minutes(meta["length_km"], meta["free_flow_speed_kmh"], fl * 0.9, new_cap, alpha, beta)
        rows.append({
            "candidate_id": str(r.candidate_id),
            "segment_id": seg,
            "intervention_type": str(r.intervention_type),
            "capacity_delta_vph": float(r.capacity_delta_vph),
            "cost_index": float(r.cost_index) if hasattr(r, "cost_index") else None,
            "feasibility_band": str(r.feasibility_band) if hasattr(r, "feasibility_band") else None,
            "delay_before_min": round(before, 3),
            "delay_after_min": round(after, 3),
            "delay_reduction_min": round(before - after, 3),
            "delay_after_range_min": [round(after_lo, 3), round(after_hi, 3)],
            "label": label,
        })
        if len(rows) >= 8:
            break
    rows.sort(key=lambda x: x["delay_reduction_min"], reverse=True)
    return rows
