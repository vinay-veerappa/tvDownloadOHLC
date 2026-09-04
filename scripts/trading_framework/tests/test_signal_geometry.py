"""Acceptance tests for the signal-geometry check.

WHAT IT PROTECTS. A long whose stop sits ABOVE its entry is not a risky trade,
it is an arithmetically impossible one: the "stop" is hit immediately and books a
PROFIT. Measured 2026-09-04 on NQ1 `mean_reversion` over 2024-01-01..2026-03-31,
106 of 702 signals (15.1%) were shaped that way, and of the 38 resulting trades
**36 exited with reason "Stop Loss" for an average of +48.6 points** (max
+439.75). The run reported win rate 76.3%, profit factor 31.64 and Sharpe 9.38 --
numbers that look like a discovery and were produced by profitable stop-losses.

Every rule below has a negative control, because a geometry check that drops
everything satisfies any test that only asserts the bad case was caught.
"""
import numpy as np
import pandas as pd
import pytest

from scripts.trading_framework.core.backtest_engine import (
    VectorizedBacktester,
    validate_signal_geometry,
)


def _sig(rows):
    """rows: list of (direction, entry, stop, target)."""
    idx = pd.date_range("2020-01-01", periods=len(rows), freq="5min")
    return pd.DataFrame({
        "signal_time": idx,
        "direction": [r[0] for r in rows],
        "entry_price": [r[1] for r in rows],
        "stop_price": [r[2] for r in rows],
        "target1_price": [r[3] for r in rows],
    })


# --------------------------------------------------------------------------
# must FIRE
# --------------------------------------------------------------------------
def test_long_with_stop_above_entry_is_refused():
    """The exact shape that produced profitable stop-losses."""
    kept, rep = validate_signal_geometry(_sig([("long", 100.0, 105.0, 110.0)]), {})
    assert len(kept) == 0
    assert rep["dropped_stop_wrong_side"] == 1


def test_short_with_stop_below_entry_is_refused():
    kept, rep = validate_signal_geometry(_sig([("short", 100.0, 95.0, 90.0)]), {})
    assert len(kept) == 0
    assert rep["dropped_stop_wrong_side"] == 1


def test_target_on_the_wrong_side_is_refused():
    rows = [("long", 100.0, 95.0, 98.0), ("short", 100.0, 105.0, 102.0)]
    kept, rep = validate_signal_geometry(_sig(rows), {})
    assert len(kept) == 0
    assert rep["dropped_target_wrong_side"] == 2


def test_sub_tick_stop_is_refused():
    """12 of the 702 measured signals had a stop under one NQ tick.

    A stop 0.01 points from entry is not a price on an instrument that trades in
    0.25 increments.
    """
    kept, rep = validate_signal_geometry(
        _sig([("long", 20000.0, 19999.99, 20010.0)]), {"tick_size": 0.25})
    assert len(kept) == 0
    assert rep["dropped_stop_sub_tick"] == 1


def test_non_finite_and_non_positive_prices_are_refused():
    rows = [("long", np.nan, 95.0, 110.0),
            ("long", 100.0, np.inf, 110.0),
            ("long", 100.0, 95.0, np.nan),
            ("long", 0.0, -5.0, 10.0)]
    kept, rep = validate_signal_geometry(_sig(rows), {})
    assert len(kept) == 0
    assert rep["dropped_non_finite"] == 4


def test_strict_geometry_raises_and_names_the_counts():
    with pytest.raises(ValueError, match="books a PROFIT"):
        validate_signal_geometry(_sig([("long", 100.0, 105.0, 110.0)]),
                                 {"strict_geometry": True})


def test_drop_counts_sum_to_the_number_dropped():
    """Each signal is attributed to the FIRST rule it broke, so a single bad
    signal cannot inflate three counters and make the report unreadable."""
    rows = [("long", 100.0, 105.0, 110.0),     # stop wrong side
            ("long", 100.0, 95.0, 98.0),       # target wrong side
            ("long", 100.0, 99.99, 110.0),     # sub-tick
            ("long", np.nan, 95.0, 110.0),     # non-finite
            ("long", 100.0, 95.0, 110.0)]      # good
    kept, rep = validate_signal_geometry(_sig(rows), {"tick_size": 0.25})
    dropped = rep["signals_in"] - rep["signals_kept"]
    assert dropped == 4
    assert (rep["dropped_stop_wrong_side"] + rep["dropped_target_wrong_side"]
            + rep["dropped_stop_sub_tick"] + rep["dropped_non_finite"]) == dropped
    assert len(kept) == 1


