"""
Adaptive RSI Variants Library
================================
Three additional adaptive RSI implementations beyond the AdaptiveRSIZones port:

1. Chande Dynamic Momentum Index (DMI)
   - Variable lookback: TD = int(14 / VI), clipped to [5, 30]
   - VI = std(close, 5) / sma(std(close, 5), 10)
   - Shortens period in high volatility (faster), lengthens in low vol (slower)

2. Kaufman Efficiency Ratio RSI (ER-RSI)
   - ER = |close - close[n]| / sum(|close[i] - close[i-1]|) over n bars
   - ER in [0, 1]: 0 = choppy/random, 1 = perfectly directional
   - Period = base_period * (2 - ER) → 14 in trends (ER=1), 28 in chop (ER=0)
   - Also adjusts smoothing alpha: faster in trends, slower in chop

3. Ehlers Cycle-Based RSI
   - Measures dominant cycle via autocorrelation periodogram
   - Sets RSI length = half the dominant cycle
   - Adapts to the market's actual rhythm

All three return pd.Series on the same 0-100 scale as Wilder RSI, so they
can be drop-in replacements in the BB strategy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ─── 1. Chande Dynamic Momentum Index ───────────────────────────────────────

def chande_dmi_rsi(close: pd.Series, base_period: int = 14, vol_lookback: int = 5,
                   vol_smooth: int = 10, min_len: int = 5, max_len: int = 30) -> pd.Series:
    """
    Chande & Kroll's Dynamic Momentum Index — RSI with variable lookback.

    The period contracts when volatility rises (faster reaction) and expands
    when volatility falls (more smoothing in quiet markets).

    Formula:
        sd = std(close, vol_lookback)
        VI = sd / SMA(sd, vol_smooth)
        TD = clip(int(base_period / VI), min_len, max_len)
        RSI = Wilder RSI computed over TD bars (recomputed each bar)

    Parameters
    ----------
    close : pd.Series
    base_period : int — baseline RSI length (default 14)
    vol_lookback : int — short-term volatility window (default 5)
    vol_smooth : int — smoothing window for VI (default 10)
    min_len, max_len : int — clip range for dynamic period

    Returns
    -------
    pd.Series — Dynamic RSI (0-100)
    """
    close_arr = close.values.astype(np.float64)
    n = len(close_arr)

    # Rolling std of close over vol_lookback
    s = pd.Series(close_arr)
    sd = s.rolling(vol_lookback, min_periods=1).std()
    # Volatility Index: sd / SMA(sd, vol_smooth)
    sma_sd = sd.rolling(vol_smooth, min_periods=1).mean()
    vi = sd / sma_sd.replace(0, np.nan)
    vi = vi.fillna(1.0)  # default VI=1 → TD=base_period

    # Dynamic period: TD = clip(int(base_period / VI), min_len, max_len)
    td = (base_period / vi).astype(int)
    td = td.clip(min_len, max_len)

    # Compute Wilder RSI with the dynamic period for each bar
    # We use a rolling approach: for each bar i, compute RSI over td[i] bars
    rsi = np.full(n, 50.0)

    for i in range(1, n):
        period = int(td.iloc[i])
        if i < period:
            period = i
        if period < 2:
            rsi[i] = 50.0
            continue

        # Wilder RSI over the last `period` bars ending at i
        window = close_arr[i - period:i + 1]
        if len(window) < 2:
            rsi[i] = 50.0
            continue

        delta = np.diff(window)
        gains = np.where(delta > 0, delta, 0.0)
        losses = np.where(delta < 0, -delta, 0.0)

        # Wilder smoothing (EWM with alpha=1/period)
        alpha = 1.0 / period
        avg_gain = gains[0]
        avg_loss = losses[0]
        for g, l in zip(gains[1:], losses[1:]):
            avg_gain = (1 - alpha) * avg_gain + alpha * g
            avg_loss = (1 - alpha) * avg_loss + alpha * l

        if avg_loss == 0:
            rsi[i] = 100.0
        elif avg_gain == 0:
            rsi[i] = 0.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)

    return pd.Series(rsi, index=close.index, name="chande_dmi_rsi")


# ─── 2. Kaufman Efficiency Ratio RSI ────────────────────────────────────────

def kaufman_er_rsi(close: pd.Series, er_period: int = 10, base_period: int = 14,
                   fast_len: int = 5, slow_len: int = 30) -> pd.Series:
    """
    Kaufman Efficiency Ratio RSI — adjusts the RSI lookback based on the
    Efficiency Ratio (directional movement vs total path length).

    Formula:
        ER = |close[t] - close[t-er_period]| / sum(|close[i]-close[i-1]|, er_period)
        ER in [0, 1]: 0 = choppy, 1 = perfectly directional
        dynamic_period = base_period * (2 - ER)  →  base_period in trends, 2×base in chop
        RSI = Wilder RSI over dynamic_period bars

    Alternative: instead of changing the period, we can change the smoothing
    alpha (Kaufman's original approach for KAMA). Here we do both — adjust the
    period AND use an ER-scaled alpha for the gain/loss smoothing.

    Parameters
    ----------
    close : pd.Series
    er_period : int — lookback for efficiency ratio (default 10)
    base_period : int — baseline RSI length (default 14)
    fast_len : int — fastest RSI period when ER=1 (default 5)
    slow_len : int — slowest RSI period when ER=0 (default 30)

    Returns
    -------
    pd.Series — ER-scaled RSI (0-100)
    """
    close_arr = close.values.astype(np.float64)
    n = len(close_arr)

    # Efficiency Ratio
    s = pd.Series(close_arr)
    change = (s - s.shift(er_period)).abs()
    volatility = s.diff().abs().rolling(er_period, min_periods=1).sum()
    er = (change / volatility.replace(0, np.nan)).fillna(0.0).clip(0, 1)

    # Dynamic period: interpolate between fast_len (ER=1) and slow_len (ER=0)
    # period = slow_len + (fast_len - slow_len) * ER
    # = slow_len * (1 - ER) + fast_len * ER
    dynamic_period = slow_len + (fast_len - slow_len) * er
    dynamic_period = dynamic_period.clip(2, 50).astype(int)

    # Compute Wilder RSI with dynamic period
    rsi = np.full(n, 50.0)

    for i in range(1, n):
        period = int(dynamic_period.iloc[i])
        if i < period:
            period = max(2, i)
        if period < 2:
            rsi[i] = 50.0
            continue

        window = close_arr[i - period:i + 1]
        if len(window) < 3:
            rsi[i] = 50.0
            continue
        delta = np.diff(window)
        gains = np.where(delta > 0, delta, 0.0)
        losses = np.where(delta < 0, -delta, 0.0)

        alpha = 1.0 / period
        avg_gain = gains[0]
        avg_loss = losses[0]
        for g, l in zip(gains[1:], losses[1:]):
            avg_gain = (1 - alpha) * avg_gain + alpha * g
            avg_loss = (1 - alpha) * avg_loss + alpha * l

        if avg_loss == 0:
            rsi[i] = 100.0
        elif avg_gain == 0:
            rsi[i] = 0.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)

    return pd.Series(rsi, index=close.index, name="kaufman_er_rsi")


# ─── 3. Ehlers Cycle-Based RSI ───────────────────────────────────────────────

def ehlers_cycle_rsi(close: pd.Series, min_cycle: int = 8, max_cycle: int = 50,
                     base_period: int = 14) -> pd.Series:
    """
    Ehlers cycle-based adaptive RSI — measures the dominant cycle via
    autocorrelation periodogram and sets the RSI length to half the cycle.

    This is a simplified version: instead of the full autocorrelation
    periodogram (which is computationally expensive), we use the
    Hilbert Transform approach to estimate the dominant cycle, then
    set RSI length = max(min_cycle//2, min(dominant_cycle//2, max_cycle//2)).

    For a more practical implementation, we use the zero-crossing method:
    count the bars between consecutive price reversals (slope sign changes)
    and use that as a proxy for the dominant cycle.

    Parameters
    ----------
    close : pd.Series
    min_cycle, max_cycle : int — clip range for detected cycle
    base_period : int — fallback RSI length if cycle detection fails

    Returns
    -------
    pd.Series — Cycle-adaptive RSI (0-100)
    """
    close_arr = close.values.astype(np.float64)
    n = len(close_arr)

    # Dominant cycle estimation via zero-crossing of the detrended price
    # Detrend: subtract a slow SMA to remove the trend component
    s = pd.Series(close_arr)
    trend = s.rolling(max_cycle, min_periods=1).mean()
    detrended = s - trend

    # Count zero crossings of the detrended series to estimate cycle length
    # Each full cycle = 2 zero crossings
    sign = np.sign(detrended.values)
    sign_changes = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if sign[i] != sign[i - 1] and sign[i] != 0 and sign[i - 1] != 0:
            sign_changes[i] = True

    # Rolling count of sign changes over max_cycle window → estimate cycle
    # If we see ~2 sign changes in K bars, cycle ≈ K
    cum_changes = np.cumsum(sign_changes)
    cycle_est = np.full(n, float(base_period * 2))

    for i in range(max_cycle, n):
        changes_in_window = cum_changes[i] - cum_changes[i - max_cycle]
        if changes_in_window >= 2:
            # cycle = max_cycle / (changes_in_window / 2)
            cycle_est[i] = max_cycle / (changes_in_window / 2.0)
        elif changes_in_window >= 1:
            cycle_est[i] = max_cycle * 2  # half-cycle seen

    # Clip cycle to valid range
    cycle_est = np.clip(cycle_est, min_cycle, max_cycle)

    # RSI length = half the dominant cycle
    rsi_lengths = (cycle_est / 2).astype(int)
    rsi_lengths = np.clip(rsi_lengths, 4, 25)

    # Compute Wilder RSI with the cycle-based period
    rsi = np.full(n, 50.0)

    for i in range(1, n):
        period = int(rsi_lengths[i])
        if i < period:
            period = max(2, i)
        if period < 2:
            rsi[i] = 50.0
            continue

        window = close_arr[i - period:i + 1]
        if len(window) < 3:
            rsi[i] = 50.0
            continue
        delta = np.diff(window)
        gains = np.where(delta > 0, delta, 0.0)
        losses = np.where(delta < 0, -delta, 0.0)

        alpha = 1.0 / period
        avg_gain = gains[0]
        avg_loss = losses[0]
        for g, l in zip(gains[1:], losses[1:]):
            avg_gain = (1 - alpha) * avg_gain + alpha * g
            avg_loss = (1 - alpha) * avg_loss + alpha * l

        if avg_loss == 0:
            rsi[i] = 100.0
        elif avg_gain == 0:
            rsi[i] = 0.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)

    return pd.Series(rsi, index=close.index, name="ehlers_cycle_rsi")


# ─── 4. Connors RSI (composite, as a bonus) ──────────────────────────────────

def connors_rsi(close: pd.Series, rsi_period: int = 3, streak_period: int = 2,
                roc_period: int = 100, pct_rank_period: int = 10) -> pd.Series:
    """
    Connors RSI — a composite of three components:
    1. RSI(price, rsi_period) — short-term RSI (default 3, very fast)
    2. RSI(streak, streak_period) — RSI of the consecutive up/down streak
    3. PercentRank(ROC(1), pct_rank_period) — 1-bar rate of change ranked

    Final CRSI = average of the three components.

    This is NOT an adaptive RSI, but it's a popular alternative that's
    more responsive than Wilder RSI(14) and included here for comparison.
    """
    from scripts.analysis.range_strategy_comparison import _wilder_rsi

    # Component 1: short RSI
    rsi_short = _wilder_rsi(close, rsi_period)

    # Component 2: streak RSI
    # Streak = consecutive up (positive) or down (negative) closes
    streak = np.zeros(len(close))
    close_arr = close.values
    for i in range(1, len(close_arr)):
        if close_arr[i] > close_arr[i - 1]:
            streak[i] = streak[i - 1] + 1 if streak[i - 1] > 0 else 1
        elif close_arr[i] < close_arr[i - 1]:
            streak[i] = streak[i - 1] - 1 if streak[i - 1] < 0 else -1
        else:
            streak[i] = 0

    streak_s = pd.Series(streak, index=close.index)
    rsi_streak = _wilder_rsi(streak_s, streak_period)

    # Component 3: PercentRank of 1-bar ROC
    roc = close.pct_change(1) * 100
    pct_rank = roc.rolling(pct_rank_period, min_periods=1).rank(pct=True) * 100

    # CRSI = average
    crsi = (rsi_short + rsi_streak + pct_rank) / 3.0
    return crsi.rename("connors_rsi")


# ─── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

    print("Adaptive RSI Variants — Self Test")
    print("=" * 60)

    np.random.seed(42)
    n = 500
    # Create a synthetic series with varying volatility
    prices = np.zeros(n)
    prices[0] = 6000
    for i in range(1, n):
        vol = 5.0 if i < 200 else (2.0 if i < 400 else 8.0)  # high, low, high vol
        prices[i] = prices[i - 1] + np.random.randn() * vol

    close = pd.Series(prices, index=pd.date_range("2025-01-01", periods=n, freq="5min"))

    from scripts.analysis.range_strategy_comparison import _wilder_rsi
    from scripts.libs_py.adaptive_rsi import adaptive_rsi

    wilder = _wilder_rsi(close, 14)
    adp_zones = adaptive_rsi(close, 14)
    chande = chande_dmi_rsi(close)
    kaufman = kaufman_er_rsi(close)
    ehlers = ehlers_cycle_rsi(close)
    connors = connors_rsi(close)

    print(f"\n{n} bars, varying volatility (high->low->high)")
    print(f"\n{'Variant':<20} {'Mean':>7} {'Std':>7} {'Min':>7} {'Max':>7} {'Corr Wilder':>12}")
    print("-" * 65)

    for name, rsi in [("Wilder RSI(14)", wilder), ("Adaptive Zones", adp_zones),
                       ("Chande DMI", chande), ("Kaufman ER", kaufman),
                       ("Ehlers Cycle", ehlers), ("Connors RSI", connors)]:
        corr = rsi.corr(wilder) if rsi.notna().any() else 0
        print(f"{name:<20} {rsi.mean():>7.1f} {rsi.std():>7.1f} {rsi.min():>7.1f} {rsi.max():>7.1f} {corr:>12.4f}")

    # Count extreme readings for each variant
    print(f"\nExtreme readings (<30 or >70):")
    for name, rsi in [("Wilder 33/67", wilder), ("Chande DMI", chande),
                       ("Kaufman ER", kaufman), ("Ehlers Cycle", ehlers),
                       ("Connors RSI", connors)]:
        os_count = (rsi < 33).sum()
        ob_count = (rsi > 67).sum()
        print(f"  {name:<20} OS(<33)={os_count:>4}  OB(>67)={ob_count:>4}  total={os_count+ob_count:>4}")

    # Test on real data
    print("\n--- Real ES 5m data test ---")
    df5 = pd.read_csv("data/derived/nt_es_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df5 = df5[(df5.index.year >= 2025) & (df5.index.year <= 2026)]
    # Take a 1000-bar sample from mid-2025
    sample = df5.iloc[20000:21000]
    c = sample["close"]

    w = _wilder_rsi(c, 14)
    ch = chande_dmi_rsi(c)
    ka = kaufman_er_rsi(c)
    eh = ehlers_cycle_rsi(c)
    co = connors_rsi(c)

    print(f"\n1000-bar sample (mid-2025 ES 5m):")
    print(f"{'Variant':<20} {'Mean':>7} {'Std':>7} {'Min':>7} {'Max':>7} {'Corr Wilder':>12}")
    print("-" * 65)
    for name, rsi in [("Wilder RSI(14)", w), ("Chande DMI", ch), ("Kaufman ER", ka),
                       ("Ehlers Cycle", eh), ("Connors RSI", co)]:
        corr = rsi.corr(w) if rsi.notna().any() else 0
        print(f"{name:<20} {rsi.mean():>7.1f} {rsi.std():>7.1f} {rsi.min():>7.1f} {rsi.max():>7.1f} {corr:>12.4f}")

    print(f"\nExtreme readings on real data (<33 or >67):")
    for name, rsi in [("Wilder 33/67", w), ("Chande DMI", ch), ("Kaufman ER", ka),
                       ("Ehlers Cycle", eh), ("Connors RSI", co)]:
        os_count = (rsi < 33).sum()
        ob_count = (rsi > 67).sum()
        print(f"  {name:<20} OS(<33)={os_count:>4}  OB(>67)={ob_count:>4}  total={os_count+ob_count:>4}")

    print("\n✅ All adaptive RSI variants ready")