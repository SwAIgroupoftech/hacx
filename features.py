"""Features and baselines for forecasting.

Two things live here:

1. HistoricalBaseline
   "What is normal for this road at this time of day?"  One median value per
   (day type, 5-minute time-of-day bucket, segment), learned from training data.
   Day type = weekday vs weekend/holiday (the dataset only has ~15 training
   days, so a full day-of-week x hour baseline would have 2 samples per cell;
   two day types give ~10 and ~4 and are much more stable).

2. FeatureBuilder
   Turns the cleaned wide tables (time x segment) into one row per
   (timestamp, segment). EVERY feature is causal: it only uses data at or before
   the row's timestamp. The only exceptions are things that are legitimately
   known in advance: the historical baseline at t+h, scheduled roadworks and
   scheduled event level at t+h. tests/test_features.py proves the no-look-ahead
   property by truncating the data and checking the features do not change.

The same code is used for training, for backtesting and (later) for building the
evidence packets that go to the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import scipy.sparse as sp

HORIZONS = (15, 30, 45, 60)
STEP_MIN = 5
LAGS = (1, 2, 3, 6, 12)
BUCKETS = 24 * 60 // STEP_MIN                     # 288 five-minute buckets per day
METRICS = ("speed", "flow", "congestion")
METRIC_COL = {"speed": "speed_kmh", "flow": "flow_vph", "congestion": "congestion_index"}


# ----------------------------------------------------------------------------
# calendar helpers
# ----------------------------------------------------------------------------
def tod_bucket(index: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray((index.hour * 60 + index.minute) // STEP_MIN)


def holiday_dates(context: pd.DataFrame | None) -> frozenset:
    """Dates flagged as holidays in the context file."""
    if context is None or "holiday_flag" not in context.columns:
        return frozenset()
    c = context.copy()
    c["timestamp"] = pd.to_datetime(c["timestamp"])
    days = c.loc[c["holiday_flag"] > 0, "timestamp"].dt.normalize().unique()
    return frozenset(pd.Timestamp(d) for d in days)


def day_type(index: pd.DatetimeIndex, holidays: frozenset = frozenset()) -> np.ndarray:
    """0 = normal weekday, 1 = weekend or holiday."""
    weekend = np.asarray(index.dayofweek >= 5)
    if holidays:
        weekend = weekend | np.asarray(index.normalize().isin(list(holidays)))
    return weekend.astype(int)


# ----------------------------------------------------------------------------
# historical baseline ("normal pattern")
# ----------------------------------------------------------------------------
class HistoricalBaseline:
    """Median value per (day type, time-of-day bucket, segment), lightly smoothed."""

    def __init__(self, smooth_buckets: int = 1):
        self.k = smooth_buckets
        self.table: np.ndarray | None = None      # shape (2, 288, n_segments)
        self.columns: pd.Index | None = None

    def fit(self, wide: pd.DataFrame, holidays: frozenset = frozenset()) -> "HistoricalBaseline":
        self.columns = wide.columns
        dt, b = day_type(wide.index, holidays), tod_bucket(wide.index)
        overall = wide.median()
        tables = []
        for d in (0, 1):
            m = dt == d
            tables.append(wide[m].groupby(b[m]).median().reindex(range(BUCKETS)) if m.any() else None)
        for d in (0, 1):                           # no weekend in the fit window? reuse weekdays
            if tables[d] is None:
                tables[d] = tables[1 - d]
        if tables[0] is None:
            raise ValueError("cannot fit a baseline on an empty table")
        self.table = np.stack([self._smooth(t, overall) for t in tables]).astype("float32")
        return self

    def _smooth(self, t: pd.DataFrame, overall: pd.Series) -> np.ndarray:
        k = self.k
        if k > 0:                                  # circular smoothing across midnight
            padded = pd.concat([t.iloc[-k:], t, t.iloc[:k]])
            t = padded.rolling(2 * k + 1, center=True, min_periods=1).mean().iloc[k:-k]
        t = t.reset_index(drop=True).interpolate(limit_direction="both").fillna(overall)
        return t.to_numpy()

    def at(self, index: pd.DatetimeIndex, holidays: frozenset = frozenset(),
           shift_min: int = 0) -> np.ndarray:
        """Baseline for each timestamp (+ shift), as a (len(index), n_segments) array."""
        ts = index + pd.Timedelta(minutes=shift_min)
        return self.table[day_type(ts, holidays), tod_bucket(ts)]


# ----------------------------------------------------------------------------
# graph and event helpers
# ----------------------------------------------------------------------------
def neighbour_matrices(net: pd.DataFrame, columns) -> tuple[sp.csr_matrix, sp.csr_matrix]:
    """Binary matrices U, D (n x n). U[i, j] = 1 if segment j feeds into segment i;
    D[i, j] = 1 if segment i feeds into segment j. The reverse direction of the
    same street is excluded."""
    pos = {s: i for i, s in enumerate(columns)}
    src = dict(zip(net["segment_id"], net["source_node"]))
    tgt = dict(zip(net["segment_id"], net["target_node"]))
    ends_at: dict[str, list[str]] = {}
    starts_at: dict[str, list[str]] = {}
    for s in net["segment_id"]:
        ends_at.setdefault(tgt[s], []).append(s)
        starts_at.setdefault(src[s], []).append(s)
    up_r, up_c, dn_r, dn_c = [], [], [], []
    for s in net["segment_id"]:
        i = pos[s]
        for j_id in ends_at.get(src[s], []):
            if src[j_id] != tgt[s]:                      # skip the reverse road
                up_r.append(i); up_c.append(pos[j_id])
        for j_id in starts_at.get(tgt[s], []):
            if tgt[j_id] != src[s]:
                dn_r.append(i); dn_c.append(pos[j_id])
    n = len(pos)
    U = sp.csr_matrix((np.ones(len(up_r), "float32"), (up_r, up_c)), shape=(n, n))
    D = sp.csr_matrix((np.ones(len(dn_r), "float32"), (dn_r, dn_c)), shape=(n, n))
    return U, D


def neighbour_mean(values: np.ndarray, A: sp.csr_matrix) -> np.ndarray:
    """Mean over neighbours of a (T x n) matrix; NaN where a road has no neighbour."""
    valid = ~np.isnan(values)
    total = np.nan_to_num(values) @ A.T
    count = valid.astype("float32") @ A.T
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(count > 0, total / count, np.nan)
    return out.astype("float32")


def event_matrix(index: pd.DatetimeIndex, columns, events: pd.DataFrame | None,
                 value_col: str | None) -> np.ndarray:
    """(T x n) matrix: the event's value on its segment while it is active, else 0."""
    M = np.zeros((len(index), len(columns)), "float32")
    if events is None or len(events) == 0:
        return M
    pos = {s: i for i, s in enumerate(columns)}
    for r in events.itertuples():
        j = pos.get(r.segment_id)
        if j is None:
            continue
        lo = index.searchsorted(pd.Timestamp(r.start_time), "left")
        hi = index.searchsorted(pd.Timestamp(r.end_time), "right")
        v = 1.0 if value_col is None else float(getattr(r, value_col))
        M[lo:hi, j] = np.maximum(M[lo:hi, j], v)
    return M


