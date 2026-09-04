"""Session-aware gap detection over the stored 1-minute history.

WHY THIS EXISTS
---------------
`stream_chart.detect_gaps` scans the in-memory candle list with a Python loop and
excludes only WEEKEND gaps. Two consequences, both measured 2026-09-03:

1. It forces the in-memory window to stay at 15,000 candles per symbol (~157 MB across
   the watchlist) purely to give the scan something to look at - even though the parquet
   is the authoritative history and `handle_history` already reads from it.

2. Weekend-only filtering is wrong for every symbol here. Nothing in this watchlist is
   a clean 09:30-16:00 instrument with data on every minute:

       NQ    1,020 dense min/day   ET 00:00-16:59   (near-24h future)
       SPY     553 dense min/day   ET 07:00-19:59   (extended hours)
       NFLX    408 dense min/day   ET 07:00-16:06
       VIX     390 dense min/day   ET 09:31-16:00   (659 min/day with NO bar, ever)

   A missing 1-minute bar at 03:00 for NFLX is not a data hole - no trade printed, and
   re-requesting it returns nothing. Treating those as gaps produced 18,327 "gaps"
   across the watchlist, ~15,900 of them inside the API window. Bridging those would be
   ~16k Schwab calls that cannot succeed, and the gaps would be re-detected forever.

THE APPROACH
------------
Derive each symbol's trading session FROM ITS OWN HISTORY rather than hardcoding 28
schedules that go stale. A minute-of-day is "dense" if a bar is present on at least
`dense_frac` of weekdays. A gap is worth bridging only if the minutes it is missing are
normally dense - which is exactly the definition of "data that should be there".

Detection reads only the `time` column: 6.3 ms over 598k rows, versus a Python loop over
a 15,000-dict window.

⚠️ This module DETECTS. It does not bridge. `stream_chart.detect_gaps` currently returns
None (the `return gaps` line was deleted in 8df95e34, 2026-03-22), so bridging has been
dead for five months. Restoring it must come AFTER this filter is trusted, or the first
run stampedes the Schwab API with ~16k requests.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ET_TZ = "America/New_York"
MINUTES_PER_DAY = 1440

# A minute counts as part of the session if it carries a bar on this fraction of
# weekdays.
#
# 0.80, chosen by measurement rather than taste. The threshold trades two opposite
# errors: too high hides a real session (missed bridges), too low promotes
# thin-liquidity minutes to "expected" and manufactures gaps that no API call can fill.
#
# ⚠️ A REAL SESSION CAN SIT JUST UNDER THE THRESHOLD. VIX trades from 03:15 ET, but its
# early session is present on only 40 of 48 weekdays (83.3%) - the 8 misses are streamer
# restarts, several of them the very outages this detector exists to find. At 0.90 the
# whole 03:15-09:31 block scored "not a session", so VIX's missing pre-market became
# permanently invisible: THE OUTAGE SUPPRESSED DETECTION OF ITSELF. At 0.80 the session
# resolves correctly to 03:15-16:15 (776 min) and those 8 days are reported.
#
# Measured total gaps across the watchlist, and the cost of going lower:
#     0.90 ->  86   VIX early session INVISIBLE
#     0.85 ->  91
#     0.80 -> 153   VIX 03:15-16:15 correct; NFLX 2 -> 7
#     0.75 -> 241   NFLX 21   <- thin overnight equity minutes start qualifying
#     0.70 -> 345   NFLX 61
#     0.60 -> 623   NFLX 127
#
# Only VIX among the indices has an early session; VVIX/VXN/OVX/RVX/GVZ/VXD/VOLI/VIX9D
# are RTH-only (first bar 09:31), and SPX is 09:30. SPY/QQQ carry 00:00-07:00 data at
# 70-90% coverage, which is why 0.75 and below start generating false gaps on them.
DEFAULT_DENSE_FRAC = 0.80

# Below this many weekdays of history the density estimate is noise, and the safe
# response is to decline to judge rather than to guess a session.
MIN_DAYS_FOR_MASK = 10

# A gap must be missing at least this many dense minutes to be worth an API call.
# 1 would make every thin minute inside a dense window a "gap".
DEFAULT_MIN_DENSE_MINUTES = 5

# Enumerating the missing minutes of a very old/large hole is unbounded work, and a hole
# that big is not something a 45-day bridge window can fix anyway.
MAX_GAP_MINUTES_TO_ENUMERATE = 20_000

# `bridge_gaps` refuses to fetch anything older than this, so detection is bounded to
# match. Detecting what cannot be acted on is cost with no possible outcome.
BRIDGE_MAX_AGE_DAYS = 45


def _to_et(times_ms: np.ndarray) -> pd.DatetimeIndex:
    return pd.to_datetime(times_ms, unit="ms", utc=True).tz_convert(ET_TZ)


def build_session_mask(
    times_ms: np.ndarray,
    dense_frac: float = DEFAULT_DENSE_FRAC,
    min_days: int = MIN_DAYS_FOR_MASK,
):
    """Return a 1440-element bool mask of minutes-of-day (ET) that normally carry a bar.

    Returns None when there is too little history to judge - callers must treat that as
    "cannot classify", not as "no session".
    """
    if times_ms is None or len(times_ms) == 0:
        return None
    idx = _to_et(np.asarray(times_ms))
    idx = idx[idx.weekday < 5]  # weekends are excluded from the estimate entirely
    if len(idx) == 0:
        return None
    n_days = idx.normalize().nunique()
    if n_days < min_days:
        return None
    minute_of_day = idx.hour * 60 + idx.minute
    per_minute_days = np.zeros(MINUTES_PER_DAY, dtype=float)
    # Count DISTINCT days per minute, not bars: a duplicated bar must not inflate density.
    seen = pd.DataFrame({"m": minute_of_day, "d": idx.normalize()}).drop_duplicates()
    counts = np.bincount(seen["m"].to_numpy(), minlength=MINUTES_PER_DAY)
    per_minute_days[: len(counts)] = counts
    return (per_minute_days / n_days) >= dense_frac


def session_status(times_ms: np.ndarray, dense_frac: float = DEFAULT_DENSE_FRAC) -> dict:
    """Describe what the detector can and cannot say about a symbol.

    `detect_gaps` returns [] both when a symbol is clean and when it has too little
    history to judge - an empty list that means "nothing wrong" and one that means
    "I cannot tell" are indistinguishable at the call site. Measured 2026-09-03, SEVEN
    watchlist symbols were in the second state (GVZ, OVX, RVX, VIX9D, VOLI, VXD, VXN -
    each with 7 weekdays of history against MIN_DAYS_FOR_MASK=10) and were therefore
    unmonitored while looking healthy. Use this to report that state rather than
    inferring health from an empty list.
    """
    times_ms = np.asarray(times_ms, dtype=np.int64)
    if times_ms.size < 2:
        return {"monitored": False, "reason": "insufficient bars", "weekdays": 0}
    idx = _to_et(times_ms)
    weekdays = int(idx[idx.weekday < 5].normalize().nunique())
    mask = build_session_mask(times_ms, dense_frac=dense_frac)
    if mask is None:
        return {
            "monitored": False,
            "reason": f"only {weekdays} weekdays of history (need {MIN_DAYS_FOR_MASK})",
            "weekdays": weekdays,
        }
    on = np.flatnonzero(mask)
    return {
        "monitored": True,
        "reason": "",
        "weekdays": weekdays,
        "session_minutes": int(mask.sum()),
        "session_et": f"{on[0] // 60:02d}:{on[0] % 60:02d}-{on[-1] // 60:02d}:{on[-1] % 60:02d}",
    }


def missing_dense_minutes(
    gap_start_ms: int,
    gap_end_ms: int,
    mask: np.ndarray,
    max_enumerate: int = MAX_GAP_MINUTES_TO_ENUMERATE,
) -> int:
    """Count minutes strictly between two bars that the session says should carry one."""
    if mask is None:
        return 0
    first_missing = int(gap_start_ms) + 60_000
    if first_missing >= int(gap_end_ms):
        return 0
    n = (int(gap_end_ms) - first_missing) // 60_000
    if n <= 0:
        return 0
    if n > max_enumerate:
        return 0
    stamps = _to_et(first_missing + np.arange(n, dtype=np.int64) * 60_000)
    weekday = stamps.weekday.to_numpy() < 5
    mod = (stamps.hour * 60 + stamps.minute).to_numpy()
    return int(np.count_nonzero(weekday & mask[mod]))


def detect_gaps(
    times_ms: np.ndarray,
    mask: np.ndarray | None = None,
    min_dense_minutes: int = DEFAULT_MIN_DENSE_MINUTES,
    now_ms: int | None = None,
    include_trailing: bool = True,
    max_age_days: int | None = BRIDGE_MAX_AGE_DAYS,
):
    """Find gaps in a sorted epoch-ms series that are missing minutes that should exist.

    Returns a list of (start_ms, end_ms, missing_dense_minutes), most recent last.
    An empty list means "nothing to bridge", which is different from
    `stream_chart.detect_gaps`'s current behaviour of returning None unconditionally.

    `max_age_days` bounds the SCAN to what `bridge_gaps` would actually act on - it
    refuses anything older than 45 days. Detecting older holes is pure cost: it cannot
    lead to an action, and it dominated the runtime (24.3 s -> 0.6 s across the whole
    watchlist once bounded). The session mask is still built from the FULL history,
    because a wider sample gives a better density estimate.
    """
    times_ms = np.asarray(times_ms, dtype=np.int64)
    if times_ms.size < 2:
        return []
    if mask is None:
        mask = build_session_mask(times_ms)
    if mask is None:
        return []  # not enough history to classify - decline rather than guess

    now = int(now_ms if now_ms is not None else pd.Timestamp.utcnow().timestamp() * 1000)

    scan = times_ms
    if max_age_days is not None:
        cutoff = now - int(max_age_days) * 86_400_000
        first = int(np.searchsorted(times_ms, cutoff, side="left"))
        # Step back one bar so a gap straddling the cutoff is still seen from its start.
        scan = times_ms[max(first - 1, 0):]
        if scan.size < 2:
            scan = times_ms[-2:]

    # Candidate gaps, then ONE timezone conversion for all of them together.
    # Converting per gap costs a fixed ~1 ms of pandas overhead, and thin-liquidity
    # minutes make thousands of candidates on the equity symbols: 5.5 s -> ~0.1 s.
    starts, ends = [], []
    deltas = np.diff(scan)
    for i in np.flatnonzero(deltas > 60_000):
        start, end = int(scan[i]), int(scan[i + 1])
        n_missing = (end - start) // 60_000 - 1
        if 0 < n_missing <= MAX_GAP_MINUTES_TO_ENUMERATE:
            starts.append(start)
            ends.append(end)

    if include_trailing:
        # The hole between the last stored bar and now. This is the one that matters
        # operationally - it is the live feed having stopped.
        last = int(times_ms[-1])
        n_missing = (now - last) // 60_000 - 1
        if 0 < n_missing <= MAX_GAP_MINUTES_TO_ENUMERATE:
            starts.append(last)
            ends.append(now)

    out = []
    if starts:
        counts = _batch_missing_dense_minutes(starts, ends, mask)
        for start, end, n in zip(starts, ends, counts):
            if n >= min_dense_minutes:
                out.append((start, end, int(n)))
    return out


def _batch_missing_dense_minutes(starts, ends, mask):
    """Vectorised `missing_dense_minutes` over many gaps in a single tz conversion."""
    lengths = [(int(e) - int(s)) // 60_000 - 1 for s, e in zip(starts, ends)]
    total = sum(lengths)
    if total == 0:
        return np.zeros(len(starts), dtype=np.int64)
    flat = np.empty(total, dtype=np.int64)
    pos = 0
    for s, n in zip(starts, lengths):
        if n > 0:
            flat[pos:pos + n] = int(s) + 60_000 * np.arange(1, n + 1, dtype=np.int64)
            pos += n
    stamps = _to_et(flat)
    ok = (stamps.weekday.to_numpy() < 5) & mask[(stamps.hour * 60 + stamps.minute).to_numpy()]
    # Segment-sum the boolean back into per-gap counts.
    edges = np.cumsum([0] + lengths)
    csum = np.concatenate([[0], np.cumsum(ok)])
    return csum[edges[1:]] - csum[edges[:-1]]
