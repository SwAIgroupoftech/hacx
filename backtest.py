"""Backtest and accuracy evaluation script for TrafficSense.

Evaluates forecasting models across 15, 30, 45, and 60-minute horizons
with strict no-look-ahead windowing. Compares:
    - persistence
    - historical_average
    - anomaly_adjusted
    - gbm (LightGBM)
    - situation_router (hybrid routing: persistence when congested,
      historical average when incident clearing, gbm when calm)

Generates MAE, RMSE, and Congestion-State F1 metrics broken down by
subsets (All, Congested, Moving, Incident Active).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.forecasting.features import HORIZONS, FeatureBuilder
from src.forecasting.forecast import (
    CONGESTED_RATIO,
    MOVING_KMH,
    STATE_RATIO,
    ForecastEngine,
    _scores,
    clip_pred,
    load_split,
    merge_splits,
)


def evaluate_backtest(
    engine: ForecastEngine,
    fb: FeatureBuilder,
    targets: pd.DataFrame,
    sample_timestamps: list[pd.Timestamp],
    metrics=("speed",),
    horizons=HORIZONS,
) -> pd.DataFrame:
    """Run walk-forward evaluation across sample timestamps."""
    rows = []
    
    for ts in sample_timestamps:
        if ts not in fb.index:
            continue
        loc = fb.index.get_loc(ts)
        sel = np.array([loc])
        base = fb.frame(sel)
        ff = base["free_flow"].to_numpy()
        spd_now = base["speed"].to_numpy()
        inc = base["inc_active"].to_numpy() > 0
        cur_ratio = spd_now / np.clip(ff, 1.0, None)

        for h in horizons:
            y_speed = targets[f"target_speed_{h}m"].reindex(base.index).to_numpy()
            ratio_true = y_speed / ff
            subsets = {
                "all": np.ones(len(base), bool),
                "congested": ratio_true < CONGESTED_RATIO,
                "moving": np.abs(y_speed - np.nan_to_num(spd_now, nan=0)) >= MOVING_KMH,
                "incident_now": inc,
            }

            for m in metrics:
                y = targets[f"target_{m}_{h}m"].reindex(base.index).to_numpy()
                preds = engine.predict_frame(fb, sel, m, h)
                
                # Add situation router prediction
                # congested -> persistence, incident clearing -> hist avg, calm -> gbm
                pers = preds["persistence"].to_numpy()
                hist = preds["historical_average"].to_numpy()
                gbm = preds["gbm"].to_numpy()
                router_pred = np.where(cur_ratio < 0.50, pers, np.where(inc, hist, gbm))
                preds["situation_router"] = clip_pred(m, router_pred, ff)

                for model_name, p in preds.items():
                    p_arr = p.to_numpy() if hasattr(p, "to_numpy") else np.array(p)
                    for sname, smask in subsets.items():
                        ok = smask & np.isfinite(y) & np.isfinite(p_arr)
                        if ok.sum() == 0:
                            continue
                        mae, rmse = _scores(p_arr[ok] - y[ok])
                        rows.append({
                            "timestamp": ts,
                            "metric": m,
                            "horizon": h,
                            "model": model_name,
                            "subset": sname,
                            "n": int(ok.sum()),
                            "MAE": mae,
                            "RMSE": rmse,
                        })

                    # Congestion state classification F1
                    if m == "speed":
                        ok = np.isfinite(y) & np.isfinite(p_arr)
                        t_state = (y[ok] / ff[ok]) < STATE_RATIO
                        p_state = (p_arr[ok] / ff[ok]) < STATE_RATIO
                        tp = float((t_state & p_state).sum())
                        prec = tp / max(p_state.sum(), 1)
                        rec = tp / max(t_state.sum(), 1)
                        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
                        rows.append({
                            "timestamp": ts,
                            "metric": m,
                            "horizon": h,
                            "model": model_name,
                            "subset": "state_f1",
                            "n": int(ok.sum()),
                            "MAE": np.nan,
                            "RMSE": np.nan,
                            "F1": f1,
                        })

    return pd.DataFrame(rows)


def summarize_backtest(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate per-timestamp results into overall benchmark table."""
    mae_sub = df[df["subset"] != "state_f1"].groupby(["metric", "subset", "model", "horizon"])["MAE"].mean().reset_index()
    f1_sub = df[df["subset"] == "state_f1"].groupby(["metric", "model", "horizon"])["F1"].mean().reset_index()
    return mae_sub, f1_sub


