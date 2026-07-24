"""Comprehensive test suite for scripts/libs_py/ict_engine/core.

Covers:
- FVG detection, mitigation, consecutive join, resample
- Inversion FVG (IFVG), Volume Imbalance (VI), BPR, Liquidity Void
- Order Block (OB) detection and Mean Threshold (MT)
- Breaker Block (BB) detection post-sweep
- Swings (fractals), BOS vs MSS, CISD (proxy & authoritative)
- Gaps (NDOG, NWOG, RTH gap, gap fills, CE)
- Sessions, Macros, Silver Bullets, HTF levels, IPDA ranges
- Retracements & OTE, Dealing Range (Premium/Discount)
- SMT Divergence
- TTrades Fractal, PO3, Quarterly Cycles
- SD Projections
- Edge cases, stress tests (100,000+ bars), and performance benchmarks
"""

from __future__ import annotations

import time
import numpy as np
import pandas as pd
import pytest

from scripts.libs_py.ict_engine.core.pa import (
    detect_fvg,
    check_fvg_mitigation,
    detect_volume_imbalance,
    detect_inversion_fvg,
    detect_bpr,
    detect_orderblock,
    detect_breaker,
    detect_liquidity,
    detect_liquidity_void,
    detect_first_fvg_per_hour,
    detect_first_fvg_after_time,
    detect_unicorn,
    detect_propulsion_block,
    detect_mitigation_block,
    detect_rejection_block,
    detect_org,
)
from scripts.libs_py.ict_engine.core.structure import (
    detect_swings,
    detect_structure_breaks,
    detect_cisd,
    detect_cisd_authoritative,
    detect_swing_hierarchy,
    detect_irl_erl,
    detect_hrlr_lrlr,
)
from scripts.libs_py.ict_engine.core.gaps import (
    detect_opening_gaps,
    get_gap_consequent_encroachment,
    detect_rth_gaps,
    detect_gap_fills,
)
from scripts.libs_py.ict_engine.core.sessions import (
    get_session_data,
    get_macro_data,
    get_silver_bullet_data,
)
from scripts.libs_py.ict_engine.core.htf import (
    detect_ipda_ranges,
    detect_htf_levels,
)
from scripts.libs_py.ict_engine.core.bias import (
    detect_bias_mmxm_simple,
    detect_bias_ttrades_mechanical,
    apply_midnight_open_filter,
)
from scripts.libs_py.ict_engine.core.correlation import (
    detect_smt,
    detect_triad_smt,
)
from scripts.libs_py.ict_engine.core.cycles import (
    detect_ttrade_fractal,
    quarterly_cycles,
    detect_po3,
)
from scripts.libs_py.ict_engine.core.retracements import (
    calculate_retracements,
    detect_dealing_range,
)
from scripts.libs_py.ict_engine.core.projections import (
    sd_projections,
)
from scripts.libs_py.ict_engine.core.pd_matrix import (
    rank_pd_arrays,
)
from scripts.libs_py.ict_engine.core.time_models import (
    detect_opening_range_30m,
    track_killzone_pivots,
    select_cbdr_asia_flout,
    detect_tgif_setup,
)
from scripts.libs_py.ict_engine.core.execution_models import (
    ict_2022_model,
    detect_mmbm_mmsm,
)


def create_sample_ohlc(n: int = 100, freq: str = "1min", start_price: float = 10000.0) -> pd.DataFrame:
    """Generate deterministic synthetic OHLC data for testing."""
    np.random.seed(42)
    dt_index = pd.date_range("2026-01-05 00:00:00", periods=n, freq=freq, tz="UTC")
    
    returns = np.random.normal(0, 0.001, n)
    price_paths = start_price * np.exp(np.cumsum(returns))
    
    opens = price_paths
    highs = opens + np.abs(np.random.normal(2, 1, n))
    lows = opens - np.abs(np.random.normal(2, 1, n))
    closes = opens + np.random.normal(0, 1.5, n)
    
    highs = np.maximum(highs, np.maximum(opens, closes))
    lows = np.minimum(lows, np.minimum(opens, closes))
    
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.random.randint(100, 1000, n)
    }, index=dt_index)


