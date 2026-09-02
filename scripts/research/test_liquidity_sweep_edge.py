"""
Test Liquidity Sweep + CISD (Turtle Soup Edge):
Compare RequireExternalSweep = False vs True
Across NQ and ES 2025-2026
"""

import pandas as pd
import numpy as np

def test_sweep_edge(asset="NQ"):
    print("="*95)
    print(f"TESTING LIQUIDITY SWEEP + CISD ON {asset} (2025-2026)")
    print("="*95)

    df_1m = pd.read_parquet(f"data/{asset}1_1m.parquet")
    df_1m = df_1m.loc["2025-01-01":].copy()
    times_1m = df_1m.index
    c1, o1, h1, l1 = df_1m["close"].to_numpy(), df_1m["open"].to_numpy(), df_1m["high"].to_numpy(), df_1m["low"].to_numpy()
    n1 = len(df_1m)

    df_5m = df_1m.resample("5min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    # 4H EMA(50)
    df_4h = df_1m.resample("4h").agg({"close": "last"}).dropna()
    df_4h["ema50"] = df_4h["close"].ewm(span=50).mean()
    ema_5m = df_4h["ema50"].reindex(df_5m.index, method="ffill").bfill()
    df_5m["htf_bias"] = np.where(df_5m["close"] >= ema_5m, 1, -1)

    # Rolling 20-bar swing high/low on 5m
    df_5m["swing_high"] = df_5m["high"].rolling(20).max().shift(1)
    df_5m["swing_low"] = df_5m["low"].rolling(20).min().shift(1)

    # Session Highs/Lows: Asia (18:00 - 02:00), London (02:00 - 08:00), Prior Day
    df_5m["date"] = df_5m.index.date
    df_5m["hhmm"] = df_5m.index.strftime("%H%M")

    c5, o5, h5, l5 = df_5m["close"].to_numpy(), df_5m["open"].to_numpy(), df_5m["high"].to_numpy(), df_5m["low"].to_numpy()
    sw_h, sw_l = df_5m["swing_high"].to_numpy(), df_5m["swing_low"].to_numpy()
    htf = df_5m["htf_bias"].to_numpy()
    times_5m = df_5m.index
    time_strs_5m = df_5m["hhmm"].to_numpy()
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
                ext_o = o_h[cur_idx - step] if 'o_h' in globals() else o5[cur_idx - step]
                break
        return ext_o

    for req_sweep in [False, True]:
        htf_displacements = []
        vibes = 0
        bagholder = np.nan
        pain = np.nan

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
                # Check if prior liquidity was swept
                # Lookback 10 bars for the extreme pain point sweeping swing high/low
                if req_sweep:
                    recent_min = np.min(l5[max(0, i-10):i+1])
                    recent_max = np.max(h5[max(0, i-10):i+1])
                    if sig == 1 and recent_min > sw_l[i]:
                        continue # Did NOT sweep swing low
                    if sig == -1 and recent_max < sw_h[i]:
                        continue # Did NOT sweep swing high

                has_fvg = (sig == 1 and l0 > h2) or (sig == -1 and h0 < l2)
                fvg_top = l0 if (sig == 1 and l0 > h2) else (l2 if (sig == -1 and h0 < l2) else np.nan)
                fvg_bot = h2 if (sig == 1 and l0 > h2) else (h0 if (sig == -1 and h0 < l2) else np.nan)
                htf_displacements.append({
                    "time": times_5m[i], "dir": sig, "has_fvg": has_fvg,
                    "fvg_top": fvg_top, "fvg_bot": fvg_bot, "ob_level": bagholder
                })

        # Simulate execution
        trades = []
        for disp in htf_displacements:
            t_disp, d = disp["time"], disp["dir"]
            zone_high = disp["fvg_top"] if disp["has_fvg"] else max(disp["ob_level"], disp["ob_level"] + 5.0)
            zone_low = disp["fvg_bot"] if disp["has_fvg"] else min(disp["ob_level"], disp["ob_level"] - 5.0)

            idx1 = times_1m.searchsorted(t_disp)
            if idx1 >= n1 - 180:
                continue

            wick_tapped = False
            tap_idx = -1
            for m in range(idx1 + 1, min(n1, idx1 + 25)):
                if d == 1 and l1[m] <= zone_high:
                    wick_tapped = True; tap_idx = m; break
                elif d == -1 and h1[m] >= zone_low:
                    wick_tapped = True; tap_idx = m; break

            if not wick_tapped:
                continue

            entered = False
            entry_p, sl_p, entry_bar = np.nan, np.nan, -1
            for k in range(tap_idx, min(n1, tap_idx + 10)):
                if d == 1 and c1[k] > o1[k]:
                    entry_p = c1[k]
                    protected_swing = np.min(l1[tap_idx:k+1])
                    sl_p = protected_swing - 1.0
                    entered = True; entry_bar = k; break
                elif d == -1 and c1[k] < o1[k]:
                    entry_p = c1[k]
                    protected_swing = np.max(h1[tap_idx:k+1])
                    sl_p = protected_swing + 1.0
                    entered = True; entry_bar = k; break

            if entered:
                risk_pts = abs(entry_p - sl_p)
                risk_bps = (risk_pts / entry_p) * 10000.0
                if risk_bps < 2.0 or risk_bps > 12.0:
                    continue

                tp1_p = entry_p + (entry_p * 0.0010) if d == 1 else entry_p - (entry_p * 0.0010)
                tp2_p = entry_p + (entry_p * 0.0030) if d == 1 else entry_p - (entry_p * 0.0030)

                q_hit, r_hit, active_sl, exit_p = False, False, sl_p, entry_p
                for step in range(entry_bar + 1, min(n1, entry_bar + 180)):
                    bh, bl = h1[step], l1[step]
                    if d == 1:
                        if not q_hit and bh >= tp1_p:
                            q_hit = True; active_sl = entry_p
                        if bl <= active_sl:
                            exit_p = active_sl; break
                        if bh >= tp2_p:
                            r_hit = True; exit_p = tp2_p; break
                    else:
                        if not q_hit and bl <= tp1_p:
                            q_hit = True; active_sl = entry_p
                        if bh >= active_sl:
                            exit_p = active_sl; break
                        if bl <= tp2_p:
                            r_hit = True; exit_p = tp2_p; break

                q_pts = (tp1_p - entry_p) if q_hit else (exit_p - entry_p if d == 1 else entry_p - exit_p)
                r_pts = (exit_p - entry_p) if d == 1 else (entry_p - exit_p)
                pnl_pts = (q_pts + r_pts) / 2.0
                pnl_bps = (pnl_pts / entry_p) * 10000.0 * d
                trades.append(pnl_bps)

        arr = np.array(trades)
        wr = (arr > 0).mean() * 100.0 if len(arr) > 0 else 0
        gp = arr[arr > 0].sum()
        gl = abs(arr[arr < 0].sum())
        pf = gp / gl if gl > 0 else np.nan

        sweep_label = "WITH Liquidity Sweep Filter" if req_sweep else "WITHOUT Liquidity Sweep Filter"
        print(f"\nConfiguration: {sweep_label}")
        print(f"  Total Trades:     {len(arr)}")
        print(f"  Win Rate:         {wr:.1f}%")
        print(f"  Profit Factor:    {pf:.2f}")
        print(f"  Expectancy:       {arr.mean():+.2f} bps/trade")

if __name__ == "__main__":
    test_sweep_edge("NQ")
    test_sweep_edge("ES")