def main():
    parser = argparse.ArgumentParser(description="TrafficSense Forecast Backtest & Accuracy Evaluation")
    parser.add_argument("--data-dir", default="data/raw", help="Path to raw data directory")
    parser.add_argument("--train", default="train", help="Training split")
    parser.add_argument("--eval", default="validation", help="Evaluation split")
    parser.add_argument("--stride", type=int, default=6, help="Training sampling stride")
    parser.add_argument("--eval-samples", type=int, default=15, help="Number of timestamps to evaluate in backtest")
    parser.add_argument("--out", default="outputs/forecast_eval.csv", help="Output evaluation CSV")
    args = parser.parse_args()

    data_dir = Path(args.data_dir or ROOT / "data" / "raw")
    t0 = time.time()
    print(f"Loading data from {data_dir} for backtest...")
    train = load_split(data_dir, args.train)
    val = load_split(data_dir, args.eval)
    net = pd.read_csv(data_dir / "network.csv")

    if val.targets is None:
        sys.exit("Validation forecast targets file required for backtest.")

    print("Fitting baseline models on training split...")
    engine = ForecastEngine(metrics=("speed",), anchor="persistence")
    engine.fit_baselines(train)

    combined = merge_splits([train, val])
    print("Building features across timeline...")
    fb = FeatureBuilder.build(
        combined.wide, net, engine.baselines, combined.context, combined.incidents, combined.roadworks
    )

    t_start, v_start = train.wide["speed_kmh"].index[0], val.wide["speed_kmh"].index[0]
    sel_train = fb.positions(t_start, v_start, stride=args.stride)
    print(f"Training GBM residual engine on {len(sel_train) * len(fb.columns):,} rows...")
    engine.fit(fb, sel_train, log=print)

    # Pick evenly spaced timestamps from validation
    val_times = val.wide["speed_kmh"].index
    # avoid the very end where future targets might exceed range
    valid_window = val_times[val_times <= val_times[-1] - pd.Timedelta(minutes=60)]
    step = max(len(valid_window) // args.eval_samples, 1)
    sample_ts = list(valid_window[::step][:args.eval_samples])
    print(f"\nRunning walk-forward backtest across {len(sample_ts)} replay timestamps...")

    raw_p = out_p.parent / "forecast_eval_by_timestamp.csv"
    raw_results.to_csv(raw_p, index=False)

    agg = raw_results.groupby(["metric", "horizon", "model", "subset"], as_index=False).agg({
        "n": "sum",
        "MAE": "mean",
        "RMSE": "mean",
        "F1": "mean",
    })
    agg.to_csv(out_p, index=False)

    mae_table, f1_table = summarize_backtest(raw_results)
    
    print("\n" + "=" * 70)
    print("FORECASTING ACCURACY BACKTEST REPORT (MAE km/h by horizon)")
    print("=" * 70)
    for subset in ["all", "congested", "moving", "incident_now"]:
        sub_df = mae_table[mae_table["subset"] == subset]
        if not sub_df.empty:
            piv = sub_df.pivot(index="model", columns="horizon", values="MAE").round(2)
            print(f"\nSubset: {subset.upper()}")
            print(piv.to_string())

    print("\nCONGESTION-STATE F1 (speed < 50% free-flow)")
    piv_f1 = f1_table.pivot(index="model", columns="horizon", values="F1").round(3)
    print(piv_f1.to_string())
    print("=" * 70)
    print(f"Full backtest details saved -> {out_p} ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
