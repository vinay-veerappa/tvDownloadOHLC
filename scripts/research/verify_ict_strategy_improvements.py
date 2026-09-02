"""
========================================================================================
Institutional ICT Strategy Review & Empirical Verification Engine (2022-2026)
========================================================================================
Tests 5 advanced ICT concepts to improve the CISD / FVG strategy:
1. Power of 3 (PO3) / Midnight Open (NMO) & 08:30 Open Gate (Discount Buying / Premium Selling)
2. Intermarket SMT Divergence (NQ vs ES at the sweep)
3. Draw on Liquidity (DOL) Clearance Room (LRLR vs HRLR)
4. ICT Macros & Silver Bullet Timing Windows (09:50-10:10, 10:00-11:00, 14:00-15:00)
5. Combined Institutional Alpha Stack
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


def load_and_prepare_data(start_year: int = 2022) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load NQ and ES 5m data, synchronize timestamps, and convert to America/New_York."""
    print("Loading NQ1 and ES1 5m parquet data...", flush=True)
    nq_path = _root / "data/NQ1_5m.parquet"
    es_path = _root / "data/ES1_5m.parquet"

    df_nq = pd.read_parquet(nq_path)
    df_es = pd.read_parquet(es_path)

    # Filter to start_year onwards
    df_nq = df_nq[df_nq.index >= f"{start_year}-01-01"].copy()
    df_es = df_es[df_es.index >= f"{start_year}-01-01"].copy()

    # Timezone conversion to America/New_York
    if df_nq.index.tz is None:
        df_nq.index = df_nq.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_nq.index = df_nq.index.tz_convert("America/New_York")

    if df_es.index.tz is None:
        df_es.index = df_es.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_es.index = df_es.index.tz_convert("America/New_York")

    # Align timestamps
    common_idx = df_nq.index.intersection(df_es.index)
    df_nq = df_nq.loc[common_idx].sort_index()
    df_es = df_es.loc[common_idx].sort_index()

    print(f"Data synchronized: {len(common_idx):,d} bars ({common_idx[0].strftime('%Y-%m-%d')} to {common_idx[-1].strftime('%Y-%m-%d')})", flush=True)
    return df_nq, df_es


