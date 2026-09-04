"""Acceptance tests for `sequential_evaluation_folds`.

This helper exists because `PurgedKFold` was being used for a PARAMETER sweep,
where nothing is fitted and there is therefore no training set to purge. The
k-fold split also handed the caller the job of re-indexing signals onto each
test block, which is the step that failed silently (see
test_signal_frame_alignment.py and scripts/research/measure_cv_objective_defect.py).

Each property below is asserted with the reason it matters, because a fold
generator that returns plausible-looking dicts satisfies any test that only
checks the shape.
"""
import numpy as np
import pytest

from scripts.trading_framework.ml.walk_forward import sequential_evaluation_folds


def test_windows_do_not_overlap():
    """Overlap would double-count the same bars as independent evidence."""
    folds = sequential_evaluation_folds(100_000, n_splits=4, exit_buffer=1440, embargo=0)
    for a, b in zip(folds, folds[1:]):
        assert a["test_end"] <= b["test_start"]


def test_embargo_leaves_a_real_gap():
    """Without a gap, serial correlation at a boundary is shared by two folds."""
    folds = sequential_evaluation_folds(100_000, n_splits=3, exit_buffer=1440, embargo=500)
    gaps = [b["test_start"] - a["test_end"] for a, b in zip(folds, folds[1:])]
    assert gaps == [500, 500]


def test_zero_embargo_is_still_offered_but_produces_no_gap():
    """Control: the embargo is a caller decision, not silently imposed."""
    folds = sequential_evaluation_folds(100_000, n_splits=3, exit_buffer=1440, embargo=0)
    gaps = [b["test_start"] - a["test_end"] for a, b in zip(folds, folds[1:])]
    assert gaps == [0, 0]


def test_windows_are_equal_length():
    """VectorizedBacktester's Sharpe is built from a per-BAR series that is zero
    except at exit bars, so it scales with frame length. Unequal windows would
    make the fold scores incomparable to each other, and the objective is their
    mean."""
    for n_splits in (2, 3, 5, 7):
        folds = sequential_evaluation_folds(
            500_000, n_splits=n_splits, exit_buffer=1440, embargo=1440)
        widths = {f["test_end"] - f["test_start"] for f in folds}
        assert len(widths) == 1, (n_splits, widths)
        scored = {f["n_bars_scored"] for f in folds}
        assert len(scored) == 1, (n_splits, scored)


def test_exit_buffer_is_reserved_from_the_end_not_borrowed():
    """The last fold must get a full exit buffer.

    If the buffer were carved out of the data rather than reserved ahead of it,
    the final window's late trades would exit at the last available bar --
    truncation that reads as a real result.
    """
    n = 100_000
    folds = sequential_evaluation_folds(n, n_splits=3, exit_buffer=1440, embargo=0)
    last = folds[-1]
    assert last["score_end"] <= n
    assert last["score_end"] - last["test_end"] == 1440
    for f in folds:
        assert f["score_end"] - f["test_end"] == 1440


def test_generator_horizon_never_passes_the_window_end():
    """`gen_end == test_end` is the causality boundary: a signal inside the
    window cannot have been informed by a bar after it."""
    folds = sequential_evaluation_folds(100_000, n_splits=4, exit_buffer=1440, embargo=100)
    for f in folds:
        assert f["gen_end"] == f["test_end"]
        assert f["score_start"] == f["test_start"]
        assert f["score_end"] > f["test_end"]


def test_refuses_rather_than_returning_degenerate_folds():
    """A one-bar window also satisfies every structural property above.

    This is the case that makes the other assertions non-vacuous: too little
    data must raise, not quietly yield windows too small to measure anything.
    """
    with pytest.raises(ValueError, match="not enough bars"):
        sequential_evaluation_folds(1_000, n_splits=3, exit_buffer=1440)
    with pytest.raises(ValueError, match="not enough bars"):
        sequential_evaluation_folds(1_500, n_splits=10, exit_buffer=1440, embargo=1440)


def test_rejects_nonsense_arguments():
    with pytest.raises(ValueError, match="n_splits"):
        sequential_evaluation_folds(100_000, n_splits=0)
    with pytest.raises(ValueError, match=">= 0"):
        sequential_evaluation_folds(100_000, exit_buffer=-1)
    with pytest.raises(ValueError, match=">= 0"):
        sequential_evaluation_folds(100_000, embargo=-1)


def test_returns_a_list_so_it_can_be_iterated_twice():
    """Optuna evaluates the same folds once per trial. A generator would yield
    nothing on trial 2 and every fold list would silently come back empty."""
    folds = sequential_evaluation_folds(100_000, n_splits=3, exit_buffer=1440)
    assert isinstance(folds, list)
    assert len(list(folds)) == 3
    assert len(list(folds)) == 3


def test_single_split_is_a_plain_holdout():
    folds = sequential_evaluation_folds(100_000, n_splits=1, exit_buffer=1440)
    assert len(folds) == 1
    assert folds[0]["test_start"] == 0
    assert folds[0]["score_end"] == 100_000
