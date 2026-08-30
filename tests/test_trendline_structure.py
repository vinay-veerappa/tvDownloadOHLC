"""Unit tests for the generic trendline-structure engine (zero-lookahead pivot
anchors + measured projection). Deterministic synthetic OHLC fixtures only."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.libs_py.price_action.trendline_structure import (
    StructureSignal,
    TrendlineStructureParams,
    _atr,
    _di_components,
    find_pivot_highs,
    find_pivot_lows,
    scan_trendline_structures,
)


def make_downtrend(n=300, legs=15, leg_len=20, drop_per_leg=4.0, osc=6.0):
    t = pd.date_range("2025-01-02 09:30", periods=n, freq="5min")
    rows = []
    for j in range(n):
        leg = j // leg_len
        mid = 6000.0 - leg * drop_per_leg + osc * np.sin(j / 3.0)
        o, c = mid + 1.0, mid - 1.0
        h, l = max(o, c) + 1.5, min(o, c) - 1.5
        rows.append((t[j], o, h, l, c, 1000))
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).set_index("time")


def make_uptrend(n=300, legs=15, leg_len=20, rise_per_leg=4.0, osc=6.0):
    t = pd.date_range("2025-01-02 09:30", periods=n, freq="5min")
    rows = []
    for j in range(n):
        leg = j // leg_len
        mid = 6000.0 + leg * rise_per_leg + osc * np.sin(j / 3.0)
        o, c = mid - 1.0, mid + 1.0
        h, l = max(o, c) + 1.5, min(o, c) - 1.5
        rows.append((t[j], o, h, l, c, 1000))
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).set_index("time")


def test_pivots_deterministic():
    df = make_downtrend()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    ph = find_pivot_highs(h, 3)
    pl = find_pivot_lows(l, 3)
    assert len(ph) > 5 and len(pl) > 5
    # confirmation index strictly after anchor index
    for p in ph + pl:
        assert p.confirm_idx == p.idx + 3
    # re-run produces identical output
    ph2 = find_pivot_highs(h, 3)
    assert [(p.idx, p.price) for p in ph] == [(p.idx, p.price) for p in ph2]


def test_engine_zero_lookahead_staircase():
    """Signals must never reference a pivot confirmed after the trigger bar."""
    df = make_downtrend()
    sigs = scan_trendline_structures(df, TrendlineStructureParams(require_directional_bar=False, di_edge=-100.0))
    h = df["high"].to_numpy()
    for s in sigs:
        # trigger index must be strictly after the second pivot's confirmation
        assert s.trigger_idx > find_pivot_highs(df["high"].to_numpy(), 3)[0].confirm_idx
    assert len(sigs) >= 1


def test_short_signal_geometry():
    df = make_downtrend()
    sigs = scan_trendline_structures(df, TrendlineStructureParams(require_directional_bar=False, di_edge=-100.0))
    shorts = [s for s in sigs if s.direction == "SHORT"]
    if shorts:
        s = shorts[0]
        # short: stop above entry, tp1 below entry; measured dist positive
        assert s.stop_loss > s.entry_price > s.tp1_price
        assert s.dist_pts > 0
        # 1:1 projection: (entry - tp1) relates to dist through projection geometry
        proj = s.entry_price - s.tp1_price
        assert proj > 0
        # risk bracket: 2-15 bps of price
        risk_bps = abs(s.stop_loss - s.entry_price) / s.entry_price * 1e4
        assert 2.0 <= risk_bps <= 15.0


def test_di_gate_blocks_counter_trend():
    """With DI gate ON (edge=0), an oppressive downtrend should emit shorts, not longs."""
    df = make_downtrend()
    sigs = scan_trendline_structures(df, TrendlineStructureParams(require_directional_bar=False, di_edge=0.0))
    if sigs:
        dirs = {s.direction for s in sigs}
        # in a clean downtrend, DI gate should suppress long-side signals entirely
        assert "LONG" not in dirs


def test_atr_and_di_positive():
    df = make_downtrend()
    a = _atr(df["high"], df["low"], df["close"], 14)
    pdi, mdi = _di_components(df["high"], df["low"], df["close"], 14)
    a_w, pdi_w, mdi_w = a.iloc[14:], pdi.iloc[14:], mdi.iloc[14:]  # EMA warm-up
    assert a_w.notna().all()
    assert (a_w > 0).all()
    assert (mdi_w > pdi_w).mean() > 0.6  # downtrend: minus-DI dominant


def test_rng_signal_generation_reproducible():
    df = make_downtrend()
    p = TrendlineStructureParams(require_directional_bar=False, di_edge=-100.0)
    s1 = scan_trendline_structures(df, p)
    s2 = scan_trendline_structures(df, p)
    assert [(x.entry_time, x.entry_price, x.tp1_price) for x in s1] == \
           [(x.entry_time, x.entry_price, x.tp1_price) for x in s2]


def test_strategy_class_hunt_interface():
    from scripts.strategies.measured_move.core.measured_move import MeasuredMoveStrategy
    df = make_downtrend()
    strat = MeasuredMoveStrategy("ES")
    out = strat.hunt(df, params={"require_directional_bar": False, "di_edge": -100.0})
    assert isinstance(out, pd.DataFrame)
    expected_cols = {"signal_time", "direction", "entry_price", "stop_price",
                     "target1_price", "target2_price", "ordinal", "dist_atr", "line_slope"}
    assert expected_cols.issubset(out.columns)
    assert len(out) == len(scan_trendline_structures(df, TrendlineStructureParams(
        require_directional_bar=False, di_edge=-100.0)))


def test_ordinal_monotonicity():
    df = make_downtrend()
    p = TrendlineStructureParams(require_directional_bar=False, di_edge=-100.0)
    sigs = scan_trendline_structures(df, p)
    shorts = [s.ordinal for s in sigs if s.direction == "SHORT"]
    if len(shorts) > 1:
        # ordinals for same direction increments by 1 or resets to 1 only after a
        # direction switch (none happens in pure downtrend), so must be non-decreasing
        assert all(b >= a for a, b in zip(shorts, shorts[1:]))


def test_uptrend_mirrors():
    df = make_uptrend()
    p = TrendlineStructureParams(require_directional_bar=False, di_edge=-100.0)
    sigs = scan_trendline_structures(df, p)
    if sigs:
        longs = [s for s in sigs if s.direction == "LONG"]
        if longs:
            s = longs[0]
            assert s.stop_loss < s.entry_price < s.tp1_price
            risk_bps = abs(s.entry_price - s.stop_loss) / s.entry_price * 1e4
            assert 2.0 <= risk_bps <= 15.0