"""Local speed forecasts to pack into the evidence JSON.

Situation router (beats a single model on the congested / incident slices):
    already congested  -> persistence
    labelled incident  -> historical average (clearance tends toward normal)
    otherwise          -> LightGBM if trained, else anomaly-adjusted
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.forecasting.features import HORIZONS
from src.forecasting.forecast import clip_pred


def local_forecasts(frame: pd.DataFrame, flagged: pd.DataFrame,
                    engine=None, fb=None, sel=None) -> dict:
    """segment_id -> {horizon: {model: speed_kmh, chosen: ...}}."""
    idx = flagged.index.get_level_values("segment_id")
    out: dict = {s: {} for s in idx}
    ff = flagged["free_flow"].to_numpy()
    cur = flagged["speed"].to_numpy()
    ratio = flagged["ratio"].to_numpy()
    inc = flagged["inc_active"].to_numpy() > 0

    gbm_frames = {}
    if engine is not None and fb is not None and sel is not None:
        try:
            for h in engine.horizons:
                gbm_frames[h] = engine.predict_frame(fb, sel, "speed", h)
        except Exception:
            gbm_frames = {}

    for h in HORIZONS:
        hist = flagged[f"speed_hist_h_{h}"] if f"speed_hist_h_{h}" in flagged.columns else None
        if hist is None:
            # FeatureBuilder stores hist at now; horizon hist is in horizon_frame
            hist_vals = flagged["speed_hist_now"].to_numpy()
        else:
            hist_vals = hist.to_numpy()
        pers = np.where(np.isfinite(cur), cur, hist_vals)
        chosen = np.where(ratio < 0.50, pers, np.where(inc, hist_vals, pers))
        for i, seg in enumerate(idx):
            rec = {
                "persistence": _num(pers[i]),
                "historical_average": _num(hist_vals[i]),
                "chosen_model": "persistence" if ratio[i] < 0.50 else (
                    "historical_average" if inc[i] else "persistence"),
            }
            if h in gbm_frames:
                g = gbm_frames[h]
                try:
                    gbm_v = float(g.loc[(g.index.get_level_values("segment_id") == seg), "gbm"].iloc[0])
                    rec["gbm"] = _num(clip_pred("speed", np.array([gbm_v]), np.array([ff[i]]))[0])
                    if rec["chosen_model"] == "persistence" and ratio[i] >= 0.50 and not inc[i]:
                        rec["chosen_model"] = "gbm"
                        rec["chosen"] = rec["gbm"]
                except Exception:
                    pass
            if "chosen" not in rec:
                rec["chosen"] = rec["persistence"] if rec["chosen_model"] == "persistence" else rec["historical_average"]
            out[seg][str(h)] = rec
    return out


def attach_horizon_hist(flagged: pd.DataFrame, fb, sel) -> pd.DataFrame:
    extra = flagged.copy()
    for h in HORIZONS:
        hf = fb.horizon_frame(sel, h)
        extra[f"speed_hist_h_{h}"] = hf["speed_hist_h"].reindex(flagged.index).to_numpy()
    return extra


def _num(v) -> float | None:
    if v is None or not np.isfinite(v):
        return None
    return round(float(v), 2)
