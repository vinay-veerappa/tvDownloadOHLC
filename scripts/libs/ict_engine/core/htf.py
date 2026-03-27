import pandas as pd
import numpy as np
from .validation import validate_ohlc

@validate_ohlc(input_type="ohlc")
def detect_htf_levels(ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    HTF Level Detection (PDH/PDL, PWH/PWL, PMH/PML).
    Finds Previous Day, Week, and Month Highs and Lows.
    """
    # 1. Previous Day High / Low / Mid
    # Resample to Daily
    daily = ohlc.resample("D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    daily_shift = daily.shift(1)
    
    pdh = daily_shift["high"].reindex(ohlc.index, method="ffill")
    pdl = daily_shift["low"].reindex(ohlc.index, method="ffill")
    pdm = (pdh + pdl) / 2
    
    # 2. Previous Week High / Low / Mid
    weekly = ohlc.resample("W").agg({"high": "max", "low": "min"}).dropna()
    weekly_shift = weekly.shift(1)
    
    pwh = weekly_shift["high"].reindex(ohlc.index, method="ffill")
    pwl = weekly_shift["low"].reindex(ohlc.index, method="ffill")
    pwm = (pwh + pwl) / 2
    
    # 3. Previous Month High / Low / Mid
    monthly = ohlc.resample("ME").agg({"high": "max", "low": "min"}).dropna()
    monthly_shift = monthly.shift(1)
    
    pmh = monthly_shift["high"].reindex(ohlc.index, method="ffill")
    pml = monthly_shift["low"].reindex(ohlc.index, method="ffill")
    pmm = (pmh + pml) / 2
    
    return pd.DataFrame({
        "pdh": pdh,
        "pdl": pdl,
        "pdm": pdm,
        "pwh": pwh,
        "pwl": pwl,
        "pwm": pwm,
        "pmh": pmh,
        "pml": pml,
        "pmm": pmm
    }, index=ohlc.index)
