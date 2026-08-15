"""
Comprehensive test suite for dedicated high-performance ICT libraries:
- scripts.libs_py.cisd (Change in State of Delivery)
- scripts.libs_py.fvg (Fair Value Gaps & Consequent Encroachment)
- scripts.libs_py.ifvg (Inversion Fair Value Gaps)
- scripts.libs_py.bpr (Balanced Price Ranges)
- scripts.libs_py.orderblock (Order Blocks & Breaker Blocks)
"""
import os
import pytest
import numpy as np
import pandas as pd

from scripts.libs_py.cisd import compute_cisd, CISDTracker
from scripts.libs_py.fvg import compute_fvg, FVGTracker
from scripts.libs_py.ifvg import compute_ifvg, IFVGTracker
from scripts.libs_py.bpr import compute_bpr, BPRTracker
from scripts.libs_py.orderblock import compute_orderblock, OrderBlockTracker


@pytest.fixture
def sample_nq_data():
    """Load sample parquet data or generate synthetic OHLC."""
    path = "data/-NQ_1m.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path).head(10000)
    else:
        n = 1000
        sim_c = 100.0 + np.cumsum(np.random.randn(n))
        return pd.DataFrame({
            "open": sim_c + np.random.randn(n) * 0.1,
            "high": sim_c + np.abs(np.random.randn(n) * 0.3),
            "low": sim_c - np.abs(np.random.randn(n) * 0.3),
            "close": sim_c,
            "volume": 100
        }, index=pd.date_range("2024-01-01", periods=n, freq="1min"))


def test_cisd_multi_timeframe(sample_nq_data):
    """Test CISD on 1m, 3m, 5m, and 15m resolutions."""
    res_1m = compute_cisd(sample_nq_data)
    assert "cisd_event" in res_1m.columns
    assert len(res_1m) == len(sample_nq_data)

    res_3m = compute_cisd(sample_nq_data, timeframe="3min", align_to_base=True)
    assert len(res_3m) == len(sample_nq_data)

    res_5m = compute_cisd(sample_nq_data, timeframe="5min", align_to_base=True)
    assert len(res_5m) == len(sample_nq_data)

    res_15m_native = compute_cisd(sample_nq_data, timeframe="15min", align_to_base=False)
    assert len(res_15m_native) < len(sample_nq_data)


def test_fvg_multi_timeframe(sample_nq_data):
    """Test FVG on 1m, 3m, 5m, and 15m resolutions with CE calculation."""
    res_1m = compute_fvg(sample_nq_data, min_gap_pts=0.0)
    assert "fvg_event" in res_1m.columns
    assert "fvg_ce" in res_1m.columns

    has_fvg = res_1m["fvg_event"] != 0
    if has_fvg.any():
        tops = res_1m.loc[has_fvg, "fvg_top"]
        bots = res_1m.loc[has_fvg, "fvg_bottom"]
        ces = res_1m.loc[has_fvg, "fvg_ce"]
        expected_ce = (tops + bots) / 2.0
        np.testing.assert_allclose(ces.values, expected_ce.values, rtol=1e-5)

    res_5m = compute_fvg(sample_nq_data, timeframe="5min", align_to_base=True)
    assert len(res_5m) == len(sample_nq_data)


def test_ifvg_multi_timeframe(sample_nq_data):
    """Test iFVG inversion detection across timeframes."""
    res_1m = compute_ifvg(sample_nq_data)
    assert "ifvg_event" in res_1m.columns
    assert "ifvg_state" in res_1m.columns

    res_15m = compute_ifvg(sample_nq_data, timeframe="15min", align_to_base=True)
    assert len(res_15m) == len(sample_nq_data)


def test_bpr_multi_timeframe(sample_nq_data):
    """Test Balanced Price Range detection and midpoint calculations."""
    res_1m = compute_bpr(sample_nq_data)
    assert "bpr_event" in res_1m.columns
    assert "bpr_midpoint" in res_1m.columns

    res_5m = compute_bpr(sample_nq_data, timeframe="5min", align_to_base=True)
    assert len(res_5m) == len(sample_nq_data)


def test_orderblock_multi_timeframe(sample_nq_data):
    """Test Order Block and Breaker Block detection with Mean Thresholds."""
    res_1m = compute_orderblock(sample_nq_data, swing_lookback=5)
    assert "ob_event" in res_1m.columns
    assert "ob_mt" in res_1m.columns

    has_ob = res_1m["ob_event"] != 0
    if has_ob.any():
        tops = res_1m.loc[has_ob, "ob_top"]
        bots = res_1m.loc[has_ob, "ob_bottom"]
        mts = res_1m.loc[has_ob, "ob_mt"]
        expected_mt = (tops + bots) / 2.0
        np.testing.assert_allclose(mts.values, expected_mt.values, rtol=1e-5)

    res_15m = compute_orderblock(sample_nq_data, timeframe="15min", align_to_base=True)
    assert len(res_15m) == len(sample_nq_data)


def test_streaming_trackers():
    """Test incremental streaming trackers for live bar feeds."""
    cisd_t = CISDTracker()
    fvg_t = FVGTracker()
    ifvg_t = IFVGTracker()
    bpr_t = BPRTracker()
    ob_t = OrderBlockTracker()

    sample_bars = [
        (100.0, 101.0, 99.0, 99.5),
        (99.5, 100.0, 97.0, 97.5),
        (97.5, 98.0, 95.0, 95.5),
        (95.5, 102.0, 95.0, 101.5),
        (101.5, 103.0, 96.0, 96.5),
    ]

    for o, h, l, c in sample_bars:
        c_res = cisd_t.update(o, h, l, c)
        f_res = fvg_t.update(o, h, l, c)
        i_res = ifvg_t.update(o, h, l, c)
        b_res = bpr_t.update(o, h, l, c)
        o_res = ob_t.update(o, h, l, c)

        assert isinstance(c_res.event, (int, np.integer))
        assert isinstance(f_res.event, (int, np.integer))
        assert isinstance(i_res.event, (int, np.integer))
        assert isinstance(b_res.event, (int, np.integer))
        assert isinstance(o_res.event, (int, np.integer))


if __name__ == "__main__":
    pytest.main(["-v", __file__])
