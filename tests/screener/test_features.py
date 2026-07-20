import pytest
import pandas as pd
import numpy as np

from scripts.screener.core.features import build_feature_matrix

def test_vectorized_feature_matrix_calculation():
    """Verify 100% vectorized feature matrix calculations for Qullamaggie / Minervini setups."""
    dates = pd.date_range("2024-01-01", periods=250, freq="D")
    prices = np.linspace(100, 200, 250) + np.random.normal(0, 1.5, 250)
    
    df = pd.DataFrame({
        "Open": prices - 0.5,
        "High": prices + 2.0,
        "Low": prices - 2.0,
        "Close": prices,
        "Volume": [500000] * 250
    }, index=dates)

    matrix = build_feature_matrix(df, ticker="TEST")
    
    assert isinstance(matrix, pd.DataFrame)
    assert not matrix.empty
    assert "adr_20_pct" in matrix.columns
    assert "ema10" in matrix.columns
    assert "ema20" in matrix.columns
    assert "sma50" in matrix.columns
    assert "sma200" in matrix.columns
    assert "dist_10ema_pct" in matrix.columns
    assert "vcp_tightness_ratio" in matrix.columns
    assert "rvol_20" in matrix.columns
    
    last_row = matrix.iloc[-1]
    assert last_row["adr_20_pct"] > 0.0
    assert last_row["rvol_20"] >= 0.0
