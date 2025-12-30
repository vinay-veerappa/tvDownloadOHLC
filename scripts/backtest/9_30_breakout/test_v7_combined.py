"""
V7 Combined Configuration Test
==============================
Tests all optimized parameters together:
- USE_REGIME = False
- USE_VVIX = True
- USE_TUESDAY = True
- USE_WEDNESDAY = True (NEW)
- HARD_EXIT = 11:00
- ENTRY_MODE = IMMEDIATE
- MAX_SL_PCT = 0.25%
- TP1 = 0.10% (exit 50%)
- TP2 = 0.15% (exit remaining)
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

# V7 CONFIGURATION
V7_CONFIG = {
    'USE_REGIME': False,      # OFF (was ON)
    'USE_VVIX': True,         # ON
    'USE_TUESDAY': True,      # ON
    'USE_WEDNESDAY': True,    # NEW: Skip Wednesday
    'MAX_RANGE_PCT': 0.25,
    'ENTRY_MODE': 'IMMEDIATE', # Changed from PULLBACK_FALLBACK
    'PB_LEVEL_PCT': 0.15,     # Shallow (for reference)
    'PB_TIMEOUT': 5,
    'MAX_SL_PCT': 0.25,       # Tighter (was 0.30)
    'HARD_EXIT': time(11, 0), # Extended (was 10:00)
    # Multi-TP
    'USE_MULTI_TP': True,
    'TP1_PCT': 0.10,          # First target: 0.10%
    'TP1_QTY': 0.50,          # Exit 50% at TP1
    'TP2_PCT': 0.15,          # Second target: 0.15%
}

def run_backtest(or_df, df_1m, df_daily, vvix, config):
    end_date = or_df.index.max()
    start_date = end_date - pd.Timedelta(days=YEARS*365)
    or_df_filtered = or_df[or_df.index >= start_date]
    
    trades = []
    
    for d, row in or_df_filtered.iterrows():
        day_str = d.date()
        dow = d.strftime('%a')
        r_high, r_low, r_open = row['high'], row['low'], row['open']
        r_pct = row.get('range_pct', (r_high - r_low) / r_open)
        
        # FILTERS
        if config['USE_TUESDAY'] and d.dayofweek == 1: continue
        if config.get('USE_WEDNESDAY', False) and d.dayofweek == 2: continue
        if r_pct > config['MAX_RANGE_PCT']: continue
        
        # Regime (skipped if USE_REGIME is False)
        if config['USE_REGIME']:
            try:
                d_normalized = pd.Timestamp(d).normalize().tz_localize('US/Eastern')
                prior_day_rec = df_daily.loc[:d_normalized].iloc[-2]
                if prior_day_rec['close'] < prior_day_rec['SMA20']:
                    continue
            except:
                pass
        
        # VVIX
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
        
        trade = execute_trade_multi_tp(market_data, r_high, r_low, r_open, config)
        if trade:
            trade['Date'] = day_str
            trade['DayOfWeek'] = dow
            trade['Range_Pct'] = round(r_pct * 100, 4)
            trades.append(trade)
    
    return pd.DataFrame(trades) if trades else pd.DataFrame()

def execute_trade_multi_tp(market_data, r_high, r_low, r_open, config):
    """Execute trade with multi-TP logic."""
    r_size = r_high - r_low
    
    pos = 0
    entry_px = 0.0
    sl_px = 0.0
    mae, mfe = 0.0, 0.0
    
    breakout_dir = 0
    breakout_bar_idx = None
    
    entry_mode = config['ENTRY_MODE']
    max_sl = config['MAX_SL_PCT']
    use_multi_tp = config.get('USE_MULTI_TP', False)
    tp1_pct = config.get('TP1_PCT', 0.10)
    tp2_pct = config.get('TP2_PCT', 0.15)
    tp1_qty = config.get('TP1_QTY', 0.50)
    
    tp1_hit = False
    total_pnl = 0.0
    
    for i, (t, bar) in enumerate(market_data.iterrows()):
        if pos == 0:
            # Detect Breakout
            if breakout_dir == 0:
                if bar['close'] > r_high:
                    breakout_dir, breakout_bar_idx = 1, i
                elif bar['close'] < r_low:
                    breakout_dir, breakout_bar_idx = -1, i
            
            # IMMEDIATE Entry
            if breakout_dir != 0 and breakout_bar_idx == i and entry_mode == "IMMEDIATE":
                pos = breakout_dir
                entry_px = bar['close']
                sl_px = r_low if pos == 1 else r_high
                mae, mfe = entry_px, entry_px
        
        if pos != 0:
            # Apply Max SL Cap
            dist = abs(entry_px - sl_px)
            max_dist = entry_px * (max_sl / 100.0)
            if dist > max_dist:
                sl_px = entry_px - max_dist if pos == 1 else entry_px + max_dist
            
            # Update MAE/MFE
            if pos == 1:
                mae, mfe = min(mae, bar['low']), max(mfe, bar['high'])
            else:
                mae, mfe = max(mae, bar['high']), min(mfe, bar['low'])
            
            # Check TP1
            if use_multi_tp and not tp1_hit:
                tp1_px = entry_px * (1 + tp1_pct/100) if pos == 1 else entry_px * (1 - tp1_pct/100)
                if (pos == 1 and bar['high'] >= tp1_px) or (pos == -1 and bar['low'] <= tp1_px):
                    # TP1 hit - partial exit
                    pnl1 = tp1_pct * tp1_qty  # Realized PnL from 50% at TP1
                    total_pnl += pnl1
                    tp1_hit = True
            
            # Check TP2
            if use_multi_tp and tp1_hit:
                tp2_px = entry_px * (1 + tp2_pct/100) if pos == 1 else entry_px * (1 - tp2_pct/100)
                if (pos == 1 and bar['high'] >= tp2_px) or (pos == -1 and bar['low'] <= tp2_px):
                    # TP2 hit - exit remaining
                    pnl2 = tp2_pct * (1 - tp1_qty)  # Remaining 50% at TP2
                    total_pnl += pnl2
                    mae_pct = abs(entry_px - mae) / entry_px * 100
                    mfe_pct = abs(mfe - entry_px) / entry_px * 100
                    return {'Result': 'WIN', 'PnL_Pct': total_pnl, 'MAE_Pct': mae_pct, 'MFE_Pct': mfe_pct, 'Exit_Reason': 'TP2'}
            
            # Stop Loss (only on remaining position)
            sl_hit = (pos == 1 and bar['low'] <= sl_px) or (pos == -1 and bar['high'] >= sl_px)
            if sl_hit:
                if tp1_hit:
                    # Already took TP1, now SL on remaining
                    sl_pnl = -max_sl * (1 - tp1_qty)
                    total_pnl += sl_pnl
                else:
                    # Full SL
                    total_pnl = -max_sl
                mae_pct = abs(entry_px - mae) / entry_px * 100
                mfe_pct = abs(mfe - entry_px) / entry_px * 100
                result = 'WIN' if total_pnl > 0 else 'LOSS'
                return {'Result': result, 'PnL_Pct': total_pnl, 'MAE_Pct': mae_pct, 'MFE_Pct': mfe_pct, 'Exit_Reason': 'SL'}
            
            # Time Exit
            if i == len(market_data) - 1:
                exit_px = bar['close']
                time_pnl = ((exit_px - entry_px) / entry_px * 100) if pos == 1 else ((entry_px - exit_px) / entry_px * 100)
                if tp1_hit:
                    total_pnl += time_pnl * (1 - tp1_qty)  # Time exit on remaining
                else:
                    total_pnl = time_pnl  # Full time exit
                mae_pct = abs(entry_px - mae) / entry_px * 100
                mfe_pct = abs(mfe - entry_px) / entry_px * 100
                result = 'WIN' if total_pnl > 0 else 'LOSS'
                return {'Result': result, 'PnL_Pct': total_pnl, 'MAE_Pct': mae_pct, 'MFE_Pct': mfe_pct, 'Exit_Reason': 'TIME'}
    
    return None

def calculate_pf(df):
    if df.empty: return 0
    gross_profit = df[df['PnL_Pct'] > 0]['PnL_Pct'].sum()
    gross_loss = abs(df[df['PnL_Pct'] < 0]['PnL_Pct'].sum())
    return gross_profit / gross_loss if gross_loss > 0 else float('inf')

# MAIN
print("Loading data...")
or_df, df_1m, df_daily, vvix = load_data()

print("\n=== V7 COMBINED CONFIGURATION TEST ===")
print("Parameters:")
for k, v in V7_CONFIG.items():
    print(f"  {k}: {v}")

print("\nRunning backtest...")
trades = run_backtest(or_df, df_1m, df_daily, vvix, V7_CONFIG)

if not trades.empty:
    pf = calculate_pf(trades)
    winners = len(trades[trades['PnL_Pct'] > 0])
    losers = len(trades[trades['PnL_Pct'] <= 0])
    
    print("\n=== RESULTS ===")
    print(f"Total Trades: {len(trades)}")
    print(f"Win Rate: {winners/len(trades):.2%}")
    print(f"Winners: {winners} | Losers: {losers}")
    print(f"Gross PnL: {trades['PnL_Pct'].sum():.2f}%")
    print(f"Avg PnL: {trades['PnL_Pct'].mean():.4f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Avg MAE: {trades['MAE_Pct'].mean():.4f}%")
    print(f"Avg MFE: {trades['MFE_Pct'].mean():.4f}%")
    
    print("\n=== EXIT REASONS ===")
    for reason in trades['Exit_Reason'].unique():
        count = len(trades[trades['Exit_Reason'] == reason])
        print(f"  {reason}: {count} ({count/len(trades)*100:.1f}%)")
    
    # Save results
    output_dir = "scripts/backtest/9_30_breakout/results"
    trades.to_csv(os.path.join(output_dir, "v7_optimized_immediate_multitp.csv"), index=False)
    print(f"\nSaved: v7_optimized_immediate_multitp.csv")
else:
    print("No trades found.")
