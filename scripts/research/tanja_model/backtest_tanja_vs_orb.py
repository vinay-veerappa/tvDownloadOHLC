"""
Tanja Model vs Basic ORB Backtest
==================================
Compare the Tanja 930 model (wait for Judas, trade reversal) against
basic ORB breakout strategy.

Strategy A: BASIC ORB
- Enter on break of 9:30-9:31 opening range
- Direction: breakout direction
- Exit: 9:44

Strategy B: TANJA MODEL (Judas Reversal)
- Wait for first move (liquidity grab)
- Enter opposite direction after sweep
- Exit: 9:44

Key insight from validation: 
- First move UP → 87% ends BEARISH
- First move DOWN → 90% ends BULLISH
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

DATA_DIR = Path("data")
TICKER = "NQ1"
OUTPUT_DIR = Path("scripts/research/ml_price_curves/output")


def load_1m_data():
    """Load 1-minute OHLC data."""
    file_path = DATA_DIR / f"{TICKER}_1m.parquet"
    df = pd.read_parquet(file_path)
    
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
        df = df.set_index('datetime')
    
    return df


def get_opening_range(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date):
    """Get the 9:30-9:31 opening range (first 2 minutes)."""
    mask = (np_date == target_date) & (np_hour == 9) & ((np_minute == 30) | (np_minute == 31))
    
    if mask.sum() < 1:
        return None
    
    return {
        'or_high': np_high[mask].max(),
        'or_low': np_low[mask].min(),
        'or_open': np_open[mask][0],
    }


def simulate_basic_orb(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date, or_data):
    """
    Simulate basic ORB strategy:
    - Enter on break of OR high (LONG) or OR low (SHORT)
    - Exit at 9:44
    """
    mask_session = (np_date == target_date) & (np_hour == 9) & (np_minute >= 32) & (np_minute <= 44)
    idxs = np.where(mask_session)[0]
    
    if len(idxs) < 5:
        return None
    
    or_high = or_data['or_high']
    or_low = or_data['or_low']
    
    entry_price = None
    entry_direction = None
    entry_minute = None
    
    # Check for breakout
    for idx in idxs:
        minute = np_minute[idx]
        high = np_high[idx]
        low = np_low[idx]
        
        if high > or_high and entry_price is None:
            # Breakout long
            entry_price = or_high
            entry_direction = 'LONG'
            entry_minute = minute
            break
        elif low < or_low and entry_price is None:
            # Breakout short
            entry_price = or_low
            entry_direction = 'SHORT'
            entry_minute = minute
            break
    
    if entry_price is None:
        return None  # No breakout
    
    # Get exit price at 9:44
    mask_exit = (np_date == target_date) & (np_hour == 9) & (np_minute == 44)
    exit_idxs = np.where(mask_exit)[0]
    
    if len(exit_idxs) == 0:
        return None
    
    exit_price = np_close[exit_idxs[0]]
    
    # Calculate P&L
    if entry_direction == 'LONG':
        pnl_points = exit_price - entry_price
    else:
        pnl_points = entry_price - exit_price
    
    return {
        'entry_price': entry_price,
        'entry_direction': entry_direction,
        'entry_minute': entry_minute,
        'exit_price': exit_price,
        'pnl_points': pnl_points,
    }


def simulate_tanja_model(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date, or_data):
    """
    Simulate Tanja Judas reversal model:
    - Detect first move direction (which extreme forms first)
    - Trade opposite direction
    - Stop-loss at opening range extreme
    - Exit at 9:44 or stop-loss hit
    
    Entry: After 9:35 (wait for Judas sweep)
    Direction: Opposite of first move
    Stop-Loss: OR high (for short) or OR low (for long)
    """
    or_high = or_data['or_high']
    or_low = or_data['or_low']
    
    # Get 9:30-9:35 data to detect first move
    mask_first = (np_date == target_date) & (np_hour == 9) & (np_minute >= 30) & (np_minute <= 35)
    first_idxs = np.where(mask_first)[0]
    
    if len(first_idxs) < 3:
        return None
    
    # Find which extreme forms first in this window
    first_highs = np_high[first_idxs]
    first_lows = np_low[first_idxs]
    
    high_idx = np.argmax(first_highs)
    low_idx = np.argmin(first_lows)
    
    if high_idx < low_idx:
        # High formed first = fake bullish = trade BEARISH
        first_move = 'UP'
        entry_direction = 'SHORT'
        stop_loss = or_high  # Stop above OR high
    else:
        # Low formed first = fake bearish = trade BULLISH
        first_move = 'DOWN'
        entry_direction = 'LONG'
        stop_loss = or_low  # Stop below OR low
    
    # Entry at 9:36
    mask_entry = (np_date == target_date) & (np_hour == 9) & (np_minute == 36)
    entry_idxs = np.where(mask_entry)[0]
    
    if len(entry_idxs) == 0:
        return None
    
    entry_price = np_open[entry_idxs[0]]
    entry_minute = 36
    
    # Check for stop-loss hit from entry to 9:44
    mask_session = (np_date == target_date) & (np_hour == 9) & (np_minute >= 36) & (np_minute <= 44)
    session_idxs = np.where(mask_session)[0]
    
    stopped_out = False
    exit_price = None
    exit_minute = None
    
    for idx in session_idxs:
        high = np_high[idx]
        low = np_low[idx]
        minute = np_minute[idx]
        
        if entry_direction == 'LONG' and low <= stop_loss:
            # Stop-loss hit for long
            stopped_out = True
            exit_price = stop_loss
            exit_minute = minute
            break
        elif entry_direction == 'SHORT' and high >= stop_loss:
            # Stop-loss hit for short
            stopped_out = True
            exit_price = stop_loss
            exit_minute = minute
            break
    
    # If not stopped, exit at 9:44
    if not stopped_out:
        mask_exit = (np_date == target_date) & (np_hour == 9) & (np_minute == 44)
        exit_idxs = np.where(mask_exit)[0]
        
        if len(exit_idxs) == 0:
            return None
        
        exit_price = np_close[exit_idxs[0]]
        exit_minute = 44
    
    # Calculate P&L
    if entry_direction == 'LONG':
        pnl_points = exit_price - entry_price
    else:
        pnl_points = entry_price - exit_price
    
    return {
        'entry_price': entry_price,
        'entry_direction': entry_direction,
        'entry_minute': entry_minute,
        'exit_price': exit_price,
        'exit_minute': exit_minute,
        'pnl_points': pnl_points,
        'first_move': first_move,
        'stopped_out': stopped_out,
        'stop_loss': stop_loss,
    }


def main():
    print("="*70)
    print("TANJA MODEL vs BASIC ORB BACKTEST")
    print("="*70)
    
    # Load data
    print("\nLoading 1-minute data...")
    df = load_1m_data()
    print(f"Loaded {len(df)} bars")
    
    # Pre-compute arrays
    np_open = df['open'].values
    np_high = df['high'].values
    np_low = df['low'].values
    np_close = df['close'].values
    np_hour = df.index.hour.values
    np_minute = df.index.minute.values
    np_date = df.index.date
    
    # Filter to 2023-2024
    start_date = date(2023, 1, 1)
    end_date = date(2024, 12, 31)
    
    unique_dates = np.unique(np_date)
    unique_dates = [d for d in unique_dates if start_date <= d <= end_date]
    print(f"Backtesting {len(unique_dates)} trading days (2023-2024)")
    
    orb_results = []
    tanja_results = []
    
    for i, target_date in enumerate(unique_dates):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(unique_dates)}")
        
        # Get opening range
        or_data = get_opening_range(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date)
        
        if not or_data:
            continue
        
        # Basic ORB
        orb = simulate_basic_orb(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date, or_data)
        if orb:
            orb['date'] = str(target_date)
            orb_results.append(orb)
        
        # Tanja Model
        tanja = simulate_tanja_model(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date, or_data)
        if tanja:
            tanja['date'] = str(target_date)
            tanja_results.append(tanja)
    
    df_orb = pd.DataFrame(orb_results)
    df_tanja = pd.DataFrame(tanja_results)
    
    print(f"\nORB trades: {len(df_orb)}")
    print(f"Tanja trades: {len(df_tanja)}")
    
    # Summary Statistics
    print("\n" + "="*70)
    print("RESULTS COMPARISON")
    print("="*70)
    
    print(f"\n{'Metric':<25} | {'Basic ORB':>12} | {'Tanja Model':>12}")
    print("-"*55)
    
    # Total trades
    print(f"{'Total Trades':<25} | {len(df_orb):>12} | {len(df_tanja):>12}")
    
    # Win rate
    orb_wins = (df_orb['pnl_points'] > 0).sum()
    orb_wr = orb_wins / len(df_orb) * 100 if len(df_orb) > 0 else 0
    
    tanja_wins = (df_tanja['pnl_points'] > 0).sum()
    tanja_wr = tanja_wins / len(df_tanja) * 100 if len(df_tanja) > 0 else 0
    
    print(f"{'Win Rate':<25} | {orb_wr:>11.1f}% | {tanja_wr:>11.1f}%")
    
    # Avg P&L
    orb_avg = df_orb['pnl_points'].mean() if len(df_orb) > 0 else 0
    tanja_avg = df_tanja['pnl_points'].mean() if len(df_tanja) > 0 else 0
    
    print(f"{'Avg P&L (points)':<25} | {orb_avg:>12.2f} | {tanja_avg:>12.2f}")
    
    # Total P&L
    orb_total = df_orb['pnl_points'].sum() if len(df_orb) > 0 else 0
    tanja_total = df_tanja['pnl_points'].sum() if len(df_tanja) > 0 else 0
    
    print(f"{'Total P&L (points)':<25} | {orb_total:>12.2f} | {tanja_total:>12.2f}")
    
    # Profit factor
    orb_gross_profit = df_orb[df_orb['pnl_points'] > 0]['pnl_points'].sum() if len(df_orb) > 0 else 0
    orb_gross_loss = abs(df_orb[df_orb['pnl_points'] < 0]['pnl_points'].sum()) if len(df_orb) > 0 else 1
    orb_pf = orb_gross_profit / orb_gross_loss if orb_gross_loss > 0 else 0
    
    tanja_gross_profit = df_tanja[df_tanja['pnl_points'] > 0]['pnl_points'].sum() if len(df_tanja) > 0 else 0
    tanja_gross_loss = abs(df_tanja[df_tanja['pnl_points'] < 0]['pnl_points'].sum()) if len(df_tanja) > 0 else 1
    tanja_pf = tanja_gross_profit / tanja_gross_loss if tanja_gross_loss > 0 else 0
    
    print(f"{'Profit Factor':<25} | {orb_pf:>12.2f} | {tanja_pf:>12.2f}")
    
    # Max Win / Max Loss
    print(f"{'Max Win (points)':<25} | {df_orb['pnl_points'].max():>12.2f} | {df_tanja['pnl_points'].max():>12.2f}")
    print(f"{'Max Loss (points)':<25} | {df_orb['pnl_points'].min():>12.2f} | {df_tanja['pnl_points'].min():>12.2f}")
    
    # Breakdown by direction
    print("\n" + "="*70)
    print("TANJA MODEL BY FIRST MOVE")
    print("="*70)
    
    for first_move in ['UP', 'DOWN']:
        subset = df_tanja[df_tanja['first_move'] == first_move]
        if len(subset) == 0:
            continue
        
        wr = (subset['pnl_points'] > 0).mean() * 100
        avg = subset['pnl_points'].mean()
        
        print(f"\nFirst Move {first_move}: {len(subset)} trades")
        print(f"  Win Rate: {wr:.1f}%")
        print(f"  Avg P&L: {avg:.2f} points")
    
    print("\n" + "="*70)
    print("BACKTEST COMPLETE")
    print("="*70)
    
    # Save
    df_orb.to_csv(OUTPUT_DIR / 'backtest_orb.csv', index=False)
    df_tanja.to_csv(OUTPUT_DIR / 'backtest_tanja.csv', index=False)
    print(f"\nResults saved to output/")


if __name__ == "__main__":
    main()
