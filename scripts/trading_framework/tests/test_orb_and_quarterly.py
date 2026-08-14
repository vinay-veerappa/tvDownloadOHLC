from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import numpy as np
import pytest

from scripts.libs_py.features.orb_bias import compute_orb_bias
from scripts.libs_py.features.quarterly_cycles import compute_quarterly_cycles
from scripts.trading_framework.core.multi_contract_backtester import MultiContractBacktester
from scripts.strategies.vwap_reclaim.core.vwap_institutional import VWAPInstitutionalStrategy


@pytest.fixture
def sample_rth_df():
    # Create 1-minute OHLCV data for 1 day
    times = pd.date_range("2026-01-05 09:30:00", "2026-01-05 16:00:00", freq="1min", tz="America/New_York")
    n = len(times)
    np.random.seed(42)

    # Synthetic prices
    price = 15000.0 + np.cumsum(np.random.normal(0.5, 2.0, size=n))
    high = price + np.random.uniform(1.0, 3.0, size=n)
    low = price - np.random.uniform(1.0, 3.0, size=n)
    close = price + np.random.uniform(-1.0, 1.0, size=n)
    volume = np.random.randint(100, 1000, size=n)

    df = pd.DataFrame(
        {
            "open": price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=times,
    )
    return df


def test_orb_bias_computation(sample_rth_df):
    df_orb = compute_orb_bias(sample_rth_df)

    assert "orb_1m_high" in df_orb.columns
    assert "orb_1m_low" in df_orb.columns
    assert "orb_1m_bias" in df_orb.columns
    assert "orb_1m_confirmed_up" in df_orb.columns
    assert "orb_1m_confirmed_dn" in df_orb.columns

    # Verify 09:30 bar values are frozen and broadcast
    orb_h = df_orb.loc["2026-01-05 09:30:00", "high"]
    orb_l = df_orb.loc["2026-01-05 09:30:00", "low"]
    assert df_orb.loc["2026-01-05 10:00:00", "orb_1m_high"] == orb_h
    assert df_orb.loc["2026-01-05 10:00:00", "orb_1m_low"] == orb_l


def test_quarterly_cycles_computation(sample_rth_df):
    df_q = compute_quarterly_cycles(sample_rth_df)

    assert "quarter_90m" in df_q.columns
    assert "is_quarterly_expansion_window" in df_q.columns
    assert "hour_quarter" in df_q.columns
    assert "is_05_box" in df_q.columns

    # 10:00 should be Q1 and hour_quarter 1
    assert df_q.loc["2026-01-05 10:00:00", "quarter_90m"] == "Q1"
    assert df_q.loc["2026-01-05 10:00:00", "hour_quarter"] == 1

    # 11:15 should be Q2 and hour_quarter 2
    assert df_q.loc["2026-01-05 11:15:00", "quarter_90m"] == "Q2"
    assert df_q.loc["2026-01-05 11:15:00", "hour_quarter"] == 2


def test_multi_contract_backtester_execution(sample_rth_df):
    strat = VWAPInstitutionalStrategy(ticker="NQ1")
    sigs = strat.hunt(sample_rth_df, params={"use_orb_bias": False, "use_quarterly_cycles": False})

    backtester = MultiContractBacktester(contracts=2, tp1_qty_pct=0.5, point_value=2.0)
    res = backtester.run(sigs, sample_rth_df)

    assert "num_trades" in res
    assert "win_rate_%" in res
    assert "profit_factor" in res
    assert "total_net_pnl_usd" in res
    assert "max_drawdown_usd" in res
