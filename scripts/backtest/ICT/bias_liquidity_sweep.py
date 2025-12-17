
import pandas as pd
import numpy as np
import os
import argparse
import sys
from datetime import timedelta

# Define paths
# 4 dirname calls to get to root from scripts/backtest/ICT
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
        # Rename index col to datetime if needed, or if it is named 'time' already
        # usually reset_index creates 'index' or the name of index
        if 'time' not in df.columns and 'datetime' not in df.columns:
             # Assume the first column is now the date
             df.rename(columns={df.columns[0]: 'datetime'}, inplace=True)
    
    if 'time' in df.columns and 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        
    if 'datetime' not in df.columns:
         # Fallback try to find a column with date
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

def identify_swings(df, window=2):
    """
    Identify Swing Highs and Lows.
    A swing high is a high surrounded by 'window' lower highs on both sides.
    """
    df['swing_high'] = False
    df['swing_low'] = False
    
    # Vectorized check for local maxima/minima
    # Using rolling window technique is complex for "both sides"
    # Iterating is acceptable for Daily data (small size)
    
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

def backtest_liquidity_sweep(ticker):
    print(f"Backtesting Liquidity Sweep Bias for {ticker}...")
    df = load_data(ticker)
    
    # Filter for last 3 years (approx) or user param
    # Hardcoding 2022-01-01 for now as requested
    df = df[df['datetime'] >= '2022-01-01'].reset_index(drop=True)
    print(f"Data filtered from 2022-01-01. Rows: {len(df)}")
    
    df = identify_swings(df, window=3) # 3-bar fractal
    
    # Store active swing points
    active_highs = [] # (price, index)
    active_lows = []
    
    results = []
    
    # We iterate through days. 
    # Logic:
    # On Day T, we check if we swept a PREVIOUS swing established before Day T.
    
    # NOTE: Swing points are identified based on FUTURE data (i+k).
    # So on Day T, we can only "know" a swing high existed at T-k IF T > T-k + window.
    # The logic below respects this causality.
    
    # Pre-calculate swings for lookup speed
    swing_highs_idx = df[df['swing_high']].index.tolist()
    swing_lows_idx = df[df['swing_low']].index.tolist()
    
    wins = 0
    losses = 0
    total_trades = 0
    
    # Iterate
    # Start after some buffer
    for i in range(20, len(df) - 1):        
        current_date = df['datetime'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        
        bias = None # 'Bullish', 'Bearish'
        reason = ""
        
        # 1. Check for Buy-Side Liquidity (BSL) Sweep
        # Condition: High > Old Swing High AND Close < Old Swing High
        # Find valid previous swing highs
        # A swing at index 's' is "confirmed" at 's + window'.
        # Since we ran identify_swings on full data, we must check confirmation: s + 3 <= i
        
        relevant_highs = [s for s in swing_highs_idx if s + 3 <= i]
        
        for idx in relevant_highs:
            old_high_price = df['high'].iloc[idx]
            
            # Check if this old high was "alive" (not violated recently? Optional but keeping simple)
            # Simple Sweep: Use the MOST RECENT broken high? or ANY un-swept?
            
            # Let's keep it simple: Did we sweep the *most recent* valid swing high?
            # Or did we break it?
            
            pass 
        
        # Simplified Approach:
        # Look at the *last confirmed* swing high/low relative to today.
        last_high_idx = next((s for s in reversed(swing_highs_idx) if s + 3 <= i), None)
        last_low_idx = next((s for s in reversed(swing_lows_idx) if s + 3 <= i), None)

        # BSL Sweep (Bearish Setup)
        if last_high_idx is not None:
            sw_high_price = df['high'].iloc[last_high_idx]
            if current_high > sw_high_price and current_close < sw_high_price:
                bias = "Bearish"
                reason = f"Swept High {df['datetime'].iloc[last_high_idx].date()} ({sw_high_price})"

        # SSL Sweep (Bullish Setup)
        # Note: If both happen (outside bar), Neutral or prioritize valid close?
        if last_low_idx is not None:
            sw_low_price = df['low'].iloc[last_low_idx]
            if current_low < sw_low_price and current_close > sw_low_price:
                # If we already have Bearish bias (Outside Bar), checking close helps.
                # If Close > Open (Green Candle), favor Bullish.
                if bias == "Bearish":
                   if current_close > df['open'].iloc[i]: bias = "Bullish"
                   else: bias = "Bearish"
                else:
                    bias = "Bullish"
                    reason = f"Swept Low {df['datetime'].iloc[last_low_idx].date()} ({sw_low_price})"
                    
        
        if bias:
            # Check Next Day (i+1)
            next_day_open = df['open'].iloc[i+1]
            next_day_close = df['close'].iloc[i+1]
            next_day_change = next_day_close - next_day_open
            
            win = False
            if bias == "Bullish" and next_day_change > 0: win = True
            if bias == "Bearish" and next_day_change < 0: win = True
            
            # Expansion Metric (Absolute points)
            expansion = abs(next_day_change)
            
            results.append({
                "Date": current_date.strftime("%Y-%m-%d"),
                "Bias": bias,
                "Reason": reason,
                "NextDay": df['datetime'].iloc[i+1].strftime("%Y-%m-%d"),
                "Outcome": "Win" if win else "Loss",
                "PnL_Points": next_day_change if bias == "Bullish" else -next_day_change
            })
            
            if win: wins += 1
            else: losses += 1
            total_trades += 1

    # Reporting
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    if results:
        res_df = pd.DataFrame(results)
        avg_win = res_df[res_df["Outcome"] == "Win"]["PnL_Points"].mean()
        avg_loss = res_df[res_df["Outcome"] == "Loss"]["PnL_Points"].mean()
        total_pnl = res_df["PnL_Points"].sum()
        
        print(f"\n--- Results for {ticker} ---")
        print(f"Concepts: Liquidity Sweep + Reversal Close")
        print(f"Total Setups: {total_trades}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Avg Win: {avg_win:.2f} pts")
        print(f"Avg Loss: {avg_loss:.2f} pts")
        print(f"Total PnL (1 contract): {total_pnl:.2f} pts")
        
        # Recent
        print("\nLast 5 Trades:")
        print(res_df.tail(5).to_string(index=False))
        
    else:
        print("No setups found.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="NQ1", help="Ticker symbol (default: NQ1)")
    args = parser.parse_args()
    
    backtest_liquidity_sweep(args.ticker)
