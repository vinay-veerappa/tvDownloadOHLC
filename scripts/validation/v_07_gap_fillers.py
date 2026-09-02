"""Validation Script: Mickey Gap-Filler Engines (Step 0.7)

Independently validates each of the six gap-filler checks for NQ1 and ES1:
  [1] Open-Price Flag Flip (prev-day open pivot, touch/toggle state)
  [2] True/False Streak Variance (proxy classification + streak state)
  [3] DRO Checkbook Verdict (via session_budget_engine)
  [4] Out-of-Stat Extremes (four generic H/L windows)
  [5] Magic Hour (06:00-08:30, 75% continuation)
  [6] 4-Step Continuation Checklist (structural, spot-checked)

Each aspect is validated in isolation and its derived parquet is checked.
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from scripts.wargaming.mickey_gap_fillers import (
    compute_open_price_flag_flip,
    compute_true_false_streaks,
    compute_out_of_stat_extremes,
    compute_magic_hour,
    compute_all_gap_fillers,
    format_gap_fillers_markdown,
    build_continuation_checklist,
    GAP_DERIVED_DIR,
)
from scripts.wargaming.session_budget_engine import compute_session_budget
from scripts.utils.fused_data_loader import load_fused_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def validate_gap_fillers_for_ticker(ticker: str, t_date=None) -> bool:
    ok = True
    print(f"\n{'=' * 60}")
    print(f"   VALIDATING GAP FILLERS FOR TICKER: {ticker}")
    print(f"{'=' * 60}")

    t_dt = t_date or datetime.now().date()
    df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
    if df_1m is None or df_1m.empty:
        print(f"[X] FAIL: no 1m data for {ticker}")
        return False
    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")

    # ---- [1] Open-Price Flag Flip ----
    print(f"\n[1] Open-Price Flag Flip...")
    spot = float(df_1m["close"].iloc[-1])
    ff = compute_open_price_flag_flip(df_1m, t_dt, spot)
    if not ff.get("available"):
        print("    [X] FAIL: not available")
        ok = False
    else:
        print(f"    prev_open: {ff['prev_open']} | spot: {ff['spot']} "
              f"| dist: {ff['spot_vs_pivot_bps']:+.1f} bps")
        print(f"    touched_overnight: {ff['touched_overnight']} -> state: {ff['state']}")
        # sanity: state must be one of the three canonical states
        if ff["state"] not in {"FLAG_FLIPPED", "AT_PIVOT", "INTACT"}:
            print("    [X] FAIL: invalid state")
            ok = False
        else:
            print("    [OK] pass")

    # ---- [2] True/False Streak Variance ----
    print(f"\n[2] True/False Streak Variance...")
    st = compute_true_false_streaks(ticker, t_dt)
    if not st.get("available"):
        print("    [X] FAIL: not available")
        ok = False
    else:
        print(f"    source: {st['source']} | history: {st.get('history_start')} -> {st.get('history_end')} "
              f"({st['sample_days']} days)")
        print(f"    current: {st['current_streak']}x {st['current_type']} | "
              f"P(True next)={st['p_true_next']}% | P(False next)={st['p_false_next']}%")
        print(f"    max False ever: {st['max_false_streak_ever']} | max True ever: {st['max_true_streak_ever']}")
        if st.get("alert"):
            print(f"    ALERT: {st['alert']}")
        if st["sample_days"] < 30 or st.get("source") != "profiler_ny1":
            print("    [X] FAIL: insufficient history or wrong source")
            ok = False
        else:
            print("    [OK] pass")

    # ---- [3] DRO Checkbook Verdict ----
    print(f"\n[3] DRO Checkbook Verdict (session_budget_engine)...")
    dro = compute_session_budget(ticker=ticker, target_date=t_dt.isoformat())
    print(f"    10d median: {dro['10d_median_range_pts']} pts | overnight spent: "
          f"{dro['overnight_spend_pct']}% | regime: {dro['regime']}")
    if dro["regime"] not in {"COILED / CHEAP VOLATILITY", "OVERSPENT / EXPENSIVE VOLATILITY",
                             "NORMAL VOLATILITY BUDGET"}:
        print("    [X] FAIL: invalid regime classification")
        ok = False
    else:
        print("    [OK] pass")

    # ---- [4] Out-of-Stat Extremes ----
    print(f"\n[4] Out-of-Stat Extremes (synthetic probe times)...")
    oos = compute_out_of_stat_extremes(df_1m, t_dt, "05:39", "10:05")
    for f in oos["flags"]:
        print(f"    {f['extreme']}@{f['time']} -> in_stat={f['in_stat']} window={f['window']}")
    # 05:39 is outside all four windows -> must be flagged; 10:05 inside RTH window
    hod_flag = next(f for f in oos["flags"] if f["extreme"] == "HOD")
    lod_flag = next(f for f in oos["flags"] if f["extreme"] == "LOD")
    if hod_flag["in_stat"] or not lod_flag["in_stat"]:
        print("    [X] FAIL: window classification wrong")
        ok = False
    else:
        print(f"    n_out_of_stat={oos['n_out_of_stat']}")
        print("    [OK] pass")

    # ---- [5] Magic Hour ----
    print(f"\n[5] Magic Hour (06:00-08:30)...")
    mg = compute_magic_hour(df_1m, t_dt)
    print(f"    state: {mg['state']} | {mg.get('note', '')}")
    if mg.get("core_range"):
        print(f"    core range: {mg['core_range']}")
    if mg["state"] not in {"PENDING", "BROKEN_UP", "BROKEN_DOWN", "BOTH_SIDES_WIPED", "INSIDE_RANGE"}:
        print("    [X] FAIL: invalid state")
        ok = False
    else:
        print("    [OK] pass")

    # ---- [6] 4-Step Continuation Checklist ----
    print(f"\n[6] 4-Step Continuation Checklist (structural)...")
    p12 = {"low": spot - 100, "high": spot + 100}
    ny1 = {"high": spot + 50, "low": spot - 50}
    checklist = build_continuation_checklist(spot, p12, {}, ny1)
    print("\n".join("    " + c for c in checklist))
    if len(checklist) < 5:
        print("    [X] FAIL: checklist incomplete")
        ok = False
    else:
        print("    [OK] pass")

    # ---- [7] Orchestrator + persistence ----
    print(f"\n[7] Orchestrator + Derived Persistence...")
    gap = compute_all_gap_fillers(ticker, t_dt, df_1m, spot, p12, persist=True)
    print(f"    aspects computed: {list(gap.keys())}")
    expected = {"flag_flip", "tf_streaks", "out_of_stat", "magic_hour"}
    if set(gap.keys()) != expected:
        print("    [X] FAIL: aspect set mismatch")
        ok = False
    else:
        print("    [OK] aspects complete")

    for aspect in ["flag_flip", "tf_streak", "out_of_stat", "magic_hour"]:
        p = GAP_DERIVED_DIR / f"{ticker}_{aspect}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            print(f"    derived: {p.name} | {len(df)} rows | latest {df['date'].iloc[-1]}")
        else:
            print(f"    [X] FAIL: missing derived file {p.name}")
            ok = False

    print(f"\nFormatted gap-filler block:")
    print("-" * 60)
    print(format_gap_fillers_markdown(ff, st, dro, oos, mg))
    print("-" * 60)
    return ok


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate Mickey gap-filler engines")
    parser.add_argument("--tickers", nargs="*", default=["NQ1", "ES1"])
    parser.add_argument("--date", default=None, help="YYYY-MM-DD")
    args = parser.parse_args()

    t_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    results = {}
    for t in args.tickers:
        try:
            results[t] = validate_gap_fillers_for_ticker(t, t_date)
        except Exception as e:
            log.exception("validation error for %s", t)
            results[t] = False

    print(f"\n{'=' * 60}")
    for t, passed in results.items():
        print(f"   {t}: {'PASS' if passed else 'FAIL'}")
    if all(results.values()):
        print("\n   ALL GAP FILLER VALIDATION TESTS PASSED!")
    else:
        print("\n   GAP FILLER VALIDATION FAILED FOR SOME TICKERS.")
        sys.exit(1)


if __name__ == "__main__":
    main()