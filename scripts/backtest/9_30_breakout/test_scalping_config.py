"""
Scalping Configuration Test
============================
- Hard exit at 09:44/09:45
- TP target based on MAE/MFE median
- Cashflow-focused (quick in/out)
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import time

print("=== MAE/MFE ANALYSIS FOR SCALPING ===")
df = pd.read_csv('scripts/backtest/9_30_breakout/results/v6_backtest_details.csv')

print("\nMAE (Max Adverse Excursion):")
print(f"  Mean:   {df['MAE_Pct'].mean():.4f}%")
print(f"  Median: {df['MAE_Pct'].median():.4f}%")
print(f"  25th:   {df['MAE_Pct'].quantile(0.25):.4f}%")
print(f"  75th:   {df['MAE_Pct'].quantile(0.75):.4f}%")

print("\nMFE (Max Favorable Excursion):")
print(f"  Mean:   {df['MFE_Pct'].mean():.4f}%")
print(f"  Median: {df['MFE_Pct'].median():.4f}%")
print(f"  25th:   {df['MFE_Pct'].quantile(0.25):.4f}%")
print(f"  75th:   {df['MFE_Pct'].quantile(0.75):.4f}%")

print("\nSuggested Scalping Targets (based on median):")
print(f"  TP Target: {df['MFE_Pct'].median():.4f}% (50% hit rate)")
print(f"  SL Cap:    {df['MAE_Pct'].median():.4f}%")

print("\nHit Rate Analysis:")
for tp in [0.03, 0.05, 0.07, 0.08, 0.10, 0.12, 0.15]:
    hit = (df['MFE_Pct'] >= tp).mean()
    print(f"  TP {tp:.2f}%: {hit:.1%} would hit target")

# ======================
# SCALPING BACKTEST
# ======================
print("\n" + "="*60)
print("SCALPING BACKTEST: 09:45 Exit + TP Target")
print("="*60)

TICKER = 'NQ1'
YEARS = 10

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

vvix = None
if os.path.exists('data/VVIX_1d.parquet'):
    vvix_raw = pd.read_parquet('data/VVIX_1d.parquet')
    if 'time' in vvix_raw.columns:
        vvix_raw['date'] = pd.to_datetime(vvix_raw['time'], unit='s').dt.date
        vvix = vvix_raw.set_index('date')
    elif isinstance(vvix_raw.index, pd.DatetimeIndex):
        vvix_raw['date'] = vvix_raw.index.date
        vvix = vvix_raw.set_index('date')

# Test multiple TP/Exit combinations
results = []

for exit_time in [time(9, 44), time(9, 45)]:
    for tp_pct in [0.05, 0.07, 0.08, 0.10]:
        for sl_pct in [0.08, 0.10, 0.12]:
            
            config = {
                'USE_VVIX': True, 'USE_TUESDAY': True, 'USE_WEDNESDAY': True,
                'MAX_RANGE_PCT': 0.25, 'HARD_EXIT': exit_time,
                'TP_PCT': tp_pct, 'SL_PCT': sl_pct,
            }
            
            end_date = or_df.index.max()
            start_date = end_date - pd.Timedelta(days=YEARS*365)
            or_filtered = or_df[or_df.index >= start_date]
            
            trades = []
            for d, row in or_filtered.iterrows():
                day_str = d.date()
                r_high, r_low, r_open = row['high'], row['low'], row['open']
                r_pct = row.get('range_pct', (r_high-r_low)/r_open)
                
                if config['USE_TUESDAY'] and d.dayofweek == 1: continue
                if config['USE_WEDNESDAY'] and d.dayofweek == 2: continue
                if r_pct > config['MAX_RANGE_PCT']: continue
                
                if config['USE_VVIX'] and vvix is not None:
                    try:
                        vv = vvix.loc[day_str]['open']
                        if isinstance(vv, pd.Series): vv = vv.iloc[0]
                        if vv > 115: continue
                    except: pass
                
                d_loc = pd.Timestamp(d).tz_localize('US/Eastern')
                t_start = d_loc + pd.Timedelta(hours=9, minutes=31)
                t_end = d_loc + pd.Timedelta(hours=config['HARD_EXIT'].hour, minutes=config['HARD_EXIT'].minute)
                
                mkt = df_price.loc[t_start:t_end]
                if len(mkt) < 2: continue
                
                # IMMEDIATE entry with TP/SL
                pos, entry_px = 0, 0
                for i, (t, bar) in enumerate(mkt.iterrows()):
                    if pos == 0:
                        if bar['close'] > r_high:
                            pos, entry_px = 1, bar['close']
                        elif bar['close'] < r_low:
                            pos, entry_px = -1, bar['close']
                    
                    if pos != 0:
                        # Calculate TP/SL prices
                        tp_px = entry_px * (1 + config['TP_PCT']/100) if pos == 1 else entry_px * (1 - config['TP_PCT']/100)
                        sl_px = entry_px * (1 - config['SL_PCT']/100) if pos == 1 else entry_px * (1 + config['SL_PCT']/100)
                        
                        # Check TP
                        if (pos == 1 and bar['high'] >= tp_px) or (pos == -1 and bar['low'] <= tp_px):
                            trades.append({'PnL_Pct': config['TP_PCT'], 'Exit': 'TP'})
                            break
                        
                        # Check SL
                        if (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px):
                            trades.append({'PnL_Pct': -config['SL_PCT'], 'Exit': 'SL'})
                            break
                        
                        # Time exit
                        if i == len(mkt) - 1:
                            pnl = (bar['close'] - entry_px)/entry_px*100 if pos == 1 else (entry_px - bar['close'])/entry_px*100
                            trades.append({'PnL_Pct': pnl, 'Exit': 'TIME'})
            
            if trades:
                df_t = pd.DataFrame(trades)
                wr = (df_t['PnL_Pct'] > 0).mean()
                gross = df_t['PnL_Pct'].sum()
                gp = df_t[df_t['PnL_Pct']>0]['PnL_Pct'].sum()
                gl = abs(df_t[df_t['PnL_Pct']<0]['PnL_Pct'].sum())
                pf = gp/gl if gl > 0 else 0
                
                results.append({
                    'Exit': f"{exit_time.hour}:{exit_time.minute:02d}",
                    'TP': f"{tp_pct:.2f}%",
                    'SL': f"{sl_pct:.2f}%",
                    'Trades': len(df_t),
                    'WinRate': f"{wr:.1%}",
                    'PnL': f"{gross:.2f}%",
                    'PF': f"{pf:.2f}",
                    'TP_Hits': len(df_t[df_t['Exit']=='TP']),
                    'SL_Hits': len(df_t[df_t['Exit']=='SL']),
                })

# Display results
print("\nScalping Strategy Grid Search Results:")
print("-" * 90)
df_results = pd.DataFrame(results)
df_results = df_results.sort_values('PnL', ascending=False)
print(df_results.to_string(index=False))

# Save best result
best = df_results.iloc[0]
print(f"\n=== BEST SCALPING CONFIG ===")
print(f"Exit: {best['Exit']}, TP: {best['TP']}, SL: {best['SL']}")
print(f"Trades: {best['Trades']}, Win Rate: {best['WinRate']}, PnL: {best['PnL']}, PF: {best['PF']}")

df_results.to_csv('scripts/backtest/9_30_breakout/results/scalping_grid_search.csv', index=False)
print("\nSaved: scalping_grid_search.csv")
