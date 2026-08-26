"""
Adaptive RSI vs Wilder RSI — Signal Frequency & Edge Comparison on BB Strategy
================================================================================
Tests whether replacing Wilder RSI with Adaptive RSI in the BB mean reversion
strategy increases trade frequency without degrading edge.

Also tests the adaptive zone thresholds (72.3/27.7 for length=14) vs the
fixed 33/67 we currently use.
"""
import sys, io
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import pandas as pd
import numpy as np

from scripts.analysis.range_strategy_comparison import build_day_context, _wilder_rsi, _adx
from scripts.libs_py.adaptive_rsi import adaptive_rsi, adaptive_rsi_zones

def load_data(sym="ES"):
    df1 = pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df5 = pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df1 = df1[(df1.index.year>=2025)&(df1.index.year<=2026)]
    df5 = df5[(df5.index.year>=2025)&(df5.index.year<=2026)]
    tr2 = pd.concat([
        df1.resample("D").agg({"high":"max","low":"min"}).dropna().pipe(lambda d: d["high"]-d["low"]),
        (df1.resample("D").agg({"high":"max","close":"last"}).dropna()["high"] - df1.resample("D").agg({"close":"last"}).dropna()["close"].shift(1)).abs(),
        (df1.resample("D").agg({"low":"min","close":"last"}).dropna()["low"] - df1.resample("D").agg({"close":"last"}).dropna()["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    daily_atr = tr2.rolling(10, min_periods=1).mean()
    df1["trade_date"] = df1.index.date
    df1.loc[df1.index.hour>=18, "trade_date"] = (df1.loc[df1.index.hour>=18].index + pd.Timedelta(days=1)).date
    return df1, df5, daily_atr


def run_comparison(df1, df5, daily_atr):
    """Compare Wilder RSI 33/67 vs Adaptive RSI with adaptive zones."""
    unique_dates = sorted(df1["trade_date"].unique())

    # Counters for each RSI variant
    results = {
        "wilder_33_67": {"touches": 0, "rsi_extreme": 0, "hooks": 0, "adx_pass": 0, "final": 0},
        "wilder_35_65": {"touches": 0, "rsi_extreme": 0, "hooks": 0, "adx_pass": 0, "final": 0},
        "adaptive_zones": {"touches": 0, "rsi_extreme": 0, "hooks": 0, "adx_pass": 0, "final": 0},
        "adaptive_relaxed": {"touches": 0, "rsi_extreme": 0, "hooks": 0, "adx_pass": 0, "final": 0},
    }

    # Also collect trade-level data for outcome comparison
    trades = []

    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
        if ctx is None:
            continue

        ib_bars = ctx.session_5m.get("NY_AM")
        ib_ok = True
        if ib_bars is not None and len(ib_bars) >= 6:
            ib_range = ib_bars["high"].iloc[:6].max() - ib_bars["low"].iloc[:6].min()
            if ib_range > 0.40 * ctx.atr_val:
                ib_ok = False

        for sess in ("NY_MIDDAY", "NY_PM"):
            bars_5m = ctx.session_5m.get(sess)
            if bars_5m is None or len(bars_5m) < 30:
                continue

            close = bars_5m["close"]
            high = bars_5m["high"]
            low = bars_5m["low"]
            sma = close.rolling(20).mean()
            std = close.rolling(20).std()
            upper = sma + 2.0 * std
            lower = sma - 2.0 * std

            wilder = _wilder_rsi(close, 14)
            adp = adaptive_rsi(close, 14)
            adp_zones = adaptive_rsi_zones(close, 14, high=high, low=low)
            adp_ob = adp_zones["ob_threshold"].iloc[0]
            adp_os = adp_zones["os_threshold"].iloc[0]

            # Relaxed adaptive: use zone R1/S1 instead of OB/OS
            adp_relaxed_ob = adp_zones["zone_r1"].iloc[0]
            adp_relaxed_os = adp_zones["zone_s1"].iloc[0]

            adx_s = _adx(high, low, close, 14)
            atr = ctx.atr_val if not np.isnan(ctx.atr_val) and ctx.atr_val > 0 else 20.0

            for i in range(2, len(bars_5m)):
                curr_time = bars_5m.index[i]
                if curr_time.time() < pd.Timestamp("11:30:00").time():
                    continue
                if curr_time.hour >= 13 and curr_time.hour < 14:
                    continue  # lunch skip

                long_touch = close.iloc[i-1] < lower.iloc[i-1]
                short_touch = close.iloc[i-1] > upper.iloc[i-1]
                if not long_touch and not short_touch:
                    continue

                direction = "LONG" if long_touch else "SHORT"

                # ADX gate
                adx_val = adx_s.iloc[i]
                adx_ok = not (not np.isnan(adx_val) and adx_val >= 25.0)
                if not ib_ok:
                    continue

                # Hook back inside
                long_hook = long_touch and close.iloc[i] > lower.iloc[i] and wilder.iloc[i] > wilder.iloc[i-1] and close.iloc[i] < sma.iloc[i] and wilder.iloc[i] < 50
                short_hook = short_touch and close.iloc[i] < upper.iloc[i] and wilder.iloc[i] < wilder.iloc[i-1] and close.iloc[i] > sma.iloc[i] and wilder.iloc[i] > 50

                # Adaptive hook: same logic but using adaptive RSI
                long_hook_adp = long_touch and close.iloc[i] > lower.iloc[i] and adp.iloc[i] > adp.iloc[i-1] and close.iloc[i] < sma.iloc[i] and adp.iloc[i] < 50
                short_hook_adp = short_touch and close.iloc[i] < upper.iloc[i] and adp.iloc[i] < adp.iloc[i-1] and close.iloc[i] > sma.iloc[i] and adp.iloc[i] > 50

                # --- Wilder 33/67 ---
                results["wilder_33_67"]["touches"] += 1
                w_extreme = (long_touch and wilder.iloc[i-1] < 33) or (short_touch and wilder.iloc[i-1] > 67)
                if w_extreme:
                    results["wilder_33_67"]["rsi_extreme"] += 1
                    if long_hook or short_hook:
                        results["wilder_33_67"]["hooks"] += 1
                        if adx_ok:
                            results["wilder_33_67"]["adx_pass"] += 1
                            results["wilder_33_67"]["final"] += 1

                # --- Wilder 35/65 (relaxed) ---
                results["wilder_35_65"]["touches"] += 1
                w_extreme2 = (long_touch and wilder.iloc[i-1] < 35) or (short_touch and wilder.iloc[i-1] > 65)
                if w_extreme2:
                    results["wilder_35_65"]["rsi_extreme"] += 1
                    if long_hook or short_hook:
                        results["wilder_35_65"]["hooks"] += 1
                        if adx_ok:
                            results["wilder_35_65"]["adx_pass"] += 1
                            results["wilder_35_65"]["final"] += 1

                # --- Adaptive RSI with adaptive zones (OB/OS thresholds) ---
                results["adaptive_zones"]["touches"] += 1
                a_extreme = (long_touch and adp.iloc[i-1] < adp_os) or (short_touch and adp.iloc[i-1] > adp_ob)
                if a_extreme:
                    results["adaptive_zones"]["rsi_extreme"] += 1
                    if long_hook_adp or short_hook_adp:
                        results["adaptive_zones"]["hooks"] += 1
                        if adx_ok:
                            results["adaptive_zones"]["adx_pass"] += 1
                            results["adaptive_zones"]["final"] += 1

                # --- Adaptive RSI relaxed (zone R1/S1 = closer to 50) ---
                results["adaptive_relaxed"]["touches"] += 1
                a_extreme2 = (long_touch and adp.iloc[i-1] < adp_relaxed_os) or (short_touch and adp.iloc[i-1] > adp_relaxed_ob)
                if a_extreme2:
                    results["adaptive_relaxed"]["rsi_extreme"] += 1
                    if long_hook_adp or short_hook_adp:
                        results["adaptive_relaxed"]["hooks"] += 1
                        if adx_ok:
                            results["adaptive_relaxed"]["adx_pass"] += 1
                            results["adaptive_relaxed"]["final"] += 1

                # Record RSI values at touch for comparison
                trades.append({
                    "date": str(ts.date()),
                    "direction": direction,
                    "wilder_rsi": float(wilder.iloc[i-1]),
                    "adaptive_rsi": float(adp.iloc[i-1]),
                    "adp_ob": float(adp_ob),
                    "adp_os": float(adp_os),
                    "wilder_extreme_33_67": w_extreme,
                    "wilder_extreme_35_65": w_extreme2,
                    "adaptive_extreme": a_extreme,
                    "adaptive_relaxed_extreme": a_extreme2,
                    "hooked_wilder": long_hook or short_hook,
                    "hooked_adaptive": long_hook_adp or short_hook_adp,
                })

    return results, pd.DataFrame(trades)


def main():
    print("=" * 80)
    print("ADAPTIVE RSI vs WILDER RSI — SIGNAL FREQUENCY COMPARISON")
    print("=" * 80)

    print("\nLoading ES 09-26 5m data...")
    df1, df5, daily_atr = load_data("ES")
    print(f"  1m: {len(df1):,} | 5m: {len(df5):,}")

    print("\nRunning comparison (4 RSI variants)...")
    results, touches = run_comparison(df1, df5, daily_atr)

    print(f"\nTotal raw BB touches: {len(touches)}")
    print(f"\n{'Variant':<25} {'Touches':>8} {'RSI Ext':>8} {'Hooks':>8} {'ADX OK':>8} {'Final':>8}")
    print("-" * 70)
    for variant, counts in results.items():
        print(f"{variant:<25} {counts['touches']:>8} {counts['rsi_extreme']:>8} {counts['hooks']:>8} {counts['adx_pass']:>8} {counts['final']:>8}")

    # RSI distribution comparison
    print(f"\n--- RSI Distribution at BB Touch ({len(touches)} touches) ---")
    print(f"\nWilder RSI at touch:")
    w = touches["wilder_rsi"]
    print(f"  p10={w.quantile(.1):.1f}  p25={w.quantile(.25):.1f}  p50={w.quantile(.5):.1f}  p75={w.quantile(.75):.1f}  p90={w.quantile(.9):.1f}")
    print(f"  <30: {(w<30).sum()}  <33: {(w<33).sum()}  <35: {(w<35).sum()}  <40: {(w<40).sum()}")

    print(f"\nAdaptive RSI at touch:")
    a = touches["adaptive_rsi"]
    print(f"  p10={a.quantile(.1):.1f}  p25={a.quantile(.25):.1f}  p50={a.quantile(.5):.1f}  p75={a.quantile(.75):.1f}  p90={a.quantile(.9):.1f}")
    adp_os = touches["adp_os"].iloc[0]
    adp_ob = touches["adp_ob"].iloc[0]
    relaxed_os = 50 - (50 - adp_os) * 0.6  # 60% of the way to 50
    print(f"  <{adp_os:.1f} (OS zone): {(a<adp_os).sum()}  <{adp_os+5:.1f}: {(a<adp_os+5).sum()}  <40: {(a<40).sum()}  <45: {(a<45).sum()}")

    # Correlation
    corr = w.corr(a)
    print(f"\nCorrelation Wilder vs Adaptive: {corr:.4f}")

    # When do they disagree?
    disagree = touches[
        (touches["wilder_extreme_33_67"] != touches["adaptive_extreme"])
    ]
    print(f"\nDisagreements (Wilder 33/67 extreme vs Adaptive zone extreme): {len(disagree)}")
    if len(disagree) > 0:
        wilder_only = disagree[touches["wilder_extreme_33_67"] & ~touches["adaptive_extreme"]]
        adp_only = disagree[~touches["wilder_extreme_33_67"] & touches["adaptive_extreme"]]
        print(f"  Wilder extreme but NOT adaptive: {len(wilder_only)}")
        print(f"  Adaptive extreme but NOT wilder: {len(adp_only)}")
        if len(wilder_only) > 0:
            print(f"  Wilder-only RSI range: {wilder_only['wilder_rsi'].min():.1f}-{wilder_only['wilder_rsi'].max():.1f} (Wilder) vs {wilder_only['adaptive_rsi'].min():.1f}-{wilder_only['adaptive_rsi'].max():.1f} (Adaptive)")
        if len(adp_only) > 0:
            print(f"  Adaptive-only RSI range: {adp_only['wilder_rsi'].min():.1f}-{adp_only['wilder_rsi'].max():.1f} (Wilder) vs {adp_only['adaptive_rsi'].min():.1f}-{adp_only['adaptive_rsi'].max():.1f} (Adaptive)")

    # Hook comparison
    print(f"\n--- Hook-Back Rate ---")
    for variant, label in [("wilder_extreme_33_67", "Wilder 33/67"), ("wilder_extreme_35_65", "Wilder 35/65"), ("adaptive_extreme", "Adaptive zone"), ("adaptive_relaxed_extreme", "Adaptive relaxed")]:
        extreme = touches[touches[variant]]
        if len(extreme) > 0:
            hook_col = "hooked_adaptive" if "adaptive" in variant else "hooked_wilder"
            hook_rate = extreme[hook_col].mean() * 100
            print(f"  {label:<20} {len(extreme):>4} extremes -> {extreme[hook_col].sum():>3} hooks ({hook_rate:.0f}%)")

    # Key question: what would the adaptive RSI thresholds be at different lengths?
    print(f"\n--- Adaptive Zone Thresholds by Length ---")
    for length in [7, 10, 14, 20]:
        zones = adaptive_rsi_zones(pd.Series([100, 99, 101, 100]), length=length)
        ob = zones["ob_threshold"].iloc[-1]
        os_ = zones["os_threshold"].iloc[-1]
        r1 = zones["zone_r1"].iloc[-1]
        s1 = zones["zone_s1"].iloc[-1]
        print(f"  Length={length:2d}: OB={ob:.1f}  OS={os_:.1f}  R1={r1:.1f}  S1={s1:.1f}")

    print(f"\n--- VERDICT ---")
    final_w = results["wilder_33_67"]["final"]
    final_a = results["adaptive_zones"]["final"]
    final_ar = results["adaptive_relaxed"]["final"]
    print(f"  Wilder 33/67:       {final_w} final signals")
    print(f"  Adaptive zones:     {final_a} final signals ({final_a/final_w*100:.0f}% of Wilder)" if final_w > 0 else "")
    print(f"  Adaptive relaxed:   {final_ar} final signals ({final_ar/final_w*100:.0f}% of Wilder)" if final_w > 0 else "")
    print(f"\n  The adaptive zones are {'WIDER' if final_a < final_w else 'TIGHTER'} than Wilder 33/67")
    print(f"  -> {'Fewer' if final_a < final_w else 'More'} signals with adaptive RSI")

    # Save touches for further analysis
    touches.to_csv("data/derived/rsi_comparison_touches.csv", index=False)
    print(f"\n  Saved {len(touches)} touches -> data/derived/rsi_comparison_touches.csv")


if __name__ == "__main__":
    main()