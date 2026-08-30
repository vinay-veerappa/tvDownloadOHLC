"""E35 — exit-geometry battery for the trendline-rejection (pullback-done) trigger.

User reframing: keep the trendline break as the WHEN, drop the measured-move target.
Exits: fixed 10/20 bps brackets (user proposal), BB-exhaustion ("move is done"),
and Pack split (10 bps partial + BB-exhaustion runner). Plus the MFE/MAE excursion
curve that decides whether any fixed bracket is viable (AGENTS.md universal bps/std).

Arms (all long-only E34L base PF1.38 unless noted, ES 5m, structural stop):
  MFE      excursion curve — how far does price travel post-rejection? (no trades)
  E35a     fixed +10 bps target
  E35b     fixed +20 bps target
  E35c     BB-exhaustion exit: hold until close prints %B extreme against us
  E35d     Pack: 10 bps partial (50%) + BE lock + BB-exhaustion runner
  E35e     E35c short-only (mirror check — E34S was the weak side)

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/mm_e35_exit_battery.py
"""
from __future__ import annotations

import argparse
import sys
import warnings
from typing import Dict, Optional

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.mm_e34_battery import daily_atr_of, run_arm, summarize
from scripts.libs_py.price_action.trendline_structure import (
    TrendlineStructureParams,
    _atr,
    _di_components,
    find_pivot_highs,
    find_pivot_lows,
)
from scripts.strategies.measured_move.core.measured_move import bb_context_flags

warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# 1. MFE / MAE excursion study over saved E34 signals (no simulation)
# ---------------------------------------------------------------------------
def mfe_mae_study(sig_df: pd.DataFrame, df5: pd.DataFrame, max_hold_bars: int = 96) -> dict:
    """From each long signal entry price, walk forward max_hold 5m bars and record
    MFE/MAE in bps (signed: + favorable for long). Percentile tables + survival."""
    entries = []
    for _, r in sig_df.iterrows():
        t0 = pd.Timestamp(r["entry_time"])
        price = float(r["entry_price"])
        if t0 not in df5.index:
            continue
        i0 = df5.index.get_loc(t0)
        seg = df5.iloc[i0 + 1: i0 + 1 + max_hold_bars]
        if seg.empty:
            continue
        # MFE: highest high vs entry (long), MAE: lowest low vs entry
        mfe_bps = (seg["high"].max() - price) / price * 1e4
        mae_bps = (seg["low"].min() - price) / price * 1e4
        # time to +10/+20 bps
        def _time_to(thresh_bps):
            hit = seg[(seg["high"] - price) / price * 1e4 >= thresh_bps]
            return len(seg.loc[:hit.index[0]]) if len(hit) else np.nan
        entries.append({
            "mfe_bps": mfe_bps,
            "mae_bps": mae_bps,
            "t10": _time_to(10.0),
            "t20": _time_to(20.0),
        })
    return pd.DataFrame(entries)


# ---------------------------------------------------------------------------
# 2. Exit-variant simulation on E34L signals (long-only base, structural stop)
# ---------------------------------------------------------------------------
def simulate_exit_variant(sig_df: pd.DataFrame, df5: pd.DataFrame,
                          pt_val: float = 5.0,
                          exit_mode: str = "bb_exhaustion",
                          tp_bps: float = 10.0,
                          pack_split: bool = False,
                          max_hold_bars: int = 96,
                          be_at: float | None = None) -> pd.DataFrame:
    """Walk each signal forward with the chosen exit. Long-only.

    exit_mode:
      fixed_bps        — TP at entry*(1+tp_bps/1e4), structural stop, EOD flat
      bb_exhaustion    — hold until close >= opposite (upper) band extreme zone
                         (%B >= exhaust_pb) OR structural stop OR EOD/max-hold
      pack             — 50% at +tp_bps (BE lock after), runner until BB exhaustion
    """
    rows = []
    bb_cache: Dict[str, pd.DataFrame] = {}
    for _, r in sig_df.iterrows():
        t0 = pd.Timestamp(r["entry_time"])
        if t0 not in df5.index:
            continue
        day_key = str(t0.date())
        if day_key not in bb_cache:
            # BB context on the whole day frame (18:00 → 16:00) once per day
            day_start = t0.normalize() - pd.Timedelta(hours=6)
            day_end = t0.normalize() + pd.Timedelta(hours=16)
            seg_ctx = df5.loc[day_start:day_end]
            bb_cache[day_key] = bb_context_flags(seg_ctx) if len(seg_ctx) > 50 else seg_ctx.assign(
                bb_pct_b=np.nan, pb_hi_thr=np.nan)
        ctx = bb_cache[day_key]

        i0 = df5.index.get_loc(t0)
        seg = df5.iloc[i0 + 1: i0 + 1 + max_hold_bars]
        if seg.empty:
            continue
        entry = float(df5["open"].iloc[i0 + 1])  # next-open fill like E34
        sl = float(r["stop_loss"])
        risk = entry - sl
        if risk <= 0:
            continue
        tp_fixed = entry * (1 + tp_bps / 1e4)

        if exit_mode in ("bb_exhaustion", "pack") and t0 in ctx.index:
            pb_hi = ctx.loc[t0:, "bb_pct_b"]
            pb_hi_thr = ctx.loc[t0:, "pb_hi_thr"] if "pb_hi_thr" in ctx else None
        else:
            pb_hi = None

        leg_pnl = 0.0
        exit_price = None
        exit_reason = None
        t1 = False
        for j, (t, bar) in enumerate(seg.iterrows()):
            h, l, c = float(bar["high"]), float(bar["low"]), float(bar["close"])
            # structural stop
            if l <= sl:
                exit_price, exit_reason = sl, "SL"
                break
            if exit_mode == "fixed_bps":
                if h >= tp_fixed:
                    exit_price, exit_reason = tp_fixed, "TP"
                    break
            else:
                # TP leg for pack (50% at +10bps then BE)
                if pack_split and not t1 and h >= entry * (1 + 10 / 1e4):
                    t1 = True
                    sl = entry  # BE lock
                # BB exhaustion: close at/above the %B extreme threshold
                if pb_hi is not None and t in pb_hi.index:
                    thr = pb_hi_thr.loc[t] if pb_hi_thr is not None else 0.9
                    pb = pb_hi.loc[t]
                    if not np.isnan(thr) and pb >= thr:
                        exit_price, exit_reason = c, "BB_EXH"
                        break
        if exit_price is None:
            exit_price = float(seg["close"].iloc[-1])
            exit_reason = "EOD"

        if pack_split and t1:
            # 50% banked at +10bps, 50% at exit
            pnl_pts = (entry * 10 / 1e4) * 0.5 + (exit_price - entry) * 0.5
        else:
            pnl_pts = exit_price - entry
        pnl_bps = (exit_price - entry) / entry * 1e4
        rows.append({
            "date": r["date"],
            "direction": r["direction"],
            "entry_time": r["entry_time"],
            "exit_time": seg.index[-1] if exit_reason == "EOD" else t,
            "entry_price": entry,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "risk_points": risk,
            "pnl_pts": pnl_pts,
            "r_multiple": pnl_pts / risk if risk > 0 else 0.0,
        })
    return pd.DataFrame(rows)