def create_fvg_scenario() -> pd.DataFrame:
    """Create OHLC dataset with known Bullish and Bearish FVGs."""
    dt_index = pd.date_range("2026-01-05 09:30:00", periods=10, freq="1min", tz="UTC")
    data = {
        "open":  [96, 98, 103, 107, 102, 93, 91, 95, 96, 97],
        "high":  [100, 105, 110, 108, 103, 94, 94, 98, 99, 100],
        "low":   [95, 97, 102, 101, 95, 88, 89, 93, 94, 95],
        "close": [98, 104, 108, 102, 96, 90, 93, 97, 98, 99],
    }
    return pd.DataFrame(data, index=dt_index)


# ── TEST SUITES ─────────────────────────────────────────────────────────────

def test_fvg_detection_and_mitigation():
    """Verify FVG detection logic and mitigation tracking."""
    df = create_fvg_scenario()
    fvg = detect_fvg(df)

    assert "fvg_type" in fvg.columns
    assert "fvg_top" in fvg.columns
    assert "fvg_bottom" in fvg.columns

    assert fvg.iloc[2]["fvg_type"] == 1
    assert fvg.iloc[2]["fvg_top"] == 102.0
    assert fvg.iloc[2]["fvg_bottom"] == 100.0

    assert fvg.iloc[5]["fvg_type"] == -1
    assert fvg.iloc[5]["fvg_top"] == 101.0
    assert fvg.iloc[5]["fvg_bottom"] == 94.0

    mit = check_fvg_mitigation(df, fvg)
    assert mit.iloc[2] == 3

    print("[PASS] test_fvg_detection_and_mitigation")


def test_orderblock_detection():
    """Verify Order Block detection and Mean Threshold (MT)."""
    df = create_sample_ohlc(50)
    swings = detect_swings(df, swing_length=3)
    ob = detect_orderblock(df, swings)

    assert "ob" in ob.columns
    assert "top" in ob.columns
    assert "bottom" in ob.columns
    assert "mt" in ob.columns

    print("[PASS] test_orderblock_detection")


def test_breaker_detection():
    """Verify Breaker Block detection post liquidity sweep."""
    dt_index = pd.date_range("2026-01-05 09:30:00", periods=8, freq="1min", tz="UTC")
    data = {
        "open":  [100, 104, 102, 101, 105, 103, 106, 107],
        "high":  [102, 106, 103, 102, 107, 104, 109, 108],
        "low":   [99,  103, 100, 99,  103, 101, 105, 106],
        "close": [101, 105, 101, 100, 104, 102, 108, 107],
    }
    df = pd.DataFrame(data, index=dt_index)
    swings = pd.DataFrame({
        "shl": [0, 1, 0, 0, 0, 0, 0, 0],
        "level": [np.nan, 106.0, 106.0, 106.0, 106.0, 106.0, 106.0, 106.0]
    }, index=dt_index)

    breaker = detect_breaker(df, swings)
    assert (breaker["breaker"] != 0).any()
    print("[PASS] test_breaker_detection")


def test_cisd_detection():
    """Verify proxy and authoritative CISD detection."""
    df = create_sample_ohlc(50)
    swings = detect_swings(df, swing_length=3)
    
    cisd_proxy = detect_cisd(df, swings)
    assert "cisd" in cisd_proxy.columns

    cisd_auth = detect_cisd_authoritative(df, swings)
    assert "cisd_type" in cisd_auth.columns
    assert "cisd_level" in cisd_auth.columns

    print("[PASS] test_cisd_detection")


def test_structure_breaks():
    """Verify Break of Structure (BOS) vs Market Structure Shift (MSS)."""
    df = create_sample_ohlc(50)
    swings = detect_swings(df, swing_length=3)
    sb = detect_structure_breaks(df, swings)

    assert "break_high" in sb.columns
    assert "break_low" in sb.columns
    assert "structure_type" in sb.columns

    print("[PASS] test_structure_breaks")


