from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from session_extractor import TradingDay, get_ohlc_in_range
from pda_detector import PDArray, resample_to_15m
from config import SESSION_TIMES

@dataclass
class NYOutcome:
    hit_london_high: bool = False
    hit_london_low: bool = False
    hit_asia_high: bool = False
    hit_asia_low: bool = False
    hit_midnight_open: bool = False
    hit_7_8_mid: bool = False
    hit_2_3_mid: bool = False
    hit_prev_day_high: bool = False
    hit_prev_day_low: bool = False
    
    hit_london_high_first: bool = None
    hit_london_high_time: datetime = None
    hit_london_low_time: datetime = None
    hit_asia_high_time: datetime = None
    hit_asia_low_time: datetime = None
    hit_midnight_open_time: datetime = None
    hit_7_8_mid_time: datetime = None
    hit_2_3_mid_time: datetime = None
    hit_prev_day_high_time: datetime = None
    hit_prev_day_low_time: datetime = None
    
    gap_fill_25: bool = False
    gap_fill_50: bool = False
    gap_fill_100: bool = False
    gap_fill_25_time: datetime = None
    
    manipulation_reversed: bool = False
    reversal_time: datetime = None
    
    arrays_touched: List[str] = field(default_factory=list)
    arrays_respected: List[str] = field(default_factory=list)
    arrays_failed: List[str] = field(default_factory=list)
    
    # ═══ NEW: Additional level hits during NY ═══
    hit_overnight_high: bool = False
    hit_overnight_high_time: datetime = None
    hit_overnight_low: bool = False
    hit_overnight_low_time: datetime = None
    hit_overnight_mid: bool = False
    hit_p12_high: bool = False
    hit_p12_high_time: datetime = None
    hit_p12_low: bool = False
    hit_p12_low_time: datetime = None
    hit_p12_mid: bool = False
    hit_ote_bull_62: bool = False
    hit_ote_bear_62: bool = False
    hit_prev_day_mid: bool = False
    hit_prev_day_close: bool = False
    hit_prev_day_close_time: datetime = None
    hit_prev_week_high: bool = False
    hit_prev_week_high_time: datetime = None
    hit_prev_week_low: bool = False
    hit_prev_week_low_time: datetime = None
    hit_prev_week_close: bool = False
    hit_prev_week_close_time: datetime = None
    hit_weekly_open: bool = False
    hit_weekly_open_time: datetime = None
    hit_globex_open: bool = False
    hit_globex_open_time: datetime = None
    hit_open_0730: bool = False
    hit_open_0730_time: datetime = None
    hit_london_mid: bool = False
    hit_london_mid_time: datetime = None
    hit_asia_mid: bool = False
    hit_asia_mid_time: datetime = None
    
    # NEW: Hit-first pairs during NY
    # LO_H vs LO_L already exists (hit_london_high_first)
    on_high_first: bool = None          # Overnight H vs L
    p12_high_first: bool = None
    pd_high_first: bool = None          # PDH vs PDL
    london_high_vs_pdh_first: str = None  # "LO_H" or "PDH" or "NEITHER"
    london_low_vs_pdl_first: str = None
    
    # NEW: Hit-first during NY AM only
    am_london_high_first: bool = None   # During 09:30-12:00
    
    # NEW: Hit-first during NY PM only
    pm_am_high_first: bool = None       # AM_H vs AM_L during PM
    
    # NEW: CBDR sigma hits during NY
    cbdr_hit_up_0_5: bool = False
    cbdr_hit_up_1: bool = False
    cbdr_hit_up_1_5: bool = False
    cbdr_hit_up_2: bool = False
    cbdr_hit_up_2_5: bool = False
    cbdr_hit_up_3: bool = False
    cbdr_hit_up_4: bool = False
    cbdr_hit_dn_0_5: bool = False
    cbdr_hit_dn_1: bool = False
    cbdr_hit_dn_1_5: bool = False
    cbdr_hit_dn_2: bool = False
    cbdr_hit_dn_2_5: bool = False
    cbdr_hit_dn_3: bool = False
    cbdr_hit_dn_4: bool = False
    cbdr_upside_sigmas: float = np.nan
    cbdr_downside_sigmas: float = np.nan

