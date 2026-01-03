"""
Analyze Reversal Signals for Loss Mitigation
============================================
Testing specific reversal signatures to see if they predict failure better than random noise.

Signals to Test:
1. CLOSE BACK INSIDE: Price closes back inside the Opening Range
2. MOMENTUM REVERSAL: 2 consecutive bars against position
3. VOLUME SPIKE: Adverse bar volume > 1.5x average
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

def run_test(exit_mode, label):
    trades = []
    
    for d, row in or_df.iterrows():
        r_high, r_low = row['high'], row['low']
        if row.get('range_pct', (r_high-r_low)/row['open']) > 0.25: continue
        
        d_loc = pd.Timestamp(d).tz_localize('US/Eastern')
        t_start = d_loc + pd.Timedelta(hours=9, minutes=31)
        t_end = d_loc + pd.Timedelta(hours=11, minutes=0)
        
        mkt = df_price.loc[t_start:t_end]
        if len(mkt) < 5: continue
        
        # Calculate volume MA for the day so far? Or use global?
        # Simple approximation: Compare to recent 5 bars
        
        pos, entry_px = 0, 0
        sl_px = 0
        consecutive_adverse = 0
        
        for i in range(len(mkt)):
            bar = mkt.iloc[i]
            
            if pos == 0:
                # Confirmed entry
                if bar['close'] > r_high * 1.001:
                    pos, entry_px = 1, bar['close']
                    sl_px = r_low
                elif bar['close'] < r_low * 0.999:
                    pos, entry_px = -1, bar['close']
                    sl_px = r_high
            
            if pos != 0:
                # Check Signal
                should_exit = False
                
                # Signal 1: Close Back Inside Range
                if exit_mode == 'CloseInside':
                    if pos == 1 and bar['close'] < r_high:
                        should_exit = True
                    elif pos == -1 and bar['close'] > r_low:
                        should_exit = True
                
                # Signal 2: 2 Consecutive Adverse Bars
                elif exit_mode == 'Consecutive':
                    is_adverse = (pos == 1 and bar['close'] < bar['open']) or (pos == -1 and bar['close'] > bar['open'])
                    if is_adverse:
                        consecutive_adverse += 1
                    else:
                        consecutive_adverse = 0
                    
                    if consecutive_adverse >= 2:
                        should_exit = True
                
                # Signal 3: Volume Reversal (Adverse candle > 1.5x prev 5 vol)
                elif exit_mode == 'Volume':
                    is_adverse = (pos == 1 and bar['close'] < bar['open']) or (pos == -1 and bar['close'] > bar['open'])
                    if is_adverse and i > 5:
                        avg_vol = mkt.iloc[i-5:i]['volume'].mean()
                        if bar['volume'] > avg_vol * 1.5:
                            should_exit = True
                
                # Execute Exit or SL/TP
                if should_exit:
                    pnl = (bar['close'] - entry_px)/entry_px*100 if pos == 1 else (entry_px - bar['close'])/entry_px*100
                    trades.append({'PnL': pnl, 'Exit': 'SIGNAL'})
                    break
                
                # SL
                if (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px):
                    pnl = (sl_px - entry_px)/entry_px*100 if pos == 1 else (entry_px - sl_px)/entry_px*100
                    trades.append({'PnL': pnl, 'Exit': 'SL'})
                    break
                
                # Time
                if i == len(mkt) - 1:
                    pnl = (bar['close'] - entry_px)/entry_px*100 if pos == 1 else (entry_px - bar['close'])/entry_px*100
                    trades.append({'PnL': pnl, 'Exit': 'TIME'})

    if not trades: return
    df = pd.DataFrame(trades)
    wr = (df['PnL'] > 0).mean()
    pnl = df['PnL'].sum()
    sig_count = (df['Exit'] == 'SIGNAL').sum()
    
    print(f'{label:25s} Trades: {len(df):4d}, WR: {wr:.1%}, PnL: {pnl:+7.2f}%, SigExits: {sig_count}')

print('=== REVERSAL SIGNAL ANALYSIS ===\\n')
run_test('None', 'Baseline (No Signal)')
print()
run_test('CloseInside', 'Close Back Inside Range')
run_test('Consecutive', '2 Consecutive Adverse')
run_test('Volume', 'Volume Spike (>1.5x)')
