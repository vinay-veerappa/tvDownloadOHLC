import pytest
import pandas as pd
import numpy as np

from scripts.screener.core.data_policy import prepare_price_series

def test_prepare_price_series_separation():
    """Verify split-adjusted vs total return series separation."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    raw_df = pd.DataFrame({
        "Open": np.linspace(100, 110, 10),
        "High": np.linspace(102, 112, 10),
        "Low": np.linspace(99, 109, 10),
        "Close": np.linspace(101, 111, 10),
        "Volume": [100000] * 10,
        "Dividends": [0, 0, 1.5, 0, 0, 0, 0, 0, 0, 0],
        "Stock_Splits": [0, 0, 0, 0, 2.0, 0, 0, 0, 0, 0]
    }, index=dates)

    split_df, tr_df = prepare_price_series(raw_df)
    
    assert "Close" in split_df.columns
    assert "Close" in tr_df.columns
    assert isinstance(split_df, pd.DataFrame)
    assert isinstance(tr_df, pd.DataFrame)
