"""Tests for session-aware gap detection.

Every positive case is paired with a negative control. A gap detector that fires on
everything passes every positive test ever written for it - and the failure mode that
matters here is precisely over-detection: the previous weekend-only logic found 117,977
"gaps" across the watchlist, of which 86 are real.
"""

import numpy as np
import pandas as pd
import pytest

from scripts.streaming.gap_detect import (
    DEFAULT_MIN_DENSE_MINUTES,
    build_session_mask,
    detect_gaps,
    missing_dense_minutes,
    session_status,
)

MIN = 60_000
ET = "America/New_York"


def _series(start_et, minutes, days=40, session=(9, 30), skip=()):
    """Build a synthetic 1m series: `minutes` bars/day from `session`, weekdays only.

    `skip` is a set of (day_index, minute_index) bars to omit, i.e. an injected hole.
    """
    out = []
    day = pd.Timestamp(start_et, tz=ET)
    d = 0
    while d < days:
        if day.weekday() < 5:
            base = day.replace(hour=session[0], minute=session[1], second=0, microsecond=0)
            for m in range(minutes):
                if (d, m) in skip:
                    continue
                out.append(int(base.value // 1_000_000) + m * MIN)
            d += 1
        day += pd.Timedelta(days=1)
    return np.array(sorted(out), dtype=np.int64)


@pytest.fixture
def rth():
    """40 weekdays of a clean 09:30-16:00 ET instrument."""
    return _series("2026-06-01", minutes=390)


# ---------------------------------------------------------------- session mask

def test_mask_marks_the_traded_window_dense(rth):
    mask = build_session_mask(rth)
    assert mask is not None
    assert mask.sum() == 390
    assert mask[9 * 60 + 30] and mask[15 * 60 + 59]


def test_mask_marks_untraded_minutes_thin(rth):
    # NEGATIVE CONTROL for the above: if the mask were all-True, every test below
    # would pass vacuously.
    mask = build_session_mask(rth)
    assert not mask[3 * 60]      # 03:00 - never traded
    assert not mask[20 * 60]     # 20:00 - never traded
    assert mask.sum() < 1440


def test_mask_declines_on_thin_history():
    # Fewer than MIN_DAYS_FOR_MASK weekdays: the estimate would be noise, so the
    # function must return None rather than invent a session.
    assert build_session_mask(_series("2026-06-01", minutes=390, days=3)) is None


def test_mask_is_none_for_empty_input():
    assert build_session_mask(np.array([], dtype=np.int64)) is None


def test_duplicate_bars_do_not_inflate_density():
    s = _series("2026-06-01", minutes=390)
    doubled = np.sort(np.concatenate([s, s]))
    assert np.array_equal(build_session_mask(s), build_session_mask(doubled))


# ---------------------------------------------------------------- detection

def test_no_gaps_in_a_clean_series(rth):
    # The single most important negative control.
    assert detect_gaps(rth, now_ms=int(rth[-1]) + MIN, include_trailing=False) == []


def test_detects_a_hole_inside_the_session():
    # Drop 30 consecutive mid-session bars on day 20.
    holed = _series("2026-06-01", minutes=390, skip={(20, m) for m in range(100, 130)})
    gaps = detect_gaps(holed, now_ms=int(holed[-1]) + MIN, include_trailing=False)
    assert len(gaps) == 1
    assert gaps[0][2] == 30


def test_ignores_a_hole_too_small_to_be_worth_an_api_call():
    small = DEFAULT_MIN_DENSE_MINUTES - 1
    holed = _series("2026-06-01", minutes=390, skip={(20, 100 + m) for m in range(small)})
    assert detect_gaps(holed, now_ms=int(holed[-1]) + MIN, include_trailing=False) == []


def test_overnight_close_is_not_a_gap(rth):
    # 16:00 -> next 09:30 is ~17.5h of absence and must NOT be a gap. This is the
    # defect that produced NFLX 2,835 / MSFT 2,281 under weekend-only filtering.
    assert detect_gaps(rth, now_ms=int(rth[-1]) + MIN, include_trailing=False) == []


def test_weekend_is_not_a_gap(rth):
    # Friday close -> Monday open, implicitly covered by the clean series, asserted
    # explicitly here so a regression names itself.
    idx = pd.to_datetime(rth, unit="ms", utc=True).tz_convert(ET)
    assert (idx.weekday == 4).any() and (idx.weekday == 0).any()
    assert detect_gaps(rth, now_ms=int(rth[-1]) + MIN, include_trailing=False) == []


def test_thin_minute_absence_is_not_a_gap():
    # A near-24h symbol that only trades densely 09:30-16:00: absence at 03:00 is
    # normal and unbridgeable, so it must not be reported.
    dense = _series("2026-06-01", minutes=390)
    sparse = _series("2026-06-01", minutes=1, session=(3, 0), days=40)[::4]  # 3am, ~25%
    series = np.sort(np.concatenate([dense, sparse]))
    for gap in detect_gaps(series, now_ms=int(series[-1]) + MIN, include_trailing=False):
        start = pd.Timestamp(gap[0], unit="ms", tz="UTC").tz_convert(ET)
        assert 9 <= start.hour <= 16, f"reported a gap starting at {start}"


# ---------------------------------------------------------------- trailing / bounds

def test_detects_a_stopped_feed(rth):
    # The operationally important case: the feed stopped WHILE the market was open.
    # The last bar must therefore be mid-session, not at the close - a series ending at
    # 15:59 plus two hours lands at 17:59, when absence is expected and correctly not a
    # gap (that is `test_no_trailing_gap_when_market_is_closed`).
    idx = pd.to_datetime(rth, unit="ms", utc=True).tz_convert(ET)
    mid = rth[(idx.hour == 11) & (idx.minute == 0)][-1]      # 11:00 ET on the last day
    truncated = rth[rth <= mid]
    now = int(mid) + 120 * MIN                               # 13:00 ET, session open
    gaps = detect_gaps(truncated, now_ms=now)
    assert gaps, "a feed that stopped for 2h mid-session must be reported"
    assert gaps[-1][1] == now
    assert gaps[-1][2] == 119                                # missing dense minutes


def test_no_trailing_gap_when_market_is_closed(rth):
    # NEGATIVE CONTROL: same elapsed time, but overnight - absence is expected.
    last = int(rth[-1])
    now = last + 10 * 60 * MIN  # 10h later => ~02:00 ET
    assert detect_gaps(rth, now_ms=now) == []


def test_old_gaps_outside_the_bridge_window_are_not_reported():
    holed = _series("2026-06-01", minutes=390, skip={(2, m) for m in range(100, 140)})
    now = int(holed[-1]) + 200 * 24 * 3600 * 1000  # 200 days later
    assert detect_gaps(holed, now_ms=now, max_age_days=45, include_trailing=False) == []


def test_the_age_bound_is_on_by_default():
    """Pins the DEFAULT, not just the explicitly-passed value.

    Caught by mutation: flipping `max_age_days=BRIDGE_MAX_AGE_DAYS` to `None` in the
    signature survived the whole suite, because every age test passed the argument
    explicitly. An unbounded default would put five months of dead-period holes back in
    front of the bridger on the first run.
    """
    holed = _series("2026-06-01", minutes=390, skip={(2, m) for m in range(100, 140)})
    now = int(holed[-1]) + 200 * 24 * 3600 * 1000
    assert detect_gaps(holed, now_ms=now, include_trailing=False) == []


def test_the_same_gap_is_reported_without_the_age_bound():
    # Proves the previous test excluded on AGE, not because detection is broken.
    holed = _series("2026-06-01", minutes=390, skip={(2, m) for m in range(100, 140)})
    now = int(holed[-1]) + 200 * 24 * 3600 * 1000
    gaps = detect_gaps(holed, now_ms=now, max_age_days=None, include_trailing=False)
    assert len(gaps) == 1 and gaps[0][2] == 40


def test_declines_when_history_is_too_thin_to_classify():
    short = _series("2026-06-01", minutes=390, days=3)
    assert detect_gaps(short, now_ms=int(short[-1]) + MIN) == []


def test_handles_degenerate_input():
    assert detect_gaps(np.array([], dtype=np.int64)) == []
    assert detect_gaps(np.array([1_700_000_000_000], dtype=np.int64)) == []


# ---------------------------------------------------------------- session threshold

def _early_session_series(days=48, missed_early_days=8):
    """A VIX-shaped symbol: an early block plus RTH, with the early block absent on
    some days because the collector restarted."""
    out = []
    day = pd.Timestamp("2026-06-01", tz=ET)
    d = 0
    while d < days:
        if day.weekday() < 5:
            rth = day.replace(hour=9, minute=31, second=0, microsecond=0)
            out += [int(rth.value // 1_000_000) + m * MIN for m in range(390)]
            if d >= missed_early_days:  # early block missing on the first N days
                early = day.replace(hour=3, minute=15, second=0, microsecond=0)
                out += [int(early.value // 1_000_000) + m * MIN for m in range(375)]
            d += 1
        day += pd.Timedelta(days=1)
    return np.array(sorted(out), dtype=np.int64)


def test_a_session_present_on_83pct_of_days_is_still_a_session():
    """Regression test for the 0.90 -> 0.80 threshold decision.

    VIX trades from 03:15 ET but its early block is present on only 40/48 weekdays; the
    8 misses are collector restarts, several of them the outages this detector exists to
    find. At 0.90 the block scored "not a session" and VIX's missing pre-market became
    permanently invisible - the outage suppressed detection of itself.
    """
    s = _early_session_series()
    mask = build_session_mask(s)
    assert mask is not None
    assert mask[3 * 60 + 15], "03:15 must be part of the session at the shipped threshold"
    assert mask.sum() > 700, f"expected the early block to be included, got {mask.sum()}"


def test_that_session_is_invisible_at_a_stricter_threshold():
    """NEGATIVE CONTROL: proves the test above is sensitive to the threshold and not
    passing for some unrelated reason."""
    s = _early_session_series()
    strict = build_session_mask(s, dense_frac=0.90)
    assert not strict[3 * 60 + 15]
    assert strict.sum() == 390  # RTH only


def test_missing_early_blocks_are_reported_as_gaps():
    s = _early_session_series()
    gaps = detect_gaps(s, now_ms=int(s[-1]) + MIN, include_trailing=False, max_age_days=None)
    # Each day that lacks its early block is one gap of 375 dense minutes.
    assert gaps, "days missing their early session must be reported"
    assert any(g[2] == 375 for g in gaps), [g[2] for g in gaps]


def test_thin_minutes_stay_excluded_at_the_shipped_threshold():
    """The other half of the threshold trade: a minute present on ~60% of days is
    thin liquidity, not a session, and must not manufacture gaps."""
    dense = _series("2026-06-01", minutes=390, days=48)
    rng = np.random.default_rng(0)
    thin = []
    day = pd.Timestamp("2026-06-01", tz=ET)
    d = 0
    while d < 48:
        if day.weekday() < 5:
            if rng.random() < 0.60:  # present on ~60% of days
                base = day.replace(hour=3, minute=0, second=0, microsecond=0)
                thin += [int(base.value // 1_000_000) + m * MIN for m in range(60)]
            d += 1
        day += pd.Timedelta(days=1)
    series = np.array(sorted(np.concatenate([dense, np.array(thin, dtype=np.int64)])), dtype=np.int64)
    mask = build_session_mask(series)
    assert not mask[3 * 60 + 30], "a 60%-present overnight minute must not count as session"


# ---------------------------------------------------------------- session_status

def test_session_status_reports_an_unmonitored_symbol():
    """`detect_gaps` returns [] both for 'clean' and for 'cannot tell'. Seven watchlist
    symbols were in the second state and looked healthy."""
    short = _series("2026-06-01", minutes=390, days=3)
    st = session_status(short)
    assert st["monitored"] is False
    assert "weekdays of history" in st["reason"]
    assert detect_gaps(short, now_ms=int(short[-1]) + MIN) == []  # the ambiguous []


def test_session_status_describes_a_monitored_symbol(rth):
    st = session_status(rth)
    assert st["monitored"] is True
    assert st["session_minutes"] == 390
    assert st["session_et"] == "09:30-15:59"


# ---------------------------------------------------------------- batching

def test_batched_counts_match_the_per_gap_computation():
    """The batched path is an optimisation (5.5s -> 0.2s); it must not change results."""
    holed = _series(
        "2026-06-01",
        minutes=390,
        skip={(5, m) for m in range(50, 90)} | {(12, m) for m in range(200, 260)},
    )
    mask = build_session_mask(holed)
    now = int(holed[-1]) + MIN
    # max_age_days=None: this asserts BATCHING equivalence, and the 40-weekday fixture
    # spans 53 calendar days, so the default 45-day bound would legitimately drop the
    # earlier hole and make the comparison test the age bound instead.
    fast = detect_gaps(holed, mask=mask, now_ms=now, include_trailing=False, max_age_days=None)
    ref = []
    for i in np.flatnonzero(np.diff(holed) > MIN):
        s, e = int(holed[i]), int(holed[i + 1])
        n = missing_dense_minutes(s, e, mask)
        if n >= DEFAULT_MIN_DENSE_MINUTES:
            ref.append((s, e, n))
    assert fast == ref
    assert len(ref) == 2  # the batching test is worthless if there is nothing to batch
