"""
Test True ICT HTF Liquidity Grab + CISD Model:
HTF Anchors:
1. Time-Based Liquidity: PDH/PDL, Asia H/L (20:00-00:00), London H/L (02:00-05:00), NY AM IB (09:30-10:00)
2. Structural HTF: 1-Hour (H1) and 4-Hour (H4) Highs/Lows (Wick sweep: High > Level & Close < Level)
3. HTF Imbalances: 1-Hour and 15-Minute FVGs (Price taps into opposing HTF FVG)

Rule: A CISD is ONLY valid if it occurs immediately after an HTF Liquidity Grab!
"""

import pandas as pd
import numpy as np
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def run_htf_liquidity_cisd_test(asset="NQ"):
    print("="*105)
    print(f"AUTHENTIC ICT HTF LIQUIDITY GRAB + CISD AUDIT: {asset} (2025-2026)")
    print("="*105)

    df_1m = pd.read_parquet(f"data/{asset}1_1m.parquet")
    df_1m = df_1m.loc["2025-01-01":].copy()

    times_1m = df_1m.index
    c1, o1, h1, l1 = df_1m["close"].to_numpy(), df_1m["open"].to_numpy(), df_1m["high"].to_numpy(), df_1m["low"].to_numpy()
    n1 = len(df_1m)

    # 1. Resample to 15m (Primary HTF Structure per TTrades) and 1H / 4H / Daily
    df_15m = df_1m.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_1h = df_1m.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h = df_1m.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # Prior 1H & 4H Highs/Lows (shifted by 1 to prevent lookahead)
    h1_high = df_1h["high"].shift(1).reindex(df_15m.index, method="ffill").bfill().to_numpy()
    h1_low = df_1h["low"].shift(1).reindex(df_15m.index, method="ffill").bfill().to_numpy()
    h4_high = df_4h["high"].shift(1).reindex(df_15m.index, method="ffill").bfill().to_numpy()
    h4_low = df_4h["low"].shift(1).reindex(df_15m.index, method="ffill").bfill().to_numpy()

    # 4H EMA50 for Trend Bias
    df_4h["ema50"] = df_4h["close"].ewm(span=50).mean()
    ema_15m = df_4h["ema50"].reindex(df_15m.index, method="ffill").bfill().to_numpy()

    # 2. Time-Based Sessions (Asia 20:00-00:00, London 02:00-05:00, PDH/PDL, NY AM 09:30-10:00)
    df_1m["date"] = df_1m.index.date
    df_1m["hhmm"] = df_1m.index.strftime("%H%M")

    # Group daily high/lows
    daily_hl = df_1m.groupby("date").agg({"high": "max", "low": "min"})
    pdh_map = daily_hl["high"].shift(1).to_dict()
    pdl_map = daily_hl["low"].shift(1).to_dict()

    df_15m["date"] = df_15m.index.date
    df_15m["hhmm"] = df_15m.index.strftime("%H%M")
    df_15m["pdh"] = df_15m["date"].map(pdh_map)
    df_15m["pdl"] = df_15m["date"].map(pdl_map)

    # Session tracking on 15m
    c15, o15, h15, l15 = df_15m["close"].to_numpy(), df_15m["open"].to_numpy(), df_15m["high"].to_numpy(), df_15m["low"].to_numpy()
    pdh, pdl = df_15m["pdh"].to_numpy(), df_15m["pdl"].to_numpy()
    hhmm_15m = df_15m["hhmm"].to_numpy()
    dates_15m = df_15m["date"].to_numpy()
    n15 = len(df_15m)

    # 3. 1H FVGs
    df_1h["bull_fvg_top"] = np.where((df_1h["low"] > df_1h["high"].shift(2)), df_1h["low"], np.nan)
    df_1h["bull_fvg_bot"] = np.where((df_1h["low"] > df_1h["high"].shift(2)), df_1h["high"].shift(2), np.nan)
    df_1h["bear_fvg_top"] = np.where((df_1h["high"] < df_1h["low"].shift(2)), df_1h["low"].shift(2), np.nan)
    df_1h["bear_fvg_bot"] = np.where((df_1h["high"] < df_1h["low"].shift(2)), df_1h["high"], np.nan)

    h1_bull_fvg_top = df_1h["bull_fvg_top"].shift(1).reindex(df_15m.index, method="ffill").to_numpy()
    h1_bull_fvg_bot = df_1h["bull_fvg_bot"].shift(1).reindex(df_15m.index, method="ffill").to_numpy()
    h1_bear_fvg_top = df_1h["bear_fvg_top"].shift(1).reindex(df_15m.index, method="ffill").to_numpy()
    h1_bear_fvg_bot = df_1h["bear_fvg_bot"].shift(1).reindex(df_15m.index, method="ffill").to_numpy()

    # Track Asia & London
    asia_high, asia_low = np.nan, np.nan
    london_high, london_low = np.nan, np.nan
    ny_am_high, ny_am_low = np.nan, np.nan
    cur_d = None

    asia_h_arr = np.full(n15, np.nan)
    asia_l_arr = np.full(n15, np.nan)
    lon_h_arr = np.full(n15, np.nan)
    lon_l_arr = np.full(n15, np.nan)
    ny_am_h_arr = np.full(n15, np.nan)
    ny_am_l_arr = np.full(n15, np.nan)

    temp_asia_h, temp_asia_l = np.nan, np.nan
    temp_lon_h, temp_lon_l = np.nan, np.nan
    temp_ny_h, temp_ny_l = np.nan, np.nan

    for i in range(n15):
        d = dates_15m[i]
        t = hhmm_15m[i]
        if d != cur_d:
            cur_d = d
            temp_ny_h, temp_ny_l = np.nan, np.nan

        # Asia: 20:00 - 00:00
        if "2000" <= t <= "2345":
            temp_asia_h = h15[i] if np.isnan(temp_asia_h) else max(temp_asia_h, h15[i])
            temp_asia_l = l15[i] if np.isnan(temp_asia_l) else min(temp_asia_l, l15[i])
        elif t == "0000":
            asia_high, asia_low = temp_asia_h, temp_asia_l
            temp_asia_h, temp_asia_l = np.nan, np.nan

        # London: 02:00 - 05:00
        if "0200" <= t <= "0500":
            temp_lon_h = h15[i] if np.isnan(temp_lon_h) else max(temp_lon_h, h15[i])
            temp_lon_l = l15[i] if np.isnan(temp_lon_l) else min(temp_lon_l, l15[i])
        elif t == "0515":
            london_high, london_low = temp_lon_h, temp_lon_l
            temp_lon_h, temp_lon_l = np.nan, np.nan

        # NY AM IB: 09:30 - 10:00
        if "0930" <= t <= "1000":
            temp_ny_h = h15[i] if np.isnan(temp_ny_h) else max(temp_ny_h, h15[i])
            temp_ny_l = l15[i] if np.isnan(temp_ny_l) else min(temp_ny_l, l15[i])
        elif t > "1000" and not np.isnan(temp_ny_h):
            ny_am_high, ny_am_low = temp_ny_h, temp_ny_l

        asia_h_arr[i] = asia_high
        asia_l_arr[i] = asia_low
        lon_h_arr[i] = london_high
        lon_l_arr[i] = london_low
        ny_am_h_arr[i] = ny_am_high
        ny_am_l_arr[i] = ny_am_low

    # 4. Run CISD with & without Strict HTF Liquidity Grab Filter
    def consult_cb(b, cur_idx):
        max_lb = min(15, cur_idx)
        ext_o = o15[cur_idx - 1]
        for step in range(1, max_lb + 1):
            is_opp = (c15[cur_idx - step] < o15[cur_idx - step]) if b == 1 else (c15[cur_idx - step] > o15[cur_idx - step])
            if is_opp:
                ext_o = o15[cur_idx - step]
                break
        return ext_o

    for req_htf_grab in [False, True]:
        vibes = 0
        bagholder = np.nan
        pain = np.nan
        htf_displacements = []

        for i in range(50, n15 - 40):
            hhmm = hhmm_15m[i]
            c0, o0, h0, l0 = c15[i], o15[i], h15[i], l15[i]
            h2, l2 = h15[i - 2], l15[i - 2]

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
            if vibes == -1 and c0 > bagholder and in_time and c0 >= ema_15m[i]:
                vibes = 1
                pain = h0
                bagholder = consult_cb(1, i)
                sig = 1
            elif vibes == 1 and c0 < bagholder and in_time and c0 <= ema_15m[i]:
                vibes = -1
                pain = l0
                bagholder = consult_cb(-1, i)
                sig = -1

            if sig != 0:
                if req_htf_grab:
                    # Check recent 3 bars for an AUTHENTIC HTF LIQUIDITY GRAB
                    # Lookback recent lows and highs
                    rec_l = np.min(l15[max(0, i-3):i+1])
                    rec_h = np.max(h15[max(0, i-3):i+1])
                    rec_c = c0

                    # 1. Time-based sweeps (Wick sweep: Extr > Level & Close inside)
                    sweep_pdl = (rec_l < pdl[i]) and (rec_c > pdl[i]) if not np.isnan(pdl[i]) else False
                    sweep_pdh = (rec_h > pdh[i]) and (rec_c < pdh[i]) if not np.isnan(pdh[i]) else False

                    sweep_asia_l = (rec_l < asia_l_arr[i]) and (rec_c > asia_l_arr[i]) if not np.isnan(asia_l_arr[i]) else False
                    sweep_asia_h = (rec_h > asia_h_arr[i]) and (rec_c < asia_h_arr[i]) if not np.isnan(asia_h_arr[i]) else False

                    sweep_lon_l = (rec_l < lon_l_arr[i]) and (rec_c > lon_l_arr[i]) if not np.isnan(lon_l_arr[i]) else False
                    sweep_lon_h = (rec_h > lon_h_arr[i]) and (rec_c < lon_h_arr[i]) if not np.isnan(lon_h_arr[i]) else False

                    sweep_ny_l = (rec_l < ny_am_l_arr[i]) and (rec_c > ny_am_l_arr[i]) if not np.isnan(ny_am_l_arr[i]) else False
                    sweep_ny_h = (rec_h > ny_am_h_arr[i]) and (rec_c < ny_am_h_arr[i]) if not np.isnan(ny_am_h_arr[i]) else False

                    # 2. Hourly & 4H High/Low sweeps
                    sweep_h1_l = (rec_l < h1_low[i]) and (rec_c > h1_low[i])
                    sweep_h1_h = (rec_h > h1_high[i]) and (rec_c < h1_high[i])
                    sweep_h4_l = (rec_l < h4_low[i]) and (rec_c > h4_low[i])
                    sweep_h4_h = (rec_h > h4_high[i]) and (rec_c < h4_high[i])

                    # 3. HTF FVG tap (Price taps into 1H FVG)
                    tap_h1_bull_fvg = (rec_l <= h1_bull_fvg_top[i]) and (rec_l >= h1_bull_fvg_bot[i]) if not np.isnan(h1_bull_fvg_top[i]) else False
                    tap_h1_bear_fvg = (rec_h >= h1_bear_fvg_bot[i]) and (rec_h <= h1_bear_fvg_top[i]) if not np.isnan(h1_bear_fvg_top[i]) else False

                    bull_grab = sweep_pdl or sweep_asia_l or sweep_lon_l or sweep_ny_l or sweep_h1_l or sweep_h4_l or tap_h1_bull_fvg
                    bear_grab = sweep_pdh or sweep_asia_h or sweep_lon_h or sweep_ny_h or sweep_h1_h or sweep_h4_h or tap_h1_bear_fvg

                    if sig == 1 and not bull_grab:
                        continue # DISCARD CISD (No HTF Liquidity Grab!)
                    if sig == -1 and not bear_grab:
                        continue # DISCARD CISD (No HTF Liquidity Grab!)

                has_fvg = (sig == 1 and l0 > h2) or (sig == -1 and h0 < l2)
                fvg_top = l0 if (sig == 1 and l0 > h2) else (l2 if (sig == -1 and h0 < l2) else np.nan)
                fvg_bot = h2 if (sig == 1 and l0 > h2) else (h0 if (sig == -1 and h0 < l2) else np.nan)
                htf_displacements.append({
                    "time": df_15m.index[i], "dir": sig, "has_fvg": has_fvg,
                    "fvg_top": fvg_top, "fvg_bot": fvg_bot, "ob_level": bagholder
                })

        # 5. Simulate 1-Minute Execution (TTrades Wick Confirmation)
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
                            q_hit = True; active_sl = entry_p # BE lock
                        if bl <= active_sl:
                            exit_p = active_sl; break
                        if bh >= tp2_p:
                            r_hit = True; exit_p = tp2_p; break
                    else:
                        if not q_hit and bl <= tp1_p:
                            q_hit = True; active_sl = entry_p # BE lock
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

        lbl = "WITH STRICT HTF LIQUIDITY GRAB" if req_htf_grab else "WITHOUT HTF GRAB (EVERY CISD)"
        print(f"\nModel: {lbl}")
        print(f"  Total Trades:     {len(arr)}")
        print(f"  Win Rate:         {wr:.1f}%")
        print(f"  Profit Factor:    {pf:.2f}")
        print(f"  Expectancy:       {arr.mean():+.2f} bps/trade")

if __name__ == "__main__":
    run_htf_liquidity_cisd_test("NQ")
    run_htf_liquidity_cisd_test("ES")
