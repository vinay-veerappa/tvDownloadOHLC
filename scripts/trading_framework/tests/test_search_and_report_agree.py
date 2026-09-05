"""The search and the report must score under the SAME payoff function.

`run_optimization` took `engine=None` and fell back to `VectorizedBacktester()`,
and nothing ever passed one. Meanwhile `--engine` defaults to `nt8_parity`
(ADR-024), so the tearsheet came from `NT8ParityBacktester`. The two engines do
not agree on what a trade is worth:

    VectorizedBacktester   honours the hunter's own `target1_price`,
                           no bracket, no risk state machine, no costs
    NT8ParityBacktester    10/30 bps queen/runner bracket, NT8's risk state
                           machine, commission, slippage

So parameters were SELECTED under one and JUDGED under the other, and the
reported Sharpe described a parameter set that nothing had chosen. It is not a
tolerance question -- the best parameters under a fixed target need not be the
best under a two-leg bracket.

The trap in fixing it: `evaluate_folds` read `metrics.get("num_trades", 0)` and
the parity engine names that key `total_trades`. Swapping the engine in without
touching that line would have scored EVERY fold as `EMPTY_FOLD_SCORE`, so the
study would have optimised a constant and still printed a "best". The first two
tests here are that trap.
"""
import inspect
import os
import sys
import types

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.trading_framework import run_backtest as rb
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.core.nt8_parity_backtester import NT8ParityBacktester
from scripts.trading_framework.research.objective import (
    EMPTY_FOLD_SCORE, evaluate_folds)


BARS = 600


@pytest.fixture
def data():
    idx = pd.date_range("2026-01-05 09:30", periods=BARS, freq="5min", tz="UTC")
    close = 20000 + np.cumsum(np.random.default_rng(7).normal(0, 2, BARS))
    return pd.DataFrame({"open": close, "high": close + 3, "low": close - 3,
                         "close": close}, index=idx)


