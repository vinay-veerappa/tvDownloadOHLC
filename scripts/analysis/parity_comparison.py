"""
Parity Comparison: Python vs NinjaTrader 8 vs TradingView

Compares the diagnostic CSV output from NT8's IBFadeBot with the Python
benchmark_range_regime_fvg.py results to identify signal divergence.

NT8 CSV columns (from IBFadeBot.WriteDiagRow):
  BarTime, BarIdx, Open, High, Low, Close, RangeHigh, RangeLow, RangeRange,
  RangeMid, RangeComplete, DailyAtr, IbCompressed, InMiddayPM, SweepDir,
  SweepExtreme, Fvg5mHigh, Fvg5mLow, Fvg5mClose, Prev5mCount, Prev5mH0,
  Prev5mL0, Prev5mH1, Prev5mL1, CanEnterLong, CanEnterShort, FvgRequired,
  MinFvgSize, TimeNum

Python CSV columns (from range_strategy_comparison):
  strategy_name, symbol, session_name, date, direction, entry_time, entry_price,
  stop_loss, tp1_price, tp2_price, risk_points, t1_hit, t2_hit, stopped_out,
  exit_time, leg1_pnl, leg2_pnl, total_pnl_points, total_pnl_dollars, r_multiple

Usage:
    python -m scripts.analysis.parity_comparison \
        --nt8-csv "%TEMP%/ibfade_sweep_diag_xxx.csv" \
        --python-csv data/derived/range_strategy_comparison_ES_2021_2026.csv \
        --symbol ES
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def load_nt8_csv(path: str) -> pd.DataFrame:
    """Load NT8 diagnostic CSV and parse timestamps."""
    df = pd.read_csv(path)
    df["BarTime"] = pd.to_datetime(df["BarTime"])
    df = df.sort_values("BarTime").reset_index(drop=True)
    return df


def load_python_csv(path: str, symbol: str) -> pd.DataFrame:
    """Load Python strategy comparison CSV, filter to IB_Sweep_Fade."""
    df = pd.read_csv(path)
    if "strategy_name" in df.columns:
        df = df[df["strategy_name"] == "IB_Sweep_Fade"]
    if "symbol" in df.columns:
        df = df[df["symbol"] == symbol]
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.sort_values("entry_time").reset_index(drop=True)


def extract_nt8_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Extract trade signals from NT8 diagnostic CSV.

    A signal is armed when SweepDir changes from 0 to non-zero.
    A fill occurs when the price touches the entry level.
    """
    signals = []
    current_sweep = 0
    current_extreme = 0.0
    sweep_armed_time = None
    sweep_armed_dir = 0
    entry_price_armed = 0.0
    ib_high = 0.0
    ib_low = 0.0
    ib_mid = 0.0

    for _, row in df.iterrows():
        # Track IB levels
        if row["RangeComplete"] == 1:
            ib_high = row["RangeHigh"]
            ib_low = row["RangeLow"]
            ib_mid = row["RangeMid"]

        # Detect sweep arming (SweepDir transitions from 0 to non-zero)
        new_sweep = int(row["SweepDir"])
        if new_sweep != 0 and current_sweep == 0:
            sweep_armed_time = row["BarTime"]
            sweep_armed_dir = new_sweep
            current_extreme = row["SweepExtreme"]

            # Estimate entry price from the 5m bar data
            if new_sweep == 1:  # Short — entry = b2 high
                entry_price_armed = row["Prev5mH1"] if row["Prev5mCount"] >= 2 else row["Fvg5mHigh"]
            else:  # Long — entry = b2 low
                entry_price_armed = row["Prev5mL1"] if row["Prev5mCount"] >= 2 else row["Fvg5mLow"]

        # Detect fill (price touches entry)
        if current_sweep != 0 and sweep_armed_time is not None:
            filled = False
            if sweep_armed_dir == 1 and row["High"] >= entry_price_armed:
                filled = True
            elif sweep_armed_dir == -1 and row["Low"] <= entry_price_armed:
                filled = True

            if filled:
                stop_price = (current_extreme + 2 * 0.25) if sweep_armed_dir == 1 else (current_extreme - 2 * 0.25)
                tp1 = ib_mid
                tp2 = ib_low if sweep_armed_dir == 1 else ib_high

                signals.append({
                    "date": sweep_armed_time.date(),
                    "entry_time": sweep_armed_time,
                    "fill_time": row["BarTime"],
                    "direction": "SHORT" if sweep_armed_dir == 1 else "LONG",
                    "entry_price": entry_price_armed,
                    "stop_loss": stop_price,
                    "tp1_price": tp1,
                    "tp2_price": tp2,
                    "ib_high": ib_high,
                    "ib_low": ib_low,
                    "sweep_extreme": current_extreme,
                })
                # Reset sweep state
                sweep_armed_time = None
                sweep_armed_dir = 0
                entry_price_armed = 0.0

        current_sweep = new_sweep

    return pd.DataFrame(signals)


