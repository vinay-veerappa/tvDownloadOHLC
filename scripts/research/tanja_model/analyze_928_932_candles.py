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
        
        # Find 9:32-9:59 session
        session_mask = date_mask & (np_hour == 9) & (np_minute >= 32) & (np_minute <= 59)
        session_idxs = np.where(session_mask)[0]
        
        if len(session_idxs) < 5:
            continue
        
        session_open = np_open[session_idxs[0]]
        session_close = np_close[session_idxs[-1]]
        pct_move = (session_close - session_open) / session_open * 100
        
        # Classify
        c928_dir = classify_928_direction(c928)
        pattern, _ = classify_relationship(c928, c932)
        
        if session_close > session_open:
            outcome_dir = 'BULLISH'
        elif session_close < session_open:
            outcome_dir = 'BEARISH'
        else:
            outcome_dir = 'FLAT'
        
        aligned = (c928_dir == outcome_dir)
        
        results.append({
            'date': str(date),
            'c928_dir': c928_dir,
            'pattern': pattern,
            'session_dir': outcome_dir,
            'pct_move': pct_move,
            'aligned': aligned,
        })
    
    df_results = pd.DataFrame(results)
    print(f"\nAnalyzed {len(df_results)} valid trading days")
    
    # Summary by pattern
    print("\n" + "="*70)
    print("RESULTS BY PATTERN")
    print("="*70)
    
    print(f"\n{'Pattern':<12} | {'Count':>6} | {'Aligned':>8} | {'Rate':>6} | {'Avg Move':>10}")
    print("-"*55)
    
    for pattern in ['ON_TOP', 'BELOW', 'KISS', 'ENGULF', 'GAP_UP', 'GAP_DOWN', 'INSIDE']:
        subset = df_results[df_results['pattern'] == pattern]
        if len(subset) == 0:
            continue
        
        count = len(subset)
        aligned = subset['aligned'].sum()
        rate = aligned / count * 100
        avg_move = subset['pct_move'].abs().mean()
        
        print(f"{pattern:<12} | {count:>6} | {aligned:>8} | {rate:>5.1f}% | {avg_move:>9.3f}%")
    
    # Summary by 9:28 direction
    print("\n" + "="*70)
    print("RESULTS BY 9:28 DIRECTION")
    print("="*70)
    
    for dir_928 in ['BULLISH', 'BEARISH']:
        subset = df_results[df_results['c928_dir'] == dir_928]
        if len(subset) == 0:
            continue
        
        print(f"\n9:28 = {dir_928}")
        print(f"  Total: {len(subset)}")
        print(f"  Session aligned: {subset['aligned'].sum()} ({subset['aligned'].mean()*100:.1f}%)")
        print(f"  Avg session move: {subset['pct_move'].mean():.3f}%")
    
    # Key insight: ENGULF pattern
    print("\n" + "="*70)
    print("KEY INSIGHT: ENGULF (JUDAS) PATTERN")
    print("="*70)
    
    engulf = df_results[df_results['pattern'] == 'ENGULF']
    non_engulf = df_results[df_results['pattern'] != 'ENGULF']
    
    if len(engulf) > 0 and len(non_engulf) > 0:
        print(f"\nENGULF pattern alignment: {engulf['aligned'].mean()*100:.1f}%")
        print(f"Non-ENGULF pattern alignment: {non_engulf['aligned'].mean()*100:.1f}%")
        
        diff = non_engulf['aligned'].mean() - engulf['aligned'].mean()
        print(f"\nDifference: {diff*100:+.1f}% better alignment when NOT engulfed")
    
    # Confirmation patterns
    print("\n" + "="*70)
    print("CONFIRMATION PATTERNS (Best conditions)")
    print("="*70)
    
    # Bullish: 9:28 bullish + ON_TOP
    bull_confirm = df_results[(df_results['c928_dir'] == 'BULLISH') & (df_results['pattern'] == 'ON_TOP')]
    if len(bull_confirm) > 0:
        print(f"\n9:28 BULLISH + ON_TOP: {len(bull_confirm)} days, {bull_confirm['aligned'].mean()*100:.1f}% aligned")
    
    # Bearish: 9:28 bearish + BELOW
    bear_confirm = df_results[(df_results['c928_dir'] == 'BEARISH') & (df_results['pattern'] == 'BELOW')]
    if len(bear_confirm) > 0:
        print(f"9:28 BEARISH + BELOW: {len(bear_confirm)} days, {bear_confirm['aligned'].mean()*100:.1f}% aligned")
    
    # KISS pattern
    kiss = df_results[df_results['pattern'] == 'KISS']
    if len(kiss) > 0:
        print(f"\nKISS pattern overall: {len(kiss)} days, {kiss['aligned'].mean()*100:.1f}% aligned")
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    
    # Save results
    output_path = Path("scripts/research/ml_price_curves/output/candle_928_932_results.csv")
    df_results.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
