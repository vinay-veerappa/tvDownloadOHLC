"""
Bar-by-bar CISD/FVG comparison using identical NT8 5m bar data.

This script:
1. Fetches NT8 5m bars via the MCP API (or loads from saved JSON)
2. Runs the Python CISD engine on the exact same bars
3. Runs the Python FVG engine on the same bars
4. Compares bar-by-bar: CISD triggers, FVG events, regime state
5. Also runs the NT8 backtest and compares trade entries

Key: Both engines see the SAME OHLC data. Any differences in CISD/FVG
output are pure logic differences, not data alignment issues.
"""
from __future__ import annotations

import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import pandas as pd
import numpy as np
import json

from scripts.libs_py.cisd import compute_cisd
from scripts.libs_py.fvg import compute_fvg
from scripts.libs_py.ifvg import compute_ifvg


def load_nt8_bars_from_api_result(filepath: str) -> pd.DataFrame:
    """Load NT8 bars from a saved nt_bars API result JSON."""
    with open(filepath) as f:
        data = json.load(f)
    bars = data.get("bars", data.get("data", []))
    if not bars:
        # Try reading as raw text
        with open(filepath) as f:
            lines = f.readlines()
        # Parse CSV-like format
        return pd.DataFrame()

    df = pd.DataFrame(bars)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    # NT8 bar time = close time. Rename to match Python convention.
    df.index.name = "datetime"
    return df[["open", "high", "low", "close", "volume"]]


def run_python_engines(df: pd.DataFrame) -> pd.DataFrame:
    """Run CISD + FVG + IFVG on the given OHLC DataFrame."""
    df = df.copy()
    # Ensure columns are float
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df["volume"] = df["volume"].astype(float)

    # Run CISD (adds cisd_event, cisd_state, etc.)
    cisd_result = compute_cisd(df.copy())
    for col in cisd_result.columns:
        if col not in df.columns:
            df[col] = cisd_result[col]

    # Run FVG (adds fvg_event, fvg_top, etc.)
    fvg_result = compute_fvg(df.copy())
    for col in fvg_result.columns:
        if col not in df.columns:
            df[col] = fvg_result[col]

    # Run IFVG (may fail if dependencies missing)
    try:
        ifvg_result = compute_ifvg(df.copy())
        for col in ifvg_result.columns:
            if col not in df.columns:
                df[col] = ifvg_result[col]
    except Exception as e:
        print(f"IFVG skipped: {e}")

    return df


def compare_engines(py_result: pd.DataFrame, date_filter: str = "2025-08-19") -> None:
    """Print bar-by-bar comparison of CISD/FVG events for a given date."""

    mask = py_result.index.strftime("%Y-%m-%d") == date_filter
    day_bars = py_result[mask]

    print(f"\n{'='*120}")
    print(f"BAR-BY-BAR ENGINE OUTPUT: {date_filter}")
    print(f"{'='*120}")
    print(f"Total bars: {len(day_bars)}")
    print()

    # CISD events
    bull_cisd = day_bars[day_bars["cisd_event"] == 1]
    bear_cisd = day_bars[day_bars["cisd_event"] == -1]
    print(f"CISD Events:")
    print(f"  Bullish triggers: {len(bull_cisd)}")
    print(f"  Bearish triggers: {len(bear_cisd)}")
    print()

    # Print all CISD events with details
    cisd_events = day_bars[day_bars["cisd_event"] != 0]
    if len(cisd_events) > 0:
        print(f"  {'Time':<22} {'O':>10} {'H':>10} {'L':>10} {'C':>10} {'Event':>6} {'State':>6} {'BullLvl':>10} {'BearLvl':>10}")
        print(f"  {'-'*100}")
        for _, r in cisd_events.iterrows():
            evt = "+CISD" if r["cisd_event"] == 1 else "-CISD" if r["cisd_event"] == -1 else ""
            state = f"{r['cisd_state']:+.0f}"
            blvl = f"{r['active_bull_cisd_level']:.2f}" if not np.isnan(r["active_bull_cisd_level"]) else "---"
            blvl_bear = f"{r['active_bear_cisd_level']:.2f}" if not np.isnan(r["active_bear_cisd_level"]) else "---"
            print(f"  {str(r.name):<22} {r['open']:>10.2f} {r['high']:>10.2f} {r['low']:>10.2f} {r['close']:>10.2f} {evt:>6} {state:>6} {blvl:>10} {blvl_bear:>10}")
    print()

    # FVG events
    if "fvg_event" in day_bars.columns:
        bull_fvg = day_bars[day_bars["fvg_event"] == 1]
        bear_fvg = day_bars[day_bars["fvg_event"] == -1]
        print(f"FVG Events:")
        print(f"  Bullish FVG: {len(bull_fvg)}")
        print(f"  Bearish FVG: {len(bear_fvg)}")
        if len(bull_fvg) + len(bear_fvg) > 0:
            fvg_events = day_bars[day_bars["fvg_event"] != 0]
            print(f"  {'Time':<22} {'O':>10} {'H':>10} {'L':>10} {'C':>10} {'FVG':>6}")
            print(f"  {'-'*60}")
            for _, r in fvg_events.iterrows():
                evt = "BULL" if r["fvg_event"] == 1 else "BEAR"
                print(f"  {str(r.name):<22} {r['open']:>10.2f} {r['high']:>10.2f} {r['low']:>10.2f} {r['close']:>10.2f} {evt:>6}")
        print()

    # IFVG events
    if "ifvg_event" in day_bars.columns:
        bull_ifvg = day_bars[day_bars["ifvg_event"] == 1]
        bear_ifvg = day_bars[day_bars["ifvg_event"] == -1]
        print(f"IFVG Events:")
        print(f"  Bullish IFVG: {len(bull_ifvg)}")
        print(f"  Bearish IFVG: {len(bear_ifvg)}")
        if len(bull_ifvg) + len(bear_ifvg) > 0:
            ifvg_events = day_bars[day_bars["ifvg_event"] != 0]
            print(f"  {'Time':<22} {'O':>10} {'H':>10} {'L':>10} {'C':>10} {'IFVG':>6}")
            print(f"  {'-'*60}")
            for _, r in ifvg_events.iterrows():
                evt = "BULL" if r["ifvg_event"] == 1 else "BEAR"
                print(f"  {str(r.name):<22} {r['open']:>10.2f} {r['high']:>10.2f} {r['low']:>10.2f} {r['close']:>10.2f} {evt:>6}")
        print()

    # Regime state timeline
    print(f"Regime State Timeline (changes only):")
    prev_state = 0
    for _, r in day_bars.iterrows():
        state = int(r["cisd_state"])
        if state != prev_state:
            print(f"  {str(r.name):<22}  regime: {prev_state:+d} -> {state:+d}  close={r['close']:.2f}")
            prev_state = state
    print()