@dataclass
class AsiaOutcome:
    """Outcomes measured during Asia session of the NEXT day."""
    hit_pm_high: bool = False
    hit_pm_high_time: datetime = None
    hit_pm_low: bool = False
    hit_pm_low_time: datetime = None
    hit_am_high: bool = False
    hit_am_high_time: datetime = None
    hit_am_low: bool = False
    hit_am_low_time: datetime = None
    hit_lunch_high: bool = False
    hit_lunch_high_time: datetime = None
    hit_lunch_low: bool = False
    hit_lunch_low_time: datetime = None
    hit_pdh: bool = False
    hit_pdh_time: datetime = None
    hit_pdl: bool = False
    hit_pdl_time: datetime = None
    hit_pdc: bool = False
    hit_pdc_time: datetime = None
    
    pm_high_first: bool = None      # PM_H vs PM_L during Asia
    am_high_first: bool = None      # AM_H vs AM_L during Asia
    pd_high_first: bool = None      # PDH vs PDL during Asia
    
    pm_manip_reversed: bool = False
    pm_reversal_time: datetime = None

@dataclass
class LunchOutcome:
    """Outcomes measured during NY Lunch session (12:00 - 13:30)."""
    hit_am_high: bool = False
    hit_am_high_time: datetime = None
    hit_am_low: bool = False
    hit_am_low_time: datetime = None
    hit_london_high: bool = False
    hit_london_high_time: datetime = None
    hit_london_low: bool = False
    hit_london_low_time: datetime = None
    hit_on_high: bool = False
    hit_on_high_time: datetime = None
    hit_on_low: bool = False
    hit_on_low_time: datetime = None
    hit_asia_high: bool = False
    hit_asia_high_time: datetime = None
    hit_asia_low: bool = False
    hit_asia_low_time: datetime = None
    
    am_high_first: bool = None      # AM_H vs AM_L during Lunch

@dataclass  
class PMOutcome:
    """Outcomes measured during NY PM session."""
    hit_am_high: bool = False
    hit_am_high_time: datetime = None
    hit_am_low: bool = False
    hit_am_low_time: datetime = None
    hit_london_high: bool = False
    hit_london_high_time: datetime = None
    hit_london_low: bool = False
    hit_london_low_time: datetime = None
    hit_on_high: bool = False
    hit_on_high_time: datetime = None
    hit_on_low: bool = False
    hit_on_low_time: datetime = None
    hit_lunch_high: bool = False
    hit_lunch_high_time: datetime = None
    hit_lunch_low: bool = False
    hit_lunch_low_time: datetime = None
    
    am_high_first: bool = None      # AM_H vs AM_L during PM

