"""Run an end-to-end TrafficSense intelligence scenario.

Usage:
    python scripts/run_scenario.py --split validation
    python scripts/run_scenario.py --split validation --as-of "2026-01-16 16:40"
    python scripts/run_scenario.py --split validation --scenario-id TRAIN_SC_001
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

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

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.scenario import run_scenario


def main():
    parser = argparse.ArgumentParser(description="Run TrafficSense Scenario Pipeline")
    parser.add_argument("--split", default="validation", help="Dataset split to evaluate")
    parser.add_argument("--as-of", default=None, help="Replay timestamp (YYYY-MM-DD HH:MM)")
    parser.add_argument("--scenario-id", default=None, help="Scenario ID from scenario_examples.csv")
    parser.add_argument("--data-dir", default="data/raw", help="Directory of raw data files")
    parser.add_argument("--out-dir", default="data/processed", help="Directory for output JSON reports")
    parser.add_argument("--no-llm", action="store_true", help="Use local rule-based templates instead of Groq API")
    args = parser.parse_args()

    as_of = args.as_of
    if args.scenario_id:
        sc_path = Path(args.data_dir) / "scenario_examples.csv"
        if sc_path.exists():
            sc_df = pd.read_csv(sc_path)
            match = sc_df[sc_df["scenario_id"] == args.scenario_id]
            if not match.empty:
                st_time = pd.Timestamp(match.iloc[0]["start_time"]) + pd.Timedelta(minutes=10)
                as_of = st_time.strftime("%Y-%m-%d %H:%M")
                print(f"Loaded scenario {args.scenario_id}: setting as_of to {as_of}")

    report, out_path = run_scenario(
        split=args.split,
        as_of=as_of,
        data_dir=args.data_dir,
        processed_dir=args.out_dir,
        use_llm=not args.no_llm,
    )

    llm = report.get("llm", {})
    print("\n" + "=" * 70)
    print(f"TrafficSense Intelligence Report | As Of: {report.get('as_of')}")
    print(f"Source: {llm.get('source')} | File: {out_path.name}")
    print("=" * 70)
    print(f"Summary: {llm.get('summary')}\n")

    print("--- Forecasts (15-60 min) ---")
    fc_df = pd.DataFrame(llm.get("forecasts", []))
    if not fc_df.empty:
        print(fc_df.to_string(index=False))

    print("\n--- Incidents Detected & Classified ---")
    inc_df = pd.DataFrame(llm.get("incidents", []))
    if not inc_df.empty:
        print(inc_df.to_string(index=False))

    print("\n--- Operational & Diversion Advisories ---")
    for a in llm.get("advisories", []):
        aff = ", ".join(a.get("affected_segments") or [])
        via = ", ".join(a.get("diversion") or [])
        print(f"* {a.get('title')} -> Action: {a.get('action')}")
        print(f"  Affected: [{aff}] | Via: [{via}] | Saving: ~{a.get('expected_saving_min')} min | Conf: {a.get('confidence')}")

    print("\n--- Infrastructure Counterfactual Proposals (BPR Simulated) ---")
    for row in llm.get("infrastructure", []):
        print(f"* {row.get('candidate_id')} on {row.get('segment_id')}: {row.get('intervention')} "
              f"(~{row.get('estimated_delay_reduction_pct')}% delay reduction)")
        print(f"  Rationale: {row.get('rationale')}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
