"""Backtest local (and optional LLM) forecasts on FLAGED roads only.

A full-network LLM backtest does not fit a free Groq budget. This script scores
the situation-routed local forecast on the roads operators care about.

    python -m src.pipeline.backtest_flags --split validation --max-times 24
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.flags import flag_snapshot  # noqa: E402
from src.forecasting.features import HORIZONS, FeatureBuilder  # noqa: E402
from src.forecasting.forecast import ForecastEngine, load_split  # noqa: E402
from src.ingestion.assets import load_assets  # noqa: E402
from src.state.forecast_pack import attach_horizon_hist, local_forecasts  # noqa: E402
from src.util import load_config, write_json  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=os.getenv("RAW_DATA_DIR", "data/raw"))
    ap.add_argument("--split", default="validation")
    ap.add_argument("--train", default="train")
    ap.add_argument("--stride", type=int, default=12, help="every Nth timestamp (12 = 1 hour)")
    ap.add_argument("--max-times", type=int, default=24)
    args = ap.parse_args()

    cfg = load_config(ROOT)
    data_dir = Path(args.data_dir)
    data_dir = data_dir if data_dir.is_absolute() else ROOT / data_dir
    train, val = load_split(data_dir, args.train), load_split(data_dir, args.split)
    if val.targets is None:
        sys.exit("need forecast_targets for this split")
    assets = load_assets(data_dir, args.split)
    engine = ForecastEngine(metrics=("speed",), anchor="persistence")
    model_dir = ROOT / "outputs" / "models"
    saved = None
    if model_dir.exists():
        import joblib
        for p in sorted(model_dir.glob("engine_*.joblib")):
            if args.train in p.name:
                try:
                    saved = joblib.load(p)
                    break
                except Exception:
                    pass
    if saved is not None:
        engine = saved
        print(f"engine: {engine.trained_on}")
    else:
        engine.fit_baselines(train)

    fb = FeatureBuilder.build(
        val.wide, assets["network"], engine.baselines,
        assets.get("context"), assets.get("incidents"), assets.get("roadworks"),
    )
    times = fb.index[:: args.stride][: args.max_times]
    rows = []
    for ts in times:
        sel = fb.positions(ts, ts + pd.Timedelta(minutes=1))
        if len(sel) == 0:
            continue
        frame = fb.frame(sel)
        flagged = flag_snapshot(frame, cfg, max_items=8)
        if flagged.empty:
            continue
        flagged = attach_horizon_hist(flagged, fb, sel)
        fc = local_forecasts(frame, flagged, engine=engine if engine.gbm else None, fb=fb, sel=sel)
        for seg, horizons in fc.items():
            tgt_idx = (ts, seg)
            for h, rec in horizons.items():
                col = f"target_speed_{h}m"
                if col not in val.targets.columns:
                    continue
                try:
                    y = float(val.targets.loc[tgt_idx, col])
                except KeyError:
                    continue
                pred = rec.get("chosen")
                if pred is None or not np.isfinite(y):
                    continue
                rows.append({
                    "timestamp": ts.isoformat(),
                    "segment_id": seg,
                    "horizon": int(h),
                    "model": rec.get("chosen_model"),
                    "pred": pred,
                    "actual": round(y, 2),
                    "abs_err": round(abs(pred - y), 2),
                })
        print(f"  {ts}  flagged={len(flagged)}  rows={len(rows)}")

    df = pd.DataFrame(rows)
    out_dir = ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    if df.empty:
        print("no flagged rows scored")
        return
    df.to_csv(out_dir / "flagged_forecast_backtest.csv", index=False)
    summary = (
        df.groupby(["horizon", "model"])["abs_err"]
        .agg(n="count", MAE="mean")
        .reset_index()
        .round(3)
    )
    write_json(out_dir / "flagged_forecast_backtest.json", {
        "n_rows": int(len(df)),
        "n_times": int(df["timestamp"].nunique()),
        "by_horizon_model": summary.to_dict(orient="records"),
        "overall_mae": round(float(df["abs_err"].mean()), 3),
    })
    print("\nMAE on flagged roads (km/h)")
    print(summary.to_string(index=False))
    print(f"overall MAE {df['abs_err'].mean():.2f} km/h  -> outputs/flagged_forecast_backtest.csv")


if __name__ == "__main__":
    main()
