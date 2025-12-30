"""
ORB V6 Parameter Optimization Study
====================================
Tests multiple values for each configurable parameter to identify optimal defaults.

Output:
- Individual CSVs per configuration (in results/optimization/)
- Summary CSV comparing all configurations

Parameters Tested:
- Filters: USE_REGIME, USE_VVIX, USE_TUESDAY, USE_WEDNESDAY
- Range: MAX_RANGE_PCT (0.15 - 0.35)
- Entry: ENTRY_MODE (IMMEDIATE, PULLBACK_ONLY, PULLBACK_FALLBACK)
- Pullback: PB_LEVEL_PCT (0.15 - 0.35), PB_TIMEOUT (3-10 bars)
- Risk: MAX_SL_PCT (0.20 - 0.40)
- Exit: HARD_EXIT (9:45, 10:00, 10:30, 11:00)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import time, timedelta
from itertools import product

# ==============================================================================
# OPTIMIZATION CONFIGURATION
# ==============================================================================
TICKER = "NQ1"
YEARS = 10

# Parameter Grid (Each list = values to test)
PARAM_GRID = {
    # Binary Filters
    'USE_REGIME':    [True, False],
    'USE_VVIX':      [True, False],
    'USE_TUESDAY':   [True, False],
    'USE_WEDNESDAY': [True, False],
    
    # Range Filter
    'MAX_RANGE_PCT': [0.15, 0.20, 0.25, 0.30, 0.35],
    
    # Entry Mode
    'ENTRY_MODE':    ['IMMEDIATE', 'PULLBACK_ONLY', 'PULLBACK_FALLBACK'],
    
    # Pullback Settings
    'PB_LEVEL_PCT':  [0.15, 0.20, 0.25, 0.30, 0.35],
    'PB_TIMEOUT':    [3, 5, 7, 10],
    
    # Risk Settings
    'MAX_SL_PCT':    [0.20, 0.25, 0.30, 0.35, 0.40],
    
    # Exit Time
    'HARD_EXIT':     [time(9, 45), time(10, 0), time(10, 30), time(11, 0)],
}

# Output Directories
OUTPUT_DIR = "scripts/backtest/9_30_breakout/results/optimization"
SUMMARY_FILE = "scripts/backtest/9_30_breakout/results/optimization_summary.csv"

# ==============================================================================
# DATA LOADING (Same as main script)
# ==============================================================================
def load_data():
    """Load all required data sources."""
    # 1. Opening Range
    or_path = f"data/{TICKER}_opening_range.json"
    with open(or_path, 'r') as f:
        or_data = json.load(f)
    or_df = pd.DataFrame(or_data)
    or_df['date'] = pd.to_datetime(or_df['date'])
    or_df = or_df.set_index('date')
    
    # 2. 1-Minute Price Data
    p_path = f"data/{TICKER}_1m.parquet"
    df = pd.read_parquet(p_path)
    if 'time' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        df = df.set_index('datetime')
    if df.index.tz is None:
        df = df.tz_localize('UTC')
    df = df.tz_convert('US/Eastern')
    df = df.sort_index()
    
    # 3. Daily Data (for Regime)
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

    return or_df, df, df_daily, vvix

# ==============================================================================
# SINGLE PARAMETER TEST (Isolated)
# ==============================================================================
def run_single_param_test(or_df, df_1m, df_daily, vvix, param_name, param_value, baseline_config):
    """
    Run backtest with ONE parameter changed from baseline.
    Returns summary stats.
    """
    config = baseline_config.copy()
    config[param_name] = param_value
    
    return run_backtest_with_config(or_df, df_1m, df_daily, vvix, config)

def run_backtest_with_config(or_df, df_1m, df_daily, vvix, config, config_name=None):
    """Run backtest with specific configuration. Returns (summary_dict, trades_df)."""
    # Limit to requested years
    end_date = or_df.index.max()
    start_date = end_date - pd.Timedelta(days=YEARS*365)
    or_df_filtered = or_df[or_df.index >= start_date]
    
    trades = []
    
    for d, row in or_df_filtered.iterrows():
        day_str = d.date()
        dow = d.strftime('%a')
        
        r_high = row['high']
        r_low = row['low']
        r_open = row['open']
        r_pct = row.get('range_pct', (r_high - r_low) / r_open)
        
        # FILTERS
        if config['USE_TUESDAY'] and d.dayofweek == 1:
            continue
        if config.get('USE_WEDNESDAY', False) and d.dayofweek == 2:
            continue
        if r_pct > config['MAX_RANGE_PCT']:
            continue
        
        # Regime
        regime_bull = True
        try:
            d_normalized = pd.Timestamp(d).normalize().tz_localize('US/Eastern')
            prior_day_rec = df_daily.loc[:d_normalized].iloc[-2]
            if config['USE_REGIME'] and prior_day_rec['close'] < prior_day_rec['SMA20']:
                continue
            regime_bull = prior_day_rec['close'] >= prior_day_rec['SMA20']
        except:
            pass
        
        # VVIX
        vvix_open = np.nan
        if config['USE_VVIX'] and vvix is not None:
            try:
                vvix_val = vvix.loc[day_str]['open']
                if isinstance(vvix_val, pd.Series):
                    vvix_val = vvix_val.iloc[0]
                vvix_open = vvix_val
                if vvix_val > 115:
                    continue
            except:
                pass
        
        # EXECUTION
        d_localized = pd.Timestamp(d).tz_localize('US/Eastern')
        t_start = d_localized + pd.Timedelta(hours=9, minutes=31)
        hard_exit = config['HARD_EXIT']
        t_end = d_localized + pd.Timedelta(hours=hard_exit.hour, minutes=hard_exit.minute)
        
        market_data = df_1m.loc[t_start : t_end]
        if len(market_data) < 2:
            continue
        
        trade = execute_trade(market_data, r_high, r_low, r_open, config)
        if trade:
            # Add context fields
            trade['Date'] = day_str
            trade['DayOfWeek'] = dow
            trade['Range_High'] = r_high
            trade['Range_Low'] = r_low
            trade['Range_Pct'] = round(r_pct * 100, 4)
            trade['Regime_Bull'] = regime_bull
            trade['VVIX_Open'] = vvix_open
            # Add config info
            if config_name:
                trade['Config'] = config_name
            trades.append(trade)
    
    # Create DataFrame
    if trades:
        df_trades = pd.DataFrame(trades)
        summary = {
            'Trades': len(df_trades),
            'WinRate': (df_trades['Result'] == 'WIN').mean(),
            'GrossPnL': df_trades['PnL_Pct'].sum(),
            'AvgPnL': df_trades['PnL_Pct'].mean(),
            'AvgMAE': df_trades['MAE_Pct'].mean(),
            'AvgMFE': df_trades['MFE_Pct'].mean(),
        }
        return summary, df_trades
    else:
        return {'Trades': 0, 'WinRate': 0, 'GrossPnL': 0, 'AvgPnL': 0, 'AvgMAE': 0, 'AvgMFE': 0}, pd.DataFrame()

def execute_trade(market_data, r_high, r_low, r_open, config):
    """Execute trade logic with given config."""
    r_size = r_high - r_low
    
    pos = 0
    entry_px = 0.0
    sl_px = 0.0
    entry_time = None
    entry_type = None
    
    breakout_dir = 0
    breakout_bar_idx = None
    
    mae = 0.0
    mfe = 0.0
    
    entry_mode = config['ENTRY_MODE']
    pb_level = config['PB_LEVEL_PCT']
    pb_timeout = config['PB_TIMEOUT']
    max_sl = config['MAX_SL_PCT']
    
    for i, (t, bar) in enumerate(market_data.iterrows()):
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
                pb_buy = r_high - (r_size * pb_level)
                pb_sell = r_low + (r_size * pb_level)
                bars_elapsed = i - breakout_bar_idx
                
                if entry_mode == "IMMEDIATE" and bars_elapsed == 0:
                    pos = breakout_dir
                    entry_px = bar['close']
                    sl_px = r_low if pos == 1 else r_high
                    entry_time = t
                    entry_type = 'Immediate'
                    mae = entry_px
                    mfe = entry_px
                
                elif "PULLBACK" in entry_mode:
                    if breakout_dir == 1 and bar['low'] <= pb_buy and bar['close'] > pb_buy:
                        pos = 1
                        entry_px = bar['close']
                        sl_px = r_low
                        entry_time = t
                        entry_type = 'Pullback'
                        mae = entry_px
                        mfe = entry_px
                    elif breakout_dir == -1 and bar['high'] >= pb_sell and bar['close'] < pb_sell:
                        pos = -1
                        entry_px = bar['close']
                        sl_px = r_high
                        entry_time = t
                        entry_type = 'Pullback'
                        mae = entry_px
                        mfe = entry_px
                    
                    elif entry_mode == "PULLBACK_FALLBACK" and bars_elapsed >= pb_timeout and pos == 0:
                        pos = breakout_dir
                        entry_px = bar['close']
                        sl_px = r_low if pos == 1 else r_high
                        entry_time = t
                        entry_type = 'Fallback'
                        mae = entry_px
                        mfe = entry_px
        
        # Trade Management
        if pos != 0:
            # Apply Max SL Cap
            dist = abs(entry_px - sl_px)
            max_dist = entry_px * (max_sl / 100.0)
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
                return {'Result': 'WIN' if pnl_pct > 0 else 'LOSS', 'PnL_Pct': pnl_pct, 'MAE_Pct': mae_pct, 'MFE_Pct': mfe_pct}
            
            # Time Exit
            if i == len(market_data) - 1:
                exit_px = bar['close']
                pnl = (exit_px - entry_px) if pos == 1 else (entry_px - exit_px)
                pnl_pct = (pnl / entry_px) * 100
                mae_pct = abs(entry_px - mae) / entry_px * 100
                mfe_pct = abs(mfe - entry_px) / entry_px * 100
                return {'Result': 'WIN' if pnl_pct > 0 else 'LOSS', 'PnL_Pct': pnl_pct, 'MAE_Pct': mae_pct, 'MFE_Pct': mfe_pct}
    
    return None

# ==============================================================================
# MAIN OPTIMIZATION LOOP
# ==============================================================================
def run_optimization():
    print("=== ORB V6 PARAMETER OPTIMIZATION ===")
    print(f"Loading data for {TICKER}...")
    
    or_df, df_1m, df_daily, vvix = load_data()
    print(f"Loaded {len(or_df)} days of opening range data")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Baseline Configuration (V6 Defaults)
    baseline = {
        'USE_REGIME': True,
        'USE_VVIX': True,
        'USE_TUESDAY': True,
        'USE_WEDNESDAY': False,
        'MAX_RANGE_PCT': 0.25,
        'ENTRY_MODE': 'PULLBACK_FALLBACK',
        'PB_LEVEL_PCT': 0.25,
        'PB_TIMEOUT': 5,
        'MAX_SL_PCT': 0.30,
        'HARD_EXIT': time(10, 0),
    }
    
    # Run Baseline
    print("\n--- Running Baseline ---")
    baseline_result, baseline_trades = run_backtest_with_config(or_df, df_1m, df_daily, vvix, baseline, 'BASELINE')
    print(f"Baseline: {baseline_result['Trades']} trades, WR: {baseline_result['WinRate']:.2%}, PnL: {baseline_result['GrossPnL']:.2f}%")
    
    # Save baseline trades
    if not baseline_trades.empty:
        baseline_trades.to_csv(os.path.join(OUTPUT_DIR, "trades_BASELINE.csv"), index=False)
    
    results = []
    results.append({
        'Param': 'BASELINE',
        'Value': 'V6_Defaults',
        **baseline_result
    })
    
    all_trades = [baseline_trades] if not baseline_trades.empty else []
    
    # Test Each Parameter
    for param_name, param_values in PARAM_GRID.items():
        print(f"\n--- Testing {param_name} ---")
        for value in param_values:
            # Skip baseline value (already tested)
            if baseline.get(param_name) == value:
                continue
            
            # Create config name
            value_str = str(value) if not isinstance(value, time) else f"{value.hour}:{value.minute:02d}"
            config_name = f"{param_name}_{value_str}"
            
            # Run test
            config = baseline.copy()
            config[param_name] = value
            result, trades_df = run_backtest_with_config(or_df, df_1m, df_daily, vvix, config, config_name)
            
            print(f"  {param_name}={value_str}: {result['Trades']} trades, WR: {result['WinRate']:.2%}, PnL: {result['GrossPnL']:.2f}%")
            
            # Save individual trades CSV
            if not trades_df.empty:
                safe_name = config_name.replace(":", "").replace("/", "_")
                trades_df.to_csv(os.path.join(OUTPUT_DIR, f"trades_{safe_name}.csv"), index=False)
                all_trades.append(trades_df)
            
            results.append({
                'Param': param_name,
                'Value': value_str,
                **result
            })
    
    # Save Summary
    df_results = pd.DataFrame(results)
    df_results.to_csv(SUMMARY_FILE, index=False)
    print(f"\n=== OPTIMIZATION COMPLETE ===")
    print(f"Summary saved to: {SUMMARY_FILE}")
    print(f"Individual trade CSVs saved to: {OUTPUT_DIR}/")
    
    # Save combined trades file
    if all_trades:
        combined = pd.concat(all_trades, ignore_index=True)
        combined.to_csv(os.path.join(OUTPUT_DIR, "all_trades_combined.csv"), index=False)
        print(f"Combined trades file: {os.path.join(OUTPUT_DIR, 'all_trades_combined.csv')}")
    
    # Show Best Configurations
    print("\n--- TOP 5 BY PnL ---")
    top5 = df_results.nlargest(5, 'GrossPnL')
    print(top5[['Param', 'Value', 'Trades', 'WinRate', 'GrossPnL']].to_string(index=False))
    
    print("\n--- WORST 5 BY PnL ---")
    worst5 = df_results.nsmallest(5, 'GrossPnL')
    print(worst5[['Param', 'Value', 'Trades', 'WinRate', 'GrossPnL']].to_string(index=False))

if __name__ == "__main__":
    run_optimization()
