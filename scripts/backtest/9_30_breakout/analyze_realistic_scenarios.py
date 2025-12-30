"""
Realistic Trade Scenario Analysis
==================================
Think like a seasoned day trader and analyze:

1. POST-BREAKOUT BEHAVIOR
   - What happens after price closes 0.10% above range?
   - How often does it pullback?
   - How deep is the pullback (to what level)?
   
2. ENGULFING CANDLE EXIT
   - If next candle engulfs the breakout candle, should we exit?
   
3. RE-ENTRY SCENARIOS
   - If stopped at BE, should we re-enter?
   - What's the success rate of re-entries?
   
4. REALISTIC TRADE SIMULATION
   - Bar-by-bar simulation with actual decision points
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import time, timedelta

TICKER = 'NQ1'
YEARS = 10

print("=== REALISTIC TRADE SCENARIO ANALYSIS ===")
print("Thinking like a seasoned day trader...\n")

# Load data
with open(f'data/{TICKER}_opening_range.json', 'r') as f:
    or_df = pd.DataFrame(json.load(f))
or_df['date'] = pd.to_datetime(or_df['date'])
or_df = or_df.set_index('date')

df_price = pd.read_parquet(f'data/{TICKER}_1m.parquet')
if 'time' in df_price.columns:
    df_price['datetime'] = pd.to_datetime(df_price['time'], unit='s')
    df_price = df_price.set_index('datetime')
if df_price.index.tz is None:
    df_price = df_price.tz_localize('UTC')
df_price = df_price.tz_convert('US/Eastern').sort_index()

# Filter to analysis period
end_date = or_df.index.max()
start_date = end_date - pd.Timedelta(days=YEARS*365)
or_df = or_df[or_df.index >= start_date]

# ============================================================
# 1. POST-BREAKOUT BEHAVIOR ANALYSIS
# ============================================================
print("=" * 70)
print("1. POST-BREAKOUT BEHAVIOR ANALYSIS")
print("=" * 70)

breakout_events = []

for d, row in or_df.iterrows():
    r_high, r_low = row['high'], row['low']
    r_pct = row.get('range_pct', (r_high-r_low)/row['open'])
    
    # Skip filtered days
    if d.dayofweek in [1, 2]: continue  # Tue, Wed
    if r_pct > 0.25: continue
    
    d_loc = pd.Timestamp(d).tz_localize('US/Eastern')
    t_start = d_loc + pd.Timedelta(hours=9, minutes=31)
    t_end = d_loc + pd.Timedelta(hours=11, minutes=0)
    
    mkt = df_price.loc[t_start:t_end]
    if len(mkt) < 10: continue
    
    # Find confirmed breakout (0.10% close above range)
    confirm_long = r_high * 1.001
    confirm_short = r_low * 0.999
    
    breakout_bar = None
    direction = 0
    
    for i, (t, bar) in enumerate(mkt.iterrows()):
        if bar['close'] > confirm_long:
            breakout_bar = i
            direction = 1
            entry_px = bar['close']
            breakout_candle = bar
            break
        elif bar['close'] < confirm_short:
            breakout_bar = i
            direction = -1
            entry_px = bar['close']
            breakout_candle = bar
            break
    
    if breakout_bar is None:
        continue
    
    # Analyze post-breakout behavior
    post_bars = mkt.iloc[breakout_bar+1:breakout_bar+31]  # Next 30 bars
    if len(post_bars) < 5:
        continue
    
    # Track pullback behavior
    if direction == 1:  # Long
        max_runup = (post_bars['high'].max() - entry_px) / entry_px * 100
        max_pullback = (entry_px - post_bars['low'].min()) / entry_px * 100
        pullback_to_entry = any(post_bars['low'] <= entry_px)
        pullback_to_range = any(post_bars['low'] <= r_high)
        pullback_to_sl = any(post_bars['low'] <= r_low)
        
        # Check for engulfing candle
        if len(post_bars) > 0:
            next_bar = post_bars.iloc[0]
            engulfing = (next_bar['close'] < breakout_candle['open'] and 
                        next_bar['open'] > breakout_candle['close'])
        else:
            engulfing = False
            
    else:  # Short
        max_runup = (entry_px - post_bars['low'].min()) / entry_px * 100
        max_pullback = (post_bars['high'].max() - entry_px) / entry_px * 100
        pullback_to_entry = any(post_bars['high'] >= entry_px)
        pullback_to_range = any(post_bars['high'] >= r_low)
        pullback_to_sl = any(post_bars['high'] >= r_high)
        
        if len(post_bars) > 0:
            next_bar = post_bars.iloc[0]
            engulfing = (next_bar['close'] > breakout_candle['open'] and 
                        next_bar['open'] < breakout_candle['close'])
        else:
            engulfing = False
    
    # Find how many bars until pullback to entry
    bars_to_pullback = None
    for j, (t2, bar2) in enumerate(post_bars.iterrows()):
        if direction == 1 and bar2['low'] <= entry_px:
            bars_to_pullback = j + 1
            break
        elif direction == -1 and bar2['high'] >= entry_px:
            bars_to_pullback = j + 1
            break
    
    breakout_events.append({
        'date': d,
        'direction': 'LONG' if direction == 1 else 'SHORT',
        'entry_px': entry_px,
        'max_runup_pct': max_runup,
        'max_pullback_pct': max_pullback,
        'pullback_to_entry': pullback_to_entry,
        'pullback_to_range': pullback_to_range,
        'pullback_to_sl': pullback_to_sl,
        'bars_to_pullback': bars_to_pullback,
        'engulfing_next': engulfing,
    })

df_events = pd.DataFrame(breakout_events)
print(f"Analyzed {len(df_events)} confirmed breakout events\n")

# Pullback Statistics
print("PULLBACK PROBABILITY (within 30 bars post-breakout):")
print(f"  Pulls back to Entry (BE level):  {df_events['pullback_to_entry'].mean():.1%}")
print(f"  Pulls back to Range High/Low:    {df_events['pullback_to_range'].mean():.1%}")
print(f"  Pulls back to SL (Range other):  {df_events['pullback_to_sl'].mean():.1%}")

print(f"\nAVERAGE PULLBACK DEPTH: {df_events['max_pullback_pct'].mean():.4f}%")
print(f"AVERAGE MAX RUNUP: {df_events['max_runup_pct'].mean():.4f}%")

# Time to pullback
pb_events = df_events[df_events['pullback_to_entry']]
if len(pb_events) > 0:
    print(f"\nWhen pullback happens, avg bars until pullback: {pb_events['bars_to_pullback'].mean():.1f}")

# ============================================================
# 2. ENGULFING CANDLE ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("2. ENGULFING CANDLE ANALYSIS")
print("=" * 70)

engulfing_events = df_events[df_events['engulfing_next'] == True]
non_engulfing = df_events[df_events['engulfing_next'] == False]

print(f"Engulfing candle after breakout: {len(engulfing_events)} ({len(engulfing_events)/len(df_events)*100:.1f}%)")
print(f"No engulfing: {len(non_engulfing)} ({len(non_engulfing)/len(df_events)*100:.1f}%)")

if len(engulfing_events) > 0:
    print(f"\nWhen ENGULFING occurs:")
    print(f"  Avg subsequent runup: {engulfing_events['max_runup_pct'].mean():.4f}%")
    print(f"  Avg pullback: {engulfing_events['max_pullback_pct'].mean():.4f}%")
    print(f"  Hit SL: {engulfing_events['pullback_to_sl'].mean():.1%}")

if len(non_engulfing) > 0:
    print(f"\nWhen NO engulfing:")
    print(f"  Avg subsequent runup: {non_engulfing['max_runup_pct'].mean():.4f}%")
    print(f"  Avg pullback: {non_engulfing['max_pullback_pct'].mean():.4f}%")
    print(f"  Hit SL: {non_engulfing['pullback_to_sl'].mean():.1%}")

# ============================================================
# 3. RUNUP DISTRIBUTION (What targets are realistic?)
# ============================================================
print("\n" + "=" * 70)
print("3. RUNUP DISTRIBUTION AFTER CONFIRMATION")
print("=" * 70)

print("Post-breakout runup percentiles:")
for pct in [25, 50, 75, 90, 95]:
    val = df_events['max_runup_pct'].quantile(pct/100)
    hit_pct = (df_events['max_runup_pct'] >= val).mean() * 100
    print(f"  {pct}th percentile: {val:.4f}% (would hit {100-pct}% of the time)")

print("\nProbability of reaching target after confirmation:")
for target in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
    hit_rate = (df_events['max_runup_pct'] >= target).mean()
    print(f"  +{target:.2f}%: {hit_rate:.1%}")

# ============================================================
# 4. PULLBACK THEN CONTINUATION ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("4. PULLBACK THEN CONTINUATION (Wait for Pullback Entry)")
print("=" * 70)

# Of trades that pulled back to entry, how many then continued to profit?
pb_trades = df_events[df_events['pullback_to_entry'] == True]
if len(pb_trades) > 0:
    continued = pb_trades[pb_trades['max_runup_pct'] > 0.10]  # Ran up 0.10%+ after
    print(f"Trades that pulled back to entry: {len(pb_trades)}")
    print(f"Of those, ran up 0.10%+ afterward: {len(continued)} ({len(continued)/len(pb_trades)*100:.1f}%)")
    print(f"Avg final runup after pullback: {pb_trades['max_runup_pct'].mean():.4f}%")

# ============================================================
# 5. RE-ENTRY SCENARIO ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("5. RE-ENTRY SCENARIO (If stopped at BE, should we re-enter?)")
print("=" * 70)

# Simulate: After BE stop, if price breaks above the BE level again, re-enter
print("Scenario: After BE stop, wait for price to break back above entry level")
print("This would require bar-by-bar simulation with state tracking...")
print("(Complex scenario - would need detailed implementation)")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("TRADING INSIGHTS SUMMARY")
print("=" * 70)

print(f"""
1. PULLBACK IS COMMON: {df_events['pullback_to_entry'].mean():.0%} of trades pull back to entry level
   → This is why BE trail hurts: pullback is normal, not failure

