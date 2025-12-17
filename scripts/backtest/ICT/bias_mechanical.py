
import pandas as pd
import numpy as np
import os
import argparse
import sys
from datetime import timedelta, time

# Define paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(ROOT_DIR, "data")

def load_data(ticker, timeframe="15m"):
    path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
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
        
    # Sort
    if 'datetime' in df.columns:
        df = df.sort_values('datetime').reset_index(drop=True)
    else:
        print("Error: Could not identify datetime column")
        sys.exit(1)
        
    return df

def backtest_mechanical_bias(ticker):
    print(f"Backtesting Mechanical Bias (Asia/London) for {ticker}...")
    
    # 1. Load Intraday Data (15m is good for session logic)
    df = load_data(ticker, "15m")
    
    # Filter recent years
    df = df[df['datetime'] >= '2022-01-01'].reset_index(drop=True)
    
    # 2. Resample to Daily for Context (Prev Day Close > Open)
    # We need a quick way to look up Daily context.
    df['date'] = df['datetime'].dt.date
    
    daily_agg = df.groupby('date').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })
    daily_agg['direction'] = np.where(daily_agg['close'] > daily_agg['open'], 'Bullish', 'Bearish')
    
    # Shift daily so date T has info about T-1
    daily_agg['prev_direction'] = daily_agg['direction'].shift(1)
    
    # 3. Iterate through Days
    unique_dates = df['date'].unique()
    
    results = []
    wins = 0; losses = 0; total = 0
    
    for current_date in unique_dates:
        # Get Daily Context
        if current_date not in daily_agg.index: continue
        
        context = daily_agg.loc[current_date]
        prev_dir = context['prev_direction']
        
        if pd.isna(prev_dir): continue
        
        # Get Intraday Data for this day
        # Note: Futures Session is complex (opens prev evening).
        # We need data from 18:00 previous day to 17:00 current day.
        # But 'date' column might be strictly calendar date in some datasets.
        # Let's assume standard EST conversion has happened or we handle timestamps.
        
        # Define Session Times (Approx EST)
        # Asia: 18:00 (Prev) - 00:00 (Curr) or 18:00 - 02:00? 
        # User: "London Session (typically 2:00 AM to 5:00 AM EST)"
        # So Asia is before 02:00. Let's say 18:00 - 02:00.
        
        # Filtering data for "Today's Session" requires careful timestamp logic w.r.t UTC/EST.
        # Assuming timestamps are local exchange time (CT/ET).
        # Let's look at 00:00 to 02:00 as late Asia, and 18:00-00:00 prev day as Early Asia?
        # Simplify: Look at 00:00 - 08:30 Period on Current Date.
        
        day_data = df[df['date'] == current_date]
        if day_data.empty: continue
        
        # Define Time Windows
        t_asia_end = time(2, 0)
        t_london_start = time(2, 0)
        t_london_end = time(5, 0)
        t_ny_open = time(8, 30) # Funding / Bias Confirmation Time
        
        # Extract Sessions
        # Asia (Using 00:00 to 02:00 for simplicity of filtering single day object, 
        # ideally should include prev evening but let's test strict calendar first).
        asia_data = day_data[day_data['datetime'].dt.time < t_asia_end] 
        london_data = day_data[(day_data['datetime'].dt.time >= t_london_start) & (day_data['datetime'].dt.time < t_london_end)]
        
        if asia_data.empty or london_data.empty: continue
        
        asia_high = asia_data['high'].max()
        asia_low = asia_data['low'].min()
        
        london_high = london_data['high'].max()
        london_low = london_data['low'].min()
        
        bias = "Neutral"
        reason = ""
        
        # Logic: 
        # Bullish Bias:
        # 1. Prev Day was Bullish (Order Flow).
        # 2. London Sweeps Asia Low (Judas).
        # 3. MSS (Simplified): London Close > Asia Low? Or simply London Low < Asia Low.
        
        # STRICT CONDITION FROM USER:
        # "London Session sweeps (takes out) the Sell-Side Liquidity (e.g., the Asian Session Low)"
        
        # Bullish Setup
        if prev_dir == "Bullish":
            if london_low < asia_low:
                # Sweep Confirmed.
                # MSS: Did we bounce? 
                # Let's check if the *last* price of London session is > Asia Low (Reclaiming the range)
                # Or check 08:30 open price?
                
                # User: "Following the sweep, price shows a clear Market Structure Shift"
                # Simplify: Did London Close (05:00 bar) close > Asia Low? (False Breakout)
                london_close = london_data['close'].iloc[-1]
                
                if london_close > asia_low:
                    bias = "Bullish"
                    reason = "Prev Bullish + London Swept Asia Low & Reclaimed"
        
        # Bearish Setup
        elif prev_dir == "Bearish":
            if london_high > asia_high:
                # Sweep Confirmed
                london_close = london_data['close'].iloc[-1]
                if london_close < asia_high: # False breakout
                    bias = "Bearish"
                    reason = "Prev Bearish + London Swept Asia High & Reclaimed"
        
        # Outcome
        if bias != "Neutral":
            # Measure NY Session Expansion (08:30 to Close)
            ny_data = day_data[day_data['datetime'].dt.time >= t_ny_open]
            if not ny_data.empty:
                ny_open = ny_data['open'].iloc[0]
                ny_close = ny_data['close'].iloc[-1]
                change = ny_close - ny_open
                
                win = False
                if bias == "Bullish" and change > 0: win = True
                if bias == "Bearish" and change < 0: win = True
                
                results.append({
                    "Date": current_date,
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
        print(f"Concepts: Mechanical Intraday Bias (London Judas)")
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
    
    backtest_mechanical_bias(args.ticker)
