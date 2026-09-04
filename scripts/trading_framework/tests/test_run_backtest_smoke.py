"""Smoke tests for `run_backtest.run_research_pipeline`.

This is the only automated reader of the de facto research entry point, and it
had been red. Its job is to catch stale API names and stale dict keys as the
pipeline's collaborators change -- so the collaborators are mocked and the
pipeline's own wiring is what is under test.

It now also asserts the two things the pipeline gained: that a searched run
cannot report on the bars it searched, and that the returned run record's
`attributable` verdict responds to whether the engine actually produced metrics.
"""
from types import SimpleNamespace

import pandas as pd
import pytest


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

import scripts.trading_framework.run_backtest as rb
from scripts.trading_framework.provenance import run_record as rr


def _cfg():
    return SimpleNamespace(
        account_risk=SimpleNamespace(starting_equity=50000.0, trailing_drawdown=2000.0,
                                     daily_loss_limit=1000.0),
        session_risk=SimpleNamespace(daily_max_loss=400.0, max_trades_per_day=4),
        mfe_mae=SimpleNamespace(),
        optimization=SimpleNamespace(monte_carlo=SimpleNamespace()),
        prop_firm=SimpleNamespace(run_profiles=['apex_50k'], overrides={},
                                  n_simulations=10, primary_profile='apex_50k'),
        execution=SimpleNamespace(point_value={'NQ1': 20.0}),
    )


def _frame(periods=400):
    idx = pd.date_range("2026-01-01 09:30:00", periods=periods, freq="1min")
    close = pd.Series(range(periods), index=idx, dtype=float) * 0.1 + 100.0
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                         "close": close, "volume": 1000.0}, index=idx)


def _signals(df, positions=(10, 50, 100)):
    px = df["close"].to_numpy()[list(positions)]
    return pd.DataFrame({
        "signal_time": df.index[list(positions)],
        "direction": ["long"] * len(positions),
        "entry_price": px,
        "stop_price": px - 1.0,
        "target1_price": px + 1.0,
    })


