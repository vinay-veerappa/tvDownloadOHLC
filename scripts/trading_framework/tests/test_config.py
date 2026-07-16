import pytest
from pathlib import Path

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.trading_framework.config.config_loader import (
    AppConfig, RiskMode, TrailingType, load_config
)

@pytest.fixture
def mock_yaml():
    """Mock YAML configuration string including new use_micro_multipliers flag."""
    return """
data:
  parquet_dir: "data"
  symbols:
    price: ["NQ1!"]
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
  tick_size: {"NQ1!": 0.25}
  point_value: {"NQ1!": 20.0} # Mini Value
  default_contracts: 1
  use_micro_multipliers: true

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
  n_trials: 20
  n_jobs: 1
  primary_metric: "ev"
  secondary_metrics: ["profit_factor"]
  walk_forward: {train_days: 1, test_days: 1, step_days: 1, embargo_bars: 1}
  monte_carlo: {n_simulations: 1, eval_days: 1}
"""

def test_config_loading(mock_yaml, tmp_path):
    """Test that YAML loads into AppConfig and applies ADR-009 scaling."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(mock_yaml)
    
    config = load_config(str(config_file))
    
    # 1. Core Config
    assert "NQ1!" in config.symbols_price
    
    # 2. ADR-009 Scaling: NQ1! (Mini) point_value should be 2.0 (Micro) NOT 20.0 (Mini)
    # even though the mock_yaml explicitly provided 20.0.
    assert config.execution.point_value["NQ1!"] == 2.0
    
    # 3. Optimization Fix check
    assert config.optimization.n_trials == 20

def test_account_risk_enums(mock_yaml, tmp_path):
    """Test that account risk trailing type is correctly mapped to Enum."""
    config_file = tmp_path / "test_config_enum.yaml"
    config_file.write_text(mock_yaml)
    
    config = load_config(str(config_file))
    assert config.account_risk.trailing_type == TrailingType.EOD
