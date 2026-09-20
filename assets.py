"""Load supporting CSVs (network, incidents, planning, …). Missing files become None."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _read(path: Path, **kw):
    return pd.read_csv(path, **kw) if path.exists() else None


def load_assets(data_dir, split: str) -> dict:
    d = Path(data_dir)
    return {
        "network": pd.read_csv(d / "network.csv"),
        "nodes": pd.read_csv(d / "nodes.csv"),
        "context": _read(d / f"context_{split}.csv"),
        "incidents": _read(d / f"incidents_{split}.csv", parse_dates=["start_time", "end_time"]),
        "roadworks": _read(d / f"roadworks_{split}.csv", parse_dates=["start_time", "end_time"]),
        "turn_restrictions": _read(d / "turn_restrictions.csv"),
        "od_demand": _read(d / "od_demand_profiles.csv"),
        "planning": _read(d / "planning_candidates.csv"),
        "signal_plans": _read(d / "signal_plans.csv"),
        "scenarios": _read(d / "scenario_examples.csv", parse_dates=["start_time", "end_time"]),
        "targets": _read(d / f"forecast_targets_{split}.csv", parse_dates=["timestamp"]),
    }
