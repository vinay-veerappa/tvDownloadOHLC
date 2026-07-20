"""
test_integration.py
===================
Integration tests for trade_screener engine fixes:
1. Dynamic feature matrix with Total Return, Industry RS, Earnings, Float validation.
2. YAML Evaluator strict error handling on invalid rule expressions.
3. DuckDB setup logger close price extraction.
4. Earnings calendar bridge functions.
"""
import os
import pytest
import pandas as pd
import numpy as np
import tempfile
from scripts.screener.core.features import build_feature_matrix
from scripts.screener.core.yaml_evaluator import evaluate_strategy_file
from scripts.screener.tracker.setup_logger import log_setups_to_duckdb
from scripts.market_data.sync_earnings_calendar import has_upcoming_earnings, is_episodic_pivot_catalyst


def get_mock_ohlcv(days=100):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="D")
    np.random.seed(42)
    close = 100.0 + np.cumsum(np.random.randn(days) * 0.5)
    high = close + np.abs(np.random.randn(days) * 0.3)
    low = close - np.abs(np.random.randn(days) * 0.3)
    open_p = low + (high - low) * 0.5
    volume = np.random.randint(500000, 2000000, size=days)
    
    df = pd.DataFrame({
        "Open": open_p,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume
    }, index=dates)
    return df


def test_build_feature_matrix_dynamic_bindings():
    df = get_mock_ohlcv(100)
    tr_df = df.copy()
    tr_df["Adj Close"] = df["Close"] * 1.05 # Simulate total return divergence
    
    fm = build_feature_matrix(
        df,
        ticker="TEST",
        tr_df=tr_df,
        industry_rs_rank=88.5,
        has_upcoming_earnings=True,
        float_info={"discrepancy_pct": 5.2, "flagged": False}
    )
    
    assert not fm.empty
    assert fm["industry_rs_rank"].iloc[-1] == 88.5
    assert fm["has_upcoming_earnings_7d"].iloc[-1] == True
    assert fm["float_discrepancy_pct"].iloc[-1] == 5.2
    assert fm["float_flagged"].iloc[-1] == False
    assert "runup_60d" in fm.columns


def test_yaml_evaluator_strict_error_handling(tmp_path):
    df = get_mock_ohlcv(100)
    fm = build_feature_matrix(df, ticker="TEST")
    
    # Create temporary YAML file with invalid expression referencing non-existent column
    bad_yaml = tmp_path / "bad_strategy.yaml"
    bad_yaml.write_text("""
strategy_id: "bad_strategy"
version: "1.0.0"
rules:
  - name: "invalid_rule"
    expression: "non_existent_column > 999"
""", encoding="utf-8")
    
    matches = evaluate_strategy_file(str(bad_yaml), fm)
    # Ensure invalid rule excludes rows rather than passing silently
    assert matches.empty


def test_duckdb_logger_close_price_extraction(tmp_path):
    df = get_mock_ohlcv(100)
    fm = build_feature_matrix(df, ticker="TEST")
    fm["market_regime"] = "BULL_EXPLOSIVE"
    fm["strategy_id"] = "test_strat"
    fm["strategy_version"] = "1.0.0"
    fm["config_hash"] = "12345678"
    
    latest_row = fm.iloc[[-1]].copy()
    db_file = tmp_path / "test_setups.duckdb"
    
    logged = log_setups_to_duckdb(latest_row, db_path=str(db_file))
    assert logged == 1
    
    import duckdb
    con = duckdb.connect(str(db_file))
    res = con.execute("SELECT ticker, entry_close_price FROM screener_setups").fetchone()
    con.close()
    
    assert res[0] == "TEST"
    assert res[1] > 0.0 # Verify entry_close_price is correctly extracted from lowercase 'close'


def test_earnings_calendar_bridge_functions():
    # Calling bridge functions should handle missing DB or empty queries gracefully without throwing errors
    res1 = has_upcoming_earnings("AAPL", window_days=7)
    res2 = is_episodic_pivot_catalyst("NVDA", window_days=3)
    assert isinstance(res1, bool)
    assert isinstance(res2, bool)