# --------------------------------------------------------------------------
# must NOT fire -- the controls
# --------------------------------------------------------------------------
def test_well_formed_signals_pass_untouched():
    rows = [("long", 100.0, 95.0, 110.0), ("short", 100.0, 105.0, 90.0)]
    kept, rep = validate_signal_geometry(_sig(rows), {})
    assert len(kept) == 2
    assert rep["signals_kept"] == 2
    assert rep["dropped_stop_wrong_side"] == 0


def test_a_very_wide_stop_is_not_a_geometry_error():
    """Only the SIDE and a one-tick minimum are checked. How far away a stop
    sits is a strategy decision, not an arithmetic impossibility."""
    kept, _ = validate_signal_geometry(
        _sig([("long", 20000.0, 15000.0, 20010.0)]), {})
    assert len(kept) == 1


def test_a_stop_exactly_one_tick_away_is_accepted():
    """Boundary: the rule is `>= tick`, not `> tick`."""
    kept, _ = validate_signal_geometry(
        _sig([("long", 20000.0, 19999.75, 20010.0)]), {"tick_size": 0.25})
    assert len(kept) == 1


def test_mixed_case_direction_is_handled():
    """`direction` arrives as 'Long'/'LONG' from some producers."""
    rows = [("Long", 100.0, 95.0, 110.0), ("SHORT", 100.0, 105.0, 90.0)]
    kept, _ = validate_signal_geometry(_sig(rows), {})
    assert len(kept) == 2


def test_an_empty_frame_is_not_an_error():
    empty = _sig([]).iloc[0:0]
    kept, rep = validate_signal_geometry(empty, {})
    assert len(kept) == 0
    assert rep["signals_in"] == 0
    assert rep["dropped_stop_wrong_side"] == 0


# --------------------------------------------------------------------------
# the engine actually applies it, and reports it
# --------------------------------------------------------------------------
def _frame(periods=500):
    idx = pd.date_range("2020-01-01", periods=periods, freq="1min")
    rng = np.random.default_rng(5)
    close = 100 + np.cumsum(rng.normal(0, 0.1, periods))
    df = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                       "close": close, "volume": 1000.0}, index=idx)
    df["returns"] = df["close"].pct_change().fillna(0.0)
    return df


def test_engine_drops_wrong_sided_signals_and_reports_them():
    df = _frame()
    px = df["close"].to_numpy()
    good = pd.DataFrame({
        "signal_time": df.index[[10, 100]],
        "direction": "long",
        "entry_price": px[[10, 100]],
        "stop_price": px[[10, 100]] - 2.0,
        "target1_price": px[[10, 100]] + 2.0,
    })
    bad = pd.DataFrame({
        "signal_time": df.index[[200, 300]],
        "direction": "long",
        "entry_price": px[[200, 300]],
        "stop_price": px[[200, 300]] + 2.0,   # ABOVE entry
        "target1_price": px[[200, 300]] + 4.0,
    })
    res = VectorizedBacktester().run(pd.concat([good, bad], ignore_index=True),
                                     df, {"ticker": "NQ1", "tick_size": 0.25})
    geom = res["signal_alignment"]["geometry"]
    assert geom["signals_in"] == 4
    assert geom["signals_kept"] == 2
    assert geom["dropped_stop_wrong_side"] == 2
    assert res["num_trades"] == 2


def test_engine_control_all_good_signals_survive():
    df = _frame()
    px = df["close"].to_numpy()
    sig = pd.DataFrame({
        "signal_time": df.index[[10, 100, 200]],
        "direction": "long",
        "entry_price": px[[10, 100, 200]],
        "stop_price": px[[10, 100, 200]] - 2.0,
        "target1_price": px[[10, 100, 200]] + 2.0,
    })
    res = VectorizedBacktester().run(sig, df, {"ticker": "NQ1", "tick_size": 0.25})
    geom = res["signal_alignment"]["geometry"]
    assert geom["signals_kept"] == 3
    assert geom["dropped_stop_wrong_side"] == 0
    assert res["num_trades"] == 3


def test_engine_returns_a_readable_null_when_every_signal_is_refused():
    """A frame of entirely impossible signals must not look like 'no signals'."""
    df = _frame()
    px = df["close"].to_numpy()
    sig = pd.DataFrame({
        "signal_time": df.index[[10, 100]],
        "direction": "long",
        "entry_price": px[[10, 100]],
        "stop_price": px[[10, 100]] + 2.0,
        "target1_price": px[[10, 100]] + 4.0,
    })
    res = VectorizedBacktester().run(sig, df, {"ticker": "NQ1"})
    align = res["signal_alignment"]
    assert res["num_trades"] == 0
    assert align["signals_in"] == 2
    assert "refused by the geometry check" in align["note"]
    assert align["geometry"]["dropped_stop_wrong_side"] == 2
