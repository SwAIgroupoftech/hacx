"""AI Traffic Copilot tab: conversational chat interface grounded in current conditions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.llm.clients import chat_with_copilot

ROOT = Path(__file__).resolve().parents[2]


def _build_context_summary(
    ts: pd.Timestamp,
    speed: pd.Series,
    free_flow: pd.Series,
    geom: pd.DataFrame,
    act_inc: pd.DataFrame,
    act_rw: pd.DataFrame,
    latest_report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a compact, human-interpretable snapshot for the copilot."""
    ratio = speed / free_flow.reindex(speed.index)
    slow_roads = ratio.sort_values().head(5)

    slow_descriptions = []
    for s, r in slow_roads.items():
        road_meta = geom.loc[s] if s in geom.index else {}
        r_class = road_meta.get("road_class", "arterial")
        lanes = road_meta.get("lanes", 2)
        spd = speed.get(s, 0.0)
        ff = free_flow.get(s, 50.0)
        slow_descriptions.append({
            "segment_id": str(s),
            "description": f"{r_class.title()} Corridor ({lanes} lanes)",
            "current_speed_kmh": round(float(spd), 1),
            "normal_speed_kmh": round(float(ff), 1),
            "percent_of_normal": f"{r:.0%}",
        })

    incidents_list = []
    if act_inc is not None and not act_inc.empty:
        for r in act_inc.itertuples():
            seg = str(r.segment_id)
            road_meta = geom.loc[seg] if seg in geom.index else {}
            r_class = road_meta.get("road_class", "arterial")
            lanes = road_meta.get("lanes", 2)
            incidents_list.append({
                "segment_id": seg,
                "location_description": f"{r_class.title()} link ({lanes} lanes total)",
                "incident_type": str(r.incident_type),
                "severity_level": int(r.severity),
                "lanes_blocked": int(r.lanes_blocked),
            })

    roadworks_list = []
    if act_rw is not None and not act_rw.empty:
        for r in act_rw.itertuples():
            seg = str(r.segment_id)
            road_meta = geom.loc[seg] if seg in geom.index else {}
            roadworks_list.append({
                "segment_id": seg,
                "road_type": str(road_meta.get("road_class", "street")),
                "activity": str(getattr(r, "activity_type", "Maintenance")),
            })

    advisories_list = []
    infra_list = []
    if latest_report:
        llm_block = latest_report.get("llm") or {}
        for adv in llm_block.get("advisories") or []:
            advisories_list.append({
                "title": adv.get("title"),
                "action": adv.get("action"),
                "affected": adv.get("affected_segments"),
                "recommended_via": adv.get("diversion"),
                "time_saving_min": adv.get("expected_saving_min"),
            })
        for inf in llm_block.get("infrastructure") or []:
            infra_list.append({
                "road_id": inf.get("segment_id"),
                "intervention": inf.get("intervention"),
                "delay_reduction": f"{inf.get('estimated_delay_reduction_pct')}%",
                "rationale": inf.get("rationale"),
            })

    return {
        "timestamp": f"{ts:%A, %B %d, %Y at %H:%M}",
        "network_status": {
            "average_network_speed_vs_normal": f"{ratio.mean():.0%}",
            "number_of_congested_corridors": int((ratio < 0.70).sum()),
            "total_active_incidents": len(incidents_list),
        },
        "slowest_corridors": slow_descriptions,
        "active_incidents": incidents_list,
        "active_roadworks": roadworks_list,
        "current_advisories": advisories_list,
        "infrastructure_proposals": infra_list,
    }


def render(
    *,
    ts: pd.Timestamp,
    speed: pd.Series,
    free_flow: pd.Series,
    geom: pd.DataFrame,
    act_inc: pd.DataFrame,
    act_rw: pd.DataFrame,
    latest_report: dict[str, Any] | None,
) -> None:
    st.subheader("TrafficSense Copilot: Conversational AI")
    st.caption("Ask questions in plain English. The AI understands current conditions, incidents, and reroutes.")

    context = _build_context_summary(ts, speed, free_flow, geom, act_inc, act_rw, latest_report)

    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = [
            {
                "role": "assistant",
                "content": (
                    f"Hello! I am your **TrafficSense Copilot**. "
                    f"I am monitoring conditions at **{ts:%A, %H:%M}**.\n\n"
                    f"- **Network Health**: {context['network_status']['average_network_speed_vs_normal']} of typical speed.\n"
                    f"- **Active Incidents**: {context['network_status']['total_active_incidents']}.\n"
                    f"- **Congested Corridors**: {context['network_status']['number_of_congested_corridors']} roads running slow.\n\n"
                    "Ask me anything about current delays, accidents, recommended alternate routes, or proposed road fixes!"
                ),
            }
        ]

    # Quick prompt suggestion buttons
    st.write("**Quick Questions:**")
    q_col1, q_col2, q_col3, q_col4 = st.columns(4)
    quick_prompt = None

    if q_col1.button("🚦 Current Overview", key="qp_1", use_container_width=True):
        quick_prompt = "What is the overall traffic situation right now and which areas are most affected?"
    if q_col2.button("🚨 Active Incidents", key="qp_2", use_container_width=True):
        quick_prompt = "Are there any accidents, stalls, or closed lanes right now? What caused them?"
    if q_col3.button("🔄 Best Alternate Routes", key="qp_3", use_container_width=True):
        quick_prompt = "How can drivers avoid the worst bottlenecks right now? What reroutes are recommended?"
    if q_col4.button("🏗️ Long-Term Fixes", key="qp_4", use_container_width=True):
        quick_prompt = "What infrastructure upgrades or signal retimings could permanently improve these bottlenecks?"

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.copilot_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # User input
    user_query = st.chat_input("Ask a question about traffic, delays, or alternate routes...") or quick_prompt

    if user_query:
        st.session_state.copilot_messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing traffic conditions..."):
                answer = chat_with_copilot(
                    query=user_query,
                    chat_history=st.session_state.copilot_messages[:-1],
                    context_summary=context,
                    root=ROOT,
                )
                st.markdown(answer)

        st.session_state.copilot_messages.append({"role": "assistant", "content": answer})
