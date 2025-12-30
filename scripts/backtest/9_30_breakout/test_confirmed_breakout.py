"""
Confirmed Breakout Entry Test
=============================
Only enter trade when price closes X% ABOVE Range High (Long)
or X% BELOW Range Low (Short).

This filters out weak/fake breakouts.
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import time

TICKER = 'NQ1'
YEARS = 10

print("=== CONFIRMED BREAKOUT ENTRY TEST ===")
print("Entry only after price closes X% beyond Range High/Low")

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

for confirm_pct in [0.0, 0.03, 0.05, 0.07, 0.10]:
    for exit_time in [time(10, 0), time(11, 0)]:
        
        end_date = or_df.index.max()
        start_date = end_date - pd.Timedelta(days=YEARS*365)
        or_filtered = or_df[or_df.index >= start_date]
        
        trades = []
        for d, row in or_filtered.iterrows():
            day_str = d.date()
            r_high, r_low, r_open = row['high'], row['low'], row['open']
            r_pct = row.get('range_pct', (r_high-r_low)/r_open)
            
            # Filters (V7)
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
            
            # Calculate confirmation levels
            confirm_long = r_high * (1 + confirm_pct/100)  # Long: price must close above this
            confirm_short = r_low * (1 - confirm_pct/100)  # Short: price must close below this
            
            pos, entry_px = 0, 0
            sl_px = 0
            
            for i, (t, bar) in enumerate(mkt.iterrows()):
                if pos == 0:
                    # CONFIRMED BREAKOUT ENTRY
                    if bar['close'] > confirm_long:
                        pos, entry_px = 1, bar['close']
                        sl_px = r_low  # SL at Range Low
                    elif bar['close'] < confirm_short:
                        pos, entry_px = -1, bar['close']
                        sl_px = r_high  # SL at Range High
                
                if pos != 0:
                    # Check SL
                    if (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px):
                        pnl = (sl_px - entry_px)/entry_px*100 if pos == 1 else (entry_px - sl_px)/entry_px*100
                        trades.append({'PnL_Pct': pnl, 'Exit': 'SL'})
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
            sl_exits = len(df_t[df_t['Exit']=='SL'])
            time_exits = len(df_t[df_t['Exit']=='TIME'])
            
            results.append({
                'Confirm': f"{confirm_pct:.2f}%",
                'Exit': f"{exit_time.hour}:{exit_time.minute:02d}",
                'Trades': len(df_t),
                'WinRate': wr,
                'PnL': gross,
                'PF': pf,
                'SL_Exits': sl_exits,
                'TIME_Exits': time_exits,
            })

# Display results
print("\n" + "="*80)
print("CONFIRMED BREAKOUT RESULTS")
print("="*80)
df_results = pd.DataFrame(results)
df_results = df_results.sort_values('PnL', ascending=False)
df_results['WinRate'] = df_results['WinRate'].apply(lambda x: f"{x:.1%}")
df_results['PnL'] = df_results['PnL'].apply(lambda x: f"{x:+.2f}%")
df_results['PF'] = df_results['PF'].apply(lambda x: f"{x:.2f}")
print(df_results.to_string(index=False))

print("\n=== TOP 3 CONFIGURATIONS ===")
for i, row in df_results.head(3).iterrows():
    print(f"  Confirm {row['Confirm']}, Exit {row['Exit']}: {row['Trades']} trades, WR={row['WinRate']}, PnL={row['PnL']}, PF={row['PF']}")

# Compare to baseline (0% confirmation)
print("\n=== IMPACT OF CONFIRMATION FILTER ===")
baseline = df_results[df_results['Confirm'] == '0.00%']
for confirm in ['0.03%', '0.05%', '0.07%', '0.10%']:
    filtered = df_results[df_results['Confirm'] == confirm]
    if not filtered.empty and not baseline.empty:
        b_trades = baseline.iloc[0]['Trades']
        f_trades = filtered.iloc[0]['Trades']
        trades_lost = b_trades - f_trades
        print(f"  {confirm} confirmation: -{trades_lost} trades ({trades_lost/b_trades*100:.1f}% filtered out)")

df_results.to_csv('scripts/backtest/9_30_breakout/results/confirmed_breakout_test.csv', index=False)
print("\nSaved: confirmed_breakout_test.csv")
