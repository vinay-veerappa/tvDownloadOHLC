"""
Breakeven Trail Test
====================
After hitting TP1 (Cover the Queen), move SL to breakeven.
This protects the remaining position from turning into a loss.
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import time

TICKER = 'NQ1'
YEARS = 10

print("=== BREAKEVEN TRAIL TEST ===")
print("After TP1 hit, move SL to breakeven (entry price)")

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

# Test configs
results = []

for confirm_pct in [0.05, 0.10]:
    for tp1_pct in [0.05, 0.07, 0.10]:
        for use_be_trail in [False, True]:
            
            end_date = or_df.index.max()
            start_date = end_date - pd.Timedelta(days=YEARS*365)
            or_filtered = or_df[or_df.index >= start_date]
            
            trades = []
            for d, row in or_filtered.iterrows():
                day_str = d.date()
                r_high, r_low, r_open = row['high'], row['low'], row['open']
                r_pct = row.get('range_pct', (r_high-r_low)/r_open)
                
                # Filters
                if d.dayofweek == 1: continue  # Tuesday
                if d.dayofweek == 2: continue  # Wednesday
                if r_pct > 0.25: continue
                
                if vvix is not None:
                    try:
                        vv = vvix.loc[day_str]['open']
                        if isinstance(vv, pd.Series): vv = vv.iloc[0]
                        if vv > 115: continue
                    except: pass
                
                d_loc = pd.Timestamp(d).tz_localize('US/Eastern')
                t_start = d_loc + pd.Timedelta(hours=9, minutes=31)
                t_end = d_loc + pd.Timedelta(hours=11, minutes=0)  # 11:00 exit
                
                mkt = df_price.loc[t_start:t_end]
                if len(mkt) < 2: continue
                
                # Confirmation levels
                confirm_long = r_high * (1 + confirm_pct/100)
                confirm_short = r_low * (1 - confirm_pct/100)
                
                pos, entry_px = 0, 0
                sl_px = 0
                tp1_hit = False
                realized_pnl = 0.0
                
                for i, (t, bar) in enumerate(mkt.iterrows()):
                    if pos == 0:
                        # Confirmed entry
                        if bar['close'] > confirm_long:
                            pos, entry_px = 1, bar['close']
                            sl_px = r_low
                        elif bar['close'] < confirm_short:
                            pos, entry_px = -1, bar['close']
                            sl_px = r_high
                    
                    if pos != 0:
                        # TP1 level
                        tp1_px = entry_px * (1 + tp1_pct/100) if pos == 1 else entry_px * (1 - tp1_pct/100)
                        
                        # Check TP1 (50%)
                        if not tp1_hit:
                            if (pos == 1 and bar['high'] >= tp1_px) or (pos == -1 and bar['low'] <= tp1_px):
                                realized_pnl += tp1_pct * 0.50  # 50% at TP1
                                tp1_hit = True
                                # Move SL to breakeven if enabled
                                if use_be_trail:
                                    sl_px = entry_px
                        
                        # Check SL on remaining
                        if (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px):
                            if tp1_hit:
                                # Already took TP1
                                if use_be_trail:
                                    # SL is at breakeven, so PnL on remaining = 0
                                    realized_pnl += 0  # breakeven on remaining 50%
                                else:
                                    # SL still at Range
                                    sl_loss = abs(entry_px - sl_px) / entry_px * 100
                                    realized_pnl -= sl_loss * 0.50
                            else:
                                # Full SL before TP1
                                sl_loss = abs(entry_px - sl_px) / entry_px * 100
                                realized_pnl = -sl_loss
                            trades.append({'PnL_Pct': realized_pnl, 'Exit': 'SL', 'TP1_Hit': tp1_hit})
                            break
                        
                        # Time exit
                        if i == len(mkt) - 1:
                            time_pnl = (bar['close'] - entry_px)/entry_px*100 if pos == 1 else (entry_px - bar['close'])/entry_px*100
                            if tp1_hit:
                                realized_pnl += time_pnl * 0.50  # Time exit on remaining
                            else:
                                realized_pnl = time_pnl
                            trades.append({'PnL_Pct': realized_pnl, 'Exit': 'TIME', 'TP1_Hit': tp1_hit})
            
            if trades:
                df_t = pd.DataFrame(trades)
                wr = (df_t['PnL_Pct'] > 0).mean()
                gross = df_t['PnL_Pct'].sum()
                gp = df_t[df_t['PnL_Pct']>0]['PnL_Pct'].sum()
                gl = abs(df_t[df_t['PnL_Pct']<0]['PnL_Pct'].sum())
                pf = gp/gl if gl > 0 else 0
                tp1_hits = df_t['TP1_Hit'].sum()
                
                results.append({
                    'Confirm': f"{confirm_pct:.2f}%",
                    'TP1': f"{tp1_pct:.2f}%",
                    'BE_Trail': 'YES' if use_be_trail else 'NO',
                    'Trades': len(df_t),
                    'WinRate': wr,
                    'PnL': gross,
                    'PF': pf,
                    'TP1_Hits': tp1_hits,
                })

# Display results
print("\n" + "="*90)
print("BREAKEVEN TRAIL RESULTS")
print("="*90)
df_results = pd.DataFrame(results)
df_results = df_results.sort_values('PnL', ascending=False)
df_results['WinRate'] = df_results['WinRate'].apply(lambda x: f"{x:.1%}")
df_results['PnL'] = df_results['PnL'].apply(lambda x: f"{x:+.2f}%")
df_results['PF'] = df_results['PF'].apply(lambda x: f"{x:.2f}")
print(df_results.to_string(index=False))

print("\n=== BE TRAIL VS NO TRAIL COMPARISON ===")
for confirm in ['0.05%', '0.10%']:
    for tp1 in ['0.05%', '0.07%', '0.10%']:
        no_trail = df_results[(df_results['Confirm']==confirm) & (df_results['TP1']==tp1) & (df_results['BE_Trail']=='NO')]
        with_trail = df_results[(df_results['Confirm']==confirm) & (df_results['TP1']==tp1) & (df_results['BE_Trail']=='YES')]
        if not no_trail.empty and not with_trail.empty:
            print(f"  Confirm {confirm}, TP1 {tp1}: NO={no_trail.iloc[0]['PnL']}, YES={with_trail.iloc[0]['PnL']}")

df_results.to_csv('scripts/backtest/9_30_breakout/results/be_trail_test.csv', index=False)
print("\nSaved: be_trail_test.csv")
