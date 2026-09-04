"""Tests for `read_parquet_tail`.

Two call sites (init_chart_data, handle_history) wanted a small tail and were decoding
the entire file to get it - ~598,000 rows to keep 1,500, for 27 symbols, at startup.
Parquet can only skip whole ROW GROUPS, and these files were written as a single group,
so there was nothing to skip to.

The correctness bar is exact: a tail read must return precisely what a full read followed
by .tail() returns. If it silently returned a different slice, the in-memory window and
every /history response would be wrong with no error anywhere.
"""

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from scripts.streaming.parquet_io import (
    CANDLE_COLS,
    PARQUET_ROW_GROUP_SIZE,
    read_parquet_tail,
)


@pytest.fixture(scope="module")
def frame():
    n = 120_000
    t0 = 1_780_000_000_000
    return pd.DataFrame({
        "time": t0 + np.arange(n, dtype=np.int64) * 60_000,
        "open": np.arange(n, dtype=float) + 0.25,
        "high": np.arange(n, dtype=float) + 1.0,
        "low": np.arange(n, dtype=float) - 1.0,
        "close": np.arange(n, dtype=float) + 0.5,
        "volume": np.arange(n, dtype=np.int64),
        # Derived string column that neither caller needs - the expensive one to decode.
        "timestamp": pd.to_datetime(t0 + np.arange(n) * 60_000, unit="ms", utc=True)
                       .strftime("%Y-%m-%d %H:%M:%S+00:00"),
    })


@pytest.fixture(scope="module")
def one_group(tmp_path_factory, frame):
    """How every file on disk is written TODAY - a single row group."""
    p = tmp_path_factory.mktemp("pq") / "one.parquet"
    frame.to_parquet(p, index=False)
    assert pq.ParquetFile(p).num_row_groups == 1
    return str(p)


@pytest.fixture(scope="module")
def many_groups(tmp_path_factory, frame):
    """How files are written after this change."""
    p = tmp_path_factory.mktemp("pq") / "many.parquet"
    frame.to_parquet(p, index=False, row_group_size=PARQUET_ROW_GROUP_SIZE)
    assert pq.ParquetFile(p).num_row_groups > 1
    return str(p)


@pytest.mark.parametrize("n", [1, 2, 100, 1_500, 50_000, 50_001])
def test_tail_matches_a_full_read_on_a_single_group_file(one_group, frame, n):
    got = read_parquet_tail(one_group, n, columns=CANDLE_COLS).tail(n).reset_index(drop=True)
    assert got.equals(frame[CANDLE_COLS].tail(n).reset_index(drop=True))


@pytest.mark.parametrize("n", [1, 2, 100, 1_500, 50_000, 50_001, 119_999])
def test_tail_matches_a_full_read_on_a_multi_group_file(many_groups, frame, n):
    got = read_parquet_tail(many_groups, n, columns=CANDLE_COLS).tail(n).reset_index(drop=True)
    assert got.equals(frame[CANDLE_COLS].tail(n).reset_index(drop=True))


def test_the_two_file_shapes_agree(one_group, many_groups):
    """Row-group chunking must not change what is read. Files convert lazily on their
    next write, so both shapes are live at once and must be indistinguishable."""
    a = read_parquet_tail(one_group, 1_500, columns=CANDLE_COLS).tail(1_500).reset_index(drop=True)
    b = read_parquet_tail(many_groups, 1_500, columns=CANDLE_COLS).tail(1_500).reset_index(drop=True)
    assert a.equals(b)


def test_asking_for_more_rows_than_exist_returns_everything(many_groups, frame):
    got = read_parquet_tail(many_groups, 10_000_000, columns=CANDLE_COLS)
    assert len(got) == len(frame)


def test_it_decodes_fewer_rows_than_the_file_holds(many_groups, frame):
    """The whole point. Without this the function could satisfy every equality test
    above by simply reading everything - which is exactly the behaviour being removed."""
    got = read_parquet_tail(many_groups, 1_500, columns=CANDLE_COLS)
    assert len(got) < len(frame), "read the whole file; row groups are not being skipped"
    assert len(got) >= 1_500
    assert len(got) <= PARQUET_ROW_GROUP_SIZE * 2


def test_a_single_group_file_still_returns_correct_data_even_though_it_cannot_skip(one_group, frame):
    # NEGATIVE CONTROL for the test above: on one group there is nothing to skip, so a
    # full decode is expected and correct - it must not be treated as a failure.
    got = read_parquet_tail(one_group, 1_500, columns=CANDLE_COLS)
    assert len(got) == len(frame)
    assert got[CANDLE_COLS].tail(1_500).reset_index(drop=True).equals(
        frame[CANDLE_COLS].tail(1_500).reset_index(drop=True))


def test_it_reads_the_MINIMUM_number_of_row_groups(many_groups):
    """Asking for exactly one group's worth must decode exactly that group.

    Caught by mutation: `total >= n_rows` -> `total > n_rows` survived the whole suite.
    It still returns correct data - callers .tail() anyway - so every equality test
    passed while the function quietly read an extra 50,000-row group at each boundary.
    Minimality IS the contract here; without this test it is unenforced.
    """
    pf = pq.ParquetFile(many_groups)
    last = pf.metadata.row_group(pf.num_row_groups - 1).num_rows
    got = read_parquet_tail(many_groups, last, columns=CANDLE_COLS)
    assert len(got) == last, f"decoded {len(got)} rows for a {last}-row request"


def test_columns_are_honoured(many_groups):
    got = read_parquet_tail(many_groups, 10, columns=CANDLE_COLS)
    assert list(got.columns) == CANDLE_COLS
    assert "timestamp" not in got.columns


def test_all_columns_when_none_requested(many_groups, frame):
    got = read_parquet_tail(many_groups, 10, columns=None)
    assert set(got.columns) == set(frame.columns)