def _install(monkeypatch, tmp_path, df, sig, engine_result):
    class _Loader:
        def __init__(self, _cfg):
            pass

        def load_enriched(self, _ticker):
            return df

    class _Strategy:
        strategy_name = "Mock Strategy"

        def get_param_grid(self):
            return {"x": ("int", 1, 5)}

        def generate_signals(self, _df, _params):
            return sig

    class _Engine:
        def run(self, _signals, _df, _risk):
            return engine_result

    monkeypatch.setattr(rb, "load_config", lambda _path: _cfg())
    monkeypatch.setattr(rb, "DataLoader", _Loader)
    monkeypatch.setattr(rb, "get_strategy", lambda _s, _t: _Strategy())
    monkeypatch.setattr(rb, "VectorizedBacktester", lambda: _Engine())
    monkeypatch.setattr(rb, "compute_mfe_mae", lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setattr(rb, "compute_prop_eval_stats", lambda *_a, **_k: {"pass_rate": 0.9})
    monkeypatch.setattr(rb, "generate_tearsheet", lambda _res: "ok")
    monkeypatch.setattr(rb, "generate_mfe_mae_report", lambda *_a, **_k: None)
    # Neither the artifacts nor the ledger may touch the real results tree.
    monkeypatch.setattr(rr, "DEFAULT_LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.chdir(tmp_path)


def _args(**kw):
    base = dict(
        ticker="NQ1",
        strategy="box_reversion",
        config="scripts/trading_framework/config/sessions.yaml",
        optimize=False,
        trials=1,
        engine="vectorized",
        oos_start=None,
        price_adjustment="unadjusted",
        allow_unattributable=False,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------
def test_pipeline_runs_and_returns_an_attributable_record(monkeypatch, tmp_path):
    """Stale API names and stale dict keys must surface here, not in a research run."""
    df = _frame()
    result = {
        "equity_curve": pd.Series([1.0, 1.01], index=df.index[:2]),
        "trade_returns_pct": pd.Series([0.01]),
        "trades_detailed": pd.DataFrame({"pnl_pct": [1.0], "exit_time": [df.index[2]]}),
        "num_trades": 3,
        "sharpe_ratio": 1.1,
        "win_rate_%": 66.0,
        "max_drawdown_%": -2.0,
        "signal_alignment": {"signals_in": 3, "signals_kept": 3,
                             "dropped_before_frame_start": 0,
                             "dropped_snap_too_far": 0},
    }
    _install(monkeypatch, tmp_path, df, _signals(df), result)

    record = rb.run_research_pipeline(_args())

    assert record is not None
    assert record["attributable"] is True, record["refusals"] + record["missingRequired"]
    assert record["metrics"]["num_trades"] == 3
    assert record["data"]["contentHash"].startswith("sha256:")
    assert [s["name"] for s in record["stages"]][:4] == [
        "load_data", "split", "causality_probe", "generate_signals"]


def test_a_zero_trade_result_is_refused(monkeypatch, tmp_path):
    """Control: the verdict must respond to the engine actually measuring something."""
    df = _frame()
    result = {
        "equity_curve": pd.Series([1.0, 1.0], index=df.index[:2]),
        "trade_returns_pct": pd.Series([], dtype=float),
        "trades_detailed": pd.DataFrame(),
        "num_trades": 0,
        "sharpe_ratio": 0.0,
        "max_drawdown_%": 0.0,
    }
    _install(monkeypatch, tmp_path, df, _signals(df), result)

    record = rb.run_research_pipeline(_args())
    assert record["attributable"] is False
    assert any("ZERO trades" in r for r in record["refusals"])


def test_optimize_without_oos_start_is_refused(monkeypatch, tmp_path):
    """A searched result may not be reported on the bars it searched."""
    df = _frame()
    _install(monkeypatch, tmp_path, df, _signals(df), {"num_trades": 1})

    with pytest.raises(ValueError, match="in-sample result"):
        rb.run_research_pipeline(_args(optimize=True))


def test_a_full_sample_run_without_optimize_warns_but_proceeds(monkeypatch, tmp_path):
    """Without a search there is nothing to overfit, so this is legitimate --
    but the report still covers the bars it ran on, and a reader is told."""
    df = _frame()
    result = {"equity_curve": pd.Series([1.0], index=df.index[:1]),
              "trade_returns_pct": pd.Series([0.01]),
              "trades_detailed": pd.DataFrame({"pnl_pct": [1.0]}),
              "num_trades": 3, "sharpe_ratio": 1.0, "max_drawdown_%": -1.0}
    _install(monkeypatch, tmp_path, df, _signals(df), result)

    record = rb.run_research_pipeline(_args())
    assert any("no --oos-start" in w for w in record["warnings"])
    split = [s for s in record["stages"] if s["name"] == "split"][0]
    assert split["detail"]["reportIsOutOfSample"] is False


def test_oos_start_restricts_the_reporting_window(monkeypatch, tmp_path):
    df = _frame()
    cut = df.index[200]
    result = {"equity_curve": pd.Series([1.0], index=df.index[:1]),
              "trade_returns_pct": pd.Series([0.01]),
              "trades_detailed": pd.DataFrame({"pnl_pct": [1.0]}),
              "num_trades": 1, "sharpe_ratio": 1.0, "max_drawdown_%": -1.0}
    # signals on both sides of the cut; only the later one is this run's evidence
    _install(monkeypatch, tmp_path, df, _signals(df, (10, 250)), result)

    # A full timestamp, not a date: this fixture's 400 bars are all on one day,
    # so a date-only cut cannot split it -- which the split guard correctly
    # refused when this test first tried it.
    record = rb.run_research_pipeline(_args(oos_start=str(cut)))
    split = [s for s in record["stages"] if s["name"] == "split"][0]
    assert split["detail"]["reportIsOutOfSample"] is True
    gen = [s for s in record["stages"] if s["name"] == "generate_signals"][0]
    assert gen["detail"]["signalsGenerated"] == 2
    assert gen["detail"]["signalsInReportWindow"] == 1


def test_a_failure_is_recorded_before_it_propagates(monkeypatch, tmp_path):
    df = _frame()

    class _Boom:
        def run(self, *_a, **_k):
            raise RuntimeError("engine exploded")

    _install(monkeypatch, tmp_path, df, _signals(df), {})
    monkeypatch.setattr(rb, "VectorizedBacktester", lambda: _Boom())

    with pytest.raises(RuntimeError, match="engine exploded"):
        rb.run_research_pipeline(_args())

    rows = rr.read_ledger(str(tmp_path / "ledger.jsonl"))
    assert rows and rows[-1]["status"] == "failed"


def test_artifacts_do_not_overwrite_a_previous_run(monkeypatch, tmp_path):
    """The tearsheet path was fixed per ticker+strategy, so run N+1 silently
    replaced run N and no history existed."""
    df = _frame()
    result = {"equity_curve": pd.Series([1.0], index=df.index[:1]),
              "trade_returns_pct": pd.Series([0.01]),
              "trades_detailed": pd.DataFrame({"pnl_pct": [1.0]}),
              "num_trades": 1, "sharpe_ratio": 1.0, "max_drawdown_%": -1.0}
    _install(monkeypatch, tmp_path, df, _signals(df), result)

    a = rb.run_research_pipeline(_args())
    b = rb.run_research_pipeline(_args())
    assert a["runId"] != b["runId"]
    records = list((tmp_path / "results").rglob("run_record.json"))
    assert len(records) == 2, records