def measure_outcomes(day_1m_df: pd.DataFrame, day_stats: TradingDay, pd_arrays: List[PDArray], manipulation_type: str) -> NYOutcome:
    outcome = NYOutcome()
    
    # Filter 1m data to NY Session (09:30 - 16:00)
    # Using between_time on index
    if day_1m_df.empty:
        return outcome
        
    ny_df = day_1m_df.between_time(SESSION_TIMES['NY_AM'][0], SESSION_TIMES['NY_PM'][1])
    
    if ny_df.empty:
        return outcome
        
    # --- Level Hits ---
    highs = ny_df['high']
    lows = ny_df['low']
    
    def check_hit(level):
        if level is None or pd.isna(level): return False, None
        hits = (highs >= level) & (lows <= level)
        if hits.any():
            return True, hits.idxmax()
        return False, None
        
    outcome.hit_london_high, t_lh = check_hit(day_stats.london_high)
    outcome.hit_london_low, t_ll = check_hit(day_stats.london_low)
    outcome.hit_london_high_time = t_lh
    outcome.hit_london_low_time = t_ll
    
    if outcome.hit_london_high and outcome.hit_london_low:
        outcome.hit_london_high_first = t_lh < t_ll
    elif outcome.hit_london_high:
        outcome.hit_london_high_first = True
    elif outcome.hit_london_low:
        outcome.hit_london_high_first = False
        
    outcome.hit_asia_high, outcome.hit_asia_high_time = check_hit(day_stats.asia_high)
    outcome.hit_asia_low, outcome.hit_asia_low_time = check_hit(day_stats.asia_low)
    outcome.hit_midnight_open, outcome.hit_midnight_open_time = check_hit(day_stats.midnight_open)
    outcome.hit_7_8_mid, outcome.hit_7_8_mid_time = check_hit(day_stats.hour_7_8_mid)
    outcome.hit_2_3_mid, outcome.hit_2_3_mid_time = check_hit(day_stats.hour_2_3_mid)
    outcome.hit_prev_day_high, outcome.hit_prev_day_high_time = check_hit(day_stats.prev_day_high)
    outcome.hit_prev_day_low, outcome.hit_prev_day_low_time = check_hit(day_stats.prev_day_low)

    # --- Gap Fills ---
    if pd.notna(day_stats.rth_gap) and day_stats.rth_gap != 0 and pd.notna(day_stats.prev_settle):
        gap_dir = 1 if day_stats.rth_gap > 0 else -1
        fill_target_25 = day_stats.ny_open - (day_stats.rth_gap * 0.25)
        fill_target_50 = day_stats.ny_open - (day_stats.rth_gap * 0.50)
        fill_target_100 = day_stats.prev_settle
        
        if gap_dir > 0: # Gap Up
            outcome.gap_fill_25 = (lows.min() <= fill_target_25)
            outcome.gap_fill_50 = (lows.min() <= fill_target_50)
            outcome.gap_fill_100 = (lows.min() <= fill_target_100)
            if outcome.gap_fill_25:
                 hits = lows[lows <= fill_target_25]
                 if not hits.empty:
                    outcome.gap_fill_25_time = hits.index[0]
        else: # Gap Down
            outcome.gap_fill_25 = (highs.max() >= fill_target_25)
            outcome.gap_fill_50 = (highs.max() >= fill_target_50)
            outcome.gap_fill_100 = (highs.max() >= fill_target_100)
            if outcome.gap_fill_25:
                 hits = highs[highs >= fill_target_25]
                 if not hits.empty:
                    outcome.gap_fill_25_time = hits.index[0]

    # --- Manipulation Reversal ---
    if manipulation_type == "BEARISH_MANIPULATION":
        if outcome.hit_london_low:
             hits = lows[lows < day_stats.london_low]
             if not hits.empty:
                 outcome.manipulation_reversed = True
                 outcome.reversal_time = hits.index[0]
                 
    elif manipulation_type == "BULLISH_MANIPULATION":
         if outcome.hit_london_high:
             hits = highs[highs > day_stats.london_high]
             if not hits.empty:
                 outcome.manipulation_reversed = True
                 outcome.reversal_time = hits.index[0]
                 
    # --- PD Arrays ---
    if pd_arrays:
        # Resample NY to 15m for array logic verification
        ny_15m = resample_to_15m(day_1m_df).between_time(SESSION_TIMES['NY_AM'][0], SESSION_TIMES['NY_PM'][1])
        
        if not ny_15m.empty:
            for array in pd_arrays:
                touched = False
                touch_start_idx = -1
                
                # Check touch on 15m bars
                for i in range(len(ny_15m)):
                    b_high = ny_15m['high'].iloc[i]
                    b_low = ny_15m['low'].iloc[i]
                    
                    is_bull = "BULL" in array.type or "SWING_L" in array.type
                    is_bear = "BEAR" in array.type or "SWING_H" in array.type
                    
                    is_touch = False
                    if is_bull:
                        if b_low <= array.high and b_high >= array.low:
                            is_touch = True
                    elif is_bear:
                        if b_high >= array.low and b_low <= array.high:
                            is_touch = True
                            
                    if is_touch:
                        touched = True
                        touch_start_idx = i
                        outcome.arrays_touched.append(f"{array.type}_{array.time}")
                        break
                        
                if touched:
                    # Check outcome (Respected vs Failed)
                    # Look ahead from touch_start_idx
                    zone_size = array.high - array.low
                    target_move = max(zone_size * 0.5, array.high * 0.0005) # Minimum move fallback
                    
                    state = "PENDING"
                    is_bull = "BULL" in array.type or "SWING_L" in array.type
                    
                    for j in range(touch_start_idx, len(ny_15m)):
                        close = ny_15m['close'].iloc[j]
                        b_high = ny_15m['high'].iloc[j]
                        b_low = ny_15m['low'].iloc[j]
                        
                        if is_bull:
                            # Fail: Close below low
                            if close < array.low:
                                state = "FAILED"
                                break
                            # Respect: Move up by target
                            if b_high >= (array.high + target_move):
                                state = "RESPECTED"
                                break
                        else:
                            # Fail: Close above high
                            if close > array.high:
                                state = "FAILED"
                                break
                            # Respect: Move down
                            if b_low <= (array.low - target_move):
                                state = "RESPECTED"
                                break
                                
                    if state == "RESPECTED":
                        outcome.arrays_respected.append(f"{array.type}_{array.time}")
                    elif state == "FAILED":
                        outcome.arrays_failed.append(f"{array.type}_{array.time}")
                        
    return outcome