def compare_signals(nt8_signals: pd.DataFrame, py_signals: pd.DataFrame) -> Dict:
    """Compare signal sets by date and direction."""
    if nt8_signals.empty or py_signals.empty:
        return {
            "nt8_count": len(nt8_signals),
            "python_count": len(py_signals),
            "matched": 0,
            "nt8_only": len(nt8_signals),
            "python_only": len(py_signals),
            "matches": [],
            "divergences": [],
        }

    # Match by date + direction
    nt8_signals = nt8_signals.copy()
    py_signals = py_signals.copy()
    nt8_signals["date_str"] = nt8_signals["date"].astype(str)
    py_signals["date_str"] = py_signals["date"].astype(str)

    matches = []
    nt8_only = []
    py_only = []

    for _, py_row in py_signals.iterrows():
        match = nt8_signals[
            (nt8_signals["date_str"] == py_row["date_str"]) &
            (nt8_signals["direction"] == py_row["direction"])
        ]
        if len(match) > 0:
            nt8_match = match.iloc[0]
            matches.append({
                "date": py_row["date_str"],
                "direction": py_row["direction"],
                "py_entry": py_row["entry_price"],
                "nt8_entry": nt8_match["entry_price"],
                "entry_diff": abs(py_row["entry_price"] - nt8_match["entry_price"]),
                "py_stop": py_row["stop_loss"],
                "nt8_stop": nt8_match["stop_loss"],
                "stop_diff": abs(py_row["stop_loss"] - nt8_match["stop_loss"]),
            })
        else:
            py_only.append(py_row["date_str"])

    for _, nt8_row in nt8_signals.iterrows():
        match = py_signals[
            (py_signals["date_str"] == nt8_row["date_str"]) &
            (py_signals["direction"] == nt8_row["direction"])
        ]
        if len(match) == 0:
            nt8_only.append(nt8_row["date_str"])

    return {
        "nt8_count": len(nt8_signals),
        "python_count": len(py_signals),
        "matched": len(matches),
        "nt8_only": len(nt8_only),
        "python_only": len(py_only),
        "matches": matches,
        "nt8_only_dates": nt8_only,
        "python_only_dates": py_only,
    }


def analyze_divergence(matches: List[Dict]) -> Dict:
    """Analyze entry/stop price divergences between NT8 and Python."""
    if not matches:
        return {"avg_entry_diff": 0, "avg_stop_diff": 0, "max_entry_diff": 0, "max_stop_diff": 0}

    entry_diffs = [m["entry_diff"] for m in matches]
    stop_diffs = [m["stop_diff"] for m in matches]

    return {
        "avg_entry_diff": np.mean(entry_diffs),
        "avg_stop_diff": np.mean(stop_diffs),
        "max_entry_diff": np.max(entry_diffs),
        "max_stop_diff": np.max(stop_diffs),
        "entry_diff_pct": np.percentile(entry_diffs, [50, 75, 90, 95, 99]).tolist(),
        "stop_diff_pct": np.percentile(stop_diffs, [50, 75, 90, 95, 99]).tolist(),
    }


