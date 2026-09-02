"""
Cross-Platform Parity Validation: Exactly matching NT8 Run #0 (2026-01-01 to 2026-08-01)
"""

import pandas as pd
import numpy as np

def validate_2026(asset="NQ", htf_min=15):
    file_path = f"data/{asset}1_1m.parquet"
    df_1m = pd.read_parquet(file_path)
    df_1m = df_1m.loc["2026-01-01":"2026-08-01"].copy()

    times_1m = df_1m.index
    c1, o1, h1, l1 = df_1m["close"].to_numpy(), df_1m["open"].to_numpy(), df_1m["high"].to_numpy(), df_1m["low"].to_numpy()
    n1 = len(df_1m)

    df_5m = df_1m.resample(f"{htf_min}min").agg({
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

    htf_displacements = []
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
            has_fvg = (sig == 1 and l0 > h2) or (sig == -1 and h0 < l2)
            fvg_top = l0 if (sig == 1 and l0 > h2) else (l2 if (sig == -1 and h0 < l2) else np.nan)
            fvg_bot = h2 if (sig == 1 and l0 > h2) else (h0 if (sig == -1 and h0 < l2) else np.nan)
            htf_displacements.append({
                "time": times_5m[i], "dir": sig, "has_fvg": has_fvg,
                "fvg_top": fvg_top, "fvg_bot": fvg_bot, "ob_level": bagholder
            })

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
            pt_val = 20.0 if asset == "NQ" else 50.0
            # 2 contracts: 1 Queen + 1 Runner
            pnl_usd = (q_pts * pt_val) + (r_pts * pt_val) - 5.60 # commissions
            trades.append({
                "pnl_usd": pnl_usd,
                "is_win": pnl_usd > 0,
                "q_hit": q_hit,
                "r_hit": r_hit,
            })

    df_tr = pd.DataFrame(trades)
    wins = df_tr["pnl_usd"] > 0
    wr = wins.mean() * 100.0 if len(df_tr) > 0 else 0
    gp = df_tr.loc[df_tr["pnl_usd"] > 0, "pnl_usd"].sum()
    gl = abs(df_tr.loc[df_tr["pnl_usd"] < 0, "pnl_usd"].sum())
    pf = gp / gl if gl > 0 else np.nan
    net = df_tr["pnl_usd"].sum()
    print(f"\n=========================================================================")
    print(f"PYTHON VALIDATION: {asset} (2026-01-01 to 2026-08-01)")
    print(f"=========================================================================")
    print(f"Total Entries:      {len(df_tr)} entries ({len(df_tr)*2} contracts)")
    print(f"Entry Win Rate:     {wr:.1f}%")
    print(f"Queen Reach (+10):  {df_tr['q_hit'].mean()*100.0:.1f}% (Locks Breakeven)")
    print(f"Profit Factor:      {pf:.3f}")
    print(f"Net Realized P&L:   ${net:,.2f}")
    print(f"=========================================================================")

if __name__ == "__main__":
    validate_2026("NQ", 15)
    validate_2026("ES", 15)
