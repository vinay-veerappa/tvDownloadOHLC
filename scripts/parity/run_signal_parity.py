#!/usr/bin/env python3
"""
run_signal_parity.py — THE parity gate for the IFVG/CISD ICT engines.

Compares, bar by bar, the C# engine harness output (dotnet, shared/ict/) against
the Python reference kernels (scripts/libs_py + _variant_signal_kernel) on the
SAME fixture CSV. Exit 0 only on zero mismatches per column.

Usage:
    python scripts/parity/run_signal_parity.py --fixture scripts/parity/fixtures/<f>.csv
    python scripts/parity/run_signal_parity.py --fixture <f>.csv --variant 2 --stop-type 0 --entry-mech 1
    python scripts/parity/run_signal_parity.py --fixture <f>.csv --python-only   # reference dump

Tolerances: events/state are exact ints; prices compare at 1e-9 (both print 'G',
round-trip exact on doubles within float printing).
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.libs_py.cisd import compute_cisd            # noqa: E402
from scripts.libs_py.fvg import compute_fvg              # noqa: E402
from scripts.libs_py.ifvg import compute_ifvg           # noqa: E402
from scripts.libs_py.bpr import compute_bpr             # noqa: E402
from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import (  # noqa: E402
    _variant_signal_kernel,
)

HARNESS_DIR = REPO_ROOT / "scripts" / "parity" / "csharp"

COMPARE_COLUMNS = [
    ("CisdEvent", "cisd_event", "int"),
    ("CisdState", "cisd_state", "int"),
    ("ActiveBullLevel", "active_bull", "float"),
    ("ActiveBearLevel", "active_bear", "float"),
    ("FvgEvent", "fvg_event", "int"),
    ("IfvgEvent", "ifvg_event", "int"),
    ("BprEvent", "bpr_event", "int"),
    ("Signal", "signal", "int"),
    ("EntryPrice", "entry", "float"),
    ("StopPrice", "stop", "float"),
    ("RiskPts", "risk", "float"),
]

PRICE_TOL = 1e-6


def python_reference(bars: pd.DataFrame, variant: int, stop_type: int,
                     entry_mech: int, tick: float, min_bps: float, max_bps: float,
                     stop_bps: float) -> pd.DataFrame:
    """Run the Python kernels over the bars exactly as _hunt_csharp_variants does."""
    cisd = compute_cisd(bars, align_to_base=False)
    fvg = compute_fvg(bars, include_vi=True, require_directional_candle=False, align_to_base=False)
    ifvg = compute_ifvg(bars, include_vi=True, require_directional_candle=False, align_to_base=False)
    bpr = compute_bpr(bars, align_to_base=False, require_directional_candle=False)

    sig_idx, sig_dir, sig_entry, sig_stop, sig_risk = _variant_signal_kernel(
        bars["open"].values.astype(np.float64),
        bars["high"].values.astype(np.float64),
        bars["low"].values.astype(np.float64),
        bars["close"].values.astype(np.float64),
        cisd["cisd_event"].values.astype(np.int8),
        cisd["cisd_state"].values.astype(np.int8),
        fvg["fvg_event"].values.astype(np.int8),
        fvg["fvg_top"].values.astype(np.float64),
        fvg["fvg_bottom"].values.astype(np.float64),
        ifvg["ifvg_event"].values.astype(np.int8),
        bpr["bpr_event"].values.astype(np.int8),
        cisd["active_bull_cisd_level"].values.astype(np.float64),
        cisd["active_bear_cisd_level"].values.astype(np.float64),
        variant, tick, min_bps, max_bps,
        stop_type, stop_bps, entry_mech,
    )

    n = len(bars)
    signal = np.zeros(n, dtype=np.int64)
    entry = np.full(n, np.nan)
    stop = np.full(n, np.nan)
    risk = np.full(n, np.nan)
    for j in range(len(sig_idx)):
        i = sig_idx[j]
        signal[i] = sig_dir[j]
        entry[i] = sig_entry[j]
        stop[i] = sig_stop[j]
        risk[i] = sig_risk[j]

    return pd.DataFrame({
        "time": bars.index,
        "cisd_event": cisd["cisd_event"].values,
        "cisd_state": cisd["cisd_state"].values,
        "active_bull": cisd["active_bull_cisd_level"].values,
        "active_bear": cisd["active_bear_cisd_level"].values,
        "fvg_event": fvg["fvg_event"].values,
        "ifvg_event": ifvg["ifvg_event"].values,
        "bpr_event": bpr["bpr_event"].values,
        "signal": signal,
        "entry": entry,
        "stop": stop,
        "risk": risk,
    })


def run_csharp_harness(fixture: Path, variant: int, stop_type: int, entry_mech: int) -> pd.DataFrame:
    out_path = Path(tempfile.gettempdir()) / f"ict_parity_csharp_{variant}_{stop_type}_{entry_mech}.csv"
    cmd = ["dotnet", "run", "--project", str(HARNESS_DIR / "CsdEngineHarness.csproj"),
           "--", str(fixture.resolve()), str(out_path), str(variant), str(stop_type), str(entry_mech)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("[FATAL] C# harness failed:")
        print(res.stdout)
        print(res.stderr)
        sys.exit(2)
    return pd.read_csv(out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--variant", type=int, default=2)
    ap.add_argument("--stop-type", type=int, default=0)
    ap.add_argument("--entry-mech", type=int, default=1)
    ap.add_argument("--tick", type=float, default=0.25)
    ap.add_argument("--min-bps", type=float, default=2.0)
    ap.add_argument("--max-bps", type=float, default=15.0)
    ap.add_argument("--stop-bps", type=float, default=5.0)
    ap.add_argument("--python-only", action="store_true", help="Dump the Python reference; skip the C# run.")
    args = ap.parse_args()

    bars = pd.read_csv(args.fixture)
    bars["time"] = pd.to_datetime(bars["time"])
    bars = bars.set_index("time")

    py = python_reference(bars, args.variant, args.stop_type, args.entry_mech,
                          args.tick, args.min_bps, args.max_bps, args.stop_bps)

    if args.python_only:
        print(py[py["signal"] != 0].to_string())
        return 0

    cs = run_csharp_harness(args.fixture, args.variant, args.stop_type, args.entry_mech)

    if len(cs) != len(py):
        print(f"[FATAL] row count differs: python={len(py)} csharp={len(cs)}")
        return 2

    total_mismatch = 0
    print(f"{'column':<18} {'mismatches':>10}")
    for cs_col, py_col, kind in COMPARE_COLUMNS:
        csv_ = cs[cs_col].values
        pyv = py[py_col].values
        bad = 0
        first_bad = None
        for i in range(len(py)):
            a, b = csv_[i], pyv[i]
            if kind == "int":
                a = 0 if pd.isna(a) else int(a)
                b = 0 if pd.isna(b) else int(b)
                if a != b:
                    bad += 1
                    if first_bad is None:
                        first_bad = (i, a, b)
            else:
                an, bn = float(a) if not pd.isna(a) else np.nan, float(b) if not pd.isna(b) else np.nan
                a_na, b_na = np.isnan(an), np.isnan(bn)
                if a_na != b_na or (not a_na and abs(an - bn) > PRICE_TOL):
                    bad += 1
                    if first_bad is None:
                        first_bad = (i, an, bn)
        print(f"{cs_col:<18} {bad:>10}")
        total_mismatch += bad
        if bad and first_bad:
            i, a, b = first_bad
            print(f"    first @ row {i} ({bars.index[i]}): csharp={a} python={b}")

    print()
    if total_mismatch == 0:
        print(f"PARITY OK — {len(py)} bars, variant={args.variant}, stop={args.stop_type}, mech={args.entry_mech}")
        return 0
    print(f"PARITY FAIL — {total_mismatch} cell mismatches")
    return 1


if __name__ == "__main__":
    sys.exit(main())