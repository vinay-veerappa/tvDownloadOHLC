"""Section 11 item 7: box_reversion was structurally dead, silently.

Two defects, found while chasing the ticket's TypeError:

1. The NQStats adapter looked up '{session}_mid', a column that never
   existed -- the engine names the box mids '{session}box_mid'. So
   'feat_ny1_mid_dist' was never created, and the hunter's
   `.get(..., Series(0))` fallback made the distance gate always False:
   ZERO signals on all data, for the strategy's whole life, with no error.
   The ticket's TypeError was an earlier symptom of the same broken path;
   the current code fails silently, which is worse.

2. Once the feature existed, the magnitude-only distance gate emitted longs
   whose target sat BELOW entry (mid_dist negative) -- a reversion signal
   pointing away from the mid it reverts to.

These tests pin: the adapter produces the mid-distance features; the hunter
REFUSES on a missing feature rather than defaulting; and every emitted signal
has its target on the reversion side of entry.
"""

import numpy as np
import pandas as pd
import pytest

from scripts.trading_framework.library.adapters.nqstats_adapter import (
    NQStatsAdapter,
)


def _synthetic_day(n_days: int = 5) -> pd.DataFrame:
    """1m bars over several trading days, shaped so the NQStats engine
    produces SETTLED box statuses: each day ramps post-08:30 so the NY1 box
    breaks up (LT/LF) and sometimes reverses down, and pre-07:30 is quiet so
    the box forms in its window.
    TZ-AWARE ET -- the engine treats naive input as UTC (engine.process),
    so a naive-ET fixture silently shifts every session window by 5 hours
    and produces no settled statuses at all."""
    frames = []
    rng = np.random.default_rng(7)
    for d in range(n_days):
        day = pd.Timestamp("2026-03-02") + pd.Timedelta(days=d)
        idx = pd.date_range(day + pd.Timedelta(hours=0), periods=1380,
                            freq="1min", tz="US/Eastern")
        walk = 20000 + rng.normal(0, 6, len(idx)).cumsum()
        # Force a break of the NY1 box (07:30-08:30) every day: from 09:00,
        # trend away from the box by a magnitude that exceeds the box range.
        t = idx.to_numpy()
        mins = (pd.DatetimeIndex(idx).hour * 60
                + pd.DatetimeIndex(idx).minute)
        # ramp magnitude grows through the NY eval window
        ramp = np.where((mins >= 540) & (mins <= 690),      # 09:00-11:30
                        (mins - 540) * (30 if d % 2 == 0 else -30) / 60.0,
                        0.0)
        walk = walk + ramp
        df = pd.DataFrame(
            {"open": walk,
             "high": walk + rng.uniform(1, 6, len(idx)),
             "low": walk - rng.uniform(1, 6, len(idx)),
             "close": walk + rng.normal(0, 2, len(idx)),
             "volume": 100},
            index=idx)
        frames.append(df)
    return pd.concat(frames)


class TestAdapterProducesMidDistances:
    def test_box_mid_features_exist(self):
        """The whole defect: '{session}_mid' never existed; the engine names
        the box mids '{session}box_mid'. Before the fix this produced ZERO
        mid-distance columns and every downstream .get() fell back to a
        constant."""
        feats = NQStatsAdapter.get_box_features(_synthetic_day())
        for session in ("asia", "london", "ny1"):
            col = f"feat_{session}_mid_dist"
            assert col in feats.columns, (
                f"{col} missing -- the adapter is looking up a column the "
                "engine never produces, and every consumer silently defaults")
            assert feats[col].notna().any(), col


class TestHunterRefusesOnMissingFeature:
    def test_missing_feature_raises_not_defaults(self):
        """A wiring error must refuse, not trade on a fabricated feature.
        Before the fix the Series(0) fallback made the distance gate
        unconditionally False: zero signals, no error, forever."""
        from scripts.strategies.reversal.core.box_reversion import (
            BoxReversionStrategy,
        )
        df = _synthetic_day()
        s = BoxReversionStrategy()
        # Sabotage the adapter to reproduce the pre-fix condition.
        orig = type(s.adapter).__dict__["get_box_features"]
        try:
            type(s.adapter).get_box_features = staticmethod(
                lambda df_1m, ticker="NQ1": pd.DataFrame(
                    index=df_1m.index))          # no features at all
            with pytest.raises(ValueError, match="wiring"):
                s.hunt(df)
        finally:
            type(s.adapter).get_box_features = orig


class TestSignalGeometryOnTheReversionSide:
    def _hunt(self):
        from scripts.strategies.reversal.core.box_reversion import (
            BoxReversionStrategy,
        )
        return BoxReversionStrategy().hunt(_synthetic_day(10))

    def test_alive_on_real_shaped_data(self):
        """Negative control for the whole item: the strategy emits signals.
        Before the feature fix it emitted zero on everything."""
        out = self._hunt()
        assert len(out) > 0, (
            "box_reversion emitted zero signals on shaped data -- either the "
            "adapter feature is missing again or a fallback silenced it")

    def test_long_targets_above_entry_short_below(self):
        out = self._hunt()
        assert len(out)
        longs = out[out["direction"] == "long"]
        shorts = out[out["direction"] == "short"]
        assert (longs["target1_price"] > longs["entry_price"]).all()
        assert (shorts["target1_price"] < shorts["entry_price"]).all()

    def test_stops_on_the_adverse_side(self):
        out = self._hunt()
        is_long = out["direction"] == "long"
        assert (out.loc[is_long, "stop_price"] < out.loc[is_long, "entry_price"]).all()
        assert (out.loc[~is_long, "stop_price"] > out.loc[~is_long, "entry_price"]).all()


class TestLegacyLogicModuleAgrees:
    def test_refuses_missing_feature_and_targets_the_mid(self):
        """The logic/ mirror of the hunter carries the same two defects; pin
        its fixes too: refusal on missing features and target = mid, not its
        mirror image."""
        from scripts.strategies.logic.box_reversion import BoxMeanReversionSignal
        df = _synthetic_day()
        s = BoxMeanReversionSignal()

        # Refusal path: strip the features.
        import scripts.trading_framework.library.adapters.nqstats_adapter as adapter_mod
        orig = adapter_mod.NQStatsAdapter.__dict__["get_box_features"]
        try:
            adapter_mod.NQStatsAdapter.get_box_features = staticmethod(
                lambda df_1m, ticker="NQ1": pd.DataFrame(index=df_1m.index))
            with pytest.raises(ValueError, match="feat_ny1_status"):
                s.generate_signals(df, {})
        finally:
            adapter_mod.NQStatsAdapter.get_box_features = orig

        # Geometry path on real features.
        sig = s.generate_signals(df, {"min_dist": 0.0})
        if len(sig):
            longs = sig[sig["direction"] == "long"]
            shorts = sig[sig["direction"] == "short"]
            assert (longs["target1_price"] > longs["entry_price"]).all()
            assert (shorts["target1_price"] < shorts["entry_price"]).all()