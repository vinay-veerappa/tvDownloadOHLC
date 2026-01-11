"""
9:28 / 9:32 Candle Relationship Analysis
=========================================
Theory: The 9:28 candle is a directional signal for 9:30-9:59.

Patterns to test:
1. KISS: 9:32 touches 9:28 (close proximity) → Direction confirmed
2. ON_TOP: 9:32 high > 9:28 high AND 9:32 low > 9:28 low → Bullish confirmed
3. BELOW: 9:32 low < 9:28 low AND 9:32 high < 9:28 high → Bearish confirmed
4. ENGULF: 9:32 fully contains/swallows 9:28 → Direction uncertain (Judas)

Measure: Does the 9:30-9:59 (or 9:32-9:59) move align with 9:28 direction?
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("data")
TICKER = "NQ1"


def load_1m_data():
    """Load 1-minute OHLC data."""
    file_path = DATA_DIR / f"{TICKER}_1m.parquet"
    df = pd.read_parquet(file_path)
    
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
        df = df.set_index('datetime')
    
    return df


def classify_928_direction(candle):
    """Classify 9:28 candle direction."""
    if candle['close'] > candle['open']:
        return 'BULLISH'
    elif candle['close'] < candle['open']:
        return 'BEARISH'
    else:
        return 'DOJI'


def classify_relationship(c928, c932):
    """
    Classify the relationship between 9:28 and 9:32 candles.
    
    Returns: (pattern, description)
    """
    # Calculate range overlap
    overlap_high = min(c928['high'], c932['high'])
    overlap_low = max(c928['low'], c932['low'])
    
    # 9:32 fully above 9:28 (Bullish confirmation)
    if c932['low'] >= c928['high']:
        return 'GAP_UP', '9:32 gapped up above 9:28'
    
    # 9:32 fully below 9:28 (Bearish confirmation)
    if c932['high'] <= c928['low']:
        return 'GAP_DOWN', '9:32 gapped down below 9:28'
    
    # 9:32 ON TOP of 9:28 (Bullish bias)
    if c932['high'] > c928['high'] and c932['low'] > c928['low']:
        return 'ON_TOP', '9:32 is on top of 9:28 (bullish)'
    
    # 9:32 BELOW 9:28 (Bearish bias)
    if c932['low'] < c928['low'] and c932['high'] < c928['high']:
        return 'BELOW', '9:32 is below 9:28 (bearish)'
    
    # 9:32 ENGULFS 9:28 (Judas/uncertain)
    if c932['high'] >= c928['high'] and c932['low'] <= c928['low']:
        return 'ENGULF', '9:32 swallows/engulfs 9:28 (Judas)'
    
    # 9:32 INSIDE 9:28 (consolidation)
    if c932['high'] <= c928['high'] and c932['low'] >= c928['low']:
        return 'INSIDE', '9:32 is inside 9:28 (consolidation)'
    
    # KISS - overlapping but neither fully contains the other
    return 'KISS', '9:28 and 9:32 overlap (kissing)'


def get_session_outcome(df_session):
    """
    Calculate outcome for 9:32-9:59 period.
    Returns: direction (BULLISH/BEARISH), % move
    """
    if len(df_session) < 2:
        return None, 0
    
    open_price = df_session['open'].iloc[0]
    close_price = df_session['close'].iloc[-1]
    
    pct_move = (close_price - open_price) / open_price * 100
    
    if close_price > open_price:
        return 'BULLISH', pct_move
    elif close_price < open_price:
        return 'BEARISH', pct_move
    else:
        return 'FLAT', pct_move


def main():
    print("="*70)
    print("9:28 / 9:32 CANDLE RELATIONSHIP ANALYSIS")
    print("="*70)
    
    # Load data
    print("\nLoading 1-minute data...")
    df = load_1m_data()
    print(f"Loaded {len(df)} bars")
    
    # Pre-compute arrays for speed
    np_open = df['open'].values
    np_high = df['high'].values
    np_low = df['low'].values
    np_close = df['close'].values
    np_hour = df.index.hour.values
    np_minute = df.index.minute.values
    np_date = df.index.date
    
    # Filter to 2023-2024 only for faster analysis
    from datetime import date
    start_date = date(2023, 1, 1)
    end_date = date(2024, 12, 31)
    date_filter = (np_date >= start_date) & (np_date <= end_date)
    
    np_open = np_open[date_filter]
    np_high = np_high[date_filter]
    np_low = np_low[date_filter]
    np_close = np_close[date_filter]
    np_hour = np_hour[date_filter]
    np_minute = np_minute[date_filter]
    np_date = np_date[date_filter]
    
    unique_dates = np.unique(np_date)
    print(f"Filtered to 2023-2024: {len(unique_dates)} trading days")
    
    results = []
    
    for i, date in enumerate(unique_dates):
        if i % 1000 == 0:
            print(f"  Progress: {i}/{len(unique_dates)}")
        
        # Fast mask for this date
        date_mask = np_date == date
        
        # Find 9:28 candle
        mask_928 = date_mask & (np_hour == 9) & (np_minute == 28)
        idx_928 = np.where(mask_928)[0]
        
        if len(idx_928) == 0:
            continue
        
        idx_928 = idx_928[0]
        c928 = {
            'open': np_open[idx_928],
            'high': np_high[idx_928],
            'low': np_low[idx_928],
            'close': np_close[idx_928]
        }
        
        # Find 9:32 candle
        mask_932 = date_mask & (np_hour == 9) & (np_minute == 32)
        idx_932 = np.where(mask_932)[0]
        
        if len(idx_932) == 0:
            continue
        
        idx_932 = idx_932[0]
        c932 = {
            'open': np_open[idx_932],
            'high': np_high[idx_932],
            'low': np_low[idx_932],
            'close': np_close[idx_932]
        }
        
        # Find 9:30 candle (Opening Range)
        mask_930 = date_mask & (np_hour == 9) & (np_minute == 30)
        idx_930 = np.where(mask_930)[0]
        
        if len(idx_930) == 0:
            continue
            
        c930_high = np_high[idx_930[0]]
        c930_low = np_low[idx_930[0]]
        
        # Find 9:31-9:44 session (Extension Window)
        session_mask = date_mask & (np_hour == 9) & (np_minute >= 31) & (np_minute <= 44)
        session_idxs = np.where(session_mask)[0]
        
        if len(session_idxs) < 5:
            continue
        
        # Calculate extensions
        session_high = np_high[session_idxs].max()
        session_low = np_low[session_idxs].min()
        
        ext_up = max(0, (session_high - c930_high) / c930_high * 100)
        ext_down = max(0, (c930_low - session_low) / c930_low * 100)
        
        # Determine winning side
        if ext_up > ext_down:
            win_side = 'UP'
            win_score = ext_up
        elif ext_down > ext_up:
            win_side = 'DOWN'
            win_score = ext_down
        else:
            win_side = 'NEUTRAL'
            win_score = 0

        # Classify patterns
        c928_dir = classify_928_direction(c928)
        pattern, _ = classify_relationship(c928, c932)
        
        # Check alignment (Bullish pattern -> Up extension?)
        aligned = False
        if c928_dir == 'BULLISH' and win_side == 'UP':
            aligned = True
        elif c928_dir == 'BEARISH' and win_side == 'DOWN':
            aligned = True
            
        results.append({
            'date': str(date),
            'c928_dir': c928_dir,
            'pattern': pattern,
            'win_side': win_side,
            'ext_up': ext_up,
            'ext_down': ext_down,
            'aligned': aligned,
        })
    
    df_results = pd.DataFrame(results)
    print(f"\nAnalyzed {len(df_results)} valid trading days")
    
    # Summary by pattern
    print("\n" + "="*70)
    print("RESULTS BY PATTERN (Predicting 9:30-9:44 Extension %)")
    print("="*70)
    print("Do these patterns predict which side of the 9:30 range breaks further?")
    
    print(f"\n{'Pattern':<12} | {'Count':>6} | {'Aligned':>8} | {'Win Rate':>8} | {'Avg Ext (%)':>14}")
    print("-"*70)
    
    for pattern in ['ON_TOP', 'BELOW', 'KISS', 'ENGULF', 'GAP_UP', 'GAP_DOWN', 'INSIDE']:
        subset = df_results[df_results['pattern'] == pattern]
        if len(subset) == 0:
            continue
        
        # Win Rate calculation
        # If Pattern implies UP (Bullish), how often did UP win?
        # We need a 'predicted_direction' logic for this table
        
        # Assume standard logic:
        # ON_TOP, GAP_UP -> Predict UP
        # BELOW, GAP_DOWN -> Predict DOWN
        # ENGULF, INSIDE, KISS -> Uncertain (check alignment with 9:28 dir)
        
        if pattern in ['ON_TOP', 'GAP_UP']:
            wins = (subset['win_side'] == 'UP').sum()
            avg_ext = subset['ext_up'].mean()
        elif pattern in ['BELOW', 'GAP_DOWN']:
            wins = (subset['win_side'] == 'DOWN').sum()
            avg_ext = subset['ext_down'].mean()
        else:
            # For neutral patterns, check alignment with 9:28 dir
            wins = subset['aligned'].sum()
            # Avg extension of the *aligned* side
            exts = []
            for _, row in subset.iterrows():
                if row['aligned']:
                    exts.append(row['ext_up'] if row['c928_dir'] == 'BULLISH' else row['ext_down'])
            avg_ext = np.mean(exts) if exts else 0
            
        count = len(subset)
        rate = wins / count * 100
        
        print(f"{pattern:<12} | {count:>6} | {wins:>8} | {rate:>7.1f}% | {avg_ext:>13.3f}%")
    
    # Summary by 9:28 direction
    print("\n" + "="*70)
    print("RESULTS BY 9:28 DIRECTION")
    print("="*70)
    
    for dir_928 in ['BULLISH', 'BEARISH']:
        subset = df_results[df_results['c928_dir'] == dir_928]
        if len(subset) == 0:
            continue
        
        if dir_928 == 'BULLISH':
            correct = (subset['win_side'] == 'UP').sum()
            avg_win = subset[subset['win_side'] == 'UP']['ext_up'].mean()
        else:
            correct = (subset['win_side'] == 'DOWN').sum()
            avg_win = subset[subset['win_side'] == 'DOWN']['ext_down'].mean()

        rate = correct / len(subset) * 100
        print(f"\n9:28 = {dir_928}")
        print(f"  Total: {len(subset)}")
        print(f"  Correct Prediction: {correct} ({rate:.1f}%)")
        print(f"  Avg Winning Extension: {avg_win:.3f}%")

    # Specific Combo Check
    print("\n" + "="*70)
    print("GOLDEN COMBO CHECK")
    print("="*70)
    
    bull_combo = df_results[(df_results['c928_dir'] == 'BULLISH') & (df_results['pattern'] == 'ON_TOP')]
    if len(bull_combo) > 0:
        wins = (bull_combo['win_side'] == 'UP').sum()
        rate = wins / len(bull_combo) * 100
        avg_ext = bull_combo['ext_up'].mean()
        print(f"9:28 BULLISH + ON_TOP: {len(bull_combo)} trades")
        print(f"  Extension UP Win Rate: {rate:.1f}%")
        print(f"  Avg Extension UP: {avg_ext:.3f}%")
    
    # Save results
    output_path = Path("scripts/research/ml_price_curves/output/candle_928_932_results.csv")
    df_results.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
