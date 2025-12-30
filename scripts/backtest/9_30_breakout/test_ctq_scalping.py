"""
Scalping with Cover the Queen (CQT) Logic
==========================================
- SL = Range High/Low (opposite of entry direction)
- TP1 = Take 50% off at first target (Cover the Queen)
- TP2 = Let remaining 50% run to second target or time exit
- Hard exit at 09:45
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import time

TICKER = 'NQ1'
YEARS = 10

print("=== COVER THE QUEEN SCALPING TEST ===")
print("SL = Range High/Low (structure-based)")
print("TP1 = Cover 50%, TP2 = Runner")

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

# Test grid
results = []

for exit_time in [time(9, 45), time(10, 0), time(10, 30), time(11, 0)]:
    for tp1_pct in [0.05, 0.07, 0.10]:
        for tp2_pct in [0.15, 0.20, 0.25]:
            
            end_date = or_df.index.max()
            start_date = end_date - pd.Timedelta(days=YEARS*365)
            or_filtered = or_df[or_df.index >= start_date]
            
            trades = []
            for d, row in or_filtered.iterrows():
                day_str = d.date()
                r_high, r_low, r_open = row['high'], row['low'], row['open']
                r_pct = row.get('range_pct', (r_high-r_low)/r_open)
                r_size = r_high - r_low
                
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
                t_end = d_loc + pd.Timedelta(hours=exit_time.hour, minutes=exit_time.minute)
                
                mkt = df_price.loc[t_start:t_end]
                if len(mkt) < 2: continue
                
                # Trade execution with Cover the Queen
                pos, entry_px = 0, 0
                tp1_hit = False
                realized_pnl = 0.0
                
                for i, (t, bar) in enumerate(mkt.iterrows()):
                    if pos == 0:
                        if bar['close'] > r_high:
                            pos, entry_px = 1, bar['close']
                            sl_px = r_low  # SL at Range Low for Long
                        elif bar['close'] < r_low:
                            pos, entry_px = -1, bar['close']
                            sl_px = r_high  # SL at Range High for Short
                    
                    if pos != 0:
                        # Calculate TP prices based on entry
                        tp1_px = entry_px * (1 + tp1_pct/100) if pos == 1 else entry_px * (1 - tp1_pct/100)
                        tp2_px = entry_px * (1 + tp2_pct/100) if pos == 1 else entry_px * (1 - tp2_pct/100)
                        
                        # Check TP1 (Cover the Queen - 50%)
                        if not tp1_hit:
                            if (pos == 1 and bar['high'] >= tp1_px) or (pos == -1 and bar['low'] <= tp1_px):
                                realized_pnl += tp1_pct * 0.50  # 50% at TP1
                                tp1_hit = True
                        
                        # If TP1 hit, check TP2 for remaining 50%
                        if tp1_hit:
                            if (pos == 1 and bar['high'] >= tp2_px) or (pos == -1 and bar['low'] <= tp2_px):
                                realized_pnl += tp2_pct * 0.50  # Remaining 50% at TP2
                                trades.append({'PnL_Pct': realized_pnl, 'Exit': 'TP2'})
                                break
                        
                        # Check SL (on remaining position)
                        if (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px):
                            # Calculate SL % based on range
                            sl_pct = abs(entry_px - sl_px) / entry_px * 100
                            if tp1_hit:
                                realized_pnl -= sl_pct * 0.50  # SL on remaining 50%
                            else:
                                realized_pnl -= sl_pct  # Full SL
                            trades.append({'PnL_Pct': realized_pnl, 'Exit': 'SL'})
                            break
                        
                        # Time exit
                        if i == len(mkt) - 1:
                            exit_px = bar['close']
                            time_pnl = (exit_px - entry_px)/entry_px*100 if pos == 1 else (entry_px - exit_px)/entry_px*100
                            if tp1_hit:
                                realized_pnl += time_pnl * 0.50  # Time exit on remaining 50%
                            else:
                                realized_pnl = time_pnl  # Full time exit
                            trades.append({'PnL_Pct': realized_pnl, 'Exit': 'TIME'})
            
            if trades:
                df_t = pd.DataFrame(trades)
                wr = (df_t['PnL_Pct'] > 0).mean()
                gross = df_t['PnL_Pct'].sum()
                gp = df_t[df_t['PnL_Pct']>0]['PnL_Pct'].sum()
                gl = abs(df_t[df_t['PnL_Pct']<0]['PnL_Pct'].sum())
                pf = gp/gl if gl > 0 else 0
                
                results.append({
                    'Exit': f"{exit_time.hour}:{exit_time.minute:02d}",
                    'TP1': f"{tp1_pct:.2f}%",
                    'TP2': f"{tp2_pct:.2f}%",
                    'Trades': len(df_t),
                    'WinRate': wr,
                    'PnL': gross,
                    'PF': pf,
                    'TP2_Exits': len(df_t[df_t['Exit']=='TP2']),
                    'SL_Exits': len(df_t[df_t['Exit']=='SL']),
                    'TIME_Exits': len(df_t[df_t['Exit']=='TIME']),
                })

# Display results
print("\n" + "="*100)
print("COVER THE QUEEN GRID SEARCH RESULTS")
print("="*100)
df_results = pd.DataFrame(results)
df_results = df_results.sort_values('PnL', ascending=False)
df_results['WinRate'] = df_results['WinRate'].apply(lambda x: f"{x:.1%}")
df_results['PnL'] = df_results['PnL'].apply(lambda x: f"{x:.2f}%")
df_results['PF'] = df_results['PF'].apply(lambda x: f"{x:.2f}")
print(df_results.head(20).to_string(index=False))

# Best config
print("\n=== TOP 5 CONFIGURATIONS ===")
for i, row in df_results.head(5).iterrows():
    print(f"  Exit {row['Exit']}, TP1 {row['TP1']}, TP2 {row['TP2']}: PnL={row['PnL']}, WR={row['WinRate']}, PF={row['PF']}")

df_results.to_csv('scripts/backtest/9_30_breakout/results/ctq_scalping_grid.csv', index=False)
print("\nSaved: ctq_scalping_grid.csv")
