"""
ICT Time Levels Validation
===========================
Validate the core concepts from TTrades and MMT Trading:

1. Premium/Discount Rule: Below midnight+8:30 = LONG, Above = SHORT
2. 11:30 Cutoff: Levels lose predictive power after 11:30
3. 9:30 Judas Swing: First move reverses
4. 4H OHLC: 10:00/2:00 candle behavior
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, time

DATA_DIR = Path("data")
TICKER = "NQ1"
OUTPUT_DIR = Path("scripts/research/ttrades/output")


def load_1m_data():
    """Load 1-minute OHLC data."""
    file_path = DATA_DIR / f"{TICKER}_1m.parquet"
    df = pd.read_parquet(file_path)
    
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
        df = df.set_index('datetime')
    
    return df


def get_price_at_time(np_open, np_close, np_hour, np_minute, np_date, target_date, hour, minute):
    """Get the close price at a specific time."""
    mask = (np_date == target_date) & (np_hour == hour) & (np_minute == minute)
    idxs = np.where(mask)[0]
    
    if len(idxs) == 0:
        return None
    
    return np_close[idxs[0]]


def get_session_direction(np_open, np_close, np_hour, np_minute, np_date, target_date, start_hour, start_min, end_hour, end_min):
    """Get direction of a session (open to close)."""
    # Get session start
    mask_start = (np_date == target_date) & (np_hour == start_hour) & (np_minute == start_min)
    start_idxs = np.where(mask_start)[0]
    
    # Get session end  
    mask_end = (np_date == target_date) & (np_hour == end_hour) & (np_minute == end_min)
    end_idxs = np.where(mask_end)[0]
    
    if len(start_idxs) == 0 or len(end_idxs) == 0:
        return None, 0
    
    session_open = np_open[start_idxs[0]]
    session_close = np_close[end_idxs[0]]
    
    pct_move = (session_close - session_open) / session_open * 100
    
    if session_close > session_open:
        return 'BULLISH', pct_move
    elif session_close < session_open:
        return 'BEARISH', pct_move
    else:
        return 'FLAT', pct_move


def main():
    print("="*70)
    print("ICT TIME LEVELS VALIDATION")
    print("="*70)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
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
        
        # Get midnight open (use 18:00 previous day's futures open, approximate with 00:00)
        # For futures, we'll use 18:00 as session start. Let's use 9:00 of current day as proxy.
        # Better: Use the first bar of the day as "midnight" reference
        mask_day = np_date == target_date
        day_idxs = np.where(mask_day)[0]
        
        if len(day_idxs) < 100:
            continue
        
        # Get midnight open (first bar of the day after midnight)
        mask_midnight = mask_day & (np_hour == 0) & (np_minute == 0)
        midnight_idxs = np.where(mask_midnight)[0]
        
        if len(midnight_idxs) == 0:
            # Try 18:00 previous day
            continue
        
        midnight_open = np_open[midnight_idxs[0]]
        
        # Get 8:30 candle (Judas check)
        mask_830 = (np_date == target_date) & (np_hour == 8) & (np_minute == 30)
        idx_830 = np.where(mask_830)[0]
        
        if len(idx_830) == 0:
            continue
            
        c830_open = np_open[idx_830[0]]
        c830_close = np_close[idx_830[0]]
        price_830 = c830_close # Use close for zone check
        
        # Get 9:30 candle (Judas check)
        mask_930 = (np_date == target_date) & (np_hour == 9) & (np_minute == 30)
        idx_930 = np.where(mask_930)[0]
        
        if len(idx_930) == 0:
            continue
            
        c930_open = np_open[idx_930[0]]
        c930_close = np_close[idx_930[0]]
        price_930 = c930_close # Use close for zone check

        # Get Previous Day High/Low (Liquidity Pools)
        prev_day_mask = (np_date < target_date)
        if prev_day_mask.sum() > 0:
            prev_date = np.max(np_date[prev_day_mask])
            mask_prev = np_date == prev_date
            pdh = np_high[mask_prev].max()
            pdl = np_low[mask_prev].min()
        else:
            pdh = 999999
            pdl = 0
            
        # --- DETERMINE ZONES (BIAS) ---
        above_midnight = price_930 > midnight_open
        above_830 = price_930 > price_830
        above_pdh = price_930 > pdh
        below_pdl = price_930 < pdl
        
        zone = 'MIXED'
        if above_midnight and above_830:
            zone = 'DEEP_PREMIUM' if above_pdh else 'PREMIUM'
        elif not above_midnight and not above_830:
            zone = 'DEEP_DISCOUNT' if below_pdl else 'DISCOUNT'
            
        # --- JUDAS SWING DETECTION ---
        # Did 8:30 candle move UP or DOWN?
        judas_830_dir = 'UP' if c830_close > c830_open else 'DOWN'
        
        # Did 9:30 candle move UP or DOWN?
        judas_930_dir = 'UP' if c930_close > c930_open else 'DOWN'
        
        # --- NY AM SESSION OUTCOME (9:30 - 12:00) ---
        actual_am, pct_am = get_session_direction(
            np_open, np_close, np_hour, np_minute, np_date, target_date, 9, 30, 12, 0
        )
        
        if actual_am is None:
            continue
            
        results.append({
            'date': str(target_date),
            'zone': zone,
            'judas_830': judas_830_dir,
            'judas_930': judas_930_dir,
            'actual_am': actual_am,
            'pct_am': pct_am
        })
    
    df_results = pd.DataFrame(results)
    print(f"\nAnalyzed {len(df_results)} valid trading days")
    
    # ========== VALIDATION 3: Judas Swing + Bias ==========
    print("\n" + "="*70)
    print("VALIDATION 3: JUDAS SWING + BIAS (NY AM 9:30-12:00)")
    print("="*70)
    
    # HYPOTHESIS: 
    # Premium Zone (Bearish Bias) + Judas UP = Strong Short
    # Discount Zone (Bullish Bias) + Judas DOWN = Strong Long
    
    def test_judas(name, zone_filter, judas_col, judas_val, expect_dir):
        subset = df_results[
            (df_results['zone'].str.contains(zone_filter)) & 
            (df_results[judas_col] == judas_val)
        ]
        count = len(subset)
        if count == 0:
            return
            
        accuracy = (subset['actual_am'] == expect_dir).mean() * 100
        avg_ret = subset['pct_am'].mean()
        
        print(f"\n{name}:")
        print(f"  Condition: {zone_filter} + {judas_col} {judas_val} -> Expect {expect_dir}")
        print(f"  Days: {count}")
        print(f"  Accuracy: {accuracy:.1f}%")
        print(f"  Avg Return: {avg_ret:.3f}%")
        
    # Test 8:30 Judas
    print("\n--- 8:30 Judas Tests ---")
    test_judas("Bearish Setup (8:30)", "PREMIUM", "judas_830", "UP", "BEARISH")
    test_judas("Bullish Setup (8:30)", "DISCOUNT", "judas_830", "DOWN", "BULLISH")
    
    # Test 9:30 Judas
    print("\n--- 9:30 Judas Tests ---")
    test_judas("Bearish Setup (9:30)", "PREMIUM", "judas_930", "UP", "BEARISH")
    test_judas("Bullish Setup (9:30)", "DISCOUNT", "judas_930", "DOWN", "BULLISH")

    # ========== SUMMARY ==========
    # Save results
    df_results.to_csv(OUTPUT_DIR / 'judas_validation.csv', index=False)
    print(f"\nResults saved to: {OUTPUT_DIR / 'judas_validation.csv'}")
    
    print("\n" + "="*70)
    print("VALIDATION COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
