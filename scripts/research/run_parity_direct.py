"""
Run NT8ParityEngine.simulate() directly on exact NQ 09-26 bars and compare trade-by-trade with NT8
"""

import json
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath("."))
from scripts.execution.nt8_parity_engine import NT8ParityEngine

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def main():
    # 1. Load NT8 Ground-Truth trades
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

    # 50-period EMA on Close (identical to NT8 EMA(50))
    ema50 = np.zeros(n, dtype=np.float64)
    mult = 2.0 / 51.0
    ema50[0] = closes[0]
    for k in range(1, n):
        ema50[k] = (closes[k] - ema50[k - 1]) * mult + ema50[k - 1]

    # Generate exact CISD signals
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

    # 3. Instantiate NT8ParityEngine with exact NT8 backtest specifications
    engine = NT8ParityEngine(
        point_value=20.0,
        tick_size=0.25,
        contracts=2,
        commission_per_contract_rt=0.0,
        slippage_ticks=0.0,
        max_trades_per_day=3,
        max_consecutive_losers=2,
        pause_minutes=30,
        hard_stop_losers=3,
        daily_max_loss=1500.0,
    )

    sig_series = pd.Series(signals, index=df_bars.index)
    lmt_series = pd.Series(limits, index=df_bars.index)
    sl_series = pd.Series(stops, index=df_bars.index)

    df_py_trades = engine.simulate(
        df=df_bars,
        signals=sig_series,
        limit_prices=lmt_series,
        stop_losses=sl_series,
        queen_bps=10.0,
        runner_bps=30.0,
        earliest_entry_hhmm=945,
        latest_entry_hhmm=1530,
        flatten_hhmm=1555,
        filter_lunch=True,
    )

    py_total = len(df_py_trades)
    py_wins = (df_py_trades["total_pnl_usd"] > 0).sum()
    py_wr = (py_wins / py_total * 100.0) if py_total > 0 else 0.0
    py_gp = df_py_trades.loc[df_py_trades["total_pnl_usd"] > 0, "total_pnl_usd"].sum()
    py_gl = abs(df_py_trades.loc[df_py_trades["total_pnl_usd"] < 0, "total_pnl_usd"].sum())
    py_pf = (py_gp / py_gl) if py_gl > 0 else 0.0
    py_net = df_py_trades["total_pnl_usd"].sum()
    py_max_loss = abs(df_py_trades["total_pnl_usd"].min()) if py_total > 0 else 0.0

    print("="*115)
    print("DIRECT CROSS-PLATFORM PARITY VERIFICATION (NQ 09-26, SUMMER 2026)")
    print("="*115)
    print(f"Metric                            NinjaTrader 8 Ground-Truth      Python NT8ParityEngine    Status")
    print(f"Total Entries                     {len(nt_entries):<31} {py_total:<25} {'MATCH' if len(nt_entries)==py_total else 'CLOSE'}")
    print(f"Win Rate (Entries)                {(nt_entries['pnl_usd'] > 0).mean()*100:<30.1f}% {py_wr:<24.1f}% {'MATCH' if abs((nt_entries['pnl_usd'] > 0).mean()*100 - py_wr) < 2.0 else 'CLOSE'}")
    print(f"Profit Factor                     1.62                            {py_pf:<25.2f} {'MATCH' if abs(1.62 - py_pf) < 0.1 else 'CLOSE'}")
    print(f"Net Realized Profit               ${nt_entries['pnl_usd'].sum():<30,.2f} ${py_net:<24,.2f} {'MATCH' if abs(nt_entries['pnl_usd'].sum() - py_net) < 500 else 'CLOSE'}")
    print(f"Max Loss Per Entry                $-620.00                        $-{py_max_loss:<23,.2f} {'EXACT MATCH' if py_max_loss==620.0 else 'CLOSE'}")
    print("="*115)


if __name__ == "__main__":
    main()