@pytest.fixture
def strategy(data):
    """Emits one canonical signal inside every window."""
    class S:
        def generate_signals(self, df, params):
            take = df.index[len(df) // 2:len(df) // 2 + 3]
            return pd.DataFrame({
                "signal_time": take,
                "direction": 1,
                "entry_price": df["close"].reindex(take).to_numpy(),
                "stop_price": df["close"].reindex(take).to_numpy() - 20,
                "target1_price": df["close"].reindex(take).to_numpy() + 40,
            }).reset_index(drop=True)
    return S()


@pytest.fixture
def folds():
    return [{"fold": 0, "gen_end": 400, "test_start": 200, "test_end": 400,
             "score_start": 200, "score_end": BARS}]


class SpyEngine:
    """Returns the metrics dict it was told to, and remembers its inputs."""

    def __init__(self, metrics):
        self.metrics = metrics
        self.calls = []

    def run(self, signals, data, risk_params):
        self.calls.append(dict(risk_params))
        return dict(self.metrics)


# --------------------------------------------------------------------------- #
# The trap: two engines, two names for the trade count
# --------------------------------------------------------------------------- #
def test_a_fold_scored_by_the_parity_engines_key_is_not_read_as_empty(
        strategy, data, folds):
    """`total_trades` is the parity engine's name. `.get("num_trades", 0)` made
    every one of its folds look like a fold that took no trades."""
    eng = SpyEngine({"total_trades": 5, "sharpe_ratio": 1.75})
    scores = evaluate_folds(strategy, data, {}, eng, "NQ1", folds)
    assert scores == [1.75], scores


def test_a_fold_that_really_took_no_trades_still_scores_empty(
        strategy, data, folds):
    """The negative control. Reading the other key must not make every fold
    look non-empty, which would be the same defect pointing the other way."""
    eng = SpyEngine({"total_trades": 0, "sharpe_ratio": 9.9})
    assert evaluate_folds(strategy, data, {}, eng, "NQ1", folds) == [EMPTY_FOLD_SCORE]


def test_metrics_with_no_trade_count_key_at_all_raises(strategy, data, folds):
    """"could not be measured" must not resolve to "took no trades"."""
    eng = SpyEngine({"sharpe_ratio": 1.0})
    with pytest.raises(KeyError, match="no trade-count key"):
        evaluate_folds(strategy, data, {}, eng, "NQ1", folds)


# --------------------------------------------------------------------------- #
# The execution policy reaches the search, not just the report
# --------------------------------------------------------------------------- #
def test_the_search_scores_under_the_reports_risk_params(strategy, data, folds):
    eng = SpyEngine({"total_trades": 3, "sharpe_ratio": 1.0})
    rp = {"ticker": "NQ1", "queen_bps": 10.0, "flatten_hhmm": 1545,
          "filter_lunch": False, "latest_entry_hhmm": 2359}
    evaluate_folds(strategy, data, {}, eng, "NQ1", folds, risk_params=rp)
    got = eng.calls[0]
    for k, v in rp.items():
        assert got[k] == v, k
    assert got["strict_alignment"] is True


def test_without_risk_params_the_search_still_declares_its_ticker(
        strategy, data, folds):
    """The old literal dict is the fallback, and it must keep the one field the
    parity engine refuses to guess."""
    eng = SpyEngine({"total_trades": 3, "sharpe_ratio": 1.0})
    evaluate_folds(strategy, data, {}, eng, "NQ1", folds)
    assert eng.calls[0]["ticker"] == "NQ1"


# --------------------------------------------------------------------------- #
# One constructor
# --------------------------------------------------------------------------- #
def _args(engine="nt8_parity"):
    return types.SimpleNamespace(engine=engine, ticker="NQ1", strategy="mean_reversion")


@pytest.fixture
def config():
    from scripts.trading_framework.config.config_loader import load_config
    return load_config()


def test_build_engine_returns_the_adr024_default(config):
    eng, rp = rb.build_engine(_args(), config)
    assert isinstance(eng, NT8ParityBacktester)
    assert rp["ticker"] == "NQ1"


def test_build_engine_honours_an_explicit_vectorized_choice(config):
    eng, rp = rb.build_engine(_args("vectorized"), config)
    assert isinstance(eng, VectorizedBacktester)
    assert rp["ticker"] == "NQ1", "the NQ1 multiplier fallback defect"


def _construction_sites(name):
    """Where `name(...)` is actually CALLED, by AST -- never by substring.

    A substring count read 3 for `VectorizedBacktester(` on the first run of
    this test, and all three were PROSE: the docstrings explaining the defect
    name the class that used to be constructed there. A scan that cannot tell a
    call from a comment makes documenting a fix impossible, and would have been
    deleted rather than obeyed.
    """
    import ast
    src = inspect.getsource(rb)
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == name):
            out.append(node.lineno)
    return out


def test_each_engine_is_constructed_in_exactly_one_place():
    """Two construction sites is how the two payoff functions got apart."""
    factory_src = inspect.getsource(rb.build_engine)
    factory_lines = set(range(1, len(factory_src.splitlines()) + 1))
    for name in ("NT8ParityBacktester", "VectorizedBacktester"):
        sites = _construction_sites(name)
        assert len(sites) == 1, \
            "{} is constructed at {} sites in run_backtest.py".format(name, len(sites))
    # ...and both of those sites are inside the factory.
    assert "NT8ParityBacktester(" in factory_src
    assert "VectorizedBacktester(" in factory_src


def test_the_scan_can_tell_a_call_from_the_prose_describing_one():
    """The control: prose naming a constructor must not count as one.

    Both docstrings deliberately contain the string `VectorizedBacktester()`
    while describing the fallback that was removed.
    """
    src = inspect.getsource(rb)
    assert src.count("VectorizedBacktester(") > len(
        _construction_sites("VectorizedBacktester")), \
        "no prose mention left to distinguish from a call -- the control is vacuous"


def test_the_search_does_not_construct_an_engine_of_its_own():
    """`run_optimization(engine=None)` must delegate, not invent."""
    import ast
    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(rb)))
              if isinstance(n, ast.FunctionDef) and n.name == "run_optimization")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "VectorizedBacktester" not in called, \
        "the fallback that made the search score under a different engine is back"
    assert "NT8ParityBacktester" not in called
    assert "build_engine" in called


def test_the_pipeline_passes_its_engine_into_the_search():
    src = inspect.getsource(rb.run_research_pipeline)
    assert "build_engine(args, config, rec)" in src
    assert "engine=engine" in src and "risk_params=risk_dict" in src
