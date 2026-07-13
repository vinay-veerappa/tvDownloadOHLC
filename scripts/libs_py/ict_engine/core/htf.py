import pandas as pd
import numpy as np
from .validation import validate_ohlc

# ── IPDA Data Ranges (20/40/60) ────────────────────────────────────
# Rolling lookback windows defining the Interbank Price Delivery
# Algorithm's operating range. Each shifts daily and excludes the
# current bar so that the algorithm's targets are strictly historical.
IPDA_RANGES = (20, 40, 60)


@validate_ohlc(input_type="ohlc")
def detect_ipda_ranges(ohlc: pd.DataFrame) -> pd.DataFrame:
    """IPDA 20/40/60 rolling dealing ranges.

    For each window size N, computes:
      - ipda{N}_high   : highest high of prior N daily candles
      - ipda{N}_low    : lowest low of prior N daily candles
      - ipda{N}_eq     : equilibrium (midpoint)
      - ipda{N}_pct    : current close position within range (0-100)

    All values are forward-filled onto the intraday index so they are
    available bar-by-bar. The current daily candle is excluded (shift(1)).

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data at any timeframe. Will be resampled to daily internally.

    Returns
    -------
    pd.DataFrame with columns ipda20_high, ipda20_low, ipda20_eq,
    ipda20_pct, ipda40_*, ipda60_* — indexed to match ``ohlc``.
    """
    # Resample to daily OHLC (dropna removes non-trading days)
    daily = (
        ohlc.resample("D")
        .agg({"high": "max", "low": "min", "close": "last"})
        .dropna()
    )

    cols: dict[str, pd.Series] = {}
    for n in IPDA_RANGES:
        # Shift(1) excludes the current daily candle
        hi = daily["high"].rolling(n).max().shift(1)
        lo = daily["low"].rolling(n).min().shift(1)
        eq = (hi + lo) / 2.0
        rng = (hi - lo).replace(0, np.nan)
        pct = ((daily["close"] - lo) / rng) * 100.0

        # Forward-fill daily values onto the intraday index
        cols[f"ipda{n}_high"] = hi.reindex(ohlc.index, method="ffill")
        cols[f"ipda{n}_low"] = lo.reindex(ohlc.index, method="ffill")
        cols[f"ipda{n}_eq"] = eq.reindex(ohlc.index, method="ffill")
        cols[f"ipda{n}_pct"] = pct.reindex(ohlc.index, method="ffill")

    return pd.DataFrame(cols, index=ohlc.index)


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
