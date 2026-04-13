from types import SimpleNamespace

import pandas as pd

import scripts.trading_framework.run_backtest as rb


def test_run_research_pipeline_uses_registry_and_trades_detailed(monkeypatch):
    # Mock config object with required nested attrs
    cfg = SimpleNamespace(
        account_risk=SimpleNamespace(starting_equity=50000.0, trailing_drawdown=2000.0),
        session_risk=SimpleNamespace(daily_max_loss=400.0, max_trades_per_day=4),
        mfe_mae=SimpleNamespace(),
        optimization=SimpleNamespace(monte_carlo=SimpleNamespace()),
    )

    # Mock dataframe and signals
    idx = pd.date_range("2026-01-01 09:30:00", periods=5, freq="1min")
    df = pd.DataFrame({"close": [100, 101, 102, 103, 104]}, index=idx)
    sig = pd.DataFrame(
        {
            "signal_time": [idx[1]],
            "direction": ["long"],
            "entry_price": [101.0],
            "stop_price": [100.0],
            "target1_price": [103.0],
        }
    )

    class _Loader:
        def __init__(self, _cfg):
            pass

        def load_enriched(self, _ticker):
            return df

    class _Strategy:
        def generate_signals(self, _df, _params):
            return sig

    class _Engine:
        def run(self, _signals, _df, _risk):
            return {
                "equity_curve": pd.Series([1.0, 1.01], index=idx[:2]),
                "trade_returns_pct": pd.Series([0.01]),
                "trades_detailed": pd.DataFrame(
                    {"pnl_pct": [1.0], "exit_time": [idx[2]]}
                ),
            }

    monkeypatch.setattr(rb, "load_config", lambda _path: cfg)
    monkeypatch.setattr(rb, "DataLoader", _Loader)
    monkeypatch.setattr(rb, "get_strategy", lambda _strategy, _ticker: _Strategy())
    monkeypatch.setattr(rb, "VectorizedBacktester", lambda: _Engine())
    monkeypatch.setattr(rb, "compute_mfe_mae", lambda _signals, _df, _mfe: pd.DataFrame())
    monkeypatch.setattr(rb, "compute_prop_eval_stats", lambda _rets, _mc: {"pass_rate": 0.9})
    monkeypatch.setattr(rb, "generate_tearsheet", lambda _res: "ok")
    monkeypatch.setattr(rb, "generate_mfe_mae_report", lambda *_args, **_kwargs: None)

    args = SimpleNamespace(
        ticker="NQ1",
        strategy="box_reversion",
        config="scripts/trading_framework/config/sessions.yaml",
        optimize=False,
        trials=1,
    )

    # Should run without import/key errors from stale API names/keys.
    rb.run_research_pipeline(args)
