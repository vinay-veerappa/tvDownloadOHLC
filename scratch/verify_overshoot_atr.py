#!/usr/bin/env python
"""Verify stop-overshoot amplifier + compare absolute vs ATR-normalized IB ceiling."""
import json, os, datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ET = "America/New_York"
PARQUET = os.path.join(HERE, "..", "data", "NQ1_1m.parquet")
d = json.load(open(os.path.join(HERE, "forensic_retest_report.json"), encoding="utf-8"))
tr = d["trades"]

# 1. Stop-overshoot check: mae vs stop_dist (0.5*ib_range)
print("=== Stop-overshoot (mae vs 0.5*ib_range) ===")
for lab, sel in [("H1-win", [t for t in tr if t["h1"] and t["win"]]),
                 ("H1-loss", [t for t in tr if t["h1"] and not t["win"]]),
                 ("H2-win", [t for t in tr if not t["h1"] and t["win"]]),
                 ("H2-loss", [t for t in tr if not t["h1"] and not t["win"]])]:
    if not sel:
        continue
    mae = np.array([t["mae"] for t in sel])
    stopd = np.array([0.5 * t["ib_range"] for t in sel])
    overshoot = mae / stopd  # >1 means stop blown past
    print(f"  {lab:8s} n={len(sel):2d} median_mae={np.median(mae):.0f} "
          f"median_stopd={np.median(stopd):.0f} median_overshoot={np.median(overshoot):.2f} "
          f"frac_overshoot>1={np.mean(overshoot>1):.2f}")

# 2. ATR-normalized IB ceiling: ib_range / ATR14(daily, through D-1)
print("\n=== Loading daily for ATR ===")
df = pd.read_parquet(PARQUET)
if not isinstance(df.index, pd.DatetimeIndex):
    df.index = pd.to_datetime(df.index)
df.index = df.index.tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
df = df[~df.index.isna()].sort_index()
rth = df.between_time("09:30", "15:59")
daily = rth.resample("1B").agg({"high": "max", "low": "min", "close": "last"}).dropna()
atr14 = (pd.concat([daily["high"] - daily["low"],
                    (daily["high"] - daily["close"].shift()).abs(),
                    (daily["low"] - daily["close"].shift()).abs()], axis=1).max(axis=1)).rolling(14).mean()
atr_prior = atr14.shift(1)  # ATR through D-1

# map trade date -> atr_prior
trade_dates = [datetime.date.fromisoformat(t["date"]) for t in tr]
atr_map = {}
for idx, val in atr_prior.items():
    if not np.isnan(val):
        atr_map[idx.date()] = val

print("=== IB-range / ATR14(prior) CEILING sweep ===")
allh1 = [t for t in tr if t["h1"]]
allh2 = [t for t in tr if not t["h1"]]
for x in [1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]:
    kept = []
    for t in tr:
        a = atr_map.get(datetime.date.fromisoformat(t["date"]))
        if a is None or a <= 0:
            continue
        if t["ib_range"] / a <= x:
            kept.append(t)
    h1 = [t for t in kept if t["h1"]]; h2 = [t for t in kept if not t["h1"]]
    wr1 = sum(t["win"] for t in h1) / len(h1) if h1 else 0
    wr2 = sum(t["win"] for t in h2) / len(h2) if h2 else 0
    net = sum(t["pnl"] for t in kept)
    gw = sum(t["pnl"] for t in kept if t["pnl"] > 0)
    gl = abs(sum(t["pnl"] for t in kept if t["pnl"] < 0))
    pf = round(gw / gl, 3) if gl else float("inf")
    print(f"  ceiling {x:.2f}xATR: H1 {len(h1)}/{len(allh1)} WR={wr1:.3f} | "
          f"H2 {len(h2)}/{len(allh2)} WR={wr2:.3f} | total n={len(kept)} net={int(net):+d} PF={pf}")

# 3. Sanity: report ATR values for H1 vs H2 trade days
print("\n=== ATR14(prior) on trade days ===")
h1_atr = [atr_map.get(datetime.date.fromisoformat(t["date"])) for t in allh1]
h2_atr = [atr_map.get(datetime.date.fromisoformat(t["date"])) for t in allh2]
print(f"  H1 median ATR = {np.median([a for a in h1_atr if a]):.1f}")
print(f"  H2 median ATR = {np.median([a for a in h2_atr if a]):.1f}")