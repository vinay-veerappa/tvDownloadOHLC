"""
Validation of the Canonical HTF Liquidity Grab & TTrades Execution Engine
Enforces:
1. Time-based liquidity: PDH/PDL, Asia H/L, London H/L, NY AM IB (09:30-10:00)
2. Structural HTF: Hourly (H1) and 4-Hour (H4) Highs/Lows with strict wick rejection (Turtle Soup)
3. HTF Imbalances: 1-Hour and 15-Minute FVGs
4. TTrades M15 / M1 Execution: Pullbacks into the FVG form the lower wick of the bull candle -> BUY to trade body!
"""

import pandas as pd
import numpy as np
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def validate_asset(asset="NQ", start_date="2025-01-01"):
    print("=" * 110)
    print(f"CANONICAL VALIDATION: {asset} (From {start_date})")
    print("=" * 110)

    df_1m = pd.read_parquet(f"data/{asset}1_1m.parquet")
    df_1m = df_1m.loc[start_date:].copy()

    times_1m = df_1m.index
    c1, o1, h1, l1 = df_1m["close"].to_numpy(), df_1m["open"].to_numpy(), df_1m["high"].to_numpy(), df_1m["low"].to_numpy()
    n1 = len(df_1m)

    df_15m = df_1m.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_1h = df_1m.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h = df_1m.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    h1_high = df_1h["high"].shift(1).reindex(df_15m.index, method="ffill").bfill().to_numpy()
    h1_low = df_1h["low"].shift(1).reindex(df_15m.index, method="ffill").bfill().to_numpy()
    h4_high = df_4h["high"].shift(1).reindex(df_15m.index, method="ffill").bfill().to_numpy()
    h4_low = df_4h["low"].shift(1).reindex(df_15m.index, method="ffill").bfill().to_numpy()

    df_4h["ema50"] = df_4h["close"].ewm(span=50).mean()
    ema_15m = df_4h["ema50"].reindex(df_15m.index, method="ffill").bfill().to_numpy()

    df_1m["date"] = df_1m.index.date
    daily_hl = df_1m.groupby("date").agg({"high": "max", "low": "min"})
    pdh_map = daily_hl["high"].shift(1).to_dict()
    pdl_map = daily_hl["low"].shift(1).to_dict()

    df_15m["date"] = df_15m.index.date
    df_15m["hhmm"] = df_15m.index.strftime("%H%M")
    df_15m["pdh"] = df_15m["date"].map(pdh_map)
    df_15m["pdl"] = df_15m["date"].map(pdl_map)

    c15, o15, h15, l15 = df_15m["close"].to_numpy(), df_15m["open"].to_numpy(), df_15m["high"].to_numpy(), df_15m["low"].to_numpy()
    pdh, pdl = df_15m["pdh"].to_numpy(), df_15m["pdl"].to_numpy()
    hhmm_15m = df_15m["hhmm"].to_numpy()
    dates_15m = df_15m["date"].to_numpy()
    n15 = len(df_15m)

    # 1H FVGs
    df_1h["bull_fvg_top"] = np.where((df_1h["low"] > df_1h["high"].shift(2)), df_1h["low"], np.nan)
    df_1h["bull_fvg_bot"] = np.where((df_1h["low"] > df_1h["high"].shift(2)), df_1h["high"].shift(2), np.nan)
    df_1h["bear_fvg_top"] = np.where((df_1h["high"] < df_1h["low"].shift(2)), df_1h["low"].shift(2), np.nan)
    df_1h["bear_fvg_bot"] = np.where((df_1h["high"] < df_1h["low"].shift(2)), df_1h["high"], np.nan)

    h1_bull_fvg_top = df_1h["bull_fvg_top"].shift(1).reindex(df_15m.index, method="ffill").to_numpy()
    h1_bull_fvg_bot = df_1h["bull_fvg_bot"].shift(1).reindex(df_15m.index, method="ffill").to_numpy()
    h1_bear_fvg_top = df_1h["bear_fvg_top"].shift(1).reindex(df_15m.index, method="ffill").to_numpy()
    h1_bear_fvg_bot = df_1h["bear_fvg_bot"].shift(1).reindex(df_15m.index, method="ffill").to_numpy()

    # Session Tracking
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

        if "2000" <= t <= "2345":
            temp_asia_h = h15[i] if np.isnan(temp_asia_h) else max(temp_asia_h, h15[i])
            temp_asia_l = l15[i] if np.isnan(temp_asia_l) else min(temp_asia_l, l15[i])
        elif t == "0000":
            asia_high, asia_low = temp_asia_h, temp_asia_l
            temp_asia_h, temp_asia_l = np.nan, np.nan

        if "0200" <= t <= "0500":
            temp_lon_h = h15[i] if np.isnan(temp_lon_h) else max(temp_lon_h, h15[i])
            temp_lon_l = l15[i] if np.isnan(temp_lon_l) else min(temp_lon_l, l15[i])
        elif t == "0515":
            london_high, london_low = temp_lon_h, temp_lon_l
            temp_lon_h, temp_lon_l = np.nan, np.nan

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

    def consult_cb(b, cur_idx):
        max_lb = min(15, cur_idx)
        ext_o = o15[cur_idx - 1]
        for step in range(1, max_lb + 1):
            is_opp = (c15[cur_idx - step] < o15[cur_idx - step]) if b == 1 else (c15[cur_idx - step] > o15[cur_idx - step])
            if is_opp:
                ext_o = o15[cur_idx - step]
                break
        return ext_o

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
            # Check for Rejection Sweep in last 3 bars (Wick breach, body inside)
            def check_sweep_bull(level):
                if np.isnan(level) or level <= 0: return False
                for k in range(max(0, i-3), i+1):
                    if l15[k] <= level and c15[k] > level: return True
                return False

            def check_sweep_bear(level):
                if np.isnan(level) or level <= 0: return False
                for k in range(max(0, i-3), i+1):
                    if h15[k] >= level and c15[k] < level: return True
                return False

            def check_fvg_tap_bull():
                top, bot = h1_bull_fvg_top[i], h1_bull_fvg_bot[i]
                if np.isnan(top) or np.isnan(bot): return False
                for k in range(max(0, i-3), i+1):
                    if l15[k] <= top and l15[k] >= bot: return True
                return False

            def check_fvg_tap_bear():
                top, bot = h1_bear_fvg_top[i], h1_bear_fvg_bot[i]
                if np.isnan(top) or np.isnan(bot): return False
                for k in range(max(0, i-3), i+1):
                    if h15[k] >= bot and h15[k] <= top: return True
                return False

            bull_grab = (check_sweep_bull(pdl[i]) or check_sweep_bull(asia_l_arr[i]) or 
                         check_sweep_bull(lon_l_arr[i]) or check_sweep_bull(ny_am_l_arr[i]) or 
                         check_sweep_bull(h1_low[i]) or check_sweep_bull(h4_low[i]) or check_fvg_tap_bull())

            bear_grab = (check_sweep_bear(pdh[i]) or check_sweep_bear(asia_h_arr[i]) or 
                         check_sweep_bear(lon_h_arr[i]) or check_sweep_bear(ny_am_h_arr[i]) or 
                         check_sweep_bear(h1_high[i]) or check_sweep_bear(h4_high[i]) or check_fvg_tap_bear())

            if sig == 1 and not bull_grab:
                continue
            if sig == -1 and not bear_grab:
                continue

            has_fvg = (sig == 1 and l0 > h2) or (sig == -1 and h0 < l2)
            fvg_top = l0 if (sig == 1 and l0 > h2) else (l2 if (sig == -1 and h0 < l2) else np.nan)
            fvg_bot = h2 if (sig == 1 and l0 > h2) else (h0 if (sig == -1 and h0 < l2) else np.nan)
            htf_displacements.append({
                "time": df_15m.index[i], "dir": sig, "has_fvg": has_fvg,
                "fvg_top": fvg_top, "fvg_bot": fvg_bot, "ob_level": bagholder
            })

    # TTrades 1m Execution
    trade_records = []
    for disp in htf_displacements:
        t_disp, d = disp["time"], disp["dir"]
        zone_high = disp["fvg_top"] if disp["has_fvg"] else max(disp["ob_level"], disp["ob_level"] + 5.0)
        zone_low = disp["fvg_bot"] if disp["has_fvg"] else min(disp["ob_level"], disp["ob_level"] - 5.0)

        idx1 = times_1m.searchsorted(t_disp)
        if idx1 >= n1 - 180:
            continue

        wick_tapped = False
        tap_idx = -1
        for m in range(idx1 + 1, min(n1, idx1 + 15)):
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
            trade_records.append({
                "time": times_1m[entry_bar], "dir": "LONG" if d == 1 else "SHORT",
                "entry": entry_p, "sl": sl_p, "pnl_bps": pnl_bps, "q_hit": q_hit, "r_hit": r_hit
            })

    tdf = pd.DataFrame(trade_records)
    if len(tdf) == 0:
        print("No trades generated.")
        return

    pnl = tdf["pnl_bps"].to_numpy()
    wins = (pnl > 0).sum()
    total = len(pnl)
    wr = (wins / total) * 100.0
    gp = pnl[pnl > 0].sum()
    gl = abs(pnl[pnl < 0].sum())
    pf = gp / gl if gl > 0 else np.nan

    cum = np.cumsum(pnl)
    peaks = np.maximum.accumulate(cum)
    dd = peaks - cum
    max_dd = np.max(dd) if len(dd) > 0 else 0

    print(f"\n📊 FINAL AUDIT PERFORMANCE:")
    print(f"  • Total Trades:         {total}")
    print(f"  • Win Rate:             {wr:.1f}% ({wins} wins / {total - wins} losses)")
    print(f"  • Profit Factor:        {pf:.2f}")
    print(f"  • Total Return:         {cum[-1]:+.1f} bps")
    print(f"  • Expectancy:           {np.mean(pnl):+.2f} bps/trade")
    print(f"  • Max Drawdown:         -{max_dd:.1f} bps")
    print(f"  • Queen Hit Rate (+10): {(tdf['q_hit'].sum() / total) * 100:.1f}%")
    print(f"  • Runner Hit Rate (+30):{(tdf['r_hit'].sum() / total) * 100:.1f}%")

    print("\nSAMPLE RECENT TRADES:")
    print(tdf[["time", "dir", "entry", "sl", "pnl_bps", "q_hit", "r_hit"]].tail(10).to_string(index=False))

if __name__ == "__main__":
    validate_asset("NQ", "2025-01-01")
    validate_asset("ES", "2025-01-01")
