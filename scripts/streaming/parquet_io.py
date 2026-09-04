"""Parquet read/write helpers for the live 1-minute stores.

Split out of `stream_chart` deliberately. That module rebinds `sys.stdout` to a new
TextIOWrapper at import time (a Windows cp1252 workaround), which closes the stream
pytest is capturing - so anything importable only through `stream_chart` cannot be unit
tested without disabling capture. These helpers are pure and belong on their own.
"""

from __future__ import annotations

import pyarrow.parquet as pq

# Rows per parquet row group. Parquet can only skip whole row groups, so a file written
# as ONE group must be decoded in full even to read its last bar - and two call sites
# (init_chart_data, handle_history) read the whole file purely to take a tail.
#
# Measured on live_storage_-NQ.parquet (598,606 rows):
#     row_group_size   groups   file MB   tail read   tail RAM   rows decoded
#       (one group)         1      12.3     11.1 ms    39.8 MB        598,606
#           100,000         6      13.7      2.6 ms     1.3 MB         98,606
#            50,000        12      14.3      1.7 ms     0.1 MB         48,606
#            20,000        30      15.2      1.2 ms     0.8 MB         18,606
#
# 50,000 is the knee: tail reads become ~free for +16% on disk (data/live ~504 -> ~585
# MB). Smaller groups keep shrinking the read but compress worse for no useful gain.
PARQUET_ROW_GROUP_SIZE = 50_000

# The only columns either tail-reader needs. `timestamp` is a derived string column and
# decoding it is the most expensive part of a read - init_chart_data dropped it
# immediately anyway, and handle_history never referenced it.
CANDLE_COLS = ["time", "open", "high", "low", "close", "volume"]


def read_parquet_tail(path, n_rows, columns=None):
    """Read approximately the last `n_rows` rows, decoding as few row groups as possible.

    Returns AT LEAST `n_rows` when the file holds that many - callers still `.tail()` to
    the exact count, because row-group boundaries will not line up with the request.

    Falls back to a full read on a single-group file. Every file on disk is single-group
    until its next write, so both shapes are live simultaneously and must return
    identical data; that equivalence is what the tests pin.
    """
    pf = pq.ParquetFile(path)
    n_groups = pf.num_row_groups
    if n_groups <= 1:
        return pq.read_table(path, columns=columns).to_pandas()

    md = pf.metadata
    take, total = [], 0
    for i in range(n_groups - 1, -1, -1):
        take.append(i)
        total += md.row_group(i).num_rows
        if total >= n_rows:
            break
    take.reverse()
    return pf.read_row_groups(take, columns=columns).to_pandas()
