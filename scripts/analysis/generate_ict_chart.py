"""
ICT Chart Generator

Generates a 1-Hour chart with ICT-style overlays:
- Order Blocks (Bullish/Bearish)
- Fair Value Gaps (Daily, Weekly)
- Key Levels: PDH/PDL/PWH/PWL/PMH/PML, Midpoints, Daily/Weekly Close

Usage:
    python generate_ict_chart.py NQ1 --date 2026-01-22
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

OUTPUT_DIR = "c:/Users/vinay/tvDownloadOHLC/data/analysis/charts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================
# ICT CONCEPT DETECTORS
# ============================================

def detect_order_blocks(df, lookback=50):
    """
    Detect Order Blocks.
    Bullish OB: Last bearish candle before a strong bullish move (displacement).
    Bearish OB: Last bullish candle before a strong bearish move.
    """
    obs = []
    
    # Calculate body size and direction
    df = df.copy()
    df['body'] = abs(df['close'] - df['open'])
    df['is_bullish'] = df['close'] > df['open']
    
    # Need at least lookback bars
    if len(df) < lookback:
        return obs
    
    # Simplified OB detection: Look for displacement (large body candle)
    # following a small opposite-direction candle.
    avg_body = df['body'].rolling(20).mean()
    df['is_displacement'] = df['body'] > (avg_body * 2.0) # 2x average body = displacement
    
    for i in range(5, len(df) - 1):
        if df['is_displacement'].iloc[i]:
            # Check if current is bullish displacement
            if df['is_bullish'].iloc[i]:
                # Find last bearish candle before this
                for j in range(i-1, max(0, i-5), -1):
                    if not df['is_bullish'].iloc[j]:
                        obs.append({
                            'type': 'BULLISH_OB',
                            'datetime': df.iloc[j].name, # Index is datetime
                            'high': df['high'].iloc[j],
                            'low': df['low'].iloc[j],
                        })
                        break
            else:
                # Bearish displacement
                for j in range(i-1, max(0, i-5), -1):
                    if df['is_bullish'].iloc[j]:
                        obs.append({
                            'type': 'BEARISH_OB',
                            'datetime': df.iloc[j].name,
                            'high': df['high'].iloc[j],
                            'low': df['low'].iloc[j],
                        })
                        break
                        
    return obs[-20:] # Return last 20 OBs (most recent)

def detect_fvgs(df, min_gap_ticks=5.0, timeframe="1H"):
    """
    Detect Fair Value Gaps.
    Bullish FVG: Gap between candle[i-2].high and candle[i].low
    Bearish FVG: Gap between candle[i-2].low and candle[i].high
    
    timeframe: Label for FVG source (1H, Daily, Weekly)
    """
    fvgs = []
    
    for i in range(2, len(df)):
        # Bullish FVG: Low[i] > High[i-2]
        gap = df['low'].iloc[i] - df['high'].iloc[i-2]
        if gap > min_gap_ticks:
            fvgs.append({
                'type': 'BULLISH_FVG',
                'timeframe': timeframe,
                'datetime': df.iloc[i-1].name, # Middle candle time
                'top': df['low'].iloc[i],
                'bottom': df['high'].iloc[i-2],
            })
        
        # Bearish FVG: High[i] < Low[i-2]
        gap = df['low'].iloc[i-2] - df['high'].iloc[i]
        if gap > min_gap_ticks:
            fvgs.append({
                'type': 'BEARISH_FVG',
                'timeframe': timeframe,
                'datetime': df.iloc[i-1].name,
                'top': df['low'].iloc[i-2],
                'bottom': df['high'].iloc[i],
            })
            
    return fvgs[-30:] # Return last 30 FVGs

def filter_mitigated_obs(obs, df):
    """
    Filter out Order Blocks that have been mitigated.
    Bullish OB mitigated if price later traded BELOW the OB low (invalidated).
    Bearish OB mitigated if price later traded ABOVE the OB high (invalidated).
    """
    valid_obs = []
    for ob in obs:
        future_data = df[df.index > ob['datetime']]
        if future_data.empty:
            valid_obs.append(ob)
            continue
            
        if ob['type'] == 'BULLISH_OB':
            # OB invalidated if price traded below OB low
            if future_data['low'].min() < ob['low']:
                continue # Mitigated
        else: # BEARISH_OB
            # OB invalidated if price traded above OB high
            if future_data['high'].max() > ob['high']:
                continue # Mitigated
                
        valid_obs.append(ob)
    return valid_obs

def filter_mitigated_fvgs(fvgs, df):
    """
    Filter out FVGs that have been filled (mitigated).
    Bullish FVG mitigated if price later traded into/through the gap (below the top).
    Bearish FVG mitigated if price later traded into/through the gap (above the bottom).
    """
    valid_fvgs = []
    for fvg in fvgs:
        future_data = df[df.index > fvg['datetime']]
        if future_data.empty:
            valid_fvgs.append(fvg)
            continue
            
        if fvg['type'] == 'BULLISH_FVG':
            # FVG filled if price traded below the top of the gap
            if future_data['low'].min() <= fvg['bottom']:
                continue # Filled
        else: # BEARISH_FVG
            # FVG filled if price traded above the bottom of the gap
            if future_data['high'].max() >= fvg['top']:
                continue # Filled
                
        valid_fvgs.append(fvg)
    return valid_fvgs

# ============================================
# SWING-BASED STANDARD DEVIATION PROJECTIONS
# ============================================

def detect_weekly_swing(df_1h, target_date):
    """
    Detect the current week's HOTW (High of Week) and LOTW (Low of Week).
    Returns the swing range and anchor points for SD projection.
    
    Args:
        df_1h: 1-hour DataFrame with OHLCV
        target_date: The date we're analyzing for
        
    Returns:
        dict with 'hotw', 'lotw', 'hotw_day', 'lotw_day', 'range', 'direction'
    """
    # Get start of current week (Sunday 18:00 ET or Monday)
    # Futures week starts Sunday 6PM ET, but for simplicity use Monday
    from datetime import timedelta
    
    # Find the Monday of the week containing target_date
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)
    
    # Filter data for the current week up to target_date
    week_data = df_1h[(df_1h.index.date >= week_start) & (df_1h.index.date <= target_date)]
    
    if week_data.empty:
        return None
    
    # Find HOTW and LOTW
    hotw = week_data['high'].max()
    lotw = week_data['low'].min()
    
    # Find which day made the high/low
    hotw_idx = week_data['high'].idxmax()
    lotw_idx = week_data['low'].idxmin()
    
    hotw_day = hotw_idx.strftime('%A') if hotw_idx else 'Unknown'
    lotw_day = lotw_idx.strftime('%A') if lotw_idx else 'Unknown'
    
    # Determine direction based on which came first
    # If LOTW came before HOTW, it's a bullish week (low to high)
    # If HOTW came before LOTW, it's a bearish week (high to low)
    direction = 'BULLISH' if lotw_idx < hotw_idx else 'BEARISH'
    
    swing_range = hotw - lotw
    
    return {
        'hotw': hotw,
        'lotw': lotw,
        'hotw_datetime': hotw_idx,
        'lotw_datetime': lotw_idx,
        'hotw_day': hotw_day,
        'lotw_day': lotw_day,
        'range': swing_range,
        'direction': direction,
        'week_start': week_start
    }

def detect_intraday_swing(df_5m, target_date):
    """
    Detect the key intraday swing for SD projection.
    Finds the INITIAL swing of the session (not overall high/low).
    
    The swing is typically:
    - Overnight/London session low → First significant push high (bullish)
    - OR Overnight high → First significant push low (bearish)
    
    Args:
        df_5m: 5-minute DataFrame
        target_date: The date we're analyzing
        
    Returns:
        dict with swing info including anchor points
    """
    from datetime import time, timedelta
    
    # Get data for target date and previous evening
    prev_date = target_date - timedelta(days=1)
    if prev_date.weekday() >= 5:  # Skip weekend
        prev_date = target_date - timedelta(days=3 if prev_date.weekday() == 6 else 2)
    
    # Define key session times (Eastern Time)
    # Overnight/Asia: 18:00 prev day to 02:00
    # London: 02:00 to 08:00
    # NY Pre-market: 08:00 to 09:30
    # NY Session: 09:30 to 16:00
    
    overnight_start = pd.Timestamp.combine(prev_date, time(18, 0))
    london_end = pd.Timestamp.combine(target_date, time(8, 0))
    ny_open = pd.Timestamp.combine(target_date, time(9, 30))
    
    if df_5m.index.tz:
        overnight_start = overnight_start.tz_localize('US/Eastern')
        london_end = london_end.tz_localize('US/Eastern')
        ny_open = ny_open.tz_localize('US/Eastern')
    
    # Get overnight + London data (where the initial swing typically forms)
    early_session = df_5m[(df_5m.index >= overnight_start) & (df_5m.index <= london_end)]
    
    if early_session.empty or len(early_session) < 10:
        return None
    
    # Find swing pivots using a simple rolling window method
    # A swing low: lowest low within a window where this bar is lower than neighbors
    # A swing high: highest high within a window where this bar is higher than neighbors
    
    pivot_window = 6  # 30 minutes (6 x 5min bars) on each side
    
    early_session = early_session.copy()
    early_session['is_swing_low'] = False
    early_session['is_swing_high'] = False
    
    # Find swing lows
    for i in range(pivot_window, len(early_session) - pivot_window):
        window_lows = early_session['low'].iloc[i-pivot_window:i+pivot_window+1]
        if early_session['low'].iloc[i] == window_lows.min():
            early_session.iloc[i, early_session.columns.get_loc('is_swing_low')] = True
    
    # Find swing highs
    for i in range(pivot_window, len(early_session) - pivot_window):
        window_highs = early_session['high'].iloc[i-pivot_window:i+pivot_window+1]
        if early_session['high'].iloc[i] == window_highs.max():
            early_session.iloc[i, early_session.columns.get_loc('is_swing_high')] = True
    
    swing_lows = early_session[early_session['is_swing_low']]
    swing_highs = early_session[early_session['is_swing_high']]
    
    if swing_lows.empty or swing_highs.empty:
        # Fallback: use overall session extremes
        return {
            'high': early_session['high'].max(),
            'low': early_session['low'].min(),
            'high_datetime': early_session['high'].idxmax(),
            'low_datetime': early_session['low'].idxmin(),
            'range': early_session['high'].max() - early_session['low'].min(),
            'direction': 'BULLISH' if early_session['low'].idxmin() < early_session['high'].idxmax() else 'BEARISH'
        }
    
    # Find the FIRST significant swing
    # Typically: first swing low followed by first swing high = bullish swing
    # OR: first swing high followed by first swing low = bearish swing
    
    first_swing_low = swing_lows.iloc[0] if not swing_lows.empty else None
    first_swing_high = swing_highs.iloc[0] if not swing_highs.empty else None
    
    first_low_time = swing_lows.index[0] if not swing_lows.empty else None
    first_high_time = swing_highs.index[0] if not swing_highs.empty else None
    
    # Determine swing direction based on which came first
    if first_low_time and first_high_time:
        if first_low_time < first_high_time:
            # Bullish swing: Low came first, then High
            # Find the swing high that comes AFTER this swing low
            subsequent_highs = swing_highs[swing_highs.index > first_low_time]
            if not subsequent_highs.empty:
                swing_high_bar = subsequent_highs.iloc[0]
                swing_high_time = subsequent_highs.index[0]
            else:
                swing_high_bar = first_swing_high
                swing_high_time = first_high_time
            
            anchor_low = first_swing_low['low']
            anchor_high = swing_high_bar['high']
            
            return {
                'high': anchor_high,
                'low': anchor_low,
                'high_datetime': swing_high_time,
                'low_datetime': first_low_time,
                'range': anchor_high - anchor_low,
                'direction': 'BULLISH',
                'anchor': anchor_low,  # 0 level = swing low
                'anchor_1': anchor_high  # 1 level = swing high
            }
        else:
            # Bearish swing: High came first, then Low
            subsequent_lows = swing_lows[swing_lows.index > first_high_time]
            if not subsequent_lows.empty:
                swing_low_bar = subsequent_lows.iloc[0]
                swing_low_time = subsequent_lows.index[0]
            else:
                swing_low_bar = first_swing_low
                swing_low_time = first_low_time
            
            anchor_high = first_swing_high['high']
            anchor_low = swing_low_bar['low']
            
            return {
                'high': anchor_high,
                'low': anchor_low,
                'high_datetime': first_high_time,
                'low_datetime': swing_low_time,
                'range': anchor_high - anchor_low,
                'direction': 'BEARISH',
                'anchor': anchor_high,  # 0 level = swing high
                'anchor_1': anchor_low  # 1 level (actually -1) = swing low
            }
    
    return None

def calculate_sd_levels(anchor, swing_range, direction='up', levels=None):
    """
    Calculate SD projection levels from an anchor point.
    
    Args:
        anchor: The anchor price (0 level)
        swing_range: The range to use as 1 SD unit
        direction: 'up' or 'down' - primary projection direction
        levels: List of SD levels to calculate (default: standard set)
        
    Returns:
        List of dicts with 'level', 'price', 'label'
    """
    if levels is None:
        levels = [-4.5, -4, -3.5, -3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5]
    
    result = []
    for lvl in levels:
        price = anchor + (lvl * swing_range)
        result.append({
            'level': lvl,
            'price': price,
            'label': f"{lvl}" if lvl != 0 else "0 (Anchor)"
        })
    
    return result


def calculate_htf_levels(df_1h, target_date):
    """
    Calculate HTF levels: PDH, PDL, PDC, PWH, PWL, PWC, PMH, PML.
    target_date: The date we are analyzing FOR (e.g., tomorrow).
    """
    levels = {}
    
    # Prior Day (the day before target_date)
    prior_day = target_date - timedelta(days=1)
    # Skip weekends
    while prior_day.weekday() >= 5:
        prior_day -= timedelta(days=1)
        
    prior_day_data = df_1h[df_1h.index.date == prior_day]
    if not prior_day_data.empty:
        levels['PDH'] = prior_day_data['high'].max()
        levels['PDL'] = prior_day_data['low'].min()
        levels['PDC'] = prior_day_data['close'].iloc[-1]
        levels['PDM'] = (levels['PDH'] + levels['PDL']) / 2 # Mid
    
    # Prior Week (resample)
    df_weekly = df_1h.resample('W-FRI').agg({'high':'max', 'low':'min', 'close':'last'})
    prior_weeks = df_weekly[df_weekly.index.date < target_date]
    if not prior_weeks.empty:
        last_week = prior_weeks.iloc[-1]
        levels['PWH'] = last_week['high']
        levels['PWL'] = last_week['low']
        levels['PWC'] = last_week['close']
        levels['PWM'] = (levels['PWH'] + levels['PWL']) / 2
    
    # Prior Month
    df_monthly = df_1h.resample('ME').agg({'high':'max', 'low':'min', 'close':'last'})
    prior_months = df_monthly[df_monthly.index.date < target_date]
    if not prior_months.empty:
        last_month = prior_months.iloc[-1]
        levels['PMH'] = last_month['high']
        levels['PML'] = last_month['low']
        levels['PMM'] = (levels['PMH'] + levels['PML']) / 2
        
    return levels

# ============================================
# CHART PLOTTING
# ============================================

def plot_ict_chart(df_1h, ticker, target_date, obs, fvgs, levels, save_path):
    """
    Plot the 1H chart with all ICT overlays.
    """
    fig, ax = plt.subplots(figsize=(22, 12))
    
    # Filter to last 14 days for context (like reference image)
    start_view = target_date - timedelta(days=14)
    df_view = df_1h[(df_1h.index.date >= start_view) & (df_1h.index.date <= target_date)]
    
    if df_view.empty:
        print("No data in view range.")
        return
    
    # --- 1. Candlesticks ---
    width = 0.03 # Width for 1H bars
    up = df_view[df_view['close'] >= df_view['open']]
    down = df_view[df_view['close'] < df_view['open']]
    
    ax.bar(up.index, up['close'] - up['open'], width, bottom=up['open'], color='#26a69a', edgecolor='#26a69a')
    ax.vlines(up.index, up['low'], up['high'], color='#26a69a', linewidth=1)
    ax.bar(down.index, down['close'] - down['open'], width, bottom=down['open'], color='#ef5350', edgecolor='#ef5350')
    ax.vlines(down.index, down['low'], down['high'], color='#ef5350', linewidth=1)
    
    # --- 2. Order Blocks (as rectangles extending to current price) ---
    right_edge = mdates.date2num(df_view.index.max())
    for ob in obs:
        if ob['datetime'] < df_view.index.min():
            continue
        color = '#4caf50' if ob['type'] == 'BULLISH_OB' else '#f44336'
        label = '+OB' if ob['type'] == 'BULLISH_OB' else '-OB'
        ob_start = mdates.date2num(ob['datetime'])
        rect = mpatches.Rectangle(
            (ob_start, ob['low']),
            right_edge - ob_start, # Extend to right edge
            ob['high'] - ob['low'],
            linewidth=1, edgecolor=color, facecolor=color, alpha=0.25
        )
        ax.add_patch(rect)
        # Add label on right side
        mid_price = (ob['high'] + ob['low']) / 2
        ax.annotate(label, xy=(right_edge, mid_price), fontsize=8, color=color, fontweight='bold', va='center')
    
    # --- 3. Fair Value Gaps (as shaded rectangles extending right) ---
    # Color by timeframe
    fvg_colors = {
        ('BULLISH_FVG', '1H'): '#81d4fa',     # Light Blue
        ('BEARISH_FVG', '1H'): '#ffab91',     # Light Orange
        ('BULLISH_FVG', 'Daily'): '#4fc3f7',  # Darker Blue
        ('BEARISH_FVG', 'Daily'): '#ff8a65',  # Darker Orange
        ('BULLISH_FVG', 'Weekly'): '#0288d1', # Deep Blue
        ('BEARISH_FVG', 'Weekly'): '#e64a19', # Deep Orange
    }
    
    for fvg in fvgs:
        if fvg['datetime'] < df_view.index.min():
            continue
        key = (fvg['type'], fvg.get('timeframe', '1H'))
        color = fvg_colors.get(key, '#aaaaaa')
        # Extend FVG rectangle to the right edge of the chart
        rect = mpatches.Rectangle(
            (mdates.date2num(fvg['datetime']), fvg['bottom']),
            mdates.date2num(df_view.index.max()) - mdates.date2num(fvg['datetime']),
            fvg['top'] - fvg['bottom'],
            linewidth=0, facecolor=color, alpha=0.4
        )
        ax.add_patch(rect)
    
    # --- 4. HTF Levels ---
    level_styles = {
        'PDH': ('red', '-', 1.5, 'PDH'),
        'PDL': ('green', '-', 1.5, 'PDL'),
        'PDC': ('blue', '--', 1.0, 'PDC'),
        'PDM': ('purple', ':', 1.0, 'PDM'),
        'PWH': ('darkred', '-', 2.0, 'PWH'),
        'PWL': ('darkgreen', '-', 2.0, 'PWL'),
        'PWC': ('darkblue', '--', 1.5, 'PWC'),
        'PWM': ('magenta', ':', 1.2, 'PWM'),
        'PMH': ('maroon', '-', 2.5, 'PMH'),
        'PML': ('olive', '-', 2.5, 'PML'),
        'PMM': ('brown', ':', 1.5, 'PMM'),
    }
    
    for name, price in levels.items():
        if price is None or name not in level_styles:
            continue
        color, style, lw, label = level_styles[name]
        ax.axhline(price, linestyle=style, color=color, linewidth=lw, alpha=0.7, label=f"{label}: {price:.2f}")
    
    # --- 5. Formatting ---
    ax.set_title(f"ICT Context Chart: {ticker} | Target: {target_date}", fontsize=14, fontweight='bold')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    fig.autofmt_xdate()
    
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylabel("Price")
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"📈 Chart saved to: {save_path}")

def plot_ict_chart_with_sd(df_1h, ticker, target_date, obs, fvgs, levels, weekly_swing, sd_levels, save_path):
    """
    Plot the 1H chart with all ICT overlays INCLUDING SD projections.
    """
    fig, ax = plt.subplots(figsize=(22, 14))
    
    # Filter to last 14 days for context
    start_view = target_date - timedelta(days=14)
    df_view = df_1h[(df_1h.index.date >= start_view) & (df_1h.index.date <= target_date)]
    
    if df_view.empty:
        print("No data in view range.")
        return
    
    price_min = df_view['low'].min()
    price_max = df_view['high'].max()
    
    # --- 1. Candlesticks ---
    width = 0.03
    up = df_view[df_view['close'] >= df_view['open']]
    down = df_view[df_view['close'] < df_view['open']]
    
    ax.bar(up.index, up['close'] - up['open'], width, bottom=up['open'], color='#26a69a', edgecolor='#26a69a')
    ax.vlines(up.index, up['low'], up['high'], color='#26a69a', linewidth=1)
    ax.bar(down.index, down['close'] - down['open'], width, bottom=down['open'], color='#ef5350', edgecolor='#ef5350')
    ax.vlines(down.index, down['low'], down['high'], color='#ef5350', linewidth=1)
    
    right_edge = mdates.date2num(df_view.index.max())
    
    # --- 2. Order Blocks ---
    for ob in obs:
        if ob['datetime'] < df_view.index.min():
            continue
        color = '#4caf50' if ob['type'] == 'BULLISH_OB' else '#f44336'
        label = '+OB' if ob['type'] == 'BULLISH_OB' else '-OB'
        ob_start = mdates.date2num(ob['datetime'])
        rect = mpatches.Rectangle(
            (ob_start, ob['low']),
            right_edge - ob_start,
            ob['high'] - ob['low'],
            linewidth=1, edgecolor=color, facecolor=color, alpha=0.25
        )
        ax.add_patch(rect)
        mid_price = (ob['high'] + ob['low']) / 2
        ax.annotate(label, xy=(right_edge, mid_price), fontsize=8, color=color, fontweight='bold', va='center')
    
    # --- 3. Fair Value Gaps ---
    fvg_colors = {
        ('BULLISH_FVG', '1H'): '#81d4fa',
        ('BEARISH_FVG', '1H'): '#ffab91',
        ('BULLISH_FVG', 'Daily'): '#4fc3f7',
        ('BEARISH_FVG', 'Daily'): '#ff8a65',
        ('BULLISH_FVG', 'Weekly'): '#0288d1',
        ('BEARISH_FVG', 'Weekly'): '#e64a19',
    }
    
    for fvg in fvgs:
        if fvg['datetime'] < df_view.index.min():
            continue
        key = (fvg['type'], fvg.get('timeframe', '1H'))
        color = fvg_colors.get(key, '#aaaaaa')
        rect = mpatches.Rectangle(
            (mdates.date2num(fvg['datetime']), fvg['bottom']),
            mdates.date2num(df_view.index.max()) - mdates.date2num(fvg['datetime']),
            fvg['top'] - fvg['bottom'],
            linewidth=0, facecolor=color, alpha=0.4
        )
        ax.add_patch(rect)
    
    # --- 4. SD PROJECTION LEVELS ---
    if sd_levels and weekly_swing:
        sd_color_bullish = '#00bcd4'  # Cyan for bullish (below anchor)
        sd_color_bearish = '#ff9800'  # Orange for bearish (above anchor)
        
        for sd in sd_levels:
            lvl = sd['level']
            price = sd['price']
            
            # Only show levels within visible price range (with some buffer)
            buffer = (price_max - price_min) * 0.3
            if price < price_min - buffer or price > price_max + buffer:
                continue
            
            # Color based on level (positive = above, negative = below)
            if lvl == 0:
                color = 'white'
                lw = 2
                style = '-'
            elif lvl > 0:
                color = sd_color_bearish  # Extensions up
                lw = 1.0 if lvl in [1, 2, 3, 4] else 0.7
                style = '-' if lvl in [1, 2, 2.5, 3, 4] else ':'
            else:
                color = sd_color_bullish  # Extensions down
                lw = 1.0 if lvl in [-1, -2, -3, -4] else 0.7
                style = '-' if lvl in [-1, -2, -2.5, -3, -4] else ':'
            
            ax.axhline(price, linestyle=style, color=color, linewidth=lw, alpha=0.8)
            # Label on right side
            ax.annotate(f"{lvl}", xy=(right_edge, price), fontsize=7, color=color, 
                       fontweight='bold', va='center', ha='left',
                       xytext=(5, 0), textcoords='offset points')
        
        # Add swing info annotation
        swing_info = f"Weekly Swing: {weekly_swing['direction']} | HOTW: {weekly_swing['hotw_day']} | LOTW: {weekly_swing['lotw_day']} | Range: {weekly_swing['range']:.2f}"
        ax.annotate(swing_info, xy=(0.02, 0.02), xycoords='axes fraction', fontsize=9,
                   color='white', backgroundcolor='#333333', alpha=0.8)
    
    # --- 5. HTF Levels ---
    level_styles = {
        'PDH': ('red', '-', 1.5, 'PDH'),
        'PDL': ('green', '-', 1.5, 'PDL'),
        'PWH': ('darkred', '-', 2.0, 'PWH'),
        'PWL': ('darkgreen', '-', 2.0, 'PWL'),
        'PMH': ('maroon', '-', 2.5, 'PMH'),
        'PML': ('olive', '-', 2.5, 'PML'),
    }
    
    for name, price in levels.items():
        if price is None or name not in level_styles:
            continue
        color, style, lw, label = level_styles[name]
        ax.axhline(price, linestyle=style, color=color, linewidth=lw, alpha=0.7)
        ax.annotate(f"{label}: {price:.2f}", xy=(right_edge, price), fontsize=7, 
                   color=color, va='center', ha='left', xytext=(5, 0), textcoords='offset points')
    
    # --- 6. Formatting ---
    ax.set_title(f"ICT Context Chart (with SD): {ticker} | Target: {target_date}", fontsize=14, fontweight='bold')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    ax.set_facecolor('#131722')  # Dark background like TradingView
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
    print(f"📈 Chart saved to: {save_path}")

# ============================================
# MAIN
# ============================================

def main(ticker, target_date_str=None):
    print(f"\n📊 Generating ICT Chart for {ticker}...")
    
    # 1. Load 1H Data
    # Load 1m first then resample to 1H for freshest data
    df_1m = load_fused_data(ticker, timeframe="1m", require_historical=True)
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
    
    # Resample to 1H
    df_1h = df_1m.resample('1h').agg({
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
    
    # 3. Detect ICT Concepts
    print("  Detecting Order Blocks (1H)...")
    obs = detect_order_blocks(df_1h)
    print(f"    Found {len(obs)} OBs (before filtering)")
    
    # Filter out mitigated OBs
    obs = filter_mitigated_obs(obs, df_1h)
    print(f"    {len(obs)} OBs remain after mitigation filter")
    
    # Detect FVGs at multiple timeframes
    print("  Detecting FVGs...")
    all_fvgs = []
    
    # 1H FVGs
    fvgs_1h = detect_fvgs(df_1h, min_gap_ticks=5.0, timeframe="1H")
    print(f"    1H FVGs: {len(fvgs_1h)}")
    all_fvgs.extend(fvgs_1h)
    
    # Daily FVGs (resample to 1D)
    df_daily = df_1m.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    fvgs_d = detect_fvgs(df_daily, min_gap_ticks=20.0, timeframe="Daily")
    print(f"    Daily FVGs: {len(fvgs_d)}")
    all_fvgs.extend(fvgs_d)
    
    # Weekly FVGs (resample to 1W)
    df_weekly = df_1m.resample('W-FRI').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    fvgs_w = detect_fvgs(df_weekly, min_gap_ticks=50.0, timeframe="Weekly")
    print(f"    Weekly FVGs: {len(fvgs_w)}")
    all_fvgs.extend(fvgs_w)
    
    # Filter out mitigated FVGs
    all_fvgs = filter_mitigated_fvgs(all_fvgs, df_1h)
    print(f"    {len(all_fvgs)} FVGs remain after mitigation filter")
    
    print("  Calculating HTF Levels...")
    levels = calculate_htf_levels(df_1h, target_date)
    print(f"    Levels: {list(levels.keys())}")
    
    # 4. Detect Weekly Swing for SD Projection
    print("  Detecting Weekly Swing (for SD projection)...")
    weekly_swing = detect_weekly_swing(df_1h, target_date)
    sd_levels = None
    
    if weekly_swing:
        print(f"    Weekly: {weekly_swing['direction']} | HOTW: {weekly_swing['hotw_day']} @ {weekly_swing['hotw']:.2f} | LOTW: {weekly_swing['lotw_day']} @ {weekly_swing['lotw']:.2f}")
        print(f"    Range: {weekly_swing['range']:.2f}")
        
        # Calculate SD levels from LOTW (anchor at 0)
        sd_levels = calculate_sd_levels(
            anchor=weekly_swing['lotw'],
            swing_range=weekly_swing['range'],
            direction='up'
        )
        print(f"    Generated {len(sd_levels)} SD levels")
    else:
        print("    No weekly swing data available")
    
    # 5. Plot Chart with SD
    save_path = os.path.join(OUTPUT_DIR, f"{ticker}_ict_context_{target_date}.png")
    
    if sd_levels:
        plot_ict_chart_with_sd(df_1h, ticker, target_date, obs, all_fvgs, levels, weekly_swing, sd_levels, save_path)
    else:
        plot_ict_chart(df_1h, ticker, target_date, obs, all_fvgs, levels, save_path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker (e.g. NQ1)")
    parser.add_argument("--date", help="Target Date YYYY-MM-DD", required=False)
    args = parser.parse_args()
    main(args.ticker, args.date)

