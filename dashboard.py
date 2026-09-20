"""TrafficSense dashboard with real-time media player simulation and AI Copilot.

Run from the project root:
    streamlit run src/app/dashboard.py
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.advisory_tab import _latest_report, render as render_advisory  # noqa: E402
from src.app.chat_tab import render as render_chat  # noqa: E402
from src.app.forecast_tab import render as render_forecast  # noqa: E402
from src.app.network_map import MODES, build_geometry, build_network_figure  # noqa: E402
from src.ingestion.load_clean import find_splits, load_traffic_wide  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

st.set_page_config(page_title="TrafficSense Intelligence", page_icon="🚦", layout="wide")

_STRETCH = "width" in inspect.signature(st.plotly_chart).parameters


def show_chart(fig: go.Figure) -> None:
    if _STRETCH:
        st.plotly_chart(fig, width="stretch")
    else:
        st.plotly_chart(fig, use_container_width=True)


def default_data_dir() -> str:
    p = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
    return str(p if p.is_absolute() else ROOT / p)


# ----------------------------------------------------------------------------
# Cached loading
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading road network...")
def load_network(data_dir: str):
    d = Path(data_dir)
    nodes = pd.read_csv(d / "nodes.csv")
    net = pd.read_csv(d / "network.csv")
    return nodes, net, build_geometry(nodes, net)


@st.cache_data(show_spinner="Loading and cleaning traffic data...")
def load_traffic(data_dir: str, split: str):
    return load_traffic_wide(Path(data_dir) / f"traffic_{split}.csv")


@st.cache_data
def load_events(data_dir: str, split: str):
    d, out = Path(data_dir), {}
    for name in ("incidents", "roadworks"):
        f = d / f"{name}_{split}.csv"
        out[name] = (pd.read_csv(f, parse_dates=["start_time", "end_time"])
                     if f.exists() else None)
    return out


def active_at(df, ts) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["segment_id"])
    return df[(df["start_time"] <= ts) & (df["end_time"] >= ts)]


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.title("🚦 TrafficSense AI")
data_dir = st.sidebar.text_input("Data folder", default_data_dir())

if not (Path(data_dir) / "network.csv").exists() or not (Path(data_dir) / "nodes.csv").exists():
    st.error(f"network.csv / nodes.csv not found in `{data_dir}`.")
    st.stop()
splits = find_splits(data_dir)
if not splits:
    st.error(f"No traffic_<name>.csv files found in `{data_dir}`.")
    st.stop()

split = st.sidebar.selectbox("Dataset", splits,
                             index=splits.index("validation") if "validation" in splits else 0)
mode = st.sidebar.radio("Colour roads by", list(MODES))

nodes, net, geom = load_network(data_dir)
wide, report = load_traffic(data_dir, split)
events = load_events(data_dir, split)

netx = net.set_index("segment_id")
speed = wide["speed_kmh"].reindex(columns=geom.index)
flow = wide["flow_vph"].reindex(columns=geom.index)
free_flow = netx["free_flow_speed_kmh"]
capacity = netx["capacity_vph"]
times = speed.index
mean_ratio = speed.div(free_flow.reindex(speed.columns), axis=1).mean(axis=1)

# Jump to a labelled incident
inc_df = events["incidents"]
chosen = None
if inc_df is not None and len(inc_df):
    labels = ["(none)"] + [
        f"{r.incident_id} | {r.segment_id} | {r.incident_type} | {r.start_time:%b %d %H:%M}"
        for r in inc_df.itertuples()
    ]
    pick = st.sidebar.selectbox("Jump to incident", labels)
    if pick != "(none)":
        chosen = inc_df.iloc[labels.index(pick) - 1]

# ----------------------------------------------------------------------------
# Media-Player Time Simulator State
# ----------------------------------------------------------------------------
if "is_playing" not in st.session_state:
    st.session_state.is_playing = False

if "sim_ts" not in st.session_state:
    if chosen is not None:
        st.session_state.sim_ts = times[times.get_indexer([chosen["start_time"] + timedelta(minutes=10)], method="nearest")[0]]
    else:
        st.session_state.sim_ts = mean_ratio.idxmin()

# If user jumped to an incident from sidebar, update sim_ts
if chosen is not None and st.session_state.get("_last_incident_pick") != pick and pick != "(none)":
    st.session_state._last_incident_pick = pick
    st.session_state.sim_ts = times[times.get_indexer([chosen["start_time"] + timedelta(minutes=10)], method="nearest")[0]]
    st.session_state.is_playing = False


def snap_time(t) -> pd.Timestamp:
    return times[times.get_indexer([pd.Timestamp(t)], method="nearest")[0]]


# Ensure sim_ts is within bounds
if st.session_state.sim_ts < times[0] or st.session_state.sim_ts > times[-1]:
    st.session_state.sim_ts = times[0]

# ----------------------------------------------------------------------------
# Title & Media Player Controls
# ----------------------------------------------------------------------------
st.title("TrafficSense: Real-Time Network Simulation")
st.caption("ADVISORY ONLY - SIMULATED. Real-time traffic replay player with AI copilot and predictive advisories.")

player_card = st.container()
with player_card:
    ctrl1, ctrl2, ctrl3, ctrl4, ctrl5, ctrl6, ctrl7 = st.columns([1.1, 1.1, 1.6, 1.1, 1.1, 2.0, 2.8])

    # 1. Rewind -15m
    if ctrl1.button("⏪ -15m", use_container_width=True):
        new_ts = snap_time(st.session_state.sim_ts - timedelta(minutes=15))
        st.session_state.sim_ts = new_ts

    # 2. Step back -5m
    if ctrl2.button("◀️ -5m", use_container_width=True):
        new_ts = snap_time(st.session_state.sim_ts - timedelta(minutes=5))
        st.session_state.sim_ts = new_ts

    # 3. Play / Pause
    play_label = "⏸️ Pause" if st.session_state.is_playing else "▶️ Play Replay"
    if ctrl3.button(play_label, type="primary" if not st.session_state.is_playing else "secondary", use_container_width=True):
        st.session_state.is_playing = not st.session_state.is_playing

    # 4. Step forward +5m
    if ctrl4.button("▶️ +5m", use_container_width=True):
        new_ts = snap_time(st.session_state.sim_ts + timedelta(minutes=5))
        st.session_state.sim_ts = new_ts

    # 5. Jump forward +15m
    if ctrl5.button("⏩ +15m", use_container_width=True):
        new_ts = snap_time(st.session_state.sim_ts + timedelta(minutes=15))
        st.session_state.sim_ts = new_ts

    # 6. Playback speed
    speed_option = ctrl6.selectbox(
        "Replay Speed",
        ["Fast (0.5s)", "Realtime-feel (1.0s)", "Relaxed (2.0s)"],
        index=1,
        label_visibility="collapsed",
    )
    speed_delay = 0.5 if "0.5" in speed_option else (2.0 if "2.0" in speed_option else 1.0)

    # 7. Live Indicator Badge
    if st.session_state.is_playing:
        ctrl7.markdown(
            '<div style="background-color:#991b1b;color:white;padding:8px 14px;border-radius:6px;text-align:center;font-weight:bold;font-size:14px;margin-top:2px;">🔴 LIVE SIMULATING PLAYBACK</div>',
            unsafe_allow_html=True,
        )
    else:
        ctrl7.markdown(
            '<div style="background-color:#1e293b;color:#94a3b8;padding:8px 14px;border-radius:6px;text-align:center;font-weight:bold;font-size:14px;margin-top:2px;">⏸️ SIMULATION PAUSED</div>',
            unsafe_allow_html=True,
        )

    # Media Timeline Scrubber (Slider)
    picked_time = st.slider(
        "Timeline Scrub Bar",
        min_value=times[0].to_pydatetime(),
        max_value=times[-1].to_pydatetime(),
        value=st.session_state.sim_ts.to_pydatetime(),
        step=timedelta(minutes=5),
        format="YYYY-MM-DD HH:mm",
        label_visibility="collapsed",
    )
    ts = snap_time(picked_time)
    st.session_state.sim_ts = ts

# ----------------------------------------------------------------------------
# Numbers at current instant
# ----------------------------------------------------------------------------
sp, fl = speed.loc[ts], flow.loc[ts]
ratio = sp / free_flow.reindex(sp.index)
vc = fl / capacity.reindex(fl.index)
values = ratio if mode.startswith("Speed") else vc

act_inc = active_at(inc_df, ts)
act_rw = active_at(events["roadworks"], ts)
inc_type = dict(zip(act_inc["segment_id"], act_inc.get("incident_type", [])))

hover = pd.Series(
    [f"<b>{s}</b> ({geom.at[s, 'road_class']}, {geom.at[s, 'lanes']} lanes)"
     f"<br>speed {sp[s]:.0f} km/h ({ratio[s]:.0%} of normal)"
     f"<br>flow {fl[s]:.0f} veh/h ({vc[s]:.2f} of capacity)"
     + (f"<br><b>INCIDENT: {inc_type[s]}</b>" if s in inc_type else "")
     for s in geom.index], index=geom.index)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Current Time", f"{ts:%a %d %b %H:%M}")
m2.metric("Network Avg Speed", f"{ratio.mean():.0%}")
m3.metric("Congested Corridors", int((ratio < 0.70).sum()))
m4.metric("Active Incidents", len(act_inc))

# ----------------------------------------------------------------------------
# Dashboard Tabs
# ----------------------------------------------------------------------------
tab_map, tab_fc, tab_adv, tab_chat, tab_quality = st.tabs([
    "🗺️ Network Map",
    "📈 Forecasts (15-60m)",
    "🚨 Advisories & Incidents",
    "💬 AI Traffic Copilot",
    "📊 Data Quality & Health",
])

with tab_map:
    left, right = st.columns([3, 2])

    with left:
        fig = build_network_figure(geom, nodes, values, mode, hover_text=hover,
                                   incident_segments=act_inc["segment_id"].tolist(),
                                   roadwork_segments=act_rw["segment_id"].tolist())
        show_chart(fig)

    with right:
        for r in act_inc.itertuples():
            st.error(f"**{r.incident_id}** on **{r.segment_id}**: {r.incident_type}, "
                     f"severity {r.severity}, {r.lanes_blocked} lane(s) blocked "
                     f"({r.start_time:%H:%M}-{r.end_time:%H:%M})")

        st.subheader("Slowest 10 Corridors Right Now")
        worst = pd.DataFrame({
            "Corridor": sp.index,
            "Speed (km/h)": sp.values.round(0),
            "% of Normal": (ratio.values * 100).round(0),
            "Flow (veh/h)": fl.values.round(0),
            "Flow/Capacity": vc.values.round(2),
        }).sort_values("% of Normal").head(10)
        st.dataframe(worst, hide_index=True, use_container_width=True)

        st.subheader("Corridor Speed History")
        auto_seg = (act_inc["segment_id"].iloc[0] if len(act_inc) else ratio.idxmin())
        pick_seg = st.selectbox("Corridor", ["(auto: incident or slowest road)"] + list(geom.index),
                                key="segment_pick")
        seg = auto_seg if pick_seg.startswith("(auto") else pick_seg

        lo, hi = ts - timedelta(hours=3), ts + timedelta(hours=3)
        win = speed.loc[lo:hi, seg]
        chart = go.Figure()
        chart.add_trace(go.Scatter(x=win.index, y=win.values, mode="lines", name="speed"))
        chart.add_hline(y=float(free_flow[seg]), line_dash="dash", line_color="grey",
                        annotation_text="free-flow")
        chart.add_shape(type="line", x0=ts.to_pydatetime(), x1=ts.to_pydatetime(),
                        y0=0, y1=1, yref="paper", line=dict(color="black", width=1))
        if inc_df is not None:
            for r in inc_df[inc_df["segment_id"] == seg].itertuples():
                if r.end_time >= lo and r.start_time <= hi:
                    chart.add_shape(type="rect", x0=r.start_time, x1=r.end_time, y0=0, y1=1,
                                    yref="paper", fillcolor="rgba(41,128,185,0.2)", line_width=0)
        chart.update_layout(height=280, margin=dict(l=0, r=0, t=30, b=0),
                            title=f"{seg}: speed (km/h), ±3 h window", showlegend=False)
        show_chart(chart)

with tab_fc:
    render_forecast(data_dir=data_dir, split=split, splits=splits, wide=wide, net=net,
                    ts=ts, speed=speed, free_flow=free_flow, show_chart=show_chart)

with tab_adv:
    render_advisory(split=split, ts=ts)

# Load latest report for chat context if available
latest_rep = None
proc_dir = ROOT / "data" / "processed"
rep_path = _latest_report(proc_dir, split)
if rep_path and rep_path.exists():
    try:
        latest_rep = json.loads(rep_path.read_text(encoding="utf-8"))
    except Exception:
        latest_rep = None

with tab_chat:
    render_chat(
        ts=ts,
        speed=sp,
        free_flow=free_flow,
        geom=geom,
        act_inc=act_inc,
        act_rw=act_rw,
        latest_report=latest_rep,
    )

with tab_quality:
    st.subheader("Data Cleaning & Sensor Health Summary")
    st.write("Cleaned via `load_clean.py` against noise, impossible values, stuck sensors, and data drops:")

    qc1, qc2, qc3, qc4, qc5 = st.columns(5)
    qc1.metric("Total Rows In", f"{report.get('rows_in', 0):,}")
    qc2.metric("Duplicates Removed", f"{report.get('duplicate_rows_removed', 0):,}")
    qc3.metric("Spikes Filtered", f"{report.get('spikes_removed', 0):,}")
    qc4.metric("Stuck Sensors Recovered", f"{report.get('stuck_sensor_readings_removed', 0):,}")
    qc5.metric("Gaps Interpolated", f"{report.get('speed_gaps_filled', 0):,}")

    st.markdown("### Quality Audit Breakdown")
    q_table = [
        {"Cleaning Check": "Bad Timestamp / Missing IDs", "Status": "Passed", "Records Fixed": report.get("bad_timestamp_or_id_rows_removed", 0)},
        {"Cleaning Check": "Duplicate Observations", "Status": "Passed", "Records Fixed": report.get("duplicate_rows_removed", 0)},
        {"Cleaning Check": "Isolated Speed Spikes (>20 km/h leap)", "Status": "Fixed via median filter", "Records Fixed": report.get("spikes_removed", 0)},
        {"Cleaning Check": "Frozen / Stuck Sensors (1 hr flatline)", "Status": "Restored", "Records Fixed": report.get("stuck_sensor_readings_removed", 0)},
        {"Cleaning Check": "Short Missing Gaps (≤15 min)", "Status": "Linear Interpolated", "Records Fixed": report.get("speed_gaps_filled", 0)},
        {"Cleaning Check": "Unfillable Extended Outages", "Status": "Clean", "Records Fixed": report.get("speed_still_missing", 0)},
    ]
    st.dataframe(pd.DataFrame(q_table), hide_index=True, use_container_width=True)

# ----------------------------------------------------------------------------
# Automatic Time Stepping for Playing Simulation
# ----------------------------------------------------------------------------
if st.session_state.is_playing:
    time.sleep(speed_delay)
    curr_idx = times.get_indexer([st.session_state.sim_ts], method="nearest")[0]
    next_idx = (curr_idx + 1) % len(times)
    st.session_state.sim_ts = times[next_idx]
    st.rerun()