import pandas as pd

from scripts.trading_framework.core.backtest_engine import VectorizedBacktester


def test_backtest_engine_mixed_direction_chunk_metrics_do_not_crash_and_emit_cols():
    idx = pd.date_range("2026-01-01 09:30:00", periods=30, freq="1min")
    data = pd.DataFrame(
        {
            "open": [100.0 + i * 0.1 for i in range(len(idx))],
            "high": [100.4 + i * 0.1 for i in range(len(idx))],
            "low": [99.8 + i * 0.1 for i in range(len(idx))],
            "close": [100.1 + i * 0.1 for i in range(len(idx))],
        },
        index=idx,
    )

    # Mixed long/short in one batch; previously path selection used first row only.
    signals = pd.DataFrame(
        {
            "signal_time": [idx[2], idx[4], idx[6], idx[8]],
            "direction": ["long", "short", "long", "short"],
            "entry_price": [100.3, 100.5, 100.7, 100.9],
            "stop_price": [99.9, 101.1, 100.3, 101.5],
            "target1_price": [100.9, 99.9, 101.3, 100.3],
        }
    )

    bt = VectorizedBacktester()
    res = bt.run(signals, data, {"ticker": "NQ1"})

    td = res["trades_detailed"]
    assert len(td) == 4
    assert "mfe_wick_pct" in td.columns
    assert "mfe_close_pct" in td.columns
    assert td["mfe_wick_pct"].notna().all()
    assert td["mfe_close_pct"].notna().all()


def test_backtest_engine_exit_index_clipped_at_data_end():
    idx = pd.date_range("2026-01-01 09:30:00", periods=5, freq="1min")
    data = pd.DataFrame(
        {
            "open": [100, 100, 100, 100, 100],
            "high": [100.2, 100.2, 100.2, 100.2, 100.2],
            "low": [99.8, 99.8, 99.8, 99.8, 99.8],
            "close": [100, 100, 100, 100, 100],
        },
        index=idx,
    )

    # Late signal with unreachable TP/SL forces fallback to "last available" close path.
    signals = pd.DataFrame(
        {
            "signal_time": [idx[-1]],
            "direction": ["long"],
            "entry_price": [100.0],
            "stop_price": [50.0],
            "target1_price": [150.0],
        }
    )

    bt = VectorizedBacktester()
    res = bt.run(signals, data, {"ticker": "NQ1"})
    td = res["trades_detailed"]

    assert len(td) == 1
    # Should not throw IndexError and exit time should be a valid timestamp from data index.
    assert td.iloc[0]["exit_time"] in data.index
