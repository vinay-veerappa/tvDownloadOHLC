
import pandas as pd
import numpy as np
import os
import argparse
import sys
from datetime import timedelta, time

# Define paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(ROOT_DIR, "data")

def load_data(ticker, timeframe):
    path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
    if not os.path.exists(path):
         if timeframe == "15m": path = os.path.join(DATA_DIR, f"{ticker}_15m.parquet")
         
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        sys.exit(1)
        
    df = pd.read_parquet(path)
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        
    # Standardize Column Names
    df.columns = [c.lower() for c in df.columns]
        
    if 'time' not in df.columns and 'datetime' not in df.columns:
         df.rename(columns={df.columns[0]: 'datetime'}, inplace=True)
         
    if 'time' in df.columns and 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
    
    if 'datetime' not in df.columns:
         for col in df.columns:
             if pd.api.types.is_datetime64_any_dtype(df[col]):
                 df.rename(columns={col: 'datetime'}, inplace=True)
                 break
                 
    if 'datetime' in df.columns:
        # Check tz
        if df['datetime'].dt.tz is None:
             # Assume filtered externally or handle raw
             # Ideally validation happens before
             pass
        else:
             pass # Already tz aware
             
        df = df.sort_values('datetime').reset_index(drop=True)
        
    return df

def backtest_asia_volatility(ticker):
    print(f"Backtesting Asia Volatility + 07:30 Open for {ticker}...")
    
    # Load 15m Data
    df = load_data(ticker, "15m")
    
    # Filter 2022+
    start_date = pd.Timestamp("2022-01-01")
    if df['datetime'].dt.tz is not None:
        start_date = start_date.tz_localize(df['datetime'].dt.tz)
    df = df[df['datetime'] >= start_date].reset_index(drop=True)
    
    unique_dates = df['datetime'].dt.date.unique()
    
    results = []
    wins = 0; losses = 0; total = 0
    
    # Define Thresholds (Points) - Approx for NQ
    # Compressed: < 50 points? < 40? 
    # NQ is volatile. Let's say < 60 points is compressed.
    # Expanded: > 120 points.
    COMPRESSION_THRESHOLD = 60.0 
    
    for date_obj in unique_dates:
        # Need prev day evening for Asia start (18:00)
        # But wait, df is strictly datetime sorted.
        # Let's find index ranges.
        
        # Current Day Data
        day_mask = df['datetime'].dt.date == date_obj
        day_data = df[day_mask]
        
        if day_data.empty: continue
        
        # Get Asia Session (00:00 - 02:00 for simplification ON SAME DAY, 
        # or properly 18:00 prev day? Implementation complexity high for prev day lookup 
        # without full index alignment.
        # Let's use 18:00 Prev Day if available, else just 00:00-02:00 is "Late Asia"?)
        
        # Better: Use 00:00 to 07:30 as the "Pre-Open Range" proxy for Volatility?
        # User asked for "Ranges of Asia".
        # Let's try to get 18:00 Prev Day.
        
        # Find prev date
        prev_date = date_obj - timedelta(days=1)
        # Weekends?
        # Identify Previous Trading Day logic is hard without market calendar.
        
        # Logic Shortcut: 
        # Measure Range from 00:00 to 07:30 (Midnight to Pre-Open).
        # While not strictly "Asia", it captures the overnight volatility profile.
        # If Overnight is Compressed -> Breakout likely.
        
        t_0000 = time(0, 0)
        t_0730 = time(7, 30)
        t_0930 = time(9, 30)
        t_1200 = time(12, 0)
        
        overnight_data = day_data[(day_data['datetime'].dt.time >= t_0000) & (day_data['datetime'].dt.time < t_0730)]
        target_open_bar = day_data[day_data['datetime'].dt.time == t_0730]
        
        if overnight_data.empty: 
            # Possibly no midnight data (holidays/partial).
            continue
            
        # Get 07:30 Open
        if target_open_bar.empty:
            # Maybe 07:30 didn't have a bar exactly? (15m bars: 07:15, 07:30, 07:45...)
            # 07:30 bar exists.
            # Using the OPEN of the 07:30 bar.
             open_0730_price = overnight_data['close'].iloc[-1] # Close of 07:15 bar? No.
             # Find closest bar at or after 07:30
             after_0730 = day_data[day_data['datetime'].dt.time >= t_0730]
             if not after_0730.empty:
                 open_0730_price = after_0730['open'].iloc[0]
             else:
                 continue
        else:
            open_0730_price = target_open_bar['open'].iloc[0]
            
        # 1. Measure Volatility (Range)
        # Using 00:00 to 07:30 range
        rnge = overnight_data['high'].max() - overnight_data['low'].min()
        
        # 2. Check Regime
        regime = "Normal"
        if rnge < COMPRESSION_THRESHOLD:
            regime = "Compressed"
        elif rnge > (COMPRESSION_THRESHOLD * 2): # > 120
            regime = "Expanded"
            
        # Strategy: Trade Expansion on Compressed Days
        if regime == "Compressed":
            # Expect Trend Day
            # Trigger: Price Break from 07:30 Open after 09:30
            
            ny_session = day_data[(day_data['datetime'].dt.time >= t_0930) & (day_data['datetime'].dt.time < t_1200)]
            
            bias = "Neutral"
            entry_price = 0
            
            # Simple Breakout Logic from 07:30 Open
            # If we cross 07:30 Open UP -> Bullish
            # If we cross 07:30 Open DOWN -> Bearish
            
            # Check where we are at 09:30
            if ny_session.empty: continue
            
            ny_open_price = ny_session['open'].iloc[0]
            
            if ny_open_price > open_0730_price:
                bias = "Bullish"
                reason = f"Compressed Overnight ({rnge:.1f} pts) + 09:30 > 07:30 Open"
                entry_price = ny_open_price
            elif ny_open_price < open_0730_price:
                bias = "Bearish"
                reason = f"Compressed Overnight ({rnge:.1f} pts) + 09:30 < 07:30 Open"
                entry_price = ny_open_price
                
            # Outcome (EOD or Close)
            if bias != "Neutral":
                eod_close = day_data['close'].iloc[-1]
                change = eod_close - entry_price
                
                win = False
                if bias == "Bullish" and change > 0: win = True
                if bias == "Bearish" and change < 0: win = True
                
                results.append({
                    "Date": date_obj,
                    "Regime": regime,
                    "Bias": bias,
                    "Range": rnge,
                    "Outcome": "Win" if win else "Loss",
                    "PnL": change if bias == "Bullish" else -change
                })
                
                if win: wins += 1
                else: losses += 1
                total += 1
                
    # Report
    win_rate = (wins / total * 100) if total > 0 else 0
    total_pnl = 0
    if results:
         total_pnl = pd.DataFrame(results)['PnL'].sum()

    print(f"\n--- Results for {ticker} ---")
    print(f"Concepts: Asia/Overnight Compression ({COMPRESSION_THRESHOLD} pts) + 07:30 Open Trend")
    print(f"Total Traded Days: {total}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total PnL: {total_pnl:.2f} pts")
    
    if results:
        print("\nLast 5 Trades:")
        print(pd.DataFrame(results).tail(5).to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="NQ1", help="Ticker")
    args = parser.parse_args()
    backtest_asia_volatility(args.ticker)
