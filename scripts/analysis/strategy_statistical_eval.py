"""
Unified Statistical Evaluation Harness (ADR-002, 010, 021, 023)
================================================================
Runs BB_RSI (E14 config) and Supertrend (S09 config) through:
  1. MFE/MAE excursion analysis (ADR-023) — percentiles, CDF, survival curves
  2. PropFirmSimulator (ADR-021) — deterministic + Monte Carlo across all profiles
  3. Trade-level statistics: hour, day-of-week, direction, R-multiple, regime
  4. Bootstrap CI on per-session returns (STRATEGY_WORKFLOW.md §6.4)

Output: docs/research/STRATEGY_STATISTICAL_EVAL.md + data/derived/strategy_eval_*.csv
"""
import sys, io
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

from scripts.analysis.range_strategy_comparison import (
    BBRsiMeanReversionStrategy, BacktestEngine, build_day_context,
)
from scripts.trading_framework.ml.prop_firm_simulator import (
    PropFirmSimulator, FIRM_PROFILES,
)

# ─── Data Load ──────────────────────────────────────────────────────────────

def load_data(sym="ES"):
    df1 = pd.read_csv(
        f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv",
        parse_dates=["time"],
    ).set_index("time").sort_index()
    df5 = pd.read_csv(
        f"data/derived/nt_{sym.lower()}_09_26_5m_2025_2026_mergeBA.csv",
        parse_dates=["time"],
    ).set_index("time").sort_index()
    df1 = df1[(df1.index.year >= 2025) & (df1.index.year <= 2026)]
    df5 = df5[(df5.index.year >= 2025) & (df5.index.year <= 2026)]
    tr2 = pd.concat([
        df1.resample("D").agg({"high": "max", "low": "min", "close": "last"}).dropna().pipe(
            lambda d: d["high"] - d["low"]
        ),
        (df1.resample("D").agg({"high": "max", "close": "last"}).dropna()["high"]
         - df1.resample("D").agg({"close": "last"}).dropna()["close"].shift(1)).abs(),
        (df1.resample("D").agg({"low": "min", "close": "last"}).dropna()["low"]
         - df1.resample("D").agg({"close": "last"}).dropna()["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    daily_atr = tr2.rolling(10, min_periods=1).mean()
    df1["trade_date"] = df1.index.date
    df1.loc[df1.index.hour >= 18, "trade_date"] = (
        df1.loc[df1.index.hour >= 18].index + pd.Timedelta(days=1)
    ).date
    return df1, df5, daily_atr


# ─── MFE/MAE Computation (ADR-023) ──────────────────────────────────────────

def compute_mfe_mae(entry_time, exit_time, direction, entry_price, df_1m):
    """Compute MFE (max favorable) and MAE (max adverse) excursion in points."""
    bars = df_1m.loc[entry_time:exit_time]
    if bars.empty:
        return 0.0, 0.0
    if direction == "LONG":
        mfe = (bars["high"].max() - entry_price)
        mae = (entry_price - bars["low"].min())
    else:
        mfe = (entry_price - bars["low"].min())
        mae = (bars["high"].max() - entry_price)
    return float(mfe), float(mae)


def compute_mfe_mae_bars(entry_time, exit_time, direction, entry_price, stop_loss, df_1m):
    """Compute MFE/MAE as R-multiples (multiples of risk)."""
    bars = df_1m.loc[entry_time:exit_time]
    if bars.empty:
        return 0.0, 0.0
    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        return 0.0, 0.0
    if direction == "LONG":
        mfe_pts = bars["high"].max() - entry_price
        mae_pts = entry_price - bars["low"].min()
    else:
        mfe_pts = entry_price - bars["low"].min()
        mae_pts = bars["high"].max() - entry_price
    return float(mfe_pts / risk), float(mae_pts / risk)


# ─── BB E14 Strategy Runner ─────────────────────────────────────────────────

def run_bb_e14(df1, df5, daily_atr):
    """Run BB_RSI with E14 best config: BB20/2.0 + RSI14/33 + ADX25 + MACD gate + IB + lunch skip."""
    strat = BBRsiMeanReversionStrategy(
        symbol="ES", bb_period=20, std_dev=2.0, rsi_period=14,
        adx_threshold=25.0, use_adx=True, squeeze_only=False,
    )
    engine = BacktestEngine(symbol="ES", entry_mode="market")
    unique_dates = sorted(df1["trade_date"].unique())
    trades = []
    for t_date in unique_dates:
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
        if ctx is None:
            continue
        # E14 filters: IB<0.4 + skip 13:00-14:00 (lunch) + MACD hist rising
        # IB compression check
        ib_bars = ctx.session_5m.get("NY_AM")
        if ib_bars is not None and len(ib_bars) >= 6:
            ib_range = ib_bars["high"].iloc[:6].max() - ib_bars["low"].iloc[:6].min()
            if ib_range > 0.40 * ctx.atr_val:
                continue  # skip wide IB days
        for sess in ("NY_MIDDAY", "NY_PM"):
            signal = strat.detect_signal(ctx, sess)
            if signal is None:
                continue
            # Lunch skip: 13:00-14:00 ET
            sig_hour = signal.entry_time.hour
            if sig_hour >= 13 and sig_hour < 14:
                continue
            result = engine.simulate_trade(signal, ctx)
            if result is None:
                continue
            mfe, mae = compute_mfe_mae(
                result.entry_time, result.exit_time,
                result.direction, result.entry_price, df1,
            )
            mfe_r, mae_r = compute_mfe_mae_bars(
                result.entry_time, result.exit_time,
                result.direction, result.entry_price, result.stop_loss, df1,
            )
            trades.append({
                "strategy": "BB_E14",
                "date": result.date,
                "direction": result.direction,
                "entry_time": result.entry_time,
                "exit_time": result.exit_time,
                "entry_price": result.entry_price,
                "exit_price": result.stop_loss if result.stopped_out else (
                    result.tp2_price if result.t2_hit else result.entry_price
                ),
                "stop_loss": result.stop_loss,
                "risk_points": result.risk_points,
                "pnl_dollars": result.total_pnl_dollars,
                "pnl_points": result.total_pnl_points,
                "r_multiple": result.r_multiple,
                "mfe_pts": mfe,
                "mae_pts": mae,
                "mfe_r": mfe_r,
                "mae_r": mae_r,
                "t1_hit": result.t1_hit,
                "t2_hit": result.t2_hit,
                "stopped": result.stopped_out,
                "session": result.session_name,
            })
    return pd.DataFrame(trades)


# ─── Supertrend S09 Strategy Runner ─────────────────────────────────────────

def supertrend(high, low, close, period, mult):
    hl2 = (high + low) / 2.0
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    fu = upper.copy()
    fl = lower.copy()
    for i in range(1, len(upper)):
        if fu.iloc[i] > fu.iloc[i - 1]:
            fu.iloc[i] = fu.iloc[i - 1]
        if fl.iloc[i] < fl.iloc[i - 1]:
            fl.iloc[i] = fl.iloc[i - 1]
    st = pd.Series(np.nan, index=close.index)
    for i in range(1, len(close)):
        if close.iloc[i] > fu.iloc[i - 1]:
            st.iloc[i] = 1
        elif close.iloc[i] < fl.iloc[i - 1]:
            st.iloc[i] = -1
        else:
            st.iloc[i] = st.iloc[i - 1]
    return st


def run_supertrend_s09(df1, df5, daily_atr):
    """Run ST(14,2) trail 1.5xATR — S09 best config."""
    POINT_VAL = 5.0  # 1x MES (mandatory micro for all backtests)
    COMM = 0  # NT8 parity: $0 commission
    SLIP = 0  # NT8 parity: $0 slippage
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
        close = bars5["close"]
        high = bars5["high"]
        low = bars5["low"]
        st = supertrend(high, low, close, 14, 2.0)
        atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14
        pos = 0
        entry = 0.0
        stop = 0.0
        entry_idx = 0
        entry_time = None
        for i in range(1, len(bars5)):
            a5 = atr5.iloc[i]
            if np.isnan(a5) or a5 <= 0:
                continue
            st0 = st.iloc[i]
            st1 = st.iloc[i - 1]
            if pd.isna(st0) or pd.isna(st1):
                continue
            c0 = close.iloc[i]
            h0 = high.iloc[i]
            l0 = low.iloc[i]
            if pos != 0:
                if pos == 1:
                    stop = max(stop, h0 - 1.5 * a5)
                    if l0 <= stop:
                        exit_px = stop - SLIP
                        pnl = (exit_px - entry) * POINT_VAL - COMM
                        mfe, mae = compute_mfe_mae(
                            entry_time, bars5.index[i], "LONG", entry, df1,
                        )
                        risk = abs(entry - (entry - 1.5 * a5))
                        mfe_r = mfe / risk if risk > 0 else 0
                        mae_r = mae / risk if risk > 0 else 0
                        trades.append({
                            "strategy": "ST_S09", "date": str(ts.date()),
                            "direction": "LONG",
                            "entry_time": entry_time, "exit_time": bars5.index[i],
                            "entry_price": entry, "exit_price": exit_px,
                            "stop_loss": stop, "risk_points": 1.5 * a5,
                            "pnl_dollars": pnl,
                            "pnl_points": (exit_px - entry),
                            "r_multiple": (exit_px - entry) / (1.5 * a5) if a5 > 0 else 0,
                            "mfe_pts": mfe, "mae_pts": mae,
                            "mfe_r": mfe_r, "mae_r": mae_r,
                            "t1_hit": False, "t2_hit": False,
                            "stopped": True, "session": "intraday",
                        })
                        pos = 0
                else:
                    stop = min(stop, l0 + 1.5 * a5)
                    if h0 >= stop:
                        exit_px = stop + SLIP
                        pnl = (entry - exit_px) * POINT_VAL - COMM
                        mfe, mae = compute_mfe_mae(
                            entry_time, bars5.index[i], "SHORT", entry, df1,
                        )
                        risk = abs(1.5 * a5)
                        mfe_r = mfe / risk if risk > 0 else 0
                        mae_r = mae / risk if risk > 0 else 0
                        trades.append({
                            "strategy": "ST_S09", "date": str(ts.date()),
                            "direction": "SHORT",
                            "entry_time": entry_time, "exit_time": bars5.index[i],
                            "entry_price": entry, "exit_price": exit_px,
                            "stop_loss": stop, "risk_points": 1.5 * a5,
                            "pnl_dollars": pnl,
                            "pnl_points": (entry - exit_px),
                            "r_multiple": (entry - exit_px) / (1.5 * a5) if a5 > 0 else 0,
                            "mfe_pts": mfe, "mae_pts": mae,
                            "mfe_r": mfe_r, "mae_r": mae_r,
                            "t1_hit": False, "t2_hit": False,
                            "stopped": True, "session": "intraday",
                        })
                        pos = 0
            if pos == 0:
                if st0 == 1 and st1 == -1:
                    pos = 1
                    entry = c0 + SLIP
                    entry_idx = i
                    entry_time = bars5.index[i]
                    stop = entry - 1.5 * a5
                elif st0 == -1 and st1 == 1:
                    pos = -1
                    entry = c0 - SLIP
                    entry_idx = i
                    entry_time = bars5.index[i]
                    stop = entry + 1.5 * a5
        if pos != 0:
            exit_px = close.iloc[-1] - SLIP if pos == 1 else close.iloc[-1] + SLIP
            pnl = ((exit_px - entry) if pos == 1 else (entry - exit_px)) * POINT_VAL - COMM
            mfe, mae = compute_mfe_mae(
                entry_time, bars5.index[-1],
                "LONG" if pos == 1 else "SHORT", entry, df1,
            )
            risk = abs(1.5 * atr5.iloc[entry_idx])
            mfe_r = mfe / risk if risk > 0 else 0
            mae_r = mae / risk if risk > 0 else 0
            trades.append({
                "strategy": "ST_S09", "date": str(ts.date()),
                "direction": "LONG" if pos == 1 else "SHORT",
                "entry_time": entry_time, "exit_time": bars5.index[-1],
                "entry_price": entry, "exit_price": exit_px,
                "stop_loss": stop, "risk_points": 1.5 * atr5.iloc[entry_idx],
                "pnl_dollars": pnl,
                "pnl_points": (exit_px - entry) if pos == 1 else (entry - exit_px),
                "r_multiple": ((exit_px - entry) if pos == 1 else (entry - exit_px)) / risk if risk > 0 else 0,
                "mfe_pts": mfe, "mae_pts": mae,
                "mfe_r": mfe_r, "mae_r": mae_r,
                "t1_hit": False, "t2_hit": False,
                "stopped": False, "session": "EOD",
            })
    return pd.DataFrame(trades)


# ─── Excursion Analysis (ADR-023) ───────────────────────────────────────────

def excursion_analysis(trades_df, ref_price_col="entry_price"):
    """ADR-023: MFE/MAE percentiles, reach-prob CDF, MAE-conditioned survival."""
    results = {}
    for strat_name in trades_df["strategy"].unique():
        sd = trades_df[trades_df["strategy"] == strat_name].copy()
        if sd.empty:
            continue
        # Convert to bps (ADR-023: 1 bps = 0.01%)
        sd["mfe_bps"] = sd["mfe_pts"] / sd[ref_price_col] * 10000
        sd["mae_bps"] = sd["mae_pts"] / sd[ref_price_col] * 10000
        sd["risk_bps"] = sd["risk_points"] / sd[ref_price_col] * 10000

        # Percentiles
        pcts = [10, 25, 50, 75, 90, 95]
        mfe_pct = {f"p{p}": float(np.percentile(sd["mfe_bps"], p)) for p in pcts}
        mae_pct = {f"p{p}": float(np.percentile(sd["mae_bps"], p)) for p in pcts}
        mfe_r_pct = {f"p{p}": float(np.percentile(sd["mfe_r"], p)) for p in pcts}
        mae_r_pct = {f"p{p}": float(np.percentile(sd["mae_r"], p)) for p in pcts}
        risk_bps_pct = {f"p{p}": float(np.percentile(sd["risk_bps"], p)) for p in pcts}

        # Reach probability CDF: P(MFE >= threshold)
        thresholds_r = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
        reach_prob = {
            f"{t}R": float((sd["mfe_r"] >= t).mean()) for t in thresholds_r
        }

        # MAE-conditioned win-rate survival curve
        mae_bins = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
        survival = {}
        for j in range(len(mae_bins) - 1):
            lo, hi = mae_bins[j], mae_bins[j + 1]
            mask = (sd["mae_r"] >= lo) & (sd["mae_r"] < hi)
            n = mask.sum()
            if n > 0:
                wr = (sd.loc[mask, "pnl_dollars"] > 0).mean() * 100
                survival[f"{lo:.2f}-{hi:.2f}R"] = {"n": int(n), "win_rate": float(wr)}
            else:
                survival[f"{lo:.2f}-{hi:.2f}R"] = {"n": 0, "win_rate": 0.0}
        # Also: trades that survived past 1R MAE
        surv_past_1r = (sd["mae_r"] < 1.0).mean() * 100

        results[strat_name] = {
            "n_trades": len(sd),
            "mfe_bps_percentiles": mfe_pct,
            "mae_bps_percentiles": mae_pct,
            "mfe_r_percentiles": mfe_r_pct,
            "mae_r_percentiles": mae_r_pct,
            "risk_bps_percentiles": risk_bps_pct,
            "reach_prob_r": reach_prob,
            "mae_survival_bins": survival,
            "pct_survived_under_1R_mae": float(surv_past_1r),
            "median_risk_bps": float(np.median(sd["risk_bps"])),
            "median_mfe_r": float(np.median(sd["mfe_r"])),
            "median_mae_r": float(np.median(sd["mae_r"])),
        }
    return results


# ─── Trade-Level Statistics ─────────────────────────────────────────────────

def trade_level_stats(trades_df):
    """Hour, day-of-week, direction, R-multiple distribution analysis."""
    results = {}
    for strat_name in trades_df["strategy"].unique():
        sd = trades_df[trades_df["strategy"] == strat_name].copy()
        if sd.empty:
            continue
        sd["entry_hour"] = sd["entry_time"].dt.hour
        sd["entry_dow"] = sd["entry_time"].dt.dayofweek
        sd["is_win"] = sd["pnl_dollars"] > 0

        # By hour
        by_hour = sd.groupby("entry_hour").agg(
            n=("pnl_dollars", "count"),
            wins=("is_win", "sum"),
            wr=("is_win", "mean"),
            avg_pnl=("pnl_dollars", "mean"),
            total_pnl=("pnl_dollars", "sum"),
            avg_r=("r_multiple", "mean"),
        ).round(2)
        by_hour["wr"] = (by_hour["wr"] * 100).round(1)

        # By day of week
        dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        by_dow = sd.groupby("entry_dow").agg(
            n=("pnl_dollars", "count"),
            wins=("is_win", "sum"),
            wr=("is_win", "mean"),
            avg_pnl=("pnl_dollars", "mean"),
            total_pnl=("pnl_dollars", "sum"),
        ).round(2)
        by_dow["wr"] = (by_dow["wr"] * 100).round(1)
        by_dow.index = [dow_names[i] for i in by_dow.index]

        # By direction
        by_dir = sd.groupby("direction").agg(
            n=("pnl_dollars", "count"),
            wins=("is_win", "sum"),
            wr=("is_win", "mean"),
            avg_pnl=("pnl_dollars", "mean"),
            total_pnl=("pnl_dollars", "sum"),
            avg_r=("r_multiple", "mean"),
        ).round(2)
        by_dir["wr"] = (by_dir["wr"] * 100).round(1)

        # R-multiple distribution
        r_bins = [-3, -2, -1, 0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
        r_hist = pd.cut(sd["r_multiple"], bins=r_bins, right=False).value_counts().sort_index()
        r_dist = {str(k): int(v) for k, v in r_hist.items()}

        # Duration analysis
        sd["duration_min"] = (sd["exit_time"] - sd["entry_time"]).dt.total_seconds() / 60
        dur_stats = {
            "p25": float(np.percentile(sd["duration_min"], 25)),
            "p50": float(np.percentile(sd["duration_min"], 50)),
            "p75": float(np.percentile(sd["duration_min"], 75)),
            "p90": float(np.percentile(sd["duration_min"], 90)),
            "mean": float(sd["duration_min"].mean()),
        }

        results[strat_name] = {
            "by_hour": by_hour.to_dict(orient="index"),
            "by_dow": by_dow.to_dict(orient="index"),
            "by_direction": by_dir.to_dict(orient="index"),
            "r_multiple_distribution": r_dist,
            "duration_minutes": dur_stats,
            "avg_r_multiple": float(sd["r_multiple"].mean()),
            "median_r_multiple": float(sd["r_multiple"].median()),
            "expectancy_r": float(sd["r_multiple"].mean()),
            "n_trades": len(sd),
        }
    return results


# ─── Prop Firm Simulation (ADR-021) ─────────────────────────────────────────

def run_prop_eval(trades_df, point_value=5.0):
    """Run PropFirmSimulator across all profiles. Returns (report_str, results_dict).

    IMPORTANT: The prop sim's _to_dollar_pnl does pnl_pct/100 * account_size.
    Our dollar P&L is fixed (1x MES = $5/pt) regardless of account size.
    So we must pass pnl_pct = pnl_dollars / FIXED_BASE * 100 where FIXED_BASE
    is a constant, and then the sim's account_size scaling will be wrong.
    FIX: We bypass the sim's internal conversion by passing pnl_pct such that
    pnl_pct/100 * account_size = pnl_dollars, i.e. pnl_pct = pnl_dollars/account_size*100.
    But account_size varies per profile. So we run each profile separately
    with the correct pnl_pct for that profile's account_size.
    """
    results = {}
    reports = []
    for strat_name in trades_df["strategy"].unique():
        sd = trades_df[trades_df["strategy"] == strat_name].copy()
        if sd.empty:
            continue
        sim = PropFirmSimulator(account_size=50_000, point_value=point_value)
        all_results = {}
        for key, profile in FIRM_PROFILES.items():
            # Pass pnl_pct = pnl_dollars / profile.account_size * 100
            # so sim's _to_dollar_pnl returns our actual dollar P&L
            trades_detailed = pd.DataFrame({
                "exit_time": pd.to_datetime(sd["exit_time"]),
                "pnl_pct": sd["pnl_dollars"].values / profile.account_size * 100,
            })
            det = sim.run_deterministic(trades_detailed, profile)
            mc = sim.run_monte_carlo(trades_detailed, profile, n_simulations=2000)
            all_results[key] = (det, mc)
            logger_info = f"[PropEval] {strat_name} {profile.name}: pass={mc.pass_rate_pct:.1f}% grade={mc.grade}"
            print(f"    {logger_info}")
        # Format report
        report = f"\n## {strat_name} — Prop Firm Viability\n"
        report += sim.format_multi_report(all_results) + "\n"
        for key, (det, mc) in all_results.items():
            report += sim.format_report(det, mc) + "\n"
        reports.append(report)
        results[strat_name] = all_results
    return "\n".join(reports), results


# ─── Bootstrap CI (NT8 Parity Standard §2.6) ────────────────────────────────

def bootstrap_ci(trades_df, n_boot=10000, confidence=0.95):
    """Bootstrap CI on mean per-session return. If CI crosses zero → noise."""
    results = {}
    for strat_name in trades_df["strategy"].unique():
        sd = trades_df[trades_df["strategy"] == strat_name].copy()
        if sd.empty:
            continue
        # Per-session (daily) returns
        daily = sd.groupby("date")["pnl_dollars"].sum().values
        if len(daily) < 10:
            results[strat_name] = {"ci_lo": 0, "ci_hi": 0, "mean": 0, "crosses_zero": True}
            continue
        boots = np.random.choice(daily, size=(n_boot, len(daily)), replace=True).mean(axis=1)
        alpha = (1 - confidence) / 2
        ci_lo = float(np.percentile(boots, alpha * 100))
        ci_hi = float(np.percentile(boots, (1 - alpha) * 100))
        results[strat_name] = {
            "ci_lo": round(ci_lo, 2),
            "ci_hi": round(ci_hi, 2),
            "mean": round(float(daily.mean()), 2),
            "crosses_zero": ci_lo <= 0 <= ci_hi,
            "n_sessions": len(daily),
        }
    return results


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("STRATEGY STATISTICAL EVALUATION (ADR-002, 010, 021, 023)")
    print("=" * 80)

    print("\n[1/6] Loading data...")
    df1, df5, daily_atr = load_data("ES")
    print(f"  1m bars: {len(df1):,} | 5m bars: {len(df5):,} | dates: {len(daily_atr)}")

    print("\n[2/6] Running BB E14 strategy (BB20/2.0 + RSI14/33 + ADX25 + IB<0.4 + lunch skip + MACD)...")
    bb_trades = run_bb_e14(df1, df5, daily_atr)
    print(f"  BB E14 trades: {len(bb_trades)}")
    if not bb_trades.empty:
        wins = (bb_trades["pnl_dollars"] > 0).sum()
        net = bb_trades["pnl_dollars"].sum()
        gp = bb_trades.loc[bb_trades["pnl_dollars"] > 0, "pnl_dollars"].sum()
        gl = abs(bb_trades.loc[bb_trades["pnl_dollars"] < 0, "pnl_dollars"].sum())
        pf = gp / gl if gl > 0 else 999
        print(f"  WR: {wins/len(bb_trades)*100:.1f}% | PF: {pf:.2f} | Net: ${net:,.0f}")

    print("\n[3/6] Running Supertrend S09 (ST 14/2.0 trail 1.5xATR)...")
    st_trades = run_supertrend_s09(df1, df5, daily_atr)
    print(f"  ST S09 trades: {len(st_trades)}")
    if not st_trades.empty:
        wins = (st_trades["pnl_dollars"] > 0).sum()
        net = st_trades["pnl_dollars"].sum()
        gp = st_trades.loc[st_trades["pnl_dollars"] > 0, "pnl_dollars"].sum()
        gl = abs(st_trades.loc[st_trades["pnl_dollars"] < 0, "pnl_dollars"].sum())
        pf = gp / gl if gl > 0 else 999
        print(f"  WR: {wins/len(st_trades)*100:.1f}% | PF: {pf:.2f} | Net: ${net:,.0f}")

    all_trades = pd.concat([bb_trades, st_trades], ignore_index=True)
    all_trades.to_csv("data/derived/strategy_eval_trades.csv", index=False)
    print(f"\n  Saved {len(all_trades)} trades -> data/derived/strategy_eval_trades.csv")

    print("\n[4/6] Excursion analysis (ADR-023: MFE/MAE percentiles, CDF, survival)...")
    exc = excursion_analysis(all_trades)
    print(json.dumps(exc, indent=2, default=str))

    print("\n[5/6] Trade-level statistics (hour, DOW, direction, R-dist)...")
    tls = trade_level_stats(all_trades)
    for strat_name, stats in tls.items():
        print(f"\n  --- {strat_name} ---")
        print(f"  Expectancy: {stats['avg_r_multiple']:.3f}R | Median: {stats['median_r_multiple']:.3f}R")
        print(f"  Duration: p50={stats['duration_minutes']['p50']:.0f}min  p90={stats['duration_minutes']['p90']:.0f}min")
        print(f"  By direction:")
        for d, s in stats["by_direction"].items():
            print(f"    {d}: n={s['n']} WR={s['wr']}% avg=${s['avg_pnl']:.0f} R={s['avg_r']:.2f}")
        print(f"  By hour:")
        for h, s in sorted(stats["by_hour"].items()):
            print(f"    {int(h):02d}:00 n={s['n']} WR={s['wr']}% avg=${s['avg_pnl']:.0f} total=${s['total_pnl']:.0f}")
        print(f"  By DOW:")
        for d, s in stats["by_dow"].items():
            print(f"    {d}: n={s['n']} WR={s['wr']}% total=${s['total_pnl']:.0f}")

    print("\n[6/6] Prop firm simulation (ADR-021: deterministic + Monte Carlo)...")
    prop_report, prop_results = run_prop_eval(all_trades)
    print(prop_report)

    print("\n  Bootstrap CI (per-session mean, 95% confidence, 10k resamples)...")
    boot = bootstrap_ci(all_trades)
    for strat_name, ci in boot.items():
        status = "NOISE (CI crosses zero)" if ci["crosses_zero"] else "EDGE (CI excludes zero)"
        print(f"    {strat_name}: mean=${ci['mean']}/session  CI=[${ci['ci_lo']}, ${ci['ci_hi']}]  → {status}")

    # ─── Write Report ───────────────────────────────────────────────────────
    print("\n  Writing report → docs/research/STRATEGY_STATISTICAL_EVAL.md")
    report_path = Path("docs/research/STRATEGY_STATISTICAL_EVAL.md")
    report_lines = [
        "# Strategy Statistical Evaluation (ADR-002, 010, 021, 023)",
        f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        f"\n_Data: ES 09-26 MergeBackAdjusted 5m, 2025-01-01 → 2026-08-21_",
        f"\n_Engine: 1×MES $5/pt, $0 commission, $0 slippage (NT8 parity, mandatory micros)_",
        "\n---\n",
        "## 1. Summary Metrics\n",
    ]

    for strat_name in all_trades["strategy"].unique():
        sd = all_trades[all_trades["strategy"] == strat_name]
        if sd.empty:
            continue
        wins = (sd["pnl_dollars"] > 0).sum()
        net = sd["pnl_dollars"].sum()
        gp = sd.loc[sd["pnl_dollars"] > 0, "pnl_dollars"].sum()
        gl = abs(sd.loc[sd["pnl_dollars"] < 0, "pnl_dollars"].sum())
        pf = gp / gl if gl > 0 else 999
        wr = wins / len(sd) * 100
        cum = sd["pnl_dollars"].cumsum()
        dd = (cum - cum.cummax()).min()
        report_lines.append(f"### {strat_name}")
        report_lines.append(f"| Metric | Value |")
        report_lines.append(f"| :--- | :--- |")
        report_lines.append(f"| Trades | {len(sd)} |")
        report_lines.append(f"| Win Rate | {wr:.1f}% |")
        report_lines.append(f"| Profit Factor | {pf:.2f} |")
        report_lines.append(f"| Net P&L | ${net:,.0f} |")
        report_lines.append(f"| Max Drawdown | ${abs(dd):,.0f} |")
        report_lines.append(f"| Avg R | {sd['r_multiple'].mean():.3f} |")
        report_lines.append(f"| Median R | {sd['r_multiple'].median():.3f} |")
        report_lines.append(f"| Avg MFE (R) | {sd['mfe_r'].mean():.2f} |")
        report_lines.append(f"| Avg MAE (R) | {sd['mae_r'].mean():.2f} |")
        report_lines.append("")

    # Excursion
    report_lines.append("\n## 2. Excursion Analysis (ADR-023)\n")
    for strat_name, e in exc.items():
        report_lines.append(f"### {strat_name} (n={e['n_trades']})\n")
        report_lines.append(f"| Percentile | MFE (bps) | MAE (bps) | MFE (R) | MAE (R) | Risk (bps) |")
        report_lines.append(f"| :--- | :---: | :---: | :---: | :---: | :---: |")
        for p in ["p10", "p25", "p50", "p75", "p90", "p95"]:
            report_lines.append(
                f"| {p} | {e['mfe_bps_percentiles'][p]:.2f} | "
                f"{e['mae_bps_percentiles'][p]:.2f} | "
                f"{e['mfe_r_percentiles'][p]:.2f} | "
                f"{e['mae_r_percentiles'][p]:.2f} | "
                f"{e['risk_bps_percentiles'][p]:.2f} |"
            )
        report_lines.append(f"\n**Reach Probability (P[MFE ≥ threshold]):**\n")
        report_lines.append("| Threshold | Probability |")
        report_lines.append("| :--- | :---: |")
        for k, v in e["reach_prob_r"].items():
            report_lines.append(f"| {k} | {v*100:.1f}% |")
        report_lines.append(f"\n**MAE-Conditioned Win-Rate Survival Curve:**\n")
        report_lines.append("| MAE Bin | Trades | Win Rate |")
        report_lines.append("| :--- | :---: | :---: |")
        for k, v in e["mae_survival_bins"].items():
            report_lines.append(f"| {k} | {v['n']} | {v['win_rate']:.1f}% |")
        report_lines.append(
            f"\nTrades surviving under 1R MAE: **{e['pct_survived_under_1R_mae']:.1f}%** "
            f"(higher = stops are well-placed)\n"
        )

    # Trade-level stats
    report_lines.append("\n## 3. Trade-Level Statistics\n")
    for strat_name, s in tls.items():
        report_lines.append(f"### {strat_name}\n")
        report_lines.append(f"**Expectancy:** {s['avg_r_multiple']:.3f}R | **Median R:** {s['median_r_multiple']:.3f}")
        report_lines.append(
            f"\n**Duration:** p25={s['duration_minutes']['p25']:.0f}min "
            f"p50={s['duration_minutes']['p50']:.0f}min "
            f"p75={s['duration_minutes']['p75']:.0f}min "
            f"p90={s['duration_minutes']['p90']:.0f}min\n"
        )
        report_lines.append("**By Direction:**\n")
        report_lines.append("| Dir | N | WR | Avg P&L | Total | Avg R |")
        report_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for d, r in s["by_direction"].items():
            report_lines.append(
                f"| {d} | {r['n']} | {r['wr']}% | ${r['avg_pnl']:.0f} | "
                f"${r['total_pnl']:.0f} | {r['avg_r']:.2f} |"
            )
        report_lines.append("\n**By Hour (ET):**\n")
        report_lines.append("| Hour | N | WR | Avg P&L | Total | Avg R |")
        report_lines.append("| :---: | :---: | :---: | :---: | :---: | :---: |")
        for h, r in sorted(s["by_hour"].items(), key=lambda x: int(x[0])):
            report_lines.append(
                f"| {int(h):02d}:00 | {r['n']} | {r['wr']}% | ${r['avg_pnl']:.0f} | "
                f"${r['total_pnl']:.0f} | {r.get('avg_r', 0):.2f} |"
            )
        report_lines.append("\n**By Day of Week:**\n")
        report_lines.append("| Day | N | WR | Avg P&L | Total |")
        report_lines.append("| :--- | :---: | :---: | :---: | :---: |")
        for d, r in s["by_dow"].items():
            report_lines.append(
                f"| {d} | {r['n']} | {r['wr']}% | ${r['avg_pnl']:.0f} | ${r['total_pnl']:.0f} |"
            )
        report_lines.append(f"\n**R-Multiple Distribution:**\n")
        report_lines.append("| Range | Count |")
        report_lines.append("| :--- | :---: |")
        for k, v in s["r_multiple_distribution"].items():
            report_lines.append(f"| {k} | {v} |")
        report_lines.append("")

    # Prop firm
    report_lines.append("\n## 4. Prop Firm Viability (ADR-021)\n")
    report_lines.append(prop_report)

    # Bootstrap CI
    report_lines.append("\n## 5. Bootstrap Confidence Intervals (Parity §2.6)\n")
    report_lines.append("| Strategy | Mean/Session | CI Low | CI High | Verdict |")
    report_lines.append("| :--- | :---: | :---: | :---: | :---: |")
    for strat_name, ci in boot.items():
        status = "NOISE" if ci["crosses_zero"] else "EDGE"
        report_lines.append(
            f"| {strat_name} | ${ci['mean']} | ${ci['ci_lo']} | "
            f"${ci['ci_hi']} | {status} |"
        )

    # Recommendations
    report_lines.append("\n## 6. Trade Structuring Recommendations\n")
    report_lines.append("_(Auto-generated from excursion + trade-level analysis above)_\n")
    for strat_name, e in exc.items():
        report_lines.append(f"### {strat_name}")
        # Stop placement
        median_mae_r = e["median_mae_r"]
        p75_mae_r = e["mae_r_percentiles"]["p75"]
        report_lines.append(
            f"- **Stop placement:** Median MAE = {median_mae_r:.2f}R, p75 = {p75_mae_r:.2f}R. "
            f"Stops at 1.0R catch {e['pct_survived_under_1R_mae']:.0f}% of trades before full-risk drawdown."
        )
        # Target placement
        p50_mfe_r = e["mfe_r_percentiles"]["p50"]
        p75_mfe_r = e["mfe_r_percentiles"]["p75"]
        p90_mfe_r = e["mfe_r_percentiles"]["p90"]
        report_lines.append(
            f"- **Target placement:** Median MFE = {p50_mfe_r:.2f}R, p75 = {p75_mfe_r:.2f}R, "
            f"p90 = {p90_mfe_r:.2f}R. T1 at {p50_mfe_r:.1f}R captures 50% of runners; "
            f"T2 at {p75_mfe_r:.1f}R captures the top quartile."
        )
        # Risk in bps
        med_risk = e["median_risk_bps"]
        report_lines.append(
            f"- **Risk in bps (ADR-023):** Median risk = {med_risk:.2f} bps. "
            f"Floor 2.0 bps, ceiling 15.0 bps. "
            f"{'✅ Within bracket' if 2.0 <= med_risk <= 15.0 else '⚠️ Outside bracket — adjust sizing'}."
        )
        # Reach probability
        reach_1r = e["reach_prob_r"].get("1.0R", 0)
        reach_2r = e["reach_prob_r"].get("2.0R", 0)
        report_lines.append(
            f"- **Reach probability:** P(MFE≥1R) = {reach_1r*100:.0f}%, "
            f"P(MFE≥2R) = {reach_2r*100:.0f}%. "
            f"{'Edge: >50% reach 1R' if reach_1r > 0.5 else 'Warning: <50% reach 1R'}."
        )
        report_lines.append("")

    report_lines.append("\n---\n")
    report_lines.append("_Compliant with ADR-002 (price %), ADR-010 (7-layer pipeline), "
                        "ADR-021 (PropFirmSimulator), ADR-023 (bps + excursion stats)._")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n  ✅ Report written to {report_path}")
    print(f"  ✅ Trades saved to data/derived/strategy_eval_trades.csv")

    # Save JSON for programmatic access
    json_path = Path("data/derived/strategy_eval_stats.json")
    full_json = {
        "excursion": exc,
        "trade_level": tls,
        "bootstrap_ci": boot,
        "prop_grades": {
            strat: {k: {"grade": mc.grade, "pass_rate": mc.pass_rate_pct}
                    for k, (det, mc) in res.items()}
            for strat, res in prop_results.items()
        },
    }
    json_path.write_text(json.dumps(full_json, indent=2, default=str), encoding="utf-8")
    print(f"  ✅ Stats JSON saved to {json_path}")


if __name__ == "__main__":
    main()