"""
Vectorbt-based Trade Simulator
==============================
Uses vectorbt library for high-performance vectorized backtesting.

DEPENDENCIES:
    pip install vectorbt

USAGE:
    from simulate_trades_vectorbt import run_orb_backtest
    results = run_orb_backtest('NQ1', years=10)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import time

# Check if vectorbt is installed
try:
    import vectorbt as vbt
    HAS_VECTORBT = True
except ImportError:
    HAS_VECTORBT = False
    print("WARNING: vectorbt not installed. Install with: pip install vectorbt")


def load_data(ticker: str, years: int = 10):
    """Load OHLC data and opening range"""
    # Opening range
    with open(f'data/{ticker}_opening_range.json', 'r') as f:
        or_data = json.load(f)
    or_df = pd.DataFrame(or_data)
    or_df['date'] = pd.to_datetime(or_df['date'])
    or_df = or_df.set_index('date')
    
    # 1m data
    df = pd.read_parquet(f'data/{ticker}_1m.parquet')
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s')
        df = df.set_index('datetime')
    if df.index.tz is None:
        df = df.tz_localize('UTC')
    df = df.tz_convert('US/Eastern').sort_index()
    
    # Filter period
    end_date = or_df.index.max()
    start_date = end_date - pd.Timedelta(days=years*365)
    or_df = or_df[or_df.index >= start_date]
    
    return df, or_df


def generate_signals(df_1m: pd.DataFrame, or_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Generate entry/exit signals for vectorbt.
    
    Returns DataFrame with columns: entries, exits, sl_stops, tp_stops
    """
    # Initialize signal arrays
    entries = pd.Series(False, index=df_1m.index)
    exits = pd.Series(False, index=df_1m.index)
    
    # Day-by-day signal generation
    for d, row in or_df.iterrows():
        r_high, r_low = row['high'], row['low']
        r_pct = row.get('range_pct', (r_high - r_low) / row['open'])
        
        # Filters
        if d.dayofweek in [1, 2]:  # Tue, Wed
            continue
        if r_pct > config.get('max_range_pct', 0.25):
            continue
        
        # Time window
        d_loc = pd.Timestamp(d).tz_localize('US/Eastern')
        t_start = d_loc + pd.Timedelta(hours=9, minutes=31)
        t_end = d_loc + pd.Timedelta(hours=11, minutes=0)
        
        # Confirmation levels
        confirm_pct = config.get('confirm_pct', 0.10)
        confirm_long = r_high * (1 + confirm_pct / 100)
        confirm_short = r_low * (1 - confirm_pct / 100)
        
        # Find entry bar
        mask = (df_1m.index >= t_start) & (df_1m.index <= t_end)
        day_bars = df_1m.loc[mask]
        
        for bar_time, bar in day_bars.iterrows():
            if bar['close'] > confirm_long or bar['close'] < confirm_short:
                entries.loc[bar_time] = True
                break
        
        # Time exit
        if t_end in df_1m.index:
            exits.loc[t_end] = True
    
    return pd.DataFrame({
        'entries': entries,
        'exits': exits,
    })


def run_orb_backtest(ticker: str = 'NQ1', years: int = 10, config: dict = None):
    """
    Run ORB backtest using vectorbt.
    
    Parameters:
        ticker: Symbol to backtest
        years: Years of history
        config: Strategy configuration
    
    Returns:
        vbt.Portfolio object with results
    """
    if not HAS_VECTORBT:
        print("ERROR: vectorbt not installed. Run: pip install vectorbt")
        return None
    
    if config is None:
        config = {
            'confirm_pct': 0.10,
            'tp1_pct': 0.05,
            'max_range_pct': 0.25,
            'sl_pct': 0.25,  # Max SL %
        }
    
    print(f"Loading data for {ticker}...")
    df_1m, or_df = load_data(ticker, years)
    
    print("Generating signals...")
    signals = generate_signals(df_1m, or_df, config)
    
    print("Running vectorbt simulation...")
    
    # Create portfolio with vectorbt
    # Note: This is a simplified version - vectorbt handles SL/TP natively
    pf = vbt.Portfolio.from_signals(
        close=df_1m['close'],
        entries=signals['entries'],
        exits=signals['exits'],
        sl_stop=config['sl_pct'] / 100,  # Stop loss as fraction
        tp_stop=config['tp1_pct'] / 100,  # Take profit as fraction
        init_cash=100000,
        fees=0.0001,  # 0.01% fees per trade
        freq='1min',
    )
    
    return pf


def compare_results():
    """Compare custom simulator vs vectorbt"""
    print("=== SIMULATOR COMPARISON ===\n")
    
    # Run custom simulator
    print("1. Custom State Machine Simulator:")
    from simulate_trades import TradeSimulator, ORB_V7_Strategy
    strategy = ORB_V7_Strategy()
    sim = TradeSimulator(strategy)
    sim.load_data('NQ1', years=10)
    trades_df = sim.run()
    custom_summary = sim.summary()
    print(f"   Trades: {custom_summary['trades']}")
    print(f"   Win Rate: {custom_summary['win_rate']:.1%}")
    print(f"   Gross PnL: {custom_summary['gross_pnl']:.2f}%")
    print(f"   Profit Factor: {custom_summary['profit_factor']:.2f}")
    
    # Run vectorbt
    if HAS_VECTORBT:
        print("\n2. Vectorbt Simulator:")
        pf = run_orb_backtest('NQ1', years=10)
        if pf is not None:
            stats = pf.stats()
            print(f"   Total Trades: {stats['Total Trades']}")
            print(f"   Win Rate: {stats['Win Rate [%]']:.1f}%")
            print(f"   Total Return: {stats['Total Return [%]']:.2f}%")
            print(f"   Sharpe Ratio: {stats['Sharpe Ratio']:.2f}")
    else:
        print("\n2. Vectorbt: Not installed (pip install vectorbt)")
    
    print("\n=== COMPARISON NOTES ===")
    print("- Custom simulator has full control over entry/exit logic")
    print("- Vectorbt is faster but uses simplified SL/TP mechanics")
    print("- For complex logic (CTQ, engulfing), use custom simulator")


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    compare_results()
