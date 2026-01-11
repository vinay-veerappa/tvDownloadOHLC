
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time

# Configuration
DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\data"
TICKERS = ['ES1', 'NQ1']
START_YEAR = 2008
EST_TZ = pytz.timezone('US/Eastern')

def load_and_process(ticker):
    path = f"{DATA_DIR}\\{ticker}_1m.parquet"
    print(f"Loading {ticker}...")
    df = pd.read_parquet(path)
    
    # Handle Index
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df['time'], unit='s', utc=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
        
    # Convert to EST
    df = df.tz_convert(EST_TZ)
    
    # Filter Year
    df = df[df.index.year >= START_YEAR]
    
    # create helper columns
    df['Date'] = df.index.date
    df['Time'] = df.index.time
    
    # 1. RTH High/Low (09:30 - 16:15)
    # 16:15 is technically 16:15:00. The bar 16:14 is the last 1m bar? 
    # Usually "RTH Close" is 16:00 or 16:15 for futures.
    # Settlement is 16:15.
    # Ranges: 09:30 <= t <= 16:15
    mask_rth = (df.index.time >= time(9, 30)) & (df.index.time <= time(16, 15))
    df_rth = df[mask_rth].copy()
    
    rth_stats = df_rth.groupby('Date').agg(
        RTH_High=('high', 'max'),
        RTH_Low=('low', 'min')
    )
    
    # 2. 6AM Candle (06:00 - 06:59)
    # "6AM Candle" usually means the 1H bar starting at 06:00.
    mask_6am = (df.index.time >= time(6, 0)) & (df.index.time <= time(6, 59))
    df_6am = df[mask_6am].copy()
    
    # We want 6AM High/Low/Close for each day
    stats_6am = df_6am.groupby('Date').agg(
        H6_High=('high', 'max'),
        H6_Low=('low', 'min'),
        H6_Close=('close', 'last')
    )
    
    # 3. NY Session (09:30 Open - 16:00 Close)
    # We need the OPEN of 09:30 bar and CLOSE of 16:00 bar (or 15:59 close)
    # Vectorized:
    # Get 09:30 bars
    mask_open = (df.index.time == time(9, 30))
    ny_opens = df[mask_open].groupby('Date')['open'].first()
    
    # Get 16:00 bars (or close to it)
    # Using 16:00 bar close 
    mask_close = (df.index.time == time(16, 0))
    ny_closes = df[mask_close].groupby('Date')['close'].last()
    
    # Merge Stats
    # We want Current Day 6AM vs PRIOR Day RTH
    # Shift RTH stats by 1 day? 
    # No, simple shift isn't safe due to weekends/holidays.
    # We need to map "Date" to "Prior Trading Day".
    # But since we have a continuous index of valid trading days in 'rth_stats', 
    # we can use shift(1).
    # rth_stats is indexed by Date. Sorted.
    # rth_prev = rth_stats.shift(1)
    # This aligns Date[i] with RTH[i-1].
    # So for Date='2023-01-04', rth_prev will have RTH of '2023-01-03'.
    
    rth_prev = rth_stats.shift(1).rename(columns={'RTH_High': 'PDH', 'RTH_Low': 'PDL'})
    
    # Combine
    merged = stats_6am.join(rth_prev, how='inner')
    merged = merged.join(ny_opens.rename("NY_Open"), how='inner')
    merged = merged.join(ny_closes.rename("NY_Close"), how='inner')
    
    # Calculate Signals
    merged['Signal'] = 'NONE'
    
    # Sweep High Short
    cond_sweep_high = (merged['H6_High'] > merged['PDH']) & (merged['H6_Close'] < merged['PDH'])
    merged.loc[cond_sweep_high, 'Signal'] = 'SWEEP_PDH_SHORT'
    
    # Sweep Low Long
    cond_sweep_low = (merged['H6_Low'] < merged['PDL']) & (merged['H6_Close'] > merged['PDL'])
    merged.loc[cond_sweep_low, 'Signal'] = 'SWEEP_PDL_LONG'
    
    # Break High Long
    cond_break_high = (merged['H6_Close'] > merged['PDH'])
    merged.loc[cond_break_high, 'Signal'] = 'BREAK_PDH_LONG'
    
    # Break Low Short
    cond_break_low = (merged['H6_Close'] < merged['PDL'])
    merged.loc[cond_break_low, 'Signal'] = 'BREAK_PDL_SHORT'
    
    # Calculate Outcome
    merged['NY_Range'] = merged['NY_Close'] - merged['NY_Open']
    merged['Win'] = False
    
    # Long Wins
    long_signals = merged['Signal'].str.contains('LONG')
    merged.loc[long_signals & (merged['NY_Range'] > 0), 'Win'] = True
    
    # Short Wins
    short_signals = merged['Signal'].str.contains('SHORT')
    merged.loc[short_signals & (merged['NY_Range'] < 0), 'Win'] = True
    
    return merged

def analyze(ticker):
    df = load_and_process(ticker)
    
    print(f"\n--- {ticker} ({START_YEAR}-Present) ---")
    print(f"Total Days: {len(df)}")
    
    signals = df[df['Signal'] != 'NONE']
    print(f"Signals: {len(signals)} ({len(signals)/len(df)*100:.1f}%)")
    
    print(f"\n{'Signal':<20} | {'Count':<5} | {'Win Rate':<8} | {'Avg Pts':<8}")
    print("-" * 55)
    
    for sig in ['SWEEP_PDH_SHORT', 'SWEEP_PDL_LONG', 'BREAK_PDH_LONG', 'BREAK_PDL_SHORT']:
        sub = df[df['Signal'] == sig]
        cnt = len(sub)
        if cnt > 0:
            wr = sub['Win'].mean() * 100
            avg = sub['NY_Range'].mean()
            print(f"{sig:<20} | {cnt:<5} | {wr:6.1f}% | {avg:8.2f}")

if __name__ == "__main__":
    for t in TICKERS:
        analyze(t)
