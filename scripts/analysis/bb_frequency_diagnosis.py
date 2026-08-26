"""
BB Trade Frequency Diagnosis
=============================
Counts how many potential BB signals exist at each filter stage to identify
which E14 filters are over-restrictive and where the trade flow is being choked.

Stages:
  S0: Raw BB touch (close beyond band)
  S1: + RSI extreme (RSI<33 long / >67 short)
  S2: + Hook back inside (close back in band, RSI turning)
  S3: + ADX regime gate (<25)
  S4: + IB compression filter (<0.4 ATR)
  S5: + Lunch skip (13:00-14:00)
  S6: + Risk cap (risk <= 0.70 ATR)
  S7: + TP1 valid (tp1 on correct side)

Also records the indicator values at each raw touch for characteristic analysis.
"""
import sys, io
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd, numpy as np
from collections import defaultdict
from scripts.analysis.range_strategy_comparison import build_day_context, _wilder_rsi, _adx

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

def main():
    df1, df5, daily_atr = load_data("ES")
    unique_dates = sorted(df1["trade_date"].unique())

    # Stage counters
    stages = defaultdict(int)
    # Indicator values at raw touch
    touch_records = []
    # Filter rejection reasons
    rejections = defaultdict(int)

    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
        if ctx is None:
            continue

        # IB filter check
        ib_bars = ctx.session_5m.get("NY_AM")
        ib_ok = True
        if ib_bars is not None and len(ib_bars) >= 6:
            ib_range = ib_bars["high"].iloc[:6].max() - ib_bars["low"].iloc[:6].min()
            if ib_range > 0.40 * ctx.atr_val:
                ib_ok = False
                rejections["IB_wide"] += 1
        else:
            rejections["no_IB_bars"] += 1

        for sess in ("NY_MIDDAY", "NY_PM"):
            bars_5m = ctx.session_5m.get(sess)
            if bars_5m is None or len(bars_5m) < 30:
                rejections["insufficient_5m_bars"] += 1
                continue

            close = bars_5m["close"]
            high = bars_5m["high"]
            low = bars_5m["low"]
            sma = close.rolling(20).mean()
            std = close.rolling(20).std()
            upper = sma + 2.0 * std
            lower = sma - 2.0 * std
            rsi = _wilder_rsi(close, 14)
            adx_s = _adx(high, low, close, 14)

            atr = ctx.atr_val if not np.isnan(ctx.atr_val) and ctx.atr_val > 0 else 20.0

            for i in range(2, len(bars_5m)):
                curr_time = bars_5m.index[i]
                if curr_time.time() < pd.Timestamp("11:30:00").time():
                    continue

                # S0: Raw BB touch — close beyond band on prior bar
                long_touch = close.iloc[i-1] < lower.iloc[i-1]
                short_touch = close.iloc[i-1] > upper.iloc[i-1]

                if not long_touch and not short_touch:
                    continue

                stages["S0_raw_touch"] += 1
                bw = float((upper.iloc[i] - lower.iloc[i]) / sma.iloc[i]) if sma.iloc[i] > 0 else 0
                displacement_bps = abs(close.iloc[i-1] - sma.iloc[i-1]) / sma.iloc[i-1] * 10000 if sma.iloc[i-1] > 0 else 0
                touch_records.append({
                    "date": str(ts.date()), "session": sess, "bar_idx": i,
                    "time": str(curr_time.time()),
                    "direction": "LONG" if long_touch else "SHORT",
                    "close": close.iloc[i-1], "sma": sma.iloc[i-1],
                    "upper": upper.iloc[i-1], "lower": lower.iloc[i-1],
                    "rsi": rsi.iloc[i-1], "adx": adx_s.iloc[i-1],
                    "bandwidth": bw, "displacement_bps": displacement_bps,
                    "ib_ok": ib_ok,
                    "hour": curr_time.hour,
                })

                # S1: RSI extreme
                long_rsi = long_touch and rsi.iloc[i-1] < 33
                short_rsi = short_touch and rsi.iloc[i-1] > 67
                if not (long_rsi or short_rsi):
                    rejections["S1_RSI_not_extreme"] += 1
                    continue
                stages["S1_rsi_extreme"] += 1

                # S2: Hook back inside + RSI turning
                long_hook = long_rsi and close.iloc[i] > lower.iloc[i] and rsi.iloc[i] > rsi.iloc[i-1] and close.iloc[i] < sma.iloc[i] and rsi.iloc[i] < 50
                short_hook = short_rsi and close.iloc[i] < upper.iloc[i] and rsi.iloc[i] < rsi.iloc[i-1] and close.iloc[i] > sma.iloc[i] and rsi.iloc[i] > 50
                if not (long_hook or short_hook):
                    rejections["S2_no_hook_back"] += 1
                    continue
                stages["S2_hook_back"] += 1

                # S3: ADX gate
                adx_val = adx_s.iloc[i]
                if not np.isnan(adx_val) and adx_val >= 25.0:
                    rejections["S3_ADX_too_high"] += 1
                    continue
                stages["S3_adx_ok"] += 1

                # S4: IB filter
                if not ib_ok:
                    rejections["S4_IB_wide"] += 1
                    continue
                stages["S4_ib_ok"] += 1

                # S5: Lunch skip
                sig_hour = curr_time.hour
                if sig_hour >= 13 and sig_hour < 14:
                    rejections["S5_lunch_skip"] += 1
                    continue
                stages["S5_lunch_ok"] += 1

                # S6: Risk cap
                atr_5m = float((high.rolling(14).max() - low.rolling(14).min()).iloc[i] / 14) if len(bars_5m) > 20 else atr / 6
                if np.isnan(atr_5m) or atr_5m <= 0:
                    atr_5m = atr / 6
                if long_hook:
                    sl = float(min(lower.iloc[i], close.iloc[i]) - 1.5 * atr_5m)
                    sl = min(sl, close.iloc[i] - (1.0 * atr_5m))
                    risk = close.iloc[i] - sl
                    tp1 = float(sma.iloc[i])
                    valid_tp = tp1 > close.iloc[i]
                else:
                    sl = float(max(upper.iloc[i], close.iloc[i]) + 1.5 * atr_5m)
                    sl = max(sl, close.iloc[i] + (1.0 * atr_5m))
                    risk = sl - close.iloc[i]
                    tp1 = float(sma.iloc[i])
                    valid_tp = tp1 < close.iloc[i]

                if risk <= 0 or risk > (0.70 * atr):
                    rejections["S6_risk_cap"] += 1
                    continue
                stages["S6_risk_ok"] += 1

                # S7: TP1 valid
                if not valid_tp:
                    rejections["S7_tp1_invalid"] += 1
                    continue
                stages["S7_final_signal"] += 1

    print("=" * 70)
    print("BB TRADE FREQUENCY DIAGNOSIS (E14 filters)")
    print("=" * 70)
    print(f"\nTotal trading days: {len([d for d in unique_dates if pd.Timestamp(d).weekday() < 5 and pd.Timestamp(d).year >= 2025])}")
    print(f"\n--- Signal Funnel ---")
    for stage in ["S0_raw_touch", "S1_rsi_extreme", "S2_hook_back", "S3_adx_ok", "S4_ib_ok", "S5_lunch_ok", "S6_risk_ok", "S7_final_signal"]:
        print(f"  {stage}: {stages[stage]}")

    print(f"\n--- Rejection Reasons ---")
    for reason, count in sorted(rejections.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")

    # Characteristic analysis of raw touches
    touches = pd.DataFrame(touch_records)
    if touches.empty:
        print("\nNo raw touches found!")
        return

    print(f"\n--- Raw Touch Characteristics ({len(touches)} total) ---")
    print(f"\nBy direction:")
    for d in ["LONG", "SHORT"]:
        sd = touches[touches["direction"] == d]
        if sd.empty:
            continue
        print(f"  {d}: n={len(sd)}")
        print(f"    Displacement (bps): p10={sd['displacement_bps'].quantile(.1):.1f}  p25={sd['displacement_bps'].quantile(.25):.1f}  p50={sd['displacement_bps'].quantile(.5):.1f}  p75={sd['displacement_bps'].quantile(.75):.1f}  p90={sd['displacement_bps'].quantile(.9):.1f}")
        print(f"    RSI at touch: p10={sd['rsi'].quantile(.1):.1f}  p25={sd['rsi'].quantile(.25):.1f}  p50={sd['rsi'].quantile(.5):.1f}  p75={sd['rsi'].quantile(.75):.1f}  p90={sd['rsi'].quantile(.9):.1f}")
        print(f"    ADX at touch: p10={sd['adx'].quantile(.1):.1f}  p25={sd['adx'].quantile(.25):.1f}  p50={sd['adx'].quantile(.5):.1f}  p75={sd['adx'].quantile(.75):.1f}  p90={sd['adx'].quantile(.9):.1f}")
        print(f"    Bandwidth: p10={sd['bandwidth'].quantile(.1):.4f}  p25={sd['bandwidth'].quantile(.25):.4f}  p50={sd['bandwidth'].quantile(.5):.4f}  p75={sd['bandwidth'].quantile(.75):.4f}  p90={sd['bandwidth'].quantile(.9):.4f}")

    # What RSI values do LONG touches have? (to see if 33 threshold is too strict)
    long_touches = touches[touches["direction"] == "LONG"]
    if not long_touches.empty:
        print(f"\n--- LONG Touch RSI Distribution (to evaluate threshold=33) ---")
        rsi_bins = [0, 20, 25, 30, 33, 35, 38, 40, 45, 50]
        for j in range(len(rsi_bins)-1):
            lo, hi = rsi_bins[j], rsi_bins[j+1]
            n = ((long_touches["rsi"] >= lo) & (long_touches["rsi"] < hi)).sum()
            print(f"  RSI {lo}-{hi}: {n} touches")

    short_touches = touches[touches["direction"] == "SHORT"]
    if not short_touches.empty:
        print(f"\n--- SHORT Touch RSI Distribution (to evaluate threshold=67) ---")
        rsi_bins = [50, 55, 60, 62, 65, 67, 70, 75, 80, 100]
        for j in range(len(rsi_bins)-1):
            lo, hi = rsi_bins[j], rsi_bins[j+1]
            n = ((short_touches["rsi"] >= lo) & (short_touches["rsi"] < hi)).sum()
            print(f"  RSI {lo}-{hi}: {n} touches")

    # ADX distribution at touch
    print(f"\n--- ADX Distribution at Touch (to evaluate threshold=25) ---")
    adx_bins = [0, 10, 15, 18, 20, 22, 25, 28, 30, 35, 50]
    for j in range(len(adx_bins)-1):
        lo, hi = adx_bins[j], adx_bins[j+1]
        n = ((touches["adx"] >= lo) & (touches["adx"] < hi)).sum()
        print(f"  ADX {lo}-{hi}: {n} touches")

    # Hour distribution of raw touches
    print(f"\n--- Raw Touch by Hour ---")
    print(touches.groupby("hour").size().to_string())

    # What if we relax RSI to 35/65?
    print(f"\n--- What-if: Relax RSI threshold ---")
    for rsi_long, rsi_short in [(33, 67), (35, 65), (38, 62), (40, 60)]:
        long_pass = (long_touches["rsi"] < rsi_long).sum()
        short_pass = (short_touches["rsi"] > rsi_short).sum()
        print(f"  RSI<{rsi_long}/{rsi_short}>: LONG={long_pass}  SHORT={short_pass}  total={long_pass+short_pass}")

    # What if we relax ADX to 30?
    print(f"\n--- What-if: Relax ADX threshold ---")
    for adx_t in [20, 22, 25, 28, 30, 35]:
        n = (touches["adx"] < adx_t).sum()
        print(f"  ADX<{adx_t}: {n} touches pass")

    # What if we relax IB to 0.5 or 0.6?
    print(f"\n--- What-if: Relax IB filter ---")
    for ib_mult in [0.40, 0.50, 0.60, 0.70, 0.80, 1.0]:
        # Need to recount per day
        pass_days = 0
        for t_date in unique_dates:
            ts = pd.Timestamp(t_date)
            if ts.weekday() >= 5 or ts.year < 2025:
                continue
            ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
            if ctx is None:
                continue
            ib_bars = ctx.session_5m.get("NY_AM")
            if ib_bars is not None and len(ib_bars) >= 6:
                ib_range = ib_bars["high"].iloc[:6].max() - ib_bars["low"].iloc[:6].min()
                if ib_range <= ib_mult * ctx.atr_val:
                    pass_days += 1
        print(f"  IB<{ib_mult}*ATR: {pass_days} days pass (of ~350)")

    # Save raw touches for further analysis
    touches.to_csv("data/derived/bb_raw_touches.csv", index=False)
    print(f"\nSaved {len(touches)} raw touches -> data/derived/bb_raw_touches.csv")

if __name__ == "__main__":
    main()