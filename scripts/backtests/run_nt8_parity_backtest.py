"""
NT8-Logic Parity Backtest — 2-Tier vs 3-Tier
============================================
Mirrors the EXACT logic of ICTFVGCISDBot.cs:
  - Sweeps: PDH/PDL + 1H fractal swings only (NO SMT)
  - No trap re-expansion
  - Sweep staleness: 15 bars
  - Session: 0950-1115 / 1330-1515
  - Max daily trades: 3, Max risk: 12 bps
  - CISD backward walk, 50% CE entry, SL-4 origin stop

Runs both PackBracketManager (2-tier) and ThreeTierPackManager (3-tier)
through the same setups and compares against NT8 CSV exports.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.libs_py.strategy_engine.pack_bracket_manager import PackBracketManager
from scripts.libs_py.strategy_engine.three_tier_pack_manager import ThreeTierPackManager


def run_nt8_parity_backtest(
    df: pd.DataFrame,
    tier_model: str = "2-tier",
    queen_bps: float = 10.0,
    runner_bps: float = 40.0,
    runner_pm_bps: float = 60.0,
    expansion_bps: float = 30.0,
    runner_3t_bps: float = 60.0,
    max_risk_bps: float = 12.0,
    max_daily_trades: int = 3,
    point_value: float = 2.0,
    comm_per_contract: float = 0.52,
    tick_size: float = 0.50,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Python backtest matching ICTFVGCISDBot.cs logic exactly.
    No SMT, no trap. Sweeps from PDH/PDL + 1H fractal swings only.
    """

    n = len(df)
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    opens = df["open"].values
    volumes = df["volume"].values if "volume" in df.columns else np.ones(n)
    times = df.index
    time_strs = df.index.strftime("%H%M")

    # 1H HTF trend via resample (matches NT8's AddDataSeries 60min)
    df_1h = df.resample("1h").agg({"close": "last"}).dropna()
    ema20 = df_1h["close"].ewm(span=20, adjust=False).mean()
    ema50 = df_1h["close"].ewm(span=50, adjust=False).mean()
    htf_trend = (ema20 > ema50).astype(int) - (ema20 < ema50).astype(int)
    htf_trend = htf_trend.shift(1).reindex(df.index, method="ffill").fillna(0).values

    vol_sma = pd.Series(volumes).rolling(20).mean().values

    # Daily PDH/PDL (shift 1 bar, like NT8 Highs[2][1])
    daily = df.groupby(df.index.date).agg({"high": "max", "low": "min"}).shift(1)
    pdh_map = daily["high"].to_dict()
    pdl_map = daily["low"].to_dict()

    # 1H fractal swings — NT8 uses 2-bar left/right lookback
    # (Highs[1][2] > Highs[1][4] && > Highs[1][3] && > Highs[1][1] && > Highs[1][0])
    # That's: bar at index 2 is the pivot, confirmed when bars 0,1 are lower (right side)
    # and bars 3,4 are lower (left side). So lookback=2 left, 2 right.
    df_1h_full = df.resample("1h").agg({"high": "max", "low": "min"}).dropna()
    h_1h = df_1h_full["high"].values
    l_1h = df_1h_full["low"].values
    n_1h = len(df_1h_full)

    sw_h_1h = np.full(n_1h, np.nan)
    sw_l_1h = np.full(n_1h, np.nan)
    for i in range(2, n_1h - 2):
        # NT8: Highs[1][2] > Highs[1][4] && > Highs[1][3] && > Highs[1][1] && > Highs[1][0]
        # In NT8, index 0 = current bar, 1 = previous, etc.
        # So bar[2] is 2 bars ago, bar[4] is 4 bars ago, bar[0] is current, bar[1] is 1 bar ago
        # The pivot is at bar[2] (2 bars ago), confirmed by bars[3],[4] (left) and bars[0],[1] (right)
        if (h_1h[i] > h_1h[i+1] and h_1h[i] > h_1h[i+2] and
            h_1h[i] > h_1h[i-1] and h_1h[i] > h_1h[i-2]):
            # In NT8, the swing is recorded at bar[2] which is i, but confirmed 2 bars later
            # The swing level is Highs[1][2] = h_1h[i], confirmed at 1H bar i+2
            sw_h_1h[i] = h_1h[i]
        if (l_1h[i] < l_1h[i+1] and l_1h[i] < l_1h[i+2] and
            l_1h[i] < l_1h[i-1] and l_1h[i] < l_1h[i-2]):
            sw_l_1h[i] = l_1h[i]

    # Map 1H swings to 5m bars (forward-fill, shifted by 2 for confirmation)
    df_1h_full["sw_h"] = sw_h_1h
    df_1h_full["sw_l"] = sw_l_1h
    # Shift by 2 bars (confirmation delay) then reindex
    bsl_series = df_1h_full["sw_h"].shift(2).reindex(df.index, method="ffill")
    ssl_series = df_1h_full["sw_l"].shift(2).reindex(df.index, method="ffill")

    # Rolling lists (NT8 keeps last 10)
    bsl_1h_list: List[float] = []
    ssl_1h_list: List[float] = []

    # Bracket manager
    if tier_model == "3-tier":
        bracket_mgr = ThreeTierPackManager(
            queen_bps=queen_bps, expansion_bps=expansion_bps,
            runner_bps=runner_3t_bps, point_value=point_value,
            comm_per_contract=comm_per_contract, tick_size=tick_size,
        )
        active_state = None
    else:
        bracket_mgr = PackBracketManager(
            queen_bps=queen_bps, runner_bps=runner_bps,
            runner_pm_bps=runner_pm_bps, point_value=point_value,
            comm_per_contract=comm_per_contract, tick_size=tick_size,
        )
        active_state = None

    # State
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
    _3tier_closures: List[Dict] = []  # captured closes for 3-tier trade collection

    def _open_trade(direction, entry_price, stop_loss, bar_idx, bar_time, is_pm):
        nonlocal active_state, daily_trade_count
        if tier_model == "3-tier":
            if active_state is None:
                active_state = bracket_mgr.calculate_pack_levels(
                    direction=direction, entry_price=entry_price,
                    stop_price=stop_loss, entry_time=bar_time,
                    entry_bar=bar_idx, sweep_level="nt8-parity",
                )
                daily_trade_count += 1
        else:
            if bracket_mgr.active_position is None:
                bracket_mgr.open_pack(direction, entry_price, stop_loss,
                                      bar_idx, bar_time, is_pm_macro=is_pm)
                daily_trade_count += 1

    def _update_position(bar_idx, bar_time, high, low, close, is_eod):
        nonlocal active_state
        if tier_model == "3-tier":
            if active_state is None:
                return None
            closed, summary = bracket_mgr.update_bar(active_state, high=high, low=low,
                                                      close=close, is_eod=is_eod)
            if closed:
                res = {
                    "entry_price": active_state.entry_price,
                    "direction": active_state.direction,
                    "entry_time": active_state.entry_time,
                    "exit_reason": summary["exit_reason"],
                    "net_pnl_pts": summary["pnl_points"],
                    "net_pnl_usd": summary["net_pnl"],
                    "bars_held": bar_idx - active_state.entry_bar,
                    "tp1_hit": summary.get("tp1_hit", False),
                }
                _3tier_closures.append({
                    "trade_id": len(_3tier_closures) + 1,
                    "direction": res["direction"],
                    "entry_time": res["entry_time"],
                    "exit_time": bar_time,
                    "entry_price": res["entry_price"],
                    "queen_filled": res["tp1_hit"],
                    "exit_reason": res["exit_reason"],
                    "net_pnl_usd": res["net_pnl_usd"],
                    "bars_held": res["bars_held"],
                })
                active_state = None
                return res
            return None
        else:
            res = bracket_mgr.update_bar(bar_idx=bar_idx, bar_time=bar_time,
                                         high=high, low=low, close=close,
                                         is_eod_bar=is_eod)
            if res is not None:
                return {
                    "entry_price": res.entry_price,
                    "direction": res.direction,
                    "entry_time": res.entry_time,
                    "exit_reason": res.exit_reason,
                    "net_pnl_pts": res.net_pnl_pts,
                    "net_pnl_usd": res.net_pnl_usd,
                    "bars_held": res.bars_held,
                }
            return None

    for i in range(25, n):
        t = times[i]
        bar_date = t.date()
        hhmm = time_strs[i]
        is_eod = (hhmm >= "1555")
        is_pm = ("1330" <= hhmm <= "1515")
        in_session = ("0950" <= hhmm <= "1115") or is_pm

        if bar_date != current_date:
            current_date = bar_date
            daily_trade_count = 0

        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h1, l1 = highs[i-1], lows[i-1]
        h2, l2 = highs[i-2], lows[i-2]

        # Update 1H swing lists (forward-filled values)
        bsl_val = bsl_series.iloc[i] if i < len(bsl_series) else np.nan
        ssl_val = ssl_series.iloc[i] if i < len(ssl_series) else np.nan
        if not np.isnan(bsl_val):
            if not bsl_1h_list or bsl_1h_list[-1] != bsl_val:
                bsl_1h_list.append(bsl_val)
                if len(bsl_1h_list) > 10: bsl_1h_list.pop(0)
        if not np.isnan(ssl_val):
            if not ssl_1h_list or ssl_1h_list[-1] != ssl_val:
                ssl_1h_list.append(ssl_val)
                if len(ssl_1h_list) > 10: ssl_1h_list.pop(0)

        # STEP 1: EOD FLATTEN
        if is_eod:
            res = _update_position(i, t, h0, l0, c0, True)
            pending_zone = None
            # Don't return — continue to sweep detection for next bar

        # STEP 2: POSITION MANAGEMENT
        if not is_eod:
            res = _update_position(i, t, h0, l0, c0, False)

        # STEP 3: PENDING ZONE FILL
        if pending_zone is not None and in_session and daily_trade_count < max_daily_trades:
            p_dir = pending_zone["dir"]
            p_level = pending_zone["entry_level"]
            p_sl = pending_zone["sl"]
            p_bar = pending_zone["armed_bar"]

            if (i - p_bar) <= 12:  # NT8 MaxRetestWaitBars = 12
                if p_dir == 1 and l0 <= p_level:
                    _open_trade(1, p_level, p_sl, i, t, is_pm)
                    pending_zone = None
                elif p_dir == -1 and h0 >= p_level:
                    _open_trade(-1, p_level, p_sl, i, t, is_pm)
                    pending_zone = None
            else:
                pending_zone = None

        # STEP 4: SWEEP DETECTION (PDH/PDL + 1H swings only — NO SMT)
        pdh = pdh_map.get(bar_date, np.nan)
        pdl = pdl_map.get(bar_date, np.nan)
        bsl_swept = False
        ssl_swept = False

        if not np.isnan(pdh) and h0 > pdh and (c0 < pdh or o0 < pdh):
            bsl_swept = True
        if not np.isnan(pdl) and l0 < pdl and (c0 > pdl or o0 > pdl):
            ssl_swept = True

        if not bsl_swept:
            for bsl_1h in bsl_1h_list:
                if h0 > bsl_1h and (c0 < bsl_1h or o0 < bsl_1h):
                    bsl_swept = True
                    break

        if not ssl_swept:
            for ssl_1h in ssl_1h_list:
                if l0 < ssl_1h and (c0 > ssl_1h or o0 > ssl_1h):
                    ssl_swept = True
                    break

        if ssl_swept:
            has_bull_sweep = True
            bull_sweep_bar = i
        if bsl_swept:
            has_bear_sweep = True
            bear_sweep_bar = i

        # NT8: staleness = 15 bars
        if (i - bull_sweep_bar) > 15: has_bull_sweep = False
        if (i - bear_sweep_bar) > 15: has_bear_sweep = False

        # STEP 5: CANONICAL CISD (backward walk)
        if has_bull_sweep and ssl_swept:
            s_high, s_low = max(o0, c0), min(o0, c0)
            for k in range(1, min(20, i)):
                if closes[i-k] <= opens[i-k]:
                    s_high = max(s_high, max(opens[i-k], closes[i-k]))
                    s_low = min(s_low, min(opens[i-k], closes[i-k]))
                else:
                    break
            armed_bull_cisd, armed_bull_high, cisd_origin_sl = True, s_high, s_low

        if has_bear_sweep and bsl_swept:
            s_high, s_low = max(o0, c0), min(o0, c0)
            for k in range(1, min(20, i)):
                if closes[i-k] >= opens[i-k]:
                    s_high = max(s_high, max(opens[i-k], closes[i-k]))
                    s_low = min(s_low, min(opens[i-k], closes[i-k]))
                else:
                    break
            armed_bear_cisd, armed_bear_low, cisd_origin_sl = True, s_low, s_high

        # Displacement & HTF trend filters
        body_bps = (abs(c0 - o0) / c0) * 10000.0
        cur_vol = vol_sma[i] if not np.isnan(vol_sma[i]) else 1.0
        passes_disp = (body_bps >= 3.0 and volumes[i] >= 1.1 * cur_vol)
        cur_htf = htf_trend[i] if i < len(htf_trend) else 0
        bull_htf = (cur_htf >= 0)
        bear_htf = (cur_htf <= 0)

        # STEP 6: ARM FIRST FVG / BREAKER RETEST
        if armed_bull_cisd and not np.isnan(armed_bull_high) and c0 > armed_bull_high:
            armed_bull_cisd = False
            has_bull_sweep = False
            if passes_disp and bull_htf and in_session and pending_zone is None and daily_trade_count < max_daily_trades:
                pos_is_flat = (active_state is None) if tier_model == "3-tier" else (bracket_mgr.active_position is None)
                if pos_is_flat:
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

        if armed_bear_cisd and not np.isnan(armed_bear_low) and c0 < armed_bear_low:
            armed_bear_cisd = False
            has_bear_sweep = False
            if passes_disp and bear_htf and in_session and pending_zone is None and daily_trade_count < max_daily_trades:
                pos_is_flat = (active_state is None) if tier_model == "3-tier" else (bracket_mgr.active_position is None)
                if pos_is_flat:
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

    # Collect trades
    if tier_model == "3-tier":
        # ThreeTierPackManager doesn't track completed_trades — we build them
        # from the close summaries captured during the loop.
        trades_data = []
        for idx, r in enumerate(_3tier_closures):
            trades_data.append({
                "trade_id": idx + 1, "direction": r["direction"],
                "entry_time": r["entry_time"], "exit_time": r["exit_time"],
                "entry_price": r["entry_price"], "queen_filled": r.get("tp1_hit", False),
                "exit_reason": r["exit_reason"], "net_pnl_usd": r["net_pnl_usd"],
                "bars_held": r["bars_held"],
            })
    else:
        trades_data = [
            {
                "trade_id": r.trade_id, "direction": r.direction,
                "entry_time": r.entry_time, "exit_time": r.exit_time,
                "entry_price": r.entry_price, "queen_filled": r.queen_filled,
                "exit_reason": r.exit_reason, "net_pnl_usd": r.net_pnl_usd,
                "bars_held": r.bars_held,
            }
            for r in bracket_mgr.completed_trades
        ]

    trades_df = pd.DataFrame(trades_data)
    if len(trades_df) == 0:
        return trades_df, {"trades": 0}

    w = trades_df[trades_df["net_pnl_usd"] > 0]
    l = trades_df[trades_df["net_pnl_usd"] < 0]
    gp = w["net_pnl_usd"].sum()
    gl = abs(l["net_pnl_usd"].sum())
    cum = trades_df["net_pnl_usd"].cumsum()
    max_dd = (cum - cum.cummax()).min()

    stats = {
        "trades": len(trades_df),
        "win_rate": (len(w) / len(trades_df)) * 100,
        "profit_factor": (gp / gl) if gl > 0 else float("inf"),
        "net_pnl": trades_df["net_pnl_usd"].sum(),
        "gross_profit": gp, "gross_loss": gl,
        "avg_win": w["net_pnl_usd"].mean() if len(w) else 0,
        "avg_loss": l["net_pnl_usd"].mean() if len(l) else 0,
        "payoff_ratio": abs(w["net_pnl_usd"].mean() / l["net_pnl_usd"].mean()) if len(l) and len(w) else 0,
        "max_dd": max_dd,
    }
    return trades_df, stats