def shift_rows(M: np.ndarray, sel: np.ndarray, k: int) -> np.ndarray:
    """Rows sel + k of M (NaN where that runs past the end of the data)."""
    pos = sel + k
    out = np.full((len(sel), M.shape[1]), np.nan, "float32")
    ok = pos < M.shape[0]
    out[ok] = M[pos[ok]]
    return out


# ----------------------------------------------------------------------------
# feature builder
# ----------------------------------------------------------------------------
@dataclass
class FeatureBuilder:
    """Holds the (time x segment) feature matrices; .frame(positions) makes a long table."""
    index: pd.DatetimeIndex
    columns: pd.Index
    mats: dict
    baselines: dict
    holidays: frozenset
    ctx: pd.DataFrame | None
    roadworks: np.ndarray
    ff: np.ndarray
    _cache: dict = field(default_factory=dict)

    # ---- construction -------------------------------------------------------
    @classmethod
    def build(cls, wide: dict, net: pd.DataFrame, baselines: dict,
              context: pd.DataFrame | None = None,
              incidents: pd.DataFrame | None = None,
              roadworks: pd.DataFrame | None = None) -> "FeatureBuilder":
        cols = pd.Index(net["segment_id"])
        idx = wide["speed_kmh"].index
        T, n = len(idx), len(cols)
        w = {m: wide[c].reindex(columns=cols) for m, c in METRIC_COL.items() if c in wide}
        for extra in ("queue_length_veh", "delay_min"):
            if extra in wide:
                w[extra] = wide[extra].reindex(columns=cols)

        holidays = holiday_dates(context)
        netx = net.set_index("segment_id").loc[cols]
        ff = netx["free_flow_speed_kmh"].to_numpy("float32")
        cap = netx["capacity_vph"].to_numpy("float32")
        bc = lambda v: np.broadcast_to(v.astype("float32"), (T, n))     # noqa: E731

        speed = w["speed"].to_numpy("float32")
        M: dict[str, np.ndarray] = {}
        M["speed"] = speed
        M["flow"] = w["flow"].to_numpy("float32")
        M["congestion"] = w["congestion"].to_numpy("float32")
        if "queue_length_veh" in w:
            M["queue"] = w["queue_length_veh"].to_numpy("float32")
        if "delay_min" in w:
            M["delay"] = w["delay_min"].to_numpy("float32")
        M["ratio"] = speed / ff
        M["vc"] = M["flow"] / cap

        for k in LAGS:
            M[f"speed_d{k}"] = speed - w["speed"].shift(k).to_numpy("float32")
        roll = w["speed"].rolling(6, min_periods=3)
        M["speed_mean6"] = roll.mean().to_numpy("float32")
        M["speed_std6"] = roll.std().to_numpy("float32")
        M["speed_min6"] = roll.min().to_numpy("float32")
        M["flow_d3"] = M["flow"] - w["flow"].shift(3).to_numpy("float32")

        for m in METRICS:                                     # anomaly vs normal pattern
            hist = baselines[m].at(idx, holidays)
            M[f"{m}_hist_now"] = hist
            M[f"{m}_anom"] = M[m] - hist
        M["ratio_anom"] = M["speed_anom"] / ff

        U, D = neighbour_matrices(net, cols)
        M["up_ratio"] = neighbour_mean(M["ratio"], U)
        M["down_ratio"] = neighbour_mean(M["ratio"], D)
        M["up_ratio_d3"] = M["up_ratio"] - np.vstack([np.full((3, n), np.nan, "float32"),
                                                        M["up_ratio"][:-3]])

        tod = (idx.hour * 60 + idx.minute) / 1440.0
        M["tod_sin"] = bc(np.sin(2 * np.pi * tod.to_numpy())[:, None] * np.ones(n))
        M["tod_cos"] = bc(np.cos(2 * np.pi * tod.to_numpy())[:, None] * np.ones(n))
        M["day_type"] = bc(day_type(idx, holidays)[:, None] * np.ones(n))

        ctx = None
        if context is not None:
            ctx = context.copy()
            ctx["timestamp"] = pd.to_datetime(ctx["timestamp"])
            ctx = ctx.drop_duplicates("timestamp").set_index("timestamp").sort_index()
        # always create these columns (NaN if there is no context file) so the model
        # sees the same schema whether or not a context file was provided
        for name, col in (("rain", "rain_intensity"), ("temp", "temperature_c"),
                          ("event_level", "event_level")):
            vals = (ctx[col].reindex(idx).to_numpy("float32") if ctx is not None and col in ctx
                    else np.full(T, np.nan, "float32"))
            M[name] = bc(vals[:, None] * np.ones(n, "float32"))

        M["inc_active"] = event_matrix(idx, cols, incidents, None)
        M["inc_severity"] = event_matrix(idx, cols, incidents, "severity")
        M["inc_lanes"] = event_matrix(idx, cols, incidents, "lanes_blocked")
        rw = event_matrix(idx, cols, roadworks, "closure_fraction")
        M["roadwork"] = rw

        M["free_flow"] = bc(ff)
        M["capacity"] = bc(cap)
        for c in ("lanes", "length_km", "grade_pct", "structural_bottleneck", "importance",
                  "peak_capacity_factor"):
            M[c] = bc(netx[c].to_numpy("float32"))
        M["road_class"] = bc(netx["road_class"].astype("category").cat.codes.to_numpy("float32"))
        M["has_signal"] = bc(netx["signal_id"].notna().to_numpy("float32"))

        return cls(idx, cols, M, baselines, holidays, ctx, rw, ff)

    # ---- long tables --------------------------------------------------------
    def _index(self, sel: np.ndarray) -> pd.MultiIndex:
        n = len(self.columns)
        return pd.MultiIndex.from_arrays(
            [self.index[sel].repeat(n), np.tile(np.asarray(self.columns, dtype=object), len(sel))],
            names=["timestamp", "segment_id"])

    def frame(self, sel: np.ndarray) -> pd.DataFrame:
        """Features known at the row's own timestamp (no horizon-specific columns)."""
        data = {name: np.asarray(mat[sel], dtype="float32").ravel() for name, mat in self.mats.items()}
        return pd.DataFrame(data, index=self._index(sel))

    def horizon_frame(self, sel: np.ndarray, h: int) -> pd.DataFrame:
        """Columns that depend on the horizon: the normal value at t+h and the
        scheduled things (roadworks, event level) that are known in advance."""
        k = h // STEP_MIN
        idx = self.index[sel]
        out = {}
        for m in METRICS:
            out[f"{m}_hist_h"] = self.baselines[m].at(idx, self.holidays, shift_min=h).ravel()
        out["speed_hist_delta_h"] = out["speed_hist_h"] - self.mats["speed_hist_now"][sel].ravel()
        out["roadwork_h"] = shift_rows(self.roadworks, sel, k).ravel()
        if self.ctx is not None and "event_level" in self.ctx:
            ev = self.ctx["event_level"].reindex(idx + pd.Timedelta(minutes=h)).to_numpy("float32")
        else:
            ev = np.full(len(idx), np.nan, "float32")
        out["event_level_h"] = np.repeat(ev, len(self.columns))
        return pd.DataFrame({k_: np.asarray(v, dtype="float32") for k_, v in out.items()},
                            index=self._index(sel))

    def positions(self, start=None, end=None, stride: int = 1) -> np.ndarray:
        """Row positions for a time window (inclusive start, exclusive end)."""
        pos = np.arange(len(self.index))
        if start is not None:
            pos = pos[self.index[pos] >= pd.Timestamp(start)]
        if end is not None:
            pos = pos[self.index[pos] < pd.Timestamp(end)]
        return pos[::stride]