def measure_ny_enhanced(day_1m_df: pd.DataFrame, day_stats: TradingDay, outcome: NYOutcome):
    """Add enhanced measurements to existing NYOutcome (in-place modification)."""
    if day_1m_df.empty: return

    # Filter 1m data to NY Session (09:30 - 16:00)
    ny_df = day_1m_df.between_time(SESSION_TIMES['NY_AM'][0], SESSION_TIMES['NY_PM'][1])
    if ny_df.empty: return

    highs = ny_df['high']
    lows = ny_df['low']

    def check_hit(level):
        if level is None or pd.isna(level): return False, None
        hits = (highs >= level) & (lows <= level)
        if hits.any():
            return True, hits.idxmax()
        return False, None

    # --- New Level Hits ---
    outcome.hit_overnight_high, outcome.hit_overnight_high_time = check_hit(day_stats.overnight_high)
    outcome.hit_overnight_low, outcome.hit_overnight_low_time = check_hit(day_stats.overnight_low)
    outcome.hit_overnight_mid, _ = check_hit(day_stats.overnight_mid)
    
    outcome.hit_p12_high, outcome.hit_p12_high_time = check_hit(day_stats.p12_high)
    outcome.hit_p12_low, outcome.hit_p12_low_time = check_hit(day_stats.p12_low)
    outcome.hit_p12_mid, _ = check_hit(day_stats.p12_mid)
    
    outcome.hit_ote_bull_62, _ = check_hit(day_stats.ote_bull_62)
    outcome.hit_ote_bear_62, _ = check_hit(day_stats.ote_bear_62)
    
    outcome.hit_prev_day_mid, _ = check_hit(day_stats.prev_day_mid)
    outcome.hit_prev_day_close, outcome.hit_prev_day_close_time = check_hit(day_stats.prev_settle)
    outcome.hit_prev_week_high, outcome.hit_prev_week_high_time = check_hit(day_stats.prev_week_high)
    outcome.hit_prev_week_low, outcome.hit_prev_week_low_time = check_hit(day_stats.prev_week_low)
    outcome.hit_weekly_open, outcome.hit_weekly_open_time = check_hit(day_stats.weekly_open)
    outcome.hit_prev_week_close, outcome.hit_prev_week_close_time = check_hit(day_stats.prev_week_close)
    outcome.hit_globex_open, outcome.hit_globex_open_time = check_hit(day_stats.globex_open)
    outcome.hit_open_0730, outcome.hit_open_0730_time = check_hit(day_stats.open_0730)
    outcome.hit_london_mid, outcome.hit_london_mid_time = check_hit(day_stats.london_mid)
    outcome.hit_asia_mid, outcome.hit_asia_mid_time = check_hit(day_stats.asia_mid)

    # --- Hit First Logic ---
    # Overnight High/Low
    if outcome.hit_overnight_high and outcome.hit_overnight_low:
        outcome.on_high_first = outcome.hit_overnight_high_time < outcome.hit_overnight_low_time
    elif outcome.hit_overnight_high:
        outcome.on_high_first = True
    elif outcome.hit_overnight_low:
        outcome.on_high_first = False
        
    # P12 High/Low
    if outcome.hit_p12_high and outcome.hit_p12_low:
        outcome.p12_high_first = outcome.hit_p12_high_time < outcome.hit_p12_low_time
    elif outcome.hit_p12_high:
        outcome.p12_high_first = True
    elif outcome.hit_p12_low:
        outcome.p12_high_first = False

    # PDH vs PDL
    t_pdh = outcome.hit_prev_day_high_time
    t_pdl = outcome.hit_prev_day_low_time

    if outcome.hit_prev_day_high and outcome.hit_prev_day_low:
        outcome.pd_high_first = t_pdh < t_pdl
    elif outcome.hit_prev_day_high:
        outcome.pd_high_first = True
    elif outcome.hit_prev_day_low:
        outcome.pd_high_first = False

    # London High vs PDH
    # Need time for London High hit (already in outcome)
    t_lh = outcome.hit_london_high_time
    if outcome.hit_london_high and outcome.hit_prev_day_high:
        outcome.london_high_vs_pdh_first = "LO_H" if t_lh < t_pdh else "PDH"
    elif outcome.hit_london_high:
        outcome.london_high_vs_pdh_first = "LO_H"
    elif outcome.hit_prev_day_high:
        outcome.london_high_vs_pdh_first = "PDH"
    else:
        outcome.london_high_vs_pdh_first = "NEITHER"

    # London Low vs PDL
    t_ll = outcome.hit_london_low_time
    if outcome.hit_london_low and outcome.hit_prev_day_low:
        outcome.london_low_vs_pdl_first = "LO_L" if t_ll < t_pdl else "PDL"
    elif outcome.hit_london_low:
        outcome.london_low_vs_pdl_first = "LO_L"
    elif outcome.hit_prev_day_low:
        outcome.london_low_vs_pdl_first = "PDL"
    else:
        outcome.london_low_vs_pdl_first = "NEITHER"

    # --- CBDR Sigma Reach (London + NY) ---
    # User Spec: "Compute how far price went during London + NY"
    # Range: 02:30 - 16:00
    rth_plus_london = day_1m_df.between_time(SESSION_TIMES['LONDON'][0], SESSION_TIMES['NY_PM'][1])
    
    if not rth_plus_london.empty and pd.notna(day_stats.cbdr_asia_high) and pd.notna(day_stats.cbdr_asia_low):
        r = day_stats.cbdr_asia_range
        if r > 0:
            max_h = rth_plus_london['high'].max()
            min_l = rth_plus_london['low'].min()
            
            outcome.cbdr_upside_sigmas = (max_h - day_stats.cbdr_asia_high) / r
            outcome.cbdr_downside_sigmas = (day_stats.cbdr_asia_low - min_l) / r
            
            # Check specific sigma hits directly from the ratio
            outcome.cbdr_hit_up_0_5 = outcome.cbdr_upside_sigmas >= 0.5
            outcome.cbdr_hit_up_1 = outcome.cbdr_upside_sigmas >= 1.0
            outcome.cbdr_hit_up_1_5 = outcome.cbdr_upside_sigmas >= 1.5
            outcome.cbdr_hit_up_2 = outcome.cbdr_upside_sigmas >= 2.0
            outcome.cbdr_hit_up_2_5 = outcome.cbdr_upside_sigmas >= 2.5
            outcome.cbdr_hit_up_3 = outcome.cbdr_upside_sigmas >= 3.0
            outcome.cbdr_hit_up_4 = outcome.cbdr_upside_sigmas >= 4.0

            outcome.cbdr_hit_dn_0_5 = outcome.cbdr_downside_sigmas >= 0.5
            outcome.cbdr_hit_dn_1 = outcome.cbdr_downside_sigmas >= 1.0
            outcome.cbdr_hit_dn_1_5 = outcome.cbdr_downside_sigmas >= 1.5
            outcome.cbdr_hit_dn_2 = outcome.cbdr_downside_sigmas >= 2.0
            outcome.cbdr_hit_dn_2_5 = outcome.cbdr_downside_sigmas >= 2.5
            outcome.cbdr_hit_dn_3 = outcome.cbdr_downside_sigmas >= 3.0
            outcome.cbdr_hit_dn_4 = outcome.cbdr_downside_sigmas >= 4.0


