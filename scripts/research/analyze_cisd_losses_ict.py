"""
========================================================================================
ICT Institutional Post-Mortem: Diagnostic Loss Categorization on CISD Strategy
========================================================================================
Categorizes every losing trade across 5 institutional ICT dimensions:
1. Liquidity Sweep Source: Real External Sweep (PDH/PDL/Session H/L) vs. Internal Chop Trap
2. Time-of-Day / Killzone: Lunch Lull (12:00-13:30) vs Morning Macro vs Late AM Drift
3. Dealing Range Equilibrium: Buying in Premium / Selling in Discount (Wrong PD Array)
4. Counter-Trend vs. Pro-Trend HTF Delivery (Fighting 4H / Daily Orderflow)
5. FVG Invalidation / Inversion (CE 50% Breach & IFVG Flip)
========================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

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


def run_ict_loss_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    times = df.index
    opens = df["open"].to_numpy(dtype=np.float64)
    highs = df["high"].to_numpy(dtype=np.float64)
    lows = df["low"].to_numpy(dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    n = len(df)

    # 1. Calculate Daily High / Low & Midline (Equilibrium)
    df_daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_daily["pdh"] = df_daily["high"].shift(1)
    df_daily["pdl"] = df_daily["low"].shift(1)
    df_daily["pd_mid"] = (df_daily["pdh"] + df_daily["pdl"]) / 2.0
    daily_reindexed = df_daily.reindex(df.index, method="ffill")
    pdh_arr = daily_reindexed["pdh"].to_numpy()
    pdl_arr = daily_reindexed["pdl"].to_numpy()
    pdmid_arr = daily_reindexed["pd_mid"].to_numpy()

    # 2. Calculate 4H Trend / Delivery (HTF Bias)
    df_4h = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h["ema20"] = df_4h["close"].ewm(span=20).mean()
    df_4h_reindexed = df_4h.reindex(df.index, method="ffill")
    htf_bias_arr = np.where(df_4h_reindexed["close"] > df_4h_reindexed["ema20"], 1, -1)

    time_strs = times.strftime("%H%M")
    hours = times.hour
    mins = times.minute

    # Tracking Sessions
    cur_asia_h, cur_asia_l = np.nan, np.nan
    cur_lon_h, cur_lon_l = np.nan, np.nan
    last_asia_h, last_asia_l = np.nan, np.nan
    last_lon_h, last_lon_l = np.nan, np.nan

    vibes = 0
    bagholder_entry = np.nan
    pain_threshold = np.nan

    def consult_crystal_ball(bias: int, idx: int):
        max_lb = min(15, idx)
        ext_o = opens[idx - 1]
        for k in range(1, max_lb + 1):
            is_opp = (closes[idx - k] < opens[idx - k]) if bias == 1 else (closes[idx - k] > opens[idx - k])
            if is_opp:
                ext_o = opens[idx - k]
                break
        return ext_o

    trades = []
    in_pos = False
    pos_dir = 0
    pos_entry_price = 0.0
    pos_entry_time = None
    pos_entry_idx = 0
    active_sl = 0.0
    active_tp1 = 0.0
    active_tp2 = 0.0
    queen_filled = False
    sweep_type = "None"
    was_in_premium = False
    htf_aligned = True

    pending_order = None

    for i in range(25, n):
        t = times[i]
        hhmm = time_strs[i]
        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h2, l2 = highs[i - 2], lows[i - 2]
        hh = hours[i]
        mm = mins[i]

        # Track Asian Session (18:00 - 02:00)
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
                if hhmm >= "1555":
                    q_pnl = (active_tp1 - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                    r_pnl = (c0 - pos_entry_price)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": c0, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "exit_reason": "EOD Flat", "sweep_type": sweep_type,
                        "was_in_premium": was_in_premium, "htf_aligned": htf_aligned, "entry_hhmm": pos_entry_time.strftime("%H:%M"),
                    })
                    in_pos = False

                elif l0 <= active_sl:
                    q_pnl = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                    r_pnl = (active_sl - pos_entry_price)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "exit_reason": "Stop Loss", "sweep_type": sweep_type,
                        "was_in_premium": was_in_premium, "htf_aligned": htf_aligned, "entry_hhmm": pos_entry_time.strftime("%H:%M"),
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
                        "is_win": True, "exit_reason": "Runner TP2", "sweep_type": sweep_type,
                        "was_in_premium": was_in_premium, "htf_aligned": htf_aligned, "entry_hhmm": pos_entry_time.strftime("%H:%M"),
                    })
                    in_pos = False

            elif pos_dir == -1:
                if hhmm >= "1555":
                    q_pnl = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                    r_pnl = (pos_entry_price - c0)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": c0, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "exit_reason": "EOD Flat", "sweep_type": sweep_type,
                        "was_in_premium": was_in_premium, "htf_aligned": htf_aligned, "entry_hhmm": pos_entry_time.strftime("%H:%M"),
                    })
                    in_pos = False

                elif h0 >= active_sl:
                    q_pnl = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                    r_pnl = (pos_entry_price - active_sl)
                    pnl_bps = ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_sl, "pnl_bps": pnl_bps,
                        "is_win": pnl_bps > 0, "exit_reason": "Stop Loss", "sweep_type": sweep_type,
                        "was_in_premium": was_in_premium, "htf_aligned": htf_aligned, "entry_hhmm": pos_entry_time.strftime("%H:%M"),
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
                        "is_win": True, "exit_reason": "Runner TP2", "sweep_type": sweep_type,
                        "was_in_premium": was_in_premium, "htf_aligned": htf_aligned, "entry_hhmm": pos_entry_time.strftime("%H:%M"),
                    })
                    in_pos = False

        # -------------------------------------------------------------
        # 2. PENDING FVG LIMIT EVALUATION
        # -------------------------------------------------------------
        if pending_order is not None and not in_pos:
            p_dir = pending_order["dir"]
            p_limit = pending_order["limit"]
            p_sl = pending_order["sl"]
            p_bar = pending_order["bar"]

            if (i - p_bar) <= 6:
                if "0945" <= hhmm <= "1530":
                    if p_dir == 1 and l0 <= p_limit:
                        in_pos = True
                        pos_dir = 1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        pos_entry_idx = i
                        active_sl = p_sl
                        active_tp1 = p_limit + (p_limit * 0.0010)
                        active_tp2 = p_limit + (p_limit * 0.0030)
                        queen_filled = False
                        sweep_type = pending_order["sweep_type"]
                        was_in_premium = pending_order["was_in_prem"]
                        htf_aligned = pending_order["htf_aligned"]
                        pending_order = None

                    elif p_dir == -1 and h0 >= p_limit:
                        in_pos = True
                        pos_dir = -1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        pos_entry_idx = i
                        active_sl = p_sl
                        active_tp1 = p_limit - (p_limit * 0.0010)
                        active_tp2 = p_limit - (p_limit * 0.0030)
                        queen_filled = False
                        sweep_type = pending_order["sweep_type"]
                        was_in_premium = pending_order["was_in_prem"]
                        htf_aligned = pending_order["htf_aligned"]
                        pending_order = None
            else:
                pending_order = None

        # -------------------------------------------------------------
        # 3. CISD EVALUATION & CONTEXT ANNOTATION
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

        # Detect Sweeps preceding the CISD (lookback 5 bars)
        cur_sweep = "Internal Chop (No Sweep)"
        recent_low = min(lows[i-5:i+1])
        recent_high = max(highs[i-5:i+1])

        if not np.isnan(pdl_arr[i]) and recent_low < pdl_arr[i]:
            cur_sweep = "PDL Sweep"
        elif not np.isnan(pdh_arr[i]) and recent_high > pdh_arr[i]:
            cur_sweep = "PDH Sweep"
        elif not np.isnan(last_lon_l) and recent_low < last_lon_l:
            cur_sweep = "London Low Sweep"
        elif not np.isnan(last_lon_h) and recent_high > last_lon_h:
            cur_sweep = "London High Sweep"
        elif not np.isnan(last_asia_l) and recent_low < last_asia_l:
            cur_sweep = "Asia Low Sweep"
        elif not np.isnan(last_asia_h) and recent_high > last_asia_h:
            cur_sweep = "Asia High Sweep"

        # Bullish CISD
        if vibes == -1 and c0 > active_lvl:
            vibes = 1
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)
            fvg_top = h2 if l0 > h2 else active_lvl
            sl_price = fvg_top - (fvg_top * 0.0005)  # 5 bps FVG Stop

            # Is price in Premium relative to Prev Day Range?
            is_prem = not np.isnan(pdmid_arr[i]) and (c0 > pdmid_arr[i])
            is_htf = (htf_bias_arr[i] == 1)

            pending_order = {
                "dir": 1, "limit": fvg_top, "sl": sl_price, "bar": i,
                "sweep_type": cur_sweep, "was_in_prem": is_prem, "htf_aligned": is_htf,
            }

        # Bearish CISD
        elif vibes == 1 and c0 < active_lvl:
            vibes = -1
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)
            fvg_bot = l2 if h0 < l2 else active_lvl
            sl_price = fvg_bot + (fvg_bot * 0.0005)

            is_disc = not np.isnan(pdmid_arr[i]) and (c0 < pdmid_arr[i])
            is_htf = (htf_bias_arr[i] == -1)

            pending_order = {
                "dir": -1, "limit": fvg_bot, "sl": sl_price, "bar": i,
                "sweep_type": cur_sweep, "was_in_prem": is_disc, "htf_aligned": is_htf,
            }

    return pd.DataFrame(trades)


def main():
    print(f"\n{'='*100}", flush=True)
    print("ICT INSTITUTIONAL POST-MORTEM: CATEGORIZING CISD LOSSES (334,414 BARS / 2022-2026)", flush=True)
    print("=" * 100, flush=True)

    data_path = _root / "data/NQ1_5m.parquet"
    df = pd.read_parquet(data_path)
    trades = run_ict_loss_diagnostics(df)

    losses = trades[~trades["is_win"]].copy()
    wins = trades[trades["is_win"]].copy()

    print(f"\nTotal Trades Evaluated : {len(trades):,d}", flush=True)
    print(f"Total Winning Trades   : {len(wins):,d} ({len(wins)/len(trades)*100:.1f}%)", flush=True)
    print(f"Total Losing Trades    : {len(losses):,d} ({len(losses)/len(trades)*100:.1f}%)", flush=True)

    # -------------------------------------------------------------
    # CATEGORY 1: LIQUIDITY SWEEP CONTEXT (The #1 ICT Root Cause)
    # -------------------------------------------------------------
    print("\n" + "─" * 100, flush=True)
    print("🏛️ CATEGORY 1: PRECEDING LIQUIDITY CONTEXT (External Sweep vs Internal Chop Trap)", flush=True)
    print("─" * 100, flush=True)

    sweep_group = trades.groupby("sweep_type").agg(
        Total_Trades=("pnl_bps", "count"),
        Wins=("is_win", "sum"),
        Losses=("is_win", lambda x: (x == False).sum()),
        Win_Rate=("is_win", lambda x: x.mean() * 100.0),
        Net_Bps=("pnl_bps", "sum"),
        Exp_Bps=("pnl_bps", "mean"),
    )
    sweep_group["Loss_Share_%"] = (sweep_group["Losses"] / len(losses)) * 100.0
    print(sweep_group.sort_values(by="Losses", ascending=False).to_string(), flush=True)

    # -------------------------------------------------------------
    # CATEGORY 2: TIME-OF-DAY / KILLZONE BREAKDOWN
    # -------------------------------------------------------------
    print("\n" + "─" * 100, flush=True)
    print("⏰ CATEGORY 2: TIME-OF-DAY & ICT KILLZONE WINDOWS", flush=True)
    print("─" * 100, flush=True)

    def classify_kz(hhmm_str):
        hm = int(hhmm_str.replace(":", ""))
        if 945 <= hm <= 1100:
            return "1. NY AM Killzone (09:45-11:00)"
        elif 1100 < hm <= 1200:
            return "2. Late NY AM Drift (11:00-12:00)"
        elif 1200 < hm <= 1330:
            return "3. NY Lunch Lull (12:00-13:30) 🛑"
        elif 1330 < hm <= 1530:
            return "4. NY PM Expansion (13:30-15:30) 💎"
        else:
            return "5. Other / EOD"

    trades["killzone"] = trades["entry_hhmm"].apply(classify_kz)
    kz_group = trades.groupby("killzone").agg(
        Total_Trades=("pnl_bps", "count"),
        Wins=("is_win", "sum"),
        Losses=("is_win", lambda x: (x == False).sum()),
        Win_Rate=("is_win", lambda x: x.mean() * 100.0),
        Net_Bps=("pnl_bps", "sum"),
        Exp_Bps=("pnl_bps", "mean"),
    )
    kz_group["Loss_Share_%"] = (kz_group["Losses"] / len(losses)) * 100.0
    print(kz_group.to_string(), flush=True)

    # -------------------------------------------------------------
    # CATEGORY 3: PREMIUM VS DISCOUNT VIOLATION (PD ARRAY TRAP)
    # -------------------------------------------------------------
    print("\n" + "─" * 100, flush=True)
    print("⚖️ CATEGORY 3: DEALING RANGE EQUILIBRIUM (Buying in Premium / Selling in Discount)", flush=True)
    print("─" * 100, flush=True)

    pd_group = trades.groupby("was_in_premium").agg(
        Total_Trades=("pnl_bps", "count"),
        Wins=("is_win", "sum"),
        Losses=("is_win", lambda x: (x == False).sum()),
        Win_Rate=("is_win", lambda x: x.mean() * 100.0),
        Net_Bps=("pnl_bps", "sum"),
        Exp_Bps=("pnl_bps", "mean"),
    )
    pd_group.index = ["Discount Buying / Premium Selling (Proper)", "Premium Buying / Discount Selling (VIOLATION)"]
    pd_group["Loss_Share_%"] = (pd_group["Losses"] / len(losses)) * 100.0
    print(pd_group.to_string(), flush=True)

    # -------------------------------------------------------------
    # CATEGORY 4: HIGHER TIMEFRAME (HTF) ORDERFLOW ALIGNMENT
    # -------------------------------------------------------------
    print("\n" + "─" * 100, flush=True)
    print("🌊 CATEGORY 4: HTF 4-HOUR ORDERFLOW & BIAS ALIGNMENT", flush=True)
    print("─" * 100, flush=True)

    htf_group = trades.groupby("htf_aligned").agg(
        Total_Trades=("pnl_bps", "count"),
        Wins=("is_win", "sum"),
        Losses=("is_win", lambda x: (x == False).sum()),
        Win_Rate=("is_win", lambda x: x.mean() * 100.0),
        Net_Bps=("pnl_bps", "sum"),
        Exp_Bps=("pnl_bps", "mean"),
    )
    htf_group.index = ["Counter-Trend (Fighting 4H Orderflow)", "Pro-Trend (Aligned with 4H Orderflow)"]
    htf_group["Loss_Share_%"] = (htf_group["Losses"] / len(losses)) * 100.0
    print(htf_group.to_string(), flush=True)


if __name__ == "__main__":
    main()
