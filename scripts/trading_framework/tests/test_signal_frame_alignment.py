"""Acceptance tests for signal/frame alignment in VectorizedBacktester.

WHAT THIS PROTECTS. `Index.get_indexer(..., method='bfill')` snaps a missing
timestamp forward to the next available bar with no distance limit, returning -1
only when no later bar exists at all. The engine used that result directly and
kept everything that was not -1. Consequence, measured 2026-09-04: signals
generated on a TRAIN fold and scored against a TEST fold frame all mapped to
index 0 of the test frame and all passed the `!= -1` check, so the entire signal
set was evaluated as if it had entered on the first bar of the test window.
`ResearchLifecycleRunner._optimize_params` did exactly that, which made its
"purged cross-validation" objective a degenerate function that Optuna then
maximised over.

Every positive test below has a NEGATIVE CONTROL beside it, because a rule that
drops everything passes every "the bad case was caught" assertion ever written
for it. The controls are the load-bearing half: they prove the benign cases --
an exactly-matched frame, and a timestamp falling between two adjacent bars --
still go through untouched.
"""
import numpy as np
import pandas as pd
import pytest

from scripts.trading_framework.core.backtest_engine import VectorizedBacktester


def _frame(start="2020-01-01 00:00", periods=600, freq="1min", price=100.0):
    idx = pd.date_range(start, periods=periods, freq=freq)
    rng = np.random.default_rng(7)
    close = price + np.cumsum(rng.normal(0, 0.1, periods))
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1000.0,
        },
        index=idx,
    )
    df["returns"] = df["close"].pct_change().fillna(0.0)
    return df


def _signals(times, df, direction="long"):
    px = df["close"].reindex(times, method="ffill").to_numpy()
    return pd.DataFrame(
        {
            "signal_time": pd.to_datetime(list(times)),
            "direction": direction,
            "entry_price": px,
            "stop_price": px - 5.0,
            "target1_price": px + 5.0,
        }
    )


# --------------------------------------------------------------------------
# The defect itself
# --------------------------------------------------------------------------
def test_train_fold_signals_are_not_collapsed_onto_test_bar_zero():
    """The exact shape that produced the degenerate CV objective."""
    full = _frame(periods=600)
    train, test = full.iloc[:400], full.iloc[400:]
    sig = _signals(train.index[[0, 50, 100, 200]], train)

    res = VectorizedBacktester().run(sig, test, {"ticker": "NQ1"})
    align = res["signal_alignment"]

    assert align["signals_in"] == 4
    assert align["signals_kept"] == 0, "pre-frame signals must not execute at bar 0"
    assert align["dropped_before_frame_start"] == 4
    assert res["num_trades"] == 0


def test_the_last_train_bar_is_admitted_by_the_one_bar_tolerance():
    """A deliberate, documented consequence of bounding in time, not membership.

    A signal on the final TRAIN bar sits exactly one bar before the test frame
    starts, so it is indistinguishable -- by the time rule -- from a benign
    sub-bar snap, and it is kept. That is correct for a caller replaying signals
    onto an adjacent frame and WRONG for cross-validation, where a train signal
    reaching the test window is a leak of exactly one bar.

    The resolution is not to tighten the tolerance (that would break the
    legitimate sub-bar case in the control above) but for CV callers to pass
    `strict_alignment=True`, which refuses any drop at all and therefore refuses
    the whole mismatched-frame construction before this edge can arise.
    """
    full = _frame(periods=600)
    train, test = full.iloc[:400], full.iloc[400:]
    sig = _signals([train.index[-1]], train)

    res = VectorizedBacktester().run(sig, test, {"ticker": "NQ1"})
    assert res["signal_alignment"]["signals_kept"] == 1
    assert res["signal_alignment"]["snapped_within_tolerance"] == 1

    with pytest.raises(ValueError, match="strict_alignment"):
        # ...and the CV posture still refuses it, because the frame it was
        # generated on is not the frame it is being scored on.
        VectorizedBacktester().run(
            _signals(train.index[[0, 399]], train), test,
            {"ticker": "NQ1", "strict_alignment": True},
        )


def test_raw_get_indexer_would_still_have_kept_them():
    """Pins the underlying pandas behaviour this test exists to defend against.

    If a future pandas returns -1 for out-of-range bfill lookups, this test goes
    red and the guard above becomes redundant -- which is worth being told about
    rather than discovering by inference.
    """
    full = _frame(periods=600)
    train, test = full.iloc[:400], full.iloc[400:]
    raw = test.index.get_indexer(train.index[[0, 50, 399]], method="bfill")
    assert (raw == 0).all(), "bfill still snaps pre-frame timestamps to bar 0"
    assert (raw != -1).all(), "the old `!= -1` validity check still passes them"


def test_strict_alignment_raises_and_names_the_cause():
    full = _frame(periods=600)
    train, test = full.iloc[:400], full.iloc[400:]
    sig = _signals(train.index[[0, 50, 100]], train)

    with pytest.raises(ValueError, match="strict_alignment"):
        VectorizedBacktester().run(
            sig, test, {"ticker": "NQ1", "strict_alignment": True}
        )


