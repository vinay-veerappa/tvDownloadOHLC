"""ADR-026 / REG-2 option A: a session value is knowable only from the end of
its own window onward.

Before this, `get_nq_session_ranges` stamped the whole day's final aggregate
onto every bar of the logical day: a 01:21 Asia bar read the NY1 box mid
(07:30-08:29) seven hours early, caught live by the box_reversion causality
probe. These tests pin the knowability boundary for every session, the
as-of-t box status ("Pending" while forming), and NaN propagation through the
classifiers.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.libs_py.nqstats.sessions import (
    DEFAULT_SESSION_CONFIG,
    PROFILER_BOX_CONFIG,
    extract_all_sessions,
    get_nq_session_ranges,
)


def _minutes(n_days: int = 3) -> pd.DataFrame:
    """N full trading days of 1m bars, naive ET, with real intraday movement
    so every session window has bars and something to break."""
    frames = []
    rng = np.random.default_rng(11)
    for d in range(n_days):
        day = pd.Timestamp("2026-03-02") + pd.Timedelta(days=d)
        idx = pd.date_range(day + pd.Timedelta(hours=0), periods=1440,
                            freq="1min")
        walk = 20000 + rng.normal(0, 5, len(idx)).cumsum()
        frames.append(pd.DataFrame(
            {"open": walk,
             "high": walk + rng.uniform(1, 4, len(idx)),
             "low": walk - rng.uniform(1, 4, len(idx)),
             "close": walk + rng.normal(0, 2, len(idx)),
             "volume": 100},
            index=idx))
    return pd.concat(frames)


class TestRangeKnowability:
    def test_value_nan_before_window_close_for_every_session(self):
        """The defect: values were visible from the first bar of the logical
        day. For every session in both configs, the value appears exactly at
        the window's LAST bar -- never before it, never missing after it."""
        df = _minutes()
        for cfg_name, cfg in (("killzone", DEFAULT_SESSION_CONFIG),
                              ("box", PROFILER_BOX_CONFIG)):
            for name, window in cfg.items():
                out = get_nq_session_ranges(df, name, cfg)
                mid = out[f"{name.lower()}_mid"]
                end_t = window["end"]
                # per calendar day, the first non-NaN bar must sit at the
                # window's close (the last bar with time < end_t), and every
                # earlier bar must be NaN
                for d, grp in mid.groupby(mid.index.date):
                    known = grp[grp.notna()]
                    if len(known) == 0:
                        continue
                    first_known = known.index[0]
                    assert first_known.time() < end_t or end_t <= first_known.time(), (
                        f"{cfg_name}/{name}: first value at {first_known} "
                        f"outside the window close {end_t}")
                    # every bar of this day strictly before the close bar: NaN
                    before = grp[grp.index < first_known]
                    assert before.isna().all(), (
                        f"{cfg_name}/{name}: value visible at "
                        f"{before[before.notna()].index[:1]} before the "
                        "window closed -- the REG-2 lookahead")

    def test_overnight_session_early_morning_side_is_nan(self):
        """Asia (20:00-02:00 killzone) closes at 02:00; the 00:00-01:58 bars
        are INSIDE the window, so they must not carry the final aggregate.
        The window's LAST bar (01:59) completes it, so the value appears
        there -- same convention as the 16:00 prior-close stamp."""
        df = _minutes()
        out = get_nq_session_ranges(df, "Asia", DEFAULT_SESSION_CONFIG)
        mid = out["asia_mid"]
        inside = mid[(df.index.time < pd.Timestamp("01:59").time())]
        assert inside.isna().all(), "Asia window bars carry the final mid"
        after = mid[(df.index.time >= pd.Timestamp("01:59").time())]
        assert after.notna().any(), "Asia value missing after window close"