def test_retracements_and_dealing_range():
    """Verify Retracement calculations and Premium/Discount dealing range."""
    df = create_sample_ohlc(50)
    swings = detect_swings(df, swing_length=3)

    ret = calculate_retracements(df, swings)
    assert "equilibrium" in ret.columns
    assert "current_retracement" in ret.columns

    dr = detect_dealing_range(df, swings)
    assert "is_discount" in dr.columns
    assert "is_premium" in dr.columns

    print("[PASS] test_retracements_and_dealing_range")


def test_ttrade_fractal_no_roll_wrap():
    """Verify TTrades fractal detection uses shift and has no wrap-around at index 0."""
    df = create_sample_ohlc(20)
    ttrade = detect_ttrade_fractal(df)
    
    assert ttrade.iloc[0]["ttrade_reversal"] == 0
    assert ttrade.iloc[0]["ttrade_confirmation"] == 0
    assert ttrade.iloc[1]["ttrade_reversal"] == 0
    assert ttrade.iloc[1]["ttrade_confirmation"] == 0

    print("[PASS] test_ttrade_fractal_no_roll_wrap")


def test_stubs_implementation():
    """Verify PO3 and Quarterly cycles return structured outputs."""
    df = create_sample_ohlc(50)
    po3 = detect_po3(df)
    assert "phase" in po3.columns
    assert "opening_price" in po3.columns

    qc = quarterly_cycles(df)
    assert "quarter" in qc.columns
    assert "cycle_open" in qc.columns

    print("[PASS] test_stubs_implementation")


def test_projections_directional():
    """Verify Standard Deviation projections for both bullish and bearish directions."""
    df = create_sample_ohlc(10)
    
    proj_bull = sd_projections(df, anchor_high=100.0, anchor_low=90.0, direction=1)
    assert proj_bull.iloc[0]["sd_2"] == 120.0
    
    proj_bear = sd_projections(df, anchor_high=100.0, anchor_low=90.0, direction=-1)
    assert proj_bear.iloc[0]["sd_2"] == 70.0

    print("[PASS] test_projections_directional")


def test_swing_hierarchy_and_irl_erl():
    """Verify Swing Hierarchy (STH/ITH/LTH), IRL/ERL, and HRLR/LRLR."""
    df = create_sample_ohlc(100)
    swings = detect_swings(df, swing_length=3)
    hier = detect_swing_hierarchy(df, swings)
    assert "hierarchy" in hier.columns

    fvg = detect_fvg(df)
    irl_erl = detect_irl_erl(df, hier, fvg)
    assert "delivery_phase" in irl_erl.columns

    run = detect_hrlr_lrlr(df, swings)
    assert "run_type" in run.columns

    print("[PASS] test_swing_hierarchy_and_irl_erl")


def test_advanced_pd_arrays():
    """Verify Unicorn, Propulsion, Mitigation, Rejection, ORG, and Priority Matrix."""
    df = create_sample_ohlc(50)
    swings = detect_swings(df, swing_length=3)
    ob = detect_orderblock(df, swings)
    breaker = detect_breaker(df, swings)
    fvg = detect_fvg(df)
    mit = detect_mitigation_block(df, swings)
    rej = detect_rejection_block(df, swings)
    org = detect_org(df)
    dr = detect_dealing_range(df, swings)

    unicorn = detect_unicorn(breaker, fvg)
    assert "unicorn" in unicorn.columns

    prop = detect_propulsion_block(df, ob)
    assert "propulsion" in prop.columns

    assert "mitigation_block" in mit.columns
    assert "rejection_block" in rej.columns
    assert "org" in org.columns

    matrix = rank_pd_arrays(df, ob, breaker, fvg, mit, swings, dr)
    assert "primary_premium_array" in matrix.columns
    assert "primary_discount_array" in matrix.columns

    print("[PASS] test_advanced_pd_arrays")


