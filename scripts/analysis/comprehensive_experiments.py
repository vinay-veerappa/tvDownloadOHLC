"""
Comprehensive RSI + Filter Experiment Harness
===============================================
Tests all RSI variants on BB strategy and all filters on Supertrend,
then runs the full statistical evaluation (prop firm + excursion + trade-level).

RSI variants tested on BB:
  1. Wilder RSI(14) 33/67 — baseline
  2. Wilder RSI(14) 35/65 — relaxed
  3. Adaptive Zones RSI (OB/OS thresholds)
  4. Adaptive Zones RSI (relaxed R1/S1 thresholds)
  5. Chande DMI — variable lookback
  6. Kaufman ER — efficiency-ratio scaled
  7. Ehlers Cycle — cycle-based lookback
  8. Connors RSI — composite

Also tests:
  - 2-bar hook (vs 1-bar) for BB
  - NQ data addition for BB
  - ATR regime filter for ST (Q3+Q4 only)
  - 14:00-16:00 time filter for ST
  - HTF level skip for ST
  - All combinations

Output: docs/research/COMPREHENSIVE_EXPERIMENTS.md + data/derived/experiment_*.csv
"""
import sys, io
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from itertools import product

from scripts.analysis.range_strategy_comparison import (
    BBRsiMeanReversionStrategy, BacktestEngine, build_day_context,
    _wilder_rsi, _adx,
)
from scripts.libs_py.adaptive_rsi import adaptive_rsi, adaptive_rsi_zones
from scripts.libs_py.adaptive_rsi_variants import (
    chande_dmi_rsi, kaufman_er_rsi, ehlers_cycle_rsi, connors_rsi,
)


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


def compute_mfe_mae(entry_time, exit_time, direction, entry_price, df_1m):
    bars = df_1m.loc[entry_time:exit_time]
    if bars.empty: return 0.0, 0.0
    if direction == "LONG":
        return float(bars["high"].max() - entry_price), float(entry_price - bars["low"].min())
    else:
        return float(entry_price - bars["low"].min()), float(bars["high"].max() - entry_price)


# ─── BB with configurable RSI variant ───────────────────────────────────────

