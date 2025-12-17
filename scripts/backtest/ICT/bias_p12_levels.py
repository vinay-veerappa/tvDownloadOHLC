
import pandas as pd
import numpy as np
import os
import argparse
import sys
import json
from datetime import timedelta, time

# Define paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(ROOT_DIR, "data")

def load_p12_levels(ticker):
    # Load profiler json
    path = os.path.join(DATA_DIR, f"{ticker}_profiler.json")
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        return []
        
    with open(path, 'r') as f:
        data = json.load(f)
        
    # Extract extensions -> P12?
    # User mentioned "P12 levels". The structure might be inside 'extensions'.
    # Inspecting previous `type` command output or similar:
    # "extensions": { "p12": [ { "start_time": ..., "level": ... } ] }
    # Or maybe the root array IS the levels?
    # Let's assume the JSON structure based on standard usage or inspect it.
    # The previous `head` showed standard session objects. P12 is likely a key or separate file.
    # Wait, the user mentioned P12 levels from `*_profiler.json`.
    # Let's try to find keys related to levels.
    # If standard structure is list of objects, maybe we look for specific fields.
    
    # Re-reading user context: "P12 levels" might be "extensions" -> "p12" or similar.
    # Let's generic search for "p12" key in the loaded dict.
    
    levels = []
    
    if isinstance(data, dict):
        if "extensions" in data:
            ext = data["extensions"]
            if "p12" in ext:
                levels = ext["p12"]
        elif "p12" in data:
            levels = data["p12"]
            
    # Normalize levels
    # Expecting: { "start_time": iso_str, "end_time": iso_str, "price": float, "type": "support/resistance"? }
    # Or strictly price levels.
    
    # If structure is unknown, let's look for "level" or "price" keys in whatever list we found.
    parsed = []
    for l in levels:
        try:
            # Parse time
            start = pd.Timestamp(l.get("start_time"))
            end = pd.Timestamp(l.get("end_time")) if l.get("end_time") else pd.Timestamp.max.replace(tzinfo=start.tzinfo)
            price = float(l.get("level", l.get("price", 0)))
            if price > 0:
                parsed.append({
                    "start": start,
                    "end": end,
                    "price": price
                })
        except:
            continue
            
    return parsed

def load_data(ticker, timeframe):
    path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
    if not os.path.exists(path):
         if timeframe == "15m": path = os.path.join(DATA_DIR, f"{ticker}_15m.parquet")
    if not os.path.exists(path):
        sys.exit(1)
    df = pd.read_parquet(path)
    if isinstance(df.index, pd.DatetimeIndex): df = df.reset_index()
    # names
    df.columns = [c.lower() for c in df.columns]
    
    # datetime
    if 'time' in df.columns and 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
    elif 'datetime' not in df.columns:
         df.rename(columns={df.columns[0]: 'datetime'}, inplace=True)
         
    if df['datetime'].dt.tz is None:
        # Assume UTC? Or convert.
        pass
        
    df = df.sort_values('datetime').reset_index(drop=True)
    return df

def backtest_p12_interaction(ticker):
    print(f"Backtesting P12 Level Interaction (07:30 Open) for {ticker}...")
    
    # 1. Load P12 Levels
    # Note: `p12` structure is speculative. If empty, we fail gracefully.
    p12_levels = load_p12_levels(ticker)
    if not p12_levels:
        print("Warning: No P12 levels found or parsed in profiler.json. Checking simple structure...")
        # Fallback dump structure to debug if needed, but let's proceed.
        # Maybe use HOD/LOD as proxy if P12 missing? No, user specific request.
        return

    # 2. Load 15m Data
    df = load_data(ticker, "15m")
    
    # Filter 2022
    start_date = pd.Timestamp("2022-01-01")
    if df['datetime'].dt.tz is not None:
        start_date = start_date.tz_localize(df['datetime'].dt.tz)
        
        # Localize P12 levels too
        for p in p12_levels:
            if p['start'].tz is None:
                p['start'] = p['start'].tz_localize(df['datetime'].dt.tz)
            else:
                 p['start'] = p['start'].tz_convert(df['datetime'].dt.tz)
            
            if p['end'].tz is None and p['end'].year < 2200: # Max timestamp safety
                 p['end'] = p['end'].tz_localize(df['datetime'].dt.tz)
            elif p['end'].year < 2200:
                 p['end'] = p['end'].tz_convert(df['datetime'].dt.tz)

    df = df[df['datetime'] >= start_date].reset_index(drop=True)
    
    unique_dates = df['datetime'].dt.date.unique()
    
    results = []
    wins = 0; losses = 0; total = 0
    
    t_0730 = time(7, 30)
    
    PROXIMITY_THRESHOLD = 20.0 # Points tolerance (NQ)
    
    for date_obj in unique_dates:
        # Find 07:30 Open for this day
        day_mask = df['datetime'].dt.date == date_obj
        day_data = df[day_mask]
        
        if day_data.empty: continue
        
        target_bar = day_data[day_data['datetime'].dt.time == t_0730]
        if target_bar.empty:
             # Proximate bar
             after = day_data[day_data['datetime'].dt.time > t_0730]
             if after.empty: continue
             open_price = after['open'].iloc[0]
             current_dt = after['datetime'].iloc[0]
        else:
             open_price = target_bar['open'].iloc[0]
             current_dt = target_bar['datetime'].iloc[0]
             
        # Identify ACTIVE P12 levels
        # active if start < current < end
        active_levels = [l for l in p12_levels if l['start'] < current_dt and l['end'] > current_dt]
        
        if not active_levels: continue
        
        # Check interaction
        bias = "Neutral"
        reason = ""
        
        # Find nearest level
        # Calculate distances
        dists = [(abs(open_price - l['price']), l) for l in active_levels]
        dists.sort(key=lambda x: x[0])
        
        nearest_dist, nearest_lvl = dists[0]
        
        if nearest_dist <= PROXIMITY_THRESHOLD:
            # We are interacting!
            lvl_price = nearest_lvl['price']
            
            # Logic: Bounce vs Break
            # User Suggestion: "Open > Support -> Bullish"
            # If Open is ABOVE level (within tolerance), treat as Support -> Bullish
            # If Open is BELOW level (within tolerance), treat as Resistance -> Bearish
            
            if open_price > lvl_price:
                bias = "Bullish"
                reason = f"07:30 Open ({open_price}) supported by P12 ({lvl_price})"
            else:
                bias = "Bearish"
                reason = f"07:30 Open ({open_price}) resisted by P12 ({lvl_price})"
                
        # Outcome
        if bias != "Neutral":
            eod_close = day_data['close'].iloc[-1]
            change = eod_close - open_price
            
            win = False
            if bias == "Bullish" and change > 0: win = True
            if bias == "Bearish" and change < 0: win = True
            
            results.append({
                "Date": date_obj,
                "Bias": bias,
                "Dist": nearest_dist,
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
    print(f"Concepts: P12 Level Interaction (07:30 Open)")
    print(f"Total Triggers: {total}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total PnL: {total_pnl:.2f} pts")
    
    if results:
        print("\nLast 5 Trades:")
        print(pd.DataFrame(results).tail(5).to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="NQ1", help="Ticker")
    args = parser.parse_args()
    backtest_p12_interaction(args.ticker)
