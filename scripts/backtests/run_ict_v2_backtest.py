"""
ICT-Correct Backtest v2 — Fixed CISD + Premium/Discount + 1m Execution
=====================================================================
Fixes applied vs the master backtest:
  1. CISD level = OPEN of the delivery origin candle (not HIGH of the entire run)
  2. CISD confirmation = close above delivery origin OPEN (not above run HIGH)
  3. SL-4 = low of the delivery origin candle (not entire run low)
  4. Premium/Discount filter: reject longs in premium, shorts in discount
  5. 1m intrabar execution: use 1-minute bars to resolve stop/TP ambiguity

Uses the 2-tier PackBracketManager (proven winner from tier comparison).
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
from scripts.libs_py.ict_engine.core.smt import SMTDivergenceEngine
from scripts.libs_py.ict_engine.core.trap_engine import TrappedLiquidityEngine
from scripts.libs_py.features.htf_order_flow import HTFOrderFlowFilter


def run_ict_v2_backtest(
    df_nq: pd.DataFrame,
    df_es: pd.DataFrame,
    df_1m: Optional[pd.DataFrame] = None,
    symbol: str = "NQ",
    point_value: float = 2.0,
    comm_per_contract: float = 0.52,
    enable_trap_reexpansion: bool = True,
    queen_bps: float = 10.0,
    runner_bps: float = 40.0,
    runner_pm_bps: float = 60.0,
    max_risk_bps: float = 12.0,
    enable_premium_discount: bool = True,
) -> Tuple[pd.DataFrame, Dict]:
    """
    ICT-Correct Backtest with fixed CISD logic, premium/discount filter,
    and optional 1m intrabar execution.
    """

    common = df_nq.index.intersection(df_es.index)
    df_nq = df_nq.loc[common].sort_index()
    df_es = df_es.loc[common].sort_index()

    n = len(df_nq)
    highs = df_nq["high"].values
    lows = df_nq["low"].values
    closes = df_nq["close"].values
    opens = df_nq["open"].values
    volumes = df_nq["volume"].values if "volume" in df_nq.columns else np.ones(n)
    times = df_nq.index
    time_strs = df_nq.index.strftime("%H%M")

    es_highs = df_es["high"].values
    es_lows = df_es["low"].values
    es_closes = df_es["close"].values

    tick_size = 0.25 if symbol == "ES" else 0.50

    # Engines
    smt_engine = SMTDivergenceEngine(pivot_left=3, pivot_right=3, max_swings_tracked=10)
    trap_engine = TrappedLiquidityEngine(max_wait_bars=3, target_bps=40.0, max_risk_bps=15.0)
    bracket_mgr = PackBracketManager(
        queen_bps=queen_bps, runner_bps=runner_bps, runner_pm_bps=runner_pm_bps,
        point_value=point_value, comm_per_contract=comm_per_contract, tick_size=tick_size,
    )

    # HTF trend
    htf_trend_series = HTFOrderFlowFilter.compute_1h_trend_series(df_nq, fast_span=20, slow_span=50)
    vol_sma = pd.Series(volumes).rolling(20).mean().values

    # Daily levels: PDH, PDL, PDC (prior day close), equilibrium
    daily_df = df_nq.groupby(df_nq.index.date).agg(
        {"high": "max", "low": "min", "close": "last"}
    ).shift(1)
    pdh_map = daily_df["high"].to_dict()
    pdl_map = daily_df["low"].to_dict()
    pdc_map = daily_df["close"].to_dict()

    # IPDA 20-day range for premium/discount — computed from DAILY bars
    daily_full = df_nq.groupby(df_nq.index.date).agg({"high": "max", "low": "min", "close": "last"})
    daily_high_20 = daily_full["high"].rolling(20).max().shift(1)
    daily_low_20 = daily_full["low"].rolling(20).min().shift(1)
    daily_eq_series = (daily_high_20 + daily_low_20) / 2.0
    # Map daily equilibrium to 5m bars
    eq_map = daily_eq_series.to_dict()
    daily_eq = np.array([eq_map.get(d, np.nan) for d in df_nq.index.date])

    # Swing Pivots
    sw_h = np.full(n, np.nan)
    sw_l = np.full(n, np.nan)
    es_sw_h = np.full(n, np.nan)
    es_sw_l = np.full(n, np.nan)

    for i in range(3, n - 3):
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i-3] and
            highs[i] > highs[i+1] and highs[i] > highs[i+2] and highs[i] > highs[i+3]):
            sw_h[i + 3] = highs[i]
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i-3] and
            lows[i] < lows[i+1] and lows[i] < lows[i+2] and lows[i] < lows[i+3]):
            sw_l[i + 3] = lows[i]
        if (es_highs[i] > es_highs[i-1] and es_highs[i] > es_highs[i-2] and es_highs[i] > es_highs[i-3] and
            es_highs[i] > es_highs[i+1] and es_highs[i] > es_highs[i+2] and es_highs[i] > es_highs[i+3]):
            es_sw_h[i + 3] = es_highs[i]
        if (es_lows[i] < es_lows[i-1] and es_lows[i] < es_lows[i-2] and es_lows[i] < es_lows[i-3] and
            es_lows[i] < es_lows[i+1] and es_lows[i] < es_lows[i+2] and es_lows[i] < es_lows[i+3]):
            es_sw_l[i + 3] = es_lows[i]

    # 1m data for intrabar execution
    use_1m = df_1m is not None and len(df_1m) > 0
    if use_1m:
        if not isinstance(df_1m.index, pd.DatetimeIndex):
            df_1m["datetime"] = pd.to_datetime(df_1m["datetime"])
            df_1m.set_index("datetime", inplace=True)
        df_1m = df_1m.sort_index()
        df_1m_lookup = df_1m.groupby(pd.Grouper(freq="5min", closed="right", label="right"))

    # State
    has_bull_sweep = False
    has_bear_sweep = False
    bull_sweep_bar = -9999
    bear_sweep_bar = -9999

    # CISD state — now tracks the delivery origin candle, not the run high/low
    armed_bull_cisd = False
    armed_bear_cisd = False
    cisd_bull_level = np.nan      # OPEN of the delivery origin candle
    cisd_bear_level = np.nan
    cisd_bull_sl = np.nan          # LOW of the delivery origin candle (SL-4)
    cisd_bear_sl = np.nan          # HIGH of the delivery origin candle (SL-4)
    cisd_bull_sweep_bar = -1       # bar where the sweep happened (CISD can't confirm same bar)
    cisd_bear_sweep_bar = -1

    pending_zone: Optional[Dict] = None
    current_date = None
    daily_trade_count = 0

    for i in range(25, n):
        t = times[i]
        bar_date = t.date()
        hhmm = time_strs[i]
        is_eod = (hhmm >= "1555")

        if bar_date != current_date:
            current_date = bar_date
            daily_trade_count = 0

        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h1, l1 = highs[i-1], lows[i-1]
        h2, l2 = highs[i-2], lows[i-2]
        es_h, es_l, es_c = es_highs[i], es_lows[i], es_closes[i]

        # STEP 1: POSITION MANAGEMENT
        # If using 1m, evaluate the bracket on 1m bars within this 5m bar
        if use_1m and bracket_mgr.active_position is not None:
            try:
                bars_1m = df_1m_lookup.get_group(t)
            except KeyError:
                bars_1m = None
            if bars_1m is not None and len(bars_1m) > 0:
                for _, m_bar in bars_1m.iterrows():
                    mh, ml, mc = m_bar["high"], m_bar["low"], m_bar["close"]
                    m_time = m_bar.name
                    m_is_eod = m_time.strftime("%H%M") >= "1555"
                    bracket_mgr.update_bar(bar_idx=i, bar_time=m_time,
                                           high=mh, low=ml, close=mc, is_eod_bar=m_is_eod)
                    if bracket_mgr.active_position is None:
                        break  # position closed, stop evaluating 1m bars
            # Also check EOD on 5m close if still open
            if is_eod and bracket_mgr.active_position is not None:
                bracket_mgr.update_bar(bar_idx=i, bar_time=t, high=h0, low=l0,
                                       close=c0, is_eod_bar=True)
        else:
            exit_result = bracket_mgr.update_bar(
                bar_idx=i, bar_time=t, high=h0, low=l0, close=c0, is_eod_bar=is_eod,
            )
            if exit_result is not None:
                if exit_result.exit_reason == "STOP_LOSS" and enable_trap_reexpansion:
                    sl_dist = abs(exit_result.net_pnl_pts / 2.0)
                    inv_price = (exit_result.entry_price - sl_dist) if exit_result.direction == 1 else (exit_result.entry_price + sl_dist)
                    trap_engine.on_structure_invalidation(
                        bar_idx=i, failed_direction=exit_result.direction,
                        invalidation_price=inv_price, failed_anchor_price=exit_result.entry_price,
                    )

        # STEP 2: TRAP FILL CHECK
        in_am = ("0950" <= hhmm <= "1115")
        in_pm = ("1330" <= hhmm <= "1515")
        in_session = (in_am or in_pm)

        trap_fill = trap_engine.check_fill(bar_idx=i, high=h0, low=l0)
        if trap_fill is not None and in_session and bracket_mgr.active_position is None:
            t_dir, t_entry, t_sl, t_tgt = trap_fill
            bracket_mgr.open_pack(t_dir, t_entry, t_sl, i, t, is_pm_macro=in_pm)
            daily_trade_count += 1

        # STEP 3: PENDING ZONE FILL
        if pending_zone is not None and in_session and daily_trade_count < 3 and bracket_mgr.active_position is None:
            p_dir = pending_zone["dir"]
            p_level = pending_zone["entry_level"]
            p_sl = pending_zone["sl"]
            p_bar = pending_zone["armed_bar"]

            if (i - p_bar) <= 15:
                if p_dir == 1 and l0 <= p_level:
                    bracket_mgr.open_pack(1, p_level, p_sl, i, t, is_pm_macro=in_pm)
                    daily_trade_count += 1
                    pending_zone = None
                elif p_dir == -1 and h0 >= p_level:
                    bracket_mgr.open_pack(-1, p_level, p_sl, i, t, is_pm_macro=in_pm)
                    daily_trade_count += 1
                    pending_zone = None
            else:
                pending_zone = None

        # STEP 4: SMT + SWEEP DETECTION
        smt_res = smt_engine.update_bar(
            bar_idx=i, p_high=h0, p_low=l0, p_close=c0,
            b_high=es_h, b_low=es_l, b_close=es_c,
            p_swing_high=sw_h[i], p_swing_low=sw_l[i],
            b_swing_high=es_sw_h[i], b_swing_low=es_sw_l[i],
        )

        pdh = pdh_map.get(bar_date, np.nan)
        pdl = pdl_map.get(bar_date, np.nan)
        daily_bsl = not np.isnan(pdh) and h0 > pdh and (c0 < pdh or o0 < pdh)
        daily_ssl = not np.isnan(pdl) and l0 < pdl and (c0 > pdl or o0 > pdl)

        if (smt_res.bullish_smt and smt_res.primary_swept_ssl) or daily_ssl:
            has_bull_sweep = True
            bull_sweep_bar = i
        if (smt_res.bearish_smt and smt_res.primary_swept_bsl) or daily_bsl:
            has_bear_sweep = True
            bear_sweep_bar = i

        if (i - bull_sweep_bar) > 15: has_bull_sweep = False
        if (i - bear_sweep_bar) > 15: has_bear_sweep = False

        # STEP 5: CANONICAL CISD — FIXED
        # Walk backward from sweep bar to find the bearish delivery run.
        # The DELIVERY ORIGIN is the OLDEST candle in the run (the first one
        # that started the bearish move). Its OPEN is the CISD level,
        # and its LOW (body) is the SL-4 anchor.
        if has_bull_sweep:
            run_opens = []
            run_highs = []
            run_lows = []
            for k in range(1, min(20, i)):
                if closes[i-k] <= opens[i-k]:  # bearish candle
                    run_opens.append(opens[i-k])
                    run_highs.append(max(opens[i-k], closes[i-k]))
                    run_lows.append(min(opens[i-k], closes[i-k]))
                else:
                    break
            # Require at least 2 bearish candles for a valid delivery sequence
            if len(run_opens) >= 2:
                origin_open = run_opens[-1]       # OPEN of the oldest candle in the run
                origin_low = min(run_lows[-1], run_lows[-2])
                cisd_bull_level = origin_open
                cisd_bull_sl = origin_low
                armed_bull_cisd = True
                cisd_bull_sweep_bar = i

        if has_bear_sweep:
            run_opens = []
            run_highs = []
            run_lows = []
            for k in range(1, min(20, i)):
                if closes[i-k] >= opens[i-k]:  # bullish candle
                    run_opens.append(opens[i-k])
                    run_highs.append(max(opens[i-k], closes[i-k]))
                    run_lows.append(min(opens[i-k], closes[i-k]))
                else:
                    break
            if len(run_opens) >= 2:
                origin_open = run_opens[-1]
                origin_high = max(run_highs[-1], run_highs[-2])
                cisd_bear_level = origin_open
                cisd_bear_sl = origin_high
                armed_bear_cisd = True
                cisd_bear_sweep_bar = i

        # Displacement & HTF filters
        body_bps = (abs(c0 - o0) / c0) * 10000.0
        cur_vol_sma = vol_sma[i] if not np.isnan(vol_sma[i]) else 1.0
        passes_disp = (body_bps >= 3.0 and volumes[i] >= 1.1 * cur_vol_sma)
        cur_htf = htf_trend_series[i]
        bull_htf = (cur_htf >= 0)
        bear_htf = (cur_htf <= 0)

        # Premium/Discount filter
        eq = daily_eq[i] if i < len(daily_eq) and not np.isnan(daily_eq[i]) else np.nan
        if enable_premium_discount and not np.isnan(eq):
            in_discount = c0 < eq    # price below equilibrium = discount
            in_premium = c0 > eq      # price above equilibrium = premium
        else:
            in_discount = True
            in_premium = True

        # STEP 6: CISD CONFIRMATION + FVG ENTRY ARMING — FIXED
        # CISD confirmed when close crosses the DELIVERY ORIGIN OPEN (not the run high)
        # Must be on a bar AFTER the sweep bar (not the same bar)
        if armed_bull_cisd and not np.isnan(cisd_bull_level) and i > cisd_bull_sweep_bar and c0 > cisd_bull_level:
            armed_bull_cisd = False
            has_bull_sweep = False
            # Only arm if: displacement + HTF aligned + in discount + no position + no pending
            if (passes_disp and bull_htf and in_discount and
                pending_zone is None and bracket_mgr.active_position is None and
                daily_trade_count < 3):
                # REQUIRE a First Presented FVG on the CISD confirmation bar
                new_fvg = l0 > h2
                if not new_fvg:
                    has_bull_sweep = False
                    continue  # No FVG = no entry. ICT requires an imbalance to enter.

                z_top, z_bot = l0, h2
                z_ce = (z_top + z_bot) / 2.0

                # SL-4: below the delivery origin candle low
                sl_price = cisd_bull_sl - (2 * tick_size)
                if sl_price >= z_ce:
                    sl_price = min(l0, l1, l2) - (2 * tick_size)

                risk_dist = z_ce - sl_price
                if risk_dist > 0 and ((risk_dist / z_ce) * 10000.0) <= max_risk_bps:
                    pending_zone = {"dir": 1, "entry_level": z_ce, "sl": sl_price, "armed_bar": i}

        if armed_bear_cisd and not np.isnan(cisd_bear_level) and i > cisd_bear_sweep_bar and c0 < cisd_bear_level:
            armed_bear_cisd = False
            has_bear_sweep = False
            if (passes_disp and bear_htf and in_premium and
                pending_zone is None and bracket_mgr.active_position is None and
                daily_trade_count < 3):
                new_fvg = h0 < l2
                if not new_fvg:
                    has_bear_sweep = False
                    continue

                z_top, z_bot = l2, h0
                z_ce = (z_top + z_bot) / 2.0

                sl_price = cisd_bear_sl + (2 * tick_size)
                if sl_price <= z_ce:
                    sl_price = max(h0, h1, h2) + (2 * tick_size)

                risk_dist = sl_price - z_ce
                if risk_dist > 0 and ((risk_dist / z_ce) * 10000.0) <= max_risk_bps:
                    pending_zone = {"dir": -1, "entry_level": z_ce, "sl": sl_price, "armed_bar": i}

    # Compile results
    trades_data = [
        {
            "trade_id": r.trade_id, "direction": r.direction,
            "entry_time": r.entry_time, "exit_time": r.exit_time,
            "entry_price": r.entry_price, "queen_filled": r.queen_filled,
            "exit_reason": r.exit_reason, "net_pnl_pts": r.net_pnl_pts,
            "net_pnl_usd": r.net_pnl_usd, "mfe_pts": r.mfe_pts,
            "mae_pts": r.mae_pts, "bars_held": r.bars_held,
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
    p = argparse.ArgumentParser(description="ICT-Correct Backtest v2")
    p.add_argument("--symbol", default="NQ", choices=["NQ", "ES"])
    p.add_argument("--start", default="2020-01-10")
    p.add_argument("--end", default="2026-08-11")
    p.add_argument("--use-1m", action="store_true", help="Use 1m intrabar execution")
    p.add_argument("--no-pd-filter", dest="enable_pd", action="store_false",
                    help="Disable premium/discount filter")
    p.add_argument("--no-trap", dest="enable_trap", action="store_false")
    args = p.parse_args()

    sym_file = "NQ1_5m" if args.symbol == "NQ" else "ES1_5m"
    df_nq = pd.read_parquet(_root / "data" / f"{sym_file}.parquet")
    df_es = pd.read_parquet(_root / "data" / "ES1_5m.parquet")
    for d in (df_nq, df_es):
        if not isinstance(d.index, pd.DatetimeIndex):
            d["datetime"] = pd.to_datetime(d["datetime"])
            d.set_index("datetime", inplace=True)

    df_nq = df_nq[(df_nq.index >= args.start) & (df_nq.index <= args.end)]
    df_es = df_es[(df_es.index >= args.start) & (df_es.index <= args.end)]

    df_1m = None
    if args.use_1m:
        df_1m = pd.read_parquet(_root / "data" / f"{sym_file.replace('_5m', '_1m')}.parquet")

    pv = 2.0 if args.symbol == "NQ" else 5.0
    comm = 0.52 if args.symbol == "NQ" else 0.40

    print(f"Loaded {len(df_nq):,} 5m bars ({df_nq.index.min().date()} -> {df_nq.index.max().date()})")
    if args.use_1m:
        print(f"  + {len(df_1m):,} 1m bars for intrabar execution")
    print(f"  Premium/Discount filter: {'ON' if args.enable_pd else 'OFF'}")
    print(f"  Trap re-expansion: {'ON' if args.enable_trap else 'OFF'}")
    print()

    tdf, stats = run_ict_v2_backtest(
        df_nq, df_es, df_1m=df_1m if args.use_1m else None,
        symbol=args.symbol, point_value=pv, comm_per_contract=comm,
        enable_trap_reexpansion=args.enable_trap,
        enable_premium_discount=args.enable_pd,
    )

    if len(tdf) == 0:
        print("No trades generated.")
        return

    print("=" * 80)
    print(f"  ICT v2 RESULTS — {args.symbol} ({args.start} -> {args.end})")
    print("=" * 80)
    print(f"Total Trades:       {stats['trades']}")
    print(f"Win Rate:           {stats['win_rate']:.1f}%")
    print(f"Profit Factor:      {stats['profit_factor']:.2f}")
    print(f"Net PnL:            ${stats['net_pnl']:,.2f}")
    print(f"Gross Profit:       ${stats['gross_profit']:,.2f}")
    print(f"Gross Loss:         ${stats['gross_loss']:,.2f}")
    print(f"Avg Win:            ${stats['avg_win']:.2f}")
    print(f"Avg Loss:           ${stats['avg_loss']:.2f}")
    print(f"Payoff Ratio:       {stats['payoff_ratio']:.2f}:1")
    print(f"Max Drawdown:       ${stats['max_dd']:,.2f}")
    print()

    print("Exit Reasons:")
    for reason, cnt in tdf["exit_reason"].value_counts().items():
        print(f"  {reason:<20} {cnt:>5}  ({cnt/len(tdf)*100:.1f}%)")

    # Forensic on losers
    losers = tdf[tdf["net_pnl_usd"] < 0]
    winners = tdf[tdf["net_pnl_usd"] > 0]
    if len(losers) > 0:
        print(f"\nLoser Analysis:")
        print(f"  Avg MFE: {losers['mfe_pts'].mean():.1f}pts  Avg MAE: {losers['mae_pts'].mean():.1f}pts")
        print(f"  Avg bars held: {losers['bars_held'].mean():.1f}")
        be_losers = losers[losers["queen_filled"]]
        sl_losers = losers[~losers["queen_filled"]]
        print(f"  Queen filled then lost (BE): {len(be_losers)} ({len(be_losers)/len(losers)*100:.1f}%)")
        print(f"  Pure stop loss (no Queen):   {len(sl_losers)} ({len(sl_losers)/len(losers)*100:.1f}%)")
    if len(winners) > 0:
        print(f"\nWinner Analysis:")
        print(f"  Avg MFE: {winners['mfe_pts'].mean():.1f}pts  Avg MAE: {winners['mae_pts'].mean():.1f}pts")
        print(f"  Avg bars held: {winners['bars_held'].mean():.1f}")

    # Save
    out_dir = _root / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    tdf.to_csv(out_dir / f"ict_v2_{stamp}.csv", index=False)
    print(f"\nTrades saved to reports/ict_v2_{stamp}.csv")


if __name__ == "__main__":
    main()