def measure_pm_outcomes(day_1m_df: pd.DataFrame, day_stats: TradingDay) -> PMOutcome:
    """Measure outcomes during NY PM session (13:30 - 16:00)."""
    outcome = PMOutcome()
    
    if day_1m_df.empty: return outcome
    
    # Filter to PM Session
    pm_df = day_1m_df.between_time(SESSION_TIMES['NY_PM_ICT'][0], SESSION_TIMES['NY_PM_ICT'][1])
    if pm_df.empty: return outcome
    
    highs = pm_df['high']
    lows = pm_df['low']
    
    def check_hit(level):
        if level is None or pd.isna(level): return False, None
        hits = (highs >= level) & (lows <= level)
        if hits.any():
            return True, hits.idxmax()
        return False, None
        
    outcome.hit_am_high, outcome.hit_am_high_time = check_hit(day_stats.ny_am_high)
    outcome.hit_am_low, outcome.hit_am_low_time = check_hit(day_stats.ny_am_low)
    outcome.hit_london_high, outcome.hit_london_high_time = check_hit(day_stats.london_high)
    outcome.hit_london_low, outcome.hit_london_low_time = check_hit(day_stats.london_low)
    outcome.hit_on_high, outcome.hit_on_high_time = check_hit(day_stats.overnight_high)
    outcome.hit_on_low, outcome.hit_on_low_time = check_hit(day_stats.overnight_low)
    outcome.hit_lunch_high, outcome.hit_lunch_high_time = check_hit(day_stats.lunch_high)
    outcome.hit_lunch_low, outcome.hit_lunch_low_time = check_hit(day_stats.lunch_low)
    
    if outcome.hit_am_high and outcome.hit_am_low:
        outcome.am_high_first = outcome.hit_am_high_time < outcome.hit_am_low_time
    elif outcome.hit_am_high:
        outcome.am_high_first = True
    elif outcome.hit_am_low:
        outcome.am_high_first = False
        
    return outcome