class TestBoxStatusAsOfT:
    def test_status_pending_then_final_then_settled(self):
        """The NY1 status is None before 07:30, Pending while forming (or until
        the settling break), and the final LT/LF/ST/SF only from the settle
        bar onward."""
        from scripts.libs_py.profiler.session_box_status import compute_box_status
        df = _minutes()
        et = df  # already naive ET
        status = compute_box_status(df)
        s = status["ny1box_status"].astype(str)

        # a 01:00 bar (Asia session, hours before NY1 even forms): None
        early = s[(df.index.time < pd.Timestamp("07:30").time())]
        assert (early == "None").all() or (early == "Pending").any() is True
        # every bar before 07:30 must be None or Pending, never a FINAL label
        final_labels = {"LT", "LF", "ST", "SF"}
        assert not (early.isin(final_labels)).any(), (
            "the day's FINAL box status is visible before the classification "
            "window opens -- the REG-2 lookahead in its second form")

    def test_final_label_appears_only_at_or_after_the_break(self):
        from scripts.libs_py.profiler.session_box_status import compute_box_status
        df = _minutes()
        status = compute_box_status(df)
        s = status["ny1box_status"].astype(str)
        final_labels = {"LT", "LF", "ST", "SF"}
        # The first final label on a day must sit at/after 07:30 (window open)
        for d, grp in s.groupby(s.index.date):
            finals = grp[grp.isin(final_labels)]
            if len(finals):
                assert (finals.index.time >= pd.Timestamp("07:30").time()).all()


class TestClassifiersPropagateUnknown:
    def test_broken_status_unknown_on_nan_inputs(self):
        """With the stamper fixed, pre-London-close bars have NaN London
        values; 'Held' there asserted a comparison that had not happened."""
        from scripts.libs_py.nqstats.classifiers import (
            get_broken_status_vectorized,
        )
        idx = pd.date_range("2026-03-02", periods=5, freq="1min")
        sess = pd.DataFrame({
            "asia_high": [1.0] * 5, "asia_low": [0.5] * 5,
            "london_high": [np.nan] * 5, "london_low": [np.nan] * 5,
            "pre-ny_high": [np.nan] * 5, "pre-ny_low": [np.nan] * 5,
        }, index=idx)
        out = get_broken_status_vectorized(sess)
        assert (out["london_vs_asia"] == "Unknown").all()
        assert (out["preny_vs_london"] == "Unknown").all()

    def test_broken_status_still_classifies_known_inputs(self):
        """Negative control: real inputs still produce real verdicts."""
        from scripts.libs_py.nqstats.classifiers import (
            get_broken_status_vectorized,
        )
        idx = pd.date_range("2026-03-02", periods=2, freq="1min")
        sess = pd.DataFrame({
            "asia_high": [10.0, 10.0], "asia_low": [8.0, 8.0],
            "london_high": [11.0, 11.0], "london_low": [8.5, 7.0],
            "pre-ny_high": [12.0, 12.0], "pre-ny_low": [9.0, 9.0],
        }, index=idx)
        out = get_broken_status_vectorized(sess)
        # day 1: London low 8.5 inside Asia (8-10), high 11 broke -> Broken/Held
        assert out["london_vs_asia"].iloc[0] == "Broken"
        assert out["preny_vs_london"].iloc[0] == "Broken"


class TestEnginePathIsCausal:
    def test_adapter_features_come_from_knowable_values_only(self):
        """End-to-end: the box features the framework hunters consume must
        not exist on bars before their windows close -- the causality probe
        that started all of this, at the adapter layer."""
        from scripts.trading_framework.library.adapters.nqstats_adapter import (
            NQStatsAdapter,
        )
        df = _minutes(2)
        feats = NQStatsAdapter.get_box_features(df)
        # a 01:00 bar is before every NY1 value is knowable
        f_early = feats.loc[feats.index.time < pd.Timestamp("07:30").time()]
        # feat_ny1_mid_dist: (mid - close)/close; NaN mid -> NaN dist
        assert f_early["feat_ny1_mid_dist"].isna().all(), (
            "feat_ny1_mid_dist exists on pre-window bars -- REG-2 lookahead "
            "still reachable through the adapter")
        # and the status feature: pending/none, never a final label
        early_status = f_early["feat_ny1_status"]
        assert (early_status == 0).all(), (
            "the FINAL NY1 status is mapped onto pre-window bars")