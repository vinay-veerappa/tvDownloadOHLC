"""Unified Strat benchmark — new engine vs legacy backtester on real data.

New path: StratSignalEngine (per-TF classify + FTFC attach + session gate +
measured-move targets + next-bar confirmation) + minimal forward simulator
(stop-first, target1, time/flatten exit, costs from strat_config.json).

Legacy path: StratBacktester over the same setups (structural mag1 targets)
for contrast.

Usage:
    .\\.venv\\Scripts\\python.exe -m scripts.strategies.the_strat.core.run_unified_strat
    ... --ticker NQ1 --start 2024-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import sys
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

_project_root = Path(__file__).resolve().parent
while _project_root.name and _project_root.name != "scripts":
    _project_root = _project_root.parent
if _project_root.name == "scripts":
    _project_root = _project_root.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.libs_py.the_strat.combos import ComboType
from scripts.libs_py.the_strat.config import load_strat_config
from scripts.libs_py.the_strat.signals import StratSignalEngine
from scripts.libs_py.the_strat.strategy import StratBacktester


def load_1m_et(ticker: str, start: str, end: str, source: str = "history") -> pd.DataFrame:
    if source == "live":
        base = ticker.replace("1", "").replace("!", "")
        p = _project_root / "data" / "live" / f"live_storage_-{base}.parquet"
    else:
        p = _project_root / "data" / f"{ticker}_1m.parquet"
        if not p.exists():
            p = _project_root / "data" / f"{ticker.replace('1', '')}_1m.parquet"
    if not p.exists():
        raise FileNotFoundError(f"No 1m parquet for {ticker} (source={source})")
    df = pd.read_parquet(p)
    if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
        pass  # historical shape: datetime index already
    elif "time" in df.columns:
        unit = "ms" if int(df["time"].max()) > 10**12 else "s"  # live=ms, legacy=s
        df = df.set_index(pd.to_datetime(df["time"], utc=True, unit=unit)).drop(columns=["time"])
    else:
        raise ValueError(f"Unrecognized 1m parquet shape for {ticker}: {df.index.dtype}")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df.index = df.index.tz_convert("America/New_York")
    df = df.sort_index()
    lo = pd.Timestamp(start, tz="America/New_York")
    hi = pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1)
    return df[(df.index >= lo) & (df.index < hi)]


def simulate_signals(
    sig: pd.DataFrame,
    bars: pd.DataFrame,
    point_value: float,
    commission: float,
    slip_pts: float,
    max_holding_bars: int,
    flatten_by: time,
    max_trades_per_day: int,
) -> pd.DataFrame:
    """Two-leg forward simulator — parity with NT8 FixedTP1TP2.

    50% scale at measured T1, runner stop moves to breakeven (entry) after TP1,
    runner exits at measured T2 / BE-stop / flatten / max hold. Stop-first
    intrabar (conservative). Skips overlapping signals. 1-contract economics:
    net = 0.5*leg1 + 0.5*leg2 (NT8 trades 2 contracts, same per-unit math).
    """
    h = bars["high"].values
    l = bars["low"].values
    c = bars["close"].values
    idx = bars.index
    pos = {t: i for i, t in enumerate(idx)}
    trades = []
    last_exit = -1
    day_counts: dict = {}
    for _, s in sig.sort_values("signal_time").iterrows():
        i = pos.get(s["signal_time"])
        if i is None or i <= last_exit:
            continue
        day = s["signal_time"].date()
        if day_counts.get(day, 0) >= max_trades_per_day:
            continue
        long = s["direction"] == 1
        entry = s["entry_price"] + (slip_pts if long else -slip_pts)
        stop = s["stop_price"]
        tgt1 = s["target1_price"]
        tgt2 = s["target2_price"]
        leg1 = leg2 = 0.0
        hit_t1 = hit_t2 = hit_s = False
        exit_idx, reason = i, "time_exit"

        for f in range(i, min(i + max_holding_bars, len(bars))):
            if idx[f].date() != day or idx[f].time() >= flatten_by:
                exit_idx = max(f - 1, i)
                px = c[exit_idx]
                leg1 = px - entry if long else entry - px
                if hit_t1:
                    leg2 = px - entry if long else entry - px
                else:
                    leg1 = leg2 = leg1
                reason = "flatten"
                break
            bh, bl = h[f], l[f]
            cur_stop = entry if hit_t1 else stop  # BE runner after TP1 (NT8 mirror)
            if long:
                if bl <= cur_stop:
                    px = cur_stop - slip_pts
                    if not hit_t1:
                        leg1 = leg2 = px - entry
                    else:
                        leg2 = px - entry
                    exit_idx, reason, hit_s = f, ("be_stop" if hit_t1 else "stop"), True
                    break
                if not hit_t1 and bh >= tgt1:
                    leg1 = tgt1 - entry
                    hit_t1 = True
                elif hit_t1 and bh >= tgt2:
                    leg2 = tgt2 - entry
                    exit_idx, reason, hit_t2 = f, "target2", True
                    break
            else:
                if bh >= cur_stop:
                    px = cur_stop + slip_pts
                    if not hit_t1:
                        leg1 = leg2 = entry - px
                    else:
                        leg2 = entry - px
                    exit_idx, reason, hit_s = f, ("be_stop" if hit_t1 else "stop"), True
                    break
                if not hit_t1 and bl <= tgt1:
                    leg1 = entry - tgt1
                    hit_t1 = True
                elif hit_t1 and bl <= tgt2:
                    leg2 = entry - tgt2
                    exit_idx, reason, hit_t2 = f, "target2", True
                    break
        else:
            exit_idx = min(i + max_holding_bars - 1, len(bars) - 1)
            px = c[exit_idx]
            rem = px - entry if long else entry - px
            if not hit_t1:
                leg1 = leg2 = rem
            else:
                leg2 = rem

        pnl_pts = 0.5 * leg1 + 0.5 * leg2
        net = pnl_pts * point_value - 2 * commission
        last_exit = exit_idx
        day_counts[day] = day_counts.get(day, 0) + 1
        trades.append({"pnl_pts": pnl_pts, "net": net, "reason": reason,
                       "hit_t": hit_t1, "hit_t2": hit_t2, "hit_s": hit_s,
                       "time": s["signal_time"], "model": s["model_name"],
                       "dir": "LONG" if long else "SHORT"})
    return pd.DataFrame(trades)


def summarize(name: str, t: pd.DataFrame) -> dict:
    if t is None or len(t) == 0:
        print(f"{name}: NO TRADES")
        return {}
    wins = t[t["net"] > 0]
    losses = t[t["net"] <= 0]
    pf = wins["net"].sum() / abs(losses["net"].sum()) if len(losses) and losses["net"].sum() != 0 else 999.0
    cum = t["net"].cumsum()
    dd = float((cum.cummax() - cum).max())
    days = t["time"].dt.date.nunique() if "time" in t else len(t)
    return {"name": name, "n": len(t), "tpd": len(t) / max(days, 1),
            "wr": len(wins) / len(t), "pf": pf, "net": t["net"].sum(),
            "pts": t["pnl_pts"].sum(), "dd": dd,
            "avg_win": t[t["net"] > 0]["pnl_pts"].mean() if len(wins) else 0.0,
            "avg_loss": t[t["net"] <= 0]["pnl_pts"].mean() if len(losses) else 0.0,
            "t1_rate": t["hit_t"].mean() if "hit_t" in t else float("nan"),
            "t2_rate": t["hit_t2"].mean() if "hit_t2" in t else float("nan")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="NQ1")
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--source", default="history", choices=["history", "live"],
                    help="history=data/{T}_1m.parquet, live=data/live/live_storage_-{T}.parquet")
    a = ap.parse_args();

    cfg = load_strat_config()
    spec = cfg.instrument(a.ticker)
    print(f"Unified Strat benchmark — {a.ticker} {a.start}..{a.end} (source={a.source}, config v{cfg.version})")

    df_1m = load_1m_et(a.ticker, a.start, a.end, source=a.source)
    if len(df_1m) == 0:
        raise SystemExit(f"No bars for {a.ticker} {a.start}..{a.end} (source={a.source})")
    bars_5m = df_1m[["open", "high", "low", "close"]].resample("5min", origin="start_day").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    print(f"5m bars: {len(bars_5m):,} ({bars_5m.index[0].date()}..{bars_5m.index[-1].date()})")

    engine = StratSignalEngine(config=cfg, tick_size=spec.tick_size)

    variants = [
        ("NEW full (FTFC+kz+confirm)", {}),
        ("NEW no-FTFC (kz+confirm)", {"use_ftfc_filter": False}),
        ("NEW no-gates (raw patterns)", {"use_ftfc_filter": False, "use_killzones": False,
                                         "confirm_next_bar": False, "min_rr_ratio": 0.0}),
    ]
    rows = []
    for name, overrides in variants:
        sig = engine.generate(bars_5m, params=overrides)
        print(f"  {name}: {len(sig)} signals")
        t = simulate_signals(sig, bars_5m, spec.point_value, spec.commission,
                             spec.slippage_ticks * spec.tick_size, cfg.max_holding_bars,
                             time(15, 55), cfg.max_trades_per_day)
        rows.append(summarize(name, t))

    # Legacy contrast: structural mag1 targets, same setups/time window.
    legacy = StratBacktester(point_value=spec.point_value,
                             commission_per_contract=spec.commission,
                             slippage_ticks=spec.slippage_ticks, tick_size=spec.tick_size)
    legacy_map = {"2-1-2_BULL_CONT": ComboType.BULLISH_212_CONT,
                  "2-1-2_BEAR_CONT": ComboType.BEARISH_212_CONT,
                  "2-2_BULL_REV": ComboType.BULLISH_22_REV,
                  "2-2_BEAR_REV": ComboType.BEARISH_22_REV,
                  "3-1-2_BULL": ComboType.BULLISH_312,
                  "3-1-2_BEAR": ComboType.BEARISH_312}
    ls = legacy.run_backtest(bars_5m, allowed_combos=set(legacy_map.values()),
                             min_rr_ratio=0.0, max_holding_bars=15,
                             start_time_et=time(9, 30), end_time_et=time(15, 30))
    leg_df = pd.DataFrame([{"pnl_pts": x.pnl_points, "net": x.pnl_dollars,
                              "time": pd.Timestamp(x.entry_time)} for x in ls.trades])
    rows.append(summarize("LEGACY structural-mag1 (min_rr=0)", leg_df))

    print("\n" + "-" * 118)
    print(f"{'Variant':<38} | {'Trades':>6} | {'Tr/d':>5} | {'Win%':>6} | {'PF':>6} | {'Net $':>13} | {'Net pts':>9} | {'MaxDD $':>11} | {'T1%':>6} | {'T2%':>6}")
    print("-" * 128)
    for r in rows:
        if not r:
            continue
        print(f"{r['name']:<38} | {r['n']:>6} | {r['tpd']:>5.2f} | {r['wr']*100:>5.1f}% | "
              f"{r['pf']:>6.2f} | ${r['net']:>+12,.0f} | {r['pts']:>+8.0f} | ${r['dd']:>10,.0f} | "
              f"{r['t1_rate']*100:>5.1f}% | {r.get('t2_rate', float('nan'))*100:>5.1f}%")
    print("-" * 128)
    print("Costs: 1pt=$%.0f, comm=$%.2f/rt, slip=%d tick | flat 15:55 ET, max %d trades/day, hold<=%d bars"
          % (spec.point_value, 2 * spec.commission, spec.slippage_ticks,
             cfg.max_trades_per_day, cfg.max_holding_bars))

    # Honesty breakdown for the full-gate variant: direction x year.
    full_sig = engine.generate(bars_5m, params={})
    full_t = simulate_signals(full_sig, bars_5m, spec.point_value, spec.commission,
                              spec.slippage_ticks * spec.tick_size, cfg.max_holding_bars,
                              time(15, 55), cfg.max_trades_per_day)
    full_t["year"] = full_t["time"].dt.year
    print("\nNEW-full breakdown (dir x year):")
    print(f"{'Slice':<14} | {'Trades':>6} | {'Win%':>6} | {'PF':>6} | {'Net $':>12} | {'Avg win':>8} | {'Avg loss':>8}")
    for key, g in sorted(full_t.groupby(["dir", "year"]).groups.items()):
        gg = full_t.loc[g]
        w = gg[gg["net"] > 0]
        l = gg[gg["net"] <= 0]
        pf = w["net"].sum() / abs(l["net"].sum()) if len(l) and l["net"].sum() != 0 else 999.0
        print(f"{key[0]} {key[1]:<9} | {len(gg):>6} | {len(w)/len(gg)*100:>5.1f}% | "
              f"{pf:>6.2f} | ${gg['net'].sum():>+11,.0f} | {gg[gg['net']>0]['pnl_pts'].mean():>+7.1f} | "
              f"{gg[gg['net']<=0]['pnl_pts'].mean():>+7.1f}")


if __name__ == "__main__":
    main()
