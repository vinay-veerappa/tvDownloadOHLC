import pytest
import pandas as pd
import numpy as np

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

def test_cli_runner_execution():
    """Verify CLI runner executes full screener pipeline."""
    results = run_screener(strategy_id="qullamaggie_hft", limit=5)
    assert isinstance(results, pd.DataFrame)
