"""
Analyze Entry Times for Winners vs Losers
=========================================
Identify the "Golden Window" for entries.
Do winners tend to happen earlier or later?

Metrics:
- Entry Time Mode (most frequent 5-minute bucket)
- Distribution of Entry Times for Winners vs Losers
"""
import pandas as pd
import numpy as np
import json
from datetime import time, timedelta

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

end_date = or_df.index.max()
start_date = end_date - pd.Timedelta(days=YEARS*365)
or_df = or_df[or_df.index >= start_date]

print('=== ENTRY TIME ANALYSIS ===')
print('Finding the mode entry time for Winners vs Losers\n')

trades = []

for d, row in or_df.iterrows():
    r_high, r_low = row['high'], row['low']
    r_size = r_high - r_low
    if row.get('range_pct', r_size/row['open']) > 0.25: continue
    
    d_loc = pd.Timestamp(d).tz_localize('US/Eastern')
    t_start = d_loc + pd.Timedelta(hours=9, minutes=31)
    t_end = d_loc + pd.Timedelta(hours=11, minutes=0)
    
    mkt = df_price.loc[t_start:t_end]
    if len(mkt) < 5: continue
    
    pos, entry_px = 0, 0
    sl_px = 0
    entry_time = None
    
    for i, (t, bar) in enumerate(mkt.iterrows()):
        bar_time = t.time()
        
        # Stop entering after 10:30
        if pos == 0 and bar_time < time(10, 30):
            if bar['close'] > r_high * 1.001:
                pos, entry_px = 1, bar['close']
                sl_px = r_low
                entry_time = bar_time
            elif bar['close'] < r_low * 0.999:
                pos, entry_px = -1, bar['close']
                sl_px = r_high
                entry_time = bar_time
        
        if pos != 0:
            if (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px):
                pnl = (sl_px - entry_px)/entry_px*100 if pos == 1 else (entry_px - sl_px)/entry_px*100
                trades.append({
                    'Result': 'LOSS',
                    'EntryTime': entry_time
                })
                break
            
            if i == len(mkt) - 1:
                pnl = (bar['close'] - entry_px)/entry_px*100 if pos == 1 else (entry_px - bar['close'])/entry_px*100
                trades.append({
                    'Result': 'WIN' if pnl > 0 else 'LOSS',
                    'EntryTime': entry_time
                })

df = pd.DataFrame(trades)
df['EntryBucket'] = df['EntryTime'].apply(lambda x: x.replace(second=0, microsecond=0))

winners = df[df['Result'] == 'WIN']
losers = df[df['Result'] == 'LOSS']

print(f'Total Trades: {len(df)}')
print(f'Winners: {len(winners)}')
print(f'Losers: {len(losers)}')

# Mode
win_mode = winners['EntryBucket'].mode()[0]
loss_mode = losers['EntryBucket'].mode()[0]
print(f'\nWinner Mode Entry Time: {win_mode}')
print(f'Loser Mode Entry Time : {loss_mode}')

# Distribution
print('\n=== ENTRY TIME DISTRIBUTION (5-min buckets) ===')
buckets = sorted(df['EntryBucket'].unique())
print(f'{"Time":10s} | {"Win Rate":10s} | {"Count":8s} | {"Win% Dist":12s}')
print('-'*50)

for b in buckets:
    sub = df[df['EntryBucket'] == b]
    n = len(sub)
    if n > 20: 
        sub_wins = len(sub[sub['Result'] == 'WIN'])
        wr = sub_wins / n
        win_share = sub_wins / len(winners) # % of all winners that happened at this time
        print(f'{b} | {wr:8.1%} | {n:8d} | {win_share:10.1%}')

print('\n=== CUMULATIVE WINNER ANALYSIS ===')
print('By what time have X% of all winners already entered?')
winners_sorted = np.sort(winners['EntryBucket'])
for p in [0.25, 0.50, 0.75, 0.90]:
    idx = int(len(winners_sorted) * p)
    print(f'{p*100:.0f}% of winners have entered by: {winners_sorted[idx]}')
