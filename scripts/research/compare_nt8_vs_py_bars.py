"""
Compare NT8 exact trades against bar data and Python signals
"""

import json
import pandas as pd
import numpy as np

def main():
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

    csv_path = r"C:\Users\vinay\Documents\NinjaTrader 8\mcp_bars_NQ_09_26_Minute5.csv"
    df_bars = pd.read_csv(csv_path)
    df_bars.columns = [c.strip().lower() for c in df_bars.columns]
    df_bars["time"] = pd.to_datetime(df_bars["time"])
    df_bars = df_bars.set_index("time").sort_index()

    # Reconstruct exact C# ICTFVGCISDIndicator state machine
    closes = df_bars["close"].to_numpy()
    highs = df_bars["high"].to_numpy()
    lows = df_bars["low"].to_numpy()
    opens = df_bars["open"].to_numpy()
    times = df_bars.index
    n = len(df_bars)

    # 50-period EMA on Close
    # NT8 EMA formula: multiplier = 2.0 / (period + 1.0)
    ema50 = np.zeros(n, dtype=np.float64)
    mult = 2.0 / 51.0
    ema50[0] = closes[0]
    for k in range(1, n):
        ema50[k] = (closes[k] - ema50[k - 1]) * mult + ema50[k - 1]

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
                    limits[i] = lmt
                    stops[i] = sl
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
                    limits[i] = lmt
                    stops[i] = sl
                    vibes = -1
                    pain = l0
                    bagholder = consult_crystal_ball(-1, i)

    sig_times = times[signals != 0]
    print(f"Total Reconstructed Signals: {len(sig_times)}")

    # Check how many NT8 entries matched an exact signal bar or bar-1
    sig_set = set(sig_times)
    matched_exact = 0
    matched_prev = 0
    for idx, r in nt_entries.iterrows():
        et = r["entryTime"]
        # Find index in df_bars
        if et in df_bars.index:
            loc = df_bars.index.get_loc(et)
            prev_t = df_bars.index[loc - 1] if loc > 0 else None
            if et in sig_set:
                matched_exact += 1
            elif prev_t in sig_set:
                matched_prev += 1
            else:
                print(f"NT8 entry {et} ({r['direction']} @ {r['entry_price']}) NOT matched in signals! Prev bar: {prev_t}")

    print(f"\nExact Bar Matches: {matched_exact}/{len(nt_entries)}")
    print(f"Signal on Prior Bar (Filled Next Bar): {matched_prev}/{len(nt_entries)}")
    print(f"Total Matched: {matched_exact + matched_prev}/{len(nt_entries)}")


if __name__ == "__main__":
    main()
