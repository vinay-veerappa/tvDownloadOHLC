
import pandas as pd
import numpy as np
import os
import argparse
import sys
from datetime import timedelta

# Define paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(ROOT_DIR, "data")

def load_data(ticker, timeframe):
    path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
    # Handle case differences
    if not os.path.exists(path):
        if timeframe == "1d": path = os.path.join(DATA_DIR, f"{ticker}_1D.parquet")
        if timeframe == "1h": path = os.path.join(DATA_DIR, f"{ticker}_1H.parquet")
        
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

def find_fvgs(df, tf_label):
    fvgs = []
    for i in range(2, len(df)):
        # Bullish FVG
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            fvgs.append({
                'type': 'Bullish',
                'top': df['low'].iloc[i],
                'bottom': df['high'].iloc[i-2],
                'created_at': df['datetime'].iloc[i], # Use datetime instead of index
                'tf': tf_label
            })
            
        # Bearish FVG
        if df['high'].iloc[i] < df['low'].iloc[i-2]:
            fvgs.append({
                'type': 'Bearish',
                'top': df['low'].iloc[i-2],
                'bottom': df['high'].iloc[i],
                'created_at': df['datetime'].iloc[i],
                'tf': tf_label
            })
    return fvgs

def run_mtf_test(ticker, timeframes, mode="single"):
    print(f"Backtesting {mode} FVG Bias ({', '.join(timeframes)}) for {ticker}...")
    
    # 1. Load Data
    data_map = {}
    fvg_map = {}
    
    # Load Daily for "Outcome" testing (The Price Action we trade)
    daily_df = load_data(ticker, "1d")
    daily_df = daily_df[daily_df['datetime'] >= '2022-01-01'].reset_index(drop=True)
    
    # Load Context Data (FVG Sources)
    for tf in timeframes:
        if tf == "1d": 
            df = daily_df.copy() # Reuse
        else:
            df = load_data(ticker, tf)
            df = df[df['datetime'] >= '2021-12-01'] # Need context slightly earlier
            
        data_map[tf] = df
        fvg_map[tf] = find_fvgs(df, tf)
        print(f"  {tf}: Found {len(fvg_map[tf])} FVGs")

    # 2. Iterate Daily Bars
    results = []
    wins = 0; losses = 0; total = 0
    respected_count = 0
    tap_count = 0
    
    for i in range(1, len(daily_df) - 1):
        current_date = daily_df['datetime'].iloc[i]
        low = daily_df['low'].iloc[i]
        high = daily_df['high'].iloc[i]
        close = daily_df['close'].iloc[i]
        
        bias = "Neutral"
        reason_list = []
        
        # Collect Active FVGs from all requested timeframes
        active_fvgs = []
        for tf in timeframes:
            # Filter FVGs created BEFORE this day
            # Simple check: created_at < current_date (ignore time for daily source, strictly <)
            valid = [f for f in fvg_map[tf] if f['created_at'] < current_date]
            
            # Optimization: Filter by recentness (e.g. last 30 days)
            # valid = [f for f in valid if (current_date - f['created_at']).days < 30]
            active_fvgs.extend(valid)
            
        # Logic
        # Mode "single": Just needs to tap ANY valid FVG in the list.
        # Mode "nested": Needs to tap FVGs from ALL timeframes simultaneously (Overlap).
        # Mode "combo": (Daily+1H) -> Nested.
        
        # Let's find "Touching" FVGs
        touching_bullish = []
        touching_bearish = []
        
        for fvg in active_fvgs:
            # Bullish: Low <= Top and High >= Bottom
            if fvg['type'] == 'Bullish':
                if low <= fvg['top'] and high >= fvg['bottom']:
                    touching_bullish.append(fvg)
            # Bearish: High >= Bottom and Low <= Top
            elif fvg['type'] == 'Bearish':
                if high >= fvg['bottom'] and low <= fvg['top']:
                    touching_bearish.append(fvg)
                    
        # Apply Mode Logic
        selected_bias = "Neutral"
        
        has_bullish = False
        has_bearish = False
        
        if mode == "nested":
            # Must have at least one FVG from EACH requested timeframe in the touching list
            # Group touching by TF
            tfs_bull = set(f['tf'] for f in touching_bullish)
            tfs_bear = set(f['tf'] for f in touching_bearish)
            
            if len(tfs_bull) == len(timeframes): has_bullish = True
            if len(tfs_bear) == len(timeframes): has_bearish = True
            
        else: # any / single
            if touching_bullish: has_bullish = True
            if touching_bearish: has_bearish = True
            
        # Respect Logic check
        # Only valid if we RESPECT the level.
        # Bullish: Close >= Bottom of "key" FVG.
        # Which FVG is key? The strict one (inner) or outer?
        # Logic: If we are bullish, we shouldn't close below the LOWEST bottom of the engaged FVGs?
        # Or just "don't close below the Daily FVG bottom"?
        
        # Simplified Respect:
        # If Bullish Signal: Close >= Combined Bottom (min bottom of touched FVGs) ? No, that's too loose.
        # Close >= Combined Bottom (max bottom)? Safer.
        
        if has_bullish and not has_bearish:
            # Check Respect
            # Let's verify we didn't crash through ALL of them.
            # Conservative: Must close ABOVE the lowest bottom of the engaged group.
            limit = min(f['bottom'] for f in touching_bullish)
            if close >= limit:
                selected_bias = "Bullish"
                reason_list = [f"{f['tf']} {f['type']}" for f in touching_bullish]
                tap_count += 1
                respected_count += 1
            else:
                tap_count += 1 # Failed tap
                
        elif has_bearish and not has_bullish:
             limit = max(f['top'] for f in touching_bearish)
             if close <= limit:
                 selected_bias = "Bearish"
                 reason_list = [f"{f['tf']} {f['type']}" for f in touching_bearish]
                 tap_count += 1
                 respected_count += 1
             else:
                 tap_count += 1

        # Outcome Verification
        if selected_bias != "Neutral":
            next_open = daily_df['open'].iloc[i+1]
            next_close = daily_df['close'].iloc[i+1]
            change = next_close - next_open
            
            win = False
            if selected_bias == "Bullish" and change > 0: win = True
            if selected_bias == "Bearish" and change < 0: win = True
            
            results.append({
                "Date": current_date.date(),
                "Mode": mode,
                "Bias": selected_bias,
                "Outcome": "Win" if win else "Loss",
                "PnL": change if selected_bias == "Bullish" else -change
            })
            
            if win: wins += 1
            else: losses += 1
            total += 1

    # Report
    win_rate = (wins / total * 100) if total > 0 else 0
    res_rate = (respected_count / tap_count * 100) if tap_count > 0 else 0
    
    total_pnl = 0
    if results:
         total_pnl = pd.DataFrame(results)['PnL'].sum()

    print(f"\nResults ({mode} {timeframes}):")
    print(f"Active Taps: {tap_count} | Respected: {respected_count} ({res_rate:.1f}%)")
    print(f"Bias Trades: {total} | Win Rate: {win_rate:.2f}% | PnL: {total_pnl:.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker")
    parser.add_argument("--tfs", nargs="+", default=["1d"], help="Timeframes (1d 4h 1h)")
    parser.add_argument("--mode", default="single", choices=["single", "nested"], help="Mode")
    
    args = parser.parse_args()
    run_mtf_test(args.ticker, args.tfs, args.mode)
