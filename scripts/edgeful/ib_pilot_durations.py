"""IB Statistics Pilot - Phase F: Multi-duration IB comparison.

Computes IB at 5/15/30/45/60 min directly from 1-min bars and compares:
  - Range ratio: how much of the 60-min IB is captured by shorter windows
  - Direction agreement: does the 5/15-min IB predict the 60-min IB direction?
  - Close position agreement: does the short IB close position predict the long one?
  - Break direction agreement: does the short IB break predict the long IB break?
  - Per-duration edge: E[R] for each play at each IB duration
  - Dollar risk comparison: shorter IB = smaller range = tighter $ stop

Usage:
    python -m scripts.edgeful.ib_pilot_durations --symbol NQ1 --years 2
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.edgeful.ib_pilot_stats import DERIVED

DURATIONS = [5, 15, 30, 45, 60]
NY_OPEN = "09:30"  # ET


def load_1m(symbol: str, years: int = 2) -> pd.DataFrame:
    """Load 1-min bars for the last N years (historical + live fused)."""
    # Historical
    hist_path = ROOT / "data" / f"{symbol}_1m.parquet"
    df_hist = pd.read_parquet(hist_path)
    df_hist.index = pd.to_datetime(df_hist.index)
    df_hist = df_hist.tz_localize(None) if df_hist.index.tz is not None else df_hist

    # Live
    live_path = ROOT / "data" / "live" / f"live_storage_-{symbol.replace('1','')}.parquet"
    if live_path.exists():
        df_live = pd.read_parquet(live_path)
        if "timestamp" in df_live.columns:
            df_live.index = pd.to_datetime(df_live["timestamp"])
        df_live = df_live[["open", "high", "low", "close"]]
        # Combine and dedupe
        df = pd.concat([df_hist[["open","high","low","close"]], df_live])
        df = df[~df.index.duplicated(keep="last")]
    else:
        df = df_hist[["open", "high", "low", "close"]]

    # Filter to last N years
    max_ts = df.index.max()
    min_ts = max_ts - pd.Timedelta(days=years * 365)
    df = df[df.index >= min_ts].copy()
    print(f"[1m] {symbol}: {len(df)} bars from {df.index.min()} to {df.index.max()}")
    return df


def compute_ib_at_duration(df_1m: pd.DataFrame, duration_min: int) -> pd.DataFrame:
    """Compute IB high/low/open/close for each trading day at a given duration.

    IB window: 09:30 ET to 09:30 + duration_min
    Returns one row per trading_day with ib_high, ib_low, ib_open, ib_close, ib_range.
    """
    # Filter to RTH hours (09:30 to 16:00 ET) — the 1m data is in ET
    # The historical data index is naive datetime in ET
    df = df_1m.copy()
    df["time"] = df.index.time
    df["date"] = df.index.date

    ib_start = pd.Timestamp(NY_OPEN).time()
    ib_end = (pd.Timestamp(NY_OPEN) + pd.Timedelta(minutes=duration_min)).time()

    # IB window bars
    ib_mask = (df["time"] >= ib_start) & (df["time"] < ib_end)
    ib_bars = df[ib_mask].copy()
    if ib_bars.empty:
        return pd.DataFrame()

    # Aggregate per trading day
    ib_agg = ib_bars.groupby("date").agg(
        ib_open=("open", "first"),
        ib_high=("high", "max"),
        ib_low=("low", "min"),
        ib_close=("close", "last"),
    )
    ib_agg["ib_range"] = ib_agg["ib_high"] - ib_agg["ib_low"]
    ib_agg["ib_mid"] = (ib_agg["ib_high"] + ib_agg["ib_low"]) / 2
    ib_agg["ib_close_position"] = np.where(
        ib_agg["ib_range"] > 0,
        ((ib_agg["ib_close"] - ib_agg["ib_low"]) / ib_agg["ib_range"]).clip(0, 1),
        0.5
    )
    ib_agg["ib_candle_color"] = np.where(ib_agg["ib_close"] > ib_agg["ib_open"], "green",
                                          np.where(ib_agg["ib_close"] < ib_agg["ib_open"], "red", "doji"))
    # Direction: +1 if low formed first (bullish), -1 if high formed first
    # Need first-touch times — track when each extreme was FIRST established
    # The first bar always sets both; we need the bar where the SECOND extreme is set
    # i.e. the low is "formed first" if the high is not reached until later
    # Track: first time the high reaches its final IB value, and vice versa
    ib_bars_sorted = ib_bars.sort_values(["date", "time"])
    # Cumulative max/min within IB window
    ib_bars_sorted["cum_high"] = ib_bars_sorted.groupby("date")["high"].cummax()
    ib_bars_sorted["cum_low"] = ib_bars_sorted.groupby("date")["low"].cummin()
    # The final IB high/low
    final_high = ib_bars_sorted.groupby("date")["cum_high"].transform("last")
    final_low = ib_bars_sorted.groupby("date")["cum_low"].transform("last")
    # First time cum_high reaches final_high
    ib_bars_sorted["high_done"] = ib_bars_sorted["cum_high"] >= final_high
    ib_bars_sorted["low_done"] = ib_bars_sorted["cum_low"] <= final_low
    # First bar where high is done
    first_high_done = ib_bars_sorted[ib_bars_sorted["high_done"]].groupby("date").head(1)
    first_low_done = ib_bars_sorted[ib_bars_sorted["low_done"]].groupby("date").head(1)

    fh = first_high_done.groupby("date").apply(lambda g: g.index[0]).rename("first_high_time")
    fl = first_low_done.groupby("date").apply(lambda g: g.index[0]).rename("first_low_time")
    ib_agg = ib_agg.join(fh).join(fl)
    ib_agg["bias_firstreach"] = np.where(
        ib_agg["first_low_time"] < ib_agg["first_high_time"], 1,
        np.where(ib_agg["first_high_time"] < ib_agg["first_low_time"], -1, 0)
    )

    # Range as % of price
    ib_agg["range_pct"] = (ib_agg["ib_range"] / ib_agg["ib_close"]) * 100

    ib_agg["duration_min"] = duration_min
    ib_agg["trading_day"] = pd.to_datetime(ib_agg.index)

    return ib_agg.reset_index(drop=True)


def compute_break_direction(df_1m: pd.DataFrame, ib: pd.DataFrame, duration_min: int) -> pd.DataFrame:
    """Compute first break direction for each day (which IB boundary broke first).

    Uses the outcome window (IB close to 16:00 ET).
    """
    df = df_1m.copy()
    df["time"] = df.index.time
    df["date"] = df.index.date

    ib_end = (pd.Timestamp(NY_OPEN) + pd.Timedelta(minutes=duration_min)).time()
    rth_end = pd.Timestamp("16:00").time()

    # Outcome window: after IB close to 16:00
    outcome_mask = (df["time"] >= ib_end) & (df["time"] < rth_end)
    outcome_bars = df[outcome_mask].copy()

    results = []
    for _, row in ib.iterrows():
        date = row["trading_day"].date()
        day_bars = outcome_bars[outcome_bars["date"] == date]
        if day_bars.empty:
            results.append({"trading_day": row["trading_day"], "first_break_dir": 0,
                           "first_break_minutes": np.nan, "double_break": False})
            continue

        ib_high = row["ib_high"]
        ib_low = row["ib_low"]

        # Find first break (close beyond boundary)
        high_break = day_bars[day_bars["close"] > ib_high]
        low_break = day_bars[day_bars["close"] < ib_low]

        first_high_time = high_break.index[0] if not high_break.empty else pd.NaT
        first_low_time = low_break.index[0] if not low_break.empty else pd.NaT

        if pd.isna(first_high_time) and pd.isna(first_low_time):
            break_dir = 0
            break_min = np.nan
            double = False
        elif pd.isna(first_low_time):
            break_dir = 1
            break_min = (first_high_time - pd.Timestamp.combine(date, ib_end)).total_seconds() / 60
            double = not low_break.empty
        elif pd.isna(first_high_time):
            break_dir = -1
            break_min = (first_low_time - pd.Timestamp.combine(date, ib_end)).total_seconds() / 60
            double = not high_break.empty
        else:
            if first_high_time < first_low_time:
                break_dir = 1
                break_min = (first_high_time - pd.Timestamp.combine(date, ib_end)).total_seconds() / 60
                double = True
            else:
                break_dir = -1
                break_min = (first_low_time - pd.Timestamp.combine(date, ib_end)).total_seconds() / 60
                double = True

        results.append({
            "trading_day": row["trading_day"],
            "first_break_dir": break_dir,
            "first_break_minutes": break_min,
            "double_break": double,
        })

    return pd.DataFrame(results)


def compare_durations(symbol: str, years: int = 2):
    """Compute IB at all durations and compare."""
    print(f"\n{'='*90}")
    print(f"MULTI-DURATION IB COMPARISON ({symbol}, {years} years)")
    print(f"{'='*90}")

    df_1m = load_1m(symbol, years)
    if len(df_1m) == 0:
        return

    # Compute IB at each duration
    ib_by_dur: Dict[int, pd.DataFrame] = {}
    for dur in DURATIONS:
        ib = compute_ib_at_duration(df_1m, dur)
        if len(ib) == 0:
            continue
        breaks = compute_break_direction(df_1m, ib, dur)
        ib = ib.merge(breaks, on="trading_day", how="left")
        ib_by_dur[dur] = ib
        print(f"  IB{dur}: {len(ib)} sessions, range_pct median={ib['range_pct'].median():.3f}%")

    if len(ib_by_dur) < 2:
        print("  Insufficient durations computed.")
        return

    # ── 1. Range ratio: how much of IB60 is captured by shorter windows ──
    print(f"\n--- 1. Range Ratio (shorter IB / 60-min IB) ---")
    ib60 = ib_by_dur[60].set_index("trading_day")
    print(f"  {'Duration':<10} {'Median range':>14} {'Median ratio':>14} {'P25 ratio':>12} {'P75 ratio':>12}")
    for dur in DURATIONS:
        if dur not in ib_by_dur:
            continue
        ib = ib_by_dur[dur].set_index("trading_day")
        common = ib.index.intersection(ib60.index)
        if len(common) < 20:
            continue
        ratio = ib.loc[common, "ib_range"] / ib60.loc[common, "ib_range"]
        med_range = ib["ib_range"].median()
        print(f"  IB{dur:<8} {med_range:>12.1f}pt {ratio.median():>13.2f}x {ratio.quantile(0.25):>11.2f}x {ratio.quantile(0.75):>11.2f}x")

    # ── 2. Direction agreement: does short IB predict long IB bias? ──
    print(f"\n--- 2. Direction Agreement (bias_firstreach short vs 60-min) ---")
    print(f"  {'Duration':<10} {'Agree %':>10} {'N':>6} {'Kappa':>8}")
    for dur in DURATIONS:
        if dur not in ib_by_dur or dur == 60:
            continue
        ib = ib_by_dur[dur].set_index("trading_day")
        common = ib.index.intersection(ib60.index)
        if len(common) < 20:
            continue
        short_bias = ib.loc[common, "bias_firstreach"]
        long_bias = ib60.loc[common, "bias_firstreach"]
        agree = (short_bias == long_bias).mean() * 100
        # Cohen's kappa
        n = len(common)
        po = agree / 100
        pe = ((short_bias == 1).mean() * (long_bias == 1).mean() +
              (short_bias == -1).mean() * (long_bias == -1).mean() +
              (short_bias == 0).mean() * (long_bias == 0).mean())
        kappa = (po - pe) / (1 - pe) if (1 - pe) > 0 else 0
        print(f"  IB{dur:<8} {agree:>9.1f}% {n:>6} {kappa:>8.3f}")

    # ── 3. Close position agreement ──
    print(f"\n--- 3. Close Position Agreement (short IB close pos vs 60-min) ---")
    print(f"  {'Duration':<10} {'Corr':>8} {'P(|diff|<0.1)':>14} {'N':>6}")
    for dur in DURATIONS:
        if dur not in ib_by_dur or dur == 60:
            continue
        ib = ib_by_dur[dur].set_index("trading_day")
        common = ib.index.intersection(ib60.index)
        if len(common) < 20:
            continue
        short_cp = ib.loc[common, "ib_close_position"]
        long_cp = ib60.loc[common, "ib_close_position"]
        corr = short_cp.corr(long_cp)
        close = (abs(short_cp - long_cp) < 0.1).mean() * 100
        print(f"  IB{dur:<8} {corr:>8.3f} {close:>13.1f}% {len(common):>6}")

    # ── 4. Break direction agreement ──
    print(f"\n--- 4. Break Direction Agreement (short IB break vs 60-min break) ---")
    print(f"  {'Duration':<10} {'Agree %':>10} {'N':>6}")
    for dur in DURATIONS:
        if dur not in ib_by_dur or dur == 60:
            continue
        ib = ib_by_dur[dur].set_index("trading_day")
        common = ib.index.intersection(ib60.index)
        if len(common) < 20:
            continue
        short_break = ib.loc[common, "first_break_dir"]
        long_break = ib60.loc[common, "first_break_dir"]
        # Only compare days where both have a break
        both_broke = (short_break != 0) & (long_break != 0)
        if both_broke.sum() < 20:
            print(f"  IB{dur:<8} (insufficient both-broke days)")
            continue
        agree = (short_break[both_broke] == long_break[both_broke]).mean() * 100
        print(f"  IB{dur:<8} {agree:>9.1f}% {both_broke.sum():>6}")

    # ── 5. Rule 1 replication at each duration ──
    print(f"\n--- 5. Rule 1 Direction Trigger at Each Duration ---")
    print(f"  {'Duration':<10} {'N (1A)':>7} {'1A hit %':>10} {'N (1B)':>7} {'1B hit %':>10}")
    for dur in DURATIONS:
        if dur not in ib_by_dur:
            continue
        ib = ib_by_dur[dur]
        # Rule 1A: low first + close in top 25%
        r1a = ib[(ib["bias_firstreach"] == 1) & (ib["ib_close_position"] >= 0.75)]
        n1a = len(r1a)
        hit1a = (r1a["first_break_dir"] == 1).sum() if n1a else 0
        pct1a = 100 * hit1a / n1a if n1a else 0
        # Rule 1B: high first + close in bot 25%
        r1b = ib[(ib["bias_firstreach"] == -1) & (ib["ib_close_position"] <= 0.25)]
        n1b = len(r1b)
        hit1b = (r1b["first_break_dir"] == -1).sum() if n1b else 0
        pct1b = 100 * hit1b / n1b if n1b else 0
        print(f"  IB{dur:<8} {n1a:>7} {pct1a:>9.1f}% {n1b:>7} {pct1b:>9.1f}%")

    # ── 6. Dollar risk comparison (the key prop-viability question) ──
    print(f"\n--- 6. Dollar Risk Comparison (1 Micro, $50K account) ---")
    point_value = 2.0  # MNQ
    account = 50000
    print(f"  {'Duration':<10} {'Median range':>14} {'Median $ risk':>14} {'% account':>11} {'Stop (pts)':>11}")
    for dur in DURATIONS:
        if dur not in ib_by_dur:
            continue
        ib = ib_by_dur[dur]
        med_range = ib["ib_range"].median()
        # Stop at opposite IB boundary = full range
        dollar_risk = med_range * point_value
        pct = 100 * dollar_risk / account
        print(f"  IB{dur:<8} {med_range:>12.1f}pt ${dollar_risk:>11.0f} {pct:>9.2f}% {med_range:>10.1f}pt")

    # ── 7. Can IB5 + IB15 predict IB60? ──
    print(f"\n--- 7. Predictive Power: Can IB5 + IB15 predict IB60? ---")
    if 5 in ib_by_dur and 15 in ib_by_dur and 60 in ib_by_dur:
        ib5 = ib_by_dur[5].set_index("trading_day")
        ib15 = ib_by_dur[15].set_index("trading_day")
        ib60 = ib_by_dur[60].set_index("trading_day")
        common = ib5.index.intersection(ib15.index).intersection(ib60.index)
        if len(common) < 100:
            print("  Insufficient common days.")
            return

        # Features from IB5 and IB15
        X = pd.DataFrame({
            "bias_5": ib5.loc[common, "bias_firstreach"],
            "bias_15": ib15.loc[common, "bias_firstreach"],
            "close_pos_5": ib5.loc[common, "ib_close_position"],
            "close_pos_15": ib15.loc[common, "ib_close_position"],
            "range_5": ib5.loc[common, "ib_range"],
            "range_15": ib15.loc[common, "ib_range"],
            "range_pct_5": ib5.loc[common, "range_pct"],
            "range_pct_15": ib15.loc[common, "range_pct"],
        })
        # Target: IB60 break direction (only days where break != 0)
        y_break = ib60.loc[common, "first_break_dir"]
        mask = y_break != 0
        X_use = X[mask]
        y_use = (y_break[mask] == 1).astype(int)  # 1 = high broke first

        if len(y_use) < 100:
            print("  Insufficient break days.")
            return

        # Logistic regression
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score

        split = int(len(X_use) * 0.7)
        X_train, X_test = X_use.iloc[:split], X_use.iloc[split:]
        y_train, y_test = y_use.iloc[:split], y_use.iloc[split:]

        lr = LogisticRegression(max_iter=1000, C=0.1)
        lr.fit(X_train, y_train)
        pred = lr.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, pred)

        print(f"  Logistic regression: P(IB60 high breaks first | IB5 + IB15 features)")
        print(f"  N_train={len(X_train)}  N_test={len(X_test)}  AUC={auc:.4f}")
        print(f"  Coefficients:")
        for feat, coef in zip(X.columns, lr.coef_[0]):
            print(f"    {feat:<20} {coef:>+.4f}")

        # Also: does IB5+IB15 Rule 1A predict IB60 Rule 1A?
        # IB5 Rule 1A: bias_5=+1 AND close_pos_5 >= 0.75
        r1a_5 = (X["bias_5"] == 1) & (X["close_pos_5"] >= 0.75)
        r1a_15 = (X["bias_15"] == 1) & (X["close_pos_15"] >= 0.75)
        r1a_60 = (ib60.loc[common, "bias_firstreach"] == 1) & (ib60.loc[common, "ib_close_position"] >= 0.75)

        print(f"\n  Rule 1A agreement (IB5 vs IB60): {(r1a_5 == r1a_60).mean()*100:.1f}%")
        print(f"  Rule 1A agreement (IB15 vs IB60): {(r1a_15 == r1a_60).mean()*100:.1f}%")
        print(f"  Rule 1A agreement (IB5 AND IB15 vs IB60): {((r1a_5 & r1a_15) == r1a_60).mean()*100:.1f}%")

        # P(IB60 high breaks first | IB5 Rule 1A fires)
        if r1a_5.sum() > 0:
            hit = (y_break[r1a_5] == 1).mean() * 100
            print(f"\n  P(IB60 high breaks first | IB5 Rule 1A fires): {hit:.1f}% (N={r1a_5.sum()})")
        if r1a_15.sum() > 0:
            hit = (y_break[r1a_15] == 1).mean() * 100
            print(f"  P(IB60 high breaks first | IB15 Rule 1A fires): {hit:.1f}% (N={r1a_15.sum()})")
        both = r1a_5 & r1a_15
        if both.sum() > 0:
            hit = (y_break[both] == 1).mean() * 100
            print(f"  P(IB60 high breaks first | IB5 AND IB15 Rule 1A fire): {hit:.1f}% (N={both.sum()})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="NQ1")
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()

    print(f"\n{'#'*90}")
    print(f"# PHASE F: MULTI-DURATION IB COMPARISON")
    print(f"# Symbol: {args.symbol}, {args.years} years, durations: {DURATIONS}")
    print(f"{'#'*90}")

    compare_durations(args.symbol, args.years)

    print(f"\n{'#'*90}")
    print(f"# PHASE F COMPLETE")
    print(f"{'#'*90}")


if __name__ == "__main__":
    main()