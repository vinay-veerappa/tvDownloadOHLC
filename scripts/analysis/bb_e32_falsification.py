"""E32 — BB falsification ladder. Does the Bollinger condition add anything?

Arms (all long-only, identical ATR-normalized exits: SL 1xATR5, TP1 1xATR5, TP2 2xATR5,
market entry next 1m bar, max 1 trade per allowed hour per day):

  T0   time only        — long at every allowed hour, no signal condition
  T1   time + extension — prior 5m bar closed at 20-bar closing low, current bar hooks up
  T1x  T1 + ADX25 gate  — mirrors T2's structure with a non-BB extension detector
  T2   time + BB + ADX  — the E22 entry condition (BB touch + RSI hook + ADX25)

Windows:
  4h   — the h20/h00/h04/h07 allowlist from E28 (overfit-flagged)
  full — the whole overnight block 19:00-08:00 (robustness check)

Readout:
  T0 ~= T2                -> BB is decoration; strategy is session timing
  T1/T1x ~= T2 > T0       -> extension real, BB redundant -> simplify
  T2 > T1x > T1 > T0      -> BB earns its place

Usage:
  .\\.venv\\Scripts\\python.exe scripts/analysis/bb_e32_falsification.py
"""
import sys
import warnings

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.range_strategy_comparison import (
    BacktestEngine,
    TradeSignal,
    _adx,
    _wilder_rsi,
    build_day_context,
)

warnings.filterwarnings("ignore", category=FutureWarning)

HOURS_4 = {20, 0, 4, 7}
HOURS_FULL = set(range(19, 24)) | set(range(0, 8))
ARMS = ["T0", "T1", "T1x", "T2"]


def scan_arm(bars5: pd.DataFrame, arm: str, hours: set, adx_threshold: float = 25.0,
             n_ext: int = 20, bb_period: int = 20, std_dev: float = 1.8) -> list:
    """Scan one day's GLOBEX 5m bars for the arm's entry condition. One trade/hour/day."""
    if bars5 is None or len(bars5) < bb_period + 10:
        return []
    close = bars5["close"]
    high = bars5["high"]
    low = bars5["low"]

    sma = close.rolling(bb_period).mean()
    std = close.rolling(bb_period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    rsi = _wilder_rsi(close, 14)
    adx_s = _adx(high, low, close, 14)
    atr5 = (high.rolling(14).max() - low.rolling(14).min()) / 14.0

    signals = []
    used_hours = set()
    for i in range(max(2, n_ext + 1), len(bars5)):
        t = bars5.index[i]
        if t.hour not in hours or t.hour in used_hours:
            continue

        if arm == "T0":
            cond = True
        elif arm in ("T1", "T1x"):
            # extension: prior bar closed at the 20-bar closing low, current bar hooks up
            cond = (
                close.iloc[i - 1] <= close.iloc[i - 1 - n_ext:i - 1].min()
                and close.iloc[i] > close.iloc[i - 1]
            )
            if arm == "T1x":
                adx_val = adx_s.iloc[i]
                cond = cond and (np.isnan(adx_val) or adx_val < adx_threshold)
        elif arm == "T2":
            adx_val = adx_s.iloc[i]
            if not (np.isnan(adx_val) or adx_val < adx_threshold):
                continue
            cond = (
                close.iloc[i - 1] < lower.iloc[i - 1]
                and rsi.iloc[i - 1] < 33
                and close.iloc[i] > lower.iloc[i]
                and rsi.iloc[i] > rsi.iloc[i - 1]
                and close.iloc[i] < sma.iloc[i]
                and rsi.iloc[i] < 50
            )
        else:
            raise ValueError(arm)

        if not cond:
            continue

        entry = float(close.iloc[i])
        a5 = float(atr5.iloc[i])
        if np.isnan(a5) or a5 <= 0:
            continue
        signals.append(TradeSignal(
            direction="LONG", entry_price=entry,
            stop_loss=entry - a5, tp1_price=entry + a5, tp2_price=entry + 2 * a5,
            risk_points=a5, entry_time=t, session_name="GLOBEX",
            metadata={"arm": arm, "hour": t.hour},
        ))
        used_hours.add(t.hour)
    return signals


def main():
    print("Loading NT MergeBA ES...")
    df1, df5 = load_nt("ES")
    df_daily = df1.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    tr = pd.concat([
        df_daily["high"] - df_daily["low"],
        (df_daily["high"] - df_daily["close"].shift(1)).abs(),
        (df_daily["low"] - df_daily["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    daily_atr = tr.rolling(10, min_periods=1).mean()

    df1["trade_date"] = df1.index.date
    evening = df1.index.hour >= 18
    df1.loc[evening, "trade_date"] = (df1.loc[evening].index + pd.Timedelta(days=1)).date
    unique_dates = sorted(df1["trade_date"].unique())

    engine = BacktestEngine("ES", tick_size=0.25, entry_mode="market")
    trades = {f"{arm}_{win}": [] for arm in ARMS for win in ("4h", "full")}

    print(f"Scanning {len(unique_dates)} days x {len(ARMS)} arms x 2 windows...")
    for k, t_date in enumerate(unique_dates):
        if k % 100 == 0:
            print(f"  Day {k}/{len(unique_dates)}")
        ts = pd.Timestamp(t_date)
        if ts.weekday() >= 5 or ts.year < 2025 or ts.year > 2026:
            continue
        ctx = build_day_context(ts, df1, df5, daily_atr, ib_minutes=30)
        if ctx is None:
            continue
        bars_gx = ctx.session_5m.get("GLOBEX")
        if bars_gx is None:
            continue
        for arm in ARMS:
            for win, hours in (("4h", HOURS_4), ("full", HOURS_FULL)):
                for sig in scan_arm(bars_gx, arm, hours):
                    sig.metadata["strategy_name"] = f"{arm}_{win}"
                    res = engine.simulate_trade(sig, ctx)
                    if res is not None:
                        res.strategy_name = f"{arm}_{win}"
                        trades[f"{arm}_{win}"].append(res.__dict__.copy())

    rows = []
    for key, tl in trades.items():
        tdf = pd.DataFrame(tl)
        row = {"arm": key}
        if tdf.empty:
            row.update(trades=0, wr=0, pf=0, net=0, dd=0, avg_r=0)
        else:
            pnl = tdf["total_pnl_dollars"]
            cum = pnl.cumsum()
            dd = (cum - cum.cummax()).min()
            gp, gl = pnl[pnl > 0].sum(), abs(pnl[pnl < 0].sum())
            row.update(
                trades=len(tdf), wr=round((pnl > 0).mean() * 100, 1),
                pf=round(gp / gl, 2) if gl > 0 else 999.0,
                net=round(pnl.sum()), dd=round(abs(dd)),
                avg_r=round(tdf["r_multiple"].mean(), 3),
            )
        rows.append(row)

    rdf = pd.DataFrame(rows)
    print("\n=== E32 falsification ladder (identical ATR exits, 1 trade/hour/day) ===")
    print(rdf.sort_values(["arm"]).to_string(index=False))

    rdf.to_csv("data/derived/bb_e32_falsification_results.csv", index=False)
    # save trade-level for the winner analysis
    all_trades = pd.DataFrame([t for tl in trades.values() for t in tl])
    all_trades.to_csv("data/derived/bb_e32_trades_detail.csv", index=False)
    print("\nSaved data/derived/bb_e32_falsification_results.csv + bb_e32_trades_detail.csv")


if __name__ == "__main__":
    main()