"""
ICT 5-Minute Intraday Chart Generator

Generates a 5-minute chart with ICT-style overlays:
- Order Blocks
- FVGs
- Session Swing-Based SD Projections

Usage:
    python generate_ict_chart_5m.py NQ1 --date 2026-01-22
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import os
import sys
from datetime import datetime, timedelta, time

# Fused Data Loader
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
from fused_data_loader import load_fused_data

# Import detection functions from main chart generator
from generate_ict_chart import (
    detect_order_blocks, detect_fvgs, 
    filter_mitigated_obs, filter_mitigated_fvgs,
    detect_intraday_swing, calculate_sd_levels
)

OUTPUT_DIR = "c:/Users/vinay/tvDownloadOHLC/data/analysis/charts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def plot_5m_chart_with_sd(df_5m, ticker, target_date, obs, fvgs, intraday_swing, sd_levels, save_path):
    """
    Plot the 5M intraday chart with SD projections.
    """
    fig, ax = plt.subplots(figsize=(24, 12))
    
    # Filter to just the target date session (overnight + day)
    prev_date = target_date - timedelta(days=1)
    if prev_date.weekday() >= 5:
        prev_date = target_date - timedelta(days=3 if prev_date.weekday() == 6 else 2)
    
    # Session from prev day 18:00 to target day 16:00
    start_view = pd.Timestamp.combine(prev_date, time(18, 0))
    end_view = pd.Timestamp.combine(target_date, time(16, 0))
    
    if df_5m.index.tz:
        start_view = start_view.tz_localize('US/Eastern')
        end_view = end_view.tz_localize('US/Eastern')
    
    df_view = df_5m[(df_5m.index >= start_view) & (df_5m.index <= end_view)]
    
    if df_view.empty:
        print("No data in view range.")
        return
    
    price_min = df_view['low'].min()
    price_max = df_view['high'].max()
    
    # --- 1. Candlesticks ---
    width = 0.002  # Narrower for 5M bars
    up = df_view[df_view['close'] >= df_view['open']]
    down = df_view[df_view['close'] < df_view['open']]
    
    ax.bar(up.index, up['close'] - up['open'], width, bottom=up['open'], color='#26a69a', edgecolor='#26a69a')
    ax.vlines(up.index, up['low'], up['high'], color='#26a69a', linewidth=0.5)
    ax.bar(down.index, down['close'] - down['open'], width, bottom=down['open'], color='#ef5350', edgecolor='#ef5350')
    ax.vlines(down.index, down['low'], down['high'], color='#ef5350', linewidth=0.5)
    
    right_edge = mdates.date2num(df_view.index.max())
    
    # --- 2. Order Blocks ---
    for ob in obs:
        if ob['datetime'] < df_view.index.min() or ob['datetime'] > df_view.index.max():
            continue
        color = '#4caf50' if ob['type'] == 'BULLISH_OB' else '#f44336'
        label = '+OB' if ob['type'] == 'BULLISH_OB' else '-OB'
        ob_start = mdates.date2num(ob['datetime'])
        rect = mpatches.Rectangle(
            (ob_start, ob['low']),
            right_edge - ob_start,
            ob['high'] - ob['low'],
            linewidth=1, edgecolor=color, facecolor=color, alpha=0.3
        )
        ax.add_patch(rect)
        mid_price = (ob['high'] + ob['low']) / 2
        ax.annotate(label, xy=(right_edge, mid_price), fontsize=7, color=color, fontweight='bold', va='center')
    
    # --- 3. Fair Value Gaps ---
    fvg_colors = {
        ('BULLISH_FVG', '5M'): '#81d4fa',
        ('BEARISH_FVG', '5M'): '#ffab91',
    }
    
    for fvg in fvgs:
        if fvg['datetime'] < df_view.index.min() or fvg['datetime'] > df_view.index.max():
            continue
        key = (fvg['type'], fvg.get('timeframe', '5M'))
        color = fvg_colors.get(key, '#81d4fa' if 'BULLISH' in fvg['type'] else '#ffab91')
        rect = mpatches.Rectangle(
            (mdates.date2num(fvg['datetime']), fvg['bottom']),
            right_edge - mdates.date2num(fvg['datetime']),
            fvg['top'] - fvg['bottom'],
            linewidth=0, facecolor=color, alpha=0.4
        )
        ax.add_patch(rect)
    
    # --- 4. SD PROJECTION LEVELS ---
    if sd_levels and intraday_swing:
        sd_color_bullish = '#00bcd4'  # Cyan
        sd_color_bearish = '#ff9800'  # Orange
        
        for sd in sd_levels:
            lvl = sd['level']
            price = sd['price']
            
            # Only show levels within visible price range
            buffer = (price_max - price_min) * 0.2
            if price < price_min - buffer or price > price_max + buffer:
                continue
            
            if lvl == 0:
                color = 'white'
                lw = 2
                style = '-'
            elif lvl > 0:
                color = sd_color_bearish
                lw = 1.0 if abs(lvl) in [1, 2, 3, 4] else 0.7
                style = '-' if abs(lvl) in [1, 2, 2.5, 3, 4] else ':'
            else:
                color = sd_color_bullish
                lw = 1.0 if abs(lvl) in [1, 2, 3, 4] else 0.7
                style = '-' if abs(lvl) in [1, 2, 2.5, 3, 4] else ':'
            
            ax.axhline(price, linestyle=style, color=color, linewidth=lw, alpha=0.8)
            ax.annotate(f"{lvl}", xy=(right_edge, price), fontsize=7, color=color, 
                       fontweight='bold', va='center', ha='left',
                       xytext=(5, 0), textcoords='offset points')
        
        # Swing info
        swing_info = f"Session Swing: {intraday_swing['direction']} | High: {intraday_swing['high']:.2f} | Low: {intraday_swing['low']:.2f} | Range: {intraday_swing['range']:.2f}"
        ax.annotate(swing_info, xy=(0.02, 0.02), xycoords='axes fraction', fontsize=9,
                   color='white', backgroundcolor='#333333', alpha=0.8)
    
    # --- 5. Session Time Markers ---
    # 09:30 NY Open
    ny_open = pd.Timestamp.combine(target_date, time(9, 30))
    if df_5m.index.tz:
        ny_open = ny_open.tz_localize('US/Eastern')
    if ny_open >= df_view.index.min() and ny_open <= df_view.index.max():
        ax.axvline(ny_open, color='orange', linewidth=1.5, linestyle='--', alpha=0.7)
        ax.annotate('09:30', xy=(ny_open, price_max), fontsize=8, color='orange', va='bottom', ha='center')
    
    # --- 6. Formatting ---
    ax.set_title(f"ICT 5M Chart (with SD): {ticker} | {target_date}", fontsize=14, fontweight='bold')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.set_facecolor('#131722')
    fig.patch.set_facecolor('#131722')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    for spine in ax.spines.values():
        spine.set_color('#363a45')
    fig.autofmt_xdate()
    
    ax.grid(True, alpha=0.2, color='#363a45')
    ax.set_ylabel("Price", color='white')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor='#131722')
    plt.close()
    print(f"📈 5M Chart saved to: {save_path}")

def main(ticker, target_date_str=None):
    print(f"\n📊 Generating ICT 5M Chart for {ticker}...")
    
    # 1. Load 1m data (we'll resample to 5m)
    df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
    if df_1m.empty:
        print("Error: No data.")
        return
    
    # Ensure ET timezone
    try:
        df_1m.index = df_1m.index.tz_convert('US/Eastern')
    except:
        try:
            df_1m.index = df_1m.index.tz_localize('UTC').tz_convert('US/Eastern')
        except:
            pass
    
    # Resample to 5M
    df_5m = df_1m.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # 2. Determine Target Date
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date()
    
    # 3. Detect ICT Concepts on 5M
    print("  Detecting Order Blocks (5M)...")
    obs = detect_order_blocks(df_5m)
    obs = filter_mitigated_obs(obs, df_5m)
    print(f"    {len(obs)} OBs after filter")
    
    print("  Detecting FVGs (5M)...")
    fvgs = detect_fvgs(df_5m, min_gap_ticks=3.0, timeframe="5M")
    fvgs = filter_mitigated_fvgs(fvgs, df_5m)
    print(f"    {len(fvgs)} FVGs after filter")
    
    # 4. Detect Intraday Swing
    print("  Detecting Intraday Swing (for SD projection)...")
    intraday_swing = detect_intraday_swing(df_5m, target_date)
    sd_levels = None
    
    if intraday_swing:
        print(f"    Session: {intraday_swing['direction']} | High: {intraday_swing['high']:.2f} | Low: {intraday_swing['low']:.2f}")
        print(f"    Range: {intraday_swing['range']:.2f}")
        
        # Use the explicit anchor from swing detection if available
        anchor = intraday_swing.get('anchor', intraday_swing['low'])
        print(f"    Anchor (0 level): {anchor:.2f}")
        
        # Calculate SD levels
        sd_levels = calculate_sd_levels(
            anchor=anchor,
            swing_range=intraday_swing['range'],
            direction='up' if intraday_swing['direction'] == 'BULLISH' else 'down'
        )
        print(f"    Generated {len(sd_levels)} SD levels")
    else:
        print("    No intraday swing data available")
    
    # 5. Plot 5M Chart
    save_path = os.path.join(OUTPUT_DIR, f"{ticker}_ict_5m_{target_date}.png")
    plot_5m_chart_with_sd(df_5m, ticker, target_date, obs, fvgs, intraday_swing, sd_levels, save_path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker (e.g. NQ1)")
    parser.add_argument("--date", help="Target Date YYYY-MM-DD", required=False)
    args = parser.parse_args()
    main(args.ticker, args.date)