def run_ict_simulation(
    df_nq: pd.DataFrame,
    df_es: pd.DataFrame,
    use_4h_filter: bool = True,
    filter_lunch: bool = True,
    use_po3_midnight_open: bool = False,
    require_smt: bool = False,
    min_dol_clearance_bps: float = 0.0,
    restrict_to_macros_sb: bool = False,
    queen_bps: float = 10.0,
    runner_bps: float = 30.0,
    stop_bps: float = 5.0,
) -> pd.DataFrame:
    times = df_nq.index
    n = len(df_nq)

    # NQ Series
    nq_o = df_nq["open"].to_numpy(dtype=np.float64)
    nq_h = df_nq["high"].to_numpy(dtype=np.float64)
    nq_l = df_nq["low"].to_numpy(dtype=np.float64)
    nq_c = df_nq["close"].to_numpy(dtype=np.float64)

    # ES Series (for SMT)
    es_h = df_es["high"].to_numpy(dtype=np.float64)
    es_l = df_es["low"].to_numpy(dtype=np.float64)

    # 1. 4H Trend / Delivery (HTF Bias)
    df_4h = df_nq.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["ema20"] = df_4h["close"].ewm(span=20).mean()
    df_4h_reindexed = df_4h.reindex(df_nq.index, method="ffill")
    htf_bias_arr = np.where(df_4h_reindexed["close"] > df_4h_reindexed["ema20"], 1, -1)

    # 2. Daily Reference Levels (PDH, PDL, PDM)
    df_daily = df_nq.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_daily["pdh"] = df_daily["high"].shift(1)
    df_daily["pdl"] = df_daily["low"].shift(1)
    df_daily["pd_mid"] = (df_daily["pdh"] + df_daily["pdl"]) / 2.0
    daily_reindexed = df_daily.reindex(df_nq.index, method="ffill")
    pdh_arr = daily_reindexed["pdh"].to_numpy()
    pdl_arr = daily_reindexed["pdl"].to_numpy()
    pdmid_arr = daily_reindexed["pd_mid"].to_numpy()

    time_strs = times.strftime("%H%M")
    hours = times.hour
    mins = times.minute

    # Tracking Session Opens & H/L
    midnight_open = np.nan
    open_0830 = np.nan
    cur_day = None

    cur_asia_h, cur_asia_l = np.nan, np.nan
    cur_lon_h, cur_lon_l = np.nan, np.nan
    last_asia_h, last_asia_l = np.nan, np.nan
    last_lon_h, last_lon_l = np.nan, np.nan

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
    pos_mfe = 0.0
    pos_mae = 0.0

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

        # Day Boundary & Session Opens
        if bar_date != cur_day:
            cur_day = bar_date
            daily_trades = 0
            pending_order = None

        # Midnight Open (00:00 ET)
        if hh == 0 and mm == 0:
            midnight_open = o0

        # 08:30 Open
        if hh == 8 and mm == 30:
            open_0830 = o0

        # Track Sessions
        if hh == 18 and mm == 0:
            cur_asia_h, cur_asia_l = h0, l0
        elif (hh >= 18 or hh < 2):
            cur_asia_h = max(cur_asia_h, h0) if not np.isnan(cur_asia_h) else h0
            cur_asia_l = min(cur_asia_l, l0) if not np.isnan(cur_asia_l) else l0
        elif hh == 2 and mm == 0:
            last_asia_h, last_asia_l = cur_asia_h, cur_asia_l
            cur_lon_h, cur_lon_l = h0, l0
        elif (2 <= hh < 8):
            cur_lon_h = max(cur_lon_h, h0) if not np.isnan(cur_lon_h) else h0
            cur_lon_l = min(cur_lon_l, l0) if not np.isnan(cur_lon_l) else l0
        elif hh == 8 and mm == 0:
            last_lon_h, last_lon_l = cur_lon_h, cur_lon_l

        # -------------------------------------------------------------
        # 1. POSITION MANAGEMENT
        # -------------------------------------------------------------
        if in_pos:
            if pos_dir == 1:
                pos_mfe = max(pos_mfe, (h0 - pos_entry_price) / pos_entry_price * 10000.0)
                pos_mae = max(pos_mae, (pos_entry_price - l0) / pos_entry_price * 10000.0)

                if hhmm >= "1555":
                    q_pnl = (active_tp1 - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                    r_pnl = (c0 - pos_entry_price)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": c0, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "queen_hit": queen_filled, "runner_hit": False,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif l0 <= active_sl:
                    q_pnl = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                    r_pnl = (active_sl - pos_entry_price)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "queen_hit": queen_filled, "runner_hit": False,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif not queen_filled and h0 >= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price  # BE Lock

                elif h0 >= active_tp2:
                    q_pnl = (active_tp1 - pos_entry_price)
                    r_pnl = (active_tp2 - pos_entry_price)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_tp2, "pnl_bps": pnl_bps,
                        "is_win": True, "queen_hit": True, "runner_hit": True,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

            elif pos_dir == -1:
                pos_mfe = max(pos_mfe, (pos_entry_price - l0) / pos_entry_price * 10000.0)
                pos_mae = max(pos_mae, (h0 - pos_entry_price) / pos_entry_price * 10000.0)

                if hhmm >= "1555":
                    q_pnl = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                    r_pnl = (pos_entry_price - c0)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": c0, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "queen_hit": queen_filled, "runner_hit": False,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif h0 >= active_sl:
                    q_pnl = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                    r_pnl = (pos_entry_price - active_sl)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "queen_hit": queen_filled, "runner_hit": False,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif not queen_filled and l0 <= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price

                elif l0 <= active_tp2:
                    q_pnl = (pos_entry_price - active_tp1)
                    r_pnl = (pos_entry_price - active_tp2)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_tp2, "pnl_bps": pnl_bps,
                        "is_win": True, "queen_hit": True, "runner_hit": True,
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

        # -------------------------------------------------------------
        # 2. PENDING FVG LIMIT ORDER EVALUATION
        # -------------------------------------------------------------
        if pending_order is not None and not in_pos:
            p_dir = pending_order["dir"]
            p_limit = pending_order["limit"]
            p_sl = pending_order["sl"]
            p_bar = pending_order["bar"]

            if (i - p_bar) <= 6:
                in_time = ("0945" <= hhmm <= "1530")
                if filter_lunch and ("1200" <= hhmm <= "1330"):
                    in_time = False

                # ICT Macro / Silver Bullet filter
                if restrict_to_macros_sb:
                    is_sb_am = ("1000" <= hhmm <= "1100")
                    is_sb_pm = ("1400" <= hhmm <= "1500")
                    is_macro_am = ("0950" <= hhmm <= "1010")
                    is_macro_mid = ("1050" <= hhmm <= "1110")
                    is_macro_pm = ("1515" <= hhmm <= "1545")
                    if not (is_sb_am or is_sb_pm or is_macro_am or is_macro_mid or is_macro_pm):
                        in_time = False

                if in_time and daily_trades < 5:
                    if p_dir == 1 and l0 <= p_limit:
                        in_pos = True
                        pos_dir = 1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        active_sl = p_sl
                        active_tp1 = p_limit + (p_limit * (queen_bps / 10000.0))
                        active_tp2 = p_limit + (p_limit * (runner_bps / 10000.0))
                        queen_filled = False
                        pos_mfe = max(0.0, (h0 - pos_entry_price) / pos_entry_price * 10000.0)
                        pos_mae = max(0.0, (pos_entry_price - l0) / pos_entry_price * 10000.0)
                        daily_trades += 1
                        pending_order = None

                    elif p_dir == -1 and h0 >= p_limit:
                        in_pos = True
                        pos_dir = -1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        active_sl = p_sl
                        active_tp1 = p_limit - (p_limit * (queen_bps / 10000.0))
                        active_tp2 = p_limit - (p_limit * (runner_bps / 10000.0))
                        queen_filled = False
                        pos_mfe = max(0.0, (pos_entry_price - l0) / pos_entry_price * 10000.0)
                        pos_mae = max(0.0, (h0 - pos_entry_price) / pos_entry_price * 10000.0)
                        daily_trades += 1
                        pending_order = None
            else:
                pending_order = None

        # -------------------------------------------------------------
        # 3. CISD SIGNAL EVALUATION
        # -------------------------------------------------------------
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

        # SMT Divergence Detection (NQ vs ES at recent swing low/high in last 5 bars)
        # Bullish SMT: NQ made Lower Low while ES made Higher Low (or vice versa)
        nq_recent_l = min(nq_l[i-4:i+1])
        nq_prev_l = min(nq_l[i-10:i-4])
        es_recent_l = min(es_l[i-4:i+1])
        es_prev_l = min(es_l[i-10:i-4])

        nq_made_ll = (nq_recent_l < nq_prev_l)
        es_made_ll = (es_recent_l < es_prev_l)
        bullish_smt = (nq_made_ll and not es_made_ll) or (not nq_made_ll and es_made_ll)

        # Bearish SMT: NQ made Higher High while ES made Lower High (or vice versa)
        nq_recent_h = max(nq_h[i-4:i+1])
        nq_prev_h = max(nq_h[i-10:i-4])
        es_recent_h = max(es_h[i-4:i+1])
        es_prev_h = max(es_h[i-10:i-4])

        nq_made_hh = (nq_recent_h > nq_prev_h)
        es_made_hh = (es_recent_h > es_prev_h)
        bearish_smt = (nq_made_hh and not es_made_hh) or (not nq_made_hh and es_made_hh)

        # Draw on Liquidity (DOL) Clearance Calculation
        # For Long: distance to nearest opposing high (PDH or London High) in bps
        opp_targets_long = [lvl for lvl in [pdh_arr[i], last_lon_h] if not np.isnan(lvl) and lvl > c0]
        nearest_dol_long_bps = min([(lvl - c0) / c0 * 10000.0 for lvl in opp_targets_long]) if len(opp_targets_long) > 0 else 999.0

        # For Short: distance to nearest opposing low (PDL or London Low) in bps
        opp_targets_short = [lvl for lvl in [pdl_arr[i], last_lon_l] if not np.isnan(lvl) and lvl < c0]
        nearest_dol_short_bps = min([(c0 - lvl) / c0 * 10000.0 for lvl in opp_targets_short]) if len(opp_targets_short) > 0 else 999.0

        # Bullish CISD
        if vibes == -1 and c0 > active_lvl:
            vibes = 1
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)

            allow_signal = True
            # 1. 4H Trend
            if use_4h_filter and htf_bias_arr[i] != 1:
                allow_signal = False
            # 2. Power of 3 (PO3): Long only in Discount (<= Midnight Open or <= 08:30 Open)
            if use_po3_midnight_open:
                ref_open = midnight_open if not np.isnan(midnight_open) else open_0830
                if not np.isnan(ref_open) and c0 > ref_open:
                    allow_signal = False
            # 3. SMT Divergence
            if require_smt and not bullish_smt:
                allow_signal = False
            # 4. DOL Clearance Room
            if min_dol_clearance_bps > 0 and nearest_dol_long_bps < min_dol_clearance_bps:
                allow_signal = False

            if allow_signal:
                fvg_top = h2 if l0 > h2 else active_lvl
                sl_price = fvg_top - (fvg_top * (stop_bps / 10000.0))
                pending_order = {"dir": 1, "limit": fvg_top, "sl": sl_price, "bar": i}

        # Bearish CISD
        elif vibes == 1 and c0 < active_lvl:
            vibes = -1
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)

            allow_signal = True
            if use_4h_filter and htf_bias_arr[i] != -1:
                allow_signal = False
            if use_po3_midnight_open:
                ref_open = midnight_open if not np.isnan(midnight_open) else open_0830
                if not np.isnan(ref_open) and c0 < ref_open:
                    allow_signal = False
            if require_smt and not bearish_smt:
                allow_signal = False
            if min_dol_clearance_bps > 0 and nearest_dol_short_bps < min_dol_clearance_bps:
                allow_signal = False

            if allow_signal:
                fvg_bot = l2 if h0 < l2 else active_lvl
                sl_price = fvg_bot + (fvg_bot * (stop_bps / 10000.0))
                pending_order = {"dir": -1, "limit": fvg_bot, "sl": sl_price, "bar": i}

    return pd.DataFrame(trades)


