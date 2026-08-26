"""
========================================================================================
Empirical Study: FVG Limit vs. Market Entry & 09:30-09:45 Judas Window Filter
========================================================================================
Analyzes:
1. Entry Order Types: Market on Break vs FVG Limit Touch vs FVG 50% C.E. Retest
2. Time-of-Day Filter: 09:30-09:45 Open Trap Filter (Turnaround 09:45-10:00)
3. Stop Loss Anchors: 5.0 bps FVG Stop vs Structural SL-4 Origin
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


def run_cisd_simulation(
    df: pd.DataFrame,
    entry_mechanism: str = "Market",     # "Market", "FVG_Touch", "FVG_CE50"
    start_hhmm: str = "0945",            # "0930" or "0945"
    end_hhmm: str = "1530",
    stop_mode: str = "SL_5bps",          # "SL_5bps", "SL_Structural", "SL_8bps", "SL_12bps"
    queen_bps: float = 10.0,
    runner_bps: float = 30.0,
    max_wait_bars: int = 6,              # Max bars to wait for limit retest
) -> pd.DataFrame:
    times = df.index
    opens = df["open"].to_numpy(dtype=np.float64)
    highs = df["high"].to_numpy(dtype=np.float64)
    lows = df["low"].to_numpy(dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    n = len(df)
    time_strs = times.strftime("%H%M")

    vibes = 0
    bagholder_entry = np.nan
    pain_threshold = np.nan
    delivery_origin_l = np.nan
    delivery_origin_h = np.nan

    def consult_crystal_ball(bias: int, idx: int):
        max_lb = min(15, idx)
        ext_o = opens[idx - 1]
        ext_orig = lows[idx - 1] if bias == 1 else highs[idx - 1]
        for k in range(1, max_lb + 1):
            is_opp = (closes[idx - k] < opens[idx - k]) if bias == 1 else (closes[idx - k] > opens[idx - k])
            if is_opp:
                ext_o = opens[idx - k]
                break
        for k in range(1, min(10, idx)):
            if bias == 1 and lows[idx - k] < ext_orig:
                ext_orig = lows[idx - k]
            if bias == -1 and highs[idx - k] > ext_orig:
                ext_orig = highs[idx - k]
        return ext_o, ext_orig

    trades = []
    trade_count = 0

    in_pos = False
    pos_dir = 0
    pos_entry_time = None
    pos_entry_price = 0.0
    active_sl = 0.0
    active_tp1 = 0.0
    active_tp2 = 0.0
    queen_filled = False
    pos_mfe = 0.0
    pos_mae = 0.0

    current_day = None
    daily_trades = 0

    pending_order = None  # {dir, limit_price, sl_price, armed_bar, armed_time}

    for i in range(25, n):
        t = times[i]
        hhmm = time_strs[i]
        bar_date = t.date()
        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h2, l2 = highs[i - 2], lows[i - 2]

        if bar_date != current_day:
            current_day = bar_date
            daily_trades = 0
            pending_order = None

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
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": c0,
                        "pnl_bps": ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0,
                        "queen_hit": queen_filled, "runner_hit": False, "exit_reason": "EOD Flat",
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif l0 <= active_sl:
                    q_pnl = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                    r_pnl = (active_sl - pos_entry_price)
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_sl,
                        "pnl_bps": ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0,
                        "queen_hit": queen_filled, "runner_hit": False, "exit_reason": "Stop Loss",
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif not queen_filled and h0 >= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price  # BE Lock

                elif h0 >= active_tp2:
                    q_pnl = (active_tp1 - pos_entry_price)
                    r_pnl = (active_tp2 - pos_entry_price)
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_tp2,
                        "pnl_bps": ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0,
                        "queen_hit": True, "runner_hit": True, "exit_reason": "Runner TP2",
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

            elif pos_dir == -1:
                pos_mfe = max(pos_mfe, (pos_entry_price - l0) / pos_entry_price * 10000.0)
                pos_mae = max(pos_mae, (h0 - pos_entry_price) / pos_entry_price * 10000.0)

                if hhmm >= "1555":
                    q_pnl = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                    r_pnl = (pos_entry_price - c0)
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": c0,
                        "pnl_bps": ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0,
                        "queen_hit": queen_filled, "runner_hit": False, "exit_reason": "EOD Flat",
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif h0 >= active_sl:
                    q_pnl = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                    r_pnl = (pos_entry_price - active_sl)
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_sl,
                        "pnl_bps": ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0,
                        "queen_hit": queen_filled, "runner_hit": False, "exit_reason": "Stop Loss",
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

                elif not queen_filled and l0 <= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price

                elif l0 <= active_tp2:
                    q_pnl = (pos_entry_price - active_tp1)
                    r_pnl = (pos_entry_price - active_tp2)
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_tp2,
                        "pnl_bps": ((q_pnl + r_pnl) / 2.0) / pos_entry_price * 10000.0,
                        "queen_hit": True, "runner_hit": True, "exit_reason": "Runner TP2",
                        "mfe_bps": pos_mfe, "mae_bps": pos_mae,
                    })
                    in_pos = False

        # -------------------------------------------------------------
        # 2. PENDING LIMIT ORDER EVALUATION
        # -------------------------------------------------------------
        if pending_order is not None and not in_pos:
            p_dir = pending_order["dir"]
            p_limit = pending_order["limit_price"]
            p_sl = pending_order["sl_price"]
            p_bar = pending_order["bar"]

            if (i - p_bar) <= max_wait_bars:
                in_window = (start_hhmm <= hhmm <= end_hhmm)
                if in_window and daily_trades < 5:
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
            bagholder_entry, delivery_origin_l = consult_crystal_ball(vibes, i)
            pain_threshold = h0 if vibes == 1 else l0
            delivery_origin_h = delivery_origin_l

        if vibes == 1 and h0 > pain_threshold:
            pain_threshold = h0
            bagholder_entry, delivery_origin_l = consult_crystal_ball(1, i)
        elif vibes == -1 and l0 < pain_threshold:
            pain_threshold = l0
            bagholder_entry, delivery_origin_h = consult_crystal_ball(-1, i)

        active_lvl = bagholder_entry

        # Bullish CISD
        if vibes == -1 and c0 > active_lvl:
            vibes = 1
            pain_threshold = h0
            bagholder_entry, delivery_origin_l = consult_crystal_ball(1, i)

            # Determine Stop Loss
            if stop_mode == "SL_5bps":
                sl_price = c0 - (c0 * 0.0005)  # 5 bps Stop
            elif stop_mode == "SL_8bps":
                sl_price = c0 - (c0 * 0.0008)  # 8 bps Stop
            elif stop_mode == "SL_12bps":
                sl_price = c0 - (c0 * 0.0012)  # 12 bps Stop
            else:
                sl_price = min(delivery_origin_l, min(lows[i-4:i+1]))

            # Determine Entry Mechanism
            if entry_mechanism == "Market":
                if not in_pos and (start_hhmm <= hhmm <= end_hhmm) and (daily_trades < 5):
                    in_pos = True
                    pos_dir = 1
                    pos_entry_time = t
                    pos_entry_price = c0
                    active_sl = sl_price
                    active_tp1 = c0 + (c0 * (queen_bps / 10000.0))
                    active_tp2 = c0 + (c0 * (runner_bps / 10000.0))
                    queen_filled = False
                    pos_mfe = 0.0
                    pos_mae = 0.0
                    daily_trades += 1
            elif entry_mechanism == "FVG_Touch":
                # FVG Top boundary is h2 if bull FVG exists, or CISD level
                fvg_top = h2 if l0 > h2 else active_lvl
                pending_order = {"dir": 1, "limit_price": fvg_top, "sl_price": fvg_top - (fvg_top * 0.0005) if stop_mode == "SL_5bps" else sl_price, "bar": i}
            elif entry_mechanism == "FVG_CE50":
                fvg_mid = (l0 + h2) / 2.0 if l0 > h2 else (c0 + active_lvl) / 2.0
                pending_order = {"dir": 1, "limit_price": fvg_mid, "sl_price": fvg_mid - (fvg_mid * 0.0005) if stop_mode == "SL_5bps" else sl_price, "bar": i}

        # Bearish CISD
        elif vibes == 1 and c0 < active_lvl:
            vibes = -1
            pain_threshold = l0
            bagholder_entry, delivery_origin_h = consult_crystal_ball(-1, i)

            if stop_mode == "SL_5bps":
                sl_price = c0 + (c0 * 0.0005)  # 5 bps Stop
            elif stop_mode == "SL_8bps":
                sl_price = c0 + (c0 * 0.0008)
            elif stop_mode == "SL_12bps":
                sl_price = c0 + (c0 * 0.0012)
            else:
                sl_price = max(delivery_origin_h, max(highs[i-4:i+1]))

            if entry_mechanism == "Market":
                if not in_pos and (start_hhmm <= hhmm <= end_hhmm) and (daily_trades < 5):
                    in_pos = True
                    pos_dir = -1
                    pos_entry_time = t
                    pos_entry_price = c0
                    active_sl = sl_price
                    active_tp1 = c0 - (c0 * (queen_bps / 10000.0))
                    active_tp2 = c0 - (c0 * (runner_bps / 10000.0))
                    queen_filled = False
                    pos_mfe = 0.0
                    pos_mae = 0.0
                    daily_trades += 1
            elif entry_mechanism == "FVG_Touch":
                fvg_bot = l2 if h0 < l2 else active_lvl
                pending_order = {"dir": -1, "limit_price": fvg_bot, "sl_price": fvg_bot + (fvg_bot * 0.0005) if stop_mode == "SL_5bps" else sl_price, "bar": i}
            elif entry_mechanism == "FVG_CE50":
                fvg_mid = (h0 + l2) / 2.0 if h0 < l2 else (c0 + active_lvl) / 2.0
                pending_order = {"dir": -1, "limit_price": fvg_mid, "sl_price": fvg_mid + (fvg_mid * 0.0005) if stop_mode == "SL_5bps" else sl_price, "bar": i}

    return pd.DataFrame(trades)


def main():
    print(f"\n{'='*105}", flush=True)
    print("EMPIRICAL STUDY: FVG LIMIT VS. MARKET ENTRY & 09:30-09:45 FILTER (334,414 BARS / 2022-2026)", flush=True)
    print("=" * 105, flush=True)

    data_path = _root / "data/NQ1_5m.parquet"
    df = pd.read_parquet(data_path)

    # Matrix of configurations to test
    configs = [
        {"name": "1. Baseline Market (09:30-15:30 | Structural SL)", "mech": "Market", "start": "0930", "sl": "SL_Structural"},
        {"name": "2. Market + 09:45 Filter (09:45-15:30 | Structural SL)", "mech": "Market", "start": "0945", "sl": "SL_Structural"},
        {"name": "3. Market + 09:45 Filter (09:45-15:30 | 5 bps SL)", "mech": "Market", "start": "0945", "sl": "SL_5bps"},
        {"name": "4. Market + 09:45 Filter (09:45-15:30 | 8 bps SL)", "mech": "Market", "start": "0945", "sl": "SL_8bps"},
        {"name": "5. FVG Touch Limit (09:45-15:30 | 5 bps SL)", "mech": "FVG_Touch", "start": "0945", "sl": "SL_5bps"},
        {"name": "6. FVG Touch Limit (09:45-15:30 | 8 bps SL)", "mech": "FVG_Touch", "start": "0945", "sl": "SL_8bps"},
        {"name": "7. FVG Touch Limit (09:45-15:30 | Structural SL)", "mech": "FVG_Touch", "start": "0945", "sl": "SL_Structural"},
        {"name": "8. FVG CE 50% Limit (09:45-15:30 | 5 bps SL)", "mech": "FVG_CE50", "start": "0945", "sl": "SL_5bps"},
        {"name": "9. FVG CE 50% Limit (09:45-15:30 | 8 bps SL)", "mech": "FVG_CE50", "start": "0945", "sl": "SL_8bps"},
    ]

    results = []
    for cfg in configs:
        trades = run_cisd_simulation(
            df,
            entry_mechanism=cfg["mech"],
            start_hhmm=cfg["start"],
            stop_mode=cfg["sl"],
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

        results.append({
            "Configuration": cfg["name"],
            "Trades": len(trades),
            "Win Rate": f"{wr:.1f}%",
            "Profit Factor": f"{pf:.2f}",
            "Queen (+10bps) %": f"{queen_reach:.1f}%",
            "Runner (+30bps) %": f"{runner_reach:.1f}%",
            "Net Bps": f"{net_bps:+,.1f} bps",
            "Expectancy": f"{exp_bps:+,.2f} bps/tr",
        })

    print(pd.DataFrame(results).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
