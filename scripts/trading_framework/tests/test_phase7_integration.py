import pandas as pd
import numpy as np


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

from scripts.trading_framework.core.signal_adapter import enrich_signals
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester


def test_signal_adapter_enriches_day_event_and_first_boundary(monkeypatch):
    idx = pd.date_range("2026-04-01 13:30:00", periods=5, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "close": [100.0, 100.2, 100.1, 100.3, 100.4],
            "chop_score": [2, 2, 3, 3, 2],
            "chop_regime": ["MIX"] * 5,
            "session_block": ["NY_AM"] * 5,
            "vwap_distance_atr": [0.1] * 5,
            "chop_vwap_flag": [False] * 5,
        },
        index=idx,
    )

    sig = pd.DataFrame(
        {
            "signal_time": [idx[2]],
            "direction": ["long"],
            "entry_price": [100.1],
            "stop_price": [99.6],
            "target1_price": [100.8],
        }
    )

    def _mock_vix():
        vix_idx = pd.to_datetime(["2026-04-01"])
        return pd.DataFrame(
            {
                "vix_daily": [18.0],
                "vix_regime": ["Normal"],
                "vvix_level": [95.0],
                "vvix_regime": ["Normal"],
            },
            index=vix_idx,
        )

    def _mock_daily_context(_symbol: str):
        return pd.DataFrame(
            {
                "trading_date": [pd.to_datetime("2026-04-01").date()],
                "day_of_week": [2],
                "event_type": ["FOMC"],
            }
        )

    def _mock_range_context():
        return pd.DataFrame(
            {
                "symbol": ["NQ1"],
                "trading_date": [pd.to_datetime("2026-04-01").date()],
                "range_name": ["OR_15"],
                "first_boundary_broken": ["HIGH"],
            }
        )

    monkeypatch.setattr("scripts.trading_framework.core.signal_adapter._load_vix_context", _mock_vix)
    monkeypatch.setattr("scripts.trading_framework.core.signal_adapter._load_daily_context", _mock_daily_context)
    monkeypatch.setattr("scripts.trading_framework.core.signal_adapter._load_range_first_boundary", _mock_range_context)

    out = enrich_signals(sig, df, strategy_name="ORB_BREAKOUT", symbol="NQ1")

    assert len(out) == 1
    row = out.iloc[0]
    assert int(row["context_day_of_week"]) == 2
    assert row["context_event_type"] == "FOMC"
    assert row["context_first_boundary_broken"] == "HIGH"
    assert row["context"]["event_type"] == "FOMC"
    assert row["context"]["first_boundary_broken"] == "HIGH"


def test_signal_adapter_defaults_first_boundary_for_non_orb(monkeypatch):
    idx = pd.date_range("2026-04-01 13:30:00", periods=3, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "close": [100.0, 100.1, 100.2],
            "chop_score": [2, 2, 2],
            "chop_regime": ["MIX"] * 3,
            "session_block": ["NY_AM"] * 3,
            "vwap_distance_atr": [0.1] * 3,
            "chop_vwap_flag": [False] * 3,
        },
        index=idx,
    )
    sig = pd.DataFrame(
        {
            "signal_time": [idx[1]],
            "direction": ["long"],
            "entry_price": [100.1],
            "stop_price": [99.8],
            "target1_price": [100.4],
        }
    )

    monkeypatch.setattr("scripts.trading_framework.core.signal_adapter._load_vix_context", lambda: pd.DataFrame())
    monkeypatch.setattr("scripts.trading_framework.core.signal_adapter._load_daily_context", lambda _symbol: pd.DataFrame())
    monkeypatch.setattr("scripts.trading_framework.core.signal_adapter._load_range_first_boundary", lambda: pd.DataFrame())

    out = enrich_signals(sig, df, strategy_name="MOMENTUM", symbol="NQ1")
    assert out.iloc[0]["context_first_boundary_broken"] == "NONE"


def test_backtester_phase7_outputs_rolling_and_wick_close_metrics():
    idx = pd.date_range("2026-01-01 09:30:00", periods=300, freq="1min")
    base = np.linspace(100.0, 110.0, num=len(idx))
    data = pd.DataFrame(
        {
            "open": base,
            "high": base + 0.5,
            "low": base - 0.4,
            "close": base + 0.1,
        },
        index=idx,
    )

    sig = pd.DataFrame(
        {
            "signal_time": [idx[10], idx[30], idx[60], idx[90]],
            "direction": ["long", "long", "long", "long"],
            "entry_price": [float(data.iloc[10]["close"]), float(data.iloc[30]["close"]), float(data.iloc[60]["close"]), float(data.iloc[90]["close"])],
            "stop_price": [float(data.iloc[10]["close"] - 0.8), float(data.iloc[30]["close"] - 0.8), float(data.iloc[60]["close"] - 0.8), float(data.iloc[90]["close"] - 0.8)],
            "target1_price": [float(data.iloc[10]["close"] + 0.6), float(data.iloc[30]["close"] + 0.6), float(data.iloc[60]["close"] + 0.6), float(data.iloc[90]["close"] + 0.6)],
        }
    )

    bt = VectorizedBacktester()
    res = bt.run(sig, data, {"ticker": "NQ1"})

    assert "rolling_performance" in res
    assert "30d" in res["rolling_performance"]
    assert "90d" in res["rolling_performance"]

    assert "performance_by_measurement" in res
    assert "wick" in res["performance_by_measurement"]
    assert "close" in res["performance_by_measurement"]

    td = res["trades_detailed"]
    assert "mfe_wick_pct" in td.columns
    assert "mfe_close_pct" in td.columns
    assert (td["mfe_wick_pct"] >= td["mfe_close_pct"]).all()
