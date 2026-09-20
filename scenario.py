"""End-to-end scenario pipeline for TrafficSense.

Cleans data, builds features, flags anomalies and incidents, ranks bottlenecks,
evaluates infrastructure candidates via BPR, generates graph-based diversions,
packs local evidence, calls Groq LLM (openai/gpt-oss-120b) with validation and caching,
and saves the comprehensive intelligence report to data/processed/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.advisory.evidence import build_evidence
from src.forecasting.features import FeatureBuilder, HistoricalBaseline, holiday_dates
from src.forecasting.forecast import ForecastEngine, load_split, merge_splits
from src.ingestion.assets import load_assets
from src.ingestion.load_clean import load_traffic_wide
from src.llm.clients import call_groq
from src.llm.fallback import fallback_response
from src.util import load_config, write_json


def select_default_as_of(wide: dict, assets: dict, split: str) -> pd.Timestamp:
    """Find an interesting replay moment: an active incident or peak network congestion."""
    inc = assets.get("incidents")
    if inc is not None and not inc.empty:
        # Pick 10 minutes into the first incident
        first_inc = inc.iloc[0]
        start_ts = pd.Timestamp(first_inc["start_time"]) + pd.Timedelta(minutes=10)
        speed_times = wide["speed_kmh"].index
        nearest = speed_times[speed_times.get_indexer([start_ts], method="nearest")[0]]
        return nearest

    scenarios = assets.get("scenarios")
    if scenarios is not None and not scenarios.empty:
        first_sc = scenarios.iloc[0]
        start_ts = pd.Timestamp(first_sc["start_time"]) + pd.Timedelta(minutes=10)
        speed_times = wide["speed_kmh"].index
        nearest = speed_times[speed_times.get_indexer([start_ts], method="nearest")[0]]
        return nearest

    # Fallback: find timestamp with minimum average speed
    mean_speed = wide["speed_kmh"].mean(axis=1)
    return mean_speed.idxmin()


def run_scenario(
    *,
    split: str = "validation",
    as_of: str | pd.Timestamp | None = None,
    data_dir: str | Path | None = None,
    processed_dir: str | Path | None = None,
    use_llm: bool = True,
    save_cleaned: bool = True,
    log=print,
) -> tuple[dict[str, Any], Path]:
    """Run end-to-end intelligence pipeline for one scenario timestamp."""
    data_path = Path(data_dir or ROOT / "data" / "raw")
    proc_path = Path(processed_dir or ROOT / "data" / "processed")
    proc_path.mkdir(parents=True, exist_ok=True)

    cfg = load_config(ROOT)
    log(f"Loading assets and cleaning traffic data for split '{split}'...")
    assets = load_assets(data_path, split)
    wide, clean_report = load_traffic_wide(data_path / f"traffic_{split}.csv")

    if save_cleaned:
        # Save clean traffic and report to processed dir
        try:
            for metric_name, w_df in wide.items():
                w_df.to_parquet(proc_path / f"cleaned_{split}_{metric_name}.parquet")
            write_json(proc_path / f"cleaning_report_{split}.json", clean_report)
            log(f"Saved cleaned tables and quality report to {proc_path}")
        except Exception as e:
            log(f"Notice: Parquet save skipped ({e}), continuing with analysis.")

    # Determine as_of timestamp
    if as_of is None:
        target_ts = select_default_as_of(wide, assets, split)
    else:
        target_ts = pd.Timestamp(as_of)

    # Snap to available regular 5-minute index
    speed_idx = wide["speed_kmh"].index
    if target_ts not in speed_idx:
        target_ts = speed_idx[speed_idx.get_indexer([target_ts], method="nearest")[0]]

    log(f"Scenario timestamp as_of: {target_ts}")

    # Build baselines and features
    train_split_name = "train" if split != "train" else "validation"
    train_file = data_path / f"traffic_{train_split_name}.csv"
    
    if train_file.exists():
        log(f"Fitting historical baselines on '{train_split_name}' split...")
        train_split = load_split(data_path, train_split_name)
        curr_split = load_split(data_path, split)
        combined = merge_splits([train_split, curr_split])
        engine = ForecastEngine(metrics=("speed",), anchor="persistence")
        engine.fit_baselines(train_split)
    else:
        log("Fitting baselines on current split...")
        curr_split = load_split(data_path, split)
        combined = curr_split
        engine = ForecastEngine(metrics=("speed",), anchor="persistence")
        engine.fit_baselines(curr_split)

    net = assets["network"]
    log("Building feature matrices up to replay timestamp...")
    fb = FeatureBuilder.build(
        combined.wide,
        net,
        engine.baselines,
        combined.context,
        combined.incidents,
        combined.roadworks,
    )

    log("Analyzing network state and constructing evidence packet...")
    evidence = build_evidence(
        as_of=target_ts,
        split=split,
        cfg=cfg,
        fb=fb,
        wide=wide,
        assets=assets,
        engine=engine,
    )

    n_flags = len(evidence.get("flagged", []))
    n_bottlenecks = len(evidence.get("bottlenecks", []))
    n_infra = len(evidence.get("infrastructure_candidates", []))
    n_diversions = len(evidence.get("diversions", []))
    log(f"Evidence prepared: {n_flags} flagged roads, {n_bottlenecks} recurring bottlenecks, "
        f"{n_diversions} diversion routes, {n_infra} infrastructure candidate evaluations.")

    # Call LLM or fallback
    if use_llm:
        log("Calling Groq LLM (openai/gpt-oss-120b) with structured schema validation...")
        llm_response = call_groq(evidence, root=ROOT)
    else:
        log("Using local template fallback for intelligence layer...")
        llm_response = fallback_response(evidence)

    log(f"LLM output source: {llm_response.get('source')} | Summary: {llm_response.get('summary')}")

    # Assemble complete intelligence report
    report = {
        "as_of": target_ts.isoformat(),
        "split": split,
        "clean_report": clean_report,
        "network_summary": evidence.get("network_summary", {}),
        "local_bottlenecks": evidence.get("bottlenecks", []),
        "local_infrastructure": evidence.get("infrastructure_candidates", []),
        "evidence": evidence,
        "llm": llm_response,
    }

    # Save processed JSON report matching dashboard pattern
    ts_slug = target_ts.strftime("%Y%m%d_%H%M%S")
    out_file = proc_path / f"report_{split}_{ts_slug}.json"
    write_json(out_file, report)
    log(f"Successfully generated intelligence report -> {out_file}")

    return report, out_file


def main():
    parser = argparse.ArgumentParser(description="TrafficSense Scenario Intelligence Pipeline")
    parser.add_argument("--split", default="validation", help="Dataset split (train, validation, test)")
    parser.add_argument("--as-of", default=None, help="Timestamp to analyze (YYYY-MM-DD HH:MM)")
    parser.add_argument("--data-dir", default="data/raw", help="Path to raw dataset directory")
    parser.add_argument("--out-dir", default="data/processed", help="Path to processed directory")
    parser.add_argument("--no-llm", action="store_true", help="Skip Groq API and use local template fallback")
    args = parser.parse_args()

    run_scenario(
        split=args.split,
        as_of=args.as_of,
        data_dir=args.data_dir,
        processed_dir=args.out_dir,
        use_llm=not args.no_llm,
    )


if __name__ == "__main__":
    main()