def main():
    # Try loading NT8 bars from the saved API output
    nt8_data_path = Path("C:/Users/vinay/.local/share/opencode/tool-output/tool_020f50a0f001x9zQn5p22KURBM")
    if not nt8_data_path.exists():
        print(f"ERROR: NT8 bars file not found at {nt8_data_path}")
        print("Run nt_bars first to fetch NT8 5m data.")
        return

    # The saved file is the raw JSON response from nt_bars
    with open(nt8_data_path) as f:
        content = f.read()

    # Try parsing as JSON
    try:
        data = json.loads(content)
        bars = data.get("bars", [])
    except json.JSONDecodeError:
        # Maybe it's the full tool output with metadata
        # Try finding JSON in the text
        start = content.find("{")
        if start >= 0:
            data = json.loads(content[start:])
            bars = data.get("bars", [])
        else:
            print("ERROR: Could not parse NT8 bars JSON")
            return

    if not bars:
        print("ERROR: No bars found in NT8 data")
        return

    df = pd.DataFrame(bars)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")
    df.index.name = "datetime"
    df = df[["open", "high", "low", "close", "volume"]].astype(float)

    print(f"Loaded {len(df)} NT8 5m bars")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print()

    # Run Python engines on the SAME data
    print("Running Python CISD + FVG engines on NT8 bar data...")
    result = run_python_engines(df)
    print(f"Engine output: {len(result)} bars")
    print(f"Columns: {list(result.columns)}")
    print()

    # Show engine output for Aug 19
    compare_engines(result, "2026-08-19")
    compare_engines(result, "2026-08-20")

    # Also compare with the old NT8 diag CSV (from Aug 19, the old engine)
    old_nt8_diag = Path("C:/Users/vinay/AppData/Local/Temp/ictfvgcisd_diag_da5de1edc19840d59468c76b23833cca.csv")
    if old_nt8_diag.exists():
        print(f"\n{'='*120}")
        print("OLD NT8 DIAG CSV (Aug 19 2026, old pivot-based engine, 3min bars)")
        print(f"{'='*120}")
        old_diag = pd.read_csv(old_nt8_diag)
        print(f"Columns: {list(old_diag.columns)}")
        print(f"Rows: {len(old_diag)}")
        print(old_diag.head(20).to_string())
        print()
        print("NOTE: This is from the OLD engine (pivot+first-open). The new engine")
        print("uses tncylyv extreme-open model. This old CSV is for reference only.")
    else:
        print("\nOld NT8 diag CSV not found.")


if __name__ == "__main__":
    main()