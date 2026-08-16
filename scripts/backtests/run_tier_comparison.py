"""
2-Tier vs 3-Tier Pack Comparison Backtest
=========================================
Runs the SAME ICT setup logic (1H+ Liquidity Sweep -> CISD -> 50% CE Retest)
through two different bracket managers and reports side-by-side metrics so we
can pick the better model empirically:

  - 2-Tier (PackBracketManager):  Queen @10bps -> BE -> Runner @40/60bps (AM/PM)
  - 3-Tier (ThreeTierPackManager): Queen @10bps -> BE -> Expansion @30bps -> Lock -> Runner @60bps

Both share:
  - Same setups (sweep bar, CISD origin, entry zone, SL)
  - Same session windows, filters, max risk, max daily trades
  - Same commission / point value
"""

from __future__ import annotations
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.libs_py.strategy_engine.pack_bracket_manager import PackBracketManager
from scripts.libs_py.strategy_engine.three_tier_pack_manager import ThreeTierPackManager


def detect_setups(df: pd.DataFrame, max_risk_bps: float = 12.0, max_daily_trades: int = 3) -> List[Dict]:
    """
    Shared setup detector. Returns a list of setup dicts with identical
    fields so each bracket manager sees the exact same entries.
    Each setup: {bar_idx, time, direction, entry_price, stop_loss, is_pm_macro}
    """
    n = len(df)
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    opens = df["open"].values
    volumes = df["volume"].values if "volume" in df.columns else np.ones(n)
    times = df.index
    time_strs = df.index.strftime("%H%M")

    # 1H HTF trend via resample
    df_1h = df.resample("1h").agg({"close": "last"}).dropna()
    ema20 = df_1h["close"].ewm(span=20, adjust=False).mean()
    ema50 = df_1h["close"].ewm(span=50, adjust=False).mean()
    htf_trend = (ema20 > ema50).astype(int) - (ema20 < ema50).astype(int)
    htf_trend = htf_trend.shift(1).reindex(df.index, method="ffill").fillna(0).values

    vol_sma = pd.Series(volumes).rolling(20).mean().values

    # Daily PDH/PDL
    daily = df.groupby(df.index.date).agg({"high": "max", "low": "min"}).shift(1)
    pdh_map = daily["high"].to_dict()
    pdl_map = daily["low"].to_dict()

    # 1H fractal swings (3-bar left + 3-bar right, confirmed 3 bars later)
    sw_h = np.full(n, np.nan)
    sw_l = np.full(n, np.nan)
    for i in range(3, n - 3):
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i-3] and
            highs[i] > highs[i+1] and highs[i] > highs[i+2] and highs[i] > highs[i+3]):
            sw_h[i + 3] = highs[i]
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i-3] and
            lows[i] < lows[i+1] and lows[i] < lows[i+2] and lows[i] < lows[i+3]):
            sw_l[i + 3] = lows[i]

    bsl_1h_list: List[float] = []
    ssl_1h_list: List[float] = []

    setups: List[Dict] = []
    has_bull_sweep = False
    has_bear_sweep = False
    bull_sweep_bar = -9999
    bear_sweep_bar = -9999
    armed_bull_cisd = False
    armed_bear_cisd = False
    armed_bull_high = np.nan
    armed_bear_low = np.nan
    cisd_origin_sl = np.nan
    pending_zone: Optional[Dict] = None
    current_date = None
    daily_trade_count = 0

    for i in range(25, n):
        t = times[i]
        bar_date = t.date()
        hhmm = time_strs[i]
        is_pm = ("1330" <= hhmm <= "1515")
        in_session = ("0950" <= hhmm <= "1115") or is_pm

        if bar_date != current_date:
            current_date = bar_date
            daily_trade_count = 0

        # update swing lists
        if not np.isnan(sw_h[i]):
            if not bsl_1h_list or bsl_1h_list[-1] != sw_h[i]:
                bsl_1h_list.append(sw_h[i])
                if len(bsl_1h_list) > 10: bsl_1h_list.pop(0)
        if not np.isnan(sw_l[i]):
            if not ssl_1h_list or ssl_1h_list[-1] != sw_l[i]:
                ssl_1h_list.append(sw_l[i])
                if len(ssl_1h_list) > 10: ssl_1h_list.pop(0)

        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h1, l1 = highs[i-1], lows[i-1]
        h2, l2 = highs[i-2], lows[i-2]

        # expire pending zone
        if pending_zone is not None and (i - pending_zone["armed_bar"] > 15):
            pending_zone = None

        # fill pending zone
        if pending_zone is not None and in_session and daily_trade_count < max_daily_trades:
            p_dir = pending_zone["dir"]
            p_level = pending_zone["entry_level"]
            p_sl = pending_zone["sl"]
            if p_dir == 1 and l0 <= p_level:
                setups.append({"bar_idx": i, "time": t, "direction": 1,
                               "entry_price": p_level, "stop_loss": p_sl, "is_pm_macro": is_pm})
                daily_trade_count += 1
                pending_zone = None
            elif p_dir == -1 and h0 >= p_level:
                setups.append({"bar_idx": i, "time": t, "direction": -1,
                               "entry_price": p_level, "stop_loss": p_sl, "is_pm_macro": is_pm})
                daily_trade_count += 1
                pending_zone = None

        # sweeps
        pdh = pdh_map.get(bar_date, np.nan)
        pdl = pdl_map.get(bar_date, np.nan)
        bsl_swept = False
        ssl_swept = False
        if not np.isnan(pdh) and h0 > pdh and (c0 < pdh or o0 < pdh): bsl_swept = True
        if not np.isnan(pdl) and l0 < pdl and (c0 > pdl or o0 > pdl): ssl_swept = True
        for bsl_1h in bsl_1h_list:
            if h0 > bsl_1h and (c0 < bsl_1h or o0 < bsl_1h): bsl_swept = True; break
        for ssl_1h in ssl_1h_list:
            if l0 < ssl_1h and (c0 > ssl_1h or o0 > ssl_1h): ssl_swept = True; break

        if ssl_swept:
            has_bull_sweep = True; bull_sweep_bar = i
        if bsl_swept:
            has_bear_sweep = True; bear_sweep_bar = i
        if (i - bull_sweep_bar) > 15: has_bull_sweep = False
        if (i - bear_sweep_bar) > 15: has_bear_sweep = False

        # CISD backward walk
        if has_bull_sweep and ssl_swept:
            s_high, s_low = max(o0, c0), min(o0, c0)
            for k in range(1, min(20, i)):
                if closes[i-k] <= opens[i-k]:
                    s_high = max(s_high, max(opens[i-k], closes[i-k]))
                    s_low = min(s_low, min(opens[i-k], closes[i-k]))
                else: break
            armed_bull_cisd, armed_bull_high, cisd_origin_sl = True, s_high, s_low

        if has_bear_sweep and bsl_swept:
            s_high, s_low = max(o0, c0), min(o0, c0)
            for k in range(1, min(20, i)):
                if closes[i-k] >= opens[i-k]:
                    s_high = max(s_high, max(opens[i-k], closes[i-k]))
                    s_low = min(s_low, min(opens[i-k], closes[i-k]))
                else: break
            armed_bear_cisd, armed_bear_low, cisd_origin_sl = True, s_low, s_high

        body_bps = (abs(c0 - o0) / c0) * 10000.0
        cur_vol = vol_sma[i] if not np.isnan(vol_sma[i]) else 1.0
        passes_disp = (body_bps >= 3.0 and volumes[i] >= 1.1 * cur_vol)
        cur_htf = htf_trend[i] if i < len(htf_trend) else 0
        bull_htf = (cur_htf >= 0)
        bear_htf = (cur_htf <= 0)

        # arm pending zone
        if armed_bull_cisd and not np.isnan(armed_bull_high) and c0 > armed_bull_high:
            armed_bull_cisd = False
            if passes_disp and bull_htf and in_session and pending_zone is None and daily_trade_count < max_daily_trades:
                new_fvg = l0 > h2
                z_top = l0 if new_fvg else armed_bull_high
                z_bot = h2 if new_fvg else (armed_bull_high - 2.0)
                z_ce = (z_top + z_bot) / 2.0
                raw_sl = cisd_origin_sl if not np.isnan(cisd_origin_sl) else l1
                if raw_sl >= z_ce: raw_sl = min(l0, l1, l2)
                sl_price = raw_sl - 0.50
                risk_dist = z_ce - sl_price
                if risk_dist > 0 and ((risk_dist / z_ce) * 10000.0) <= max_risk_bps:
                    pending_zone = {"dir": 1, "entry_level": z_ce, "sl": sl_price, "armed_bar": i}
            has_bull_sweep = False

        if armed_bear_cisd and not np.isnan(armed_bear_low) and c0 < armed_bear_low:
            armed_bear_cisd = False
            if passes_disp and bear_htf and in_session and pending_zone is None and daily_trade_count < max_daily_trades:
                new_fvg = h0 < l2
                z_top = l2 if new_fvg else (armed_bear_low + 2.0)
                z_bot = h0 if new_fvg else armed_bear_low
                z_ce = (z_top + z_bot) / 2.0
                raw_sl = cisd_origin_sl if not np.isnan(cisd_origin_sl) else h1
                if raw_sl <= z_ce: raw_sl = max(h0, h1, h2)
                sl_price = raw_sl + 0.50
                risk_dist = sl_price - z_ce
                if risk_dist > 0 and ((risk_dist / z_ce) * 10000.0) <= max_risk_bps:
                    pending_zone = {"dir": -1, "entry_level": z_ce, "sl": sl_price, "armed_bar": i}
            has_bear_sweep = False

    return setups


