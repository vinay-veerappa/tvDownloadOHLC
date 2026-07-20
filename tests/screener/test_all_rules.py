"""
test_all_rules.py
=================
Parametrized test suite that validates every YAML strategy configuration
in `scripts/screener/config/` against a comprehensive feature matrix.
"""
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from scripts.screener.core.features import build_feature_matrix
from scripts.screener.core.yaml_evaluator import evaluate_strategy_file, load_yaml_strategy

CONFIG_DIR = Path(__file__).resolve().parents[2] / "scripts" / "screener" / "config"
STRATEGY_FILES = list(CONFIG_DIR.glob("*.yaml"))


def get_mock_rich_ohlcv(days=250):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="D")
    np.random.seed(123)
    
    # Strong uptrend data to ensure features satisfy various strategy rules
    close = 50.0 * (1.002 ** np.arange(days)) + np.random.randn(days) * 0.2
    high = close + 1.0
    low = close - 1.0
    open_p = close - 0.2
    volume = np.random.randint(1000000, 3000000, size=days)
    
    df = pd.DataFrame({
        "Open": open_p,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume
    }, index=dates)
    return df


@pytest.fixture
def rich_feature_matrix():
    df = get_mock_rich_ohlcv(250)
    fm = build_feature_matrix(
        df,
        ticker="MOCK",
        industry_rs_rank=95.0,
        has_upcoming_earnings=False,
        float_info={"discrepancy_pct": 2.0, "flagged": False}
    )
    return fm


def test_strategy_files_exist():
    assert len(STRATEGY_FILES) >= 11


@pytest.mark.parametrize("yaml_path", STRATEGY_FILES, ids=lambda p: p.stem)
def test_evaluate_each_strategy_yaml(yaml_path, rich_feature_matrix):
    config = load_yaml_strategy(str(yaml_path))
    assert "strategy_id" in config
    assert "rules" in config
    
    # Evaluate strategy against feature matrix
    matches = evaluate_strategy_file(str(yaml_path), rich_feature_matrix)
    # The evaluation must return a DataFrame (empty or populated), without raising any exceptions
    assert isinstance(matches, pd.DataFrame)
