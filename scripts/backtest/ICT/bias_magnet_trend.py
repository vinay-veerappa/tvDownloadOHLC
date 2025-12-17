
import pandas as pd
import numpy as np
import os
import argparse
import sys

# Define paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(ROOT_DIR, "data")

def load_data(ticker):
    # Daily Data Only for this Model (Magnet Strength)
    path = os.path.join(DATA_DIR, f"{ticker}_1d.parquet")
    if not os.path.exists(path):
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
    return df

def identify_structure_and_fvgs(df):
    """
    Returns DataFrame with 'trend' column and list of FVGs.
    """
    # 1. Identify Swings (3-bar)
    df['swing_high'] = False
    df['swing_low'] = False
    
    window = 3
    for i in range(window, len(df) - window):
        if all(df['high'].iloc[i] > df['high'].iloc[i-k] for k in range(1, window+1)) and \
           all(df['high'].iloc[i] > df['high'].iloc[i+k] for k in range(1, window+1)):
            df.at[i, 'swing_high'] = True
            
        if all(df['low'].iloc[i] < df['low'].iloc[i-k] for k in range(1, window+1)) and \
           all(df['low'].iloc[i] < df['low'].iloc[i+k] for k in range(1, window+1)):
            df.at[i, 'swing_low'] = True
            
    # 2. Determine Trend via MSS (Displacement)
    swing_highs = df[df['swing_high']].index.tolist()
    swing_lows = df[df['swing_low']].index.tolist()
    
    trend = pd.Series("Neutral", index=df.index)
    curr_trend = "Neutral"
    
    # Simple MSS Logic iteration
    for i in range(20, len(df)):
        close = df['close'].iloc[i]
        
        # Check Breaks
        last_high = next((s for s in reversed(swing_highs) if s < i), None)
        last_low = next((s for s in reversed(swing_lows) if s < i), None)
        
        if last_high and close > df['high'].iloc[last_high]:
            curr_trend = "Bullish"
        elif last_low and close < df['low'].iloc[last_low]:
            curr_trend = "Bearish"
            
        trend.iloc[i] = curr_trend
        
    df['trend'] = trend
    
    # 3. Identify FVGs
    fvgs = []
    for i in range(2, len(df)):
        dt = df['datetime'].iloc[i]
        # Bullish
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            fvgs.append({
                'type': 'Bullish',
                'top': df['low'].iloc[i],
                'bottom': df['high'].iloc[i-2],
                'created_at': i, # Use index for easier proximity check
                'created_dt': dt
            })
        # Bearish
        if df['high'].iloc[i] < df['low'].iloc[i-2]:
            fvgs.append({
                'type': 'Bearish',
                'top': df['low'].iloc[i-2],
                'bottom': df['high'].iloc[i],
                'created_at': i,
                'created_dt': dt
            })
            
    return df, fvgs

def backtest_magnet_trend(ticker):
    print(f"Backtesting Magnet Trend Bias for {ticker}...")
    
    # Load and Filter
    df = load_data(ticker)
    df = df[df['datetime'] >= '2021-01-01'].reset_index(drop=True) # Start earlier for structure
    
    df, all_fvgs = identify_structure_and_fvgs(df)
    
    # Filter backtest period
    start_viz = df[df['datetime'] >= '2022-01-01'].index[0]
    
    results = []
    wins = 0; losses = 0; total = 0
    neutral_count = 0
    
    for i in range(start_viz, len(df) - 1):
        current_date = df['datetime'].iloc[i]
        close = df['close'].iloc[i]
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        trend = df['trend'].iloc[i]
        
        bias = "Neutral" # Default to Neutral if Obstructed
        reason = ""
        
        # "Magnets" are Opposing Arrays.
        # If Bullish, Magnet is Bearish FVG.
        # If Bearish, Magnet is Bullish FVG.
        
        # 1. Filter Relevant Active FVGs
        # Created in past (< i) and relatively recent?
        # Let's say last 100 days to keep them relevant magnets
        active_fvgs = [f for f in all_fvgs if f['created_at'] < i and (i - f['created_at']) < 200]
        
        obstruction = False
        
        if trend == "Bullish":
            # Check if OBSTRUCTED by Bearish FVG
            # Are we Inside or At a Bearish FVG?
            # Bearish FVG bounds: [bottom, top]
            # Since it's overhead, usually we approach from bottom.
            
            # Check all active Bearish FVGs
            bearish_magnets = [f for f in active_fvgs if f['type'] == 'Bearish']
            
            # Distance check?
            # If we are effectively "Mitigating" it right now.
            # Close is inside FVG range?
            for fvg in bearish_magnets:
                # If Price is inside FVG
                if close >= fvg['bottom'] and close <= fvg['top']:
                    obstruction = True
                    reason = f"Inside Bearish FVG (Obstruction) from {fvg['created_dt'].date()}"
                    break
                # Or if we just tapped it and rejected? 
                
            if not obstruction:
                # Room to run! Magnets are drawing price UP, but we haven't hit the wall yet.
                bias = "Bullish"
                reason = "Bullish Trend + Unobstructed"
                
        elif trend == "Bearish":
            # Check Obstruction by Bullish FVG (Support)
            bullish_magnets = [f for f in active_fvgs if f['type'] == 'Bullish']
            
            for fvg in bullish_magnets:
                if close >= fvg['bottom'] and close <= fvg['top']:
                    obstruction = True
                    reason = f"Inside Bullish FVG (Obstruction) from {fvg['created_dt'].date()}"
                    break
                    
            if not obstruction:
                bias = "Bearish"
                reason = "Bearish Trend + Unobstructed"
                
        # Result
        if bias != "Neutral":
            next_open = df['open'].iloc[i+1]
            next_close = df['close'].iloc[i+1]
            change = next_close - next_open
            
            win = False
            if bias == "Bullish" and change > 0: win = True
            if bias == "Bearish" and change < 0: win = True
            
            results.append({
                "Date": current_date.date(),
                "Bias": bias,
                "Reason": reason,
                "Outcome": "Win" if win else "Loss",
                "PnL": change if bias == "Bullish" else -change
            })
            if win: wins += 1
            else: losses += 1
            total += 1
        else:
            neutral_count += 1
            
    # Report
    win_rate = (wins / total * 100) if total > 0 else 0
    total_pnl = 0
    if results:
         total_pnl = pd.DataFrame(results)['PnL'].sum()

    print(f"\n--- Results for {ticker} ---")
    print(f"Concepts: Trend + FVG Magnet/Obstruction Model")
    print(f"Total Bias Trades: {total} (Neutral/Obstructed days: {neutral_count})")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total PnL: {total_pnl:.2f} pts")
    
    if results:
        print("\nLast 5 Days:")
        print(pd.DataFrame(results).tail(5).to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="NQ1", help="Ticker")
    args = parser.parse_args()
    backtest_magnet_trend(args.ticker)
