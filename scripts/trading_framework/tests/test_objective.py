"""Acceptance tests for the shared CV objective, the grid precheck and the
causality probe.

Both prechecks are detectors, and a detector that fires on everything passes
every positive test ever written for it. So each one is tested against:

  * a synthetic strategy built to exhibit the defect  -> must FIRE;
  * a synthetic strategy built not to               -> must NOT fire;
  * a degenerate input where the check could pass vacuously -> must say so.

The third case is the one that matters. `probe_causality` compared signal frames
before a cutoff, and on a strategy that emitted NO signals there it compared
empty to empty and reported `causal=True` -- a green with no reachable red.
Measured on six_am_reversal over the first half of 2023.
"""
import numpy as np
import pandas as pd
import pytest

from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.research.objective import (
    EMPTY_FOLD_SCORE,
    assert_grid_is_live,
    build_folds,
    evaluate_folds,
    grid_corners,
    probe_causality,
    probe_grid,
    suggest_from_grid,
)


def _frame(periods=20_000, start="2020-01-01"):
    idx = pd.date_range(start, periods=periods, freq="1min")
    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.normal(0, 0.1, periods))
    df = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                       "close": close, "volume": 1000.0}, index=idx)
    df["returns"] = df["close"].pct_change().fillna(0.0)
    return df


def _sig_frame(df, positions, stop=5.0, target=5.0):
    px = df["close"].to_numpy()[positions]
    return pd.DataFrame({
        "signal_time": df.index[positions],
        "direction": "long",
        "entry_price": px,
        "stop_price": px - stop,
        "target1_price": px + target,
    })


class _Sensitive:
    """Params change WHICH bars signal: the grid is connected to the output."""

    def get_param_grid(self):
        return {"every": ("int", 200, 400), "stop": ("float", 2.0, 10.0)}

    def generate_signals(self, df, params):
        every = int(params.get("every", 300))
        pos = np.arange(every, len(df), every)
        return _sig_frame(df, pos, stop=float(params.get("stop", 5.0)))


class _ExitOnly:
    """Params change ONLY stop/target prices, never entry timing.

    A legitimate shape -- `sl_atr_mult` and `tp_r_mult` behave exactly like this
    -- and the reason the grid digest must cover the whole frame rather than
    signal_time alone.
    """

    def get_param_grid(self):
        return {"stop": ("float", 2.0, 20.0)}

    def generate_signals(self, df, params):
        pos = np.arange(300, len(df), 300)
        return _sig_frame(df, pos, stop=float(params.get("stop", 5.0)))


class _IgnoresParams:
    """Declares a grid and ignores it. The shipped defect, in miniature."""

    def get_param_grid(self):
        return {"min_dist": ("float", 0.0005, 0.003),
                "filter_high_vol": ("categorical", [True, False])}

    def generate_signals(self, df, params):
        return _sig_frame(df, np.arange(300, len(df), 300))


class _EmitsNothing:
    def get_param_grid(self):
        return {"x": ("int", 1, 5)}

    def generate_signals(self, df, params):
        return pd.DataFrame(columns=["signal_time", "direction", "entry_price",
                                     "stop_price", "target1_price"])


class _NonCausal:
    """Emits a signal at bar i only if bar i+look closed higher.

    Textbook lookahead: the decision at i is a function of a bar after i, so
    appending future bars retroactively creates signals in the past. Signals are
    dense (every 10 bars) so that some sit within `look` of any cutoff -- see
    `test_causality_probe_can_miss_sparse_lookahead` for why that matters.
    """

    def __init__(self, stride=10):
        self.stride = stride

    def get_param_grid(self):
        return {"look": ("int", 20, 80)}

    def generate_signals(self, df, params):
        look = int(params.get("look", 50))
        c = df["close"].to_numpy()
        pos = [i for i in range(300, len(df) - 1, self.stride)
               if i + look < len(c) and c[i + look] > c[i]]
        if not pos:
            return _sig_frame(df, np.array([], dtype=int))
        return _sig_frame(df, np.array(pos))


class _Raises:
    def get_param_grid(self):
        return {"x": ("int", 1, 5)}

    def generate_signals(self, df, params):
        raise RuntimeError("boom")


# --------------------------------------------------------------------------
# Grid precheck -- must FIRE
# --------------------------------------------------------------------------
def test_grid_precheck_catches_a_strategy_that_ignores_its_params():
    r = probe_grid(_IgnoresParams(), _frame(), _IgnoresParams().get_param_grid())
    assert r["live"] is False
    assert "does NOT affect this strategy" in r["reason"]


