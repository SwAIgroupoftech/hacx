"""Build the compact evidence packet that is written to data/processed and sent to Groq."""
from __future__ import annotations

import pandas as pd

from src.advisory.diversion import alternate_routes, segment_graph, travel_times
from src.detection.flags import flag_snapshot
from src.network_mod.bottlenecks import rank_bottlenecks
from src.network_mod.impact import evaluate_candidates
from src.state.forecast_pack import attach_horizon_hist, local_forecasts
from src.util import json_safe


def _row_dict(row: pd.Series) -> dict:
    seg_id = str(row.name[1] if isinstance(row.name, tuple) else row.name)
    spd = row.get("speed")
    ff = row.get("free_flow")
    ratio = row.get("ratio")
    return {
        "segment_id": seg_id,
        "speed_kmh": round(float(spd), 1) if pd.notna(spd) else None,
        "free_flow_kmh": round(float(ff), 1) if pd.notna(ff) else None,
        "speed_ratio": round(float(ratio), 2) if pd.notna(ratio) else None,
        "reasons": list(row.get("reasons", [])),
    }


def build_evidence(
    *,
    as_of,
    split: str,
    cfg: dict,
    fb,
    wide: dict,
    assets: dict,
    engine=None,
) -> dict:
    as_of = pd.Timestamp(as_of)
    if as_of not in fb.index:
        as_of = fb.index[fb.index.get_indexer([as_of], method="nearest")[0]]
    sel = fb.positions(as_of, as_of + pd.Timedelta(minutes=1), stride=1)
    if len(sel) == 0:
        raise ValueError(f"no feature row at {as_of}")
    frame = fb.frame(sel)
    # Default to 4 flagged items to stay comfortably within Groq TPM limit
    max_items = int(cfg.get("llm", {}).get("max_evidence_items", 4))
    flagged = flag_snapshot(frame, cfg, max_items=max_items)
    flagged = attach_horizon_hist(flagged, fb, sel)
    forecasts = local_forecasts(frame, flagged, engine=engine, fb=fb, sel=sel)

    # Compact forecast entries to essential chosen values
    compact_forecasts = {}
    for seg, hor_map in forecasts.items():
        compact_forecasts[seg] = {
            h: {"chosen": rec.get("chosen"), "chosen_model": rec.get("chosen_model")}
            for h, rec in hor_map.items()
        }

    net = assets["network"]
    speed_now = wide["speed_kmh"].loc[as_of]
    flow_now = wide["flow_vph"].loc[as_of]
    netx = net.set_index("segment_id")
    vc_now = flow_now / netx["capacity_vph"].reindex(flow_now.index)

    g = segment_graph(net, assets.get("turn_restrictions"))
    ttimes = travel_times(net, speed_now)
    adv_cfg = cfg.get("advisory", {})
    diversions = []
    for row in flagged.itertuples():
        seg = str(row.Index[1])
        reasons = list(row.reasons)
        if not any(r in reasons for r in ("severe_congestion", "labelled_incident",
                                          "sudden_speed_drop", "congestion", "roadworks")):
            continue
        alts = alternate_routes(
            g, seg, ttimes,
            k=int(adv_cfg.get("k_alternate_routes", 2)),
            max_util=float(adv_cfg.get("max_alternate_utilisation", 0.85)),
            vc=vc_now,
            cap_gain_min=float(adv_cfg.get("min_time_saving_minutes", 3)),
        )
        diversions.append({"blocked_segment": seg, "reasons": reasons, "alternates": alts})
        if len(diversions) >= 2:
            break

    bottlenecks = rank_bottlenecks(
        wide["speed_kmh"], wide["flow_vph"], net, as_of, cfg, assets.get("incidents"),
    )[:3]

    flagged_ids = [str(ix[1]) for ix in flagged.index]
    infra = evaluate_candidates(
        flagged_ids, bottlenecks, assets.get("planning"), net, speed_now, flow_now, cfg,
    )[:3]

    ctx_now = {}
    ctx = assets.get("context")
    if ctx is not None and len(ctx):
        c = ctx.copy()
        c["timestamp"] = pd.to_datetime(c["timestamp"])
        hit = c.iloc[(c["timestamp"] - as_of).abs().argmin()]
        ctx_now = {
            "temperature_c": _f(hit.get("temperature_c")),
            "rain_intensity": _f(hit.get("rain_intensity")),
            "event_level": _f(hit.get("event_level")),
            "holiday_flag": _f(hit.get("holiday_flag")),
        }

    labelled = []
    inc = assets.get("incidents")
    if inc is not None and len(inc):
        act = inc[(inc["start_time"] <= as_of) & (inc["end_time"] >= as_of)]
        for r in act.itertuples():
            labelled.append({
                "incident_id": str(r.incident_id),
                "segment_id": str(r.segment_id),
                "incident_type": str(r.incident_type),
                "severity": int(r.severity),
                "lanes_blocked": int(r.lanes_blocked),
            })

    flagged_rows = []
    for _, row in flagged.iterrows():
        rec = _row_dict(row)
        rec["forecast_local"] = compact_forecasts.get(rec["segment_id"], {})
        rec["labelled_incident"] = next(
            (x for x in labelled if x["segment_id"] == rec["segment_id"]), None)
        flagged_rows.append(rec)

    packet = {
        "as_of": as_of.isoformat(),
        "split": split,
        "label": cfg.get("advisory", {}).get("label", "ADVISORY ONLY - SIMULATED"),
        "network_summary": {
            "n_segments": int(len(frame)),
            "n_flagged": len(flagged_rows),
            "n_congested": int((frame["ratio"] < cfg["congestion"]["speed_ratio_threshold"]).sum()),
            "mean_speed_ratio": _f(frame["ratio"].mean()),
            "active_labelled_incidents": len(labelled),
        },
        "context": ctx_now,
        "labelled_incidents": labelled,
        "flagged": flagged_rows,
        "diversions": diversions,
        "bottlenecks": bottlenecks,
        "infrastructure_candidates": infra,
        "od_demand_touching_flags": _od_near(assets.get("od_demand"), net, flagged_ids, limit=2),
        "signal_hint": _signal_hint(assets.get("signal_plans"), net, flagged_ids)[:2],
    }
    return json_safe(packet)


def _od_near(od, net, flagged_ids, limit=2) -> list[dict]:
    if od is None or not flagged_ids:
        return []
    netx = net.set_index("segment_id")
    nodes = set()
    for s in flagged_ids:
        if s in netx.index:
            nodes.add(str(netx.loc[s, "source_node"]))
            nodes.add(str(netx.loc[s, "target_node"]))
    hit = od[od["origin_node"].isin(nodes) | od["destination_node"].isin(nodes)]
    hit = hit.sort_values("base_demand_vph", ascending=False).head(limit)
    return hit.to_dict(orient="records")


def _signal_hint(plans, net, flagged_ids) -> list[dict]:
    if plans is None or not flagged_ids:
        return []
    netx = net.set_index("segment_id")
    sigs = []
    for s in flagged_ids:
        if s in netx.index and pd.notna(netx.loc[s, "signal_id"]):
            sid = str(netx.loc[s, "signal_id"])
            row = plans[plans["signal_id"] == sid]
            if len(row):
                rec = row.iloc[0].to_dict()
                rec["segment_id"] = s
                sigs.append(rec)
    return sigs[:2]


def _f(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None
