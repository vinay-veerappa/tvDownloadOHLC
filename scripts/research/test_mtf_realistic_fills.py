"""
Test MTF 5m+1m Execution Fills:
1. Model A: Market entry on 1m FVG close
2. Model B: Limit order with 3-bar cancel timeout
3. Model C: Stale limit order left open (NT8 default without timeout)
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
    print("Testing realistic fill mechanics on NQ 1m data (2025-2026)...")
    df_1m = pd.read_parquet("data/NQ1_1m.parquet")
    df_1m = df_1m.loc["2025-01-01":].copy()
    print(f"Loaded {len(df_1m):,d} 1m bars from {df_1m.index[0]} to {df_1m.index[-1]}")

    # Resample to 5m for structure
    df_5m = df_1m.resample("5min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
    }).dropna()

    # 4H EMA(50)
    df_4h = df_1m.resample("4h").agg({"close": "last"}).dropna()
    df_4h["ema50"] = df_4h["close"].ewm(span=50).mean()
    ema_5m = df_4h["ema50"].reindex(df_5m.index, method="ffill").bfill()
    df_5m["htf_bias"] = np.where(df_5m["close"] >= ema_5m, 1, -1)

    # 5m CISD Signal Generation
    c5, o5, h5, l5 = df_5m["close"].to_numpy(), df_5m["open"].to_numpy(), df_5m["high"].to_numpy(), df_5m["low"].to_numpy()
    htf = df_5m["htf_bias"].to_numpy()
    times_5m = df_5m.index
    time_strs_5m = times_5m.strftime("%H%M")
    n5 = len(df_5m)

    vibes = 0
    bagholder = np.nan
    pain = np.nan

    def consult_crystal_ball(b, cur_idx):
        max_lb = min(15, cur_idx)
        ext_o = o5[cur_idx - 1]
        for step in range(1, max_lb + 1):
            is_opp = (c5[cur_idx - step] < o5[cur_idx - step]) if b == 1 else (c5[cur_idx - step] > o5[cur_idx - step])
            if is_opp:
                ext_o = o5[cur_idx - step]
                break
        return ext_o

    sig_5m_events = []
    for i in range(50, n5):
        hhmm = time_strs_5m[i]
        c0, o0, h0, l0 = c5[i], o5[i], h5[i], l5[i]
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

        in_time = ("0945" <= hhmm <= "1530") and not ("1200" <= hhmm <= "1330")
        if vibes == -1 and c0 > bagholder and in_time:
            vibes = 1
            pain = h0
            bagholder = consult_crystal_ball(1, i)
            if htf[i] == 1:
                sig_5m_events.append((times_5m[i], 1))
        elif vibes == 1 and c0 < bagholder and in_time:
            vibes = -1
            pain = l0
            bagholder = consult_crystal_ball(-1, i)
            if htf[i] == -1:
                sig_5m_events.append((times_5m[i], -1))

    print(f"Total 5m CISD events in 2025-2026: {len(sig_5m_events):,d}")

    times_1m = df_1m.index
    c1, o1, h1, l1 = df_1m["close"].to_numpy(), df_1m["open"].to_numpy(), df_1m["high"].to_numpy(), df_1m["low"].to_numpy()
    n1 = len(df_1m)

    # Test Model A: Market Entry on 1m FVG Close
    trades_mkt = []
    # Test Model B: Limit Entry with 3-bar timeout
    trades_lmt_timeout = []

    for t_ev, d in sig_5m_events:
        idx1 = times_1m.searchsorted(t_ev)
        if idx1 >= n1 - 180:
            continue

        # Look for 1st 1m FVG in next 15 bars
        for k in range(idx1 + 2, min(n1, idx1 + 15)):
            is_bull_fvg = (d == 1 and l1[k] > h1[k - 2])
            is_bear_fvg = (d == -1 and h1[k] < l1[k - 2])

            if is_bull_fvg or is_bear_fvg:
                # ── MODEL A: Market Entry on Close of FVG candle ──
                entry_a = c1[k]
                sl_a = entry_a - (entry_a * 0.00025) if d == 1 else entry_a + (entry_a * 0.00025)
                tp1_a = entry_a + (entry_a * 0.0010) if d == 1 else entry_a - (entry_a * 0.0010)
                tp2_a = entry_a + (entry_a * 0.0030) if d == 1 else entry_a - (entry_a * 0.0030)

                q_hit_a, r_hit_a, active_sl_a, exit_a = False, False, sl_a, entry_a
                for m in range(k + 1, min(n1, k + 180)):
                    bh, bl = h1[m], l1[m]
                    if d == 1:
                        if not q_hit_a and bh >= tp1_a:
                            q_hit_a = True; active_sl_a = entry_a
                        if bl <= active_sl_a:
                            exit_a = active_sl_a; break
                        if bh >= tp2_a:
                            r_hit_a = True; exit_a = tp2_a; break
                    else:
                        if not q_hit_a and bl <= tp1_a:
                            q_hit_a = True; active_sl_a = entry_a
                        if bh >= active_sl_a:
                            exit_a = active_sl_a; break
                        if bl <= tp2_a:
                            r_hit_a = True; exit_a = tp2_a; break
                pnl_a = (((tp1_a - entry_a if q_hit_a else exit_a - entry_a) + (exit_a - entry_a)) / 2.0 / entry_a) * 10000.0 * d
                trades_mkt.append(pnl_a)

                # ── MODEL B: Limit Order on FVG Boundary (Must tap within 3 bars) ──
                lmt_price = h1[k - 2] if d == 1 else l1[k - 2]
                filled_b = False
                fill_bar = -1
                for tap in range(k + 1, min(n1, k + 4)):
                    if d == 1 and l1[tap] <= lmt_price:
                        filled_b = True; fill_bar = tap; break
                    elif d == -1 and h1[tap] >= lmt_price:
                        filled_b = True; fill_bar = tap; break

                if filled_b:
                    entry_b = lmt_price
                    sl_b = entry_b - (entry_b * 0.00025) if d == 1 else entry_b + (entry_b * 0.00025)
                    tp1_b = entry_b + (entry_b * 0.0010) if d == 1 else entry_b - (entry_b * 0.0010)
                    tp2_b = entry_b + (entry_b * 0.0030) if d == 1 else entry_b - (entry_b * 0.0030)

                    q_hit_b, r_hit_b, active_sl_b, exit_b = False, False, sl_b, entry_b
                    for m in range(fill_bar + 1, min(n1, fill_bar + 180)):
                        bh, bl = h1[m], l1[m]
                        if d == 1:
                            if not q_hit_b and bh >= tp1_b:
                                q_hit_b = True; active_sl_b = entry_b
                            if bl <= active_sl_b:
                                exit_b = active_sl_b; break
                            if bh >= tp2_b:
                                r_hit_b = True; exit_b = tp2_b; break
                        else:
                            if not q_hit_b and bl <= tp1_b:
                                q_hit_b = True; active_sl_b = entry_b
                            if bh >= active_sl_b:
                                exit_b = active_sl_b; break
                            if bl <= tp2_b:
                                r_hit_b = True; exit_b = tp2_b; break
                    pnl_b = (((tp1_b - entry_b if q_hit_b else exit_b - entry_b) + (exit_b - entry_b)) / 2.0 / entry_b) * 10000.0 * d
                    trades_lmt_timeout.append(pnl_b)

                break

    def print_stats(name, pnl_list):
        arr = np.array(pnl_list)
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

    print_stats("MODEL A: Market Entry on 1m FVG Close", trades_mkt)
    print_stats("MODEL B: Limit Retest Entry (3-bar timeout)", trades_lmt_timeout)


if __name__ == "__main__":
    main()
