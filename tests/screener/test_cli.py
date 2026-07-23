import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from scripts.screener.tracker.setup_logger import log_setups_to_duckdb
from scripts.screener.cli import run_screener

def test_duckdb_setup_logging(tmp_path):
    """Verify setup logging to DuckDB with strategy versions and config hashes."""
    db_file = str(tmp_path / "test_setups.duckdb")
    
    mock_matches = pd.DataFrame([{
        "ticker": "AAPL",
        "Close": 185.50,
        "adr_20_pct": 4.2,
        "dist_10ema_pct": 1.2,
        "rvol_20": 2.1,
        "strategy_id": "qullamaggie_hft",
        "strategy_version": "1.0.0",
        "config_hash": "a1b2c3d4"
    }])
    
    count = log_setups_to_duckdb(mock_matches, db_path=db_file)
    assert count == 1

@patch('scripts.screener.core.provider.is_cache_fresh', return_value=False)
@patch('scripts.screener.core.provider.fetch_yfinance_batch')
@patch('scripts.screener.cli.fetch_finviz_candidates')
@patch('scripts.screener.cli.get_market_regime')
def test_cli_runner_execution(mock_get_regime, mock_fetch_candidates, mock_fetch_yf_batch, mock_cache_fresh):
    """Verify CLI runner executes full screener pipeline with pluggable data provider."""
    from scripts.screener.core.regime import MarketRegimeState
    
    # Mock regime to BULL_EXPLOSIVE to allow longs
    mock_get_regime.return_value = MarketRegimeState(
        status="BULL_EXPLOSIVE", spy_close=500.0, spy_above_21ema=True, spy_above_50sma=True,
        is_macro_high_risk=False, evaluated_at="2026-07-20T12:00:00"
    )
    
    # Mock universe
    mock_fetch_candidates.return_value = [{"ticker": "MOCK"}]
    
    # Mock yfinance data to ensure it passes strict qullamaggie_hft filters
    dates = pd.date_range(end=pd.Timestamp.now(), periods=250, freq='D')
    
    # Needs 100% runup in 60 days.
    prices = np.linspace(10, 20, 190)
    prices = np.append(prices, np.linspace(20, 50, 60))
    
    # Needs volume dry up (rvol_20 < 0.7)
    volume = np.full(250, 5000000)
    volume[-5:] = 2000000
    
    # Needs VCP tightening (atr5 / atr20 < 0.6)
    spreads = np.full(250, 2.0)
    spreads[-5:] = 0.5
    
    mock_df = pd.DataFrame({
        "datetime": dates,
        "Open": prices - spreads/2,
        "High": prices + spreads,
        "Low": prices - spreads,
        "Close": prices,
        "Volume": volume
    })

    mock_fetch_yf_batch.return_value = {"MOCK": mock_df}

    results = run_screener(strategy_id="qullamaggie_hft", limit=5, provider="yfinance", force_refresh=True)

    # Verify provider was called
    mock_fetch_yf_batch.assert_called_once_with(["MOCK"])

    assert isinstance(results, pd.DataFrame)
    assert len(results) >= 1
    assert results.iloc[0]["ticker"] == "MOCK"


def test_cli_report_generation(tmp_path):
    """Verify generate_screener_reports creates matrix CSV and export watchlists."""
    from scripts.screener.generate_reports import generate_screener_reports
    
    with patch('scripts.screener.core.provider.is_cache_fresh', return_value=False), \
         patch('scripts.screener.generate_reports.fetch_finviz_candidates') as mock_fetch, \
         patch('scripts.screener.generate_reports.calculate_industry_rs') as mock_rs, \
         patch('scripts.screener.core.provider.fetch_yfinance_batch') as mock_fetch_yf_batch:
        
        mock_fetch.return_value = [{"ticker": "MOCK_RPT", "company": "Mock Co", "sector": "Tech", "industry": "Software"}]
        mock_rs.return_value = {"Software": 90.0}
        
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq='D')
        mock_df = pd.DataFrame({
            "datetime": dates,
            "Open": np.full(100, 100.0),
            "High": np.full(100, 105.0),
            "Low": np.full(100, 95.0),
            "Close": np.full(100, 102.0),
            "Volume": np.full(100, 1000000)
        })
        mock_fetch_yf_batch.return_value = {"MOCK_RPT": mock_df}
        
        paths = generate_screener_reports(limit=5)
        assert "comparison_matrix" in paths
        assert "tradingview_watchlist" in paths
        assert "thinkorswim_watchlist" in paths
        assert os.path.exists(paths["comparison_matrix"])
        assert os.path.exists(paths["tradingview_watchlist"])
        assert os.path.exists(paths["thinkorswim_watchlist"])
