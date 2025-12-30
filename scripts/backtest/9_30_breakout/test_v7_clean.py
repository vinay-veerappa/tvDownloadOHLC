"""V7 Clean Test (No Multi-TP) - Final Comparison"""
import pandas as pd
import numpy as np
import json
import os
from datetime import time

TICKER = 'NQ1'
YEARS = 10

# Load data
with open(f'data/{TICKER}_opening_range.json', 'r') as f:
    or_df = pd.DataFrame(json.load(f))
or_df['date'] = pd.to_datetime(or_df['date'])
or_df = or_df.set_index('date')

df = pd.read_parquet(f'data/{TICKER}_1m.parquet')
if 'time' in df.columns:
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('datetime')
if df.index.tz is None:
    df = df.tz_localize('UTC')
df = df.tz_convert('US/Eastern').sort_index()

vvix = None
if os.path.exists('data/VVIX_1d.parquet'):
    vvix_raw = pd.read_parquet('data/VVIX_1d.parquet')
    if 'time' in vvix_raw.columns:
        vvix_raw['date'] = pd.to_datetime(vvix_raw['time'], unit='s').dt.date
        vvix = vvix_raw.set_index('date')
    elif isinstance(vvix_raw.index, pd.DatetimeIndex):
        vvix_raw['date'] = vvix_raw.index.date
        vvix = vvix_raw.set_index('date')
    else:
        vvix = vvix_raw  # Use as-is

# V7 Config
config = {
    'USE_VVIX': True, 'USE_TUESDAY': True, 'USE_WEDNESDAY': True,
    'MAX_RANGE_PCT': 0.25, 'MAX_SL_PCT': 0.25, 'HARD_EXIT': time(11, 0),
}

end_date = or_df.index.max()
start_date = end_date - pd.Timedelta(days=YEARS*365)
or_df = or_df[or_df.index >= start_date]

trades = []
for d, row in or_df.iterrows():
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
    
    mkt = df.loc[t_start:t_end]
    if len(mkt) < 2: continue
    
    # IMMEDIATE entry
    pos, entry_px, sl_px = 0, 0, 0
    for i, (t, bar) in enumerate(mkt.iterrows()):
        if pos == 0:
            if bar['close'] > r_high:
                pos, entry_px, sl_px = 1, bar['close'], r_low
            elif bar['close'] < r_low:
                pos, entry_px, sl_px = -1, bar['close'], r_high
        if pos != 0:
            dist = abs(entry_px - sl_px)
            max_dist = entry_px * (config['MAX_SL_PCT']/100)
            if dist > max_dist:
                sl_px = entry_px - max_dist if pos == 1 else entry_px + max_dist
            
            sl_hit = (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px)
            if sl_hit:
                pnl = (sl_px - entry_px)/entry_px*100 if pos == 1 else (entry_px - sl_px)/entry_px*100
                trades.append({'PnL_Pct': pnl})
                break
            if i == len(mkt) - 1:
                pnl = (bar['close'] - entry_px)/entry_px*100 if pos == 1 else (entry_px - bar['close'])/entry_px*100
                trades.append({'PnL_Pct': pnl})

df_trades = pd.DataFrame(trades)
print('=== V7 OPTIMIZED (IMMEDIATE, Exit 11:00, SL 0.25%) ===')
print(f'Trades: {len(df_trades)}')
wr = (df_trades['PnL_Pct'] > 0).mean()
print(f'Win Rate: {wr:.2%}')
gross = df_trades['PnL_Pct'].sum()
print(f'Gross PnL: {gross:.2f}%')
gp = df_trades[df_trades['PnL_Pct']>0]['PnL_Pct'].sum()
gl = abs(df_trades[df_trades['PnL_Pct']<0]['PnL_Pct'].sum())
pf = gp/gl if gl > 0 else float('inf')
print(f'Profit Factor: {pf:.2f}')
print(f'Avg Trade: {df_trades["PnL_Pct"].mean():.4f}%')

# Save
df_trades.to_csv('scripts/backtest/9_30_breakout/results/v7_optimized_clean.csv', index=False)
print('\nSaved: v7_optimized_clean.csv')
