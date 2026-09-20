"""Forecasting 15/30/45/60 minutes ahead, plus an honest backtest.

Run from the project root:
    python -m src.forecasting.forecast --data-dir data/raw --train train --eval validation

MODELS COMPARED (per metric and horizon)
    persistence         "nothing changes": prediction = value right now
    historical_average  "back to normal": the usual value for that time of day at t+h
    anomaly_adjusted    usual value at t+h + alpha * (how far from usual we are now).
                        alpha is ONE number per metric/horizon, fitted on training data.
                        Transparent, cheap, and usually hard to beat. It is also the
                        fallback the LLM layer can use when a check fails.
    gbm                 gradient-boosted trees (LightGBM if installed, else scikit-learn)
                        that learn the RESIDUAL on top of anomaly_adjusted.

NO LEAKAGE
    * forecast_targets_*.csv are used ONLY as labels (y), never as features.
    * Features use data at or before t (see features.py and tests/test_features.py).
    * Baselines are fitted on the training split only; evaluation is on validation.
    * Train rows are sub-sampled in time (--stride) to keep training quick.

The hidden test set has no forecast_targets file we can read, so for the real test
call ForecastEngine.predict(...) on the test features and write the predictions out.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.forecasting.features import (HORIZONS, METRICS, STEP_MIN, FeatureBuilder,  # noqa: E402
                                      HistoricalBaseline, holiday_dates, shift_rows)
from src.ingestion.load_clean import load_traffic_wide  # noqa: E402

CONGESTED_RATIO = 0.70          # subset used for the "congested" rows in the report
STATE_RATIO = 0.50              # config: congestion.speed_ratio_threshold
MOVING_KMH = 5.0                # "something actually changed" subset


# ----------------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------------
@dataclass
class Split:
    name: str
    wide: dict
    report: dict
    context: pd.DataFrame | None
    incidents: pd.DataFrame | None
    roadworks: pd.DataFrame | None
    targets: pd.DataFrame | None       # indexed by (timestamp, segment_id); labels only


def _read_optional(path: Path, **kw):
    return pd.read_csv(path, **kw) if path.exists() else None


def load_split(data_dir, name: str) -> Split:
    d = Path(data_dir)
    wide, report = load_traffic_wide(d / f"traffic_{name}.csv")
    tg = _read_optional(d / f"forecast_targets_{name}.csv", parse_dates=["timestamp"])
    if tg is not None:
        tg = tg.drop_duplicates(["timestamp", "segment_id"]).set_index(["timestamp", "segment_id"])
    return Split(
        name, wide, report,
        _read_optional(d / f"context_{name}.csv"),
        _read_optional(d / f"incidents_{name}.csv", parse_dates=["start_time", "end_time"]),
        _read_optional(d / f"roadworks_{name}.csv", parse_dates=["start_time", "end_time"]),
        tg)


def merge_splits(splits: list[Split]) -> Split:
    """Join splits on one continuous 5-minute time axis (gaps become NaN, so lags and
    'value at t+h' labels never straddle a gap)."""
    wide = {}
    for m in splits[0].wide:
        t = pd.concat([sp.wide[m] for sp in splits]).sort_index()
        t = t[~t.index.duplicated()]
        wide[m] = t.reindex(pd.date_range(t.index[0], t.index[-1], freq="5min"))
    cat = lambda name: (pd.concat([getattr(sp, name) for sp in splits if getattr(sp, name) is not None],  # noqa: E731
                                  ignore_index=True)
                        if any(getattr(sp, name) is not None for sp in splits) else None)
    tg = [sp.targets for sp in splits if sp.targets is not None]
    return Split("+".join(sp.name for sp in splits), wide, {}, cat("context"), cat("incidents"),
                 cat("roadworks"), pd.concat(tg) if tg else None)


def concat_splits(a: Split, b: Split):
    m = merge_splits([a, b])
    return m.wide, m.context, m.incidents, m.roadworks


# ----------------------------------------------------------------------------
# model helpers
# ----------------------------------------------------------------------------
def make_gbm(seed: int = 42):
    try:
        import lightgbm as lgb
        return "lightgbm", lgb.LGBMRegressor(
            n_estimators=400, learning_rate=0.05, num_leaves=63, min_child_samples=50,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=seed,
            n_jobs=-1, verbose=-1)
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor
        return "sklearn-hgb", HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.1, max_leaf_nodes=63, random_state=seed)


def clip_pred(metric: str, pred: np.ndarray, free_flow: np.ndarray) -> np.ndarray:
    """Range check (README safeguard 2): physically plausible values only."""
    if metric == "speed":
        return np.clip(pred, 0, free_flow)
    if metric == "congestion":
        return np.clip(pred, 0, 1)
    return np.clip(pred, 0, None)


def _fit_alpha(y, cur, hist_now, hist_h) -> float:
    dev, gap = (cur - hist_now), (y - hist_h)
    ok = np.isfinite(dev) & np.isfinite(gap)
    denom = float((dev[ok] ** 2).sum())
    return float(np.clip((dev[ok] * gap[ok]).sum() / denom, 0.0, 1.0)) if denom > 0 else 0.0


def labels(fb: FeatureBuilder, sel: np.ndarray, index: pd.MultiIndex, metric: str, h: int,
           targets: pd.DataFrame | None) -> np.ndarray:
    """y for each (timestamp, segment) row: from the target file, or derived from traffic."""
    if targets is not None:
        return targets[f"target_{metric}_{h}m"].reindex(index).to_numpy("float32")
    return shift_rows(fb.mats[metric], sel, h // STEP_MIN).ravel()


def verify_derived_targets(fb: FeatureBuilder, targets: pd.DataFrame, sel: np.ndarray,
                           metrics=METRICS, horizons=HORIZONS) -> pd.DataFrame:
    """Does 'observation at t+h' reproduce the organizer's target file? (It should.)"""
    idx = fb._index(sel)
    rows = []
    for m in metrics:
        for h in horizons:
            mine = labels(fb, sel, idx, m, h, None)
            theirs = targets[f"target_{m}_{h}m"].reindex(idx).to_numpy("float32")
            ok = np.isfinite(mine) & np.isfinite(theirs)
            rows.append(dict(metric=m, horizon=h, rows_compared=int(ok.sum()),
                             max_abs_diff=float(np.abs(mine[ok] - theirs[ok]).max()) if ok.any() else np.nan))
    return pd.DataFrame(rows)


