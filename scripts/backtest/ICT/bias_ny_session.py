
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
    # Handle case
    if not os.path.exists(path):
        if timeframe == "1d": path = os.path.join(DATA_DIR, f"{ticker}_1D.parquet")
        if timeframe == "1h": path = os.path.join(DATA_DIR, f"{ticker}_1H.parquet")
        if timeframe == "15m": path = os.path.join(DATA_DIR, f"{ticker}_15m.parquet")
        
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

def find_fvgs(df):
    fvgs = []
    for i in range(2, len(df)):
        dt = df['datetime'].iloc[i]
        # Bullish
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            fvgs.append({
                'type': 'Bullish',
                'top': df['low'].iloc[i],
                'bottom': df['high'].iloc[i-2],
                'created_at': dt
            })
        # Bearish
        if df['high'].iloc[i] < df['low'].iloc[i-2]:
            fvgs.append({
                'type': 'Bearish',
                'top': df['low'].iloc[i-2],
                'bottom': df['high'].iloc[i],
                'created_at': dt
            })
    return fvgs

def backtest_ny_session(ticker):
    print(f"Backtesting NY Session Bias (Liq Sweep + 1H FVG) for {ticker}...")
    
    # Load Data
    df_15m = load_data(ticker, "15m")
    df_1h = load_data(ticker, "1h")
    df_1d = load_data(ticker, "1d")
    
    # Filter 2022
    start_date = pd.Timestamp("2022-01-01")
    
    # Check if df is tz-aware and localize start_date if needed
    if df_15m['datetime'].dt.tz is not None:
        start_date = start_date.tz_localize(df_15m['datetime'].dt.tz)
        
    df_15m = df_15m[df_15m['datetime'] >= start_date].reset_index(drop=True)
    
    # Handle others
    if df_1h['datetime'].dt.tz is not None:
        # Re-create or convert if different tz? Assume consistent source.
        # Just in case one is None and other is Not:
        start_date_1h = pd.Timestamp("2022-01-01").tz_localize(df_1h['datetime'].dt.tz)
        df_1h = df_1h[df_1h['datetime'] >= start_date_1h].reset_index(drop=True)
    else:
        df_1h = df_1h[df_1h['datetime'] >= pd.Timestamp("2022-01-01")].reset_index(drop=True)
        
    if df_1d['datetime'].dt.tz is not None:
        start_date_1d = pd.Timestamp("2022-01-01").tz_localize(df_1d['datetime'].dt.tz)
        df_1d = df_1d[df_1d['datetime'] >= start_date_1d].reset_index(drop=True)
    else:
        df_1d = df_1d[df_1d['datetime'] >= pd.Timestamp("2022-01-01")].reset_index(drop=True)
    
    # Identify 1H FVGs
    # Need full history for context really, but let's assume filtering 2022 is fine if we warm up
    # Actually, we should load more 1H data to have pre-existing FVGs.
    # But for simplicity, we start finding them from 2022.
    fvgs_1h = find_fvgs(df_1h)
    
    # Pre-calculate Daily Levels
    df_1d['PDH'] = df_1d['high'].shift(1)
    df_1d['PDL'] = df_1d['low'].shift(1)
    # Weekly? 
    # Simplify: Use PDH/L and Session Levels first.
    
    results = []
    wins = 0; losses = 0; total = 0
    
    # Iterate Days
    unique_dates = df_15m['datetime'].dt.date.unique()
    
    for date_obj in unique_dates:
        # Get Daily Context
        day_daily = df_1d[df_1d['datetime'].dt.date == date_obj]
        if day_daily.empty: continue
        
        pdh = day_daily['PDH'].iloc[0]
        pdl = day_daily['PDL'].iloc[0]
        if pd.isna(pdh) or pd.isna(pdl): continue
        
        # Get Intraday Data
        day_15m = df_15m[df_15m['datetime'].dt.date == date_obj]
        
        # Define Sessions
        # Asia: < 02:00 (Approx)
        # London: 02:00 - 08:00
        # NY AM: 09:30 - 12:00 (Trigger Window)
        
        t_asia_end = time(2, 0)
        t_london_start = time(2, 0)
        t_london_end = time(8, 0)
        t_ny_start = time(9, 30)
        t_ny_end = time(12, 0)
        
        asia_data = day_15m[day_15m['datetime'].dt.time < t_asia_end]
        london_data = day_15m[(day_15m['datetime'].dt.time >= t_london_start) & (day_15m['datetime'].dt.time < t_london_end)]
        ny_data = day_15m[(day_15m['datetime'].dt.time >= t_ny_start) & (day_15m['datetime'].dt.time < t_ny_end)]
        
        if asia_data.empty or london_data.empty or ny_data.empty: continue
        
        levels = {
            'PDH': pdh,
            'PDL': pdl,
            'AsiaHigh': asia_data['high'].max(),
            'AsiaLow': asia_data['low'].min(),
            'LondonHigh': london_data['high'].max(),
            'LondonLow': london_data['low'].min()
        }
        
        # Identify Active 1H FVGs (Created before NY Open today)
        ny_open_dt = pd.Timestamp.combine(date_obj, t_ny_start)
        
        # Check if FVG created_at is tz-aware
        if fvgs_1h and fvgs_1h[0]['created_at'].tzinfo is not None:
             if ny_open_dt.tzinfo is None:
                 ny_open_dt = ny_open_dt.tz_localize(fvgs_1h[0]['created_at'].tzinfo)
        elif ny_open_dt.tzinfo is not None:
              # If ny_open_dt is aware but FVG is naive? Unlikely if we localized df_1h.
              pass

        active_fvgs = [f for f in fvgs_1h if f['created_at'] < ny_open_dt]
        # Sort by recency
        active_fvgs.sort(key=lambda x: x['created_at'], reverse=True)
        # Keep recent 20
        active_fvgs = active_fvgs[:20]
        
        bias = "Neutral"
        reason = ""
        entry_price = 0
        
        # Check NY Price Action for PATTERN:
        # 1. Sweep Liquidity Level
        # 2. Inside Opposing FVG
        
        # We iterate through NY bars to find the "Trigger"
        for idx, row in ny_data.iterrows():
            curr_high = row['high']
            curr_low = row['low']
            curr_close = row['close']
            
            # Check Bearish Trigger (Sweep Highs + Tap Bearish FVG)
            swept_levels = [name for name, val in levels.items() if curr_high > val] # We went above level
            # Limit sweep? We want to have gone above, but maybe close back below?
            # Or just "Price is currently above a liquidity level" AND "Price is inside Bearish FVG"
            
            if swept_levels:
                # Are we inside a Bearish FVG?
                for fvg in active_fvgs:
                    if fvg['type'] == 'Bearish':
                        if curr_high >= fvg['bottom'] and curr_low <= fvg['top']:
                             # Overlap!
                             bias = "Bearish"
                             reason = f"Swept {swept_levels[0]} + Tap 1H Bearish FVG"
                             entry_price = curr_close # Assume entry at close of trigger bar
                             break
            
            if bias != "Neutral": break
            
            # Check Bullish Trigger (Sweep Lows + Tap Bullish FVG)
            swept_levels_low = [name for name, val in levels.items() if curr_low < val]
            
            if swept_levels_low:
                 for fvg in active_fvgs:
                    if fvg['type'] == 'Bullish':
                        if curr_low <= fvg['top'] and curr_high >= fvg['bottom']:
                            bias = "Bullish"
                            reason = f"Swept {swept_levels_low[0]} + Tap 1H Bullish FVG"
                            entry_price = curr_close
                            break
            
            if bias != "Neutral": break
            
        # Outcome: PnL from Entry to EOD Close
        if bias != "Neutral":
            eod_close = day_15m['close'].iloc[-1] # Close of the day (16:00 or 17:00)
            
            change = eod_close - entry_price
            
            win = False
            if bias == "Bullish" and change > 0: win = True
            if bias == "Bearish" and change < 0: win = True
            
            pnl = change if bias == "Bullish" else -change
            
            results.append({
                "Date": date_obj,
                "Bias": bias,
                "Reason": reason,
                "Entry": entry_price,
                "Exit": eod_close,
                "Outcome": "Win" if win else "Loss",
                "PnL": pnl
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
    print(f"Concepts: NY Session Liquidity Sweep + 1H FVG")
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
    backtest_ny_session(args.ticker)
