"""Advisories tab: reads and presents the latest intelligence report in clean, non-JSON visual UI."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]


def _latest_report(processed: Path, split: str) -> Path | None:
    files = sorted(processed.glob(f"report_{split}_*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def render(*, split: str, ts, processed_dir: str | None = None) -> None:
    processed = Path(processed_dir) if processed_dir else ROOT / "data" / "processed"
    path = _latest_report(processed, split)
    st.caption("ADVISORY ONLY - SIMULATED. Infrastructure numbers are simulated BPR estimates.")

    if path is None:
        st.info(
            f"No intelligence report found for '{split}' in `{processed}`.\n\n"
            f"Run from terminal to generate: `python scripts/run_scenario.py --split {split}`"
        )
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    llm = data.get("llm") or {}

    # Executive Banner
    source_badge = "🟢 Groq LLM (openai/gpt-oss-120b)" if "groq" in llm.get("source", "").lower() else "🟡 Rule-Based Engine"
    st.markdown(
        f"""Report File:{path.name}
            Engine: {source_badge}
            Snapshot: {data.get('as_of')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if llm.get("fallback_reason"):
        st.warning(f"Note on generation: {llm['fallback_reason']}")

    # Metric Cards
    c1, c2, c3, c4 = st.columns(4)
    ns = data.get("network_summary") or {}
    c1.metric("Flagged Roads", ns.get("n_flagged", "—"))
    c2.metric("Congested Corridors", ns.get("n_congested", "—"))
    c3.metric("Network Speed Ratio", f"{ns.get('mean_speed_ratio', 1.0):.0%}")
    c4.metric("Active Labelled Incidents", ns.get("active_labelled_incidents", "—"))

    # Tabs inside advisory
    t_adv, t_inc, t_fc, t_infra, t_bn = st.tabs([
        "🚨 Operational Advisories",
        "⚠️ Incident Classifications",
        "📈 Speed Forecasts (15-60m)",
        "🏗️ Infrastructure Proposals",
        "🔄 Recurring Bottlenecks",
    ])

    with t_adv:
        advisories = llm.get("advisories") or []
        if advisories:
            for i, a in enumerate(advisories):
                aff = ", ".join(a.get("affected_segments") or [])
                via = ", ".join(a.get("diversion") or [])
                saving = a.get("expected_saving_min", 0)
                conf = a.get("confidence", 0.5)

                st.markdown(
                    f"""
                    Recommended Action:{a.get('action')}
                    Affected Corridors:
                    🛣️ Alternate Route (Via): {via or 'No diversion needed / continue on route'}
                            {f"⏱️ Expected Time Saving: ~{saving} minutes" if saving > 0 else ""}
                            Evidence: {a.get('evidence', '')}
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No active diversion advisories required at this time.")

    with t_inc:
        incidents = llm.get("incidents") or []
        if incidents:
            inc_data = []
            for inc in incidents:
                raw_class = inc.get("incident_class", "unclassified_anomaly")
                pretty_class = raw_class.replace("_", " ").title()
                inc_data.append({
                    "Road Corridor": inc.get("segment_id"),
                    "Detected Classification": pretty_class,
                    "Confidence": f"{inc.get('confidence', 0.5):.0%}",
                    "Operational Analysis": inc.get("rationale", ""),
                })
            st.dataframe(pd.DataFrame(inc_data), hide_index=True, use_container_width=True)
        else:
            st.info("No abnormal incident events detected.")

    with t_fc:
        forecasts = llm.get("forecasts") or []
        if forecasts:
            fc_data = []
            for f in forecasts:
                fc_data.append({
                    "Corridor": f.get("segment_id"),
                    "Horizon (+Min)": f"+{f.get('horizon_min')}m",
                    "Expected Speed (km/h)": f"{f.get('speed_kmh', 0):.1f} km/h",
                    "Confidence": f"{f.get('confidence', 0.5):.0%}",
                    "Forecasting Rationale": f.get("rationale", ""),
                })
            st.dataframe(pd.DataFrame(fc_data), hide_index=True, use_container_width=True)
        else:
            st.info("No forecast rows recorded.")

    with t_infra:
        infra = llm.get("infrastructure") or []
        local_infra = data.get("local_infrastructure") or []
        if infra or local_infra:
            st.write("Data-driven infrastructure counterfactuals evaluated using the **Bureau of Public Roads (BPR)** delay model:")
            for row in infra:
                red_pct = row.get("estimated_delay_reduction_pct", 0)
                st.markdown(
                    f"""
                    <div style="background-color: #0f172a; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #10b981;">
                        <b style="color: #f1f5f9;">{row.get('candidate_id')} on Corridor {row.get('segment_id')}</b> — 
                        <span style="color: #38bdf8;">{row.get('intervention', '').replace('_', ' ').title()}</span>
                        <div style="color: #a7f3d0; font-size: 14px; margin-top: 4px;">
                            Estimated Delay Reduction: <b>{red_pct:.1f}%</b>
                        </div>
                        <div style="color: #94a3b8; font-size: 13px; margin-top: 2px;">
                            {row.get('rationale')}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No planning candidates flagged for this snapshot.")

    with t_bn:
        bottlenecks = data.get("local_bottlenecks") or []
        if bottlenecks:
            bn_data = []
            for b in bottlenecks:
                bn_data.append({
                    "Road Corridor": b.get("segment_id"),
                    "Road Type": str(b.get("road_class", "arterial")).title(),
                    "Lanes": b.get("lanes", 2),
                    "Congestion Frequency": f"{b.get('congested_fraction', 0):.1%}",
                    "Total Delay (Veh-Hours)": f"{b.get('vehicle_hours_delay', 0):.1f}h",
                    "Severity Index": f"{b.get('mean_severity', 0):.2f}",
                })
            st.dataframe(pd.DataFrame(bn_data), hide_index=True, use_container_width=True)
        else:
            st.info("No recurring bottlenecks computed for this period.")