def run_2tier(df: pd.DataFrame, setups: List[Dict], queen_bps=10.0, runner_bps=40.0,
              runner_pm_bps=60.0, point_value=2.0, comm=0.52, tick_size=0.25) -> pd.DataFrame:
    mgr = PackBracketManager(queen_bps=queen_bps, runner_bps=runner_bps,
                             runner_pm_bps=runner_pm_bps, point_value=point_value,
                             comm_per_contract=comm, tick_size=tick_size)
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    times = df.index

    # build a bar->idx map for quick lookup
    time_to_idx = {t: i for i, t in enumerate(times)}

    s_idx = 0
    for i in range(25, len(df)):
        # open new position at this bar if a setup fires here
        while s_idx < len(setups) and setups[s_idx]["bar_idx"] == i:
            s = setups[s_idx]
            if mgr.active_position is None:
                mgr.open_pack(direction=s["direction"], entry_price=s["entry_price"],
                              stop_loss=s["stop_loss"], bar_idx=i, bar_time=s["time"],
                              is_pm_macro=s["is_pm_macro"])
            s_idx += 1

        is_eod = (times[i].strftime("%H%M") >= "1555")
        mgr.update_bar(bar_idx=i, bar_time=times[i], high=highs[i], low=lows[i],
                       close=closes[i], is_eod_bar=is_eod)

    rows = []
    for r in mgr.completed_trades:
        rows.append({"tier_model": "2-Tier", "trade_id": r.trade_id, "direction": r.direction,
                     "entry_time": r.entry_time, "exit_time": r.exit_time,
                     "entry_price": r.entry_price, "exit_reason": r.exit_reason,
                     "queen_filled": r.queen_filled, "net_pnl": r.net_pnl_usd,
                     "mfe_pts": r.mfe_pts, "mae_pts": r.mae_pts, "bars_held": r.bars_held})
    return pd.DataFrame(rows)


