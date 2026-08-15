"""
========================================================================================
Production Master Institutional Strategy Backtester
========================================================================================
Combines modular, reusable components from scripts/libs_py:
- SMTDivergenceEngine (scripts.libs_py.ict_engine.core.smt)
- TrappedLiquidityEngine (scripts.libs_py.ict_engine.core.trap_engine)
- PackBracketManager (scripts.libs_py.strategy_engine.pack_bracket_manager)
- HTFOrderFlowFilter (scripts.libs_py.features.htf_order_flow)

Demonstrates clean, decoupled architecture usable across all strategies in the repo.
========================================================================================
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd
import numpy as np

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.libs_py.ict_engine.core.smt import SMTDivergenceEngine
from scripts.libs_py.ict_engine.core.trap_engine import TrappedLiquidityEngine
from scripts.libs_py.strategy_engine.pack_bracket_manager import PackBracketManager
from scripts.libs_py.features.htf_order_flow import HTFOrderFlowFilter

def run_master_backtest(
    df_nq: pd.DataFrame,
    df_es: pd.DataFrame,
    symbol: str = "NQ",
    point_value: float = 2.0,
    comm_per_contract: float = 0.52,
    enable_trap_reexpansion: bool = True,
    queen_bps: float = 10.0,
    runner_bps: float = 40.0,
    runner_pm_bps: float = 60.0,
    max_risk_bps: float = 12.0,
) -> Tuple[pd.DataFrame, Dict]:

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

    es_highs = df_es["high"].values
    es_lows = df_es["low"].values
    es_closes = df_es["close"].values

    # 1. Initialize Modular Engines
    smt_engine = SMTDivergenceEngine(pivot_left=3, pivot_right=3, max_swings_tracked=10)
    trap_engine = TrappedLiquidityEngine(max_wait_bars=3, target_bps=40.0, max_risk_bps=15.0)
    bracket_mgr = PackBracketManager(
        queen_bps=queen_bps,
        runner_bps=runner_bps,
        runner_pm_bps=runner_pm_bps,
        point_value=point_value,
        comm_per_contract=comm_per_contract,
        tick_size=0.25 if symbol == "ES" else 0.50,
    )

    # 2. HTF Features
    htf_trend_series = HTFOrderFlowFilter.compute_1h_trend_series(df_nq, fast_span=20, slow_span=50)
    vol_sma = pd.Series(volumes).rolling(20).mean().values

    daily_df = df_nq.groupby(df_nq.index.date).agg({"high": "max", "low": "min"}).shift(1)
    pdh_map = daily_df["high"].to_dict()
    pdl_map = daily_df["low"].to_dict()

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

    time_strs = df_nq.index.strftime("%H%M")

    # State tracking
    has_bull_sweep = False
    has_bear_sweep = False
    bull_sweep_bar = -9999
    bear_sweep_bar = -9999

    armed_bull_cisd = False
    armed_bear_cisd = False
    armed_bull_high = np.nan
    armed_bear_low = np.nan
    armed_cisd_origin_sl = np.nan

    pending_zone = None
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

        # -------------------------------------------------------------
        # STEP 1: POSITION MANAGEMENT VIA MODULAR BRACKET MANAGER
        # -------------------------------------------------------------
        exit_result = bracket_mgr.update_bar(
            bar_idx=i,
            bar_time=t,
            high=h0,
            low=l0,
            close=c0,
            is_eod_bar=is_eod,
        )

        if exit_result is not None:
            # If standard trade stopped out at initial SL, arm Trapped Liquidity Breakout!
            if exit_result.exit_reason == "STOP_LOSS" and enable_trap_reexpansion:
                sl_dist = abs(exit_result.net_pnl_pts / 2.0)
                inv_price = (exit_result.entry_price - sl_dist) if exit_result.direction == 1 else (exit_result.entry_price + sl_dist)
                trap_engine.on_structure_invalidation(
                    bar_idx=i,
                    failed_direction=exit_result.direction,
                    invalidation_price=inv_price,
                    failed_anchor_price=exit_result.entry_price,
                )

        # -------------------------------------------------------------
        # STEP 2: CHECK TRAPPED LIQUIDITY RE-EXPANSION FILL (Alpha 1)
        # -------------------------------------------------------------
        in_am = ("0950" <= hhmm <= "1115")
        in_pm = ("1330" <= hhmm <= "1515")
        in_session = (in_am or in_pm)

        trap_fill = trap_engine.check_fill(bar_idx=i, high=h0, low=l0)
        if trap_fill is not None and in_session and bracket_mgr.active_position is None:
            t_dir, t_entry, t_sl, t_tgt = trap_fill
            bracket_mgr.open_pack(
                direction=t_dir,
                entry_price=t_entry,
                stop_loss=t_sl,
                bar_idx=i,
                bar_time=t,
                is_pm_macro=in_pm,
            )
            daily_trade_count += 1

        # -------------------------------------------------------------
        # STEP 3: CHECK STANDARD FIRST FVG RETEST FILL
        # -------------------------------------------------------------
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

        # -------------------------------------------------------------
        # STEP 4: INTERMARKET SMT ENGINE & SWEEP UPDATE
        # -------------------------------------------------------------
        smt_res = smt_engine.update_bar(
            bar_idx=i,
            p_high=h0, p_low=l0, p_close=c0,
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

        if (i - bull_sweep_bar) > 20: has_bull_sweep = False
        if (i - bear_sweep_bar) > 20: has_bear_sweep = False

        # -------------------------------------------------------------
        # STEP 5: CANONICAL CISD DETECTION
        # -------------------------------------------------------------
        if has_bull_sweep:
            s_high, s_low = max(o0, c0), min(o0, c0)
            for k in range(1, min(20, i)):
                if closes[i-k] <= opens[i-k]:
                    s_high = max(s_high, max(opens[i-k], closes[i-k]))
                    s_low = min(s_low, min(opens[i-k], closes[i-k]))
                else: break
            armed_bull_cisd, armed_bull_high, armed_cisd_origin_sl = True, s_high, s_low

        if has_bear_sweep:
            s_high, s_low = max(o0, c0), min(o0, c0)
            for k in range(1, min(20, i)):
                if closes[i-k] >= opens[i-k]:
                    s_high = max(s_high, max(opens[i-k], closes[i-k]))
                    s_low = min(s_low, min(opens[i-k], closes[i-k]))
                else: break
            armed_bear_cisd, armed_bear_low, armed_cisd_origin_sl = True, s_low, s_high

        body_bps = (abs(c0 - o0) / c0) * 10000.0
        cur_vol_sma = vol_sma[i] if not np.isnan(vol_sma[i]) else 1.0
        passes_disp = (body_bps >= 3.0 and volumes[i] >= 1.1 * cur_vol_sma)

        cur_htf = htf_trend_series[i]
        bull_htf = (cur_htf >= 0)
        bear_htf = (cur_htf <= 0)

        # First Presented FVG Arming
        if armed_bull_cisd and not np.isnan(armed_bull_high) and c0 > armed_bull_high:
            armed_bull_cisd = False
            if passes_disp and bull_htf and pending_zone is None and bracket_mgr.active_position is None:
                new_fvg = l0 > h2
                z_top = l0 if new_fvg else armed_bull_high
                z_bot = h2 if new_fvg else (armed_bull_high - 2.0)
                z_ce = (z_top + z_bot) / 2.0
                raw_sl = armed_cisd_origin_sl if not np.isnan(armed_cisd_origin_sl) else l1
                if raw_sl >= z_ce: raw_sl = min(l0, l1, l2)
                sl_price = raw_sl - 0.50
                risk_dist = z_ce - sl_price
                if risk_dist > 0 and ((risk_dist / z_ce) * 10000.0) <= max_risk_bps:
                    pending_zone = {"dir": 1, "entry_level": z_ce, "sl": sl_price, "armed_bar": i}
            has_bull_sweep = False

        if armed_bear_cisd and not np.isnan(armed_bear_low) and c0 < armed_bear_low:
            armed_bear_cisd = False
            if passes_disp and bear_htf and pending_zone is None and bracket_mgr.active_position is None:
                new_fvg = h0 < l2
                z_top = l2 if new_fvg else (armed_bear_low + 2.0)
                z_bot = h0 if new_fvg else armed_bear_low
                z_ce = (z_top + z_bot) / 2.0
                raw_sl = armed_cisd_origin_sl if not np.isnan(armed_cisd_origin_sl) else h1
                if raw_sl <= z_ce: raw_sl = max(h0, h1, h2)
                sl_price = raw_sl + 0.50
                risk_dist = sl_price - z_ce
                if risk_dist > 0 and ((risk_dist / z_ce) * 10000.0) <= max_risk_bps:
                    pending_zone = {"dir": -1, "entry_level": z_ce, "sl": sl_price, "armed_bar": i}
            has_bear_sweep = False

    # Compile Results
    trades_data = [
        {
            "trade_id": r.trade_id,
            "direction": r.direction,
            "entry_time": r.entry_time,
            "exit_time": r.exit_time,
            "entry_price": r.entry_price,
            "queen_filled": r.queen_filled,
            "exit_reason": r.exit_reason,
            "net_pnl_pts": r.net_pnl_pts,
            "net_pnl_usd": r.net_pnl_usd,
            "mfe_pts": r.mfe_pts,
            "mae_pts": r.mae_pts,
            "bars_held": r.bars_held,
        }
        for r in bracket_mgr.completed_trades
    ]
    trades_df = pd.DataFrame(trades_data)
    if len(trades_df) == 0:
        return trades_df, {}

    w = trades_df[trades_df["net_pnl_usd"] > 0]
    l = trades_df[trades_df["net_pnl_usd"] < 0]
    gp = w["net_pnl_usd"].sum()
    gl = abs(l["net_pnl_usd"].sum())

    stats = {
        "trades": len(trades_df),
        "win_rate": (len(w) / len(trades_df)) * 100,
        "profit_factor": (gp / gl) if gl > 0 else np.nan,
        "net_pnl": trades_df["net_pnl_usd"].sum(),
        "gross_profit": gp,
        "gross_loss": gl,
        "avg_win": w["net_pnl_usd"].mean() if len(w) > 0 else 0,
        "avg_loss": l["net_pnl_usd"].mean() if len(l) > 0 else 0,
        "payoff_ratio": abs(w["net_pnl_usd"].mean() / l["net_pnl_usd"].mean()) if len(l) > 0 else np.nan,
    }
    return trades_df, stats

if __name__ == "__main__":
    df_nq = pd.read_parquet(_root / "data" / "NQ1_5m.parquet")
    df_es = pd.read_parquet(_root / "data" / "ES1_5m.parquet")

    for d in (df_nq, df_es):
        if not isinstance(d.index, pd.DatetimeIndex):
            d["datetime"] = pd.to_datetime(d["datetime"])
            d.set_index("datetime", inplace=True)

    df_nq_sub = df_nq[df_nq.index >= "2024-01-01"]
    df_es_sub = df_es[df_es.index >= "2024-01-01"]

    print("Running Modular Master Institutional Backtest (2024–2026)...")
    tdf, stats = run_master_backtest(df_nq_sub, df_es_sub, symbol="NQ", point_value=2.0)

    print("\n" + "=" * 80)
    print("MODULAR MASTER STRATEGY RESULTS (2024–2026)")
    print("=" * 80)
    print(f"Total Completed Trades: {stats['trades']}")
    print(f"Win Rate:               {stats['win_rate']:.1f}%")
    print(f"Profit Factor:          {stats['profit_factor']:.2f}")
    print(f"Net PnL (Micro MNQ):    ${stats['net_pnl']:,.2f}  (or +${stats['net_pnl']*10:,.2f} on 1 NQ)")
    print(f"Average Win:            ${stats['avg_win']:.2f}")
    print(f"Average Loss:           ${stats['avg_loss']:.2f}")
    print(f"Payoff Ratio:           {stats['payoff_ratio']:.2f} : 1")