# --------------------------------------------------------------------------
# NEGATIVE CONTROLS -- the rule must not fire on legitimate input
# --------------------------------------------------------------------------
def test_matched_frame_keeps_every_signal():
    """Control: the overwhelmingly common case must be untouched."""
    df = _frame(periods=600)
    sig = _signals(df.index[[10, 100, 200, 300, 400]], df)

    res = VectorizedBacktester().run(sig, df, {"ticker": "NQ1"})
    align = res["signal_alignment"]

    assert align["signals_in"] == 5
    assert align["signals_kept"] == 5
    assert align["dropped_before_frame_start"] == 0
    assert align["dropped_snap_too_far"] == 0
    assert align["snapped_within_tolerance"] == 0
    assert res["num_trades"] == 5


def test_sub_bar_timestamp_snaps_forward_and_is_kept():
    """Control: a signal_time between two adjacent bars is benign.

    A 5m-derived signal executed on a 1m frame, or a timestamp carrying seconds,
    lands strictly inside one bar. Executing it on the next bar is correct and
    must not be treated as a frame mismatch -- but it IS counted, so a caller
    can see it happened.
    """
    df = _frame(periods=600)
    times = [df.index[100] + pd.Timedelta(seconds=30),
             df.index[200] + pd.Timedelta(seconds=45)]
    sig = _signals(times, df)

    res = VectorizedBacktester().run(sig, df, {"ticker": "NQ1"})
    align = res["signal_alignment"]

    assert align["signals_kept"] == 2
    assert align["snapped_within_tolerance"] == 2
    assert align["dropped_snap_too_far"] == 0


def test_session_gap_snap_beyond_one_bar_is_dropped():
    """The bound is in TIME, not bars.

    Between two adjacent bars there are no other bars, so bfill always lands
    exactly one bar forward and a bar-count limit can never bind. This frame has
    a 4-hour hole; a signal inside the hole is still "one bar" from the next
    print but four hours late, which is not an executable fill.
    """
    a = _frame(start="2020-01-01 09:00", periods=60)
    b = _frame(start="2020-01-01 14:00", periods=60)
    df = pd.concat([a, b])

    inside_gap = pd.Timestamp("2020-01-01 11:00")
    assert df.index.get_indexer([inside_gap], method="bfill")[0] == 60
    sig = _signals([inside_gap], df)

    res = VectorizedBacktester().run(sig, df, {"ticker": "NQ1"})
    align = res["signal_alignment"]

    assert align["dropped_snap_too_far"] == 1
    assert align["signals_kept"] == 0


def test_explicit_tolerance_can_admit_the_gap():
    """The bound is a policy, not a law -- a caller may widen it deliberately."""
    a = _frame(start="2020-01-01 09:00", periods=60)
    b = _frame(start="2020-01-01 14:00", periods=60)
    df = pd.concat([a, b])
    sig = _signals([pd.Timestamp("2020-01-01 11:00")], df)

    res = VectorizedBacktester().run(
        sig, df, {"ticker": "NQ1", "max_snap_seconds": 6 * 3600}
    )
    assert res["signal_alignment"]["signals_kept"] == 1


def test_signals_past_frame_end_are_dropped_and_counted_separately():
    df = _frame(periods=600)
    late = [df.index[-1] + pd.Timedelta(minutes=10)]
    sig = _signals([df.index[100]] + late, df)
    sig.loc[1, "entry_price"] = float(df["close"].iloc[-1])
    sig.loc[1, "stop_price"] = sig.loc[1, "entry_price"] - 5.0
    sig.loc[1, "target1_price"] = sig.loc[1, "entry_price"] + 5.0

    res = VectorizedBacktester().run(sig, df, {"ticker": "NQ1"})
    align = res["signal_alignment"]

    assert align["dropped_past_frame_end"] == 1
    assert align["dropped_before_frame_start"] == 0
    assert align["signals_kept"] == 1


# --------------------------------------------------------------------------
# The parallel hazard on the raw-vectorized path
# --------------------------------------------------------------------------
def test_raw_vectorized_refuses_a_mismatched_index():
    full = _frame(periods=600)
    train, test = full.iloc[:400], full.iloc[400:]
    s = pd.Series(0.0, index=train.index)
    s.iloc[[10, 100]] = 1.0

    with pytest.raises(ValueError, match="share one index"):
        VectorizedBacktester().run(s, test, {"ticker": "NQ1"})


def test_raw_vectorized_accepts_a_matched_index():
    """Control: the guard must not break the path it protects."""
    df = _frame(periods=600)
    s = pd.Series(0.0, index=df.index)
    s.iloc[[10, 100, 200]] = 1.0

    res = VectorizedBacktester().run(s, df, {"ticker": "NQ1"})
    assert not np.isnan(res["sharpe_ratio"])
    assert res["num_trades"] > 0


def test_raw_vectorized_mismatch_would_have_returned_nan_not_raised():
    """Pins WHY the guard exists: the failure mode was a number, not a crash."""
    full = _frame(periods=600)
    train, test = full.iloc[:400], full.iloc[400:]
    s = pd.Series(0.0, index=train.index)
    s.iloc[[10, 100]] = 1.0

    # the multiply the guard now prevents
    silent = s.shift(1).fillna(0) * test["returns"]
    assert silent.isna().any(), "index-aligned multiply still yields NaN"
