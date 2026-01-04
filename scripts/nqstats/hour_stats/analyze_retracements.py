
import pandas as pd
import numpy as np
import os
import argparse
from datetime import time, timedelta

# --- Configuration ---
DATA_DIR = 'data'
START_YEAR = 2015

def load_data(ticker):
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path): return None
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('datetime', inplace=True)
    df = df.tz_convert('US/Eastern')
    return df[df.index.year >= START_YEAR]

def analyze_retracements(df):
    print("Resampling to 1H...")
    
    # 1. Resample to 1H
    h_df = df.resample('1h').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    })
    h_df.dropna(inplace=True)
    
    # Calculate Levels
    h_df['Mid'] = (h_df['high'] + h_df['low']) / 2
    h_df['Range'] = h_df['high'] - h_df['low']
    h_df['Color'] = np.where(h_df['close'] > h_df['open'], 'Green', 'Red')
    
    # Shift to get "Previous" levels for the Current Candle
    h_df['Prev_High'] = h_df['high'].shift(1)
    h_df['Prev_Low'] = h_df['low'].shift(1)
    h_df['Prev_Mid'] = h_df['Mid'].shift(1)
    h_df['Prev_Close'] = h_df['close'].shift(1)
    h_df['Prev_Color'] = h_df['Color'].shift(1)
    
    stats = []
    
    print("Analyzing Pullbacks...")
    
    for idx, row in h_df.iterrows():
        if idx.hour < 9 or idx.hour > 16: continue
        
        # We only care if Previous was a Trend Candle (Green or Red)
        # Setup: Prev Green -> Want to Buy Pullback at Prev Mid?
        
        setup_type = None
        target_level = None
        
        if row['Prev_Color'] == 'Green':
            setup_type = 'Bullish_Pullback'
            # Where did we pull back to?
            # We look at the LOW of the current hour.
            # Did it tap Prev Mid? Prev High?
            target_mid = row['Prev_Mid']
            
        elif row['Prev_Color'] == 'Red':
            setup_type = 'Bearish_Pullback'
            target_mid = row['Prev_Mid']
        else:
            continue
            
        start_time = idx
        end_time = start_time + timedelta(hours=1)
        
        try:
            slice_df = df.loc[start_time:end_time - timedelta(minutes=1)]
        except: continue
        if slice_df.empty: continue
        
        curr_low = row['low']
        curr_high = row['high']
        curr_open = row['open']
        
        # --- Metric 1: Respecting Prev 50% ---
        # For Bullish: Did Low stay ABOVE Prev Mid? (Strong Hold)
        # Or did it Touch Prev Mid and Bounce?
        
        # Let's measure "Touch & Hold"
        # Hit Rate: Price touched the level zone (+- 2 points?)
        # Win Rate: Price closed in direction of trend after touching.
        
        respected_mid = False
        touched_mid = False
        closed_with_trend = False
        
        threshold = 2.0 # 2 points tolerance
        
        if setup_type == 'Bullish_Pullback':
            # Touch: Low <= Mid + tolerance
            if curr_low <= target_mid + threshold: touched_mid = True
            
            # Respect: Close > Mid
            if row['close'] > target_mid: respected_mid = True
            
            # Trend Continuation
            if row['close'] > row['open']: closed_with_trend = True
            
        elif setup_type == 'Bearish_Pullback':
            # Touch: High >= Mid - tolerance
            if curr_high >= target_mid - threshold: touched_mid = True
            
            # Respect: Close < Mid
            if row['close'] < target_mid: respected_mid = True
            
            # Trend Continuation
            if row['close'] < row['open']: closed_with_trend = True
            
        stats.append({
            'Setup': setup_type,
            'Touched_Prev_50': touched_mid,
            'Respected_Prev_50_Close': respected_mid,
            'Continuation_Candle': closed_with_trend
        })
        
    stats_df = pd.DataFrame(stats)
    
    print("\n--- Pullback Analysis (Prev Candle 50% Level) ---")
    
    summary = stats_df.groupby('Setup').agg({
        'Touched_Prev_50': 'mean', # Frequency of deep pullback
        'Respected_Prev_50_Close': 'mean', # Prob of holding level
        'Continuation_Candle': 'mean' # Prob of trend continuing
    })
    
    # Conditional Prob: If Touched 50%, did we Continue?
    print(summary.round(3).to_string())
    
    print("\n--- Conditional Probability (Bounce off 50%) ---")
    
    touched = stats_df[stats_df['Touched_Prev_50'] == True]
    bounce_rate = touched.groupby('Setup')['Respected_Prev_50_Close'].mean()
    print("Prob of Holding 50% GIVEN a Touch:")
    print(bounce_rate.round(3).to_string())
    
    print("\n")
    cont_rate = touched.groupby('Setup')['Continuation_Candle'].mean()
    print("Prob of Trend Continuation GIVEN a Touch of 50%:")
    print(cont_rate.round(3).to_string())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ticker', type=str, help='Ticker')
    args = parser.parse_args()
    
    df = load_data(args.ticker)
    if df is not None:
        analyze_retracements(df)

if __name__ == "__main__":
    main()
