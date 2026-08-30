"""E40 + Q2 — D1 replication on NQ/RTY + prop-firm sim E34L vs E35c.

E40 (pre-registered replication of E39b's D1 finding): E34L signal set on NQ1
(parquet source, not NT-MergeBA — the E26 finding of NQ-specificity makes the
*alternative* dataset the honest test) with 30m %B bucket breakdown, plus RTY1.
D1 replicates if bucket D1 PF > baseline PF on both symbols with WR >= 55%.

Q2: PropFirmSimulator (ADR-021, the ONLY permitted evaluator per CLAUDE.md) on
E34L (298 trades) vs E35c BB-exhaustion arm trades re-derived from the E34L
signal stream with band-exhaustion exits.

Usage: .\\.venv\\Scripts\\python.exe scripts/analysis/mm_e40_q2_replication.py
"""
import sys
import warnings

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.mm_e34_battery import run_arm, MMConfig, summarize
from scripts.trading_framework.ml.prop_firm_simulator import FIRM_PROFILES, PropFirmSimulator


def load_parquet_5m(symbol: str, nq_1m=None) -> pd.DataFrame:
    """5m bars from repo parquet (NQ1_5m / RTY1 resampled from 1m), 2025-01-01 →
    latest, tz-naive ET-like (these stores are already in exchange time)."""
    if symbol == "NQ":
        df = pd.read_parquet("data/NQ1_5m.parquet")
        df = df[["open", "high", "low", "close", "volume"]].copy()
    elif symbol == "RTY":
        df = pd.read_parquet("data/RTY1_1m.parquet")
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df = df.resample("5min").agg({"open": "first", "high": "max", "low": "min",
                                      "close": "last", "volume": "sum"}).dropna()
    else:
        raise ValueError(symbol)
    df = df[(df.index.year >= 2025) & (df.index.year <= 2026)]
    return df


def bucket_report(b: pd.DataFrame, tag: str):
    ohlc = b  # df5 with 5m bars
    oh30 = b.resample("30min").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    mid = oh30["close"].rolling(20).mean()
    sd = oh30["close"].rolling(20).std(ddof=1).clip(lower=1e-12)
    pb = (oh30["close"] - (mid - 2 * sd)) / ((mid + 2 * sd) - (mid - 2 * sd)).replace(0, np.nan)
    htf_pb = pb.shift(1).reindex(b.index, method="ffill")
    return htf_pb


def show(tag, sub):
    s3 = summarize(sub) if len(sub) else dict(trades=0, wr=0, pf=0, net=0, dd=0)
    print(f"  {tag:<34} {s3['trades']:>4} tr  WR{s3['wr']:>5.1f}%  PF{s3['pf']:>5.2f}  "
          f"Net${s3['net']:>6.0f}  DD${s3['dd']:>5.0f}")
    return s3


def replicate(symbol: str):
    print(f"\n=== E40 replication: {symbol} (parquet 2025+, E34L long-only) ===")
    df5 = load_parquet_5m(symbol)
    pt = 2.0 if symbol == "NQ" else 1.0
    df1 = df5.resample("1min").agg({"open": "first", "high": "max", "low": "min",
                                    "close": "last", "volume": "sum"}).dropna()
    padf5, padf1 = df5.copy(), df1.copy()
    padf5["_pt"] = pt
    padf1["_pt"] = pt
    setattr(padf5, "_pt_hint", pt)
    base = run_arm(symbol, MMConfig("E34L", "long-only", dir_filter="LONG"),
                   {symbol: padf1}, {symbol: padf5})
    if len(base) == 0:
        print("  0 trades — check data frame")
        return
    b = base.copy()
    # Dollarize ourselves to avoid run_arm's internal pt assumptions
    if "total_pnl_points" in b.columns:
        b["pnl_points"] = b["total_pnl_points"]
    b["pb30_src"] = 0.0

    # index-preserving bucket report on the ORIGINAL df5
    htf_pb = bucket_report(df5.copy(), symbol)
    b["pb30"] = [float(htf_pb.get(t, np.nan)) for t in b["entry_time"]]
    s = summarize(b)
    print(f"  full sample: {s['trades']} tr  WR{s['wr']}  PF{s['pf']}  Net${s['net']}  DD${s['dd']}  (pt ${pt})")
    for lo, hi_q, tag in [(0.0, 0.25, "D1  0.00-0.25"), (0.25, 0.5, "D2  0.25-0.50"),
                          (0.5, 0.75, "D3  0.50-0.75"), (0.75, 1.01, "D4  0.75+")]:
        sub = b[(b["pb30"] >= lo) & (b["pb30"] < hi_q)]
        show(tag, sub)
    return b


def q2_prop_sim():
    print("\n=== Q2: PropFirmSimulator (ADR-021) — E34L vs E35c ===")
    df1, df5 = load_nt("ES")
    e34l = run_arm("ES", MMConfig("E34L", "long-only", dir_filter="LONG"),
                   {"ES": df1}, {"ES": df5})
    print(f"  E34L: {len(e34l)} trades")

    # E35c = same signal stream, BB-exhaustion exit: re-derive from E34L trade
    # CSV? The E35 battery saved exits in its own log; we reconstruct E35c by
    # re-running its exit engine (mm_e35_exit_battery.simulate_exit_variant)
    from scripts.analysis.mm_e35_exit_battery import simulate_exit_variant
    e35c = simulate_exit_variant(e34l, df5, pt_val=5.0, exit_mode="bb_exhaustion")

    for label, tdf, col in [("E34L wide-projection", e34l, "total_pnl_dollars"),
                            ("E35c BB-exhaustion", e35c, None)]:
        if len(tdf) == 0:
            print(f"  {label}: 0 trades")
            continue
        if col is None:
            pnl_series = (tdf["pnl_pts"] if "pnl_pts" in tdf else tdf["total_pnl_points"])
            tdf2 = pd.DataFrame({"exit_time": tdf["exit_time"], "pnl_pct": pnl_series / 50_000.0 * 100.0})
        else:
            tdf2 = pd.DataFrame({"exit_time": tdf["exit_time"],
                                 "pnl_pct": tdf[col] / 50_000.0 * 100.0})
        tdf2 = tdf2.sort_values("exit_time").reset_index(drop=True)
        sim = PropFirmSimulator(account_size=50_000.0, point_value=5.0)
        for key in ["apex_50k", "topstep_50k", "ftmo_50k"]:
            mc = sim.run_monte_carlo(tdf2, FIRM_PROFILES[key], n_simulations=3000)
            det = sim.run_deterministic(tdf2, FIRM_PROFILES[key])
            print(f"  {label:<24} {FIRM_PROFILES[key].name:<14} pass {mc.pass_rate_pct:5.1f}% "
                  f"(grade {mc.grade})  blow {mc.blow_rate_pct:5.1f}%  det-passed {det.passed}")


if __name__ == "__main__":
    replicate("NQ")
    replicate("RTY")
    q2_prop_sim()