def main():
    import argparse
    p = argparse.ArgumentParser(description="NT8-Logic Parity Backtest — 2-Tier vs 3-Tier")
    p.add_argument("--symbol", default="NQ", choices=["NQ", "ES"])
    p.add_argument("--start", default="2020-01-10")
    p.add_argument("--end", default="2026-08-11")
    p.add_argument("--comm", type=float, default=0.52, help="Commission per side per contract")
    args = p.parse_args()

    sym_file = "NQ1_5m" if args.symbol == "NQ" else "ES1_5m"
    df = pd.read_parquet(_root / "data" / f"{sym_file}.parquet")
    if not isinstance(df.index, pd.DatetimeIndex):
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
    df = df.sort_index()
    df = df[(df.index >= args.start) & (df.index <= args.end)]

    point_value = 2.0 if args.symbol == "NQ" else 5.0
    tick_size = 0.50 if args.symbol == "NQ" else 0.25

    print(f"Loaded {len(df):,} bars ({df.index.min().date()} -> {df.index.max().date()})")
    print(f"Running NT8-Logic Parity Backtest (no SMT, no trap, sweep=15)...")

    results = {}
    for tier in ["2-tier", "3-tier"]:
        tdf, stats = run_nt8_parity_backtest(
            df, tier_model=tier, point_value=point_value,
            comm_per_contract=args.comm, tick_size=tick_size,
        )
        results[tier] = (tdf, stats)
        print(f"  {tier}: {stats.get('trades', 0)} trades")

    print("\n" + "=" * 90)
    print(f"  NT8-LOGIC PARITY COMPARISON — {args.symbol} ({args.start} -> {args.end})")
    print(f"  Logic: PDH/PDL + 1H swings only | No SMT | No trap | comm=${args.comm}/side")
    print("=" * 90)
    print(f"{'Metric':<24} {'2-Tier':>20}   {'3-Tier':>20}")
    print("-" * 90)
    for k in ["trades", "win_rate", "profit_factor", "net_pnl", "gross_profit",
              "gross_loss", "avg_win", "avg_loss", "payoff_ratio", "max_dd"]:
        vals = []
        for tier in ["2-tier", "3-tier"]:
            v = results[tier][1].get(k, "-")
            if k in ("net_pnl", "gross_profit", "gross_loss", "avg_win", "avg_loss", "max_dd") and isinstance(v, (int, float)):
                v = f"${v:,.2f}"
            elif k == "win_rate" and isinstance(v, (int, float)):
                v = f"{v:.1f}%"
            elif k == "profit_factor" and isinstance(v, (int, float)):
                v = f"{v:.2f}"
            elif k == "payoff_ratio" and isinstance(v, (int, float)):
                v = f"{v:.2f}:1"
            vals.append(str(v))
        print(f"  {k:<22} {vals[0]:>20}   {vals[1]:>20}")
    print("=" * 90)

    for tier in ["2-tier", "3-tier"]:
        tdf = results[tier][0]
        if len(tdf) > 0:
            print(f"\n  {tier} exit reasons:")
            for reason, cnt in tdf["exit_reason"].value_counts().items():
                print(f"    {reason:<20} {cnt:>5}  ({cnt/len(tdf)*100:.1f}%)")

    # Save trades
    out_dir = _root / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    for tier in ["2-tier", "3-tier"]:
        tdf = results[tier][0]
        if len(tdf) > 0:
            tdf.to_csv(out_dir / f"nt8_parity_{tier}_{stamp}.csv", index=False)
    print(f"\nTrades saved to reports/nt8_parity_*_{stamp}.csv")


if __name__ == "__main__":
    main()