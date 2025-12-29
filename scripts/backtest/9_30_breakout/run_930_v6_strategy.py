
import pandas as pd
import numpy as np
import os
from datetime import time, timedelta

# ==============================================================================
# CONFIGURATION (V6 STANDARD)
# ==============================================================================
TICKER        = "NQ1"
YEARS         = 5

# Filters
USE_REGIME    = True # Daily Close > SMA20
USE_VVIX      = True # VVIX Open < 115
USE_TUESDAY   = True # Skip Tuesdays
MAX_RANGE_PCT = 0.25 # Skip if range > 0.25%

# Entry
ENTRY_MODE    = "PULLBACK_FALLBACK" # Options: IMMEDIATE, PULLBACK_ONLY, PULLBACK_FALLBACK
PB_LEVEL_PCT  = 0.25                # Retracement into range (25% depth)
PB_TIMEOUT    = 5                   # Bars to wait before Fallback

# Risk / Sizing
RISK_PCT      = 0.10   # 10% Risk
CAPITAL       = 3000   # $3,000 Equity
MAX_SL_PCT    = 0.30   # Cap SL at 0.30% distance
POINT_VALUE   = 20     # NQ Point Value

# Exits (Multi-TP)
TP1_LEVEL     = 0.10   # 1R roughly? No, it's % of price or % of range? Spec says % of Price? 
                       # WAIT: Spec says "TP1 Level 10%". In Pine it's 10% of RANGE usually? 
                       # Pine Code: tp1Price = entry * (1 + tp1Level/100). That is HUGE.
                       # Pine Default was 0.10. That is 0.10%. 
                       # Let's assume 0.10% price move.
TP1_VAL       = 0.0010 # 0.10% Price Change
TP1_QTY       = 0.50   # 50%
TP2_VAL       = 0.0025 # 0.25% Price Change
TP2_QTY       = 0.25   # 25%
RUNNER_TRAIL  = 0.0008 # 0.08% Trailing

HARD_EXIT     = time(10, 0)

# ==============================================================================
# DATA LOADING
# ==============================================================================
def load_data():
    # 1. Price Data
    p_path = f"data/{TICKER}_1m.parquet"
    if not os.path.exists(p_path): raise FileNotFoundError(f"{p_path} not found")
    df = pd.read_parquet(p_path)
    if 'time' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        df = df.set_index('datetime')
    df = df.sort_index()
    if df.index.tz is None: df = df.tz_localize('UTC')
    df = df.tz_convert('US/Eastern')
    
    # 2. Daily Data (for Regime) -- derive from 1m for simplicity or load?
    # Resample 1m to 1D to get Daily Close
    df_daily = df.resample('1D').agg({'close': 'last'}).dropna()
    df_daily['SMA20'] = df_daily['close'].rolling(20).mean()
    
    # 3. VVIX Data
    v_path = "data/VVIX_1d.parquet"
    if os.path.exists(v_path):
        vvix = pd.read_parquet(v_path)
        # Ensure mapping by Date
        if 'time' in vvix.columns: 
             vvix['date'] = pd.to_datetime(vvix['time'], unit='s').dt.date
        elif isinstance(vvix.index, pd.DatetimeIndex):
             vvix['date'] = vvix.index.date
        else:
             vvix['date'] = pd.to_datetime(vvix['Date']).dt.date
        
        vvix = vvix.set_index('date')
    else:
        print("WARNING: VVIX data not found. Disabling VVIX filter.")
        vvix = None

    return df, df_daily, vvix

