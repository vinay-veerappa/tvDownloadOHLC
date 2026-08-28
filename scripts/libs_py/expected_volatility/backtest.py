"""Backtest-facing helpers: box spans and price-touch checks against 1m bars.

The Pine boxes span [session_start, session_start + 1 day]. This module maps
each session's zone ladders onto the intraday bars they cover so strategies
can test touches, holds, and breakouts per zone.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import BOX_MULTIPLIERS, is_session_start


def zone_edges(scan_row: pd.Series) -> pd.DataFrame:
    """One row per zone edge for a scanner row.

    Columns: ``side`` (res|sup), ``level`` (0.25..1.5), ``top``, ``bottom``, ``mid``.
    """
    rows = []
    for mult in BOX_MULTIPLIERS:
        label = f"{mult:g}"
        rows.append({"side": "res", "level": mult, "top": scan_row[f"res_{label}_top"],
                     "bottom": scan_row[f"res_{label}_bottom"], "mid": scan_row[f"res_{label}_mid"]})
        rows.append({"side": "sup", "level": mult, "top": scan_row[f"sup_{label}_top"],
                     "bottom": scan_row[f"sup_{label}_bottom"], "mid": scan_row[f"sup_{label}_mid"]})
    return pd.DataFrame(rows)


def box_sessions(
    intraday: pd.DataFrame,
    session: str = "0930-1600",
    tz: str = "America/New_York",
) -> pd.DataFrame:
    """Per-session bar coverage: ``start_ts`` and ``end_ts`` (UTC) of each box.

    Mirrors the Pine box lifetime: left = session start bar, right =
    ``time_close + 86400000`` (one calendar day later, i.e. the next
    session's start under RTH).
    """
    starts = is_session_start(intraday.index, session, tz)
    idx = intraday.index
    starts_ts = idx[starts]
    span = pd.Timedelta(days=1)
    return pd.DataFrame(
        {"start_ts": starts_ts, "end_ts": starts_ts + span},
        index=pd.RangeIndex(len(starts_ts)),
    )


def touch_stats(
    intraday: pd.DataFrame,
    scan: pd.DataFrame,
    session: str = "0930-1600",
    tz: str = "America/New_York",
) -> pd.DataFrame:
    """Per-session, per-zone touch statistics over the box's bar window.

    For each session row of ``scan`` (output of ``scan_expected_volatility``)
    and each zone edge, computes:
      - ``touched``    : intraday bar range intersected the zone band
      - ``first_touch``: timestamp of first intersection (NaT if none)
      - ``max_pierce`` : deepest fraction of the zone traversed (0..1+)

    Vectorised per session via numpy comparisons over the covered bars.
    """
    boxes = box_sessions(intraday, session, tz)
    idx = intraday.index
    highs = intraday["high"].to_numpy(dtype=float)
    lows = intraday["low"].to_numpy(dtype=float)

    out = []
    scan_index = scan.index.to_numpy()
    for i, (_, box) in enumerate(boxes.iterrows()):
        start, end = box["start_ts"], box["end_ts"]
        lo = idx.searchsorted(start, side="left")
        hi = idx.searchsorted(end, side="left")
        if lo >= hi:
            continue
        b_high = highs[lo:hi]
        b_low = lows[lo:hi]

        row = scan_index[i]
        edges = zone_edges(scan.loc[row])
        for _, edge in edges.iterrows():
            hit = (b_high >= edge["bottom"]) & (b_low <= edge["top"])
            first = idx[lo:hi][hit.argmax()] if hit.any() else pd.NaT
            # deepest fraction of the zone's height traveled by any bar
            height = edge["top"] - edge["bottom"]
            if height <= 0:
                pierce = 0.0
            else:
                penetrated = np.maximum(
                    np.minimum(b_high, edge["top"]) - edge["bottom"], 0.0
                )
                pierce = float(penetrated.max() / height)
            out.append({
                "session_start": start,
                "side": edge["side"],
                "level": edge["level"],
                "touched": bool(hit.any()),
                "first_touch": first,
                "max_pierce": pierce,
            })

    return pd.DataFrame(out)