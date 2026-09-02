"""
TTrades "Let the Wick Form, Trade the Body" Mechanical Backtest:
Step 1: HTF CISD (Extreme Open Reclaim)
Step 2: HTF Displacement Confirmation (5m / 15m FVG or iFVG)
Step 3: "Let the Wick Form" -> Pullback into the HTF PD Array (FVG / OB)
Step 4: Wick Confirmation -> 1m Micro-reversal / 1m FVG confirming the Protected Swing
Step 5: "Trade the Body" -> Enter with Stop Loss at Protected Swing, Target Queen (+10 bps) and Runner (+30 bps)
"""

import pandas as pd
import numpy as np
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def run_ttrades_simulation(htf_minutes=5):
    print("="*95)
    print(f"TESTING TTRADES ALGORITHM: HTF = {htf_minutes}m | LTF = 1m (NQ 2025-2026)")
    print("="*95)

    df_1m = pd.read_parquet("data/NQ1_1m.parquet")
    df_1m = df_1m.loc["2025-01-01":].copy()
    times_1m = df_1m.index
    c1, o1, h1, l1 = df_1m["close"].to_numpy(), df_1m["open"].to_numpy(), df_1m["high"].to_numpy(), df_1m["low"].to_numpy()
    n1 = len(df_1m)

    # Resample to HTF
    resample_rule = f"{htf_minutes}min"
    df_htf = df_1m.resample(resample_rule).agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    # 4H EMA(50) for overall macro trend alignment
    df_4h = df_1m.resample("4h").agg({"close": "last"}).dropna()
    df_4h["ema50"] = df_4h["close"].ewm(span=50).mean()
    ema_htf = df_4h["ema50"].reindex(df_htf.index, method="ffill").bfill()
    df_htf["htf_bias"] = np.where(df_htf["close"] >= ema_htf, 1, -1)

    c_h, o_h, h_h, l_h = df_htf["close"].to_numpy(), df_htf["open"].to_numpy(), df_htf["high"].to_numpy(), df_htf["low"].to_numpy()
    htf_bias = df_htf["htf_bias"].to_numpy()
    times_htf = df_htf.index
    time_strs_htf = times_htf.strftime("%H%M")
    nh = len(df_htf)

    # 1. Detect HTF CISD + Displacement (FVG)
    vibes = 0
    bagholder = np.nan
    pain = np.nan

    def consult_cb(b, cur_idx):
        max_lb = min(15, cur_idx)
        ext_o = o_h[cur_idx - 1]
        for step in range(1, max_lb + 1):
            is_opp = (c_h[cur_idx - step] < o_h[cur_idx - step]) if b == 1 else (c_h[cur_idx - step] > o_h[cur_idx - step])
            if is_opp:
                ext_o = o_h[cur_idx - step]
                break
        return ext_o

    htf_displacements = []

    for i in range(50, nh - 60):
        hhmm = time_strs_htf[i]
        c0, o0, h0, l0 = c_h[i], o_h[i], h_h[i], l_h[i]
        h2, l2 = h_h[i - 2], l_h[i - 2]

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

        # CISD Check
        sig = 0
        if vibes == -1 and c0 > bagholder and in_time and htf_bias[i] == 1:
            vibes = 1
            pain = h0
            bagholder = consult_cb(1, i)
            sig = 1
        elif vibes == 1 and c0 < bagholder and in_time and htf_bias[i] == -1:
            vibes = -1
            pain = l0
            bagholder = consult_cb(-1, i)
            sig = -1

        if sig != 0:
            # Step 2: Displacement check -> Was an FVG formed during this shift?
            has_fvg = False
            fvg_top, fvg_bot = np.nan, np.nan

            if sig == 1 and l0 > h2:
                has_fvg = True
                fvg_top = l0
                fvg_bot = h2
            elif sig == -1 and h0 < l2:
                has_fvg = True
                fvg_top = l2
                fvg_bot = h0

            # Even if bar i wasn't an FVG, check bar i-1 or the Order Block
            ob_level = bagholder
            htf_displacements.append({
                "bar_idx": i,
                "time": times_htf[i],
                "dir": sig,
                "has_fvg": has_fvg,
                "fvg_top": fvg_top,
                "fvg_bot": fvg_bot,
                "ob_level": ob_level,
            })

    print(f"Total HTF Displacements Identified: {len(htf_displacements):,d}")

    # Now test 3 variations of TTrades execution:
    # Option A: Wait for Wick to tap HTF FVG/OB -> 1m Candle turns (reversal confirmation) -> SL at Protected Swing
    # Option B: Wait for Wick to tap HTF FVG/OB -> 1m FVG forms in direction of trend -> SL at Protected Swing
    # Option C: Direct 5.0 bps stop at Protected Swing

    for opt in ["A_1m_candle_turn", "B_1m_fvg_confirmation", "C_5bps_fixed"]:
        trades = []

        for disp in htf_displacements:
            t_disp = disp["time"]
            d = disp["dir"]
            has_fvg = disp["has_fvg"]
            fvg_top = disp["fvg_top"]
            fvg_bot = disp["fvg_bot"]
            ob_lvl = disp["ob_level"]

            # Define the PD Array zone (the orange box in TTrades PDF)
            if has_fvg:
                zone_high = fvg_top
                zone_low = fvg_bot
            else:
                zone_high = max(disp["ob_level"], disp["ob_level"] + 10.0) if d == 1 else disp["ob_level"]
                zone_low = disp["ob_level"] if d == 1 else min(disp["ob_level"], disp["ob_level"] - 10.0)

            # Map to 1m data
            idx1 = times_1m.searchsorted(t_disp)
            if idx1 >= n1 - 180:
                continue

            # Step 3: "Let the Wick Form"
            # We look for price to enter the PD Array zone within the next 20 1-minute bars
            wick_tapped = False
            tap_idx = -1
            protected_swing = np.nan

            for m in range(idx1 + 1, min(n1, idx1 + 25)):
                if d == 1:
                    # Pulling back into bullish PD Array
                    if l1[m] <= zone_high:
                        wick_tapped = True
                        tap_idx = m
                        break
                else:
                    # Pulling back into bearish PD Array
                    if h1[m] >= zone_low:
                        wick_tapped = True
                        tap_idx = m
                        break

            if not wick_tapped:
                continue

            # Step 4: Wick Confirmation inside or rejecting the PD Array
            # Find the local Protected Swing (the lowest point of the wick for longs, highest for shorts)
            entered = False
            entry_p = np.nan
            sl_p = np.nan
            entry_bar = -1

            if opt == "A_1m_candle_turn":
                # Wait for the first 1m candle to close back in trend direction after tapping zone
                for k in range(tap_idx, min(n1, tap_idx + 10)):
                    if d == 1 and c1[k] > o1[k]: # Green 1m candle after tap
                        entry_p = c1[k]
                        protected_swing = np.min(l1[tap_idx:k+1])
                        sl_p = protected_swing - 1.0 # 1 pt below protected swing
                        entered = True
                        entry_bar = k
                        break
                    elif d == -1 and c1[k] < o1[k]: # Red 1m candle after tap
                        entry_p = c1[k]
                        protected_swing = np.max(h1[tap_idx:k+1])
                        sl_p = protected_swing + 1.0 # 1 pt above protected swing
                        entered = True
                        entry_bar = k
                        break

            elif opt == "B_1m_fvg_confirmation":
                # Wait for a 1m FVG to form in trend direction after tapping zone
                for k in range(tap_idx + 2, min(n1, tap_idx + 15)):
                    if d == 1 and l1[k] > h1[k - 2]: # 1m Bullish FVG
                        entry_p = c1[k]
                        protected_swing = np.min(l1[tap_idx:k+1])
                        sl_p = protected_swing - 1.0
                        entered = True
                        entry_bar = k
                        break
                    elif d == -1 and h1[k] < l1[k - 2]: # 1m Bearish FVG
                        entry_p = c1[k]
                        protected_swing = np.max(h1[tap_idx:k+1])
                        sl_p = protected_swing + 1.0
                        entered = True
                        entry_bar = k
                        break

            elif opt == "C_5bps_fixed":
                # Enter on tap with 5.0 bps stop
                entry_p = zone_high if d == 1 else zone_low
                sl_p = entry_p - (entry_p * 0.0005) if d == 1 else entry_p + (entry_p * 0.0005)
                entered = True
                entry_bar = tap_idx

            if entered:
                risk_pts = abs(entry_p - sl_p)
                # Cap risk between 3.0 bps and 10.0 bps
                risk_bps = (risk_pts / entry_p) * 10000.0
                if risk_bps < 2.0 or risk_bps > 12.0:
                    continue

                tp1_p = entry_p + (entry_p * 0.0010) if d == 1 else entry_p - (entry_p * 0.0010) # +10 bps Queen
                tp2_p = entry_p + (entry_p * 0.0030) if d == 1 else entry_p - (entry_p * 0.0030) # +30 bps Runner

                q_hit, r_hit, active_sl, exit_p = False, False, sl_p, entry_p
                for step in range(entry_bar + 1, min(n1, entry_bar + 180)):
                    bh, bl = h1[step], l1[step]
                    if d == 1:
                        if not q_hit and bh >= tp1_p:
                            q_hit = True; active_sl = entry_p # Lock BE
                        if bl <= active_sl:
                            exit_p = active_sl; break
                        if bh >= tp2_p:
                            r_hit = True; exit_p = tp2_p; break
                    else:
                        if not q_hit and bl <= tp1_p:
                            q_hit = True; active_sl = entry_p # Lock BE
                        if bh >= active_sl:
                            exit_p = active_sl; break
                        if bl <= tp2_p:
                            r_hit = True; exit_p = tp2_p; break

                q_pts = (tp1_p - entry_p) if q_hit else (exit_p - entry_p if d == 1 else entry_p - exit_p)
                r_pts = (exit_p - entry_p) if d == 1 else (entry_p - exit_p)
                pnl_pts = (q_pts + r_pts) / 2.0
                pnl_bps = (pnl_pts / entry_p) * 10000.0 * d
                trades.append({
                    "pnl_bps": pnl_bps,
                    "is_win": pnl_bps > 0,
                    "q_hit": q_hit,
                    "r_hit": r_hit,
                    "risk_bps": risk_bps,
                })

        arr_pnl = np.array([t["pnl_bps"] for t in trades])
        wins = arr_pnl > 0
        wr = wins.mean() * 100.0 if len(arr_pnl) > 0 else 0
        q_rate = np.mean([t["q_hit"] for t in trades]) * 100.0 if len(trades) > 0 else 0
        avg_risk = np.mean([t["risk_bps"] for t in trades]) if len(trades) > 0 else 0
        gp = arr_pnl[arr_pnl > 0].sum()
        gl = abs(arr_pnl[arr_pnl < 0].sum())
        pf = gp / gl if gl > 0 else np.nan

        print(f"\nExecution Mode: {opt}")
        print(f"  Total Trades:             {len(arr_pnl)}")
        print(f"  Average Risk (Stop):      {avg_risk:.1f} bps (~{avg_risk * 3.0:.1f} pts NQ)")
        print(f"  Queen Target (+10 bps):   {q_rate:.1f}%")
        print(f"  Net Win Rate:             {wr:.1f}%")
        print(f"  Profit Factor:            {pf:.2f}")
        print(f"  Expectancy:               {arr_pnl.mean():+.2f} bps/trade")


if __name__ == "__main__":
    run_ttrades_simulation(htf_minutes=5)
    run_ttrades_simulation(htf_minutes=15)
