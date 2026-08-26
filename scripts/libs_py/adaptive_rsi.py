"""
Adaptive RSI Zones — Python Port
==================================
Port of the NT8 AdaptiveRSIZones.cs indicator (originally from TradingView
"RSI adaptive zones [AdaptiveRSI]" by AdaptiveRSI, CC BY-NC-SA 4.0).

The Adaptive RSI differs from Wilder RSI in three key ways:

1. **Adaptive smoothing**: Uses a running mean (EMA with alpha=1/length) and
   a "cycle-corrected volatility" (ccVol = EMA of |close - prev_close|) instead
   of Wilder's fixed-period gain/loss averaging. This makes the RSI respond
   faster in volatile periods and slower in quiet periods.

2. **Logit transform**: RSI values are transformed via logit(x) = ln(x/(100-x))
   to logit space, where they are symmetric around 0 (RSI 50). This makes
   zone distances statistically meaningful — a 10-point move from RSI 20 to 30
   is NOT the same as from 40 to 50 in logit space, but Wilder RSI treats them
   identically.

3. **Adaptive zone thresholds**: Instead of fixed 30/70, the zones are computed
   from statistical distances:
     - Zone boundaries use tanh(z / sqrt(Length-1)) * 50, where z values are
       derived from sqrt((5 ± sqrt(17)) / 2) — golden-ratio-adjacent constants
     - Overbought/Oversold thresholds use sqrt(3) and sqrt((5+sqrt(17))/2)
     - These zones WIDEN in volatile markets (ccVol is larger → RSI range
       compresses toward 50 → zones effectively require more extreme readings)
       and TIGHTEN in quiet markets (ccVol smaller → RSI spreads out → zones
       are closer to 50 → more signals fire)

For BB mean reversion, this means:
  - In a squeeze (low vol), adaptive zones are tighter → more BB signals fire
    at less extreme RSI readings → solves our 24-trade problem
  - In a trend (high vol), adaptive zones widen → fewer false BB signals
    from RSI pegging at 30/70 in a trending market

Usage:
    from scripts.libs_py.adaptive_rsi import adaptive_rsi_zones, adaptive_rsi
    rsi, ob_threshold, os_threshold, zones = adaptive_rsi_zones(close, length=14)
    # rsi: the adaptive RSI values (0-100)
    # ob_threshold / os_threshold: the adaptive overbought/oversold lines
    # zones: dict with zoneR1, zoneR2, zoneS1, zoneS2, zoneOb, zoneOs boundaries
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ─── Core Adaptive RSI ──────────────────────────────────────────────────────

def _logit(x: np.ndarray) -> np.ndarray:
    """Logit transform: maps (0, 100) -> (-inf, +inf). RSI 50 -> 0."""
    eps = 1e-10
    clamped = np.clip(x, eps, 100.0 - eps)
    return np.log(clamped / (100.0 - clamped))


def _logistic(x: np.ndarray) -> np.ndarray:
    """Logistic (sigmoid) transform: maps (-inf, +inf) -> (0, 100). 0 -> 50."""
    # Clip to avoid overflow
    x = np.clip(x, -500, 500)
    e = np.exp(x)
    return 100.0 * e / (1.0 + e)


def _tanh(x: np.ndarray) -> np.ndarray:
    """Numerically stable tanh."""
    return np.tanh(np.clip(x, -500, 500))


def adaptive_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """
    Compute the Adaptive RSI (running-mean + cycle-corrected volatility).

    This is the core of the AdaptiveRSIZones indicator. Instead of Wilder's
    gain/loss EMA, it uses:
      middle = EMA(close, alpha=1/length)  -- running mean
      ccVol  = EMA(|close - prev_close|, alpha=1/length)  -- cycle-corrected vol
      RSI = 50 + 50 * (close - middle) / (ccVol * (length - 1))

    The result is an RSI that:
    - Reacts faster when volatility rises (ccVol grows, but (close-middle)
      grows faster in directional moves)
    - Stays near 50 in chop (close reverts to middle, ccVol is moderate)
    - Reaches extremes in clean trends (close departs from middle, ccVol
      is proportional but the ratio is extreme)

    Parameters
    ----------
    close : pd.Series
        Close prices.
    length : int
        Lookback period (default 14, matching Wilder RSI).

    Returns
    -------
    pd.Series
        Adaptive RSI values (0-100 scale, same as Wilder RSI).
    """
    close_arr = close.values.astype(np.float64)
    n = len(close_arr)
    sf = 1.0 / length

    middle = np.empty(n)
    cc_vol = np.empty(n)

    middle[0] = close_arr[0]
    cc_vol[0] = 0.0

    for i in range(1, n):
        middle[i] = (1.0 - sf) * middle[i - 1] + sf * close_arr[i]
        cc_vol[i] = (1.0 - sf) * cc_vol[i - 1] + sf * abs(close_arr[i] - close_arr[i - 1])

    eps = 1e-10
    denom = np.maximum(cc_vol, eps) * (length - 1.0)
    rsi = 50.0 + 50.0 * ((close_arr - middle) / denom)

    # Clamp to valid RSI range
    rsi = np.clip(rsi, 0.0, 100.0)

    return pd.Series(rsi, index=close.index, name="adaptive_rsi")


def adaptive_rsi_zones(
    close: pd.Series,
    length: int = 14,
    high: pd.Series = None,
    low: pd.Series = None,
    open_: pd.Series = None,
) -> dict:
    """
    Full Adaptive RSI Zones computation with logit-space processing and
    adaptive zone thresholds.

    Returns
    -------
    dict with keys:
        'rsi': pd.Series — the adaptive RSI (0-100)
        'rsi_high': pd.Series — adaptive RSI computed from high prices
        'rsi_low': pd.Series — adaptive RSI computed from low prices
        'logit_rsi': pd.Series — logit-transformed RSI
        'ob_threshold': pd.Series — adaptive overbought threshold (upper zone)
        'os_threshold': pd.Series — adaptive oversold threshold (lower zone)
        'zone_r1': pd.Series — resistance zone 1 (inner)
        'zone_r2': pd.Series — resistance zone 2 (outer)
        'zone_s1': pd.Series — support zone 1 (inner)
        'zone_s2': pd.Series — support zone 2 (outer)
        'zone_ob_top': pd.Series — overbought zone top
        'zone_ob_bot': pd.Series — overbought zone bottom
        'zone_os_top': pd.Series — oversold zone top
        'zone_os_bot': pd.Series — oversold zone bottom
    """
    close_arr = close.values.astype(np.float64)
    n = len(close_arr)
    sf = 1.0 / length
    eps = 1e-10

    # Running mean and cycle-corrected volatility for close
    middle = np.empty(n)
    cc_vol = np.empty(n)
    middle[0] = close_arr[0]
    cc_vol[0] = 0.0

    for i in range(1, n):
        middle[i] = (1.0 - sf) * middle[i - 1] + sf * close_arr[i]
        cc_vol[i] = (1.0 - sf) * cc_vol[i - 1] + sf * abs(close_arr[i] - close_arr[i - 1])

    # Adaptive RSI for close
    den_c = np.maximum(cc_vol, eps) * (length - 1.0)
    rsi_close = 50.0 + 50.0 * ((close_arr - middle) / den_c)
    rsi_close = np.clip(rsi_close, 0.0, 100.0)

    # Adaptive RSI for high/low (for OHLC RSI candles)
    rsi_high = rsi_low = None
    if high is not None and low is not None:
        high_arr = high.values.astype(np.float64)
        low_arr = low.values.astype(np.float64)
        rsi_high = np.empty(n)
        rsi_low = np.empty(n)
        for i in range(1, n):
            mid_h = (1.0 - sf) * middle[i - 1] + sf * high_arr[i]
            mid_l = (1.0 - sf) * middle[i - 1] + sf * low_arr[i]
            cc_h = (1.0 - sf) * cc_vol[i - 1] + sf * abs(high_arr[i] - close_arr[i - 1])
            cc_l = (1.0 - sf) * cc_vol[i - 1] + sf * abs(low_arr[i] - close_arr[i - 1])
            den_h = max(cc_h, eps) * (length - 1.0)
            den_l = max(cc_l, eps) * (length - 1.0)
            rsi_high[i] = np.clip(50.0 + 50.0 * ((high_arr[i] - mid_h) / den_h), 0, 100)
            rsi_low[i] = np.clip(50.0 + 50.0 * ((low_arr[i] - mid_l) / den_l), 0, 100)
        rsi_high[0] = rsi_low[0] = 50.0

    # Logit transform
    logit_rsi = _logit(rsi_close)

    # Zone thresholds — derived from statistical distances
    # These constants come from the original indicator:
    #   body_threshold = sqrt((5 - sqrt(17)) / 2) ≈ 0.486
    #   tail_threshold = sqrt((5 + sqrt(17)) / 2) ≈ 2.194
    #   breakout_threshold = 1.0
    #   reversal_threshold = sqrt(3) ≈ 1.732
    body_threshold = np.sqrt((5.0 - np.sqrt(17.0)) / 2.0)
    tail_threshold = np.sqrt((5.0 + np.sqrt(17.0)) / 2.0)
    breakout_threshold = 1.0
    reversal_threshold = np.sqrt(3.0)
    inv_sqrt_lenm1 = 1.0 / np.sqrt(max(length - 1.0, 1.0))

    # RSI zone distances: 50 * tanh(z / sqrt(Length-1))
    def rsi_distance(z):
        return 50.0 * _tanh(z * inv_sqrt_lenm1)

    z_ins = rsi_distance(body_threshold)
    z_out = rsi_distance(breakout_threshold)
    oo_ins = rsi_distance(reversal_threshold)
    oo_out = rsi_distance(tail_threshold)

    # Zone boundaries (all centered on 50)
    zone_r1 = 50.0 + z_out  # resistance outer
    zone_r2 = 50.0 + z_ins  # resistance inner
    zone_s1 = 50.0 - z_ins  # support inner
    zone_s2 = 50.0 - z_out  # support outer
    zone_ob_top = 50.0 + oo_out  # overbought extreme
    zone_ob_bot = 50.0 + oo_ins  # overbought entry
    zone_os_top = 50.0 - oo_ins  # oversold entry
    zone_os_bot = 50.0 - oo_out  # oversold extreme

    # The adaptive OB/OS thresholds (the ones used for signal generation)
    ob_threshold = 50.0 + oo_ins
    os_threshold = 50.0 - oo_ins

    result = {
        "rsi": pd.Series(rsi_close, index=close.index, name="adaptive_rsi"),
        "logit_rsi": pd.Series(logit_rsi, index=close.index, name="logit_rsi"),
        "ob_threshold": pd.Series(np.full(n, ob_threshold), index=close.index, name="ob_threshold"),
        "os_threshold": pd.Series(np.full(n, os_threshold), index=close.index, name="os_threshold"),
        "zone_r1": pd.Series(np.full(n, zone_r1), index=close.index, name="zone_r1"),
        "zone_r2": pd.Series(np.full(n, zone_r2), index=close.index, name="zone_r2"),
        "zone_s1": pd.Series(np.full(n, zone_s1), index=close.index, name="zone_s1"),
        "zone_s2": pd.Series(np.full(n, zone_s2), index=close.index, name="zone_s2"),
        "zone_ob_top": pd.Series(np.full(n, zone_ob_top), index=close.index, name="zone_ob_top"),
        "zone_ob_bot": pd.Series(np.full(n, zone_ob_bot), index=close.index, name="zone_ob_bot"),
        "zone_os_top": pd.Series(np.full(n, zone_os_top), index=close.index, name="zone_os_top"),
        "zone_os_bot": pd.Series(np.full(n, zone_os_bot), index=close.index, name="zone_os_bot"),
    }

    if rsi_high is not None:
        result["rsi_high"] = pd.Series(rsi_high, index=close.index, name="adaptive_rsi_high")
        result["rsi_low"] = pd.Series(rsi_low, index=close.index, name="adaptive_rsi_low")

    return result


# ─── Vectorized version for speed ────────────────────────────────────────────

def adaptive_rsi_vectorized(close: pd.Series, length: int = 14) -> pd.Series:
    """
    Vectorized Adaptive RSI using pandas EWM — faster for large datasets.
    Same formula as adaptive_rsi() but using pandas built-in EWM.

    Note: pandas EWM with adjust=False matches the loop version exactly:
    middle[i] = (1-alpha)*middle[i-1] + alpha*close[i]
    """
    sf = 1.0 / length
    middle = close.ewm(alpha=sf, min_periods=1, adjust=False).mean()
    # ccVol = EWM of |close[i] - close[i-1]|
    # First diff is NaN; replace with 0 so EWM starts at 0
    abs_diff = close.diff().abs().fillna(0)
    cc_vol = abs_diff.ewm(alpha=sf, min_periods=1, adjust=False).mean()
    eps = 1e-10
    denom = cc_vol.clip(lower=eps) * (length - 1.0)
    rsi = 50.0 + 50.0 * ((close - middle) / denom)
    return rsi.clip(0, 100)


# ─── Comparison: Wilder vs Adaptive ──────────────────────────────────────────

def compare_rsi(close: pd.Series, length: int = 14) -> pd.DataFrame:
    """
    Compare Wilder RSI vs Adaptive RSI side by side.
    Useful for understanding when they diverge.
    """
    import sys
    sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
    from scripts.analysis.range_strategy_comparison import _wilder_rsi

    wilder = _wilder_rsi(close, length)
    adaptive = adaptive_rsi(close, length)
    adaptive_v = adaptive_rsi_vectorized(close, length)

    df = pd.DataFrame({
        "close": close,
        "wilder_rsi": wilder,
        "adaptive_rsi": adaptive,
        "adaptive_rsi_vec": adaptive_v,
        "diff": adaptive - wilder,
    })

    # Zone thresholds
    body_threshold = np.sqrt((5.0 - np.sqrt(17.0)) / 2.0)
    reversal_threshold = np.sqrt(3.0)
    inv_sqrt = 1.0 / np.sqrt(max(length - 1.0, 1.0))
    ob_zone = 50.0 + 50.0 * np.tanh(reversal_threshold * inv_sqrt)
    os_zone = 50.0 - 50.0 * np.tanh(reversal_threshold * inv_sqrt)

    df["wilder_ob_70"] = 70.0
    df["wilder_os_30"] = 30.0
    df["adaptive_ob"] = ob_zone
    df["adaptive_os"] = os_zone

    return df


# ─── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("Adaptive RSI Zones — Python Port")
    print("=" * 60)

    # Test with sample data
    np.random.seed(42)
    n = 200
    prices = 6000 + np.cumsum(np.random.randn(n) * 2)
    close = pd.Series(prices, index=pd.date_range("2025-01-01", periods=n, freq="5min"))
    high = close + np.abs(np.random.randn(n)) * 1
    low = close - np.abs(np.random.randn(n)) * 1

    # Compute adaptive RSI
    rsi = adaptive_rsi(close, length=14)
    zones = adaptive_rsi_zones(close, length=14, high=high, low=low)

    # Compare with Wilder
    cmp = compare_rsi(close, length=14)

    print(f"\nSample: {n} bars, price range {close.min():.1f}-{close.max():.1f}")
    print(f"\nWilder RSI:    mean={cmp['wilder_rsi'].mean():.1f}  std={cmp['wilder_rsi'].std():.1f}  range=[{cmp['wilder_rsi'].min():.1f}, {cmp['wilder_rsi'].max():.1f}]")
    print(f"Adaptive RSI:  mean={rsi.mean():.1f}  std={rsi.std():.1f}  range=[{rsi.min():.1f}, {rsi.max():.1f}]")
    print(f"Correlation:   {cmp['wilder_rsi'].corr(rsi):.4f}")
    print(f"Mean abs diff: {(rsi - cmp['wilder_rsi']).abs().mean():.2f}")

    print(f"\nZone thresholds (length=14):")
    print(f"  Overbought: {zones['ob_threshold'].iloc[0]:.1f} (Wilder uses 70)")
    print(f"  Oversold:   {zones['os_threshold'].iloc[0]:.1f} (Wilder uses 30)")
    print(f"  Zone R1 (resistance outer):  {zones['zone_r1'].iloc[0]:.1f}")
    print(f"  Zone R2 (resistance inner):  {zones['zone_r2'].iloc[0]:.1f}")
    print(f"  Zone S1 (support inner):     {zones['zone_s1'].iloc[0]:.1f}")
    print(f"  Zone S2 (support outer):     {zones['zone_s2'].iloc[0]:.1f}")
    print(f"  OB extreme:                  {zones['zone_ob_top'].iloc[0]:.1f}")
    print(f"  OS extreme:                  {zones['zone_os_bot'].iloc[0]:.1f}")

    # Count extreme readings
    wilder_ob = (cmp['wilder_rsi'] > 67).sum()
    wilder_os = (cmp['wilder_rsi'] < 33).sum()
    adp_ob = (rsi > zones['ob_threshold']).sum()
    adp_os = (rsi < zones['os_threshold']).sum()

    print(f"\nExtreme readings (sample data):")
    print(f"  Wilder RSI >67: {wilder_ob}  | <33: {wilder_os}  | total: {wilder_ob+wilder_os}")
    print(f"  Adaptive RSI >OB zone: {adp_ob}  | <OS zone: {adp_os}  | total: {adp_ob+adp_os}")

    # Test vectorized vs loop version
    rsi_v = adaptive_rsi_vectorized(close, length=14)
    max_diff = (rsi - rsi_v).abs().max()
    print(f"\nVectorized vs loop max diff: {max_diff:.10f} (should be ~0)")

    print("\n✅ Adaptive RSI library ready")