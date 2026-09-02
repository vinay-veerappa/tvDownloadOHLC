"""
========================================================================================
Institutional Prop Firm Evaluation: Micro S&P (MES) on 25K Accounts
========================================================================================
Covers:
1. Direct strategy execution on ES1 / MES 5-minute data (2022-2026)
2. MES contract specifications: $5.00 / point ($1.25 / tick)
3. Real commissions ($1.40 RT / contract) & slippage (1 tick / $1.25)
4. 25K Prop Firm Challenges:
   - Apex 25K EOD: $1,500 Target / $1,500 EOD Trailing DD / No DLL
   - Apex 25K Legacy: $1,500 Target / $1,500 Intraday Trailing DD / No DLL
   - Take Profit Trader 25K: $1,500 Target / $1,500 EOD Trailing DD / $600 DLL
   - Tradeify / Lucid 25K: $1,500 Target / $1,500 EOD Trailing DD / $500 DLL
5. Contract Sizing Tiers: 2 MES, 4 MES, 6 MES, 8 MES
6. 5,000-run Monte Carlo Simulation across all firms and sizing permutations
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


def run_cisd_strategy_mes(start_year: int = 2022) -> pd.DataFrame:
    """Run the validated ICT CISD Strategy on ES1 / MES 5m data."""
    print("Loading ES1 5m parquet data for MES strategy evaluation...", flush=True)
    df_es = pd.read_parquet(_root / "data/ES1_5m.parquet")
    df_es = df_es[df_es.index >= f"{start_year}-01-01"].copy()

    if df_es.index.tz is None:
        df_es.index = df_es.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_es.index = df_es.index.tz_convert("America/New_York")

    times = df_es.index
    n = len(df_es)

    es_o = df_es["open"].to_numpy(dtype=np.float64)
    es_h = df_es["high"].to_numpy(dtype=np.float64)
    es_l = df_es["low"].to_numpy(dtype=np.float64)
    es_c = df_es["close"].to_numpy(dtype=np.float64)

    # 4H Bias for ES
    df_4h = df_es.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["ema20"] = df_4h["close"].ewm(span=20).mean()
    df_4h_reindexed = df_4h.reindex(df_es.index, method="ffill")
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
        ext_o = es_o[idx - 1]
        for k in range(1, max_lb + 1):
            is_opp = (es_c[idx - k] < es_o[idx - k]) if bias == 1 else (es_c[idx - k] > es_o[idx - k])
            if is_opp:
                ext_o = es_o[idx - k]
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
        h0, l0, c0, o0 = es_h[i], es_l[i], es_c[i], es_o[i]
        h2, l2 = es_h[i - 2], es_l[i - 2]
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
                    pnl_bps = (avg_pts / pos_entry_price) * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": c0, "points": avg_pts,
                        "pnl_bps": pnl_bps, "is_win": avg_pts > 0, "queen_hit": queen_filled, "runner_hit": False,
                    })
                    in_pos = False

                elif l0 <= active_sl:
                    q_pts = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                    r_pts = (active_sl - pos_entry_price)
                    avg_pts = (q_pts + r_pts) / 2.0
                    pnl_bps = (avg_pts / pos_entry_price) * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "points": avg_pts,
                        "pnl_bps": pnl_bps, "is_win": avg_pts > 0, "queen_hit": queen_filled, "runner_hit": False,
                    })
                    in_pos = False

                elif not queen_filled and h0 >= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price

                elif h0 >= active_tp2:
                    q_pts = (active_tp1 - pos_entry_price)
                    r_pts = (active_tp2 - pos_entry_price)
                    avg_pts = (q_pts + r_pts) / 2.0
                    pnl_bps = (avg_pts / pos_entry_price) * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_tp2, "points": avg_pts,
                        "pnl_bps": pnl_bps, "is_win": True, "queen_hit": True, "runner_hit": True,
                    })
                    in_pos = False

            elif pos_dir == -1:
                if hhmm >= "1555":
                    q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                    r_pts = (pos_entry_price - c0)
                    avg_pts = (q_pts + r_pts) / 2.0
                    pnl_bps = (avg_pts / pos_entry_price) * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": c0, "points": avg_pts,
                        "pnl_bps": pnl_bps, "is_win": avg_pts > 0, "queen_hit": queen_filled, "runner_hit": False,
                    })
                    in_pos = False

                elif h0 >= active_sl:
                    q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                    r_pts = (pos_entry_price - active_sl)
                    avg_pts = (q_pts + r_pts) / 2.0
                    pnl_bps = (avg_pts / pos_entry_price) * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "points": avg_pts,
                        "pnl_bps": pnl_bps, "is_win": avg_pts > 0, "queen_hit": queen_filled, "runner_hit": False,
                    })
                    in_pos = False

                elif not queen_filled and l0 <= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price

                elif l0 <= active_tp2:
                    q_pts = (pos_entry_price - active_tp1)
                    r_pts = (pos_entry_price - active_tp2)
                    avg_pts = (q_pts + r_pts) / 2.0
                    pnl_bps = (avg_pts / pos_entry_price) * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_tp2, "points": avg_pts,
                        "pnl_bps": pnl_bps, "is_win": True, "queen_hit": True, "runner_hit": True,
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
                        active_tp1 = p_limit + (p_limit * 0.0010)  # +10 bps
                        active_tp2 = p_limit + (p_limit * 0.0030)  # +30 bps
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

    df_trades = pd.DataFrame(trades)
    print(f"Total MES strategy trades extracted: {len(df_trades):,d}", flush=True)
    return df_trades


# Define 25K Profiles
PROFILES_25K = {
    # ── Apex 25K EOD ──────────────────────────────────────────────────────────
    "apex_25k_eod": PropFirmProfile(
        name="Apex 25K (EOD)",
        account_size=25_000.0,
        profit_target=1_500.0,
        max_trailing_drawdown=1_500.0,
        trailing=True,                  # EOD trailing handled in simulator
        daily_loss_limit=0.0,           # No DLL on Apex
        max_trades_per_day=999,
        consistency_rule_pct=1.0,
        eval_max_days=30,
    ),
    # ── Apex 25K Legacy (Intraday Peak Trailing) ──────────────────────────────
    "apex_25k_legacy": PropFirmProfile(
        name="Apex 25K (Legacy Peak)",
        account_size=25_000.0,
        profit_target=1_500.0,
        max_trailing_drawdown=1_500.0,
        trailing=True,
        daily_loss_limit=0.0,
        max_trades_per_day=999,
        consistency_rule_pct=1.0,
        eval_max_days=30,
    ),
    # ── Take Profit Trader (TPT) 25K ──────────────────────────────────────────
    "tpt_25k": PropFirmProfile(
        name="Take Profit Trader 25K",
        account_size=25_000.0,
        profit_target=1_500.0,
        max_trailing_drawdown=1_500.0,
        trailing=True,                  # EOD Trailing, locks at +$100
        daily_loss_limit=600.0,         # $600 Daily Loss Limit
        max_trades_per_day=999,
        consistency_rule_pct=0.50,      # 50% consistency
        eval_max_days=60,
    ),
    # ── Tradeify / Lucid 25K ──────────────────────────────────────────────────
    "tradeify_lucid_25k": PropFirmProfile(
        name="Tradeify / Lucid 25K",
        account_size=25_000.0,
        profit_target=1_500.0,
        max_trailing_drawdown=1_500.0,
        trailing=True,                  # EOD Trailing
        daily_loss_limit=500.0,         # $500 Daily Loss Limit
        max_trades_per_day=999,
        consistency_rule_pct=0.35,      # 35% consistency
        eval_max_days=60,
    ),
}


def run_mes_25k_simulation(
    trades: pd.DataFrame,
    contracts: int,
    commission_per_contract_rt: float = 1.40,
    slippage_ticks: float = 1.0,
    profile_key: str = "tpt_25k",
    n_simulations: int = 5000,
) -> Dict:
    df = trades.copy()
    point_val = 5.0  # MES = $5.00 per point ($1.25 per tick)
    tick_val = 1.25  # MES tick = $1.25

    gross_dollar = df["points"] * point_val * contracts
    total_commission = commission_per_contract_rt * contracts
    total_slippage = (slippage_ticks * tick_val) * contracts
    net_dollar = gross_dollar - total_commission - total_slippage

    df["dollar_pnl"] = net_dollar
    profile = PROFILES_25K[profile_key]
    df["pnl_pct"] = (df["dollar_pnl"] / profile.account_size) * 100.0

    sim = PropFirmSimulator(account_size=profile.account_size, point_value=point_val)
    det = sim.run_deterministic(df, profile)
    mc = sim.run_monte_carlo(df, profile, n_simulations=n_simulations)

    # Average risk per trade in dollars: 5 bps stop on ES (~5500) = ~2.75 pts = $13.75 per contract
    avg_risk_dollar = contracts * 13.75

    return {
        "contracts": contracts,
        "profile": profile.name,
        "risk_per_trade": avg_risk_dollar,
        "total_trades": det.total_trades,
        "historical_passed": det.passed,
        "historical_max_dd": det.max_drawdown_used,
        "mc_pass_rate": mc.pass_rate_pct,
        "mc_blow_rate": mc.blow_rate_pct,
        "median_days": mc.median_days_to_pass,
        "avg_max_drawdown": mc.avg_max_drawdown,
        "grade": mc.grade,
        "net_dollar_per_trade": net_dollar.mean(),
        "win_rate": (net_dollar > 0).mean() * 100.0,
    }


def main():
    print(f"\n{'='*125}", flush=True)
    print("PROP FIRM EVALUATION: MICRO S&P (MES) ON 25K ACCOUNTS (APEX EOD, TPT, TRADEIFY, LUCID)", flush=True)
    print("=" * 125, flush=True)

    trades = run_cisd_strategy_mes(start_year=2022)

    # Overall Strategy Metrics on MES
    wr = trades["is_win"].mean() * 100.0
    wins = trades[trades["points"] > 0]["points"].sum()
    losses = abs(trades[trades["points"] < 0]["points"].sum())
    pf = wins / losses if losses > 0 else np.nan
    print(f"\nMES Native Performance: Win Rate = {wr:.1f}%, Profit Factor = {pf:.2f}, Total Trades = {len(trades):,d}", flush=True)

    profiles = ["apex_25k_eod", "apex_25k_legacy", "tpt_25k", "tradeify_lucid_25k"]
    contract_tiers = [2, 4, 6, 8]

    results = []
    for prof in profiles:
        for c in contract_tiers:
            res = run_mes_25k_simulation(
                trades,
                contracts=c,
                commission_per_contract_rt=1.40,
                slippage_ticks=1.0,
                profile_key=prof,
                n_simulations=5000,
            )
            results.append({
                "Challenge": res["profile"],
                "MES Sizing": f"{c} MES",
                "Risk / Trade ($)": f"${res['risk_per_trade']:.1f}",
                "Historical Pass": "YES" if res["historical_passed"] else "NO",
                "Historical Max DD": f"${res['historical_max_dd']:,.0f}",
                "MC Pass Rate (%)": f"{res['mc_pass_rate']:.1f}%",
                "MC Blowout (%)": f"{res['mc_blow_rate']:.1f}%",
                "Median Days": f"{res['median_days']:.0f} days" if res['median_days'] is not None and res['median_days'] > 0 else "N/A",
                "Avg Max Drawdown": f"${res['avg_max_drawdown']:,.0f}",
                "Prop Grade": res["grade"],
                "Net $/Trade": f"${res['net_dollar_per_trade']:+.2f}",
            })

    df_res = pd.DataFrame(results)
    print("\n" + "─" * 125, flush=True)
    print("🎯 25K PROP FIRM MATRIX: MICRO S&P (MES) ACROSS APEX (EOD & LEGACY), TPT & TRADEIFY/LUCID", flush=True)
    print("─" * 125, flush=True)
    print(df_res.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
