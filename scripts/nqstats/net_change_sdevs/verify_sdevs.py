
import pandas as pd
import numpy as np
import os
import pytz
from datetime import time, timedelta

# --- Configuration ---
TICKERS = ['NQ1', 'ES1', 'YM1', 'RTY1', 'GC1', 'CL1']
DATA_DIR = 'data'
START_YEAR = 2015
ROLLING_WINDOW = 252 # 1 Year of Trading Days

def load_data(ticker):
    # Load 1m data
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path): return None
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('datetime', inplace=True)
    df = df.tz_convert('US/Eastern')
    return df[df.index.year >= START_YEAR] # We might need earlier data for rolling calculation?
    # To be safe, load all, calculate rolling, then filter START_YEAR.

def load_data_full(ticker):
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path): return None
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('datetime', inplace=True)
    df = df.tz_convert('US/Eastern')
    return df

def verify_sdevs(ticker):
    df = load_data_full(ticker)
    if df is None: return None
    
    # 1. Resample to Daily to get Net Change %
    # Daily Open (Session Open) vs Daily Close.
    # Standard: 9:30 - 16:00 for Equities? Or Full Day?
    # Transcript implies "Daily Bars".
    # Let's use Full Day (00:00 - 23:59 ET) for robustness, or strictly 9:30-16:00.
    # Video mentions "Session Open". For NQ, usually 18:00 or 9:30.
    # Given the "Net Change" context (Close - Open) / Open, it usually implies the full RTH or Full Day candle.
    # Let's try RTH (9:30 - 16:00) first as it aligns with other stats.
    
    # Actually, RTH (9:30) is the "Session Open" most traders reference.
    
    rth_df = df.between_time(time(9,30), time(16,0))
    daily = rth_df.resample('1D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    
    # 2. Calculate Net Change %
    daily['NetChangePct'] = (daily['close'] - daily['open']) / daily['open']
    
    # 3. Calculate Rolling SD
    # We want SD of the PERCENTAGE change.
    daily['RollingSD'] = daily['NetChangePct'].rolling(window=ROLLING_WINDOW).std()
    
    # Shift Standard Deviation! 
    # Current day's volatility shouldn't affect the level *entering* the day.
    # We use Prior 252 days to define "Today's SD".
    daily['PriorSD'] = daily['RollingSD'].shift(1)
    
    # Filter for valid years
    daily = daily[daily.index.year >= START_YEAR]
    
    # 4. Verify Hits and Reversions
    # Levels: 0.5, 1.0, 1.5, 2.0
    levels = [0.5, 1.0, 1.5, 2.0]
    results = {l: {'Hits': 0, 'Reversions': 0} for l in levels}
    
    for date, row in daily.iterrows():
        sigma = row['PriorSD']
        if pd.isna(sigma) or sigma == 0: continue
        
        open_px = row['open']
        high_px = row['high']
        low_px = row['low']
        close_px = row['close']
        
        # Calculate Price Levels for SDs
        # Formula: Level = Open + (Open * (SD * Factor))
        # Wait, if NetChange% = SD, then Price = Open * (1 + SD).
        # Correct.
        
        # We need to check BOTH sides (Plus and Minus)
        # If Price touches +1.0 SD or -1.0 SD.
        
        for l in levels:
            pct_move = sigma * l
            
            upper_level = open_px * (1 + pct_move)
            lower_level = open_px * (1 - pct_move)
            
            # Check Touch
            touched_upper = high_px >= upper_level
            touched_lower = low_px <= lower_level
            
            touched = touched_upper or touched_lower
            
            if touched:
                results[l]['Hits'] += 1
                
                # Check Reversion (Close Inside)
                # Did it close BELOW Upper and ABOVE Lower?
                # Note: We only care about the side touched.
                # If touched Upper, did it close Below Upper?
                # If touched Lower, did it close Above Lower?
                # If touched Both, did it close Inside Both?
                
                reverted = True
                if touched_upper and close_px > upper_level: reverted = False # Closed Outside Upper
                if touched_lower and close_px < lower_level: reverted = False # Closed Outside Lower
                
                if reverted:
                    results[l]['Reversions'] += 1
                    
    summary = []
    for l in levels:
        hits = results[l]['Hits']
        revs = results[l]['Reversions']
        rate = revs / hits if hits > 0 else 0
        summary.append({'Metric': f'{l} SD', 'Hits': hits, 'Reversion %': rate})
        
    return pd.DataFrame(summary).assign(Ticker=ticker)

def main():
    all_res = []
    print("Verifying Net Change SDEVs (Rolling 1-Year SD)...")
    for t in TICKERS:
        res = verify_sdevs(t)
        if res is not None:
            all_res.append(res)
            print(f"--- {t} ---")
            print(res.to_string(index=False))
            
    if all_res:
        pd.concat(all_res).to_csv('scripts/nqstats/results/sdev_verification.csv', index=False)
        print("\nSaved to scripts/nqstats/results/sdev_verification.csv")

if __name__ == "__main__":
    main()