def test_grid_precheck_catches_a_strategy_that_emits_nothing():
    r = probe_grid(_EmitsNothing(), _frame(), _EmitsNothing().get_param_grid())
    assert r["live"] is False
    assert "ZERO signals at every grid corner" in r["reason"]
    assert r["signalCounts"] == [0, 0, 0]


def test_grid_precheck_catches_an_empty_grid():
    r = probe_grid(_Sensitive(), _frame(), {})
    assert r["live"] is False
    assert "EMPTY parameter grid" in r["reason"]


def test_grid_precheck_reports_a_raising_corner_rather_than_propagating():
    r = probe_grid(_Raises(), _frame(), _Raises().get_param_grid())
    assert r["live"] is False
    assert "raised at a grid corner" in r["reason"]


def test_assert_grid_is_live_raises_on_a_dead_grid():
    with pytest.raises(ValueError, match="grid precheck FAILED"):
        assert_grid_is_live(_IgnoresParams(), _frame(),
                            _IgnoresParams().get_param_grid())


# --------------------------------------------------------------------------
# Grid precheck -- must NOT fire (the load-bearing controls)
# --------------------------------------------------------------------------
def test_grid_precheck_passes_a_live_grid():
    r = probe_grid(_Sensitive(), _frame(), _Sensitive().get_param_grid())
    assert r["live"] is True
    assert len(set(r["digests"])) > 1


def test_grid_precheck_passes_an_exit_only_grid():
    """Control for the digest design: identical signal COUNT and identical
    signal TIMES, different stops. Comparing either alone would refuse a
    perfectly good grid."""
    s = _ExitOnly()
    r = probe_grid(s, _frame(), s.get_param_grid())
    assert r["live"] is True
    assert len(set(r["signalCounts"])) == 1, "counts must be identical here"
    assert len(set(r["digests"])) == 3, "yet the frames must differ"


def test_assert_grid_is_live_returns_the_probe_on_success():
    probe = assert_grid_is_live(_Sensitive(), _frame(),
                                _Sensitive().get_param_grid())
    assert probe["live"] is True
    assert probe["barsProbed"] > 0


# --------------------------------------------------------------------------
# Causality probe
# --------------------------------------------------------------------------
def test_causality_probe_catches_real_lookahead():
    r = probe_causality(_NonCausal(), _frame(), {"look": 50})
    assert r["checked"] is True
    assert r["causal"] is False
    assert "LOOKAHEAD" in r["reason"]
    assert any(not c["identical"] for c in r["perCutoff"])


def test_causality_probe_passes_a_causal_strategy():
    """Control: it must not fire on a strategy that only looks backwards."""
    r = probe_causality(_Sensitive(), _frame(), {"every": 300, "stop": 5.0})
    assert r["checked"] is True
    assert r["causal"] is True
    assert r["vacuous"] is False
    assert r["informativeCutoffs"] >= 1
    assert all(c["identical"] for c in r["perCutoff"])


def test_causality_probe_can_miss_sparse_lookahead():
    """DOCUMENTED BLIND SPOT, not an aspiration.

    A cutoff can only expose a lookahead of horizon `h` if some signal sits
    within `h` bars BEFORE it; otherwise every signal's future is already inside
    the truncated frame and the two runs agree. This fixture is genuinely
    non-causal -- 50-bar lookahead -- but signals only every 3000 bars, so no
    signal lands near any cutoff and the probe reports causal.

    This test exists so the limitation is a recorded fact rather than something
    rediscovered later by trusting a pass. It is why `probe_causality` uses
    several cutoffs and why its result records which ones it used: a pass is
    evidence that no lookahead was EXPOSED, not proof that none exists.
    """
    r = probe_causality(_NonCausal(stride=3000), _frame(), {"look": 50})
    assert r["checked"] is True
    assert r["causal"] is True, "the blind spot still exists; update the docstring"
    assert r["informativeCutoffs"] >= 1


def test_denser_signals_close_the_blind_spot():
    """Control for the above: same lookahead, denser signals -> caught."""
    r = probe_causality(_NonCausal(stride=20), _frame(), {"look": 50})
    assert r["causal"] is False


def test_causality_probe_reports_vacuous_rather_than_passing():
    """Regression: with no signals before the cutoff, 'empty == empty' passed.

    Measured on six_am_reversal over the first half of 2023: 0 signals before
    the cutoff, reported causal=True. A green with no reachable red.
    """
    r = probe_causality(_EmitsNothing(), _frame(), {"x": 1})
    assert r["checked"] is True
    assert r["vacuous"] is True
    assert r["causal"] is None
    assert "UNTESTED" in r["reason"]
    assert r["informativeCutoffs"] == 0


