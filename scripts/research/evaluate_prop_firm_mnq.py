"""
========================================================================================
Institutional Prop Firm Evaluation Engine for Micro NQ (MNQ) Futures
========================================================================================
Evaluates the ICT CISD + FVG Strategy across Prop Firm Standards:
- Micro E-mini Nasdaq (MNQ) @ $2.00 / point ($0.50 / tick)
- Real commission friction: $1.40 round turn per MNQ contract
- Real slippage modeling: 1 tick ($0.50) on stops / market exits
- Multi-tier contract sizing: 2 MNQ, 4 MNQ, 6 MNQ, 10 MNQ (Apex / Topstep 50k & 100k)
- Monte Carlo simulation: 5,000 resampled evaluation paths
- Trailing High-Water Mark (Apex) vs. EOD Trailing Drawdown (Topstep) vs. Static
========================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.trading_framework.ml.prop_firm_simulator import (
    FIRM_PROFILES,
    PropFirmProfile,
    PropFirmSimulator,
)


def extract_strategy_trades_mnq(start_year: int = 2022) -> pd.DataFrame:
    """Run the validated ICT CISD Strategy (4H Bias + Lunch Blackout + PO3 Midnight Open) and extract raw trades."""
    print("Loading data for Prop Firm MNQ evaluation...", flush=True)
    df_nq = pd.read_parquet(_root / "data/NQ1_5m.parquet")
    df_nq = df_nq[df_nq.index >= f"{start_year}-01-01"].copy()

    if df_nq.index.tz is None:
        df_nq.index = df_nq.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_nq.index = df_nq.index.tz_convert("America/New_York")

    times = df_nq.index
    n = len(df_nq)

    nq_o = df_nq["open"].to_numpy(dtype=np.float64)
    nq_h = df_nq["high"].to_numpy(dtype=np.float64)
    nq_l = df_nq["low"].to_numpy(dtype=np.float64)
    nq_c = df_nq["close"].to_numpy(dtype=np.float64)

    # 4H Bias
    df_4h = df_nq.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["ema20"] = df_4h["close"].ewm(span=20).mean()
    df_4h_reindexed = df_4h.reindex(df_nq.index, method="ffill")
    htf_bias_arr = np.where(df_4h_reindexed["close"] > df_4h_reindexed["ema20"], 1, -1)

    time_strs = times.strftime("%H%M")
    hours = times.hour
    mins = times.minute

    midnight_open = np.nan
    cur_day = None

    vibes = 0
    bagholder_entry = np.nan
    pain_threshold = np.nan

    def consult_crystal_ball(bias: int, idx: int):
        max_lb = min(15, idx)
        ext_o = nq_o[idx - 1]
        for k in range(1, max_lb + 1):
            is_opp = (nq_c[idx - k] < nq_o[idx - k]) if bias == 1 else (nq_c[idx - k] > nq_o[idx - k])
            if is_opp:
                ext_o = nq_o[idx - k]
                break
        return ext_o

    trades = []
    in_pos = False
    pos_dir = 0
    pos_entry_price = 0.0
    pos_entry_time = None
    active_sl = 0.0
    active_tp1 = 0.0
    active_tp2 = 0.0
    queen_filled = False

    daily_trades = 0
    pending_order = None

    for i in range(25, n):
        t = times[i]
        hhmm = time_strs[i]
        bar_date = t.date()
        h0, l0, c0, o0 = nq_h[i], nq_l[i], nq_c[i], nq_o[i]
        h2, l2 = nq_h[i - 2], nq_l[i - 2]
        hh = hours[i]
        mm = mins[i]

        if bar_date != cur_day:
            cur_day = bar_date
            daily_trades = 0
            pending_order = None

        if hh == 0 and mm == 0:
            midnight_open = o0

        # Position Management
        if in_pos:
            if pos_dir == 1:
                if hhmm >= "1555":
                    q_pts = (active_tp1 - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                    r_pts = (c0 - pos_entry_price)
                    avg_pts = (q_pts + r_pts) / 2.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": c0, "points": avg_pts,
                        "is_win": avg_pts > 0, "queen_hit": queen_filled, "runner_hit": False,
                    })
                    in_pos = False

                elif l0 <= active_sl:
                    q_pts = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                    r_pts = (active_sl - pos_entry_price)
                    avg_pts = (q_pts + r_pts) / 2.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "points": avg_pts,
                        "is_win": avg_pts > 0, "queen_hit": queen_filled, "runner_hit": False,
                    })
                    in_pos = False

                elif not queen_filled and h0 >= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price

                elif h0 >= active_tp2:
                    q_pts = (active_tp1 - pos_entry_price)
                    r_pts = (active_tp2 - pos_entry_price)
                    avg_pts = (q_pts + r_pts) / 2.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_tp2, "points": avg_pts,
                        "is_win": True, "queen_hit": True, "runner_hit": True,
                    })
                    in_pos = False

            elif pos_dir == -1:
                if hhmm >= "1555":
                    q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                    r_pts = (pos_entry_price - c0)
                    avg_pts = (q_pts + r_pts) / 2.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": c0, "points": avg_pts,
                        "is_win": avg_pts > 0, "queen_hit": queen_filled, "runner_hit": False,
                    })
                    in_pos = False

                elif h0 >= active_sl:
                    q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                    r_pts = (pos_entry_price - active_sl)
                    avg_pts = (q_pts + r_pts) / 2.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "points": avg_pts,
                        "is_win": avg_pts > 0, "queen_hit": queen_filled, "runner_hit": False,
                    })
                    in_pos = False

                elif not queen_filled and l0 <= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price

                elif l0 <= active_tp2:
                    q_pts = (pos_entry_price - active_tp1)
                    r_pts = (pos_entry_price - active_tp2)
                    avg_pts = (q_pts + r_pts) / 2.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_tp2, "points": avg_pts,
                        "is_win": True, "queen_hit": True, "runner_hit": True,
                    })
                    in_pos = False

        # Limit order fill
        if pending_order is not None and not in_pos:
            p_dir = pending_order["dir"]
            p_limit = pending_order["limit"]
            p_sl = pending_order["sl"]
            p_bar = pending_order["bar"]

            if (i - p_bar) <= 6:
                in_time = ("0945" <= hhmm <= "1530") and not ("1200" <= hhmm <= "1330")
                if in_time and daily_trades < 5:
                    if p_dir == 1 and l0 <= p_limit:
                        in_pos = True
                        pos_dir = 1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        active_sl = p_sl
                        active_tp1 = p_limit + (p_limit * 0.0010)
                        active_tp2 = p_limit + (p_limit * 0.0030)
                        queen_filled = False
                        daily_trades += 1
                        pending_order = None
                    elif p_dir == -1 and h0 >= p_limit:
                        in_pos = True
                        pos_dir = -1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        active_sl = p_sl
                        active_tp1 = p_limit - (p_limit * 0.0010)
                        active_tp2 = p_limit - (p_limit * 0.0030)
                        queen_filled = False
                        daily_trades += 1
                        pending_order = None
            else:
                pending_order = None

        # CISD Signals
        candle_pers = 1 if c0 > o0 else (-1 if c0 < o0 else 0)
        if vibes == 0:
            vibes = candle_pers if candle_pers != 0 else 1
            bagholder_entry = consult_crystal_ball(vibes, i)
            pain_threshold = h0 if vibes == 1 else l0

        if vibes == 1 and h0 > pain_threshold:
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)
        elif vibes == -1 and l0 < pain_threshold:
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)

        active_lvl = bagholder_entry

        if vibes == -1 and c0 > active_lvl:
            vibes = 1
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)
            # Pro-Trend 4H & PO3 Midnight Open
            allow = (htf_bias_arr[i] == 1) and (not np.isnan(midnight_open) and c0 <= midnight_open)
            if allow:
                fvg_top = h2 if l0 > h2 else active_lvl
                sl_price = fvg_top - (fvg_top * 0.0005)  # 5 bps
                pending_order = {"dir": 1, "limit": fvg_top, "sl": sl_price, "bar": i}

        elif vibes == 1 and c0 < active_lvl:
            vibes = -1
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)
            allow = (htf_bias_arr[i] == -1) and (not np.isnan(midnight_open) and c0 >= midnight_open)
            if allow:
                fvg_bot = l2 if h0 < l2 else active_lvl
                sl_price = fvg_bot + (fvg_bot * 0.0005)
                pending_order = {"dir": -1, "limit": fvg_bot, "sl": sl_price, "bar": i}

    return pd.DataFrame(trades)


def run_mnq_prop_simulation(
    trades: pd.DataFrame,
    contracts: int,
    commission_per_contract_rt: float = 1.40,
    slippage_ticks: float = 1.0,
    profile_key: str = "apex_50k",
    n_simulations: int = 5000,
) -> Dict:
    """
    Simulate prop firm pass rate and drawdown with Micro NQ (MNQ) contracts.
    Point value = $2.00 per point ($0.50 per tick).
    """
    df = trades.copy()
    point_val = 2.0  # MNQ = $2/pt
    tick_val = 0.50  # MNQ tick = $0.50

    # Net dollar P&L per trade = (points * $2.00 * contracts) - (commissions * contracts) - (slippage * contracts)
    gross_dollar = df["points"] * point_val * contracts
    total_commission = commission_per_contract_rt * contracts
    total_slippage = (slippage_ticks * tick_val) * contracts
    net_dollar = gross_dollar - total_commission - total_slippage

    df["dollar_pnl"] = net_dollar
    # pnl_pct for PropFirmSimulator: dollar_pnl / account_size * 100
    account_size = FIRM_PROFILES[profile_key].account_size
    df["pnl_pct"] = (df["dollar_pnl"] / account_size) * 100.0

    profile = FIRM_PROFILES[profile_key]
    sim = PropFirmSimulator(account_size=account_size, point_value=point_val)

    # 1. Deterministic Historical Path
    det = sim.run_deterministic(df, profile)

    # 2. Monte Carlo Resampling (5,000 runs)
    mc = sim.run_monte_carlo(df, profile, n_simulations=n_simulations)

    return {
        "contracts": contracts,
        "profile": profile.name,
        "total_trades": det.total_trades,
        "historical_passed": det.passed,
        "historical_blown": det.blown,
        "max_dd_historical": det.max_drawdown_used,
        "mc_pass_rate": mc.pass_rate_pct,
        "mc_blow_rate": mc.blow_rate_pct,
        "median_days_to_pass": mc.median_days_to_pass,
        "avg_max_drawdown": mc.avg_max_drawdown,
        "grade": mc.grade,
        "avg_trade_dollar": net_dollar.mean(),
        "win_rate": (net_dollar > 0).mean() * 100.0,
    }


def main():
    print(f"\n{'='*120}", flush=True)
    print("INSTITUTIONAL PROP FIRM EVALUATION: MICRO NQ (MNQ) SIZING & COMPLIANCE", flush=True)
    print("=" * 120, flush=True)

    trades = extract_strategy_trades_mnq(start_year=2022)
    print(f"Total historical trades extracted: {len(trades):,d}", flush=True)

    profiles = [
        "takeprofittrader_50k",
        "tradeify_50k",
        "lucid_50k",
        "topstep_50k",
        "apex_50k",
    ]
    contract_tiers = [4, 6, 8]

    results = []
    for prof in profiles:
        for c in contract_tiers:
            res = run_mnq_prop_simulation(
                trades,
                contracts=c,
                commission_per_contract_rt=1.40,
                slippage_ticks=1.0,
                profile_key=prof,
                n_simulations=5000,
            )
            results.append({
                "Challenge": res["profile"],
                "MNQ Contracts": f"{c} MNQ",
                "Risk / Trade ($)": f"${c * 20.0:.0f}",
                "Historical Pass": "YES" if res["historical_passed"] else "NO",
                "Historical Max DD": f"${res['max_dd_historical']:,.0f}",
                "MC Pass Rate (%)": f"{res['mc_pass_rate']:.1f}%",
                "MC Blow Rate (%)": f"{res['mc_blow_rate']:.1f}%",
                "Median Days": f"{res['median_days_to_pass']:.0f} days" if res['median_days_to_pass'] is not None and res['median_days_to_pass'] > 0 else "N/A",
                "Avg Max Drawdown": f"${res['avg_max_drawdown']:,.0f}",
                "Prop Grade": res["grade"],
                "Net $/Trade": f"${res['avg_trade_dollar']:+.2f}",
            })

    df_res = pd.DataFrame(results)
    print("\n" + "─" * 120, flush=True)
    print("🎯 PROP FIRM CHALLENGE VIABILITY MATRIX (APEX / TOPSTEP WITH REAL COMMISSIONS & SLIPPAGE)", flush=True)
    print("─" * 120, flush=True)
    print(df_res.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
