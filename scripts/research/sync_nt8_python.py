"""
========================================================================================
Synchronized Cross-Platform Engine: NinjaTrader 8 Parity Verification
========================================================================================
Implements exact NinjaTrader 8 RiskManagerBase state machine in Python:
1. MaxTradesPerDay = 3
2. MaxConsecutiveLosers = 2 (pause 30 minutes)
3. HardStopConsecutiveLosers = 3 (done for day)
4. DailyMaxLoss = $1,500
5. Snap all limits, stops, targets to 0.25 tick size
6. Intraday bar evaluation order matching NinjaTrader 8
========================================================================================
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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


def run_synced_python_engine(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").sort_index()

    times = df.index
    opens = df["open"].to_numpy(dtype=np.float64)
    highs = df["high"].to_numpy(dtype=np.float64)
    lows = df["low"].to_numpy(dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    n = len(df)

    ema50 = df["close"].ewm(span=50).mean().to_numpy()
    time_strs = times.strftime("%H%M")
    hours = times.hour
    mins = times.minute

    def round_tick(p: float) -> float:
        return round(p * 4.0) / 4.0

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
    active_sl = 0.0
    active_tp1 = 0.0
    active_tp2 = 0.0
    queen_filled = False

    # NT8 RiskManagerBase State
    daily_trades = 0
    consecutive_losers = 0
    pause_until_time = None
    daily_pnl = 0.0
    cur_day = None
    pending_order = None

    for i in range(50, n):
        t = times[i]
        hhmm = time_strs[i]
        bar_date = t.date()
        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h2, l2 = highs[i - 2], lows[i - 2]
        hh = hours[i]
        mm = mins[i]

        if bar_date != cur_day:
            cur_day = bar_date
            daily_trades = 0
            consecutive_losers = 0
            pause_until_time = None
            daily_pnl = 0.0
            pending_order = None

        # Position Management
        if in_pos:
            trade_closed = False
            trade_pnl = 0.0

            if pos_dir == 1:
                # In Bullish bar: Open -> Low -> High -> Close or Open -> High -> Low -> Close
                # Check if Queen target hit first
                if not queen_filled and h0 >= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price  # BE lock

                if hhmm >= "1555":
                    q_pts = (active_tp1 - pos_entry_price) if queen_filled else (c0 - pos_entry_price)
                    r_pts = (c0 - pos_entry_price)
                    trade_pnl = (q_pts + r_pts) * 20.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": c0,
                        "total_pnl_usd": trade_pnl, "exit_reason": "EOD Flat", "queen_hit": queen_filled,
                    })
                    trade_closed = True

                elif l0 <= active_sl:
                    q_pts = (active_tp1 - pos_entry_price) if queen_filled else (active_sl - pos_entry_price)
                    r_pts = (active_sl - pos_entry_price)
                    trade_pnl = (q_pts + r_pts) * 20.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_sl,
                        "total_pnl_usd": trade_pnl, "exit_reason": "Stop Loss", "queen_hit": queen_filled,
                    })
                    trade_closed = True

                elif h0 >= active_tp2:
                    q_pts = (active_tp1 - pos_entry_price)
                    r_pts = (active_tp2 - pos_entry_price)
                    trade_pnl = (q_pts + r_pts) * 20.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Long",
                        "entry_price": pos_entry_price, "exit_price": active_tp2,
                        "total_pnl_usd": trade_pnl, "exit_reason": "Profit Target", "queen_hit": True,
                    })
                    trade_closed = True

            elif pos_dir == -1:
                if not queen_filled and l0 <= active_tp1:
                    queen_filled = True
                    active_sl = pos_entry_price

                if hhmm >= "1555":
                    q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - c0)
                    r_pts = (pos_entry_price - c0)
                    trade_pnl = (q_pts + r_pts) * 20.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": c0,
                        "total_pnl_usd": trade_pnl, "exit_reason": "EOD Flat", "queen_hit": queen_filled,
                    })
                    trade_closed = True

                elif h0 >= active_sl:
                    q_pts = (pos_entry_price - active_tp1) if queen_filled else (pos_entry_price - active_sl)
                    r_pts = (pos_entry_price - active_sl)
                    trade_pnl = (q_pts + r_pts) * 20.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_sl,
                        "total_pnl_usd": trade_pnl, "exit_reason": "Stop Loss", "queen_hit": queen_filled,
                    })
                    trade_closed = True

                elif l0 <= active_tp2:
                    q_pts = (pos_entry_price - active_tp1)
                    r_pts = (pos_entry_price - active_tp2)
                    trade_pnl = (q_pts + r_pts) * 20.0
                    trades.append({
                        "entry_time": pos_entry_time, "exit_time": t, "direction": "Short",
                        "entry_price": pos_entry_price, "exit_price": active_tp2,
                        "total_pnl_usd": trade_pnl, "exit_reason": "Profit Target", "queen_hit": True,
                    })
                    trade_closed = True

            if trade_closed:
                in_pos = False
                daily_pnl += trade_pnl
                if trade_pnl < 0:
                    consecutive_losers += 1
                    if consecutive_losers >= 2:
                        pause_until_time = t + pd.Timedelta(minutes=30)
                else:
                    consecutive_losers = 0

        # Pending Limit Order Evaluation
        if pending_order is not None and not in_pos:
            p_dir = pending_order["dir"]
            p_limit = pending_order["limit"]
            p_sl = pending_order["sl"]
            p_bar = pending_order["bar"]

            is_paused = (pause_until_time is not None and t < pause_until_time)
            hit_hard_stop = (consecutive_losers >= 3)
            hit_daily_max = (daily_pnl <= -1500)
            in_time = ("0945" <= hhmm <= "1530") and not ("1200" <= hhmm <= "1330")

            if (i - p_bar) <= 6:
                if in_time and daily_trades < 3 and not is_paused and not hit_hard_stop and not hit_daily_max:
                    if p_dir == 1 and l0 <= p_limit:
                        in_pos = True
                        pos_dir = 1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        active_sl = p_sl
                        active_tp1 = round_tick(p_limit + (p_limit * 0.0010))
                        active_tp2 = round_tick(p_limit + (p_limit * 0.0030))
                        queen_filled = False
                        daily_trades += 1
                        pending_order = None
                    elif p_dir == -1 and h0 >= p_limit:
                        in_pos = True
                        pos_dir = -1
                        pos_entry_time = t
                        pos_entry_price = p_limit
                        active_sl = p_sl
                        active_tp1 = round_tick(p_limit - (p_limit * 0.0010))
                        active_tp2 = round_tick(p_limit - (p_limit * 0.0030))
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
        in_lunch = ("1200" <= hhmm <= "1330")

        if vibes == -1 and c0 > active_lvl and not in_lunch:
            vibes = 1
            pain_threshold = h0
            bagholder_entry = consult_crystal_ball(1, i)
            if c0 >= ema50[i]:
                fvg_top = round_tick(h2 if l0 > h2 else active_lvl)
                sl_price = round_tick(fvg_top - (fvg_top * 0.0005))
                pending_order = {"dir": 1, "limit": fvg_top, "sl": sl_price, "bar": i}

        elif vibes == 1 and c0 < active_lvl and not in_lunch:
            vibes = -1
            pain_threshold = l0
            bagholder_entry = consult_crystal_ball(-1, i)
            if c0 <= ema50[i]:
                fvg_bot = round_tick(l2 if h0 < l2 else active_lvl)
                sl_price = round_tick(fvg_bot + (fvg_bot * 0.0005))
                pending_order = {"dir": -1, "limit": fvg_bot, "sl": sl_price, "bar": i}

    return pd.DataFrame(trades)


def main():
    csv_path = Path(r"C:\Users\vinay\Documents\NinjaTrader 8\mcp_bars_NQ_09_26_Minute5.csv")
    df_py = run_synced_python_engine(csv_path)

    nt8_file = Path(r"C:\Users\vinay\.gemini\antigravity\brain\4c21dcc0-89c9-42df-8e6a-fc48ef5552a9\.system_generated\steps\723\output.txt")
    with open(nt8_file, "r") as f:
        nt8_data = json.load(f)

    nt8_metrics = nt8_data["metrics"]
    nt8_trades_raw = nt8_data["trades"]

    df_nt_raw = pd.DataFrame(nt8_trades_raw)
    df_nt_raw["entryTime"] = pd.to_datetime(df_nt_raw["entryTime"])
    
    nt_entries = df_nt_raw.groupby("entryTime").agg(
        direction=("marketPosition", "first"),
        entry_price=("entryPrice", "first"),
        total_pnl_usd=("profitCurrency", "sum"),
        total_points=("profitPoints", "sum"),
        exit_names=("exitName", lambda x: list(x)),
    ).reset_index()

    print(f"\n=============================================================================")
    print("PARITY AUDIT: SYNCHRONIZED PYTHON ENGINE vs. NINJATRADER 8")
    print("=============================================================================")
    print(f"Metric                       NinjaTrader 8           Python Engine          Difference")
    print(f"Total Entries                {len(nt_entries):<23} {len(df_py):<22} {len(df_py) - len(nt_entries):+d}")
    print(f"Entry Win Rate (%)           {nt8_metrics['entryWinRatePct']:<23.1f}% {(df_py['total_pnl_usd'] > 0).mean()*100:<22.1f}% {((df_py['total_pnl_usd'] > 0).mean()*100) - nt8_metrics['entryWinRatePct']:+.1f}%")
    print(f"Gross Profit ($)             ${nt8_metrics['grossProfit']:<22,.0f} ${df_py[df_py['total_pnl_usd']>0]['total_pnl_usd'].sum():<21,.0f} ${df_py[df_py['total_pnl_usd']>0]['total_pnl_usd'].sum() - nt8_metrics['grossProfit']:+,.0f}")
    print(f"Gross Loss ($)               ${nt8_metrics['grossLoss']:<22,.0f} -${abs(df_py[df_py['total_pnl_usd']<0]['total_pnl_usd'].sum()):<20,.0f} ${abs(df_py[df_py['total_pnl_usd']<0]['total_pnl_usd'].sum()) - abs(nt8_metrics['grossLoss']):+,.0f}")
    print(f"Net Profit ($)               ${nt8_metrics['netProfit']:<22,.0f} ${df_py['total_pnl_usd'].sum():<21,.0f} ${df_py['total_pnl_usd'].sum() - nt8_metrics['netProfit']:+,.0f}")
    print(f"Profit Factor                {nt8_metrics['profitFactor']:<23.2f} {df_py[df_py['total_pnl_usd']>0]['total_pnl_usd'].sum() / abs(df_py[df_py['total_pnl_usd']<0]['total_pnl_usd'].sum()):<22.2f} {(df_py[df_py['total_pnl_usd']>0]['total_pnl_usd'].sum() / abs(df_py[df_py['total_pnl_usd']<0]['total_pnl_usd'].sum())) - nt8_metrics['profitFactor']:+.2f}")
    print(f"Max Loss Per Entry           ${nt8_metrics['maxLossEntry']:<22,.0f} ${df_py['total_pnl_usd'].min():<21,.0f} ${df_py['total_pnl_usd'].min() - nt8_metrics['maxLossEntry']:+,.0f}")

    nt_entry_times = set(nt_entries["entryTime"])
    py_entry_times = set(df_py["entry_time"])
    matched = nt_entry_times.intersection(py_entry_times)
    print(f"\nExact Matched Entry Timestamps: {len(matched)} of {len(nt_entries)} ({len(matched)/len(nt_entries)*100:.1f}% matching)")


if __name__ == "__main__":
    main()