class ForecastEngine:
    """Fits baselines + one GBM per (metric, horizon); predicts from FeatureBuilder rows."""

    def __init__(self, metrics=("speed",), horizons=HORIZONS, seed: int = 42,
                 anchor: str = "persistence"):
        self.metrics, self.horizons, self.seed, self.anchor = tuple(metrics), tuple(horizons), seed, anchor
        self.baselines: dict[str, HistoricalBaseline] = {}
        self.alpha: dict[tuple, float] = {}
        self.gbm: dict[tuple, object] = {}
        self.columns: dict[tuple, list] = {}
        self.backend = None
        self.trained_on: str = ""

    # -- baselines fitted on training data only
    def fit_baselines(self, train: Split) -> dict:
        hol = holiday_dates(train.context)
        from src.forecasting.features import METRIC_COL
        self.baselines = {m: HistoricalBaseline().fit(train.wide[METRIC_COL[m]], hol) for m in METRICS}
        return self.baselines

    def _anchor(self, cur, hn, hh, alpha):
        """The starting guess the GBM corrects. 'persistence' keeps sharp real drops
        (incidents) intact; 'anomaly_adjusted' pulls harder towards the normal pattern."""
        if self.anchor == "persistence":
            return np.where(np.isfinite(cur), cur, hh)
        return hh + alpha * (cur - hn)

    def _frames(self, fb: FeatureBuilder, sel, h):
        base = fb.frame(sel)
        return base, pd.concat([base, fb.horizon_frame(sel, h)], axis=1)

    def fit(self, fb: FeatureBuilder, sel: np.ndarray, targets: pd.DataFrame | None = None, log=print):
        """Train on the rows `sel`. Labels come from `targets` (the organizer's
        forecast_targets file) or, if targets is None, from the traffic table itself:
        the label for time t at horizon h is simply the observation at t+h."""
        for h in self.horizons:
            base, X = self._frames(fb, sel, h)
            for m in self.metrics:
                y = labels(fb, sel, X.index, m, h, targets)
                cur, hn, hh = (X[m].to_numpy(), X[f"{m}_hist_now"].to_numpy(), X[f"{m}_hist_h"].to_numpy())
                a = _fit_alpha(y, cur, hn, hh)
                self.alpha[(m, h)] = a
                ah = self._anchor(cur, hn, hh, a)
                keep = np.isfinite(y) & np.isfinite(ah)
                self.backend, model = make_gbm(self.seed)
                t0 = time.time()
                model.fit(X[keep], (y - ah)[keep])
                self.gbm[(m, h)] = model
                self.columns[(m, h)] = list(X.columns)
                log(f"  trained {m:<10} +{h}m  alpha={a:.2f}  rows={int(keep.sum()):,}  "
                    f"({self.backend}, {time.time() - t0:.0f}s)")
        return self

    def predict_frame(self, fb: FeatureBuilder, sel: np.ndarray, metric: str, h: int) -> pd.DataFrame:
        """All model predictions for one metric and horizon (columns = model names)."""
        _, X = self._frames(fb, sel, h)
        X = X.reindex(columns=self.columns[(metric, h)])       # same schema as training
        cur, hn, hh = X[metric].to_numpy(), X[f"{metric}_hist_now"].to_numpy(), X[f"{metric}_hist_h"].to_numpy()
        ff = X["free_flow"].to_numpy()
        ah = hh + self.alpha[(metric, h)] * (cur - hn)
        anchor = self._anchor(cur, hn, hh, self.alpha[(metric, h)])
        gbm = anchor + self.gbm[(metric, h)].predict(X)
        pers = np.where(np.isfinite(cur), cur, hh)
        ah = np.where(np.isfinite(ah), ah, hh)
        gbm = np.where(np.isfinite(gbm), gbm, ah)
        congested = (cur / np.clip(ff, 1.0, None)) < 0.50
        inc = X["inc_active"].to_numpy() > 0 if "inc_active" in X.columns else np.zeros(len(X), bool)
        # calm roads: GBM; already jammed: persistence; labelled incident: historical avg
        routed = np.where(congested, pers, np.where(inc, hh, gbm))
        out = {
            "persistence": pers,
            "historical_average": hh,
            "anomaly_adjusted": ah,
            "gbm": gbm,
            "routed": routed,
        }
        return pd.DataFrame({k: clip_pred(metric, v, ff) for k, v in out.items()}, index=X.index)

    def predict_all(self, fb: FeatureBuilder, sel: np.ndarray, model: str = "gbm") -> pd.DataFrame:
        """Wide result: pred_<metric>_<h>m columns, one row per (timestamp, segment)."""
        cols = {}
        for m in self.metrics:
            for h in self.horizons:
                cols[f"pred_{m}_{h}m"] = self.predict_frame(fb, sel, m, h)[model]
        return pd.DataFrame(cols)