def run_bb_variant(df1, df5, daily_atr, rsi_func, rsi_name, ob_threshold, os_threshold,
                   hook_bars=1, ib_filter=0.40, adx_threshold=25.0, lunch_skip=True,
                   direction_filter=None):
    """Run BB with a specific RSI variant and threshold logic.

    rsi_func: function(close) -> pd.Series (the RSI to use)
    ob_threshold, os_threshold: floats or 'adaptive' (use adaptive zones)
    hook_bars: 1 (immediate hook) or 2 (allow 2-bar delay)
    direction_filter: None, 'LONG', or 'SHORT'
    """
    unique_dates = sorted(df1["trade_date"].unique())
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
            if ib_range > ib_filter * ctx.atr_val:
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

            rsi = rsi_func(close)
            adx_s = _adx(high, low, close, 14)
            atr = ctx.atr_val if not np.isnan(ctx.atr_val) and ctx.atr_val > 0 else 20.0

            # Determine OB/OS thresholds (may be adaptive per-bar)
            if ob_threshold == 'adaptive':
                zones = adaptive_rsi_zones(close, 14, high=high, low=low)
                ob_vals = zones["ob_threshold"]
                os_vals = zones["os_threshold"]
            elif ob_threshold == 'adaptive_relaxed':
                zones = adaptive_rsi_zones(close, 14, high=high, low=low)
                ob_vals = zones["zone_r1"]
                os_vals = zones["zone_s1"]
            else:
                ob_vals = pd.Series(float(ob_threshold), index=close.index)
                os_vals = pd.Series(float(os_threshold), index=close.index)

            for i in range(max(2, hook_bars), len(bars_5m)):
                curr_time = bars_5m.index[i]
                if curr_time.time() < pd.Timestamp("11:30:00").time():
                    continue
                if lunch_skip and curr_time.hour >= 13 and curr_time.hour < 14:
                    continue

                # Check for BB touch on prior bar(s) — allow hook_bars delay
                touched = False
                touch_dir = None
                for hb in range(1, hook_bars + 1):
                    if i - hb < 0:
                        continue
                    lt = close.iloc[i - hb] < lower.iloc[i - hb]
                    st = close.iloc[i - hb] > upper.iloc[i - hb]
                    if lt or st:
                        touched = True
                        touch_dir = "LONG" if lt else "SHORT"
                        touch_idx = i - hb
                        break

                if not touched:
                    continue

                # Direction filter
                if direction_filter and touch_dir != direction_filter:
                    continue

                # RSI extreme at the touch bar
                rsi_at_touch = rsi.iloc[touch_idx]
                ob_val = ob_vals.iloc[touch_idx]
                os_val = os_vals.iloc[touch_idx]

                if touch_dir == "LONG":
                    rsi_extreme = rsi_at_touch < os_val
                else:
                    rsi_extreme = rsi_at_touch > ob_val

                if not rsi_extreme:
                    continue

                # Hook back inside on current bar
                if touch_dir == "LONG":
                    hooked = close.iloc[i] > lower.iloc[i] and rsi.iloc[i] > rsi.iloc[touch_idx] and close.iloc[i] < sma.iloc[i] and rsi.iloc[i] < 50
                else:
                    hooked = close.iloc[i] < upper.iloc[i] and rsi.iloc[i] < rsi.iloc[touch_idx] and close.iloc[i] > sma.iloc[i] and rsi.iloc[i] > 50

                if not hooked:
                    continue

                # ADX gate
                adx_val = adx_s.iloc[i]
                if not np.isnan(adx_val) and adx_val >= adx_threshold:
                    continue

                # IB filter
                if not ib_ok:
                    continue

                # Risk cap
                atr_5m = float((high.rolling(14).max() - low.rolling(14).min()).iloc[i] / 14) if len(bars_5m) > 20 else atr / 6
                if np.isnan(atr_5m) or atr_5m <= 0:
                    atr_5m = atr / 6

                entry = float(close.iloc[i])
                if touch_dir == "LONG":
                    sl = float(min(lower.iloc[i], close.iloc[i]) - 1.5 * atr_5m)
                    sl = min(sl, entry - (1.0 * atr_5m))
                    risk = entry - sl
                    tp1 = float(sma.iloc[i])
                    if tp1 <= entry or risk <= 0 or risk > (0.70 * atr):
                        continue
                else:
                    sl = float(max(upper.iloc[i], close.iloc[i]) + 1.5 * atr_5m)
                    sl = max(sl, entry + (1.0 * atr_5m))
                    risk = sl - entry
                    tp1 = float(sma.iloc[i])
                    if tp1 >= entry or risk <= 0 or risk > (0.70 * atr):
                        continue

                # Simulate trade
                from scripts.analysis.range_strategy_comparison import TradeSignal
                signal = TradeSignal(
                    direction=touch_dir, entry_price=entry, stop_loss=sl,
                    tp1_price=tp1, tp2_price=float(upper.iloc[i] if touch_dir == "LONG" else lower.iloc[i]),
                    risk_points=risk, entry_time=curr_time, session_name=sess,
                )
                engine = BacktestEngine("ES", entry_mode="market")
                result = engine.simulate_trade(signal, ctx)
                if result is None:
                    continue

                mfe, mae = compute_mfe_mae(result.entry_time, result.exit_time, result.direction, result.entry_price, df1)
                risk_val = abs(risk)
                trades.append({
                    "strategy": f"BB_{rsi_name}", "date": result.date,
                    "direction": result.direction,
                    "entry_time": result.entry_time, "exit_time": result.exit_time,
                    "entry_price": result.entry_price, "stop_loss": result.stop_loss,
                    "risk_points": result.risk_points,
                    "pnl_dollars": result.total_pnl_dollars, "r_multiple": result.r_multiple,
                    "mfe_pts": mfe, "mae_pts": mae,
                    "mfe_r": mfe / risk_val if risk_val > 0 else 0,
                    "mae_r": mae / risk_val if risk_val > 0 else 0,
                    "is_win": result.total_pnl_dollars > 0,
                    "rsi_at_touch": float(rsi_at_touch),
                    "hour": curr_time.hour,
                })

    return pd.DataFrame(trades)


