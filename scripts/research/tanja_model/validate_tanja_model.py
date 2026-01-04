"""
930 Tanja Model Validation
============================
Validating the strategy rules from Model_930_Tanja.pdf

Rules to test:
1. 8:50-9:10 macro as consolidation/liquidity zone
2. 9:20-9:29 range predicts Judas delivery timing
3. 9:28 directional candle (already confirmed: 57% with ON_TOP)
4. 932 relationship to 928 (KISS, ON_TOP, ENGULF)

Key Concepts:
- Judas = False move that traps traders before real direction
- Expansion = Directional move continuing from pre-market
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

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


def analyze_macro_850_910(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date):
    """
    Analyze the 8:50-9:10 macro range.
    Returns: high, low, range_size, midpoint
    """
    mask = (np_date == target_date) & (np_hour == 8) & (np_minute >= 50) | \
           (np_date == target_date) & (np_hour == 9) & (np_minute <= 10)
    
    if mask.sum() < 5:
        return None
    
    macro_high = np_high[mask].max()
    macro_low = np_low[mask].min()
    
    return {
        'macro_high': macro_high,
        'macro_low': macro_low,
        'macro_range': macro_high - macro_low,
        'macro_mid': (macro_high + macro_low) / 2
    }


def analyze_920_929_range(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date):
    """
    Analyze the 9:20-9:29 pre-open range.
    Determine: Is there a directional bias? High volatility?
    """
    mask = (np_date == target_date) & (np_hour == 9) & (np_minute >= 20) & (np_minute <= 29)
    
    if mask.sum() < 5:
        return None
    
    idxs = np.where(mask)[0]
    open_price = np_open[idxs[0]]
    close_price = np_close[idxs[-1]]
    high = np_high[mask].max()
    low = np_low[mask].min()
    
    direction = 'BULLISH' if close_price > open_price else ('BEARISH' if close_price < open_price else 'NEUTRAL')
    range_pct = (high - low) / open_price * 100
    
    # Check for potential Judas setup (price at extreme then reverses)
    # If close near low of range = potential bullish Judas (fake bearish)
    # If close near high of range = potential bearish Judas (fake bullish)
    range_size = high - low
    if range_size > 0:
        close_position = (close_price - low) / range_size  # 0 = at low, 1 = at high
    else:
        close_position = 0.5
    
    return {
        'preopen_direction': direction,
        'preopen_range_pct': range_pct,
        'preopen_close_position': close_position,  # 0=at low, 1=at high
        'preopen_high': high,
        'preopen_low': low,
    }


def analyze_930_959_session(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date):
    """
    Analyze the actual 9:30-9:59 session.
    Determine: Direction, whether it swept pre-market levels, Judas detection
    """
    mask = (np_date == target_date) & (np_hour == 9) & (np_minute >= 30) & (np_minute <= 59)
    
    if mask.sum() < 10:
        return None
    
    idxs = np.where(mask)[0]
    open_price = np_open[idxs[0]]
    close_price = np_close[idxs[-1]]
    high = np_high[mask].max()
    low = np_low[mask].min()
    
    direction = 'BULLISH' if close_price > open_price else ('BEARISH' if close_price < open_price else 'NEUTRAL')
    
    # Find when high and low occurred (minute offset from 9:30)
    high_idx = idxs[np.argmax(np_high[mask])]
    low_idx = idxs[np.argmin(np_low[mask])]
    
    high_minute = np_minute[high_idx]
    low_minute = np_minute[low_idx]
    
    return {
        'session_direction': direction,
        'session_open': open_price,
        'session_close': close_price,
        'session_high': high,
        'session_low': low,
        'session_pct_move': (close_price - open_price) / open_price * 100,
        'high_minute': high_minute,
        'low_minute': low_minute,
    }


def detect_judas(preopen_data, session_data, macro_data):
    """
    Detect if a Judas move occurred.
    Judas = Initial move that sweeps liquidity then reverses.
    
    Signs of Judas:
    1. Session starts bullish but ends bearish (or vice versa)
    2. Session sweeps pre-open high/low before reversing
    3. Session sweeps 8:50-9:10 macro level before reversing
    """
    if not all([preopen_data, session_data]):
        return None
    
    session_dir = session_data['session_direction']
    
    # Check if high formed before low (potential bullish Judas = fake bearish first)
    # Check if low formed before high (potential bearish Judas = fake bullish first)
    
    if session_data['high_minute'] < session_data['low_minute']:
        # High formed first, then low - potential bearish move after fake bullish
        first_move = 'UP'
    elif session_data['low_minute'] < session_data['high_minute']:
        # Low formed first, then high - potential bullish move after fake bearish
        first_move = 'DOWN'
    else:
        first_move = 'SIMULTANEOUS'
    
    # Judas detection
    is_judas = False
    judas_type = None
    
    if first_move == 'UP' and session_dir == 'BEARISH':
        is_judas = True
        judas_type = 'BEARISH_JUDAS'  # Fake bullish, real bearish
    elif first_move == 'DOWN' and session_dir == 'BULLISH':
        is_judas = True
        judas_type = 'BULLISH_JUDAS'  # Fake bearish, real bullish
    
    return {
        'is_judas': is_judas,
        'judas_type': judas_type,
        'first_move': first_move,
    }


def main():
    print("="*70)
    print("930 TANJA MODEL VALIDATION")
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
    print(f"Analyzing {len(unique_dates)} trading days (2023-2024)")
    
    results = []
    
    for i, target_date in enumerate(unique_dates):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(unique_dates)}")
        
        # Analyze each component
        macro = analyze_macro_850_910(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date)
        preopen = analyze_920_929_range(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date)
        session = analyze_930_959_session(np_open, np_high, np_low, np_close, np_hour, np_minute, np_date, target_date)
        
        if not all([preopen, session]):
            continue
        
        judas = detect_judas(preopen, session, macro)
        
        row = {
            'date': str(target_date),
            'preopen_dir': preopen['preopen_direction'],
            'preopen_close_pos': preopen['preopen_close_position'],
            'session_dir': session['session_direction'],
            'session_pct': session['session_pct_move'],
            'high_minute': session['high_minute'],
            'low_minute': session['low_minute'],
            'is_judas': judas['is_judas'] if judas else False,
            'judas_type': judas['judas_type'] if judas else None,
            'first_move': judas['first_move'] if judas else None,
        }
        
        results.append(row)
    
    df_results = pd.DataFrame(results)
    print(f"\nAnalyzed {len(df_results)} valid trading days")
    
    # Analysis 1: Pre-open direction predicts session direction?
    print("\n" + "="*70)
    print("1. DOES 9:20-9:29 DIRECTION PREDICT 9:30-9:59 DIRECTION?")
    print("="*70)
    
    for preopen_dir in ['BULLISH', 'BEARISH']:
        subset = df_results[df_results['preopen_dir'] == preopen_dir]
        if len(subset) == 0:
            continue
        
        same_dir = (subset['preopen_dir'] == subset['session_dir']).sum()
        rate = same_dir / len(subset) * 100
        print(f"\n9:20-9:29 {preopen_dir}: {len(subset)} days")
        print(f"  Session same direction: {same_dir} ({rate:.1f}%)")
    
    # Analysis 2: Pre-open close position predicts direction?
    print("\n" + "="*70)
    print("2. PRE-OPEN CLOSE POSITION AS JUDAS INDICATOR")
    print("="*70)
    print("(If close is near low of 9:20-9:29 range, expect bullish session)")
    
    # Close at low = potential bullish
    at_low = df_results[df_results['preopen_close_pos'] < 0.3]
    if len(at_low) > 0:
        bullish_rate = (at_low['session_dir'] == 'BULLISH').mean() * 100
        print(f"\nClose at LOW of pre-open range ({len(at_low)} days): {bullish_rate:.1f}% bullish sessions")
    
    # Close at high = potential bearish
    at_high = df_results[df_results['preopen_close_pos'] > 0.7]
    if len(at_high) > 0:
        bearish_rate = (at_high['session_dir'] == 'BEARISH').mean() * 100
        print(f"Close at HIGH of pre-open range ({len(at_high)} days): {bearish_rate:.1f}% bearish sessions")
    
    # Analysis 3: Judas occurrence
    print("\n" + "="*70)
    print("3. JUDAS MOVE FREQUENCY")
    print("="*70)
    
    judas_days = df_results[df_results['is_judas'] == True]
    print(f"\nTotal Judas days: {len(judas_days)} / {len(df_results)} ({len(judas_days)/len(df_results)*100:.1f}%)")
    
    for jtype in ['BULLISH_JUDAS', 'BEARISH_JUDAS']:
        subset = judas_days[judas_days['judas_type'] == jtype]
        if len(subset) > 0:
            print(f"  {jtype}: {len(subset)} days")
    
    # Analysis 4: First move direction
    print("\n" + "="*70)
    print("4. FIRST MOVE (HIGH vs LOW FIRST)")
    print("="*70)
    
    for first_move in ['UP', 'DOWN']:
        subset = df_results[df_results['first_move'] == first_move]
        if len(subset) == 0:
            continue
        
        # What % end in opposite direction?
        if first_move == 'UP':
            reversal_rate = (subset['session_dir'] == 'BEARISH').mean() * 100
            print(f"\nFirst move UP (high before low): {len(subset)} days")
            print(f"  Ends BEARISH (reversal): {reversal_rate:.1f}%")
        else:
            reversal_rate = (subset['session_dir'] == 'BULLISH').mean() * 100
            print(f"\nFirst move DOWN (low before high): {len(subset)} days")
            print(f"  Ends BULLISH (reversal): {reversal_rate:.1f}%")
    
    print("\n" + "="*70)
    print("VALIDATION COMPLETE")
    print("="*70)
    
    # Save
    output_path = Path("scripts/research/ml_price_curves/output/tanja_model_results.csv")
    df_results.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
