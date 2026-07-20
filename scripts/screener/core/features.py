"""
features.py
===========
Vectorized Pandas/NumPy technical feature matrix engine (ADR-017 compliant).
Calculates all required indicators for Minervini Trend Template, Qullamaggie High Tight Flags,
Stockbee Momentum Bursts, and VCP patterns in a single vectorized pass.
"""
import pandas as pd
import numpy as np
from typing import Optional

def build_feature_matrix(
    df: pd.DataFrame,
    ticker: str = "",
    tr_df: Optional[pd.DataFrame] = None,
    industry_rs_rank: float = 50.0,
    has_upcoming_earnings: bool = False,
    float_info: Optional[dict] = None
) -> pd.DataFrame:
    """
    Given a split-adjusted daily OHLCV DataFrame, returns a DataFrame enriched
    with vectorized technical features.
    """
    if df is None or len(df) < 10:
        return pd.DataFrame()

    res = df.copy()
    if isinstance(res.columns, pd.MultiIndex):
        res.columns = res.columns.get_level_values(0)
    
    # Standardize casing to lowercase to prevent KeyError in YAML evaluators
    # and provide explicit split_adjusted column
    for col in ["Close", "High", "Low", "Volume", "Open"]:
        if col in res.columns:
            res.rename(columns={col: col.lower()}, inplace=True)
            
    res["close_split_adjusted"] = res.get("close", res.get("Close"))
    
    close = res["close"]
    high = res["high"]
    low = res["low"]
    volume = res["volume"]

    # 1. Moving Averages
    res["ema10"] = close.ewm(span=10, adjust=False).mean()
    res["ema20"] = close.ewm(span=20, adjust=False).mean()
    res["sma50"] = close.rolling(window=50, min_periods=10).mean()
    res["sma150"] = close.rolling(window=150, min_periods=20).mean()
    res["sma200"] = close.rolling(window=200, min_periods=30).mean()

    # 2. SMA Slopes & Distances
    res["sma200_slope_1m"] = (res["sma200"] - res["sma200"].shift(21)) / res["sma200"].shift(21) * 100.0
    res["dist_10ema_pct"] = (close - res["ema10"]) / res["ema10"] * 100.0
    res["dist_20ema_pct"] = (close - res["ema20"]) / res["ema20"] * 100.0

    # 3. ADR% (Average Daily Range %) over 20 sessions
    res["adr_20_pct"] = ((high - low) / low).rolling(window=20, min_periods=5).mean() * 100.0

    # 4. Volatility & VCP Tightness (ATR 5 / ATR 20)
    atr5 = (high - low).rolling(window=5, min_periods=3).mean()
    atr20 = (high - low).rolling(window=20, min_periods=5).mean().replace(0, np.nan)
    res["vcp_tightness_ratio"] = atr5 / atr20

    # 5. 52-Week High & Low Distances (approx 252 trading days)
    low_52w = low.rolling(window=252, min_periods=30).min()
    high_52w = high.rolling(window=252, min_periods=30).max()
    res["dist_52w_low_pct"] = (close - low_52w) / low_52w * 100.0
    res["dist_52w_high_pct"] = (high_52w - close) / high_52w * 100.0

    # 6. Relative Volume (RVOL 20)
    avg_vol_20 = volume.rolling(window=20, min_periods=5).mean().replace(0, np.nan)
    res["rvol_20"] = volume / avg_vol_20

    # 7. Alignment Indicators & Safe Division
    res["ma_aligned_fast_momentum"] = (
        (close > res["ema10"]) &
        (res["ema10"] > res["ema20"]) &
        (res["ema20"] > res["sma50"])
    )
    res["ma_aligned_minervini"] = (
        (close > res["sma50"]) &
        (res["sma50"] > res["sma150"]) &
        (res["sma150"] > res["sma200"]) &
        (res["sma200_slope_1m"] > 0.0)
    )
    
    # Safe division for closing range strength (avoid division by zero on halts/dojis)
    range_diff = high - low
    res["closing_range_strength"] = np.where(range_diff > 0, (close - low) / range_diff, 0.5)
    
    # 8. Shift-dependent & Total Return calculations
    tr_close = close
    if tr_df is not None and not tr_df.empty:
        col_name = "Adj Close" if "Adj Close" in tr_df.columns else ("close" if "close" in tr_df.columns else "Close")
        if col_name in tr_df.columns:
            tr_close = tr_df[col_name]

    res["runup_60d"] = tr_close / tr_close.shift(60).replace(0, np.nan)
    res["runup_5d_pct"] = (tr_close / tr_close.shift(5).replace(0, np.nan) - 1.0) * 100.0
    
    # Stockbee maxv5 & 10d move formulas (max 5-day and 10-day price move range percentage)
    low_5d_min = low.rolling(window=5, min_periods=3).min().replace(0, np.nan)
    high_5d_max = high.rolling(window=5, min_periods=3).max()
    res["max_move_5d_pct"] = ((high_5d_max - low_5d_min) / low_5d_min) * 100.0

    low_10d_min = low.rolling(window=10, min_periods=5).min().replace(0, np.nan)
    high_10d_max = high.rolling(window=10, min_periods=5).max()
    res["max_move_10d_pct"] = ((high_10d_max - low_10d_min) / low_10d_min) * 100.0

    res["gap_up"] = res["open"] / res["close_split_adjusted"].shift(1).replace(0, np.nan)
    res["momentum_burst"] = close / close.shift(1).replace(0, np.nan)
    res["sma150_slope_1m"] = (res["sma150"] - res["sma150"].shift(21)) / res["sma150"].shift(21)

    
    # 9. Dynamic Feature Binding from Upstream Drivers
    res["iv_rank_52w"] = 55.0  # Placeholder until Dolt DB integration is live
    res["has_upcoming_earnings_7d"] = has_upcoming_earnings
    res["industry_rs_rank"] = float(industry_rs_rank)

    if float_info:
        res["float_discrepancy_pct"] = float_info.get("discrepancy_pct", 0.0)
        res["float_flagged"] = float_info.get("flagged", False)
    else:
        res["float_discrepancy_pct"] = 0.0
        res["float_flagged"] = False

    res["ticker"] = ticker
    return res