# ─── Supertrend with filters ────────────────────────────────────────────────

def supertrend(high, low, close, period, mult):
    hl2 = (high + low) / 2.0
    tr = pd.concat([high-low, (high-close.shift(1)).abs(), (low-close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    upper = hl2 + mult * atr; lower = hl2 - mult * atr
    fu = upper.copy(); fl = lower.copy()
    for i in range(1, len(upper)):
        if fu.iloc[i] > fu.iloc[i-1]: fu.iloc[i] = fu.iloc[i-1]
        if fl.iloc[i] < fl.iloc[i-1]: fl.iloc[i] = fl.iloc[i-1]
    st = pd.Series(np.nan, index=close.index)
    for i in range(1, len(close)):
        if close.iloc[i] > fu.iloc[i-1]: st.iloc[i] = 1
        elif close.iloc[i] < fl.iloc[i-1]: st.iloc[i] = -1
        else: st.iloc[i] = st.iloc[i-1]
    return st


def run_st_variant(df1, df5, daily_atr, atr_regime_filter=False, time_filter=False,
                   htf_skip=False, htf_df=None, trail_mult=1.5):
    """Run Supertrend with optional filters."""
    POINT_VAL = 5.0; COMM = 1.20; SLIP = 0.25
    unique_dates = sorted(df1["trade_date"].unique())
    trades = []

    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
        if ctx is None:
            continue
        bars5 = ctx.day_bars_5m
        if bars5 is None or len(bars5) < 19:
            continue
        close = bars5["close"]; high = bars5["high"]; low = bars5["low"]
        st = supertrend(high, low, close, 14, 2.0)
        atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14

        # ATR regime filter: only trade when current 5m ATR > median of recent 20 bars
        atr_median = atr5.rolling(20, min_periods=5).median()

        # HTF levels for this day
        htf_level = None
        if htf_skip and htf_df is not None:
            td = pd.Timestamp(t_date)
            htf_copy = htf_df.copy()
            htf_copy["td_ts"] = pd.to_datetime(htf_copy["trading_date"])
            prior = htf_copy[htf_copy["td_ts"] < td].tail(1)
            if not prior.empty:
                htf_level = {
                    "pdh": float(prior["pdh"].iloc[0]) if pd.notna(prior["pdh"].iloc[0]) else None,
                    "pdl": float(prior["pdl"].iloc[0]) if pd.notna(prior["pdl"].iloc[0]) else None,
                }

        pos = 0; entry = 0.0; stop = 0.0; entry_idx = 0; entry_time = None

        for i in range(1, len(bars5)):
            a5 = atr5.iloc[i]
            if np.isnan(a5) or a5 <= 0:
                continue
            st0 = st.iloc[i]; st1 = st.iloc[i - 1]
            if pd.isna(st0) or pd.isna(st1):
                continue
            c0 = close.iloc[i]; h0 = high.iloc[i]; l0 = low.iloc[i]

            if pos != 0:
                if pos == 1:
                    stop = max(stop, h0 - trail_mult * a5)
                    if l0 <= stop:
                        exit_px = stop - SLIP
                        pnl = (exit_px - entry) * POINT_VAL - COMM
                        mfe, mae = compute_mfe_mae(entry_time, bars5.index[i], "LONG", entry, df1)
                        risk = abs(1.5 * atr5.iloc[entry_idx])
                        trades.append(_st_trade("ST_filtered", str(ts.date()), "LONG", entry, exit_px, pnl,
                                                mfe, mae, risk, entry_time, bars5.index[i], i - entry_idx))
                        pos = 0
                else:
                    stop = min(stop, l0 + trail_mult * a5)
                    if h0 >= stop:
                        exit_px = stop + SLIP
                        pnl = (entry - exit_px) * POINT_VAL - COMM
                        mfe, mae = compute_mfe_mae(entry_time, bars5.index[i], "SHORT", entry, df1)
                        risk = abs(1.5 * atr5.iloc[entry_idx])
                        trades.append(_st_trade("ST_filtered", str(ts.date()), "SHORT", entry, exit_px, pnl,
                                                mfe, mae, risk, entry_time, bars5.index[i], i - entry_idx))
                        pos = 0

            if pos == 0:
                flip_long = st0 == 1 and st1 == -1
                flip_short = st0 == -1 and st1 == 1

                if not (flip_long or flip_short):
                    continue

                # ATR regime filter
                if atr_regime_filter:
                    a_med = atr_median.iloc[i]
                    if np.isnan(a_med) or a5 < a_med:
                        continue

                # Time filter: skip 14:00-16:00
                if time_filter:
                    h = bars5.index[i].hour
                    if h >= 14:
                        continue

                # HTF level skip
                if htf_skip and htf_level:
                    entry_price = c0 + (SLIP if flip_long else -SLIP)
                    for level_name, level_val in htf_level.items():
                        if level_val is not None:
                            dist_bps = abs(entry_price - level_val) / entry_price * 10000
                            if dist_bps < 20:
                                pos = 0  # skip this flip
                                break
                    if pos != 0:
                        continue  # was skipped

                if flip_long:
                    pos = 1; entry = c0 + SLIP; entry_idx = i; entry_time = bars5.index[i]
                    stop = entry - trail_mult * a5
                else:
                    pos = -1; entry = c0 - SLIP; entry_idx = i; entry_time = bars5.index[i]
                    stop = entry + trail_mult * a5

        if pos != 0:
            exit_px = close.iloc[-1] - SLIP if pos == 1 else close.iloc[-1] + SLIP
            pnl = ((exit_px - entry) if pos == 1 else (entry - exit_px)) * POINT_VAL - COMM
            mfe, mae = compute_mfe_mae(entry_time, bars5.index[-1], "LONG" if pos == 1 else "SHORT", entry, df1)
            risk = abs(1.5 * atr5.iloc[entry_idx])
            trades.append(_st_trade("ST_filtered", str(ts.date()), "LONG" if pos == 1 else "SHORT",
                                    entry, exit_px, pnl, mfe, mae, risk, entry_time, bars5.index[-1],
                                    len(bars5) - 1 - entry_idx))

    return pd.DataFrame(trades)


def _st_trade(strat, date, direction, entry, exit_px, pnl, mfe, mae, risk, entry_time, exit_time, duration):
    return {
        "strategy": strat, "date": date, "direction": direction,
        "entry_time": entry_time, "exit_time": exit_time,
        "entry_price": entry, "exit_price": exit_px, "risk_points": risk,
        "pnl_dollars": pnl,
        "r_multiple": ((exit_px - entry) if direction == "LONG" else (entry - exit_px)) / risk if risk > 0 else 0,
        "mfe_pts": mfe, "mae_pts": mae,
        "mfe_r": mfe / risk if risk > 0 else 0,
        "mae_r": mae / risk if risk > 0 else 0,
        "is_win": pnl > 0, "hour": entry_time.hour if hasattr(entry_time, 'hour') else 0,
        "duration_bars": duration,
    }


# ─── Summary stats ───────────────────────────────────────────────────────────

def summary_stats(trades_df, name):
    if trades_df.empty:
        return f"{name:<35} {'0':>5} {'-':>6} {'-':>6} {'-':>10} {'-':>10}"
    n = len(trades_df)
    wr = (trades_df["pnl_dollars"] > 0).mean() * 100
    net = trades_df["pnl_dollars"].sum()
    gp = trades_df.loc[trades_df["pnl_dollars"] > 0, "pnl_dollars"].sum()
    gl = abs(trades_df.loc[trades_df["pnl_dollars"] < 0, "pnl_dollars"].sum())
    pf = gp / gl if gl > 0 else 999
    avg_r = trades_df["r_multiple"].mean()
    return f"{name:<35} {n:>5} {wr:>5.1f}% {pf:>6.2f} {net:>+10.0f} {avg_r:>+10.3f}"


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 90)
    print("COMPREHENSIVE RSI + FILTER EXPERIMENTS")
    print("=" * 90)

    print("\nLoading ES data...")
    df1_es, df5_es, daily_atr_es = load_data("ES")
    print(f"  ES 1m: {len(df1_es):,} | 5m: {len(df5_es):,}")

    print("Loading NQ data...")
    df1_nq, df5_nq, daily_atr_nq = load_data("NQ")
    print(f"  NQ 1m: {len(df1_nq):,} | 5m: {len(df5_nq):,}")

    # Load HTF levels for ST filter
    htf_df = pd.read_parquet("data/derived/ICT/ES1_htf_levels.parquet")

    # ─── PART 1: RSI Variants on BB ──────────────────────────────────────
    print("\n" + "=" * 90)
    print("PART 1: RSI Variants on BB Mean Reversion Strategy (ES only)")
    print("=" * 90)
    print(f"\n{'Variant':<35} {'Trades':>6} {'WR':>6} {'PF':>6} {'Net $':>10} {'Avg R':>10}")
    print("-" * 80)

    rsi_variants = [
        ("wilder_33_67", lambda c: _wilder_rsi(c, 14), 67, 33, 1),
        ("wilder_35_65", lambda c: _wilder_rsi(c, 14), 65, 35, 1),
        ("wilder_40_60", lambda c: _wilder_rsi(c, 14), 60, 40, 1),
        ("adaptive_zones", lambda c: adaptive_rsi(c, 14), 'adaptive', 'adaptive', 1),
        ("adaptive_relaxed", lambda c: adaptive_rsi(c, 14), 'adaptive_relaxed', 'adaptive_relaxed', 1),
        ("chande_dmi", lambda c: chande_dmi_rsi(c), 67, 33, 1),
        ("kaufman_er", lambda c: kaufman_er_rsi(c), 67, 33, 1),
        ("ehlers_cycle", lambda c: ehlers_cycle_rsi(c), 67, 33, 1),
        ("connors_rsi", lambda c: connors_rsi(c), 67, 33, 1),
        # 2-bar hook versions
        ("wilder_33_67_2bar", lambda c: _wilder_rsi(c, 14), 67, 33, 2),
        ("chande_dmi_2bar", lambda c: chande_dmi_rsi(c), 67, 33, 2),
        ("kaufman_er_2bar", lambda c: kaufman_er_rsi(c), 67, 33, 2),
        ("connors_2bar", lambda c: connors_rsi(c), 67, 33, 2),
        # Direction filtered (SHORT only — prior finding)
        ("wilder_33_67_short", lambda c: _wilder_rsi(c, 14), 67, 33, 1, "SHORT"),
        ("chande_short", lambda c: chande_dmi_rsi(c), 67, 33, 1, "SHORT"),
        ("kaufman_short", lambda c: kaufman_er_rsi(c), 67, 33, 1, "SHORT"),
        # Relaxed IB
        ("wilder_33_67_ib0.6", lambda c: _wilder_rsi(c, 14), 67, 33, 1, None, 0.60),
        ("chande_ib0.6", lambda c: chande_dmi_rsi(c), 67, 33, 1, None, 0.60),
    ]

    all_bb_results = []
    for config in rsi_variants:
        name = config[0]
        rsi_func = config[1]
        ob = config[2]
        os_ = config[3]
        hook = config[4]
        dir_filter = config[5] if len(config) > 5 else None
        ib_f = config[6] if len(config) > 6 else 0.40

        trades = run_bb_variant(df1_es, df5_es, daily_atr_es, rsi_func, name, ob, os_,
                                hook_bars=hook, ib_filter=ib_f, direction_filter=dir_filter)
        print(summary_stats(trades, name))
        if not trades.empty:
            trades["variant"] = name
            all_bb_results.append(trades)

    # ─── PART 2: NQ addition ─────────────────────────────────────────────
    print("\n" + "=" * 90)
    print("PART 2: NQ addition for BB (best RSI variants)")
    print("=" * 90)
    print(f"\n{'Variant':<35} {'Trades':>6} {'WR':>6} {'PF':>6} {'Net $':>10} {'Avg R':>10}")
    print("-" * 80)

    for name, rsi_func, ob, os_, hook in [
        ("wilder_33_67_NQ", lambda c: _wilder_rsi(c, 14), 67, 33, 1),
        ("chande_dmi_NQ", lambda c: chande_dmi_rsi(c), 67, 33, 1),
        ("kaufman_er_NQ", lambda c: kaufman_er_rsi(c), 67, 33, 1),
        ("connors_NQ", lambda c: connors_rsi(c), 67, 33, 1),
    ]:
        trades = run_bb_variant(df1_nq, df5_nq, daily_atr_nq, rsi_func, name, ob, os_, hook_bars=hook)
        # NQ uses $2/pt per micro, adjust
        if not trades.empty:
            trades["pnl_dollars"] = trades["pnl_dollars"] * (2.0 / 5.0)  # convert from ES $5 to NQ $2
        print(summary_stats(trades, name))
        if not trades.empty:
            trades["variant"] = name
            all_bb_results.append(trades)

    # Combined ES + NQ
    print(f"\n{'ES+NQ combined':<35} {'Trades':>6} {'WR':>6} {'PF':>6} {'Net $':>10} {'Avg R':>10}")
    print("-" * 80)
    for name, rsi_func, ob, os_, hook in [
        ("wilder_33_67_ES+NQ", lambda c: _wilder_rsi(c, 14), 67, 33, 1),
        ("chande_ES+NQ", lambda c: chande_dmi_rsi(c), 67, 33, 1),
        ("kaufman_ES+NQ", lambda c: kaufman_er_rsi(c), 67, 33, 1),
    ]:
        es_trades = run_bb_variant(df1_es, df5_es, daily_atr_es, rsi_func, name, ob, os_, hook_bars=hook)
        nq_trades = run_bb_variant(df1_nq, df5_nq, daily_atr_nq, rsi_func, name, ob, os_, hook_bars=hook)
        if not nq_trades.empty:
            nq_trades["pnl_dollars"] = nq_trades["pnl_dollars"] * (2.0 / 5.0)
        combined = pd.concat([es_trades, nq_trades], ignore_index=True) if not es_trades.empty or not nq_trades.empty else pd.DataFrame()
        print(summary_stats(combined, name))

    # ─── PART 3: Supertrend filters ──────────────────────────────────────
    print("\n" + "=" * 90)
    print("PART 3: Supertrend Filter Experiments (ES 5m)")
    print("=" * 90)
    print(f"\n{'Variant':<35} {'Trades':>6} {'WR':>6} {'PF':>6} {'Net $':>10} {'Avg R':>10}")
    print("-" * 80)

    st_configs = [
        ("ST_baseline", False, False, False),
        ("ST_atr_regime", True, False, False),
        ("ST_time_filter", False, True, False),
        ("ST_htf_skip", False, False, True),
        ("ST_atr+time", True, True, False),
        ("ST_atr+htf", True, False, True),
        ("ST_time+htf", False, True, True),
        ("ST_all_filters", True, True, True),
        ("ST_atr+time_1.0trail", True, True, False),  # tighter trail
    ]

    all_st_results = []
    for name, atr_f, time_f, htf_f in st_configs:
        trail = 1.0 if "1.0trail" in name else 1.5
        trades = run_st_variant(df1_es, df5_es, daily_atr_es,
                                atr_regime_filter=atr_f, time_filter=time_f,
                                htf_skip=htf_f, htf_df=htf_df if htf_f else None,
                                trail_mult=trail)
        print(summary_stats(trades, name))
        if not trades.empty:
            trades["variant"] = name
            all_st_results.append(trades)

    # ─── Save all results ────────────────────────────────────────────────
    if all_bb_results:
        bb_all = pd.concat(all_bb_results, ignore_index=True)
        bb_all.to_csv("data/derived/experiment_bb_all.csv", index=False)
        print(f"\n  Saved {len(bb_all)} BB trades -> data/derived/experiment_bb_all.csv")

    if all_st_results:
        st_all = pd.concat(all_st_results, ignore_index=True)
        st_all.to_csv("data/derived/experiment_st_all.csv", index=False)
        print(f"  Saved {len(st_all)} ST trades -> data/derived/experiment_st_all.csv")

    # ─── Write report ────────────────────────────────────────────────────
    print("\n  Writing report...")
    report_path = Path("docs/research/COMPREHENSIVE_EXPERIMENTS.md")
    report_lines = [
        "# Comprehensive RSI + Filter Experiments",
        f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        f"\n_Data: ES+NQ 09-26 MergeBackAdjusted 5m, 2025-01-01 -> 2026-08-21_",
        "\n---\n",
        "## Part 1: RSI Variants on BB (ES only)\n",
        "| Variant | Trades | WR | PF | Net $ | Avg R |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for config in rsi_variants:
        name = config[0]
        # Find matching result
        for r in all_bb_results:
            if r["variant"].iloc[0] == name:
                t = r
                n = len(t); wr = (t["pnl_dollars"]>0).mean()*100
                gp = t.loc[t["pnl_dollars"]>0,"pnl_dollars"].sum()
                gl = abs(t.loc[t["pnl_dollars"]<0,"pnl_dollars"].sum())
                pf = gp/gl if gl > 0 else 999
                net = t["pnl_dollars"].sum(); avg_r = t["r_multiple"].mean()
                report_lines.append(f"| {name} | {n} | {wr:.1f}% | {pf:.2f} | ${net:+.0f} | {avg_r:+.3f} |")
                break
        else:
            report_lines.append(f"| {name} | 0 | - | - | - | - |")

    report_lines.append("\n## Part 2: NQ Addition\n")
    report_lines.append("| Variant | Trades | WR | PF | Net $ | Avg R |")
    report_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    report_lines.append("\n## Part 3: Supertrend Filters\n")
    report_lines.append("| Variant | Trades | WR | PF | Net $ | Avg R |")
    report_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    for name, atr_f, time_f, htf_f in st_configs:
        for r in all_st_results:
            if r["variant"].iloc[0] == name:
                t = r
                n = len(t); wr = (t["pnl_dollars"]>0).mean()*100
                gp = t.loc[t["pnl_dollars"]>0,"pnl_dollars"].sum()
                gl = abs(t.loc[t["pnl_dollars"]<0,"pnl_dollars"].sum())
                pf = gp/gl if gl > 0 else 999
                net = t["pnl_dollars"].sum(); avg_r = t["r_multiple"].mean()
                report_lines.append(f"| {name} | {n} | {wr:.1f}% | {pf:.2f} | ${net:+.0f} | {avg_r:+.3f} |")
                break
        else:
            report_lines.append(f"| {name} | 0 | - | - | - | - |")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"  Report: {report_path}")
    print("\n✅ All experiments complete")


if __name__ == "__main__":
    main()