"""Audit what data is currently being fed to the reasoner vs what's missing."""
import pandas as pd
from datetime import datetime, time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from scripts.utils.fused_data_loader import load_fused_data
from scripts.trader.signals.ict_data_loader import (
    load_ict_context, load_ipda, load_kz_pivots, load_gaps,
    load_imbalances, load_orderblocks, load_liquidity, load_structure,
)

ticker = "ES1"
target = pd.Timestamp("2026-08-04", tz="US/Eastern")

# ═══ Load 1m data ═══
df = load_fused_data(ticker, timeframe="1m", require_historical=False)
if df.index.tz is None:
    df.index = pd.DatetimeIndex(df.index).tz_localize("UTC").tz_convert("US/Eastern")
else:
    df.index = df.index.tz_convert("US/Eastern")

day = df[(df.index >= target) & (df.index < target + pd.Timedelta(days=1))]
prev_day = df[(df.index >= target - pd.Timedelta(days=1)) & (df.index < target)]
prev_prev = df[(df.index >= target - pd.Timedelta(days=2)) & (df.index < target - pd.Timedelta(days=1))]

print(f"=== {ticker} Aug 4 data ===")
print(f"Rows: {len(day)}, Range: {day.index[0]} to {day.index[-1]}")
print(f"Day OHLC: O={day['open'].iloc[0]} H={day['high'].max()} L={day['low'].min()} C={day['close'].iloc[-1]}")
print()

# ═══ Session ranges (computed correctly from 1m data) ═══
# ICT session windows (ET):
# Asia: 20:00 prev day -> 00:00 (or 18:00 -> 02:00 for futures overnight)
# London: 02:00 -> 08:30
# Pre-NY: 08:30 -> 09:30
# NY AM: 09:30 -> 12:00
# NY Lunch: 12:00 -> 13:30
# NY PM: 13:30 -> 16:00

sessions = {
    "Asia": (time(20, 0), time(23, 59)),
    "London": (time(2, 0), time(8, 29)),
    "Pre-NY": (time(8, 30), time(9, 29)),
    "NY AM": (time(9, 30), time(11, 59)),
    "NY Lunch": (time(12, 0), time(13, 29)),
    "NY PM": (time(13, 30), time(15, 59)),
}

print("=== SESSION RANGES (computed from 1m) ===")
for name, (start, end) in sessions.items():
    if start > end:  # wraps midnight (Asia)
        sess = day[(day.index.time >= start) | (day.index.time <= end)]
    else:
        sess = day[(day.index.time >= start) & (day.index.time <= end)]
    if not sess.empty:
        print(f"  {name}: {len(sess)} bars, H={sess['high'].max():.2f} L={sess['low'].min():.2f} Range={sess['high'].max()-sess['low'].min():.2f}")
    else:
        print(f"  {name}: NO DATA")
print()

# ═══ What the reasoner currently gets ═══
print("=== WHAT REASONER CURRENTLY GETS ===")
ict = load_ict_context(ticker, current_price=0)
print(f"  PDH: {ict.get('pdh')}")
print(f"  PDL: {ict.get('pdl')}")
print(f"  PDC: {ict.get('pdc')}")
print(f"  PWH: {ict.get('pwh')}")
print(f"  PWL: {ict.get('pwl')}")
print(f"  Midnight Open: {ict.get('midnight_open')}")
print(f"  Dealing Range %: {ict.get('dealing_range_pct')}")
print(f"  Premium/Discount: {ict.get('premium_discount')}")
print(f"  BSL: {ict.get('bsl_target')}")
print(f"  SSL: {ict.get('ssl_target')}")
print()

# ═══ What the reasoner is MISSING ═══
print("=== WHAT'S MISSING ===")

# Session highs/lows
print("  SESSION H/L (not in features):")
for name, (start, end) in sessions.items():
    if start > end:
        sess = day[(day.index.time >= start) | (day.index.time <= end)]
    else:
        sess = day[(day.index.time >= start) & (day.index.time <= end)]
    if not sess.empty:
        print(f"    {name} High: {sess['high'].max():.2f}, Low: {sess['low'].min():.2f}")
print()

# FVGs / Imbalances
print("  FVGs / IMBALANCES:")
imb = load_imbalances(ticker, auto_refresh=False)
if not imb.empty:
    print(f"    Total: {len(imb)} rows, columns: {imb.columns.tolist()}")
    print(f"    Last 5:")
    print(imb.tail(5).to_string())
else:
    print("    NO DATA")
print()

# Order Blocks
print("  ORDER BLOCKS:")
ob = load_orderblocks(ticker, auto_refresh=False)
if not ob.empty:
    print(f"    Total: {len(ob)} rows, columns: {ob.columns.tolist()}")
    print(f"    Last 5:")
    print(ob.tail(5).to_string())
else:
    print("    NO DATA")
print()

# Liquidity levels
print("  LIQUIDITY LEVELS:")
liq = load_liquidity(ticker, auto_refresh=False)
if not liq.empty:
    print(f"    Total: {len(liq)} rows, columns: {liq.columns.tolist()}")
    print(f"    Last 5:")
    print(liq.tail(5).to_string())
else:
    print("    NO DATA")
print()

# Structure (BOS/MSS)
print("  MARKET STRUCTURE:")
struct = load_structure(ticker, auto_refresh=False)
if not struct.empty:
    print(f"    Total: {len(struct)} rows, columns: {struct.columns.tolist()}")
    print(f"    Last 5:")
    print(struct.tail(5).to_string())
else:
    print("    NO DATA")
print()

# ═══ What's REDUNDANT (user said they don't use IPDA) ═══
print("=== REDUNDANT (user doesn't use) ===")
print("  IPDA-20 position (remove)")
print("  IPDA-60 position (remove)")
print("  Pre-computed 4-model bias (remove — this is what we're replacing)")
print("  Killzone pivots (review — may not be needed)")
print()

# ═══ HTF levels for MTF bias ═══
print("=== HTF LEVELS NEEDED FOR MTF BIAS ===")
# Daily levels
print(f"  Prior Day: O={prev_day['open'].iloc[0]:.2f} H={prev_day['high'].max():.2f} L={prev_day['low'].min():.2f} C={prev_day['close'].iloc[-1]:.2f}")
if not prev_prev.empty:
    print(f"  Prior Prior Day: O={prev_prev['open'].iloc[0]:.2f} H={prev_prev['high'].max():.2f} L={prev_prev['low'].min():.2f} C={prev_prev['close'].iloc[-1]:.2f}")

# Weekly levels (compute from data)
week_start = target - pd.Timedelta(days=target.weekday())
week = df[(df.index >= week_start) & (df.index < target + pd.Timedelta(days=1))]
if not week.empty:
    print(f"  Week (Mon-{target.date()}): H={week['high'].max():.2f} L={week['low'].min():.2f}")

# Resample to 1H and 4H for HTF structure
df_1h = df.resample("1h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna(subset=["open"])
df_4h = df.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna(subset=["open"])
df_1d = df.resample("1D").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna(subset=["open"])

print()
print("=== HTF RESAMPLED DATA ===")
print(f"  1D bars (last 5):")
print(df_1d.tail(5)[["open","high","low","close"]].to_string())
print()
print(f"  4H bars (last 5):")
print(df_4h.tail(5)[["open","high","low","close"]].to_string())
print()
print(f"  1H bars (last 10):")
print(df_1h.tail(10)[["open","high","low","close"]].to_string())