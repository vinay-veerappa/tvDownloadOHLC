
import pandas as pd
import numpy as np
import os
import argparse
import sys
from datetime import timedelta

# Define paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(ROOT_DIR, "data")

def load_data(ticker):
    # Load daily data
    path = os.path.join(DATA_DIR, f"{ticker}_1d.parquet")
    if not os.path.exists(path):
        # Fallback to NQ1_1D.parquet if NQ1_1d.parquet doesn't exist
        path = os.path.join(DATA_DIR, f"{ticker}_1D.parquet")
        
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        sys.exit(1)
        
    df = pd.read_parquet(path)
    
    # Check if index is datetime
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        if 'time' not in df.columns and 'datetime' not in df.columns:
             df.rename(columns={df.columns[0]: 'datetime'}, inplace=True)
    
    if 'time' in df.columns and 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        
    if 'datetime' not in df.columns:
         for col in df.columns:
             if pd.api.types.is_datetime64_any_dtype(df[col]):
                 df.rename(columns={col: 'datetime'}, inplace=True)
                 break
                 
    # Sort
    if 'datetime' in df.columns:
        df = df.sort_values('datetime').reset_index(drop=True)
    else:
        print("Error: Could not identify datetime column")
        sys.exit(1)
        
    return df

def identify_swings(df, window=3):
    """
    Identify Swing Highs and Lows.
    """
    df['swing_high'] = False
    df['swing_low'] = False
    
    for i in range(window, len(df) - window):
        # Swing High
        if all(df['high'].iloc[i] > df['high'].iloc[i-k] for k in range(1, window+1)) and \
           all(df['high'].iloc[i] > df['high'].iloc[i+k] for k in range(1, window+1)):
            df.at[i, 'swing_high'] = True
            
        # Swing Low
        if all(df['low'].iloc[i] < df['low'].iloc[i-k] for k in range(1, window+1)) and \
           all(df['low'].iloc[i] < df['low'].iloc[i+k] for k in range(1, window+1)):
            df.at[i, 'swing_low'] = True
            
    return df

def backtest_displacement(ticker):
    print(f"Backtesting Displacement (MSS) Bias for {ticker}...")
    df = load_data(ticker)
    
    # Filter for last 3 years
    df = df[df['datetime'] >= '2022-01-01'].reset_index(drop=True)
    print(f"Data filtered from 2022-01-01. Rows: {len(df)}")
    
    df = identify_swings(df, window=3)
    
    swing_highs_idx = df[df['swing_high']].index.tolist()
    swing_lows_idx = df[df['swing_low']].index.tolist()
    
    results = []
    wins = 0; losses = 0; total = 0
    
    current_bias = "Neutral"
    bias_reason = ""
    
    # Iterate
    # Displacement sets the bias for SUBSEQUENT days until invalidate.
    
    for i in range(20, len(df) - 1):        
        current_date = df['datetime'].iloc[i]
        close = df['close'].iloc[i]
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        
        # Check for MSS (Market Structure Shift)
        # 1. Did we close ABOVE a recent Swing High? -> Bullish MSS
        last_high = next((s for s in reversed(swing_highs_idx) if s + 3 <= i), None)
        last_low = next((s for s in reversed(swing_lows_idx) if s + 3 <= i), None)
        
        new_bias = None
        
        if last_high is not None:
            sw_high_price = df['high'].iloc[last_high]
            if close > sw_high_price:
                # MSS Bullish
                # Only if we weren't already significantly bullish? 
                # Or just treat it as confirmation.
                new_bias = "Bullish"
                bias_reason = f"Closed Above High {df['datetime'].iloc[last_high].date()} ({sw_high_price})"

        if last_low is not None:
            sw_low_price = df['low'].iloc[last_low]
            if close < sw_low_price:
                new_bias = "Bearish"
                bias_reason = f"Closed Below Low {df['datetime'].iloc[last_low].date()} ({sw_low_price})"

        # Update Bias State
        if new_bias:
            current_bias = new_bias
            
        # "Trade" the Bias on the NEXT Day?
        # If today established/confirmed bias, we trade it tomorrow.
        
        if current_bias != "Neutral":
             trade_bias = current_bias
             
             # Metric: Next Day Expansion
             next_open = df['open'].iloc[i+1]
             next_close = df['close'].iloc[i+1]
             change = next_close - next_open
             
             win = False
             if trade_bias == "Bullish" and change > 0: win = True
             if trade_bias == "Bearish" and change < 0: win = True
             
             results.append({
                "Date": current_date.strftime("%Y-%m-%d"),
                "Bias": trade_bias,
                "Reason": bias_reason, # Reason set when bias was established
                "NextDay": df['datetime'].iloc[i+1].strftime("%Y-%m-%d"),
                "Outcome": "Win" if win else "Loss",
                "PnL_Points": change if trade_bias == "Bullish" else -change
            })
             
             if win: wins += 1
             else: losses += 1
             total += 1

    # Reporting
    win_rate = (wins / total * 100) if total > 0 else 0
    if results:
        res_df = pd.DataFrame(results)
        avg_win = res_df[res_df["Outcome"] == "Win"]["PnL_Points"].mean()
        avg_loss = res_df[res_df["Outcome"] == "Loss"]["PnL_Points"].mean()
        total_pnl = res_df["PnL_Points"].sum()
        
        print(f"\n--- Results for {ticker} ---")
        print(f"Concepts: Displacement (MSS) Trend Following")
        print(f"Total Days Traded: {total}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Avg Win: {avg_win:.2f} pts")
        print(f"Avg Loss: {avg_loss:.2f} pts")
        print(f"Total PnL: {total_pnl:.2f} pts")
        
        print("\nLast 5 Days:")
        print(res_df.tail(5).to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="NQ1", help="Ticker symbol (default: NQ1)")
    args = parser.parse_args()
    
    backtest_displacement(args.ticker)
