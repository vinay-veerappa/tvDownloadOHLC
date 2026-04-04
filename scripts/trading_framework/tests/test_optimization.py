import pytest
from pathlib import Path
from scripts.trading_framework.config.config_loader import load_config, OptimizationConfig

@pytest.fixture
def mock_yaml():
    """Mock configuration with valid optimization settings."""
    return """
data:
  parquet_dir: "data"
  symbols:
    price: ["MES"]
    internals: ["VOLD"]
  date_range: {start: "2024-01-01", end: "2024-02-01"}

risk_mode: "strategy"
trade_risk:
  default_policy: "fixed_target"
  policies:
    fixed_target: {tp_atr: 2.0, sl_atr: 1.0}

sessions:
  rth_start: "09:30"
  rth_end: "16:00"
  ib_end: "10:30"
  ny_am_end: "11:00"
  lunch_start: "11:00"
  lunch_end: "13:30"
  ny_pm_start: "13:30"
  last_entry: "14:30"
  flatten_by: "15:45"

execution:
  slippage_ticks: 1
  commission_per_contract: 0.62
  tick_size: {"MES": 0.25}
  point_value: {"MES": 5.0}
  default_contracts: 1

session_risk:
  daily_max_loss: 400.0
  max_consecutive_losers: 2
  pause_after_consecutive_minutes: 30
  hard_stop_consecutive_losers: 3
  max_trades_per_day: 3
  max_concurrent_positions: 1

account_risk:
  starting_equity: 50000.0
  trailing_drawdown: 2000.0
  trailing_type: "eod"
  profit_target: 3000.0
  weekly_drawdown_limit: 800.0
  weekly_action: "observation"

chop:
  tick_persistence: {window_minutes: 30}
  vold_slope: {method: "linreg"}
  trin_regime: {window_minutes: 30}
  vwap_cross: {window_bars_5m: 12}

mfe_mae:
  forward_horizons_minutes: [5, 15]
  max_forward_bars_1m: 120
  normalize_by: "atr"
  atr_period: 14
  atr_timeframe: "5min"

optimization:
  n_trials: 50
  n_jobs: 1
  primary_metric: "expectancy"
  secondary_metrics: ["drawdown"]
  walk_forward: {train_days: 10, test_days: 5, step_days: 2, embargo_bars: 10}
  monte_carlo: {n_simulations: 100, eval_days: 30}
"""

def test_optimization_config_mapping(mock_yaml, tmp_path):
    """Test that hyperparameter tuning settings correctly map into OptimizationConfig."""
    config_file = tmp_path / "test_opt_config.yaml"
    config_file.write_text(mock_yaml)
    
    # Use the standalone load_config function now required by ADR-009
    config = load_config(str(config_file))
    
    assert config.optimization.n_trials == 50
    assert config.optimization.primary_metric == "expectancy"
    assert "drawdown" in config.optimization.secondary_metrics
