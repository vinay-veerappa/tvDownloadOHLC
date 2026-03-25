"""
Custom Configuration Test: VVIX ON + Regime OFF + Exit 11:00
Calculate Profit Factor comparison vs Baseline
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import time

TICKER = "NQ1"
YEARS = 10

def load_data():
    or_path = f"data/{TICKER}_opening_range.json"
    with open(or_path, 'r') as f:
        or_data = json.load(f)
    or_df = pd.DataFrame(or_data)
    or_df['date'] = pd.to_datetime(or_df['date'])
    or_df = or_df.set_index('date')
    
    p_path = f"data/{TICKER}_1m.parquet"
    df = pd.read_parquet(p_path)
    if 'time' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        df = df.set_index('datetime')
    if df.index.tz is None:
        df = df.tz_localize('UTC')
    df = df.tz_convert('US/Eastern')
    df = df.sort_index()
    
    df_daily = df.resample('1D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    df_daily['SMA20'] = df_daily['close'].rolling(20).mean()
    
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

def run_backtest(or_df, df_1m, df_daily, vvix, config):
    end_date = or_df.index.max()
    start_date = end_date - pd.Timedelta(days=YEARS*365)
    or_df_filtered = or_df[or_df.index >= start_date]
    
    trades = []
    
    for d, row in or_df_filtered.iterrows():
        day_str = d.date()
        r_high, r_low, r_open = row['high'], row['low'], row['open']
        r_pct = row.get('range_pct', (r_high - r_low) / r_open)
        
        if config['USE_TUESDAY'] and d.dayofweek == 1: continue
        if config.get('USE_WEDNESDAY', False) and d.dayofweek == 2: continue
        if r_pct > config['MAX_RANGE_PCT']: continue
        
        if config['USE_REGIME']:
            try:
                d_normalized = pd.Timestamp(d).normalize().tz_localize('US/Eastern')
                prior_day_rec = df_daily.loc[:d_normalized].iloc[-2]
                if prior_day_rec['close'] < prior_day_rec['SMA20']:
                    continue
            except:
                pass
        
        if config['USE_VVIX'] and vvix is not None:
            try:
                vvix_val = vvix.loc[day_str]['open']
                if isinstance(vvix_val, pd.Series):
                    vvix_val = vvix_val.iloc[0]
                if vvix_val > 115:
                    continue
            except:
                pass
        
        d_localized = pd.Timestamp(d).tz_localize('US/Eastern')
        t_start = d_localized + pd.Timedelta(hours=9, minutes=31)
        hard_exit = config['HARD_EXIT']
        t_end = d_localized + pd.Timedelta(hours=hard_exit.hour, minutes=hard_exit.minute)
        
        market_data = df_1m.loc[t_start : t_end]
        if len(market_data) < 2:
            continue
        
        trade = execute_trade(market_data, r_high, r_low, r_open, config)
        if trade:
            trades.append(trade)
    
    return pd.DataFrame(trades) if trades else pd.DataFrame()

def execute_trade(market_data, r_high, r_low, r_open, config):
    r_size = r_high - r_low
    pos = 0
    entry_px, sl_px, mae, mfe = 0.0, 0.0, 0.0, 0.0
    breakout_dir, breakout_bar_idx = 0, None
    
    entry_mode = config['ENTRY_MODE']
    pb_level = config['PB_LEVEL_PCT']
    pb_timeout = config['PB_TIMEOUT']
    max_sl = config['MAX_SL_PCT']
    
    for i, (t, bar) in enumerate(market_data.iterrows()):
        if pos == 0:
            if breakout_dir == 0:
                if bar['close'] > r_high:
                    breakout_dir, breakout_bar_idx = 1, i
                elif bar['close'] < r_low:
                    breakout_dir, breakout_bar_idx = -1, i
            
            if breakout_dir != 0 and breakout_bar_idx is not None:
                pb_buy = r_high - (r_size * pb_level)
                pb_sell = r_low + (r_size * pb_level)
                bars_elapsed = i - breakout_bar_idx
                
                if entry_mode == "IMMEDIATE" and bars_elapsed == 0:
                    pos, entry_px = breakout_dir, bar['close']
                    sl_px = r_low if pos == 1 else r_high
                    mae, mfe = entry_px, entry_px
                elif "PULLBACK" in entry_mode:
                    if breakout_dir == 1 and bar['low'] <= pb_buy and bar['close'] > pb_buy:
                        pos, entry_px, sl_px = 1, bar['close'], r_low
                        mae, mfe = entry_px, entry_px
                    elif breakout_dir == -1 and bar['high'] >= pb_sell and bar['close'] < pb_sell:
                        pos, entry_px, sl_px = -1, bar['close'], r_high
                        mae, mfe = entry_px, entry_px
                    elif entry_mode == "PULLBACK_FALLBACK" and bars_elapsed >= pb_timeout and pos == 0:
                        pos, entry_px = breakout_dir, bar['close']
                        sl_px = r_low if pos == 1 else r_high
                        mae, mfe = entry_px, entry_px
        
        if pos != 0:
            dist, max_dist = abs(entry_px - sl_px), entry_px * (max_sl / 100.0)
            if dist > max_dist:
                sl_px = entry_px - max_dist if pos == 1 else entry_px + max_dist
            
            if pos == 1:
                mae, mfe = min(mae, bar['low']), max(mfe, bar['high'])
            else:
                mae, mfe = max(mae, bar['high']), min(mfe, bar['low'])
            
            sl_hit = (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px)
            if sl_hit:
                pnl = (sl_px - entry_px) if pos == 1 else (entry_px - sl_px)
                return {'PnL_Pct': (pnl / entry_px) * 100}
            
            if i == len(market_data) - 1:
                exit_px = bar['close']
                pnl = (exit_px - entry_px) if pos == 1 else (entry_px - exit_px)
                return {'PnL_Pct': (pnl / entry_px) * 100}
    
    return None

def calculate_pf(df):
    """Calculate Profit Factor = Gross Profit / |Gross Loss|"""
    if df.empty:
        return 0
    gross_profit = df[df['PnL_Pct'] > 0]['PnL_Pct'].sum()
    gross_loss = abs(df[df['PnL_Pct'] < 0]['PnL_Pct'].sum())
    return gross_profit / gross_loss if gross_loss > 0 else float('inf')

# MAIN
print("Loading data...")
or_df, df_1m, df_daily, vvix = load_data()

# BASELINE (V6 Defaults)
baseline = {
    'USE_REGIME': True, 'USE_VVIX': True, 'USE_TUESDAY': True, 'USE_WEDNESDAY': False,
    'MAX_RANGE_PCT': 0.25, 'ENTRY_MODE': 'PULLBACK_FALLBACK',
    'PB_LEVEL_PCT': 0.25, 'PB_TIMEOUT': 5, 'MAX_SL_PCT': 0.30, 'HARD_EXIT': time(10, 0),
}

# NEW CONFIG (User Request)
new_config = baseline.copy()
new_config['USE_REGIME'] = False  # OFF
new_config['USE_VVIX'] = True     # ON (keep)
new_config['HARD_EXIT'] = time(11, 0)  # Extended

print("\n=== BASELINE (V6 Defaults) ===")
baseline_trades = run_backtest(or_df, df_1m, df_daily, vvix, baseline)
baseline_pf = calculate_pf(baseline_trades)
print(f"Trades: {len(baseline_trades)}")
print(f"Win Rate: {(baseline_trades['PnL_Pct'] > 0).mean():.2%}")
print(f"Gross PnL: {baseline_trades['PnL_Pct'].sum():.2f}%")
print(f"Profit Factor: {baseline_pf:.2f}")

print("\n=== NEW CONFIG (VVIX ON, Regime OFF, Exit 11:00) ===")
new_trades = run_backtest(or_df, df_1m, df_daily, vvix, new_config)
new_pf = calculate_pf(new_trades)
print(f"Trades: {len(new_trades)}")
print(f"Win Rate: {(new_trades['PnL_Pct'] > 0).mean():.2%}")
print(f"Gross PnL: {new_trades['PnL_Pct'].sum():.2f}%")
print(f"Profit Factor: {new_pf:.2f}")

print("\n=== COMPARISON ===")
print(f"PF Change: {baseline_pf:.2f} -> {new_pf:.2f} ({(new_pf/baseline_pf - 1)*100:+.1f}%)")
print(f"PnL Change: {baseline_trades['PnL_Pct'].sum():.2f}% -> {new_trades['PnL_Pct'].sum():.2f}%")

# Save results with descriptive names
output_dir = "scripts/backtest/9_30_breakout/results"
os.makedirs(output_dir, exist_ok=True)

# Baseline
baseline_trades.to_csv(os.path.join(output_dir, "v6_baseline_regime_on_vvix_on_exit_1000.csv"), index=False)
print(f"\nSaved: v6_baseline_regime_on_vvix_on_exit_1000.csv")

# New Config
new_trades.to_csv(os.path.join(output_dir, "v6_custom_regime_off_vvix_on_exit_1100.csv"), index=False)
print(f"Saved: v6_custom_regime_off_vvix_on_exit_1100.csv")