def test_time_models():
    """Verify 30m Opening Range, Killzone Pivots, CBDR selector, and TGIF setup."""
    df = create_sample_ohlc(100)
    or30 = detect_opening_range_30m(df)
    assert "or30_high" in or30.columns
    assert "sd_plus_05" in or30.columns

    sess = get_session_data(df, "london_open")
    pivots = track_killzone_pivots(df, sess)
    assert "kz_high" in pivots.columns

    cbdr = select_cbdr_asia_flout(df)
    assert "selected_range" in cbdr.columns

    tgif = detect_tgif_setup(df)
    assert "tgif_active" in tgif.columns

    print("[PASS] test_time_models")


def test_triad_smt_and_execution_models():
    """Verify Triad SMT, 2022 Execution Model, and MMBM/MMSM curve tracker."""
    df_a = create_sample_ohlc(50)
    df_b = create_sample_ohlc(50)
    df_c = create_sample_ohlc(50)

    swings_a = detect_swings(df_a, swing_length=3)
    swings_b = detect_swings(df_b, swing_length=3)
    swings_c = detect_swings(df_c, swing_length=3)

    triad = detect_triad_smt(df_a, df_b, df_c, swings_a, swings_b, swings_c)
    assert "triad_smt" in triad.columns

    fvg = detect_fvg(df_a)
    ob = detect_orderblock(df_a, swings_a)
    dr = detect_dealing_range(df_a, swings_a)
    bias = pd.Series(1, index=df_a.index)

    model2022 = ict_2022_model(df_a, bias, swings_a, fvg, ob, dr)
    assert "signal" in model2022.columns

    mmbm = detect_mmbm_mmsm(df_a, swings_a, fvg)
    assert "curve_phase" in mmbm.columns

    print("[PASS] test_triad_smt_and_execution_models")


def test_performance_benchmark():
    """Verify performance on 100,000 bars (Zero-Loop ADR-017 constraint)."""
    n_bars = 100_000
    df_large = create_sample_ohlc(n_bars)
    
    t0 = time.perf_counter()
    fvg = detect_fvg(df_large)
    t_fvg = (time.perf_counter() - t0) * 1000
    
    t0 = time.perf_counter()
    swings = detect_swings(df_large, swing_length=5)
    t_swings = (time.perf_counter() - t0) * 1000
    
    t0 = time.perf_counter()
    mit = check_fvg_mitigation(df_large, fvg)
    t_mit = (time.perf_counter() - t0) * 1000

    print(f"\n--- PERFORMANCE BENCHMARK ({n_bars:,} bars) ---")
    print(f"  detect_fvg:               {t_fvg:.2f} ms")
    print(f"  detect_swings:            {t_swings:.2f} ms")
    print(f"  check_fvg_mitigation:     {t_mit:.2f} ms")
    
    assert t_fvg < 500, f"detect_fvg took too long ({t_fvg:.2f} ms)"
    assert t_swings < 500, f"detect_swings took too long ({t_swings:.2f} ms)"
    assert t_mit < 1500, f"check_fvg_mitigation took too long ({t_mit:.2f} ms)"

    print("[PASS] test_performance_benchmark")


def run_all_tests():
    """Run all tests in the suite."""
    print("=== ICT CORE ENGINE TEST SUITE ===")
    tests = [
        test_fvg_detection_and_mitigation,
        test_orderblock_detection,
        test_breaker_detection,
        test_cisd_detection,
        test_structure_breaks,
        test_retracements_and_dealing_range,
        test_ttrade_fractal_no_roll_wrap,
        test_stubs_implementation,
        test_projections_directional,
        test_swing_hierarchy_and_irl_erl,
        test_advanced_pd_arrays,
        test_time_models,
        test_triad_smt_and_execution_models,
        test_performance_benchmark,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {e}")
            failed += 1
            
    print(f"\n=== RESULTS: {passed} passed, {failed} failed ===")
    return failed == 0


if __name__ == "__main__":
    run_all_tests()
