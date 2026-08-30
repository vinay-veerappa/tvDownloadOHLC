"""
Generic trendline-structure engine ("measured move" / pivot-anchored trendline break).

Zero-lookahead by construction: swing pivots are anchored only `k` bars after they
complete (confirmation index = pivot_idx + k), and every evaluation at bar i uses
only bars <= i. Deterministic anchors = the two most recent confirmed swing
pivots, so no manual trendline drawing or hindsight curve-fitting.

Geometry (documented design, ADR-consistent):
  - Distances are VERTICAL (price-axis), not perpendicular; documented limitation.
  - Measured projection: dist = line(extreme) - extreme_low  (shorts),
    mirrored for longs; target = extreme_low - proj_mult * dist.
  - Invalidation: a close beyond the trendline kills the structure.

Consumers: scripts/strategies/measured_move (Marci-style measured move),
any strategy wanting trendline-break context, or standalone scanning.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class Pivot:
    idx: int
    price: float
    confirm_idx: int


@dataclass
class TrendlineStructureParams:
    pivot_lookback: int = 3
    touch_buf_atr: float = 0.10
    stop_buf_atr: float = 0.25
    invalid_buf_atr: float = 0.10
    max_age_bars: int = 60
    proj_mult: float = 1.0
    proj_min_atr: float = 0.5
    min_risk_bps: float = 2.0
    max_risk_bps: float = 15.0
    atr_period: int = 14
    di_period: int = 14
    di_edge: float = 0.0
    use_trend_gate: bool = True
    require_directional_bar: bool = True


@dataclass
class StructureSignal:
    direction: str
    entry_price: float
    stop_loss: float
    tp1_price: float
    tp2_price: float
    entry_time: pd.Timestamp
    trigger_idx: int
    ordinal: int
    dist_pts: float
    dist_atr: float
    line_slope: float
    extreme_low: float = np.nan
    extreme_high: float = np.nan


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def _di_components(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series]:
    """Wilder +DI / -DI (direction dominance for trend gating)."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    up = high.diff()
    dn = -low.diff()
    plus_dm = up.where((up > dn) & (up > 0), 0.0)
    minus_dm = dn.where((dn > up) & (dn > 0), 0.0)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
    return plus_di, minus_di


def find_pivot_highs(high: np.ndarray, k: int) -> List[Pivot]:
    """Swing highs confirmed only after k subsequent bars (first occurrence on ties)."""
    pivots: List[Pivot] = []
    n = len(high)
    for j in range(k, n - k):
        w = high[j - k: j + k + 1]
        if high[j] == w.max() and int(np.argmax(w)) == k:
            pivots.append(Pivot(j, float(high[j]), j + k))
    return pivots


def find_pivot_lows(low: np.ndarray, k: int) -> List[Pivot]:
    pivots: List[Pivot] = []
    n = len(low)
    for j in range(k, n - k):
        w = low[j - k: j + k + 1]
        if low[j] == w.min() and int(np.argmin(w)) == k:
            pivots.append(Pivot(j, float(low[j]), j + k))
    return pivots


def _line_value(p1: float, i1: int, p2: float, i2: int, i: int) -> float:
    return p1 + (p2 - p1) * (i - i1) / (i2 - i1)


def scan_trendline_structures(df: pd.DataFrame, params: TrendlineStructureParams) -> List[StructureSignal]:
    """Detect pivot-anchored trendline-break structures on any OHLC bar series.

    Emits one signal per completed structure (short on descending pivot-high
    lines broken back downward, long on ascending pivot-low lines reclaimed).
    """
    if len(df) < max(params.atr_period, 2 * params.pivot_lookback + 1) + 5:
        return []

    idx = df.index
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)

    atr = _atr(df["high"], df["low"], df["close"], params.atr_period).to_numpy()
    plus_di, minus_di = _di_components(df["high"], df["low"], df["close"], params.di_period)
    pdi = plus_di.to_numpy()
    mdi = minus_di.to_numpy()

    ph = find_pivot_highs(h, params.pivot_lookback)
    pl = find_pivot_lows(l, params.pivot_lookback)
    ph_i = 0
    pl_i = 0

    sigs: List[StructureSignal] = []
    ordinal = {"short": 0, "long": 0}
    last_dir = {"short": None, "long": None}

    for _cur_i in range(params.pivot_lookback + 1, len(c)):
        i = _cur_i
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        a = float(atr[i])

        while ph_i < len(ph) and ph[ph_i].confirm_idx <= i:
            ph_i += 1
        while pl_i < len(pl) and pl[pl_i].confirm_idx <= i:
            pl_i += 1

        if ph_i >= 2:
            p2, p1 = ph[ph_i - 1], ph[ph_i - 2]
            if p2.idx - p1.idx >= 1:
                sig = _try_signal(
                    o, h, l, c, i, p1, p2, "short", a, params,
                    pdi, mdi, idx, ordinal, last_dir,
                )
                if sig is not None:
                    sigs.append(sig)

        if pl_i >= 2:
            p2, p1 = pl[pl_i - 1], pl[pl_i - 2]
            if p2.idx - p1.idx >= 1:
                sig = _try_signal(
                    o, h, l, c, i, p1, p2, "long", a, params,
                    pdi, mdi, idx, ordinal, last_dir,
                )
                if sig is not None:
                    sigs.append(sig)

    return sigs


