import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from scripts.screener.core.regime import get_market_regime, MarketRegimeState

@patch('scripts.screener.core.regime.DB_PATH')
@patch('scripts.screener.core.regime.yf.Ticker')
@patch('scripts.screener.core.regime.sqlite3.connect')
def test_market_regime_evaluator(mock_sqlite_connect, mock_yf_ticker, mock_db_path):
    """Verify global market regime evaluator queries correct data and returns valid state."""
    # Mock DB path exists
    mock_db_path.exists.return_value = True
    
    # Mock SQLite response for macro event
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_sqlite_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [0] # No macro events
    
    # Mock yfinance SPY data
    mock_ticker_instance = MagicMock()
    mock_yf_ticker.return_value = mock_ticker_instance
    mock_history = pd.DataFrame({"Close": range(100, 160)})
    mock_ticker_instance.history.return_value = mock_history
    
    regime = get_market_regime()
    
    # Verify SQLite was called correctly
    mock_cursor.execute.assert_called_once()
    query, args = mock_cursor.execute.call_args[0]
    assert "datetime LIKE ?" in query
    assert "impact = 'HIGH'" in query
    
    # Verify yfinance was called correctly
    mock_yf_ticker.assert_called_once_with("SPY")
    mock_ticker_instance.history.assert_called_once_with(period="6mo")
    
    assert isinstance(regime, MarketRegimeState)
    assert regime.status == "BULL_EXPLOSIVE"
    assert regime.spy_above_21ema is True
    assert regime.spy_above_50sma is True
    assert regime.is_macro_high_risk is False
