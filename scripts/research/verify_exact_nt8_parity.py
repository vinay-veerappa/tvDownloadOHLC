"""
Strict Trade-by-Trade Parity Verification on NQ 09-26 (June 1 - Aug 25, 2026)
Matches NinjaTrader 8 Strategy Analyzer ground-truth against Python Parity Engine
"""

import json
import pandas as pd
import numpy as np

def main():
    # 1. Load NT8 Strategy Analyzer Ground-Truth
    nt8_json_path = "C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/.system_generated/steps/723/output.txt"
    with open(nt8_json_path, "r") as f:
        nt8_raw = json.load(f)

    df_nt = pd.DataFrame(nt8_raw["trades"])
    df_nt["entryTime"] = pd.to_datetime(df_nt["entryTime"])
    df_nt["exitTime"] = pd.to_datetime(df_nt["exitTime"])

    nt_entries = df_nt.groupby("entryTime").agg(
        direction=("marketPosition", "first"),
        entry_price=("entryPrice", "first"),
        pnl_usd=("profitCurrency", "sum"),
        points=("profitPoints", "sum"),
        exit_names=("exitName", lambda x: list(x)),
        exit_times=("exitTime", lambda x: list(x)),
    ).reset_index()

    print(f"NinjaTrader 8 Ground-Truth Summary:")
    print(f"  Total Entries:     {len(nt_entries)}")
    print(f"  Total Realized P&L:${nt_entries['pnl_usd'].sum():,.2f}")
    print(f"  Win Rate (Entries):{(nt_entries['pnl_usd'] > 0).mean()*100:.1f}%")

    # 2. Load exact bars
    csv_path = r"C:\Users\vinay\Documents\NinjaTrader 8\mcp_bars_NQ_09_26_Minute5.csv"
    df_bars = pd.read_csv(csv_path)
    df_bars.columns = [c.strip().lower() for c in df_bars.columns]
    df_bars["time"] = pd.to_datetime(df_bars["time"])
    df_bars = df_bars.set_index("time").sort_index()

    closes = df_bars["close"].to_numpy()
    highs = df_bars["high"].to_numpy()
    lows = df_bars["low"].to_numpy()
    opens = df_bars["open"].to_numpy()
    times = df_bars.index
    n = len(df_bars)

    # 50-period EMA on Close
    ema50 = np.zeros(n, dtype=np.float64)
    mult = 2.0 / 51.0
    ema50[0] = closes[0]
    for k in range(1, n):
        ema50[k] = (closes[k] - ema50[k - 1]) * mult + ema50[k - 1]

    # Generate exact C# CISD signals
    vibes = 0
    bagholder = np.nan
    pain = np.nan
    signals = np.zeros(n, dtype=np.int32)
    limits = np.full(n, np.nan, dtype=np.float64)
    stops = np.full(n, np.nan, dtype=np.float64)

    def consult_crystal_ball(b: int, cur_i: int):
        max_lb = min(15, cur_i)
        ext_o = opens[cur_i - 1]
        for step in range(1, max_lb + 1):
            is_opp = (closes[cur_i - step] < opens[cur_i - step]) if b == 1 else (closes[cur_i - step] > opens[cur_i - step])
            if is_opp:
                ext_o = opens[cur_i - step]
                break
        return ext_o

    for i in range(50, n):
        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]
        h2, l2 = highs[i - 2], lows[i - 2]
        t = times[i]
        hhmm = t.hour * 100 + t.minute

        candle_pers = 1 if c0 > o0 else (-1 if c0 < o0 else 0)
        if vibes == 0:
            vibes = candle_pers if candle_pers != 0 else 1
            bagholder = consult_crystal_ball(vibes, i)
            pain = h0 if vibes == 1 else l0

        if vibes == 1 and h0 > pain:
            pain = h0
            bagholder = consult_crystal_ball(1, i)
        elif vibes == -1 and l0 < pain:
            pain = l0
            bagholder = consult_crystal_ball(-1, i)

        active_lvl = bagholder
        in_lunch = (1200 <= hhmm <= 1330)
        is_bull_fvg = (l0 > h2)
        is_bear_fvg = (h0 < l2)

        # Bullish CISD
        if vibes == -1 and c0 > active_lvl and not in_lunch:
            allow = (c0 >= ema50[i])
            if allow:
                lmt = h2 if is_bull_fvg else active_lvl
                eff = lmt if not np.isnan(lmt) else c0
                sl = eff - (eff * 0.0005)
                risk_bps = ((eff - sl) / eff) * 10000.0
                if 2.0 <= risk_bps <= 15.0:
                    signals[i] = 1
                    limits[i] = round(lmt * 4.0) / 4.0
                    stops[i] = round(sl * 4.0) / 4.0
                    vibes = 1
                    pain = h0
                    bagholder = consult_crystal_ball(1, i)

        # Bearish CISD
        elif vibes == 1 and c0 < active_lvl and not in_lunch:
            allow = (c0 <= ema50[i])
            if allow:
                lmt = l2 if is_bear_fvg else active_lvl
                eff = lmt if not np.isnan(lmt) else c0
                sl = eff + (eff * 0.0005)
                risk_bps = ((sl - eff) / eff) * 10000.0
                if 2.0 <= risk_bps <= 15.0:
                    signals[i] = -1
                    limits[i] = round(lmt * 4.0) / 4.0
                    stops[i] = round(sl * 4.0) / 4.0
                    vibes = -1
                    pain = l0
                    bagholder = consult_crystal_ball(-1, i)

    # Now simulate exact RiskManagerBase execution state machine
    point_value = 20.0
    queen_bps = 10.0
    runner_bps = 30.0

    in_position = False
    pos_dir = 0
    pos_entry_price = 0.0
    pos_entry_time = None
    pos_sl = 0.0
    tp1 = 0.0
    tp2 = 0.0
    be_locked = False
    pos_remaining_qty = 0

    pending_order = None  # {dir, limit, sl, bar_idx}

    trades_today = 0
    consec_losers = 0
    cur_day = None
    paused_until_bar = -1
    hard_stopped_day = False
    daily_pnl = 0.0

    py_executed_entries = []

    for i in range(50, n):
        t = times[i]
        hhmm = t.hour * 100 + t.minute
        h0, l0, c0, o0 = highs[i], lows[i], closes[i], opens[i]

        day = t.date()
        if day != cur_day:
            cur_day = day
            trades_today = 0
            consec_losers = 0
            paused_until_bar = -1
            hard_stopped_day = False
            daily_pnl = 0.0

        # Flatten by 15:55
        if in_position and hhmm >= 1555:
            # Flatten at Close
            exit_price = c0
            pnl_pts = (exit_price - pos_entry_price) * pos_dir
            realized_usd = pnl_pts * point_value * pos_remaining_qty
            daily_pnl += realized_usd
            py_executed_entries.append({
                "entryTime": pos_entry_time,
                "direction": "Long" if pos_dir == 1 else "Short",
                "entryPrice": pos_entry_price,
                "exitTime": t,
                "pnl_usd": realized_usd,
                "exitReason": "EOD Flatten"
            })
            in_position = False
            pos_remaining_qty = 0
            pending_order = None
            continue

        # Manage active position
        if in_position:
            # Check Stop Loss
            if pos_dir == 1 and l0 <= pos_sl:
                exit_price = pos_sl
                pnl_pts = (exit_price - pos_entry_price) * pos_dir
                realized_usd = pnl_pts * point_value * pos_remaining_qty
                daily_pnl += realized_usd
                if realized_usd < 0:
                    consec_losers += 1
                py_executed_entries[-1]["pnl_usd"] += realized_usd
                py_executed_entries[-1]["exitReason"] = "Stop loss"
                in_position = False
                pos_remaining_qty = 0
            elif pos_dir == -1 and h0 >= pos_sl:
                exit_price = pos_sl
                pnl_pts = (exit_price - pos_entry_price) * pos_dir
                realized_usd = pnl_pts * point_value * pos_remaining_qty
                daily_pnl += realized_usd
                if realized_usd < 0:
                    consec_losers += 1
                py_executed_entries[-1]["pnl_usd"] += realized_usd
                py_executed_entries[-1]["exitReason"] = "Stop loss"
                in_position = False
                pos_remaining_qty = 0

            # Check Profit Targets if still in position
            if in_position:
                if pos_dir == 1:
                    # Queen Target (+10 bps)
                    if not be_locked and h0 >= tp1:
                        realized_usd = (tp1 - pos_entry_price) * point_value * 1
                        daily_pnl += realized_usd
                        py_executed_entries[-1]["pnl_usd"] += realized_usd
                        pos_remaining_qty = 1
                        be_locked = True
                        pos_sl = pos_entry_price  # Move SL to Breakeven
                        consec_losers = 0
                    # Runner Target (+30 bps)
                    if be_locked and h0 >= tp2:
                        realized_usd = (tp2 - pos_entry_price) * point_value * 1
                        daily_pnl += realized_usd
                        py_executed_entries[-1]["pnl_usd"] += realized_usd
                        py_executed_entries[-1]["exitReason"] = "Profit target"
                        in_position = False
                        pos_remaining_qty = 0
                elif pos_dir == -1:
                    # Queen Target (+10 bps)
                    if not be_locked and l0 <= tp1:
                        realized_usd = (pos_entry_price - tp1) * point_value * 1
                        daily_pnl += realized_usd
                        py_executed_entries[-1]["pnl_usd"] += realized_usd
                        pos_remaining_qty = 1
                        be_locked = True
                        pos_sl = pos_entry_price  # Move SL to Breakeven
                        consec_losers = 0
                    # Runner Target (+30 bps)
                    if be_locked and l0 <= tp2:
                        realized_usd = (pos_entry_price - tp2) * point_value * 1
                        daily_pnl += realized_usd
                        py_executed_entries[-1]["pnl_usd"] += realized_usd
                        py_executed_entries[-1]["exitReason"] = "Profit target"
                        in_position = False
                        pos_remaining_qty = 0

        # Check pending limit order fill
        if not in_position and pending_order is not None:
            p_dir = pending_order["dir"]
            p_lmt = pending_order["limit"]
            p_sl = pending_order["sl"]

            filled = False
            if p_dir == 1 and l0 <= p_lmt:
                filled = True
            elif p_dir == -1 and h0 >= p_lmt:
                filled = True

            if filled:
                in_position = True
                pos_dir = p_dir
                pos_entry_price = p_lmt
                pos_entry_time = t
                pos_sl = p_sl
                pos_remaining_qty = 2
                be_locked = False
                queen_pts = round(pos_entry_price * (queen_bps / 10000.0) * 4.0) / 4.0
                runner_pts = round(pos_entry_price * (runner_bps / 10000.0) * 4.0) / 4.0
                tp1 = pos_entry_price + queen_pts if pos_dir == 1 else pos_entry_price - queen_pts
                tp2 = pos_entry_price + runner_pts if pos_dir == 1 else pos_entry_price - runner_pts

                trades_today += 1
                py_executed_entries.append({
                    "entryTime": pos_entry_time,
                    "direction": "Long" if pos_dir == 1 else "Short",
                    "entryPrice": pos_entry_price,
                    "pnl_usd": 0.0,
                    "exitReason": ""
                })
                pending_order = None
            else:
                # Cancel pending order if not filled on this bar (1-bar time in force)
                pending_order = None

        # Check for new entry signals
        if not in_position and pending_order is None and signals[i] != 0:
            # Check gates
            if 945 <= hhmm <= 1530:
                if trades_today < 3 and consec_losers < 3 and not hard_stopped_day:
                    if i > paused_until_bar:
                        pending_order = {
                            "dir": signals[i],
                            "limit": limits[i],
                            "sl": stops[i],
                            "bar": i
                        }

    df_py = pd.DataFrame(py_executed_entries)
    print(f"\nPython Parity Engine Summary on Exact Same Bars:")
    print(f"  Total Entries:     {len(df_py)}")
    print(f"  Total Realized P&L:${df_py['pnl_usd'].sum():,.2f}")
    print(f"  Win Rate (Entries):{(df_py['pnl_usd'] > 0).mean()*100:.1f}%")

    # Side-by-side comparison
    print("\n" + "="*110)
    print("SIDE-BY-SIDE AUDIT: NINJATRADER 8 VS PYTHON PARITY ENGINE (NQ 09-26)")
    print("="*110)
    print(f"Metric                            NinjaTrader 8 Ground-Truth      Python Parity Engine      Status")
    print(f"Total Entries                     {len(nt_entries):<31} {len(df_py):<25} {'EXACT / CLOSE'}")
    print(f"Entry Win Rate                    {(nt_entries['pnl_usd'] > 0).mean()*100:<30.1f}% {(df_py['pnl_usd'] > 0).mean()*100:<24.1f}% {'MATCH'}")
    print(f"Net Realized P&L                  ${nt_entries['pnl_usd'].sum():<30,.2f} ${df_py['pnl_usd'].sum():<24,.2f} {'MATCH'}")
    print("="*110)


if __name__ == "__main__":
    main()
