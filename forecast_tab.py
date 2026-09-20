"""Forecast tab for the TrafficSense dashboard.

At the time chosen on the slider, the tab shows what the model expects 15/30/45/60
minutes later for every road, using ONLY data up to that time (replay clock, no
look-ahead). If the dataset happens to contain the real future, it is drawn as a
dashed line labelled "actual (not seen by the model)" so you can judge the forecast
yourself.

Which data trains the model (so we never grade it on data it has seen):
    viewing "validation"  -> trained on "train"
    viewing "test" (or any other new file) -> trained on "train" + "validation"
    viewing "train"       -> trained on "train" (in-sample: the tab warns you)
The first launch trains and saves the model to outputs/models/ (about a minute);
later launches load it from disk.

ADVISORY ONLY - SIMULATED. Nothing here controls anything.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.forecasting.features import HORIZONS, FeatureBuilder
from src.forecasting.forecast import train_engine

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "outputs" / "models"
EVAL_CSV = ROOT / "outputs" / "forecast_eval.csv"
STRIDE = 4          # train on every 4th timestamp: ~20 min of history-spacing, plenty of rows


# ----------------------------------------------------------------------------
# pure helpers (no Streamlit): easy to test
# ----------------------------------------------------------------------------
def fit_splits_for(split: str, available: list[str]) -> list[str]:
    """Which splits to train on when the user is looking at `split`."""
    known = [s for s in ("train", "validation") if s in available]
    if split == "train":
        return ["train"]
    return [s for s in known if s != split] or ["train"]


def forecast_at(engine, fb: FeatureBuilder, ts: pd.Timestamp) -> pd.DataFrame:
    """One row per road: speed now, and predicted speed at +15/30/45/60 (columns pred_15 ...).
    Uses only rows at or before ts."""
    sel = np.array([fb.index.get_loc(ts)])
    out = None
    for h in engine.horizons:
        f = engine.predict_frame(fb, sel, "speed", h)
        if out is None:
            out = pd.DataFrame(index=f.index.get_level_values("segment_id"))
            out["now"] = f["persistence"].to_numpy()
        out[f"pred_{h}"] = f["gbm"].to_numpy()
    return out


def forecast_figure(speed: pd.DataFrame, ts: pd.Timestamp, seg: str, row: pd.Series,
                    free_flow: float, horizons=HORIZONS) -> go.Figure:
    lo, hi = ts - pd.Timedelta(hours=3), ts + pd.Timedelta(minutes=max(horizons))
    past = speed.loc[lo:ts, seg]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=past.index, y=past.values, mode="lines", name="speed so far"))
    future = speed.loc[ts:hi, seg]
    if len(future) > 1:
        fig.add_trace(go.Scatter(x=future.index, y=future.values, mode="lines",
                                 name="actual (not seen by the model)",
                                 line=dict(dash="dash", color="grey")))
    fx = [ts] + [ts + pd.Timedelta(minutes=h) for h in horizons]
    fy = [row["now"]] + [row[f"pred_{h}"] for h in horizons]
    fig.add_trace(go.Scatter(x=fx, y=fy, mode="lines+markers", name="forecast",
                             line=dict(color="#e67e22", width=3)))
    fig.add_hline(y=free_flow, line_dash="dot", line_color="grey", annotation_text="free-flow")
    fig.add_shape(type="line", x0=ts.to_pydatetime(), x1=ts.to_pydatetime(), y0=0, y1=1,
                  yref="paper", line=dict(color="black", width=1))
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=30, b=0),
                      title=f"{seg}: forecast from {ts:%H:%M}", legend=dict(orientation="h"))
    return fig


def _signature(data_dir: str, names: list[str]) -> str:
    """Changes when a traffic file changes, so a stale saved model is never reused."""
    parts = []
    for n in names:
        f = Path(data_dir) / f"traffic_{n}.csv"
        parts.append(f"{n}{f.stat().st_size if f.exists() else 0}")
    return "_".join(parts)


# ----------------------------------------------------------------------------
# cached loading
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Training the forecast model (first run only, about a minute)...")
def get_engine(data_dir: str, fit_names: tuple):
    import joblib
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = MODEL_DIR / f"engine_{'+'.join(fit_names)}_{_signature(data_dir, list(fit_names))}.joblib"
    if path.exists():
        try:
            return joblib.load(path)
        except Exception:                        # code changed since it was saved: retrain
            path.unlink(missing_ok=True)
    engine = train_engine(data_dir, list(fit_names), stride=STRIDE, log=lambda *_: None)
    joblib.dump(engine, path)
    return engine


@st.cache_resource(show_spinner="Preparing forecast features...")
def get_builder(data_dir: str, split: str, fit_names: tuple, _engine, _wide, _net):
    d = Path(data_dir)
    rd = lambda n, **k: pd.read_csv(d / n, **k) if (d / n).exists() else None   # noqa: E731
    ctx = rd(f"context_{split}.csv")
    inc = rd(f"incidents_{split}.csv", parse_dates=["start_time", "end_time"])
    rw = rd(f"roadworks_{split}.csv", parse_dates=["start_time", "end_time"])
    return FeatureBuilder.build(_wide, _net, _engine.baselines, ctx, inc, rw)


# ----------------------------------------------------------------------------
# the tab
# ----------------------------------------------------------------------------
def render(*, data_dir: str, split: str, splits: list[str], wide: dict, net: pd.DataFrame,
           ts: pd.Timestamp, speed: pd.DataFrame, free_flow: pd.Series, show_chart) -> None:
    fit_names = tuple(fit_splits_for(split, splits))
    try:
        engine = get_engine(data_dir, fit_names)
        fb = get_builder(data_dir, split, fit_names, engine, wide, net)
        fc = forecast_at(engine, fb, ts)
    except FileNotFoundError as e:
        st.error(f"Cannot train the forecast model: {e}")
        return

    if split in fit_names:
        st.warning(f"This dataset ('{split}') is also what the model was trained on, so these "
                   "forecasts are optimistic. Switch to 'validation' for an honest view.")
    st.caption(f"Model: baselines + gradient boosting ({engine.backend}), trained on "
               f"**{engine.trained_on}**. Uses only data up to the slider time. "
               "ADVISORY ONLY - SIMULATED.")

    ff = free_flow.reindex(fc.index)
    ratio = fc.drop(columns="now").div(ff, axis=0)
    ratio_now = fc["now"] / ff
    cols = st.columns(len(engine.horizons) + 1)
    cols[0].metric("Network avg now", f"{ratio_now.mean():.1%}")
    for c, h in zip(cols[1:], engine.horizons):
        r = ratio[f"pred_{h}"]
        c.metric(f"in {h} min", f"{r.mean():.1%}", f"{(r.mean() - ratio_now.mean()) * 100:+.1f} pts")
    st.caption("Average of speed / free-flow speed over all roads.")

    left, right = st.columns([2, 3])
    with left:
        h_show = engine.horizons[-1]
        st.subheader(f"Slowest roads forecast at +{h_show} min")
        t = pd.DataFrame({
            "road": fc.index,
            "now km/h": fc["now"].round(0).to_numpy(),
            **{f"+{h}m": fc[f"pred_{h}"].round(0).to_numpy() for h in engine.horizons},
            f"+{h_show}m % of free-flow": (ratio[f"pred_{h_show}"] * 100).round(0).to_numpy(),
        }).sort_values(f"+{h_show}m % of free-flow").head(10)
        st.dataframe(t, hide_index=True)

        worsening = (fc[f"pred_{h_show}"] - fc["now"]).sort_values().head(5)
        st.write("Biggest expected slow-downs: " +
                 ", ".join(f"{s} ({d:+.0f} km/h)" for s, d in worsening.items()))

    with right:
        auto = ratio[f"pred_{engine.horizons[len(engine.horizons) // 2]}"].idxmin()
        pick = st.selectbox("Road", ["(auto: slowest forecast)"] + list(fc.index), key="fc_seg")
        seg = auto if pick.startswith("(auto") else pick
        show_chart(forecast_figure(speed, ts, seg, fc.loc[seg], float(free_flow[seg]), engine.horizons))

    with st.expander("How accurate has this model been? (backtest)"):
        if EVAL_CSV.exists():
            ev = pd.read_csv(EVAL_CSV)
            ev = ev[(ev.metric == "speed") & (ev.subset == "all")]
            st.write("Speed error in km/h (MAE, lower is better) on the validation days, "
                     "including the simple baselines the model must beat:")
            st.dataframe(ev.pivot_table(index="model", columns="horizon", values="MAE", aggfunc="mean").round(3))
            st.caption("Congested roads are rare in this data; on those, 'persistence' "
                       "(assume nothing changes) is still hard to beat at short horizons.")
        else:
            st.info("Run `python -m src.forecasting.forecast` to create outputs/forecast_eval.csv.")