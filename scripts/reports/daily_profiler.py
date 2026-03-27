"""
daily_profiler.py - CLI for the Institutional Daily Profiler.

Reads live Parquet data for current session statuses, then filters the
historical profiler JSON to produce standardized probability tables.
No reference to historical dates is used for context — only live data.

Usage:
    python scripts/reports/daily_profiler.py --ticker NQ1 --session Asia
    python scripts/reports/daily_profiler.py --ticker NQ1 --session London
    python scripts/reports/daily_profiler.py --ticker NQ1 --all
    python scripts/reports/daily_profiler.py --ticker NQ1 --session NY1 --intra "Long False"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.libs.profiler import (
    ProfilerData, ProfilerFilter, ProfilerStats, ProfilerReport,
    get_live_context, get_current_trading_date, get_current_session,
)


def main():
    parser = argparse.ArgumentParser(description="Institutional Daily Profiler Report")
    parser.add_argument("--ticker",  default="NQ1",   help="Ticker: NQ1, ES1, etc.")
    parser.add_argument("--session", default="Asia",  help="Session: Asia, London, NY1, NY2")
    parser.add_argument("--intra",   default=None,    help="Override intra-state filter")
    parser.add_argument("--all",     action="store_true", help="Run all 4 sessions")
    args = parser.parse_args()

    # --- 1. Determine today's trading date (from the clock, NOT from JSON) ---
    trading_date = get_current_trading_date()
    active_session = get_current_session()
    print(f"\n[Date]  Trading date : {trading_date}")
    print(f"[Time]  Active session: {active_session or 'Between sessions'}")

    # --- 2. Load live context from Parquet (historical + live fused) ---
    print(f"\n[Context] Fetching live session statuses for {args.ticker}...")
    context = get_live_context(args.ticker)

    # Display what we know about today
    print(f"  Prev NY1  : {context.get('prev_ny1_status') or '?'}")
    print(f"  Prev NY2  : {context.get('prev_ny2_status') or '?'}")
    print(f"  Asia      : {context.get('asia_status') or '(in progress)'}")
    print(f"  London    : {context.get('lon_status') or '(pending)'}")
    print(f"  NY1       : {context.get('ny1_status') or '(pending)'}")
    print(f"  NY2       : {context.get('ny2_status') or '(pending)'}")

    # --- 3. Load historical profiler JSON (statistics only) ---
    print(f"\n[Data] Loading {args.ticker} historical profiler JSON...", end=" ", flush=True)
    try:
        data = ProfilerData.load(args.ticker)
    except FileNotFoundError as e:
        print(f"\n[X] {e}")
        sys.exit(1)
    print(f"ok ({len(data.trading_dates)} trading days, {len(data.sessions)} sessions)")

    # --- 4. Run report for selected session(s) ---
    sessions_to_run = ["Asia", "London", "NY1", "NY2"] if args.all else [args.session]

    for session in sessions_to_run:
        # Intra-state: override from flag, else auto-detect from live context
        intra = args.intra
        if intra is None:
            session_key_map = {
                "Asia": "asia_status", "London": "lon_status",
                "NY1": "ny1_status",   "NY2": "ny2_status"
            }
            intra = context.get(session_key_map.get(session))
            if intra:
                print(f"\n  [~] Auto-intra for {session}: {intra}")

        # Filter historical JSON using live context
        matched = ProfilerFilter.filter(data, session, context, intra_state=intra)
        print(f"\n[>] {args.ticker} {session} | Trading Day: {trading_date} | Matches: {len(matched)}")

        # Compute stats and render
        result = ProfilerStats.compute(matched)
        ProfilerReport.print(result, args.ticker, session,
                             context=context, intra_state=intra,
                             reference_date=trading_date)

        if args.all:
            print("\n" + "-" * 80)


if __name__ == "__main__":
    main()
