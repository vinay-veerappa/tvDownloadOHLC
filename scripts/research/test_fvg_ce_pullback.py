"""
Test ICT Stage 2 Distribution: Pullback into 5m FVG Consequent Encroachment (50% CE)
with 5.0 bps stop and Cover The Queen brackets (+10 bps / +30 bps)
"""

import pandas as pd
import numpy as np

def main():
    print("Testing Stage 2 Distribution: Pullback to 5m FVG CE (50% Midpoint)...")

    df_1m = pd.read_parquet("data/NQ1_1m.parquet")
    df_1m = df_1m.loc["2025-01-01":].copy()

    df_5m = df_1m.resample("5min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    df_4h = df_1m.resample("4h").agg({"close": "last"}).dropna()
    df_4h["ema50"] = df_4h["close"].ewm(span=50).mean()
    ema_5m = df_4h["ema50"].reindex(df_5m.index, method="ffill").bfill()
    df_5m["htf_bias"] = np.where(df_5m["close"] >= ema_5m, 1, -1)

    c5, o5, h5, l5 = df_5m["close"].to_numpy(), df_5m["open"].to_numpy(), df_5m["high"].to_numpy(), df_5m["low"].to_numpy()
    htf = df_5m["htf_bias"].to_numpy()
    times_5m = df_5m.index
    time_strs_5m = times_5m.strftime("%H%M")
    n5 = len(df_5m)

    vibes = 0
    bagholder = np.nan
    pain = np.nan

    def consult_cb(b, cur_idx):
        max_lb = min(15, cur_idx)
        ext_o = o5[cur_idx - 1]
        for step in range(1, max_lb + 1):
            is_opp = (c5[cur_idx - step] < o5[cur_idx - step]) if b == 1 else (c5[cur_idx - step] > o5[cur_idx - step])
            if is_opp:
                ext_o = o5[cur_idx - step]
                break
        return ext_o

    # 1. Detect 5m CISD shifts
    trades_ce = []
    trades_touch = []

    for i in range(50, n5 - 60):
        hhmm = time_strs_5m[i]
        c0, o0, h0, l0 = c5[i], o5[i], h5[i], l5[i]
        h2, l2 = h5[i - 2], l5[i - 2]

        candle_pers = 1 if c0 > o0 else (-1 if c0 < o0 else 0)
        if vibes == 0:
            vibes = candle_pers if candle_pers != 0 else 1
            bagholder = consult_cb(vibes, i)
            pain = h0 if vibes == 1 else l0

        if vibes == 1 and h0 > pain:
            pain = h0
            bagholder = consult_cb(1, i)
        elif vibes == -1 and l0 < pain:
            pain = l0
            bagholder = consult_cb(-1, i)

        in_time = ("0945" <= hhmm <= "1530") and not ("1200" <= hhmm <= "1330")
        is_bull_fvg = (l0 > h2)
        is_bear_fvg = (h0 < l2)

        sig = 0
        if vibes == -1 and c0 > bagholder and in_time and htf[i] == 1:
            vibes = 1
            pain = h0
            bagholder = consult_cb(1, i)
            sig = 1
        elif vibes == 1 and c0 < bagholder and in_time and htf[i] == -1:
            vibes = -1
            pain = l0
            bagholder = consult_cb(-1, i)
            sig = -1

        if sig != 0:
            # Model 1: Touch of FVG boundary (h2 / l2)
            # Model 2: 50% CE of FVG ((l0 + h2) / 2.0 or (h0 + l2) / 2.0)
            if sig == 1:
                touch_price = h2 if is_bull_fvg else bagholder
                ce_price = (l0 + h2) / 2.0 if is_bull_fvg else (c0 + bagholder) / 2.0
            else:
                touch_price = l2 if is_bear_fvg else bagholder
                ce_price = (h0 + l2) / 2.0 if is_bear_fvg else (c0 + bagholder) / 2.0

            # Simulate 1m bar-by-bar execution after 5m bar close
            # Must pull back to touch the level within next 6 5m bars (30 mins)
            for model_name, target_entry in [("touch", touch_price), ("ce", ce_price)]:
                filled = False
                fill_bar = -1
                for k in range(i + 1, min(n5, i + 7)):
                    if sig == 1 and l5[k] <= target_entry:
                        filled = True; fill_bar = k; break
                    elif sig == -1 and h5[k] >= target_entry:
                        filled = True; fill_bar = k; break

                if filled:
                    entry = target_entry
                    sl = entry - (entry * 0.0005) if sig == 1 else entry + (entry * 0.0005) # 5.0 bps stop
                    tp1 = entry + (entry * 0.0010) if sig == 1 else entry - (entry * 0.0010) # 10.0 bps
                    tp2 = entry + (entry * 0.0030) if sig == 1 else entry - (entry * 0.0030) # 30.0 bps

                    q_hit, r_hit, active_sl, exit_p = False, False, sl, entry
                    for m in range(fill_bar + 1, min(n5, fill_bar + 36)):
                        bh, bl = h5[m], l5[m]
                        if sig == 1:
                            if not q_hit and bh >= tp1:
                                q_hit = True; active_sl = entry
                            if bl <= active_sl:
                                exit_p = active_sl; break
                            if bh >= tp2:
                                r_hit = True; exit_p = tp2; break
                        else:
                            if not q_hit and bl <= tp1:
                                q_hit = True; active_sl = entry
                            if bh >= active_sl:
                                exit_p = active_sl; break
                            if bl <= tp2:
                                r_hit = True; exit_p = tp2; break

                    pnl = (((tp1 - entry if q_hit else exit_p - entry) + (exit_p - entry)) / 2.0 / entry) * 10000.0 * sig
                    if model_name == "touch":
                        trades_touch.append(pnl)
                    else:
                        trades_ce.append(pnl)

    def print_perf(name, tr_list):
        arr = np.array(tr_list)
        wins = arr > 0
        wr = wins.mean() * 100.0
        gp = arr[arr > 0].sum()
        gl = abs(arr[arr < 0].sum())
        pf = gp / gl if gl > 0 else np.nan
        print(f"\n{name}:")
        print(f"  Total Trades:     {len(arr)}")
        print(f"  Win Rate:         {wr:.1f}%")
        print(f"  Profit Factor:    {pf:.2f}")
        print(f"  Expectancy:       {arr.mean():+.2f} bps/trade")

    print_perf("1. FVG Boundary Limit Touch (5.0 bps SL)", trades_touch)
    print_perf("2. FVG 50% Consequent Encroachment (5.0 bps SL)", trades_ce)


if __name__ == "__main__":
    main()