def _try_signal(
    o, h, l, c: np.ndarray,
    i: int,
    p1: "Pivot", p2: "Pivot",
    direction: str,
    a: float,
    params: TrendlineStructureParams,
    pdi: np.ndarray, mdi: np.ndarray,
    idx: pd.Index,
    ordinal: dict,
    last_dir: dict,
) -> "StructureSignal | None":
    is_short = direction == "short"

    line_now = _line_value(p1.price, p1.idx, p2.price, p2.idx, i)
    if line_now <= 0:
        return None

    lo = min(p1.idx, p2.idx)

    slope_ok = (p2.price < p1.price) if is_short else (p2.price > p1.price)
    if not slope_ok:
        return None

    if params.max_age_bars > 0 and (i - p2.confirm_idx) > params.max_age_bars:
        return None

    win_lo = slice(lo, i + 1)
    if is_short:
        extreme_idx = lo + int(np.argmin(l[win_lo]))
        extreme = float(l[extreme_idx])
        struct_high = float(np.max(h[win_lo]))
        dist = line_now - extreme
    else:
        extreme_idx = lo + int(np.argmax(h[win_lo]))
        extreme = float(h[extreme_idx])
        struct_low = float(np.min(l[win_lo]))
        dist = extreme - line_now

    if dist < params.proj_min_atr * a:
        return None

    if params.use_trend_gate:
        di_spread = (mdi[i] - pdi[i]) if is_short else (pdi[i] - mdi[i])
        if di_spread < params.di_edge:
            return None

    touch = (h[i] >= line_now - params.touch_buf_atr * a) if is_short else (l[i] <= line_now + params.touch_buf_atr * a)
    if not touch:
        return None

    rejected = (c[i] < line_now - params.invalid_buf_atr * a) if is_short else (c[i] > line_now + params.invalid_buf_atr * a)
    if not rejected:
        return None

    if params.require_directional_bar:
        if is_short and c[i] >= o[i]:
            return None
        if not is_short and c[i] <= o[i]:
            return None
        prev_c = c[i - 1]
        if is_short and c[i] >= prev_c:
            return None
        if not is_short and c[i] <= prev_c:
            return None

    entry = float(c[i])
    if is_short:
        stop = struct_high + params.stop_buf_atr * a
        tp1 = extreme - params.proj_mult * dist
        tp2 = tp1 - params.proj_mult * dist
    else:
        stop = struct_low - params.stop_buf_atr * a
        tp1 = extreme + params.proj_mult * dist
        tp2 = tp1 + params.proj_mult * dist

    risk = abs(entry - stop)
    risk_bps = (risk / entry) * 1e4 if entry > 0 else 0.0
    if risk <= 0 or risk_bps < params.min_risk_bps or risk_bps > params.max_risk_bps:
        return None

    if is_short and not (tp1 < entry < stop):
        return None
    if not is_short and not (stop < entry < tp1):
        return None

    if last_dir[direction] == direction:
        ordinal[direction] += 1
    else:
        ordinal[direction] = 1
    last_dir[direction] = direction

    sig = StructureSignal(
        direction="SHORT" if is_short else "LONG",
        entry_price=entry,
        stop_loss=float(stop),
        tp1_price=float(tp1),
        tp2_price=float(tp2),
        entry_time=idx[i],
        trigger_idx=i,
        ordinal=ordinal[direction],
        dist_pts=float(dist),
        dist_atr=float(dist / a),
        line_slope=float((p2.price - p1.price) / (p2.idx - p1.idx)),
        extreme_low=float(extreme) if is_short else np.nan,
        extreme_high=extreme if not is_short else np.nan,
    )
    return sig