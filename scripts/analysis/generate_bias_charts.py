
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import numpy as np
from datetime import timedelta, time

# Constants
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
DATA_DIR = os.path.join(ROOT_DIR, "data")
OUTPUT_DIR = os.path.join(ROOT_DIR, "charts", "bias_concepts_5m")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_data(ticker="NQ1", timeframe="5m"):
    path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
    print(f"Loading data from: {path}")
    if not os.path.exists(path): 
        print("File not found. Falling back to 15m if 5m missing.")
        path = os.path.join(DATA_DIR, f"{ticker}_15m.parquet")
        if not os.path.exists(path): return pd.DataFrame()
        
    df = pd.read_parquet(path)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")
    
    # Handle Timerframe
    if 'datetime' not in df.columns:
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s')
        elif 'Time' in df.columns:
            df['datetime'] = pd.to_datetime(df['Time'])
        elif isinstance(df.index, pd.DatetimeIndex):
            df['datetime'] = df.index
            
    if 'datetime' not in df.columns:
        print("Error: Could not find datetime column.")
        return pd.DataFrame()
    
    # Ensure UTC then Convert to EST
    if df['datetime'].dt.tz is None:
        df['datetime'] = df['datetime'].dt.tz_localize('UTC')
    
    df['datetime'] = df['datetime'].dt.tz_convert('US/Eastern')
    
    df = df.sort_values('datetime').reset_index(drop=True)
    return df

def get_session_data(df, date_obj):
    # Date obj matches the EST date
    start_dt = pd.Timestamp.combine(date_obj, time(0, 0)).tz_localize('US/Eastern')
    end_dt = pd.Timestamp.combine(date_obj, time(16, 0)).tz_localize('US/Eastern')
    return df[(df['datetime'] >= start_dt) & (df['datetime'] <= end_dt)].copy()

def identify_level_bounce(low_price, levels, tolerance=10.0):
    match = []
    for name, price in levels.items():
        if price is None: continue
        if abs(low_price - price) <= tolerance:
            match.append(name)
    return ", ".join(match) if match else "No Key Level"

def plot_chart(df_day, title, filename, levels={}, date_obj=None):
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # Plot Candles
    width = 1.0/(24*12*1.5) # thin for 5m

    up = df_day[df_day['close'] >= df_day['open']]
    down = df_day[df_day['close'] < df_day['open']]
    
    # Convert dates to mdates
    ax.bar(up['datetime'], up['close'] - up['open'], width, bottom=up['open'], color='green', alpha=0.8)
    ax.vlines(up['datetime'], up['low'], up['high'], color='green', linewidth=1)
    
    ax.bar(down['datetime'], down['close'] - down['open'], width, bottom=down['open'], color='red', alpha=0.8)
    ax.vlines(down['datetime'], down['low'], down['high'], color='red', linewidth=1)
    
    # Plot Levels
    for name, price in levels.items():
        if price is None: continue
        color = 'black'
        style = '--'
        if 'Open' in name: color='blue'; style='-'
        if 'High' in name: color='red'; style=':'
        if 'Low' in name: color='green'; style=':'
        if 'P12' in name: color='purple'; style='-.'
        
        ax.axhline(price, linestyle=style, color=color, alpha=0.6, label=name)
        
    # Vertical Line at 09:30 EST
    if date_obj:
        t930 = pd.Timestamp.combine(date_obj, time(9, 30)).tz_localize('US/Eastern')
        ax.axvline(t930, color='orange', linestyle='-', linewidth=1.5, label='09:30 Open')
        
    ax.set_title(title)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=df_day['datetime'].dt.tz))
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    
    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path)
    plt.close()
    print(f"Saved {path}")

