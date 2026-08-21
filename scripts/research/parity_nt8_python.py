"""
Definitive NT8 vs Python parity test.

The NT8 strategy (ICTFVGCISDBot) writes a diagnostic CSV on EVERY bar during
Strategy Analyzer backtests. That CSV contains the full state machine:
  - OHLC (raw contract, e.g. NQ SEP26)
  - CISD: Vibes, BagholderEntry, PainThreshold, BullCisdTrigger, BearCisdTrigger
  - FVG:  IsBullFvg, IsBearFvg
  - IFVG: IsBullIfvg, IsBearIfvg
  - BPR:  IsBullBpr, IsBearBpr
  - Leg:  BullFvgCount, BearFvgCount, PriorBullFvgCount, PriorBearFvgCount,
          LegCisdLevel, LegCrossedLevel, LegOriginLow, LegOriginHigh
  - Signal: SignalLong, SignalShort, EntryPrice, StopPrice, RiskPts

This tool runs the Python engines on the SAME OHLC and compares bar-by-bar.
This eliminates:
  - continuous (NQ1) vs raw (NQ SEP26) contract price differences
  - timezone differences (uses the CSV's own timestamps)
  - any data alignment issues

Usage:
    python -m scripts.research.parity_nt8_python --csv <path-to-diag-csv> [--variant 0|1|2]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import numpy as np
import pandas as pd

from scripts.libs_py.cisd import compute_cisd
from scripts.libs_py.fvg import compute_fvg
from scripts.libs_py.ifvg import compute_ifvg
from scripts.libs_py.bpr import compute_bpr


def load_diag_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["BarCloseTime"] = pd.to_datetime(df["BarCloseTime"])
    df = df.set_index("BarCloseTime")
    df = df.sort_index()
    return df


def build_ohlc(diag: pd.DataFrame) -> pd.DataFrame:
    ohlc = diag[["Open", "High", "Low", "Close"]].copy()
    ohlc.columns = ["open", "high", "low", "close"]
    ohlc["volume"] = 0.0
    return ohlc


def run_python_engines(ohlc: pd.DataFrame) -> pd.DataFrame:
    out = ohlc.copy()
    cisd = compute_cisd(ohlc.copy())
    fvg = compute_fvg(ohlc.copy(), require_directional_candle=False)
    ifvg = compute_ifvg(ohlc.copy(), require_directional_candle=False)
    bpr = compute_bpr(ohlc.copy(), align_to_base=False, require_directional_candle=False)

    out["py_cisd_event"] = cisd["cisd_event"].values
    out["py_cisd_state"] = cisd["cisd_state"].values
    out["py_bull_cisd_lvl"] = cisd["active_bull_cisd_level"].values
    out["py_bear_cisd_lvl"] = cisd["active_bear_cisd_level"].values
    out["py_fvg_event"] = fvg["fvg_event"].values
    out["py_fvg_top"] = fvg["fvg_top"].values
    out["py_fvg_bottom"] = fvg["fvg_bottom"].values
    out["py_ifvg_event"] = ifvg["ifvg_event"].values
    out["py_bpr_event"] = bpr["bpr_event"].values
    return out


def compare_series(name, nt8, py, diag, limit=10, warmup=30):
    """Compare two integer event series; return mismatch summary."""
    nt8 = np.asarray(nt8, dtype=np.int64)
    py = np.asarray(py, dtype=np.int64)
    n = len(nt8)
    mismatches = np.where(nt8 != py)[0]
    # Exclude warmup bars (NT8 starts warm with 20 bars history + CISD init)
    mismatches = mismatches[mismatches >= warmup]
    print(f"\n[{name}]")
    print(f"  NT8 events:  {(nt8 != 0).sum()}")
    print(f"  PY  events:  {(py != 0).sum()}")
    print(f"  Mismatches:  {len(mismatches)} / {n} bars (warmup {warmup} skipped)")
    if len(mismatches) == 0:
        print("  ✓ PERFECT MATCH")
        return
    # Show first N mismatches with context
    shown = 0
    for idx in mismatches:
        if shown >= limit:
            break
        ts = diag.index[idx]
        row = diag.iloc[idx]
        print(f"    {ts}  nt8={nt8[idx]:+d}  py={py[idx]:+d}  "
              f"O={row['Open']:.2f} H={row['High']:.2f} L={row['Low']:.2f} C={row['Close']:.2f} "
              f"vibes={row['Vibes']:+d}")
        shown += 1
    if len(mismatches) > limit:
        print(f"    ... and {len(mismatches) - limit} more")


def compare_float_series(name, nt8, py, diag, tol=0.25, limit=10, warmup=30):
    """Compare two float series (levels) with tolerance; NaN == NaN."""
    nt8 = np.asarray(nt8, dtype=np.float64)
    py = np.asarray(py, dtype=np.float64)
    n = len(nt8)
    both_nan = np.isnan(nt8) & np.isnan(py)
    both_val = ~np.isnan(nt8) & ~np.isnan(py) & (np.abs(nt8 - py) <= tol)
    agree = both_nan | both_val
    mismatches = np.where(~agree)[0]
    mismatches = mismatches[mismatches >= warmup]
    print(f"\n[{name}]")
    print(f"  NT8 non-nan: {(~np.isnan(nt8)).sum()}")
    print(f"  PY  non-nan: {(~np.isnan(py)).sum()}")
    print(f"  Mismatches:  {len(mismatches)} / {n} bars (tol={tol}, warmup {warmup} skipped)")
    if len(mismatches) == 0:
        print("  ✓ PERFECT MATCH")
        return
    shown = 0
    for idx in mismatches:
        if shown >= limit:
            break
        ts = diag.index[idx]
        row = diag.iloc[idx]
        print(f"    {ts}  nt8={nt8[idx]:.2f}  py={py[idx]:.2f}  "
              f"C={row['Close']:.2f}  vibes={row['Vibes']:+d}")
        shown += 1
    if len(mismatches) > limit:
        print(f"    ... and {len(mismatches) - limit} more")


def first_divergence(diag, py):
    """Find the first bar where CISD state diverges, and show the lead-up."""
    nt8_state = diag["Vibes"].values.astype(np.int64)
    py_state = py["py_cisd_state"].values.astype(np.int64)
    mismatches = np.where(nt8_state != py_state)[0]
    if len(mismatches) == 0:
        print("\nNo CISD state divergence found.")
        return
    first = mismatches[0]
    print(f"\n=== FIRST CISD STATE DIVERGENCE at bar {first} ({diag.index[first]}) ===")
    start = max(0, first - 8)
    end = min(len(diag), first + 3)
    cols = ["Open", "High", "Low", "Close", "Vibes", "BagholderEntry", "PainThreshold",
            "BullCisdTrigger", "BearCisdTrigger"]
    sub = diag.iloc[start:end][cols].copy()
    sub["py_state"] = py_state[start:end]
    sub["py_bull_lvl"] = py["py_bull_cisd_lvl"].values[start:end]
    sub["py_bear_lvl"] = py["py_bear_cisd_lvl"].values[start:end]
    print(sub.to_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to NT8 diag CSV")
    parser.add_argument("--variant", type=int, default=None,
                        help="Variant to compare signals for (0/1/2). Omit to skip signal compare.")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    diag = load_diag_csv(args.csv)
    print(f"Loaded {len(diag)} bars: {diag.index[0]} -> {diag.index[-1]}")
    print(f"Variant column value: {diag['Variant'].iloc[0] if 'Variant' in diag.columns else 'N/A'}")

    ohlc = build_ohlc(diag)
    py = run_python_engines(ohlc)

    # ── CISD event ──
    nt8_cisd_event = (diag["BullCisdTrigger"].fillna(0).astype(int)
                      - diag["BearCisdTrigger"].fillna(0).astype(int)).values
    compare_series("CISD EVENT (BullCisdTrigger - BearCisdTrigger vs cisd_event)",
                   nt8_cisd_event, py["py_cisd_event"].values, diag, args.limit)

    # ── CISD state ──
    compare_series("CISD STATE (Vibes vs cisd_state)",
                   diag["Vibes"].values, py["py_cisd_state"].values, diag, args.limit)

    # ── CISD level (bagholder entry) ──
    # NT8 BagholderEntry is the active level for the current regime.
    # Python: bull level when state==1, bear level when state==-1.
    nt8_bag = diag["BagholderEntry"].values.astype(float)
    py_level = np.where(py["py_cisd_state"].values == 1,
                        py["py_bull_cisd_lvl"].values,
                        py["py_bear_cisd_lvl"].values)
    compare_float_series("CISD LEVEL (BagholderEntry vs active level)",
                         nt8_bag, py_level, diag, tol=0.25, limit=args.limit)

    # ── FVG ──
    nt8_fvg = (diag["IsBullFvg"].fillna(0).astype(int)
               - diag["IsBearFvg"].fillna(0).astype(int)).values
    compare_series("FVG (IsBullFvg - IsBearFvg vs fvg_event)",
                   nt8_fvg, py["py_fvg_event"].values, diag, args.limit)

    # ── IFVG ──
    nt8_ifvg = (diag["IsBullIfvg"].fillna(0).astype(int)
                - diag["IsBearIfvg"].fillna(0).astype(int)).values
    compare_series("IFVG (IsBullIfvg - IsBearIfvg vs ifvg_event)",
                   nt8_ifvg, py["py_ifvg_event"].values, diag, args.limit)

    # ── BPR ──
    nt8_bpr = (diag["IsBullBpr"].fillna(0).astype(int)
               - diag["IsBearBpr"].fillna(0).astype(int)).values
    compare_series("BPR (IsBullBpr - IsBearBpr vs bpr_event)",
                   nt8_bpr, py["py_bpr_event"].values, diag, args.limit)

    # ── First divergence ──
    first_divergence(diag, py)

    # ── Signal-level parity (Variant 1/2) ──
    if args.variant in (1, 2):
        from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import _variant_signal_kernel
        o = ohlc["open"].values.astype(np.float64)
        h = ohlc["high"].values.astype(np.float64)
        l = ohlc["low"].values.astype(np.float64)
        c = ohlc["close"].values.astype(np.float64)
        cisd_event = py["py_cisd_event"].values.astype(np.int8)
        cisd_state = py["py_cisd_state"].values.astype(np.int8)
        fvg_event = py["py_fvg_event"].values.astype(np.int8)
        fvg_top = py["py_fvg_top"].values.astype(np.float64)
        fvg_bottom = py["py_fvg_bottom"].values.astype(np.float64)
        ifvg_event = py["py_ifvg_event"].values.astype(np.int8)
        bpr_event = py["py_bpr_event"].values.astype(np.int8)
        bull_lvl = py["py_bull_cisd_lvl"].values.astype(np.float64)
        bear_lvl = py["py_bear_cisd_lvl"].values.astype(np.float64)

        sig_idx, sig_dir, sig_entry, sig_stop, sig_risk = _variant_signal_kernel(
            o, h, l, c, cisd_event, cisd_state, fvg_event, fvg_top, fvg_bottom,
            ifvg_event, bpr_event, bull_lvl, bear_lvl,
            args.variant, 0.25, 2.0, 15.0,
        )

        py_signal = np.zeros(len(diag), dtype=np.int8)
        for j in range(len(sig_idx)):
            py_signal[sig_idx[j]] = sig_dir[j]

        nt8_signal = (diag["SignalLong"].fillna(0).astype(int)
                      - diag["SignalShort"].fillna(0).astype(int)).values
        compare_series(f"SIGNAL (Variant {args.variant})",
                       nt8_signal, py_signal, diag, args.limit, warmup=30)


if __name__ == "__main__":
    main()
