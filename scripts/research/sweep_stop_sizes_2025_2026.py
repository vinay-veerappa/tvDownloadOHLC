import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

_root_dir = str(Path(__file__).resolve().parents[2])
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config

app_cfg = load_config()
loader = DataLoader(app_cfg)
df = loader.load_price("NQ1")

if df.index.tz is None:
    df.index = df.index.tz_localize("UTC")
df = df.tz_convert("America/New_York")

df['hour'] = df.index.hour
df['minute'] = df.index.minute
df['timeHHMM'] = df['hour'] * 100 + df['minute']

# Filter to 2025-2026 Morning Initial Balance (09:30 to 10:30 ET)
sub = df[(df.index.year >= 2024) & (df['timeHHMM'] >= 930) & (df['timeHHMM'] <= 1030)].copy()

print(f"Total 2024-2026 Morning Bars: {len(sub):,}")
print(f"Median NQ Price: {sub['close'].median():,.0f}")

# Sweep Stop Sizes at 1:2.0 R:R on Sub-Grid Touches
grid_unit = 100.0

results = []

for sl in [8.0, 10.0, 12.5, 15.0, 17.5, 20.0, 25.0]:
    tp = sl * 2.0  # Strict 1:2.0 R:R
    
    wins = 0
    losses = 0
    
    # Evaluate sub-grid touches
    # When price touches xx20 or xx80 in morning window
    closes = sub['close'].values
    highs = sub['high'].values
    lows = sub['low'].values
    n = len(sub)
    
    last_trade_bar = -10
    
    for i in range(1, n - 60):
        if i - last_trade_bar < 5:
            continue
            
        c0 = closes[i]
        base = np.floor(c0 / grid_unit) * grid_unit
        lvl20 = base + 20.0
        lvl80 = base + 80.0
        
        # Bullish touch at xx20
        if lows[i] <= lvl20 <= highs[i] and c0 >= lvl20:
            entry = lvl20
            stop_price = entry - sl
            target_price = entry + tp
            
            # Forward simulate up to 60 bars (1 hour)
            outcome = None
            for f in range(1, 60):
                curr_h = highs[i + f]
                curr_l = lows[i + f]
                
                # Check stop first (conservative)
                if curr_l <= stop_price:
                    outcome = "loss"
                    break
                elif curr_h >= target_price:
                    outcome = "win"
                    break
                    
            if outcome == "win":
                wins += 1
                last_trade_bar = i
            elif outcome == "loss":
                losses += 1
                last_trade_bar = i
                
        # Bearish touch at xx80
        elif lows[i] <= lvl80 <= highs[i] and c0 <= lvl80:
            entry = lvl80
            stop_price = entry + sl
            target_price = entry - tp
            
            outcome = None
            for f in range(1, 60):
                curr_h = highs[i + f]
                curr_l = lows[i + f]
                
                if curr_h >= stop_price:
                    outcome = "loss"
                    break
                elif curr_l <= target_price:
                    outcome = "win"
                    break
                    
            if outcome == "win":
                wins += 1
                last_trade_bar = i
            elif outcome == "loss":
                losses += 1
                last_trade_bar = i
                
    total = wins + losses
    if total > 0:
        wr = (wins / total) * 100
        gp = wins * tp * 20.0
        gl = losses * sl * 20.0
        net = gp - gl
        pf = gp / gl if gl > 0 else np.nan
        results.append({
            "sl": sl, "tp": tp, "trades": total, "wr": wr, "gp": gp, "gl": gl, "net": net, "pf": pf
        })

print("=" * 95)
print("STOP SIZE SWEEP ON 2024-2026 NQ (1:2.0 REWARD-TO-RISK)")
print("=" * 95)
print(f"{'STOP (PTS)':<11} | {'TARGET (PTS)':<13} | {'TRADES':<8} | {'WIN RATE':<9} | {'NET PnL ($)':<13} | {'PROFIT FACTOR':<13} | {'VERDICT'}")
print("-" * 95)
for r in results:
    v = "🔥 BEST EDGE" if r['pf'] >= 1.4 else ("✅ PROFITABLE" if r['pf'] >= 1.1 else "❌ TOO TIGHT (NOISE)")
    print(f"{r['sl']:>9.1f} pt | {r['tp']:>11.1f} pt | {r['trades']:>8,d} | {r['wr']:>8.1f}% | ${r['net']:>11,.2f} | {r['pf']:>13.3f} | {v}")
print("=" * 95)
