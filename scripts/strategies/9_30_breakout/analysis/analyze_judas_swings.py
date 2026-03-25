"""
Analyze Judas Swings vs Continuation
====================================
Quantify how often a confirmed breakout (0.10% beyond range) reverses (Judas Swing) 
vs continues to be a winner.

Definitions:
- Confirmed Breakout: Close > Range High * 1.001 (or Low * 0.999)
- Judas Swing (Fakeout): Confirmed breakout that subsequently hits SL (Range Low/High)
- Continuation (Winner): Confirmed breakout that closes profitable at 11:00

Metrics:
- Judas Swing Rate: % of confirmed entries that hit SL
- True Breakout Rate: % of confirmed entries that end profitable
- Judas Severity: How far did it go before reversing? (MFE of losers)
"""
import pandas as pd
import numpy as np
import json

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

print('=== JUDAS SWING ANALYSIS ===')
print('Quantifying fakeouts after 0.10% confirmation\n')

events = []

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
    max_runup_pct = 0
    result = ''
    
    for i, (t, bar) in enumerate(mkt.iterrows()):
        if pos == 0:
            if bar['close'] > r_high * 1.001:
                pos, entry_px = 1, bar['close']
                sl_px = r_low
            elif bar['close'] < r_low * 0.999:
                pos, entry_px = -1, bar['close']
                sl_px = r_high
        
        if pos != 0:
            # Track max runup before failure
            if pos == 1:
                runup = (bar['high'] - entry_px) / entry_px * 100
                max_runup_pct = max(max_runup_pct, runup)
                if bar['low'] <= sl_px:
                    result = 'JUDAS'
                    break
            else:
                runup = (entry_px - bar['low']) / entry_px * 100
                max_runup_pct = max(max_runup_pct, runup)
                if bar['high'] >= sl_px:
                    result = 'JUDAS'
                    break
            
            if i == len(mkt) - 1:
                pnl = (bar['close'] - entry_px)/entry_px*100 if pos == 1 else (entry_px - bar['close'])/entry_px*100
                if pnl > 0:
                    result = 'CONTINUATION'
                else:
                    result = 'CHOP_LOSS' # Closed negative but didn't hit SL

    if result:
        events.append({
            'Result': result,
            'MaxRunup': max_runup_pct,
            'Direction': 'Long' if pos == 1 else 'Short'
        })

df = pd.DataFrame(events)
total = len(df)
judas = df[df['Result'] == 'JUDAS']
continuation = df[df['Result'] == 'CONTINUATION']
chop = df[df['Result'] == 'CHOP_LOSS']

print(f'Total Confirmed Entries: {total}')
print(f'Continuation (Winners): {len(continuation)} ({len(continuation)/total*100:.1f}%)')
print(f'Judas Swings (SL Hit): {len(judas)} ({len(judas)/total*100:.1f}%)')
print(f'Chop (Closed Negative): {len(chop)} ({len(chop)/total*100:.1f}%)')

print('\n=== JUDAS SWING SEVERITY ===')
print('How far did the fakeout go before reversing?')
for r in [0.05, 0.10, 0.15, 0.20]:
    count = (judas['MaxRunup'] >= r).sum()
    print(f'  Reached +{r:.2f}% profit then failed: {count} ({count/len(judas)*100:.1f}% of Judas swings)')

print('\n=== WINNER ENTRY DISTRIBUTION ===')
print('Median Max Runup of Winners: {:.2f}%'.format(continuation['MaxRunup'].median()))
print('Median Max Runup of Judas Swings: {:.2f}%'.format(judas['MaxRunup'].median()))

print('\n=== CONCLUSION ===')
print(f'Judas Rate: {len(judas)/total*100:.1f}% of confirmed breakouts fail.')
print(f'Breakout Success Rate: {len(continuation)/total*100:.1f}%')
