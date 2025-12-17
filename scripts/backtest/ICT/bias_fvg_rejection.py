
import pandas as pd
import numpy as np
import os
import argparse
import sys

# Define paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(ROOT_DIR, "data")

def load_data(ticker):
    path = os.path.join(DATA_DIR, f"{ticker}_1d.parquet")
    if not os.path.exists(path):
        # Fallback to NQ1_1D.parquet if NQ1_1d.parquet doesn't exist
        path = os.path.join(DATA_DIR, f"{ticker}_1D.parquet")
        
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        sys.exit(1)
        
    df = pd.read_parquet(path)
    
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
                 
    if 'datetime' in df.columns:
        df = df.sort_values('datetime').reset_index(drop=True)
    else:
        print("Error: Could not identify datetime column")
        sys.exit(1)
        
    return df

def find_fvgs(df):
    """
    Identify Fair Value Gaps.
    Bullish FVG: Low[i] > High[i-2] (Note: Pandas index i is current)
    Let's iterate:
    Gap is between Candle i (Current) and Candle i-2.
    """
    fvgs = []
    
    # We need at least index 2
    for i in range(2, len(df)):
        # Bullish FVG (Green candle typically in middle i-1, but gap is strict price)
        # Gap between High of i-2 and Low of i.
        # IF Low[i] > High[i-2] -> There is a gap.
        
        # Bullish FVG Logic:
        # Candle i-1 was likely up. 
        # The Low of Candle i (or min low of i?) AND High of i-2 leaves a gap.
        # Wait, standard FVG creation is at CLOSE of candle i?
        # A Bullish FVG is created by Candle k. It exists between High of k-1 and Low of k+1.
        # So at index i (completion of candle), the FVG is between High[i-2] and Low[i].
        # Correct.
        
        # Bullish FVG
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            fvgs.append({
                'type': 'Bullish',
                'top': df['low'].iloc[i],
                'bottom': df['high'].iloc[i-2],
                'created_at': i,
                'invalidated_at': None
            })
            
        # Bearish FVG
        # Gap between Low of i-2 and High of i.
        if df['high'].iloc[i] < df['low'].iloc[i-2]:
            fvgs.append({
                'type': 'Bearish',
                'top': df['low'].iloc[i-2],
                'bottom': df['high'].iloc[i],
                'created_at': i,
                'invalidated_at': None
            })
            
    return fvgs

def backtest_fvg_rejection(ticker):
    print(f"Backtesting FVG Rejection Bias for {ticker}...")
    df = load_data(ticker)
    
    # Filter 2022
    df = df[df['datetime'] >= '2022-01-01'].reset_index(drop=True)
    
    # Identify all created FVGs upfront (simplified, knowing "future" creation dates relative to index)
    # We must be careful not to use "future" FVGs.
    # To be strictly causal, we should identify on fly or filter by created_at < current_day.
    
    all_fvgs = find_fvgs(df)
    
    results = []
    wins = 0; losses = 0; total = 0
    
    # Iterate days
    for i in range(10, len(df) - 1):
        current_date = df['datetime'].iloc[i]
        low = df['low'].iloc[i]
        high = df['high'].iloc[i]
        close = df['close'].iloc[i]
        
        # 1. Find ACTIVE FVGs (Created before today, not invalidated?)
        # Simplification: Just find the *most recent* valid FVG that price is inside/touching.
        
        relevant_fvgs = [f for f in all_fvgs if f['created_at'] < i]
        
        # Check interactions
        bias = "Neutral"
        reason = ""
        
        # We want to catch the "Tap and Respect"
        # Did we trade into a Bullish FVG today?
        # Bullish FVG range: [bottom, top]
        
        # Prioritize MOST RECENT FVG?
        # Let's sort reversed
        relevant_fvgs.sort(key=lambda x: x['created_at'], reverse=True)
        
        for fvg in relevant_fvgs:
            # optimize: don't look back too far? 
            if i - fvg['created_at'] > 20: continue # Stale FVG
            
            if fvg['type'] == 'Bullish':
                # Did we dip into it? Low <= Top and High >= Bottom
                if low <= fvg['top'] and high >= fvg['bottom']:
                    # Did we respect it? Close >= Bottom (Didn't close below gap)
                    if close >= fvg['bottom']:
                        # Valid Bullish Rejection
                        bias = "Bullish"
                        reason = f"Respected Bullish FVG from {df['datetime'].iloc[fvg['created_at']].date()}"
                        break
            
            elif fvg['type'] == 'Bearish':
                # Did we rise into it? High >= Bottom and Low <= Top
                if high >= fvg['bottom'] and low <= fvg['top']:
                    # Did we respect it? Close <= Top (Didn't close above gap)
                    if close <= fvg['top']:
                        # Valid Bearish Rejection
                        bias = "Bearish"
                        reason = f"Respected Bearish FVG from {df['datetime'].iloc[fvg['created_at']].date()}"
                        break
        
        # Outcome
        if bias != "Neutral":
            next_open = df['open'].iloc[i+1]
            next_close = df['close'].iloc[i+1]
            change = next_close - next_open
            
            win = False
            if bias == "Bullish" and change > 0: win = True
            if bias == "Bearish" and change < 0: win = True
            
            results.append({
                "Date": current_date.strftime("%Y-%m-%d"),
                "Bias": bias,
                "Reason": reason,
                "Outcome": "Win" if win else "Loss",
                "PnL_Points": change if bias == "Bullish" else -change
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
        print(f"Concepts: PD Array (FVG) Rejection")
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
    
    backtest_fvg_rejection(args.ticker)
