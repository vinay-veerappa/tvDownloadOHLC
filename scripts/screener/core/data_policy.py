"""
data_policy.py
==============
Enforces explicit data adjustment policies across trade_screener.
1. Technical levels, Moving Averages, Gaps, & ADR%: Split-Adjusted ONLY (Unadjusted for Dividends).
2. Relative Strength (RS) & Performance: Split- and Dividend-Adjusted Total Return.
"""
import pandas as pd
import numpy as np
from typing import Tuple

def prepare_price_series(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Given a daily OHLCV DataFrame (with columns Open, High, Low, Close, Volume, Dividends, Stock_Splits),
    returns a tuple of (split_adjusted_df, total_return_df).
    """
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame()
        
    split_df = df.copy()
    tr_df = df.copy()

    # Ensure required columns exist
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in split_df.columns:
            if col.lower() in split_df.columns:
                split_df[col] = split_df[col.lower()]
            else:
                raise ValueError(f"Missing required OHLCV column: {col}")

    # If yfinance provided Adj Close, use it for total return series
    if "Adj Close" in df.columns:
        tr_df["Close"] = df["Adj Close"]
    elif "adj_close" in df.columns:
        tr_df["Close"] = df["adj_close"]

    return split_df, tr_df
