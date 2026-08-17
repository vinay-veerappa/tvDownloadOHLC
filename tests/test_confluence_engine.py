"""
Tests for Confluence Feature Engine and Confluence Backtester
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

from src.range_prob.confluence_engine import ConfluenceFeatureEngine
from src.range_prob.confluence_backtester import ConfluenceBacktester


@pytest.fixture
def sample_synthetic_1m_data():
    """Generates 2 days of synthetic 1m OHLC bars."""
    start_time = datetime(2026, 1, 5, 18, 0, 0, tzinfo=pytz.timezone("America/New_York"))
    records = []
    price = 20000.0

    for i in range(2880):  # 2 full days of 1m bars
        t = start_time + timedelta(minutes=i)
        drift = np.sin(i / 30.0) * 5.0 + np.random.normal(0, 2.0)
        price += drift
        h = price + abs(np.random.normal(2.0, 1.0))
        l = price - abs(np.random.normal(2.0, 1.0))
        c = price + np.random.normal(0, 1.0)
        records.append({
            "time": int(t.timestamp() * 1000),
            "start_time_ny": t,
            "open": price,
            "high": max(price, h, c),
            "low": min(price, l, c),
            "close": c,
            "volume": 100,
        })
        price = c

    return pd.DataFrame(records)


def test_confluence_engine_features(sample_synthetic_1m_data):
    engine = ConfluenceFeatureEngine()
    df_confluence = engine.build_confluence_dataset(sample_synthetic_1m_data, ticker="NQ", range_minutes=60)

    assert not df_confluence.empty
    # Quarters columns
    assert "q1_high" in df_confluence.columns
    assert "q1_low" in df_confluence.columns
    assert "q2_swept_q1_high" in df_confluence.columns
    assert "q2_swept_q1_low" in df_confluence.columns
    assert "q2_bull_sweep" in df_confluence.columns
    assert "q2_bear_sweep" in df_confluence.columns
    # Candle Science columns
    assert "c1_dir" in df_confluence.columns
    assert "c2_dir" in df_confluence.columns
    assert "cs_bull_prob" in df_confluence.columns
    assert "cs_expansion_prob" in df_confluence.columns


def test_confluence_backtester_execution(sample_synthetic_1m_data):
    engine = ConfluenceFeatureEngine()
    df_confluence = engine.build_confluence_dataset(sample_synthetic_1m_data, ticker="NQ", range_minutes=60)

    # Force artificial signals for testing
    df_confluence["s_prob"] = 80.0
    df_confluence["s_res_rate"] = 50.0
    df_confluence["s_n"] = 25
    df_confluence["s_dir"] = "U"
    df_confluence["is_adjacent"] = True
    df_confluence["open_pos"] = 0.05

    bt = ConfluenceBacktester(min_prob=70.0, min_sample_size=10, entry_timing="range_open")
    res = bt.run_backtest(df_confluence)

    assert "total_trades" in res
    assert res["total_trades"] > 0
    assert "win_rate" in res
    assert "net_pnl" in res
    assert "profit_factor" in res
