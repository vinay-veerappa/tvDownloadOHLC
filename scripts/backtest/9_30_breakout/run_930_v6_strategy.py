"""
ORB V6 Backtester - Compliant with BACKTEST_STANDARDS.md
=========================================================
Strategy: 9:30 Opening Range Breakout (V6 Production)
Ticker: NQ1 (Default)
Timeframe: 10 Years (2015-2025)

CSV Output Schema (per BACKTEST_STANDARDS.md):
- Context: Date, DayOfWeek, Range_High, Range_Low, Range_Pct, Regime_Bull, VVIX_Open
- Execution: Variant, Direction, Entry_Price, Entry_Time, Entry_Type, Entry_Delay, Is_Outside_Range
- Outcome: Result, PnL_Pct, MAE_Pct, MFE_Pct, Exit_Time, Exit_Reason
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import time, timedelta

# ==============================================================================
# CONFIGURATION (V6 STANDARD)
# ==============================================================================
TICKER        = "NQ1"
YEARS         = 10

# Filters
USE_REGIME    = True   # Daily Close > SMA20
USE_VVIX      = True   # VVIX Open < 115
USE_TUESDAY   = True   # Skip Tuesdays
MAX_RANGE_PCT = 0.25   # Skip if range > 0.25%

# Entry
ENTRY_MODE    = "PULLBACK_FALLBACK" # IMMEDIATE, PULLBACK_ONLY, PULLBACK_FALLBACK
PB_LEVEL_PCT  = 0.25                # Retracement into range (25% depth)
PB_TIMEOUT    = 5                   # Bars to wait before Fallback

# Risk / Sizing
MAX_SL_PCT    = 0.30   # Cap SL at 0.30% distance

# Exits
HARD_EXIT     = time(10, 0)

# Output
OUTPUT_DIR    = "scripts/backtest/9_30_breakout/results"
OUTPUT_FILE   = "v6_backtest_details.csv"

# ==============================================================================
# DATA LOADING
# ==============================================================================
def load_data():
    """Load all required data sources."""
    # 1. Opening Range (Pre-computed 9:30 candles)
    or_path = f"data/{TICKER}_opening_range.json"
    if not os.path.exists(or_path):
        raise FileNotFoundError(f"Opening Range JSON not found: {or_path}")
    with open(or_path, 'r') as f:
        or_data = json.load(f)
    or_df = pd.DataFrame(or_data)
    or_df['date'] = pd.to_datetime(or_df['date'])
    or_df = or_df.set_index('date')
    print(f"Loaded {len(or_df)} Opening Range records from {or_path}")
    
    # 2. 1-Minute Price Data (for trade execution)
    p_path = f"data/{TICKER}_1m.parquet"
    if not os.path.exists(p_path):
        raise FileNotFoundError(f"Price parquet not found: {p_path}")
    df = pd.read_parquet(p_path)
    if 'time' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        df = df.set_index('datetime')
    if df.index.tz is None:
        df = df.tz_localize('UTC')
    df = df.tz_convert('US/Eastern')
    df = df.sort_index()
    print(f"Loaded {len(df)} 1m bars from {p_path}")
    
    # 3. Daily Data (for Regime: SMA20)
    df_daily = df.resample('1D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    df_daily['SMA20'] = df_daily['close'].rolling(20).mean()
    
    # 4. VVIX Data
    vvix = None
    v_path = "data/VVIX_1d.parquet"
    if os.path.exists(v_path):
        vvix_raw = pd.read_parquet(v_path)
        if 'time' in vvix_raw.columns:
            vvix_raw['date'] = pd.to_datetime(vvix_raw['time'], unit='s').dt.date
        elif isinstance(vvix_raw.index, pd.DatetimeIndex):
            vvix_raw['date'] = vvix_raw.index.date
        else:
            vvix_raw['date'] = pd.to_datetime(vvix_raw['Date']).dt.date
        vvix = vvix_raw.set_index('date')
        print(f"Loaded VVIX data from {v_path}")
    else:
        print(f"WARNING: VVIX data not found at {v_path}. VVIX filter disabled.")

    return or_df, df, df_daily, vvix

# ==============================================================================
# TRADE LOGIC
# ==============================================================================
def run_backtest():
    print(f"--- RUNNING ORB V6 BACKTEST [{TICKER}] ({YEARS} Years) ---")
    or_df, df_1m, df_daily, vvix = load_data()
    
    # Limit to requested years
    end_date = or_df.index.max()
    start_date = end_date - pd.Timedelta(days=YEARS*365)
    or_df = or_df[or_df.index >= start_date]
    print(f"Backtesting from {start_date.date()} to {end_date.date()}")
    
    trades = []
    
    # DEBUG COUNTERS
    debug = {'total': 0, 'tuesday': 0, 'range': 0, 'regime': 0, 'vvix': 0, 'no_data': 0, 'no_trade': 0}
    
    for d, row in or_df.iterrows():
        debug['total'] += 1
        day_str = d.date()
        dow = d.strftime('%a') # Mon, Tue, ...
        
        r_high = row['high']
        r_low  = row['low']
        r_open = row['open']
        r_pct  = row.get('range_pct', (r_high - r_low) / r_open)
        
        # === FILTERS ===
        # 1. Tuesday
        if USE_TUESDAY and d.dayofweek == 1:
            debug['tuesday'] += 1
            continue
        
        # 2. Max Range
        # NOTE: range_pct in JSON is already a percentage (0.10 = 0.10%), not decimal
        if r_pct > MAX_RANGE_PCT:
            debug['range'] += 1
            continue
        
        # 3. Regime (look at prior day's close vs SMA20)
        regime_bull = True
        try:
            # Use normalized (date-only) lookup for daily data
            d_normalized = pd.Timestamp(d).normalize().tz_localize('US/Eastern')
            prior_day_rec = df_daily.loc[:d_normalized].iloc[-2]
            if USE_REGIME and prior_day_rec['close'] < prior_day_rec['SMA20']:
                debug['regime'] += 1
                continue
            regime_bull = prior_day_rec['close'] >= prior_day_rec['SMA20']
        except Exception as e:
            pass # Not enough history
        
        # 4. VVIX
        vvix_open = np.nan
        if USE_VVIX and vvix is not None:
            try:
                vvix_val = vvix.loc[day_str]['open']
                # Handle case where lookup returns Series (duplicate dates)
                if isinstance(vvix_val, pd.Series):
                    vvix_open = vvix_val.iloc[0]
                else:
                    vvix_open = vvix_val
                if vvix_open > 115:
                    debug['vvix'] += 1
                    continue
            except KeyError:
                pass
        
        # === EXECUTION ===
        # Get intraday data for this day
        # CRITICAL: Localize the naive date to US/Eastern to match df_1m index
        d_localized = pd.Timestamp(d).tz_localize('US/Eastern')
        t_start = d_localized + pd.Timedelta(hours=9, minutes=31)
        t_end   = d_localized + pd.Timedelta(hours=HARD_EXIT.hour, minutes=HARD_EXIT.minute)
        
        market_data = df_1m.loc[t_start : t_end]
        if len(market_data) < 2:
            debug['no_data'] += 1
            continue
        
        trade = execute_trade(market_data, r_high, r_low, r_open)
        
        if trade:
            # Enrich with context
            trade['Date'] = day_str
            trade['DayOfWeek'] = dow
            trade['Range_High'] = r_high
            trade['Range_Low'] = r_low
            trade['Range_Pct'] = round(r_pct * 100, 4)
            trade['Regime_Bull'] = regime_bull
            trade['VVIX_Open'] = vvix_open
            trade['Variant'] = 'V6_PullbackFallback'
            trades.append(trade)
    
    # === OUTPUT ===
    if trades:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        df_out = pd.DataFrame(trades)
        # Reorder columns per BACKTEST_STANDARDS
        cols = [
            'Date', 'DayOfWeek', 'Range_Pct', 'Regime_Bull', 'VVIX_Open',
            'Variant', 'Direction', 'Entry_Price', 'Entry_Time', 'Entry_Type', 'Entry_Delay', 'Is_Outside_Range',
            'Result', 'PnL_Pct', 'MAE_Pct', 'MFE_Pct', 'Exit_Time', 'Exit_Reason',
            'Range_High', 'Range_Low'
        ]
        df_out = df_out[[c for c in cols if c in df_out.columns]]
        out_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
        df_out.to_csv(out_path, index=False)
        print(f"\n--- RESULTS SAVED TO {out_path} ---")
        
        # Summary
        print(f"Total Trades: {len(df_out)}")
        print(f"Win Rate:     {(df_out['Result'] == 'WIN').mean():.2%}")
        print(f"Gross PnL %:  {df_out['PnL_Pct'].sum():.2f}%")
        print(f"Avg MAE %:    {df_out['MAE_Pct'].mean():.4f}%")
        print(f"Avg MFE %:    {df_out['MFE_Pct'].mean():.4f}%")
    else:
        print("No trades found.")
    
    # DEBUG SUMMARY
    print(f"\n--- DEBUG FILTER COUNTS ---")
    print(f"Total Days:    {debug['total']}")
    print(f"Tuesday Skip:  {debug['tuesday']}")
    print(f"Range Skip:    {debug['range']}")
    print(f"Regime Skip:   {debug['regime']}")
    print(f"VVIX Skip:     {debug['vvix']}")
    print(f"No Data:       {debug['no_data']}")
    print(f"No Trade Logic:{debug['no_trade']}")

def execute_trade(market_data, r_high, r_low, r_open):
    """
    Execute a single day's trade logic.
    Returns a dict with Execution and Outcome fields, or None if no trade.
    """
    r_size = r_high - r_low
    
    pos = 0  # 1 Long, -1 Short
    entry_px = 0.0
    sl_px = 0.0
    entry_time = None
    entry_type = None
    entry_bar_idx = 0
    
    breakout_dir = 0
    breakout_bar_idx = None
    
    mae = 0.0
    mfe = 0.0
    
    for i, (t, bar) in enumerate(market_data.iterrows()):
        # === ENTRY SEARCH ===
        if pos == 0:
            # Detect Breakout
            if breakout_dir == 0:
                if bar['close'] > r_high:
                    breakout_dir = 1
                    breakout_bar_idx = i
                elif bar['close'] < r_low:
                    breakout_dir = -1
                    breakout_bar_idx = i
            
            # Entry Logic
            if breakout_dir != 0 and breakout_bar_idx is not None:
                pb_buy = r_high - (r_size * PB_LEVEL_PCT)
                pb_sell = r_low + (r_size * PB_LEVEL_PCT)
                bars_elapsed = i - breakout_bar_idx
                
                # Immediate Mode
                if ENTRY_MODE == "IMMEDIATE" and bars_elapsed == 0:
                    pos = breakout_dir
                    entry_px = bar['close']
                    sl_px = r_low if pos == 1 else r_high
                    entry_time = t
                    entry_type = 'Immediate'
                    entry_bar_idx = i
                    mae = entry_px
                    mfe = entry_px
                
                # Pullback Mode
                elif "PULLBACK" in ENTRY_MODE:
                    # Pullback Entry
                    if breakout_dir == 1 and bar['low'] <= pb_buy and bar['close'] > pb_buy:
                        pos = 1
                        entry_px = bar['close']
                        sl_px = r_low
                        entry_time = t
                        entry_type = 'Pullback'
                        entry_bar_idx = i
                        mae = entry_px
                        mfe = entry_px
                    elif breakout_dir == -1 and bar['high'] >= pb_sell and bar['close'] < pb_sell:
                        pos = -1
                        entry_px = bar['close']
                        sl_px = r_high
                        entry_time = t
                        entry_type = 'Pullback'
                        entry_bar_idx = i
                        mae = entry_px
                        mfe = entry_px
                    
                    # Fallback (Timeout)
                    elif ENTRY_MODE == "PULLBACK_FALLBACK" and bars_elapsed >= PB_TIMEOUT and pos == 0:
                        pos = breakout_dir
                        entry_px = bar['close']
                        sl_px = r_low if pos == 1 else r_high
                        entry_time = t
                        entry_type = 'Fallback'
                        entry_bar_idx = i
                        mae = entry_px
                        mfe = entry_px
        
        # === TRADE MANAGEMENT ===
        if pos != 0:
            # Apply Max SL Cap
            dist = abs(entry_px - sl_px)
            max_dist = entry_px * (MAX_SL_PCT / 100.0)
            if dist > max_dist:
                if pos == 1:
                    sl_px = entry_px - max_dist
                else:
                    sl_px = entry_px + max_dist
            
            # Update MAE/MFE
            if pos == 1:
                mae = min(mae, bar['low'])
                mfe = max(mfe, bar['high'])
            else:
                mae = max(mae, bar['high'])
                mfe = min(mfe, bar['low'])
            
            # Stop Loss Hit
            sl_hit = (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px)
            if sl_hit:
                pnl = (sl_px - entry_px) if pos == 1 else (entry_px - sl_px)
                pnl_pct = (pnl / entry_px) * 100
                mae_pct = abs(entry_px - mae) / entry_px * 100
                mfe_pct = abs(mfe - entry_px) / entry_px * 100
                return build_trade(entry_px, entry_time, entry_type, entry_bar_idx, pos, sl_px, t, 'SL', pnl_pct, mae_pct, mfe_pct, r_high, r_low)
            
            # Time Exit (Last Bar)
            if i == len(market_data) - 1:
                exit_px = bar['close']
                pnl = (exit_px - entry_px) if pos == 1 else (entry_px - exit_px)
                pnl_pct = (pnl / entry_px) * 100
                mae_pct = abs(entry_px - mae) / entry_px * 100
                mfe_pct = abs(mfe - entry_px) / entry_px * 100
                return build_trade(entry_px, entry_time, entry_type, entry_bar_idx, pos, exit_px, t, 'TIME', pnl_pct, mae_pct, mfe_pct, r_high, r_low)
    
    return None

def build_trade(entry_px, entry_time, entry_type, entry_bar_idx, direction, exit_px, exit_time, exit_reason, pnl_pct, mae_pct, mfe_pct, r_high, r_low):
    """Build a trade record dict."""
    return {
        'Direction': 'LONG' if direction == 1 else 'SHORT',
        'Entry_Price': round(entry_px, 2),
        'Entry_Time': entry_time.strftime('%H:%M:%S') if entry_time else '',
        'Entry_Type': entry_type,
        'Entry_Delay': entry_bar_idx,  # Minutes from 09:31
        'Is_Outside_Range': True,      # Always true for valid breakout
        'Result': 'WIN' if pnl_pct > 0 else ('LOSS' if pnl_pct < 0 else 'BREAKEVEN'),
        'PnL_Pct': round(pnl_pct, 4),
        'MAE_Pct': round(mae_pct, 4),
        'MFE_Pct': round(mfe_pct, 4),
        'Exit_Time': exit_time.strftime('%H:%M:%S') if exit_time else '',
        'Exit_Reason': exit_reason
    }

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    run_backtest()