# ----------------------------------------------------------------------------
# evaluation
# ----------------------------------------------------------------------------
def _scores(err: np.ndarray) -> tuple[float, float]:
    return float(np.mean(np.abs(err))), float(np.sqrt(np.mean(err ** 2)))


def train_engine(data_dir, fit_splits, metrics=("speed",), horizons=HORIZONS, stride: int = 4,
                 anchor: str = "persistence", log=print) -> ForecastEngine:
    """Fit baselines + models on one or more splits, e.g. ["train"] or ["train", "validation"].
    Labels are derived from the traffic itself; where the organizer's target file exists
    it is used as a consistency check (derived label must equal the official one)."""
    dd = Path(data_dir)
    net = pd.read_csv(dd / "network.csv")
    splits = [load_split(dd, n) for n in fit_splits]
    merged = merge_splits(splits)
    engine = ForecastEngine(metrics, horizons, anchor=anchor)
    engine.fit_baselines(merged)
    fb = FeatureBuilder.build(merged.wide, net, engine.baselines, merged.context,
                              merged.incidents, merged.roadworks)
    if merged.targets is not None:
        chk = verify_derived_targets(fb, merged.targets, fb.positions(stride=12), metrics, horizons)
        log(f"label check vs official target files: max diff {chk['max_abs_diff'].max():.4f} "
            f"over {int(chk['rows_compared'].sum()):,} comparisons")
    engine.fit(fb, fb.positions(stride=stride), None, log=log)
    engine.trained_on = "+".join(fit_splits)
    return engine


def evaluate(engine: ForecastEngine, fb: FeatureBuilder, targets: pd.DataFrame,
             sel: np.ndarray) -> pd.DataFrame:
    rows = []
    base = fb.frame(sel)
    ff, spd_now, inc = base["free_flow"].to_numpy(), base["speed"].to_numpy(), base["inc_active"].to_numpy() > 0
    for h in engine.horizons:
        y_speed = targets[f"target_speed_{h}m"].reindex(base.index).to_numpy()
        ratio_true = y_speed / ff
        subsets = {
            "all": np.ones(len(base), bool),
            "congested": ratio_true < CONGESTED_RATIO,
            "moving": np.abs(y_speed - np.nan_to_num(spd_now, nan=0)) >= MOVING_KMH,
            "incident_now": inc,
        }
        for m in engine.metrics:
            y = targets[f"target_{m}_{h}m"].reindex(base.index).to_numpy()
            preds = engine.predict_frame(fb, sel, m, h)
            for model, p in preds.items():
                p = p.to_numpy()
                for sname, smask in subsets.items():
                    ok = smask & np.isfinite(y) & np.isfinite(p)
                    if ok.sum() == 0:
                        continue
                    mae, rmse = _scores(p[ok] - y[ok])
                    rows.append(dict(metric=m, horizon=h, model=model, subset=sname,
                                     n=int(ok.sum()), MAE=mae, RMSE=rmse))
                if m == "speed":                              # state F1: congested (<50% of free flow)?
                    ok = np.isfinite(y) & np.isfinite(p)
                    t_state, p_state = (y[ok] / ff[ok]) < STATE_RATIO, (p[ok] / ff[ok]) < STATE_RATIO
                    tp = float((t_state & p_state).sum())
                    prec = tp / max(p_state.sum(), 1)
                    rec = tp / max(t_state.sum(), 1)
                    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
                    rows.append(dict(metric=m, horizon=h, model=model, subset="state_f1",
                                     n=int(ok.sum()), MAE=np.nan, RMSE=np.nan, F1=f1))
    return pd.DataFrame(rows)