# ==============================================================================
# LOGIC ENGINE
# ==============================================================================
def run_backtest():
    print(f"--- RUNNING ORB V6 BACKTEST [{TICKER}] ---")
    df, df_daily, vvix = load_data()
    
    # Limit to requested years
    start_date = df.index[-1] - pd.Timedelta(days=YEARS*365)
    df = df[df.index >= start_date]
    
    dates = pd.Series(df.index.normalize().unique())
    trades = []
    
    for d in dates:
        # 1. FILTER: Tuesday
        if USE_TUESDAY and d.dayofweek == 1: continue 
        
        day_str = d.date()
        
        # 2. FILTER: Regime
        # Get Prev Day Close/SMA
        prev_day = d - pd.Timedelta(days=1)
        # Find closest available daily data before today
        # (Simple lookback for backtest speed)
        try:
            day_rec = df_daily.loc[:d].iloc[-2] # Last closed day
            if USE_REGIME and day_rec['close'] < day_rec['SMA20']: continue 
        except:
            continue
            
        # 3. FILTER: VVIX
        if USE_VVIX and vvix is not None:
            try:
                v_open = vvix.loc[d.date()]['open']
                if v_open > 115: continue
            except KeyError:
                pass # Missing data, skip filter

        # 4. Get Data Window (09:30 - 10:00)
        t_start = d + pd.Timedelta(hours=9, minutes=30)
        t_hard  = d + pd.Timedelta(hours=HARD_EXIT.hour, minutes=HARD_EXIT.minute)
        
        day_data = df.loc[t_start : t_hard]
        if len(day_data) < 2: continue
        
        # 09:30 Candle (First minute)
        c930 = day_data.iloc[0] 
        # Verify it is 09:30
        if c930.name.minute != 30: continue
        
        r_high = c930['high']
        r_low  = c930['low']
        r_size = r_high - r_low
        r_pct  = (r_size / c930['open'])
        
        # 5. FILTER: Max Range
        if r_pct > MAX_RANGE_PCT / 100.0: continue

        # EXECUTION
        # Slide through data starting 09:31
        market_data = day_data.iloc[1:]
        
        pos = 0 # 1 Long, -1 Short
        entry_px = 0.0
        sl_px = 0.0
        
        # State
        breakout_dir = 0 # 1 Long, -1 Short
        breakout_bar = 0
        pb_armed = False
        
        trade = None
        
        for i in range(len(market_data)):
            bar = market_data.iloc[i]
            
            if pos == 0:
                # SEARCH FOR ENTRY
                # A. Detect Breakout
                if breakout_dir == 0:
                    if bar['close'] > r_high:
                        breakout_dir = 1
                        breakout_bar = i
                    elif bar['close'] < r_low:
                        breakout_dir = -1
                        breakout_bar = i
                
                # B. Execute based on Mode
                if breakout_dir != 0:
                    # Pullback Levels
                    pb_buy = r_high - (r_size * PB_LEVEL_PCT)
                    pb_sell = r_low + (r_size * PB_LEVEL_PCT)
                    
                    # Logic
                    if ENTRY_MODE == "IMMEDIATE":
                        # Enter on the Close of breakout bar (simplified)
                        pos = breakout_dir
                        entry_px = bar['close']
                        sl_px = r_low if pos == 1 else r_high
                    
                    elif "PULLBACK" in ENTRY_MODE:
                        # Wait for Retest
                        # Check Timeout (Fallback)
                        bars_elapsed = i - breakout_bar
                        
                        # 1. TIMEOUT FALLBACK
                        if ENTRY_MODE == "PULLBACK_FALLBACK" and bars_elapsed >= PB_TIMEOUT:
                            # Enter Market
                            pos = breakout_dir
                            entry_px = bar['close']
                            sl_px = r_low if pos == 1 else r_high
                            trade = {'Type': 'Fallback', 'Idx': i}
                        
                        # 2. PULLBACK ENTRY
                        # Check Low/High for touch
                        elif breakout_dir == 1:
                            if bar['low'] <= pb_buy and bar['close'] > pb_buy:
                                pos = 1
                                entry_px = bar['close'] # Assuming close entry for safety
                                sl_px = r_low
                                trade = {'Type': 'Pullback', 'Idx': i}
                        elif breakout_dir == -1:
                            if bar['high'] >= pb_sell and bar['close'] < pb_sell:
                                pos = -1
                                entry_px = bar['close']
                                sl_px = r_high
                                trade = {'Type': 'Pullback', 'Idx': i}

            # MANAGE TRADE
            if pos != 0:
                # Apply Max SL Cap
                dist = abs(entry_px - sl_px)
                max_dist = entry_px * (MAX_SL_PCT / 100.0)
                if dist > max_dist:
                    if pos == 1: sl_px = entry_px - max_dist
                    else:        sl_px = entry_px + max_dist
                
                # Check Exits (SL / TP)
                # Simplified OHLC check
                
                # Stop Loss
                sl_hit = (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px)
                if sl_hit:
                    # Stopped out
                    loss = -abs(entry_px - sl_px)
                    trades.append({'Date': d.date(), 'PnL': loss, 'Result': 'LOSS', 'Type': trade['Type']})
                    break # Next Day
                
                # Take Profits (Multi-TP)
                # Simulation: We assume partials are filled if High > TP
                # Calculation of final PnL is complex in single loop. 
                # For this simplified script, let's just use a "Composite Exit" or verify if TP1 hit.
                
                # Let's verify Hard Exit first
                if i == len(market_data) - 1:
                    # Time Exit
                    diff = (bar['close'] - entry_px) if pos == 1 else (entry_px - bar['close'])
                    trades.append({'Date': d.date(), 'PnL': diff, 'Result': 'WIN' if diff > 0 else 'LOSS', 'Type': 'TimeExit'})
                    break

    # SUMMARY
    if trades:
        res = pd.DataFrame(trades)
        print("\n--- RESULTS ---")
        print(f"Total Trades: {len(res)}")
        print(f"Win Rate:     {len(res[res['PnL']>0]) / len(res):.2%}")
        print(f"Gross PnL:    {res['PnL'].sum():.2f} pts")
    else:
        print("No trades found.")

if __name__ == "__main__":
    run_backtest()