def run_3tier(df: pd.DataFrame, setups: List[Dict], queen_bps=10.0, expansion_bps=30.0,
              runner_bps=60.0, point_value=2.0, comm=0.52, tick_size=0.25) -> pd.DataFrame:
    mgr = ThreeTierPackManager(queen_bps=queen_bps, expansion_bps=expansion_bps,
                               runner_bps=runner_bps, point_value=point_value,
                               comm_per_contract=comm, tick_size=tick_size)
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    times = df.index

    active: Optional[object] = None
    trade_counter = 0
    rows = []

    s_idx = 0
    for i in range(25, len(df)):
        # open if a setup fires here and no active position
        while s_idx < len(setups) and setups[s_idx]["bar_idx"] == i:
            s = setups[s_idx]
            if active is None:
                active = mgr.calculate_pack_levels(
                    direction=s["direction"], entry_price=s["entry_price"],
                    stop_price=s["stop_loss"], entry_time=s["time"], entry_bar=i,
                    sweep_level="3-tier")
                trade_counter += 1
            s_idx += 1

        if active is not None:
            is_eod = (times[i].strftime("%H%M") >= "1555")
            closed, summary = mgr.update_bar(active, high=highs[i], low=lows[i],
                                             close=closes[i], is_eod=is_eod)
            if closed:
                rows.append({"tier_model": "3-Tier", "trade_id": trade_counter,
                             "direction": active.direction, "entry_time": active.entry_time,
                             "exit_time": times[i], "entry_price": active.entry_price,
                             "exit_reason": summary["exit_reason"],
                             "queen_filled": summary.get("tp1_hit", False),
                             "net_pnl": summary["net_pnl"],
                             "mfe_pts": 0.0, "mae_pts": 0.0, "bars_held": i - active.entry_bar})
                active = None

    return pd.DataFrame(rows)


def stats_block(df: pd.DataFrame, label: str) -> Dict:
    if len(df) == 0:
        return {"label": label, "trades": 0}
    w = df[df["net_pnl"] > 0]
    l = df[df["net_pnl"] < 0]
    gp = w["net_pnl"].sum()
    gl = abs(l["net_pnl"].sum())
    cum = df["net_pnl"].cumsum()
    max_dd = (cum - cum.cummax()).min()
    return {
        "label": label,
        "trades": len(df),
        "win_rate": f"{(len(w)/len(df))*100:.1f}%",
        "profit_factor": f"{(gp/gl) if gl > 0 else 'inf':.2f}" if gl > 0 else "inf",
        "net_pnl": df["net_pnl"].sum(),
        "avg_win": w["net_pnl"].mean() if len(w) else 0.0,
        "avg_loss": l["net_pnl"].mean() if len(l) else 0.0,
        "max_dd": max_dd,
        "queen_fill_rate": f"{(df['queen_filled'].sum()/len(df))*100:.1f}%",
    }