def print_report(res: pd.DataFrame) -> None:
    order = ["persistence", "historical_average", "anomaly_adjusted", "gbm", "routed"]
    for m in res["metric"].unique():
        for subset in ("all", "congested", "moving", "incident_now"):
            t = res[(res.metric == m) & (res.subset == subset)]
            if t.empty:
                continue
            piv = t.pivot(index="model", columns="horizon", values="MAE").reindex(order).round(3)
            print(f"\n{m.upper()} MAE, subset = {subset}  (n per horizon ~ {int(t['n'].median()):,})")
            print(piv.to_string())
        f1 = res[(res.metric == m) & (res.subset == "state_f1")]
        if not f1.empty:
            print(f"\n{m.upper()} congestion-state F1 (speed < {STATE_RATIO:.0%} of free flow)")
            print(f1.pivot(index="model", columns="horizon", values="F1").reindex(order).round(3).to_string())


# ----------------------------------------------------------------------------
# command line
# ----------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="data/raw")
    ap.add_argument("--train", default="train")
    ap.add_argument("--eval", default="validation")
    ap.add_argument("--metrics", nargs="+", default=["speed"], choices=list(METRICS))
    ap.add_argument("--horizons", nargs="+", type=int, default=list(HORIZONS))
    ap.add_argument("--stride", type=int, default=3, help="use every Nth training timestamp")
    ap.add_argument("--anchor", default="persistence", choices=["anomaly_adjusted", "persistence"])
    ap.add_argument("--eval-stride", type=int, default=1)
    ap.add_argument("--official-train-targets", action="store_true",
                    help="train on forecast_targets_train.csv (only every 5th timestamp) "
                         "instead of labels derived from traffic_train (every timestamp)")
    ap.add_argument("--out", default="outputs/forecast_eval.csv")
    ap.add_argument("--save-model", default=None, help="optional path for a joblib dump")
    a = ap.parse_args()

    dd = Path(a.data_dir)
    dd = dd if dd.is_absolute() else ROOT / dd
    t0 = time.time()
    print("loading + cleaning ...")
    train, val = load_split(dd, a.train), load_split(dd, a.eval)
    net = pd.read_csv(dd / "network.csv")
    if val.targets is None:
        sys.exit("forecast_targets_<split>.csv is needed to evaluate")

    engine = ForecastEngine(a.metrics, a.horizons, anchor=a.anchor)
    engine.fit_baselines(train)
    wide, ctx, inc, rw = concat_splits(train, val)
    fb = FeatureBuilder.build(wide, net, engine.baselines, ctx, inc, rw)
    print(f"features built: {len(fb.mats)} per row, {len(fb.index)} timestamps x {len(fb.columns)} roads "
          f"({time.time() - t0:.0f}s)")

    t_start, v_start = train.wide["speed_kmh"].index[0], val.wide["speed_kmh"].index[0]
    sel_train = fb.positions(t_start, v_start, stride=a.stride)
    sel_val = fb.positions(v_start, None, stride=a.eval_stride)
    print(f"training on {len(sel_train) * len(fb.columns):,} rows, evaluating on "
          f"{len(sel_val) * len(fb.columns):,} rows")
    print("\nlabel check on validation (derived 'value at t+h' vs organizer target file):")
    chk = verify_derived_targets(fb, val.targets, fb.positions(v_start, None, stride=12), a.metrics, a.horizons)
    print(chk.to_string(index=False))
    engine.fit(fb, sel_train, train.targets if a.official_train_targets else None)

    res = evaluate(engine, fb, val.targets, sel_val)
    out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)
    print_report(res)
    print(f"\nfull table -> {out}   ({time.time() - t0:.0f}s total, gbm backend: {engine.backend})")

    if a.save_model:
        import joblib
        joblib.dump(engine, a.save_model)


if __name__ == "__main__":
    main()