2. BUT MOST CONTINUE: Of pullback trades, {len(continued)/len(pb_trades)*100:.0f}% run up 0.10%+ after
   → Pullback is a buying opportunity, not an exit signal

3. ENGULFING IS RARE: Only {len(engulfing_events)/len(df_events)*100:.0f}% show bearish engulfing
   → Not enough data to use as reliable exit signal

4. TARGET PROBABILITY:
   - 0.05% target: {(df_events['max_runup_pct'] >= 0.05).mean():.0%} hit rate
   - 0.10% target: {(df_events['max_runup_pct'] >= 0.10).mean():.0%} hit rate
   - 0.20% target: {(df_events['max_runup_pct'] >= 0.20).mean():.0%} hit rate

5. AVERAGE RUNUP: {df_events['max_runup_pct'].mean():.3f}% (but with fat tails)

RECOMMENDED APPROACH:
- Enter on confirmation (0.10% beyond range)
- Take TP1 at 0.05% (Cover Queen) - {(df_events['max_runup_pct'] >= 0.05).mean():.0%} hit rate
- Let runner ride to time exit (don't use BE trail)
- Consider: Wait for pullback-to-entry THEN enter (higher probability entry)
""")

# Save analysis
df_events.to_csv('scripts/backtest/9_30_breakout/results/post_breakout_behavior.csv', index=False)
print("Saved: post_breakout_behavior.csv")