def measure_lunch_outcomes(day_1m_df: pd.DataFrame, day_stats: TradingDay) -> LunchOutcome:
    """Measure outcomes during NY Lunch session (12:00 - 13:30)."""
    outcome = LunchOutcome()
    
    if day_1m_df.empty: return outcome
    
    # Filter to Lunch Session
    lunch_df = day_1m_df.between_time(SESSION_TIMES['LUNCH'][0], SESSION_TIMES['LUNCH'][1])
    if lunch_df.empty: return outcome
    
    highs = lunch_df['high']
    lows = lunch_df['low']
    
    def check_hit(level):
        if level is None or pd.isna(level): return False, None
        hits = (highs >= level) & (lows <= level)
        if hits.any():
            return True, hits.idxmax()
        return False, None
        
    outcome.hit_am_high, outcome.hit_am_high_time = check_hit(day_stats.ny_am_high)
    outcome.hit_am_low, outcome.hit_am_low_time = check_hit(day_stats.ny_am_low)
    outcome.hit_london_high, outcome.hit_london_high_time = check_hit(day_stats.london_high)
    outcome.hit_london_low, outcome.hit_london_low_time = check_hit(day_stats.london_low)
    outcome.hit_on_high, outcome.hit_on_high_time = check_hit(day_stats.overnight_high)
    outcome.hit_on_low, outcome.hit_on_low_time = check_hit(day_stats.overnight_low)
    outcome.hit_asia_high, outcome.hit_asia_high_time = check_hit(day_stats.asia_high)
    outcome.hit_asia_low, outcome.hit_asia_low_time = check_hit(day_stats.asia_low)
    
    if outcome.hit_am_high and outcome.hit_am_low:
        outcome.am_high_first = outcome.hit_am_high_time < outcome.hit_am_low_time
    elif outcome.hit_am_high:
        outcome.am_high_first = True
    elif outcome.hit_am_low:
        outcome.am_high_first = False
        
    return outcome

