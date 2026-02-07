from dataclasses import dataclass
from datetime import datetime
from typing import List
import pandas as pd
import numpy as np
import pytz
from config import RTH_GAP_THRESHOLD_PCT, SESSION_TIMES, SWING_LOOKBACK
from session_extractor import TradingDay

@dataclass
class PDArray:
    type: str                  # "OB_BULL", "OB_BEAR", "FVG_BULL", "FVG_BEAR", "SWING_H", "SWING_L"
    high: float                # Zone top
    low: float                 # Zone bottom
    midpoint: float            # Entry price (OTE 0.5 level)
    time: datetime             # When detected (bar close time)
    session: str               # "ASIA", "LONDON", "PRE_MARKET"
    in_manipulation_zone: bool # Is this array in the manipulation leg?

def resample_to_15m(day_1m_df: pd.DataFrame) -> pd.DataFrame:
    # Resample 1m to 15m
    # label='left' means 09:30 bucket covers 09:30-09:45
    # closed='left' means includes 09:30, excludes 09:45 from the bucket
    df_15m = day_1m_df.resample('15min', label='left', closed='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    return df_15m.dropna()

def detect_london_pd_arrays(day_1m_df: pd.DataFrame, day_stats: TradingDay, manipulation_type: str) -> List[PDArray]:
    arrays = []
    
    if day_1m_df.empty or pd.isna(day_stats.asia_mid):
        return arrays
        
    df_15m = resample_to_15m(day_1m_df)
    
    # Convert to python objects for speed
    closes = df_15m['close'].values
    opens = df_15m['open'].values
    highs = df_15m['high'].values
    lows = df_15m['low'].values
    times = df_15m.index  # DatetimeIndex
    
    # Identify indices belonging to London
    # London: 02:30 to 08:00
    # Since index is "start of bar", 02:30 bar is the first one. 07:45 bar is the last one (ends at 08:00).
    # 08:00 bar starts Pre-Market.
    
    # We iterate `i` for the whole day, but only add arrays if `times[i]` is in London.
    # However, detection "event" happens at `i`.
    # e.g., FVG detected at closure of bar `i`. OB at closure of bar `i`.
    # Pivot High detected at closure of bar `i` (which is 5 bars after the peak).
    # So if `times[i]` is in London, we accept it.
    
    london_start = SESSION_TIMES['LONDON'][0]
    london_end = SESSION_TIMES['LONDON'][1]
    
    # Helper to check if time is in London
    def is_in_london(t):
        current_time = t.time()
        # London doesn't cross midnight in our setup (02:30-08:00)
        return london_start <= current_time < london_end

    n = len(df_15m)
    
    for i in range(n):
        current_time_idx = times[i]
        
        # We need historical bars for patterns.
        if i < 3: continue 
        
        # Only record if DETECTION happens during London
        # (Though technically an OB formed in Asia might be valid, prompt implies "detect PD arrays ... during London")
        if not is_in_london(current_time_idx):
            continue
            
        current_close = closes[i]
        current_open = opens[i]
        current_high = highs[i]
        current_low = lows[i]
        prev_close = closes[i-1]
        
        # --- BULLISH FVG ---
        # Gap between i-2 High and i Low
        if i >= 2:
            gap_low = highs[i-2]
            gap_high = lows[i] # Current bar low
            if gap_high > gap_low:
                # Check size
                range_check = prev_close * (RTH_GAP_THRESHOLD_PCT / 100.0)
                if (gap_high - gap_low) >= range_check:
                    # Valid Bullish FVG
                    array = PDArray(
                        type="FVG_BULL",
                        high=gap_high,
                        low=gap_low,
                        midpoint=(gap_high + gap_low) / 2.0,
                        time=current_time_idx,
                        session="LONDON",
                        in_manipulation_zone=False # To be checked
                    )
                    
                    # Manipulation Zone Logic
                    # If Bullish Manipulation (London swept low)
                    # Array matches bias (FVG_BULL) AND is BELOW Asia Mid
                    if manipulation_type == "BULLISH_MANIPULATION" and array.high < day_stats.asia_mid:
                         array.in_manipulation_zone = True
                    elif manipulation_type == "BEARISH_MANIPULATION":
                         # Conflicting signal
                         array.in_manipulation_zone = False
                         
                    arrays.append(array)

        # --- BEARISH FVG ---
        # Gap between i-2 Low and i High
        if i >= 2:
            gap_high = lows[i-2]
            gap_low = highs[i] # Current bar high
            if gap_low < gap_high:
                range_check = prev_close * (RTH_GAP_THRESHOLD_PCT / 100.0)
                if (gap_high - gap_low) >= range_check:
                    array = PDArray(
                        type="FVG_BEAR",
                        high=gap_high,
                        low=gap_low,
                        midpoint=(gap_high + gap_low) / 2.0,
                        time=current_time_idx,
                        session="LONDON",
                        in_manipulation_zone=False
                    )
                    
                    if manipulation_type == "BEARISH_MANIPULATION" and array.low > day_stats.asia_mid:
                         array.in_manipulation_zone = True
                    
                    arrays.append(array)
        
        # --- BULLISH OB ---
        # Bar[i-3] Bearish, Bar[i] closes > Bar[i-3].high
        if i >= 3:
            bar3_close = closes[i-3]
            bar3_open = opens[i-3]
            bar3_high = highs[i-3]
            bar3_low = lows[i-3]
            
            is_bar3_bearish = bar3_close < bar3_open
            
            if is_bar3_bearish and current_close > bar3_high:
                # Displaced above
                array = PDArray(
                    type="OB_BULL",
                    high=bar3_high,
                    low=bar3_low,
                    midpoint=(bar3_open + bar3_close) / 2.0,
                    time=current_time_idx,
                    session="LONDON",
                    in_manipulation_zone=False
                )
                if manipulation_type == "BULLISH_MANIPULATION" and array.high < day_stats.asia_mid:
                     array.in_manipulation_zone = True
                arrays.append(array)

        # --- BEARISH OB ---
        # Bar[i-3] Bullish, Bar[i] closes < Bar[i-3].low
        if i >= 3:
            bar3_close = closes[i-3]
            bar3_open = opens[i-3]
            bar3_high = highs[i-3]
            bar3_low = lows[i-3]
            is_bar3_bullish = bar3_close > bar3_open
            
            if is_bar3_bullish and current_close < bar3_low:
                array = PDArray(
                    type="OB_BEAR",
                    high=bar3_high,
                    low=bar3_low,
                    midpoint=(bar3_open + bar3_close) / 2.0,
                    time=current_time_idx,
                    session="LONDON",
                    in_manipulation_zone=False
                )
                if manipulation_type == "BEARISH_MANIPULATION" and array.low > day_stats.asia_mid:
                     array.in_manipulation_zone = True
                arrays.append(array)
                
        # --- SWING HIGH/LOW ---
        # Using lookback 5. Need i-5, i-4... i... i+5?
        # A pivot detected AT 'i' means 'i-5' was the peak?
        # No, "Pivot high with lookback=5" usually means checking checking `i-5` is higher than neighbours.
        # But we align detection time to when it is confirmed.
        # If we need 5 bars to the right, we can only confirm it at `j = peak + 5`.
        # So at index `i`, we check if `i-5` was a pivot given neighbors `i-10` to `i`.
        
        L = SWING_LOOKBACK # 5
        if i >= 2 * L:
            pivot_idx = i - L
            pivot_high_cand = highs[pivot_idx]
            pivot_low_cand = lows[pivot_idx]
            
            # Check Max neighbors
            # range: [pivot_idx - L, pivot_idx + L]
            # indices: i - 2L to i
            window_highs = highs[i-2*L : i+1] 
            window_lows = lows[i-2*L : i+1]
            
            # Check High
            if pivot_high_cand == np.max(window_highs):
                # Ensure strictly highest if we want strictly unique peak, or just >=
                # Typically >= is fine, but checking strictly > neighbors is safer to avoid flat tops
                # Using max is fine.
                
                # Zone: price +- 0.2%
                zone_half = pivot_high_cand * 0.002
                array = PDArray(
                    type="SWING_H",
                    high=pivot_high_cand + zone_half,
                    low=pivot_high_cand - zone_half,
                    midpoint=pivot_high_cand,
                    time=current_time_idx, # Confirmed now
                    session="LONDON",
                    in_manipulation_zone=False
                )
                if manipulation_type == "BEARISH_MANIPULATION" and array.low > day_stats.asia_mid:
                         array.in_manipulation_zone = True
                arrays.append(array)
            
            # Check Low
            if pivot_low_cand == np.min(window_lows):
                zone_half = pivot_low_cand * 0.002
                array = PDArray(
                    type="SWING_L",
                    high=pivot_low_cand + zone_half,
                    low=pivot_low_cand - zone_half,
                    midpoint=pivot_low_cand,
                    time=current_time_idx,
                    session="LONDON",
                    in_manipulation_zone=False
                )
                if manipulation_type == "BULLISH_MANIPULATION" and array.high < day_stats.asia_mid:
                         array.in_manipulation_zone = True
                arrays.append(array)
                
    return arrays