def main():
    import argparse
    p = argparse.ArgumentParser(description="2-Tier vs 3-Tier Pack Comparison Backtest")
    p.add_argument("--symbol", default="NQ", choices=["NQ", "ES"])
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2026-08-15")
    p.add_argument("--max-risk-bps", type=float, default=12.0)
    p.add_argument("--max-daily-trades", type=int, default=3)
    p.add_argument("--queen-bps", type=float, default=10.0)
    p.add_argument("--expansion-bps", type=float, default=30.0)
    p.add_argument("--runner-2t-am", type=float, default=40.0)
    p.add_argument("--runner-2t-pm", type=float, default=60.0)
    p.add_argument("--runner-3t", type=float, default=60.0)
    args = p.parse_args()

    sym_file = "NQ1_5m" if args.symbol == "NQ" else "ES1_5m"
    df = pd.read_parquet(_root / "data" / f"{sym_file}.parquet")
    if not isinstance(df.index, pd.DatetimeIndex):
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
    df = df.sort_index()
    df = df[(df.index >= args.start) & (df.index <= args.end)]

    point_value = 2.0 if args.symbol == "NQ" else 5.0
    tick_size = 0.25 if args.symbol == "ES" else 0.50
    comm = 0.52 if args.symbol == "NQ" else 0.40

    print(f"Loaded {len(df):,} bars ({df.index.min().date()} -> {df.index.max().date()})")
    print("Detecting shared setups...")
    setups = detect_setups(df, max_risk_bps=args.max_risk_bps,
                           max_daily_trades=args.max_daily_trades)
    print(f"  -> {len(setups)} setups found\n")

    if len(setups) == 0:
        print("No setups. Loosen filters or expand date range.")
        return

    print("Running 2-Tier PackBracketManager...")
    df_2t = run_2tier(df, setups, queen_bps=args.queen_bps,
                      runner_bps=args.runner_2t_am, runner_pm_bps=args.runner_2t_pm,
                      point_value=point_value, comm=comm, tick_size=tick_size)

    print("Running 3-Tier ThreeTierPackManager...")
    df_3t = run_3tier(df, setups, queen_bps=args.queen_bps,
                      expansion_bps=args.expansion_bps, runner_bps=args.runner_3t,
                      point_value=point_value, comm=comm, tick_size=tick_size)

    s2 = stats_block(df_2t, "2-Tier (Queen + Runner)")
    s3 = stats_block(df_3t, "3-Tier (Queen + Expansion + Runner)")

    print("\n" + "=" * 90)
    print(f"  PACK MODEL COMPARISON — {args.symbol} ({args.start} to {args.end})")
    print("=" * 90)
    print(f"{'Metric':<28} {'2-Tier':>20}   {'3-Tier':>20}")
    print("-" * 90)
    for k in ["trades", "win_rate", "profit_factor", "net_pnl", "avg_win", "avg_loss", "max_dd", "queen_fill_rate"]:
        v2 = s2.get(k, "-")
        v3 = s3.get(k, "-")
        if k in ("net_pnl", "avg_win", "avg_loss", "max_dd"):
            v2 = f"${v2:,.2f}" if isinstance(v2, (int, float)) else v2
            v3 = f"${v3:,.2f}" if isinstance(v3, (int, float)) else v3
        print(f"  {k:<26} {str(v2):>20}   {str(v3):>20}")
    print("=" * 90)

    # exit-reason breakdown
    print("\nExit Reason Breakdown:")
    print("-" * 50)
    for model_name, df_m in [("2-Tier", df_2t), ("3-Tier", df_3t)]:
        if len(df_m) > 0:
            vc = df_m["exit_reason"].value_counts()
            print(f"  {model_name}:")
            for reason, count in vc.items():
                print(f"    {reason:<20} {count:>5}  ({count/len(df_m)*100:.1f}%)")

    # save trades
    out_dir = _root / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    df_2t.to_csv(out_dir / f"tier_comparison_2tier_{stamp}.csv", index=False)
    df_3t.to_csv(out_dir / f"tier_comparison_3tier_{stamp}.csv", index=False)
    print(f"\nTrades saved to reports/tier_comparison_*_{stamp}.csv")


if __name__ == "__main__":
    main()