def test_causality_probe_does_not_raise_on_a_raising_strategy():
    r = probe_causality(_Raises(), _frame(), {"x": 1})
    assert r["checked"] is False
    assert r["causal"] is None
    assert "raised during the causality probe" in r["reason"]


def test_causality_probe_refuses_a_frame_too_short_to_split():
    r = probe_causality(_Sensitive(), _frame(periods=50), {"every": 300})
    assert r["checked"] is False
    assert "too short" in r["reason"]


def test_causality_probe_uses_more_than_one_cutoff():
    """A single cutoff is what made the blind spot above so easy to hit."""
    r = probe_causality(_Sensitive(), _frame(), {"every": 300, "stop": 5.0})
    assert len(r["cutoffsTried"]) >= 3
    assert len(r["perCutoff"]) == len(r["cutoffsTried"])


# --------------------------------------------------------------------------
# evaluate_folds
# --------------------------------------------------------------------------
def test_evaluate_folds_scores_each_window_and_never_raises_on_alignment():
    df = _frame(periods=20_000)
    folds = build_folds(len(df), n_splits=2)
    scores = evaluate_folds(_Sensitive(), df, {"every": 300, "stop": 5.0},
                            VectorizedBacktester(), "NQ1", folds)
    assert len(scores) == len(folds)
    assert all(np.isfinite(s) for s in scores)


def test_evaluate_folds_penalises_an_empty_fold_below_zero():
    """A fold with no trades must not outscore a fold that lost money."""
    df = _frame(periods=20_000)
    folds = build_folds(len(df), n_splits=2)
    scores = evaluate_folds(_EmitsNothing(), df, {"x": 1},
                            VectorizedBacktester(), "NQ1", folds)
    assert scores == [EMPTY_FOLD_SCORE] * len(folds)
    assert EMPTY_FOLD_SCORE < 0.0


def test_evaluate_folds_uses_strict_alignment(monkeypatch):
    """The framing rules are only enforced if strict_alignment reaches the engine."""
    df = _frame(periods=20_000)
    folds = build_folds(len(df), n_splits=2)
    seen = []

    engine = VectorizedBacktester()
    real_run = engine.run

    def spy(signals, data, risk_params):
        seen.append(dict(risk_params))
        return real_run(signals, data, risk_params)

    engine.run = spy
    evaluate_folds(_Sensitive(), df, {"every": 300, "stop": 5.0},
                   engine, "ES1", folds)
    assert seen, "engine was never called"
    for rp in seen:
        assert rp["strict_alignment"] is True
        assert rp["ticker"] == "ES1", "ticker must be threaded, not defaulted"


def test_evaluate_folds_scores_only_in_window_signals():
    """Signals from earlier windows must not be counted against a later one."""
    df = _frame(periods=20_000)
    folds = build_folds(len(df), n_splits=2)
    engine = VectorizedBacktester()
    counts = []
    real_run = engine.run

    def spy(signals, data, risk_params):
        counts.append(len(signals))
        return real_run(signals, data, risk_params)

    engine.run = spy
    evaluate_folds(_Sensitive(), df, {"every": 300, "stop": 5.0},
                   engine, "NQ1", folds)
    # each window is ~the same width, so the per-window signal counts must be
    # comparable -- not growing with the cumulative generation frame
    assert max(counts) < 2 * min(counts), counts


# --------------------------------------------------------------------------
# grid helpers
# --------------------------------------------------------------------------
def test_grid_corners_spans_int_float_and_categorical():
    grid = {"i": ("int", 10, 50), "f": ("float", 0.0, 1.0),
            "c": ("categorical", ["a", "b", "c"])}
    low, mid, high = grid_corners(grid)
    assert (low["i"], high["i"]) == (10, 50)
    assert (low["f"], high["f"]) == (0.0, 1.0)
    assert (low["c"], high["c"]) == ("a", "c")
    assert 10 < mid["i"] < 50


def test_suggest_from_grid_refuses_a_spec_it_cannot_read():
    class _T:
        pass

    with pytest.raises(ValueError, match="Unsupported param grid spec"):
        suggest_from_grid(_T(), "k", object())


def test_suggest_from_grid_refuses_a_truncated_numeric_spec():
    class _T:
        pass

    with pytest.raises(ValueError, match=r"must be \('int', low, high\)"):
        suggest_from_grid(_T(), "k", ("int",))
    with pytest.raises(ValueError, match=r"must be \('float', low, high\)"):
        suggest_from_grid(_T(), "k", ("float",))
