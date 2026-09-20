"""Load and clean the traffic files.

Works for the clean train/validation files AND for the noisy hidden test files
(the manifest lists: missing values, duplicates, spikes, stuck sensors,
impossible negative readings, shuffled rows).

Main entry point:
    wide, report = load_traffic_wide("data/raw/traffic_validation.csv")

    wide["speed_kmh"]   -> table: one row per timestamp, one column per segment
    report              -> dict describing what was fixed (show this in the UI)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

METRICS = ["speed_kmh", "flow_vph", "congestion_index", "queue_length_veh", "delay_min"]
USECOLS = ["timestamp", "segment_id"] + METRICS
STEP = "5min"


def find_splits(data_dir) -> list[str]:
    """Find which traffic files exist, e.g. ['train', 'validation'] (later also 'test').

    We look for traffic_<name>.csv so nothing is hard-coded: when the organizers
    add a new file to the folder, it simply shows up.
    """
    prefix = "traffic_"
    return [p.stem[len(prefix):] for p in sorted(Path(data_dir).glob("traffic_*.csv"))]


def clean_and_pivot(
    df: pd.DataFrame,
    max_speed_kmh: float = 160.0,   # readings above this are impossible
    spike_kmh: float = 20.0,        # isolated jump this far from neighbours = spike
    stuck_window: int = 12,         # identical readings for 12 steps (1 hour) = stuck sensor
    max_gap: int = 3,               # only fill gaps up to 3 steps (15 min)
    saturated_queue_veh: float = 50.0,  # queue above this = real gridlock, not a fault
):
    """Clean a long table and return (dict of wide tables, report)."""
    report: dict = {"rows_in": int(len(df))}
    df = df.copy()

    # 1) bad timestamps / ids
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    bad = df["timestamp"].isna() | df["segment_id"].isna()
    report["bad_timestamp_or_id_rows_removed"] = int(bad.sum())
    df = df[~bad]
    df["segment_id"] = df["segment_id"].astype(str)

    # 2) duplicates (same segment, same time)
    dup = df.duplicated(["timestamp", "segment_id"], keep="first")
    report["duplicate_rows_removed"] = int(dup.sum())
    df = df[~dup]

    # 3) impossible values -> missing
    invalid = {}
    for m in METRICS:
        if m not in df.columns:
            continue
        df[m] = pd.to_numeric(df[m], errors="coerce")
        wrong = df[m] < 0
        if m == "speed_kmh":
            wrong |= df[m] > max_speed_kmh
        invalid[m] = int(wrong.sum())
        df.loc[wrong, m] = np.nan
    report["impossible_values_nulled"] = invalid

    # 4) pivot each metric into a (time x segment) table on a regular 5-minute grid
    raw_wide = {}
    for m in METRICS:
        if m not in df.columns:
            continue
        w = df.pivot(index="timestamp", columns="segment_id", values=m).sort_index()
        full = pd.date_range(w.index.min(), w.index.max(), freq=STEP)
        report["missing_timestamps"] = int(len(full) - len(w.index))
        raw_wide[m] = w.reindex(full)

    wide, spikes, stuck, filled, remaining = {}, 0, 0, 0, 0
    for m, w in raw_wide.items():
        if m == "speed_kmh":
            # spike = an isolated reading far from the median of its neighbours.
            # (a real incident is a SUSTAINED drop, so it is kept)
            med = w.rolling(5, center=True, min_periods=3).median()
            is_spike = (w - med).abs() > spike_kmh
            spikes = int(is_spike.sum().sum())
            w = w.mask(is_spike)

            # stuck sensor = exactly the same value for a long time.
            # Three look-alikes are NOT faults, so we exclude them:
            #  (a) free-flowing roads sit at their top speed for hours
            #  (b) gridlock: in the validation data some roads freeze at the
            #      simulator's caps (flow 4502, occupancy 98%, queue > 1000)
            #  (c) a real severe incident pins speed at the simulator's floor
            #      (e.g. 11.2 km/h for an hour) while flow keeps moving
            # So we only call it "stuck" when speed AND flow are both frozen.
            # ("constant" = rolling max minus min is exactly 0; std can suffer rounding error)
            flat = (w.rolling(stuck_window).max() - w.rolling(stuck_window).min()) == 0
            flow = raw_wide.get("flow_vph")
            flat_flow = ((flow.rolling(stuck_window).max() - flow.rolling(stuck_window).min()) == 0
                         if flow is not None else True)
            below_top = w < 0.97 * w.quantile(0.95)
            queue = raw_wide.get("queue_length_veh")
            gridlock = (queue > saturated_queue_veh) if queue is not None else False
            is_stuck = flat & flat_flow & below_top & ~gridlock
            stuck = int(is_stuck.sum().sum())
            w = w.mask(is_stuck)

        before = w.isna()
        w = w.interpolate(limit=max_gap, limit_area="inside")
        if m == "speed_kmh":
            filled = int((before & w.notna()).sum().sum())
            remaining = int(w.isna().sum().sum())
        wide[m] = w.astype("float32")

    report["spikes_removed"] = spikes
    report["stuck_sensor_readings_removed"] = stuck
    report["speed_gaps_filled"] = filled
    report["speed_still_missing"] = remaining
    return wide, report


def load_traffic_wide(path):
    """Read a traffic CSV from disk, clean it, and return (wide tables, report)."""
    path = Path(path)
    header = pd.read_csv(path, nrows=0).columns
    cols = [c for c in USECOLS if c in header]
    df = pd.read_csv(path, usecols=cols)
    return clean_and_pivot(df)