def summarize(ts: pd.Series) -> dict:
    if len(ts) == 0:
        return dict(trades=0, wr=0.0, pf=0.0, net=0.0, dd=0.0)
    cum = ts.cumsum()
    dd = (cum - cum.cummax()).min()
    gp, gl = ts[ts > 0].sum(), abs(ts[ts < 0].sum())
    return dict(trades=len(ts), wr=round((ts > 0).mean() * 100, 1),
                pf=round(gp / gl, 2) if gl > 0 else 999.0,
                net=round(ts.sum()), dd=round(abs(dd)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--long-only", action="store_true", default=True)
    args = ap.parse_args()

    print("Loading data + E34L signals (long-only base)...")
    df1, df5 = load_nt("ES")
    pt_val = 5.0  # ES micro $/pt

    # re-run E34L arm to get its signal set (saved file already has trades, but
    # run_arm regenerates signals deterministically)
    from scripts.analysis.mm_e34_battery import MMConfig
    e34l = run_arm("ES", MMConfig("E34L", "long-only", dir_filter="LONG"),
                   {"ES": df1}, {"ES": df5})
    sigs = pd.read_csv("data/derived/mm_e34_E34L_trades.csv") if False else e34l  # direct
    print(f"  {len(sigs)} long signals")

    print("\n=== MFE / MAE excursion study (post-rejection, 8h/96-bar window) ===")
    # rebuild signal-level entries from the trade records' entry price+time
    study = mfe_mae_study(sigs, df5)
    if len(study):
        for q in (0.10, 0.25, 0.50, 0.75, 0.90, 0.95):
            print(f"  p{int(q*100):02d}: MFE {study.mfe_bps.quantile(q):+6.1f} bps   MAE {study.mae_bps.quantile(q):+6.1f} bps")
        print(f"  hits: +5bps {((study.mfe_bps >= 5).mean()*100):5.1f}%   +10bps {((study.mfe_bps >= 10).mean()*100):5.1f}%   "
              f"+20bps {((study.mfe_bps >= 20).mean()*100):5.1f}%   +30bps {((study.mfe_bps >= 30).mean()*100):5.1f}%")
        t10 = study.t10.dropna()
        t20 = study.t20.dropna()
        print(f"  time-to-target (bars, 5m): +10bps med {t10.median():.0f} (n={len(t10)})  +20bps med {t20.median():.0f} (n={len(t20)})")

    print("\n=== E35 exit arms (long-only, structural stop, max 96 bars hold) ===")
    arms = [
        ("E35a", "fixed +10 bps", dict(exit_mode="fixed_bps", tp_bps=10.0)),
        ("E35b", "fixed +20 bps", dict(exit_mode="fixed_bps", tp_bps=20.0)),
        ("E35c", "BB-exhaustion (hold to %B extreme)", dict(exit_mode="bb_exhaustion")),
        ("E35d", "Pack: 10bps half + BB-exhaust runner", dict(exit_mode="pack", pack_split=True)),
        ("E35e", "BB-exhaustion short side", dict(exit_mode="bb_exhaustion", dir="SHORT")),
    ]

    for eid, label, kw in arms:
        want_dir = kw.pop("dir", "LONG")
        sub = sigs[sigs["direction"] == want_dir]
        tdf = simulate_exit_variant(sub, df5, **kw)
        if len(tdf):
            pnl_d = tdf["pnl_pts"] * pt_val
            s = summarize(pnl_d)
            reasons = tdf["exit_reason"].value_counts().to_dict()
            print(f"  {eid}  {label:<40} {s['trades']:>4} tr  WR{s['wr']:5.1f}%  PF{s['pf']:5.2f}  "
                  f"Net${s['net']:>6.0f}  DD${s['dd']:>5.0f}  exits={reasons}")
        else:
            print(f"  {eid}  {label:<40} 0 trades")


if __name__ == "__main__":
    main()