def measure_asia_outcomes(next_day_1m_df: pd.DataFrame, current_day_stats: TradingDay) -> AsiaOutcome:
    """Measure outcomes during Asia session of the NEXT day."""
    outcome = AsiaOutcome()
    
    if next_day_1m_df.empty: return outcome
    
    # Asia 19:30 - 02:30
    # Use get_ohlc_in_range to handle midnight crossing correctly
    asia_df = get_ohlc_in_range(next_day_1m_df, SESSION_TIMES['ASIA'][0], SESSION_TIMES['ASIA'][1])
    if asia_df.empty: return outcome
    
    highs = asia_df['high']
    lows = asia_df['low']
    
    def check_hit(level):
        if level is None or pd.isna(level): return False, None
        hits = (highs >= level) & (lows <= level)
        if hits.any():
            return True, hits.idxmax()
        return False, None
        
    # Check hits of Current Day's levels
    outcome.hit_pm_high, outcome.hit_pm_high_time = check_hit(current_day_stats.ny_pm_high)
    outcome.hit_pm_low, outcome.hit_pm_low_time = check_hit(current_day_stats.ny_pm_low)
    outcome.hit_am_high, outcome.hit_am_high_time = check_hit(current_day_stats.ny_am_high)
    outcome.hit_am_low, outcome.hit_am_low_time = check_hit(current_day_stats.ny_am_low)
    outcome.hit_lunch_high, outcome.hit_lunch_high_time = check_hit(current_day_stats.lunch_high)
    outcome.hit_lunch_low, outcome.hit_lunch_low_time = check_hit(current_day_stats.lunch_low)
    
    # PDH/PDL for the Asia session (which is Next Day's Asia) refer to the Current Day's High/Low
    outcome.hit_pdh, outcome.hit_pdh_time = check_hit(current_day_stats.ny_high)
    outcome.hit_pdl, outcome.hit_pdl_time = check_hit(current_day_stats.ny_low)
    outcome.hit_pdc, outcome.hit_pdc_time = check_hit(current_day_stats.ny_close)
    
    # Hit First logic
    if outcome.hit_pm_high and outcome.hit_pm_low:
        outcome.pm_high_first = outcome.hit_pm_high_time < outcome.hit_pm_low_time
    elif outcome.hit_pm_high:
        outcome.pm_high_first = True
    elif outcome.hit_pm_low:
        outcome.pm_high_first = False
        
    if outcome.hit_am_high and outcome.hit_am_low:
        outcome.am_high_first = outcome.hit_am_high_time < outcome.hit_am_low_time
    elif outcome.hit_am_high:
        outcome.am_high_first = True
    elif outcome.hit_am_low:
        outcome.am_high_first = False
        
    if outcome.hit_pdh and outcome.hit_pdl:
        outcome.pd_high_first = outcome.hit_pdh_time < outcome.hit_pdl_time
    elif outcome.hit_pdh:
        outcome.pd_high_first = True
    elif outcome.hit_pdl:
        outcome.pd_high_first = False
        
    # Manipulation Reversal logic specific to PM
    if current_day_stats.pm_manipulation == "BEARISH_MANIPULATION": # PM went up (fake), expected down
         # Did Asia go below PM Low?
         if outcome.hit_pm_low:
             hits = lows[lows < current_day_stats.ny_pm_low]
             if not hits.empty:
                 outcome.pm_manip_reversed = True
                 outcome.pm_reversal_time = hits.index[0]
                 
    elif current_day_stats.pm_manipulation == "BULLISH_MANIPULATION": # PM went down (fake), expected up
         # Did Asia go above PM High?
         if outcome.hit_pm_high:
             hits = highs[highs > current_day_stats.ny_pm_high]
             if not hits.empty:
                 outcome.pm_manip_reversed = True
                 outcome.pm_reversal_time = hits.index[0]
                 
    return outcome
