import pandas as pd
from session_extractor import TradingDay

def classify_overnight_pattern(day: TradingDay) -> str:
    # Check for missing data
    required = [day.london_high, day.london_low, day.asia_high, day.asia_low]
    if any(x is None or pd.isna(x) for x in required):
        return "UNKNOWN"
        
    london_above_asia_h = day.london_high > day.asia_high
    london_below_asia_l = day.london_low < day.asia_low
    
    if london_above_asia_h and london_below_asia_l:
        return "LONDON_ENGULFS"          # London took both sides
    
    elif not london_above_asia_h and not london_below_asia_l:
        return "ASIA_ENGULFS"            # London stayed inside Asia
    
    elif london_above_asia_h and not london_below_asia_l:
        return "LONDON_PARTIAL_UP"       # London swept Asia high only
    
    elif london_below_asia_l and not london_above_asia_h:
        return "LONDON_PARTIAL_DOWN"     # London swept Asia low only
        
    return "UNKNOWN"

def classify_manipulation(day: TradingDay) -> str:
    pattern = classify_overnight_pattern(day)
    
    if pattern == "LONDON_PARTIAL_UP":
        return "BEARISH_MANIPULATION"    # London swept high -> expect NY to reverse down
    
    elif pattern == "LONDON_PARTIAL_DOWN":
        return "BULLISH_MANIPULATION"    # London swept low -> expect NY to reverse up
    
    elif pattern == "LONDON_ENGULFS":
        # Both sides swept - use which was swept LAST
        # We use the time the high/low was made in London
        if pd.isna(day.london_high_time) or pd.isna(day.london_low_time):
             return "UNKNOWN"
             
        if day.london_high_time > day.london_low_time:
            return "BEARISH_MANIPULATION"  # Last move was up (sweep high last)
        else:
            return "BULLISH_MANIPULATION"  # Last move was down (sweep low last)
    
    elif pattern == "ASIA_ENGULFS":
        return "NO_MANIPULATION"         # London didn't sweep anything
        
    return "NO_MANIPULATION" # Default fallback for unknowns treated as no signal

def classify_ny_position(day: TradingDay) -> str:
    if pd.isna(day.ny_open) or pd.isna(day.london_mid):
        return "UNKNOWN"
        
    if day.ny_open > day.london_mid:
        return "ABOVE_LONDON_MID"
    else:
        return "BELOW_LONDON_MID"

# ═══ NEW: NY PM Manipulation Classification ═══

def classify_pm_pattern(day: TradingDay) -> str:
    """Classify how NY PM manipulated NY AM range."""
    # Ensure attributes exist (safe check) although dataclass has them
    if not hasattr(day, 'ny_pm_high'): return "UNKNOWN"
    
    required = [day.ny_pm_high, day.ny_pm_low, day.ny_am_high, day.ny_am_low]
    if any(x is None or pd.isna(x) for x in required):
        return "UNKNOWN"
    
    pm_above_am_h = day.ny_pm_high > day.ny_am_high
    pm_below_am_l = day.ny_pm_low < day.ny_am_low
    
    if pm_above_am_h and pm_below_am_l:
        return "PM_ENGULFS"
    elif not pm_above_am_h and not pm_below_am_l:
        return "PM_INSIDE"
    elif pm_above_am_h:
        return "PM_PARTIAL_UP"
    elif pm_below_am_l:
        return "PM_PARTIAL_DOWN"
    return "UNKNOWN"

def classify_pm_manipulation(day: TradingDay) -> str:
    """Determine manipulation direction from PM vs AM."""
    pattern = classify_pm_pattern(day)
    
    if pattern == "PM_PARTIAL_UP":
        return "BEARISH_MANIPULATION"
    elif pattern == "PM_PARTIAL_DOWN":
        return "BULLISH_MANIPULATION"
    elif pattern == "PM_ENGULFS":
        if pd.notna(day.ny_pm_high_time) and pd.notna(day.ny_pm_low_time):
            return "BEARISH_MANIPULATION" if day.ny_pm_high_time > day.ny_pm_low_time else "BULLISH_MANIPULATION"
        return "UNKNOWN"
    elif pattern == "PM_INSIDE":
        return "NO_MANIPULATION"
    return "NO_MANIPULATION"

def classify_globex_position(day: TradingDay) -> str:
    """Where globex opens relative to PM mid — for Asia prediction."""
    if pd.isna(day.globex_open) or pd.isna(day.ny_pm_mid):
        return "UNKNOWN"
    return "ABOVE_PM_MID" if day.globex_open > day.ny_pm_mid else "BELOW_PM_MID"

def detect_judas_london(day: TradingDay, manipulation: str) -> bool:
    """Detect Judas sweep sequence for London manipulation."""
    if pd.isna(day.london_high_first):
        return False
    # Judas = London faked opposite direction first
    if manipulation == "BULLISH_MANIPULATION":
        return not day.london_high_first  # Low first → High (faked down, swept low) = Judas
    elif manipulation == "BEARISH_MANIPULATION":
        return day.london_high_first  # High first → Low (faked up, swept high) = Judas
    return False

def detect_judas_pm(day: TradingDay, pm_manipulation: str) -> bool:
    """Detect Judas sweep sequence for PM manipulation."""
    if pd.isna(day.ny_pm_high_first):
        return False
    if pm_manipulation == "BULLISH_MANIPULATION":
        return not day.ny_pm_high_first
    elif pm_manipulation == "BEARISH_MANIPULATION":
        return day.ny_pm_high_first
    return False
