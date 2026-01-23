import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import json
import os
import sys
from datetime import datetime, timedelta

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
try:
    from fused_data_loader import load_fused_data
except ImportError:
    # Fallback if running from a different relative path
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'utils'))
    from fused_data_loader import load_fused_data

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'derived', 'ict_nwog_ndog.json')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'analysis', 'charts')

def plot_verification_chart(ticker="NQ1", days=14):
    print(f"Loading data for {ticker}...")
    df = load_fused_data(ticker, timeframe="15m", require_historical=True)
    
    if df.empty:
        print("No data found.")
        return

    # Ensure UTC -> ET
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df.set_index('datetime', inplace=True)
    
    try:
        df.index = df.index.tz_convert('US/Eastern')
    except:
        df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
        
    # Filter for last N days
    start_date = pd.Timestamp.now(tz='US/Eastern') - timedelta(days=days)
    df = df[df.index >= start_date]
    
    print(f"Plotting data from {df.index[0]} to {df.index[-1]}")

    # Load Gaps
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            gaps_db = json.load(f)
        gaps = gaps_db.get(ticker, {})
        nwogs = gaps.get("NWOG", [])
        ndogs = gaps.get("NDOG", [])
    else:
        print("Gap file not found.")
        nwogs = []
        ndogs = []

    # Setup Plot
    fig, ax = plt.subplots(figsize=(20, 10))
    
    # 1. Plot Candles (Manual)
    width = 0.005 # Width for 15m bars (approx)
    
    up = df[df['close'] >= df['open']]
    down = df[df['close'] < df['open']]
    
    # Width needs to be relative to date numbers
    # 15 mins = 15/(24*60) days = ~0.01
    
    ax.bar(up.index, up['close'] - up['open'], width=0.006, bottom=up['open'], color='#26a69a', edgecolor='#26a69a', alpha=0.9)
    ax.vlines(up.index, up['low'], up['high'], color='#26a69a', linewidth=1, alpha=0.9)
    
    ax.bar(down.index, down['close'] - down['open'], width=0.006, bottom=down['open'], color='#ef5350', edgecolor='#ef5350', alpha=0.9)
    ax.vlines(down.index, down['low'], down['high'], color='#ef5350', linewidth=1, alpha=0.9)

    # 2. Plot Gaps
    # We want to extend lines from the gap creation to the right
    
    def parse_time(t_str):
        if not t_str: return None
        return pd.Timestamp(t_str).tz_convert('US/Eastern')
    
    right_edge = mdates.date2num(df.index.max() + timedelta(hours=4))
    
    # Plot NWOGs
    for i, g in enumerate(nwogs):
        start_t = parse_time(g['open_time'])
        
         # Only plot if recent enough to be relevant (last 30 days)
        if start_t < start_date - timedelta(days=10):
            continue
            
        # Draw Lines
        start_num = mdates.date2num(start_t) if start_t > df.index.min() else mdates.date2num(df.index.min())

        color = '#FFA500' # Orange
        
        # High Line
        ax.hlines(g['high'], start_t, df.index.max(), color=color, linestyle='--', linewidth=1)
        # Low Line
        ax.hlines(g['low'], start_t, df.index.max(), color=color, linestyle='--', linewidth=1)
        
        # Label
        mid_price = (g['high'] + g['low']) / 2
        ax.annotate(f"NWOG {g['session_date']}", xy=(mdates.date2num(df.index.max()), mid_price), 
                    xytext=(5, 0), textcoords='offset points', color=color, fontsize=8)

    # Plot NDogs
    for i, g in enumerate(ndogs):
        start_t = parse_time(g['open_time'])
        if start_t < start_date - timedelta(days=5): # Only very recent NDOGs
            continue
            
        start_num = mdates.date2num(start_t)
        color = '#1E90FF' # DodgerBlue
        
        ax.hlines(g['high'], start_t, df.index.max(), color=color, linestyle=':', linewidth=1)
        ax.hlines(g['low'], start_t, df.index.max(), color=color, linestyle=':', linewidth=1)
        
        mid_price = (g['high'] + g['low']) / 2
        ax.annotate(f"NDOG {g['session_date']}", xy=(mdates.date2num(df.index.max()), mid_price), 
                     xytext=(5, 0), textcoords='offset points', color=color, fontsize=7)

    # Style
    ax.set_title(f"{ticker} Verification Chart: NWOG & NDOG Lines", color='white', fontsize=16)
    ax.set_facecolor('#1e1e1e')
    fig.patch.set_facecolor('#1e1e1e')
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')
    ax.yaxis.label.set_color('white')
    ax.xaxis.label.set_color('white')
    ax.grid(True, alpha=0.2)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    fig.autofmt_xdate()

    # Save
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    out_file = os.path.join(OUTPUT_DIR, f"{ticker}_verification_gaps.png")
    
    plt.tight_layout()
    plt.savefig(out_file, dpi=100, bbox_inches='tight')
    print(f"Chart saved to {out_file}")

if __name__ == "__main__":
    plot_verification_chart("NQ1", days=10)