def main():
    parser = argparse.ArgumentParser(description="Python vs NT8 Parity Comparison")
    parser.add_argument("--nt8-csv", type=str, required=True, help="Path to NT8 diagnostic CSV")
    parser.add_argument("--python-csv", type=str, required=True, help="Path to Python strategy comparison CSV")
    parser.add_argument("--symbol", type=str, default="ES", help="Symbol to compare")
    args = parser.parse_args()

    print("=" * 90)
    print(f"PARITY COMPARISON: {args.symbol}")
    print(f"NT8 CSV:   {args.nt8_csv}")
    print(f"Python CSV: {args.python_csv}")
    print("=" * 90)

    # Load data
    nt8_df = load_nt8_csv(args.nt8_csv)
    py_df = load_python_csv(args.python_csv, args.symbol)

    print(f"\nNT8 diagnostic rows: {len(nt8_df)}")
    print(f"Python IB_Sweep_Fade trades: {len(py_df)}")

    # Extract NT8 signals from diagnostic data
    nt8_signals = extract_nt8_signals(nt8_df)
    print(f"NT8 extracted signals: {len(nt8_signals)}")

    if not nt8_signals.empty:
        print(f"\nNT8 signal dates (first 10):")
        for _, s in nt8_signals.head(10).iterrows():
            print(f"  {s['date']} {s['direction']:5s} entry={s['entry_price']:.2f} stop={s['stop_loss']:.2f}")

    if not py_df.empty:
        print(f"\nPython trade dates (first 10):")
        for _, s in py_df.head(10).iterrows():
            print(f"  {s['date']} {s['direction']:5s} entry={s['entry_price']:.2f} stop={s['stop_loss']:.2f}")

    # Compare
    result = compare_signals(nt8_signals, py_df)

    print(f"\n{'=' * 90}")
    print("SIGNAL MATCH SUMMARY")
    print(f"{'=' * 90}")
    print(f"  NT8 signals:     {result['nt8_count']}")
    print(f"  Python signals:  {result['python_count']}")
    print(f"  Matched:         {result['matched']}")
    print(f"  NT8 only:        {result['nt8_only']}")
    print(f"  Python only:     {result['python_only']}")

    if result["matched"] > 0:
        div = analyze_divergence(result["matches"])
        print(f"\n{'=' * 90}")
        print("PRICE DIVERGENCE ANALYSIS (matched trades)")
        print(f"{'=' * 90}")
        print(f"  Avg entry price diff: {div['avg_entry_diff']:.4f} pts")
        print(f"  Avg stop price diff:  {div['avg_stop_diff']:.4f} pts")
        print(f"  Max entry price diff: {div['max_entry_diff']:.4f} pts")
        print(f"  Max stop price diff:  {div['max_stop_diff']:.4f} pts")
        print(f"\n  Entry diff percentiles (50/75/90/95/99):")
        for i, p in enumerate([50, 75, 90, 95, 99]):
            print(f"    P{p}: {div['entry_diff_pct'][i]:.4f} pts")

    if result.get("nt8_only_dates"):
        print(f"\n{'=' * 90}")
        print(f"NT8-ONLY SIGNALS ({len(result['nt8_only_dates'])} dates)")
        print(f"{'=' * 90}")
        for d in result["nt8_only_dates"][:20]:
            print(f"  {d}")

    if result.get("python_only_dates"):
        print(f"\n{'=' * 90}")
        print(f"PYTHON-ONLY SIGNALS ({len(result['python_only_dates'])} dates)")
        print(f"{'=' * 90}")
        for d in result["python_only_dates"][:20]:
            print(f"  {d}")

    # Save full comparison
    if result["matches"]:
        match_df = pd.DataFrame(result["matches"])
        out_path = Path(f"data/derived/parity_comparison_{args.symbol}.csv")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        match_df.to_csv(out_path, index=False)
        print(f"\nFull comparison saved to {out_path}")

    print(f"\n{'=' * 90}")
    if result["matched"] == 0 and result["nt8_count"] == 0 and result["python_count"] == 0:
        print("NO SIGNALS DETECTED IN EITHER SOURCE")
    elif result["matched"] == max(result["nt8_count"], result["python_count"]):
        print("✅ PERFECT MATCH — all signals align between NT8 and Python")
    elif result["matched"] > 0:
        match_rate = result["matched"] / max(result["nt8_count"], result["python_count"]) * 100
        print(f"⚠️  PARTIAL MATCH — {match_rate:.1f}% signal alignment. Review divergences above.")
    else:
        print("❌ NO MATCHES — signals do not align. Check data range, timezone, and FVG parameters.")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    main()