def find_and_plot_examples(ticker="NQ1"):
    df = load_data(ticker, "5m") # Try 5m
    if df.empty: return

    # Filter 2023+
    start_date = pd.Timestamp("2023-01-01").tz_localize('US/Eastern')
    df = df[df['datetime'] >= start_date]
    
    unique_dates = df['datetime'].dt.date.unique()
    
    concepts = [
        {"name": "Expansion_Long", "found": 0, "limit": 5},
        {"name": "Reversal_Buy", "found": 0, "limit": 5}
    ]
    
    print(f"Scanning {len(unique_dates)} days...")
    for date_obj in reversed(unique_dates):
        if all(c['found'] >= c['limit'] for c in concepts): break
        
        session = get_session_data(df, date_obj)
        if session.empty: continue
        
        # Levels
        midnight_open = None
        mr = session[session['datetime'].dt.time == time(0, 0)]
        if not mr.empty: midnight_open = mr['open'].iloc[0]
        
        # London High/Low (02:00-05:00 EST)
        lon_start = pd.Timestamp.combine(date_obj, time(2, 0)).tz_localize('US/Eastern')
        lon_end = pd.Timestamp.combine(date_obj, time(5, 0)).tz_localize('US/Eastern')
        lon_df = session[(session['datetime'] >= lon_start) & (session['datetime'] < lon_end)]
        
        lon_high = lon_df['high'].max() if not lon_df.empty else None
        lon_low = lon_df['low'].min() if not lon_df.empty else None
        
        # Approx P12 Low (Lowest point between 18:00 prev and 09:30 curr?)
        # Let's use overnight low (00:00 - 09:30) as proxy for "Low to break"
        pre_ny = session[session['datetime'].dt.time < time(9, 30)]
        overnight_low = pre_ny['low'].min() if not pre_ny.empty else None
        
        # NY Session
        ny_start = pd.Timestamp.combine(date_obj, time(9, 30)).tz_localize('US/Eastern')
        ny_data = session[session['datetime'] >= ny_start]
        if ny_data.empty: continue
        
        ny_open = ny_data['open'].iloc[0]
        ny_high = ny_data['high'].max()
        ny_low = ny_data['low'].min()
        day_close = session['close'].iloc[-1]
        day_low = session['low'].min()
        
        # Identify what the Day Low bounced off
        # We check Midnight Open, London Low, P12/Overnight Low (as support)
        # Note: P12 Low usually calculated from 18:00-06:00.
        # Let's approximate P12 Low as Overnight Low for checking bounces
        # Or better: check open/closes.
        
        levels = {}
        if midnight_open: levels['Midnight Open'] = midnight_open
        if lon_high: levels['London High'] = lon_high
        if lon_low: levels['London Low'] = lon_low
        if overnight_low: levels['Overnight Low'] = overnight_low # Proxy P12 Low
        
        bounce_source = identify_level_bounce(day_low, levels, tolerance=15.0) # 15 pts tolerance for NQ
        
        # 1. Expansion Long
        c = concepts[0]
        if c['found'] < c['limit']:
            if midnight_open and lon_high:
                if ny_open < midnight_open: # Open Low
                     if ny_high > lon_high: # Break High
                         if day_close > ny_open: # Green Day
                             plot_chart(session, f"Expansion Long {date_obj}\nLow Bounced: {bounce_source}", 
                                       f"expansion_long_{date_obj}.png", levels, date_obj)
                             c['found'] += 1
                             continue
                             
        # 2. Reversal Buy
        c = concepts[1]
        if c['found'] < c['limit']:
            if overnight_low:
                # Price breaks overnight low then rallies?
                # Or just check if Low Bounced off something specific?
                if day_low < overnight_low: # Swept Overnight Low
                    if day_close > ny_open: # Green Day
                         plot_chart(session, f"Reversal Buy {date_obj}\nSwept Overnight Low + Close Green", 
                                   f"reversal_buy_{date_obj}.png", levels, date_obj)
                         c['found'] += 1
                         continue

if __name__ == "__main__":
    print("Starting 5m Chart Generation...")
    find_and_plot_examples()
    print("Done.")