def main():
    print(f"\n{'='*115}", flush=True)
    print("EMPIRICAL ICT CONCEPT TESTING & VERIFICATION (2022-2026 / 334,414 BARS)", flush=True)
    print("=" * 115, flush=True)

    df_nq, df_es = load_and_prepare_data(start_year=2022)

    # Define the matrix of ICT Concepts to test
    experiments = [
        {
            "name": "1. Current Upgraded Baseline (4H Bias + Lunch Blackout + 09:45 Filter)",
            "4h": True, "lunch": True, "po3": False, "smt": False, "dol": 0.0, "macros": False,
        },
        {
            "name": "2. + Power of 3 (PO3) Midnight Open Filter (Buy in Discount / Sell in Prem)",
            "4h": True, "lunch": True, "po3": True, "smt": False, "dol": 0.0, "macros": False,
        },
        {
            "name": "3. + Intermarket SMT Divergence (NQ vs ES at Sweep)",
            "4h": True, "lunch": True, "po3": False, "smt": True, "dol": 0.0, "macros": False,
        },
        {
            "name": "4. + Draw on Liquidity (DOL) Clearance Gate (Room >= 25 bps)",
            "4h": True, "lunch": True, "po3": False, "smt": False, "dol": 25.0, "macros": False,
        },
        {
            "name": "5. + ICT Macros & Silver Bullet Windows Only (09:50-10:10, 10-11, 14-15)",
            "4h": True, "lunch": True, "po3": False, "smt": False, "dol": 0.0, "macros": True,
        },
        {
            "name": "6. Full Institutional Master Model (PO3 + SMT + DOL Clearance)",
            "4h": True, "lunch": True, "po3": True, "smt": True, "dol": 25.0, "macros": False,
        },
    ]

    results = []
    for exp in experiments:
        trades = run_ict_simulation(
            df_nq, df_es,
            use_4h_filter=exp["4h"],
            filter_lunch=exp["lunch"],
            use_po3_midnight_open=exp["po3"],
            require_smt=exp["smt"],
            min_dol_clearance_bps=exp["dol"],
            restrict_to_macros_sb=exp["macros"],
        )
        if len(trades) == 0:
            continue

        wins = trades[trades["pnl_bps"] > 0]
        losses = trades[trades["pnl_bps"] < 0]
        gp = wins["pnl_bps"].sum()
        gl = abs(losses["pnl_bps"].sum())
        pf = gp / gl if gl > 0 else np.nan
        wr = len(wins) / len(trades) * 100.0
        queen_reach = trades["queen_hit"].mean() * 100.0
        runner_reach = trades["runner_hit"].mean() * 100.0
        net_bps = trades["pnl_bps"].sum()
        exp_bps = trades["pnl_bps"].mean()
        approx_net_usd = net_bps * 36.0  # 1 NQ contract (~$36/bps)

        results.append({
            "Experiment": exp["name"],
            "Trades": len(trades),
            "Win Rate": f"{wr:.1f}%",
            "Profit Factor": f"{pf:.2f}",
            "Queen (+10bps) %": f"{queen_reach:.1f}%",
            "Runner (+30bps) %": f"{runner_reach:.1f}%",
            "Net Alpha (bps)": f"{net_bps:+,.1f} bps",
            "Expectancy": f"{exp_bps:+,.2f} bps/tr",
            "Approx P&L ($)": f"${approx_net_usd:+,.0f}",
        })

    print("\n" + "─" * 115, flush=True)
    print("📊 EMPIRICAL VERIFICATION SCORECARD ACROSS ICT ADVANCED CONCEPTS", flush=True)
    print("─" * 115, flush=True)
    print(pd.DataFrame(results).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
