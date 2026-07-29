"""
Diagnostic: quantify the AVWAP parity gap between Python (live_storage continuous)
and NT8 (##-## continuous) for the 8 mismatch days in Jan-Jun 2026.

Root cause hypothesis: the two "continuous" feeds use different roll adjustment
methods and/or volume profiles, causing the volume-weighted AVWAP to land at
different relative positions within the IB range, flipping break_vs_avwap_0930.

This script:
1. Loads the NT8 trade ledger (entry times + prices) for each month.
2. Loads the Python live_storage continuous bars for the same days.
3. Computes the price offset (NT8 price - Python price) at each NT8 entry time.
4. Computes the on-the-fly AVWAP from Python bars at the NT8 entry time.
5. Checks whether break_vs_avwap_0930 sign flips vs the pre-computed confluence value.
6. Reports whether the offset is constant (pure roll) or variable (different feed).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from datetime import time

SCRATCH = Path("scratch")

# ─── Load NT8 trade ledgers ─────────────────────────────────────────────────
NT8_FILES = {
    "jan2026": "nt8_ib_breakout_nq_jan2026.json",
    "feb2026": "nt8_ib_breakout_nq_feb2026.json",
    "mar2026": "nt8_ib_breakout_nq_mar2026.json",
    "may2026": "nt8_ib_breakout_nq_may2026.json",
    "jun2026": "nt8_ib_breakout_nq_jun2026.json",
}

nt8_trades = []
for period, fname in NT8_FILES.items():
    path = SCRATCH / fname
    if not path.exists():
        continue
    d = json.load(open(path))
    for t in d.get("trades", []):
        et = pd.Timestamp(t["entryTime"]).tz_localize("America/New_York")
        nt8_trades.append({
            "period": period,
            "entry_time": et,
            "entry_price": t["entryPrice"],
            "exit_reason": t.get("exitReason", ""),
        })
nt8_df = pd.DataFrame(nt8_trades)
print(f"NT8 trades loaded: {len(nt8_df)}")
print(nt8_df[["entry_time", "entry_price"]].to_string())

# ─── Load Python live_storage continuous NQ ────────────────────────────────
df = pd.read_parquet("data/live/live_storage_-NQ.parquet")
ts = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert("America/New_York")
df["ts"] = ts
df = df.set_index("ts").sort_index()
print(f"\nPython live_storage rows: {len(df)}, range: {df.index.min()} -> {df.index.max()}")

# ─── Load pre-computed confluence break_vs_avwap_0930 ───────────────────────
conf = pd.read_parquet("data/derived/ib_confluence_NQ1.parquet")
conf_ny = conf[conf["session_slot"] == "NY AM IB"].copy()
conf_ny["td"] = pd.to_datetime(conf_ny["trading_day"]).dt.date
conf_ny = conf_ny.set_index("td")
print(f"Confluence NY AM IB rows: {len(conf_ny)}")

# ─── For each NT8 trade, find the Python bar at the same time ───────────────
print("\n=== PRICE OFFSET ANALYSIS ===")
print(f"{'date':<12} {'nt8_time':<8} {'nt8_px':>10} {'py_px':>10} {'offset':>10} {'offset_const?'}")

offsets = []
for _, nt8_row in nt8_df.iterrows():
    et = nt8_row["entry_time"]
    day = et.date()
    # Find the Python bar at or just before the NT8 entry time
    day_bars = df.loc[et.normalize():et.normalize() + pd.Timedelta(days=1)]
    if day_bars.empty:
        continue
    # Get the bar matching the entry time (or closest)
    py_bar = day_bars[day_bars.index <= et]
    if py_bar.empty:
        continue
    py_close = float(py_bar["close"].iloc[-1])
    nt8_px = nt8_row["entry_price"]
    offset = nt8_px - py_close
    offsets.append(offset)
    print(f"{str(day):<12} {et.strftime('%H:%M'):<8} {nt8_px:>10.2f} {py_close:>10.2f} {offset:>10.2f}")

offsets = np.array(offsets)
print(f"\nOffset stats: mean={offsets.mean():.2f}, std={offsets.std():.2f}, min={offsets.min():.2f}, max={offsets.max():.2f}")
print(f"Is offset constant (std < 5pts)? {offsets.std() < 5.0}")
if offsets.std() > 5.0:
    print("→ VARIABLE offset: the two feeds are DIFFERENT constructions (not a pure roll)")
    print("→ AVWAP (volume-weighted) will land at different relative positions → sign flips")
else:
    print("→ CONSTANT offset: pure roll adjustment; AVWAP sign should be invariant")

# ─── On-the-fly AVWAP comparison for a sample day ───────────────────────────
print("\n=== ON-THE-FLY AVWAP vs PRE-COMPUTED (sample: 2026-06-04) ===")
sample_day = df.loc["2026-06-04"]
rth = sample_day.between_time("09:30", "15:50")
tp = (rth["high"] + rth["low"] + rth["close"]) / 3.0
pv = tp * rth["volume"]
cum_pv = pv.cumsum()
cum_v = rth["volume"].cumsum()
avwap_onthefly = cum_pv / cum_v
rth = rth.assign(avwap_onthefly=avwap_onthefly)

# IB boundaries
ib = rth.iloc[:30]
ib_high = ib["high"].max()
ib_low = ib["low"].min()
ib_range = ib_high - ib_low
print(f"IB: high={ib_high}, low={ib_low}, range={ib_range}")

# First break
post_ib = rth.iloc[30:]
long_break = post_ib[post_ib["close"] > ib_high]
short_break = post_ib[post_ib["close"] < ib_low]
if not long_break.empty:
    break_time = long_break.index[0]
    break_dir = 1
elif not short_break.empty:
    break_time = short_break.index[0]
    break_dir = -1
else:
    break_time = None
    break_dir = 0

if break_time is not None:
    break_close = float(rth.loc[break_time, "close"])
    break_avwap = float(rth.loc[break_time, "avwap_onthefly"])
    onthefly_bva = 1 if break_close > break_avwap else (-1 if break_close < break_avwap else 0)
    print(f"First break: time={break_time.strftime('%H:%M')}, dir={break_dir}, close={break_close}, avwap={break_avwap}")
    print(f"On-the-fly break_vs_avwap_0930 = {onthefly_bva}")

    # Pre-computed value from confluence
    precomp = conf_ny.loc[pd.Timestamp("2026-06-04").date()] if pd.Timestamp("2026-06-04").date() in conf_ny.index else None
    if precomp is not None:
        print(f"Pre-computed break_vs_avwap_0930 = {precomp['break_vs_avwap_0930']}")
        print(f"MATCH? {onthefly_bva == precomp['break_vs_avwap_0930']}")

# ─── Check if NT8 feed price is just a shifted version ──────────────────────
print("\n=== ROLL ADJUSTMENT METHOD CHECK ===")
# If additive: offset = constant. If multiplicative (ratio): offset/price = constant.
if len(offsets) > 1:
    ratios = []
    for _, nt8_row in nt8_df.iterrows():
        et = nt8_row["entry_time"]
        day_bars = df.loc[et.normalize():et.normalize() + pd.Timedelta(days=1)]
        py_bar = day_bars[day_bars.index <= et]
        if py_bar.empty:
            continue
        py_close = float(py_bar["close"].iloc[-1])
        nt8_px = nt8_row["entry_price"]
        if py_close > 0:
            ratios.append(nt8_px / py_close)
    ratios = np.array(ratios)
    print(f"Ratio (nt8/py) stats: mean={ratios.mean():.6f}, std={ratios.std():.6f}, min={ratios.min():.6f}, max={ratios.max():.6f}")
    print(f"Is ratio constant (std < 0.001)? {ratios.std() < 0.001}")
    if ratios.std() < 0.001:
        print("→ MULTIPLICATIVE roll: AVWAP sign invariant (both close and avwap scale by same ratio)")
    elif offsets.std() < 5.0:
        print("→ ADDITIVE roll: AVWAP sign invariant (both close and avwap shift by same constant)")
    else:
        print("→ NEITHER: the feeds have fundamentally different price action → AVWAP sign can flip")
        print("→ ROOT CAUSE CONFIRMED: different continuous contract constructions")