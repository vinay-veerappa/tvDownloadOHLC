import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from scripts.screener.core.yaml_evaluator import evaluate_strategy_file, load_yaml_strategy
from scripts.screener.core.features import build_feature_matrix

def test_yaml_strategy_loading_and_evaluation():
    """Verify loading and evaluation of declarative YAML strategy files."""
    dates = pd.date_range("2024-01-01", periods=250, freq="D")
    prices = np.linspace(100, 200, 250)
    
    df = pd.DataFrame({
        "Open": prices - 0.5,
        "High": prices + 2.0,
        "Low": prices - 2.0,
        "Close": prices,
        "Volume": [500000] * 250
    }, index=dates)

    feature_matrix = build_feature_matrix(df, ticker="TEST_TICKER")
    
    # Path to Qullamaggie YAML strategy
    yaml_path = Path(__file__).resolve().parents[2] / "scripts" / "screener" / "config" / "qullamaggie_hft.yaml"
    
    strategy = load_yaml_strategy(str(yaml_path))
    assert strategy["strategy_id"] == "qullamaggie_hft"
    assert "rules" in strategy

    matches = evaluate_strategy_file(str(yaml_path), feature_matrix)
    assert isinstance(matches, pd.DataFrame)
