"""Draw the road network as a schematic map with Plotly.

HOW THE MAP IS BUILT
    nodes.csv    -> junction positions (x, y on a 12 x 10 grid)
    network.csv  -> which junction each road starts and ends at
    speed data   -> the COLOUR of each road at the chosen moment

Every road is a two-way pair (R0001 goes N001->N002, R0002 goes N002->N001), so
we shift each road slightly to the left of its direction of travel. Otherwise
the two directions would be drawn on top of each other and one would be hidden.

Functions here take plain pandas objects and return a Plotly figure, so they
can be tested without starting the dashboard.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

NODE_COLOR = "#95a5a6"
NO_DATA_COLOR = "#b0b7bd"

# Colour schemes. `edges` split the value range into bins; np.digitize gives the
# bin number, which indexes `colors` and `labels` (lowest values first).
MODES = {
    "Speed ratio (speed / free-flow)": {
        "edges": [0.5, 0.7, 0.85, 0.95],
        "colors": ["#7b0d1e", "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71"],
        "labels": ["< 50%  severe", "50-70%  congested", "70-85%  slow",
                   "85-95%  slightly slow", ">= 95%  free flow"],
    },
    "Flow / capacity": {
        "edges": [0.5, 0.7, 0.85, 1.0],
        "colors": ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#7b0d1e"],
        "labels": ["< 0.5  light", "0.5-0.7  moderate", "0.7-0.85  busy",
                   "0.85-1.0  near capacity", ">= 1.0  over capacity"],
    },
}


def build_geometry(nodes: pd.DataFrame, net: pd.DataFrame,
                   lane_offset: float = 0.07, end_gap: float = 0.12) -> pd.DataFrame:
    """One row per road segment with start/end/middle coordinates on the map."""
    xy = nodes.set_index("node_id")[["x", "y"]]
    g = net.set_index("segment_id").copy()
    s = xy.loc[g["source_node"]].to_numpy(float)
    t = xy.loc[g["target_node"]].to_numpy(float)

    d = t - s
    u = d / np.hypot(d[:, 0], d[:, 1])[:, None]      # unit vector along the road
    left = np.column_stack([-u[:, 1], u[:, 0]])      # left of travel (drive-on-left)

    p0 = s + u * end_gap + left * lane_offset        # shortened + shifted start
    p1 = t - u * end_gap + left * lane_offset        # shortened + shifted end
    g["x0"], g["y0"], g["x1"], g["y1"] = p0[:, 0], p0[:, 1], p1[:, 0], p1[:, 1]
    g["mx"], g["my"] = (p0[:, 0] + p1[:, 0]) / 2, (p0[:, 1] + p1[:, 1]) / 2
    return g


def _line_xy(sel: pd.DataFrame):
    """Many separate line pieces in ONE trace: pieces are split by NaN."""
    nan = np.full(len(sel), np.nan)
    xs = np.column_stack([sel["x0"], sel["x1"], nan]).ravel()
    ys = np.column_stack([sel["y0"], sel["y1"], nan]).ravel()
    return xs, ys


def build_network_figure(
    geom: pd.DataFrame,
    nodes: pd.DataFrame,
    values: pd.Series,
    mode: str,
    hover_text: pd.Series | None = None,
    incident_segments=(),
    roadwork_segments=(),
    height: int = 640,
) -> go.Figure:
    """values: Series indexed by segment_id (e.g. speed ratio at the chosen time)."""
    cfg = MODES[mode]
    vals = values.reindex(geom.index).to_numpy(float)
    bin_idx = np.where(np.isnan(vals), -1, np.digitize(vals, cfg["edges"]))
    is_arterial = (geom["road_class"] == "arterial").to_numpy()

    fig = go.Figure()

    # highlight halo under active incidents (drawn first so it sits underneath)
    inc = geom.loc[geom.index.intersection(list(incident_segments))]
    if len(inc):
        xs, ys = _line_xy(inc)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Active incident",
                                 line=dict(color="rgba(41,128,185,0.45)", width=16),
                                 hoverinfo="skip"))

    # the roads, coloured by value: one trace per (colour bin, road class)
    shown = set()
    order = [-1] + list(range(len(cfg["colors"])))
    for b in order:
        color = NO_DATA_COLOR if b == -1 else cfg["colors"][b]
        label = "no data" if b == -1 else cfg["labels"][b]
        for arterial, width in ((False, 3), (True, 5)):
            sel = geom[(bin_idx == b) & (is_arterial == arterial)]
            if sel.empty:
                continue
            xs, ys = _line_xy(sel)
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines", name=label, legendgroup=label,
                showlegend=label not in shown, hoverinfo="skip",
                line=dict(color=color, width=width)))
            shown.add(label)

    # roadworks: dotted black line on top
    rw = geom.loc[geom.index.intersection(list(roadwork_segments))]
    if len(rw):
        xs, ys = _line_xy(rw)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Roadworks",
                                 line=dict(color="black", width=2, dash="dot"),
                                 hoverinfo="skip"))

    # junction dots
    fig.add_trace(go.Scatter(
        x=nodes["x"], y=nodes["y"], mode="markers", name="Junction", showlegend=False,
        marker=dict(size=6, color=NODE_COLOR), text=nodes["node_id"], hoverinfo="text"))

    # invisible points in the middle of each road, they carry the hover text
    hover = hover_text.reindex(geom.index) if hover_text is not None else pd.Series(geom.index, index=geom.index)
    fig.add_trace(go.Scatter(
        x=geom["mx"], y=geom["my"], mode="markers", name="Roads", showlegend=False,
        marker=dict(size=10, opacity=0), text=hover, hoverinfo="text"))

    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(visible=False, range=[-0.6, 11.6]),
        yaxis=dict(visible=False, range=[-0.6, 9.6], scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", yanchor="bottom", y=-0.08, x=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        uirevision="network",
    )
    return fig
