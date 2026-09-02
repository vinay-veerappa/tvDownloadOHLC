"""
Deep Dive Reality Audit:
1. Test 5.0 bps Stop Loss on 1-Minute Mode
2. Test Second Stage of Distribution
3. Test Realistic Retest vs Market Entries
4. Reconcile with NinjaTrader 8
"""

import pandas as pd
import numpy as np
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def main():
    print("="*95)
    print("REALITY CHECK & DIAGNOSTIC AUDIT: NQ 1-MINUTE EXECUTION")
    print("="*95)

    df_1m = pd.read_parquet("data/NQ1_1m.parquet")
    df_1m = df_1m.loc["2025-01-01":].copy()
    print(f"Loaded {len(df_1m):,d} 1m bars from {df_1m.index[0]} to {df_1m.index[-1]}")

    # Build 5m series
    df_5m = df_1m.resample("5min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    # 4H EMA(50) HTF Trend Filter
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

    # Identify 5m CISD events
    # Stage 1: First CISD shift
    # Stage 2: Second FVG/breakout in the direction of the confirmed CISD trend
    cisd_events = []
    for i in range(50, n5):
        hhmm = time_strs_5m[i]
        c0, o0, h0, l0 = c5[i], o5[i], h5[i], l5[i]
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
        if vibes == -1 and c0 > bagholder and in_time:
            vibes = 1
            pain = h0
            bagholder = consult_cb(1, i)
            if htf[i] == 1:
                cisd_events.append({"time": times_5m[i], "dir": 1, "stage": 1})
        elif vibes == 1 and c0 < bagholder and in_time:
            vibes = -1
            pain = l0
            bagholder = consult_cb(-1, i)
            if htf[i] == -1:
                cisd_events.append({"time": times_5m[i], "dir": -1, "stage": 1})

    print(f"Total 5m CISD Events (2025-2026): {len(cisd_events):,d}")

    times_1m = df_1m.index
    c1, o1, h1, l1 = df_1m["close"].to_numpy(), df_1m["open"].to_numpy(), df_1m["high"].to_numpy(), df_1m["low"].to_numpy()
    n1 = len(df_1m)

    # Now let's evaluate realistic fills with 5.0 bps stop vs 2.5 bps stop:
    # 1. 1m Market Entry on FVG confirmation (Close[0])
    # 2. 1m Retest Limit Entry (Wait for price to actually touch FVG)
    # 3. Stage 2 Distribution Entry (Enter on second FVG after initial shift)

    configs = [
        {"name": "1. 1m FVG Market Entry | 2.5 bps SL", "mode": "market", "sl_bps": 2.5, "stage": 1},
        {"name": "2. 1m FVG Market Entry | 5.0 bps SL", "mode": "market", "sl_bps": 5.0, "stage": 1},
        {"name": "3. 1m FVG Retest Limit | 2.5 bps SL", "mode": "limit",  "sl_bps": 2.5, "stage": 1},
        {"name": "4. 1m FVG Retest Limit | 5.0 bps SL", "mode": "limit",  "sl_bps": 5.0, "stage": 1},
        {"name": "5. Stage 2 Distribution | 5.0 bps SL", "mode": "stage2", "sl_bps": 5.0, "stage": 2},
    ]

    print("\n" + "="*95)
    print(f"{'Configuration':<38} {'Trades':<8} {'Win Rate':<10} {'Profit Factor':<15} {'Expectancy'}")
    print("-" * 95)

    for cfg in configs:
        sl_pct = cfg["sl_bps"] / 10000.0
        mode = cfg["mode"]
        trades = []

        for ev in cisd_events:
            t_ev = ev["time"]
            d = ev["dir"]
            idx1 = times_1m.searchsorted(t_ev)
            if idx1 >= n1 - 180:
                continue

            fvg_count = 0
            for k in range(idx1 + 2, min(n1, idx1 + 20)):
                is_bull_fvg = (d == 1 and l1[k] > h1[k - 2])
                is_bear_fvg = (d == -1 and h1[k] < l1[k - 2])

                if is_bull_fvg or is_bear_fvg:
                    fvg_count += 1

                    if mode == "stage2" and fvg_count < 2:
                        continue  # Wait for 2nd FVG (Stage 2 Distribution)

                    if mode in ["market", "stage2"]:
                        # Enter at Market on the Close of the FVG bar
                        entry = c1[k]
                        sl = entry - (entry * sl_pct) if d == 1 else entry + (entry * sl_pct)
                        tp1 = entry + (entry * 0.0010) if d == 1 else entry - (entry * 0.0010)
                        tp2 = entry + (entry * 0.0030) if d == 1 else entry - (entry * 0.0030)

                        q_hit, r_hit, active_sl, exit_p = False, False, sl, entry
                        for m in range(k + 1, min(n1, k + 180)):
                            bh, bl = h1[m], l1[m]
                            if d == 1:
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

                        pnl = (((tp1 - entry if q_hit else exit_p - entry) + (exit_p - entry)) / 2.0 / entry) * 10000.0 * d
                        trades.append(pnl)
                        break

                    elif mode == "limit":
                        # Wait for price to touch FVG boundary within 4 bars
                        lmt_price = h1[k - 2] if d == 1 else l1[k - 2]
                        filled = False
                        fill_bar = -1
                        for tap in range(k + 1, min(n1, k + 5)):
                            if d == 1 and l1[tap] <= lmt_price:
                                filled = True; fill_bar = tap; break
                            elif d == -1 and h1[tap] >= lmt_price:
                                filled = True; fill_bar = tap; break

                        if filled:
                            entry = lmt_price
                            sl = entry - (entry * sl_pct) if d == 1 else entry + (entry * sl_pct)
                            tp1 = entry + (entry * 0.0010) if d == 1 else entry - (entry * 0.0010)
                            tp2 = entry + (entry * 0.0030) if d == 1 else entry - (entry * 0.0030)

                            q_hit, r_hit, active_sl, exit_p = False, False, sl, entry
                            for m in range(fill_bar + 1, min(n1, fill_bar + 180)):
                                bh, bl = h1[m], l1[m]
                                if d == 1:
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

                            pnl = (((tp1 - entry if q_hit else exit_p - entry) + (exit_p - entry)) / 2.0 / entry) * 10000.0 * d
                            trades.append(pnl)
                        break

        arr = np.array(trades)
        wr = (arr > 0).mean() * 100.0
        gp = arr[arr > 0].sum()
        gl = abs(arr[arr < 0].sum())
        pf = gp / gl if gl > 0 else np.nan
        print(f"{cfg['name']:<38} {len(arr):<8} {wr:<10.1f}% {pf:<15.2f} {arr.mean():+.2f} bps/trade")

    print("="*95)


if __name__ == "__main__":
    main()
