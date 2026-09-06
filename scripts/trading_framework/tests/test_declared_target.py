"""Section 11 item 19 (option A, ratified 2026-09-05): the queen leg honours
the hunter's DECLARED target.

Until this change the sanctioned engine dropped `target1_price` entirely and
substituted queen_bps/runner_bps -- measured on `mean_reversion`, 88.4% of
declared targets sat INSIDE the queen leg (median 2.48 bps vs the 10 bps
bracket), so the engine took profit 4x farther than the hunter declared, on
a payoff nothing chose. The `hunt()` contract says a hunter declares a
target; now the engine honours it:

  * declared target on the right side of entry -> the QUEEN leg exits there
  * NaN / absent / wrong-side (geometry-defect class) -> the bps fallback
  * the runner leg stays at runner_bps (ADR-023 Cover-The-Queen is frozen)
  * per-trade `queen_used_declared_target` names which applied

These tests pin the semantics on BOTH paths (kernel and Python mirror must
agree -- gate2 proves it on a year of real bars; these prove the shapes).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.execution.nt8_parity_engine import NT8ParityEngine, HAS_RUST_CORE


def _bars(n=600):
    """Wide oscillation: TPs and the stop are both reachable."""
    idx = pd.date_range("2026-01-05 10:00", periods=n, freq="1min")
    px = np.full(n, 100.0) + 1.5 * np.sin(np.arange(n) / 30.0)
    return pd.DataFrame({"open": px, "high": px + 0.6, "low": px - 0.6,
                         "close": px}, index=idx), idx


def _one_signal(idx, bar=130, limit=99.72, stop=97.5):
    sig = pd.Series(0, index=idx, dtype="int32")
    sig.iloc[bar] = 1
    lmt = pd.Series(100.0, index=idx)
    lmt.iloc[bar] = limit
    sl = pd.Series(100.0, index=idx)
    sl.iloc[bar] = stop
    return sig, lmt, sl


KW = dict(earliest_entry_hhmm=0, latest_entry_hhmm=2359,
          flatten_hhmm=2359, filter_lunch=False)


class TestDeclaredTargetHonoured:
    def test_queen_exits_at_the_declared_target(self):
        """A declared target on the right side becomes the queen leg's exit:
        leg1_points must equal target - entry exactly."""
        df, idx = _bars()
        sig, lmt, sl = _one_signal(idx)
        tgt = pd.Series(np.nan, index=idx)
        tgt.iloc[130] = 100.5
        eng = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
        out = eng.simulate(df, sig, lmt, sl, target_prices=tgt, **KW)
        assert len(out) == 1
        r = out.iloc[0]
        assert bool(r["queen_used_declared_target"]) is True
        assert r["leg1_points"] == pytest.approx(100.5 - r["entry_price"],
                                                 abs=1e-9)

    def test_nan_target_falls_back_to_bps(self):
        """Negative control: NaN means 'no declaration', and the trade must
        carry the bps bracket with queen_used_declared_target False."""
        df, idx = _bars()
        sig, lmt, sl = _one_signal(idx)
        tgt = pd.Series(np.nan, index=idx)
        eng = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
        out = eng.simulate(df, sig, lmt, sl, target_prices=tgt, **KW)
        assert len(out) == 1
        assert bool(out.iloc[0]["queen_used_declared_target"]) is False

    def test_no_target_argument_equals_nan_target(self):
        """Omitting target_prices entirely must behave identically to passing
        all-NaN -- the pre-item-19 behaviour is the fallback, not the default
        silently changing."""
        df, idx = _bars()
        sig, lmt, sl = _one_signal(idx)
        a = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
        out_a = a.simulate(df, sig, lmt, sl, **KW)
        b = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
        out_b = b.simulate(df, sig, lmt, sl,
                           target_prices=pd.Series(np.nan, index=idx), **KW)
        pd.testing.assert_frame_equal(out_a, out_b)

    def test_wrong_side_declared_target_clamps_to_bps(self):
        """A declared target AT/BELOW a long's entry fills instantly and pays
        a nonsense profit -- the geometry-defect class the validator drops
        signals for. The engine must fall back to bps, not accept it."""
        df, idx = _bars()
        sig, lmt, sl = _one_signal(idx)
        tgt = pd.Series(np.nan, index=idx)
        tgt.iloc[130] = 97.0          # below the long entry: nonsense
        eng = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
        out = eng.simulate(df, sig, lmt, sl, target_prices=tgt, **KW)
        assert len(out) == 1
        assert bool(out.iloc[0]["queen_used_declared_target"]) is False

    def test_short_declared_target_above_entry_also_clamps(self):
        # Place the signal on the crest so the sell-limit fills.
        df, idx = _bars()
        sig, lmt, sl = _one_signal(idx, bar=55, limit=100.7, stop=102.5)
        sig.iloc[55] = -1
        tgt = pd.Series(np.nan, index=idx)
        tgt.iloc[55] = 103.0         # above the short entry: nonsense
        eng = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
        out = eng.simulate(df, sig, lmt, sl, target_prices=tgt, **KW)
        assert len(out) == 1, "fixture regressed: the short limit no longer fills"
        assert bool(out.iloc[0]["queen_used_declared_target"]) is False


@pytest.mark.skipif(not HAS_RUST_CORE, reason="Rust kernel not built")
class TestBothPathsAgreeOnDeclaredTarget:
    def test_rust_and_python_honour_identically(self):
        df, idx = _bars()
        sig, lmt, sl = _one_signal(idx)
        tgt = pd.Series(np.nan, index=idx)
        tgt.iloc[130] = 100.5
        eng = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
        out_r = eng.simulate(df, sig, lmt, sl, target_prices=tgt, **KW)
        eng2 = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
        out_p = eng2.simulate(df, sig, lmt, sl, target_prices=tgt,
                              use_rust=False, **KW)
        assert len(out_r) == len(out_p) == 1
        assert out_r.iloc[0]["leg1_points"] == out_p.iloc[0]["leg1_points"]
        assert (bool(out_r.iloc[0]["queen_used_declared_target"])
                == bool(out_p.iloc[0]["queen_used_declared_target"]) is True)


class TestAdapterPassesTheDeclaredTarget:
    def test_canonical_frame_target_reaches_the_engine(self):
        """End-to-end: the adapter expands target1_price onto the bars and
        the engine honours it -- the gap item 19 recorded was precisely that
        this never happened."""
        from scripts.trading_framework.core.nt8_parity_backtester import (
            NT8ParityBacktester)
        df, idx = _bars()
        sig = pd.DataFrame({
            "signal_time": [idx[130]],
            "direction": ["long"],
            "entry_price": [99.72],
            "stop_price": [97.5],
            "target1_price": [100.5],
        })
        eng = NT8ParityBacktester()
        res = eng.run(sig, df, {"ticker": "NQ1"})
        tr = res["trades_detailed"]
        assert len(tr) == 1
        assert bool(tr.iloc[0]["queen_used_declared_target"]) is True
        assert tr.iloc[0]["leg1_points"] == pytest.approx(
            100.5 - tr.iloc[0]["entry_price"], abs=1e-9)