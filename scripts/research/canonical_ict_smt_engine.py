"""
Canonical ICT SMT Engine
========================
High-Conviction Institutional ICT Setup:
1. Major HTF Liquidity Grab (NY PM H/L, London H/L, Asia H/L, PDH/PDL, 4H H/L, or HTF FVG/OB)
2. SMT Divergence Confirmation (NQ vs ES crack in correlation)
3. Structural CISD Shift (5m)
4. 2nd Stage of Distribution Retest into OB, FVG, or iFVG
5. Liquidity-Calibrated Target (Opposing BSL/SSL) with Reversal Warning
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

OUTPUT_DIR = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/scratch/charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def check_bullish_smt(nq_sweep_bar, es_df, prev_nq_anchor, prev_es_anchor, t5):
    """
    Evaluates Bullish SMT Divergence between NQ and ES.
    Case A: NQ sweeps key low (makes lower low), while ES holds higher low above its corresponding anchor.
    Case B: ES sweeps key low (makes lower low), while NQ holds higher low.
    """
    if t5 not in es_df.index:
        return False, ""
    
    es_bar = es_df.loc[t5]
    
    # Check if anchors are available
    if not np.isnan(prev_nq_anchor) and not np.isnan(prev_es_anchor):
        nq_swept = (nq_sweep_bar["low"] <= prev_nq_anchor)
        es_swept = (es_bar["low"] <= prev_es_anchor)
        
        if nq_swept and not es_swept:
            diff_es = es_bar["low"] - prev_es_anchor
            return True, f"NQ Swept ({nq_sweep_bar['low']:.1f} <= {prev_nq_anchor:.1f}) | ES Held Higher ({es_bar['low']:.2f} > {prev_es_anchor:.2f}, +{diff_es:.2f} pts)"
        elif not nq_swept and es_swept:
            diff_nq = nq_sweep_bar["low"] - prev_nq_anchor
            return True, f"ES Swept ({es_bar['low']:.2f} <= {prev_es_anchor:.2f}) | NQ Held Higher ({nq_sweep_bar['low']:.1f} > {prev_nq_anchor:.1f}, +{diff_nq:.1f} pts)"
    
    # Fallback to rolling swing low divergence over past 30-60 mins
    window_es = es_df.loc[t5 - pd.Timedelta(minutes=45):t5]
    if len(window_es) >= 5:
        es_min = window_es["low"].min()
        # If ES made a higher low while NQ is at lows
        if es_bar["low"] > es_min + 1.0:
            return True, f"ES Higher Low ({es_bar['low']:.2f} vs swing low {es_min:.2f})"
            
    return False, ""

def check_bearish_smt(nq_sweep_bar, es_df, prev_nq_anchor, prev_es_anchor, t5):
    """
    Evaluates Bearish SMT Divergence between NQ and ES.
    Case A: NQ sweeps key high (makes higher high), while ES holds lower high below its corresponding anchor.
    Case B: ES sweeps key high (makes higher high), while NQ holds lower high.
    """
    if t5 not in es_df.index:
        return False, ""
    
    es_bar = es_df.loc[t5]
    
    if not np.isnan(prev_nq_anchor) and not np.isnan(prev_es_anchor):
        nq_swept = (nq_sweep_bar["high"] >= prev_nq_anchor)
        es_swept = (es_bar["high"] >= prev_es_anchor)
        
        if nq_swept and not es_swept:
            diff_es = prev_es_anchor - es_bar["high"]
            return True, f"NQ Swept ({nq_sweep_bar['high']:.1f} >= {prev_nq_anchor:.1f}) | ES Held Lower ({es_bar['high']:.2f} < {prev_es_anchor:.2f}, -{diff_es:.2f} pts)"
        elif not nq_swept and es_swept:
            diff_nq = prev_nq_anchor - nq_sweep_bar["high"]
            return True, f"ES Swept ({es_bar['high']:.2f} >= {prev_es_anchor:.2f}) | NQ Held Lower ({nq_sweep_bar['high']:.1f} < {prev_nq_anchor:.1f}, -{diff_nq:.1f} pts)"
            
    window_es = es_df.loc[t5 - pd.Timedelta(minutes=45):t5]
    if len(window_es) >= 5:
        es_max = window_es["high"].max()
        if es_bar["high"] < es_max - 1.0:
            return True, f"ES Lower High ({es_bar['high']:.2f} vs swing high {es_max:.2f})"

    return False, ""

def run_smt_audit(target_date="2026-08-28"):
    print("=" * 110)
    print(f"CANONICAL ICT WITH SMT DIVERGENCE AUDIT: {target_date}")
    print("=" * 110)

    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    df_es = pd.read_parquet("data/ES_recent_week.parquet").sort_index()

    df_nq["date"] = df_nq.index.date
    df_nq["hhmm"] = df_nq.index.strftime("%H%M")
    df_es["date"] = df_es.index.date
    df_es["hhmm"] = df_es.index.strftime("%H%M")

    target_d = pd.to_datetime(target_date).date()
    prev_dates = sorted([d for d in df_nq["date"].unique() if d < target_d])
    if not prev_dates:
        return None
    prev_d = prev_dates[-1]

    # Target Day Data
    nq_day = df_nq[df_nq["date"] == target_d].copy()
    es_day = df_es[df_es["date"] == target_d].copy()
    if nq_day.empty or es_day.empty:
        return None

    # Resample to 5m
    nq_5m = nq_day.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    es_5m = es_day.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # Previous Day Anchors for NQ and ES
    nq_prev = df_nq[df_nq["date"] == prev_d]
    es_prev = df_es[df_es["date"] == prev_d]

    # NY PM Low & High (13:30 - 16:00 ET)
    nq_pm = nq_prev[(nq_prev["hhmm"] >= "1330") & (nq_prev["hhmm"] <= "1600")]
    es_pm = es_prev[(es_prev["hhmm"] >= "1330") & (es_prev["hhmm"] <= "1600")]
    nq_pm_low = nq_pm["low"].min() if not nq_pm.empty else np.nan
    nq_pm_high = nq_pm["high"].max() if not nq_pm.empty else np.nan
    es_pm_low = es_pm["low"].min() if not es_pm.empty else np.nan
    es_pm_high = es_pm["high"].max() if not es_pm.empty else np.nan

    # London Low & High (02:00 - 05:00 ET)
    nq_lon = nq_day[(nq_day["hhmm"] >= "0200") & (nq_day["hhmm"] < "0500")]
    es_lon = es_day[(es_day["hhmm"] >= "0200") & (es_day["hhmm"] < "0500")]
    nq_lon_low = nq_lon["low"].min() if not nq_lon.empty else np.nan
    nq_lon_high = nq_lon["high"].max() if not nq_lon.empty else np.nan
    es_lon_low = es_lon["low"].min() if not es_lon.empty else np.nan
    es_lon_high = es_lon["high"].max() if not es_lon.empty else np.nan

    # PDH / PDL
    nq_pdl = nq_prev["low"].min()
    nq_pdh = nq_prev["high"].max()
    es_pdl = es_prev["low"].min()
    es_pdh = es_prev["high"].max()

    print("Major Anchors:")
    print(f"  • NQ NY PM Low: {nq_pm_low:.2f} | ES NY PM Low: {es_pm_low:.2f}")
    print(f"  • NQ London Low: {nq_lon_low:.2f} | ES London Low: {es_lon_low:.2f}")
    print(f"  • NQ PDL: {nq_pdl:.2f} | ES PDL: {es_pdl:.2f}")

    # Execution Loop
    trades = []
    active_sweep = None
    last_down_open = np.nan
    last_up_open = np.nan
    last_down_bar = None
    last_up_bar = None
    mitigated_anchors = set()

    for i in range(len(nq_5m)):
        t5 = nq_5m.index[i]
        hhmm5 = t5.strftime("%H%M")
        c5, o5, h5, l5 = nq_5m["close"].iloc[i], nq_5m["open"].iloc[i], nq_5m["high"].iloc[i], nq_5m["low"].iloc[i]
        h5_2 = nq_5m["high"].iloc[i-2] if i >= 2 else np.nan
        l5_2 = nq_5m["low"].iloc[i-2] if i >= 2 else np.nan

        # Session Boundary Reset: Each institutional session gets a fresh opportunity to sweep key pools
        if hhmm5 in ["0200", "0930", "1330"]:
            mitigated_anchors.clear()

        if c5 < o5:
            last_down_open = o5
            last_down_bar = {"open": o5, "high": h5, "low": l5, "close": c5, "time": t5}
        elif c5 > o5:
            last_up_open = o5
            last_up_bar = {"open": o5, "high": h5, "low": l5, "close": c5, "time": t5}

        # Expiration / Invalidation
        if active_sweep:
            if active_sweep["type"] == "BEAR" and h5 > active_sweep["extreme"]:
                active_sweep = None
            elif active_sweep["type"] == "BULL" and l5 < active_sweep["extreme"]:
                active_sweep = None
            elif (i - active_sweep["bar_idx"]) > 8:
                active_sweep = None

        # Sweep Detection with SMT Divergence Requirement
        if active_sweep is None:
            # Bullish Major Pools
            bull_anchors = [
                ("NY PM Low", nq_pm_low, es_pm_low),
                ("London Low", nq_lon_low, es_lon_low),
                ("PDL", nq_pdl, es_pdl)
            ]
            for name, nq_lvl, es_lvl in bull_anchors:
                if not np.isnan(nq_lvl) and name not in mitigated_anchors:
                    is_wick_reject = (l5 <= nq_lvl and c5 > nq_lvl)
                    is_reclaim = (i > 0 and nq_5m["low"].iloc[i-1] <= nq_lvl and nq_5m["close"].iloc[i-1] <= nq_lvl and c5 > nq_lvl)
                    prior_closes_below = sum(nq_5m["close"].iloc[max(0, i-4):i] < nq_lvl)

                    if (is_wick_reject or is_reclaim) and prior_closes_below <= 1:
                        smt_valid, smt_detail = check_bullish_smt(nq_5m.iloc[i], es_5m, nq_lvl, es_lvl, t5)
                        if smt_valid:
                            active_sweep = {
                                "type": "BULL", "anchor": name, "level": nq_lvl,
                                "time": t5, "bar_idx": i, "extreme": l5,
                                "smt_detail": smt_detail
                            }
                            mitigated_anchors.add(name) # Mark level as mitigated!
                            break

            # Bearish Major Pools
            if active_sweep is None:
                bear_anchors = [
                    ("NY PM High", nq_pm_high, es_pm_high),
                    ("London High", nq_lon_high, es_lon_high),
                    ("PDH", nq_pdh, es_pdh)
                ]
                for name, nq_lvl, es_lvl in bear_anchors:
                    if not np.isnan(nq_lvl) and name not in mitigated_anchors:
                        is_wick_reject = (h5 >= nq_lvl and c5 < nq_lvl)
                        is_reclaim = (i > 0 and nq_5m["high"].iloc[i-1] >= nq_lvl and nq_5m["close"].iloc[i-1] >= nq_lvl and c5 < nq_lvl)
                        prior_closes_above = sum(nq_5m["close"].iloc[max(0, i-4):i] > nq_lvl)

                        if (is_wick_reject or is_reclaim) and prior_closes_above <= 1:
                            smt_valid, smt_detail = check_bearish_smt(nq_5m.iloc[i], es_5m, nq_lvl, es_lvl, t5)
                            if smt_valid:
                                active_sweep = {
                                    "type": "BEAR", "anchor": name, "level": nq_lvl,
                                    "time": t5, "bar_idx": i, "extreme": h5,
                                    "smt_detail": smt_detail
                                }
                                mitigated_anchors.add(name) # Mark level as mitigated!
                                break

        # CISD Shift Confirmation: Require genuine displacement depth (>= 12 pts)
        if active_sweep and (i - active_sweep["bar_idx"]) <= 8:
            if active_sweep["type"] == "BULL" and not np.isnan(last_down_open) and c5 > last_down_open:
                displacement_depth = c5 - active_sweep["extreme"]
                if displacement_depth < 12.0: # Filter small chop wiggles
                    continue
                cisd_level = last_down_open
                cisd_time = t5

                # 2nd Stage OB / FVG / iFVG Retest Zone
                ob_high = last_down_bar["high"] if last_down_bar else cisd_level
                ob_low = last_down_bar["low"] if last_down_bar else min(o5, c5)
                has_fvg = (l5 > h5_2) if not np.isnan(h5_2) else False
                fvg_top = l5 if has_fvg else max(c5, cisd_level)
                fvg_bot = h5_2 if has_fvg else min(o5, cisd_level)

                retest_top = max(ob_high, fvg_top)
                retest_bot = min(ob_low, fvg_bot)

                # Opposing Target: Next Key HTF High
                bsl_targets = [p for p in [nq_pdh, nq_pm_high, nq_lon_high] if not np.isnan(p) and p > c5]
                session_h = nq_5m["high"].iloc[:i+1].max()
                if session_h > c5: bsl_targets.append(session_h)
                opposing_target = min(bsl_targets) if bsl_targets else c5 + (c5 * 0.0030)

                # 1m Retest Check
                m1_window = nq_day.loc[t5:t5 + pd.Timedelta(minutes=35)]
                tapped, tap_idx = False, -1
                for m in range(1, len(m1_window)):
                    if m1_window.iloc[m]["low"] <= retest_top:
                        tapped = True
                        tap_idx = m
                        break

                if tapped:
                    for k in range(tap_idx, min(len(m1_window), tap_idx + 15)):
                        k_row = m1_window.iloc[k]
                        k_time = m1_window.index[k]

                        if k_row["close"] > k_row["open"]:
                            entry_p = k_row["close"]
                            protected_swing = m1_window.iloc[tap_idx:k+1]["low"].min()
                            sl_p = protected_swing - 1.0
                            risk_pts = entry_p - sl_p
                            risk_bps = (risk_pts / entry_p) * 10000.0

                            if 2.0 <= risk_bps <= 15.0:
                                tp1_p = entry_p + (entry_p * 0.0010)
                                tp2_p = opposing_target

                                sim_bars = nq_day.loc[k_time:]
                                q_hit, r_hit = False, False
                                active_sl = sl_p
                                exit_time = None

                                for s in range(1, len(sim_bars)):
                                    sb = sim_bars.iloc[s]
                                    if not q_hit and sb["high"] >= tp1_p:
                                        q_hit = True
                                        active_sl = entry_p
                                    if sb["low"] <= active_sl:
                                        exit_time = sim_bars.index[s]
                                        break
                                    if sb["high"] >= tp2_p:
                                        r_hit = True
                                        exit_time = sim_bars.index[s]
                                        break

                                trades.append({
                                    "direction": "BUY LONG",
                                    "anchor_name": active_sweep["anchor"],
                                    "anchor_level": active_sweep["level"],
                                    "smt_detail": active_sweep["smt_detail"],
                                    "sweep_time": active_sweep["time"],
                                    "cisd_level": cisd_level,
                                    "cisd_time": cisd_time,
                                    "retest_top": retest_top,
                                    "retest_bot": retest_bot,
                                    "entry_time": k_time,
                                    "entry_price": entry_p,
                                    "sl_price": sl_p,
                                    "tp1_price": tp1_p,
                                    "tp2_price": tp2_p,
                                    "opposing_target_name": f"BSL ({opposing_target:.2f})",
                                    "risk_bps": risk_bps,
                                    "q_hit": q_hit,
                                    "r_hit": r_hit,
                                    "exit_time": exit_time
                                })
                                active_sweep = None
                                break

            elif active_sweep["type"] == "BEAR" and not np.isnan(last_up_open) and c5 < last_up_open:
                displacement_depth = active_sweep["extreme"] - c5
                if displacement_depth < 12.0:
                    continue
                cisd_level = last_up_open
                cisd_time = t5

                ob_high = last_up_bar["high"] if last_up_bar else cisd_level
                ob_low = last_up_bar["low"] if last_up_bar else min(o5, c5)
                has_fvg = (h5 < l5_2) if not np.isnan(l5_2) else False
                fvg_top = l5_2 if has_fvg else max(o5, cisd_level)
                fvg_bot = h5 if has_fvg else min(c5, cisd_level)

                retest_top = max(ob_high, fvg_top)
                retest_bot = min(ob_low, fvg_bot)

                ssl_targets = [p for p in [nq_pdl, nq_pm_low, nq_lon_low] if not np.isnan(p) and p < c5]
                session_l = nq_5m["low"].iloc[:i+1].min()
                if session_l < c5: ssl_targets.append(session_l)
                opposing_target = max(ssl_targets) if ssl_targets else c5 - (c5 * 0.0030)

                m1_window = nq_day.loc[t5:t5 + pd.Timedelta(minutes=35)]
                tapped, tap_idx = False, -1
                for m in range(1, len(m1_window)):
                    if m1_window.iloc[m]["high"] >= retest_bot:
                        tapped = True
                        tap_idx = m
                        break

                if tapped:
                    for k in range(tap_idx, min(len(m1_window), tap_idx + 15)):
                        k_row = m1_window.iloc[k]
                        k_time = m1_window.index[k]

                        if k_row["close"] < k_row["open"]:
                            entry_p = k_row["close"]
                            protected_swing = m1_window.iloc[tap_idx:k+1]["high"].max()
                            sl_p = protected_swing + 1.0
                            risk_pts = sl_p - entry_p
                            risk_bps = (risk_pts / entry_p) * 10000.0

                            if 2.0 <= risk_bps <= 15.0:
                                tp1_p = entry_p - (entry_p * 0.0010)
                                tp2_p = opposing_target

                                sim_bars = nq_day.loc[k_time:]
                                q_hit, r_hit = False, False
                                active_sl = sl_p
                                exit_time = None

                                for s in range(1, len(sim_bars)):
                                    sb = sim_bars.iloc[s]
                                    if not q_hit and sb["low"] <= tp1_p:
                                        q_hit = True
                                        active_sl = entry_p
                                    if sb["high"] >= active_sl:
                                        exit_time = sim_bars.index[s]
                                        break
                                    if sb["low"] <= tp2_p:
                                        r_hit = True
                                        exit_time = sim_bars.index[s]
                                        break

                                trades.append({
                                    "direction": "SELL SHORT",
                                    "anchor_name": active_sweep["anchor"],
                                    "anchor_level": active_sweep["level"],
                                    "smt_detail": active_sweep["smt_detail"],
                                    "sweep_time": active_sweep["time"],
                                    "cisd_level": cisd_level,
                                    "cisd_time": cisd_time,
                                    "retest_top": retest_top,
                                    "retest_bot": retest_bot,
                                    "entry_time": k_time,
                                    "entry_price": entry_p,
                                    "sl_price": sl_p,
                                    "tp1_price": tp1_p,
                                    "tp2_price": tp2_p,
                                    "opposing_target_name": f"SSL ({opposing_target:.2f})",
                                    "risk_bps": risk_bps,
                                    "q_hit": q_hit,
                                    "r_hit": r_hit,
                                    "exit_time": exit_time
                                })
                                active_sweep = None
                                break

    print(f"\nHIGH-CONVICTION SMT TRADES FOR {target_date}: {len(trades)} trades")
    for tr in trades:
        print(f"  ★ [{tr['direction']}] @ {tr['entry_time'].strftime('%H:%M ET')} | Entry: {tr['entry_price']:.2f}")
        print(f"    • Anchor Swept: {tr['anchor_name']} ({tr['anchor_level']:.2f}) at {tr['sweep_time'].strftime('%H:%M ET')}")
        print(f"    • SMT Divergence: {tr['smt_detail']}")
        print(f"    • CISD Shift Level: {tr['cisd_level']:.2f} at {tr['cisd_time'].strftime('%H:%M ET')}")
        print(f"    • 2nd Stage Retest (OB/FVG/iFVG): [{tr['retest_bot']:.2f}, {tr['retest_top']:.2f}]")
        print(f"    • Stop Loss: {tr['sl_price']:.2f} ({tr['risk_bps']:.1f} bps)")
        print(f"    • Target 1 (+10 bps): {tr['q_hit']}")
        print(f"    • Liquidity Target: {tr['opposing_target_name']} | Hit: {tr['r_hit']}")

    # Render High-Resolution 2-Panel Chart (NQ + ES SMT Subpanel)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 11), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
    width = 0.0004
    width2 = 0.00008

    df_plot_nq = nq_day[(nq_day["hhmm"] >= "0800") & (nq_day["hhmm"] <= "1530")].copy()
    df_plot_es = es_day[(es_day["hhmm"] >= "0800") & (es_day["hhmm"] <= "1530")].copy()
    if df_plot_nq.empty: df_plot_nq = nq_day.copy()
    if df_plot_es.empty: df_plot_es = es_day.copy()

    # NQ Panel
    up_nq = df_plot_nq[df_plot_nq["close"] >= df_plot_nq["open"]]
    dn_nq = df_plot_nq[df_plot_nq["close"] < df_plot_nq["open"]]
    ax1.bar(up_nq.index, up_nq["close"] - up_nq["open"], width, bottom=up_nq["open"], color="#089981", edgecolor="#089981")
    ax1.bar(up_nq.index, up_nq["high"] - up_nq["close"], width2, bottom=up_nq["close"], color="#089981")
    ax1.bar(up_nq.index, up_nq["low"] - up_nq["open"], width2, bottom=up_nq["open"], color="#089981")
    ax1.bar(dn_nq.index, dn_nq["open"] - dn_nq["close"], width, bottom=dn_nq["close"], color="#f23645", edgecolor="#f23645")
    ax1.bar(dn_nq.index, dn_nq["high"] - dn_nq["open"], width2, bottom=dn_nq["open"], color="#f23645")
    ax1.bar(dn_nq.index, dn_nq["low"] - dn_nq["close"], width2, bottom=dn_nq["close"], color="#f23645")

    # ES Panel
    up_es = df_plot_es[df_plot_es["close"] >= df_plot_es["open"]]
    dn_es = df_plot_es[df_plot_es["close"] < df_plot_es["open"]]
    ax2.bar(up_es.index, up_es["close"] - up_es["open"], width, bottom=up_es["open"], color="#089981", edgecolor="#089981")
    ax2.bar(up_es.index, up_es["high"] - up_es["close"], width2, bottom=up_es["close"], color="#089981")
    ax2.bar(up_es.index, up_es["low"] - up_es["open"], width2, bottom=up_es["open"], color="#089981")
    ax2.bar(dn_es.index, dn_es["open"] - dn_es["close"], width, bottom=dn_es["close"], color="#f23645", edgecolor="#f23645")
    ax2.bar(dn_es.index, dn_es["high"] - dn_es["open"], width2, bottom=dn_es["open"], color="#f23645")
    ax2.bar(dn_es.index, dn_es["low"] - dn_es["close"], width2, bottom=dn_es["close"], color="#f23645")

    # Plot Major Anchors
    if not np.isnan(nq_pm_low): ax1.axhline(nq_pm_low, color="#ec4899", linestyle="--", alpha=0.7, label=f"NQ NY PM Low ({nq_pm_low:.1f})")
    if not np.isnan(es_pm_low): ax2.axhline(es_pm_low, color="#ec4899", linestyle="--", alpha=0.7, label=f"ES NY PM Low ({es_pm_low:.2f})")
    if not np.isnan(nq_lon_low): ax1.axhline(nq_lon_low, color="#3b82f6", linestyle=":", alpha=0.7, label=f"NQ London Low ({nq_lon_low:.1f})")
    if not np.isnan(es_lon_low): ax2.axhline(es_lon_low, color="#3b82f6", linestyle=":", alpha=0.7, label=f"ES London Low ({es_lon_low:.2f})")

    # Draw Trade Annotations on NQ
    for tr in trades:
        is_long = tr["direction"] == "BUY LONG"
        col = "#22c55e" if is_long else "#ef4444"

        # Swept Level
        ax1.axhline(tr["anchor_level"], color="#2563eb", linestyle="-.", linewidth=1.5)
        ax1.text(df_plot_nq.index[2], tr["anchor_level"] - (8 if is_long else -8), f"[HTF SWEPT] {tr['anchor_name']} ({tr['anchor_level']:.2f})", color="#2563eb", fontsize=10, fontweight="bold")

        # SMT Badge
        ax1.annotate(f"★ SMT DIVERGENCE CONFIRMED!\n{tr['smt_detail']}",
                     xy=(tr["sweep_time"], tr["anchor_level"]),
                     xytext=(tr["sweep_time"], tr["anchor_level"] - (35 if is_long else -35)),
                     arrowprops=dict(facecolor="#f59e0b", edgecolor="#b45309", width=2, headwidth=8),
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="#fef3c7", edgecolor="#f59e0b", alpha=0.95),
                     fontsize=9, fontweight="bold", color="#92400e")

        # CISD Level
        ax1.axhline(tr["cisd_level"], color="#ca8a04", linestyle="-", linewidth=1.5)
        ax1.text(tr["cisd_time"], tr["cisd_level"] + (3 if is_long else -3), f"[CISD SHIFT] {tr['cisd_level']:.2f}", color="#ca8a04", fontsize=10, fontweight="bold")

        # 2nd Stage Retest Box
        rect = Rectangle((mdates.date2num(tr["cisd_time"]), tr["retest_bot"]),
                         mdates.date2num(tr["entry_time"]) - mdates.date2num(tr["cisd_time"]) + 0.005,
                         tr["retest_top"] - tr["retest_bot"],
                         facecolor="#a855f7", alpha=0.25, edgecolor="#9333ea", linestyle="--")
        ax1.add_patch(rect)
        ax1.text(tr["cisd_time"], tr["retest_top"] + 2, "2nd Stage Retest: OB / FVG / iFVG", color="#9333ea", fontsize=9, fontweight="bold")

        # Liquidity Target
        ax1.axhline(tr["tp2_price"], color="#8b5cf6", linestyle=":", linewidth=2.0)
        ax1.text(df_plot_nq.index[10], tr["tp2_price"] + 3, f"[LIQUIDITY TARGET - WATCH FOR REVERSAL] {tr['opposing_target_name']}", color="#8b5cf6", fontsize=10, fontweight="bold")

        # Entry Marker
        offset = -55 if is_long else 55
        ax1.annotate(f"{tr['direction']}\nEntry: {tr['entry_price']:.2f}\nSL: {tr['sl_price']:.2f}\nTarget: {tr['opposing_target_name']}",
                     xy=(tr["entry_time"], tr["entry_price"]),
                     xytext=(tr["entry_time"], tr["entry_price"] + offset),
                     arrowprops=dict(facecolor=col, edgecolor="#15803d" if is_long else "#991b1b", width=2, headwidth=8),
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8fafc", edgecolor=col, alpha=0.9),
                     fontsize=9, fontweight="bold")

        ax1.hlines(tr["sl_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_plot_nq.index[-1], color="#ef4444", linestyle="--", linewidth=1.5)
        ax1.hlines(tr["tp1_price"], xmin=tr["entry_time"], xmax=tr["exit_time"] if tr["exit_time"] else df_plot_nq.index[-1], color="#22c55e", linestyle="--", linewidth=1.5)

    ax1.set_title(f"NQ Futures — {target_date} | High-Conviction Institutional Setup (HTF Grab + SMT vs ES + CISD + OB/FVG)", fontsize=12, fontweight="bold", pad=10)
    ax1.set_ylabel("NQ Price", fontsize=11)
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="upper left", fontsize=9)

    ax2.set_title("ES Futures (S&P 500) — Smart Money Divergence (SMT) Correlation", fontsize=11, fontweight="bold", pad=8)
    ax2.set_ylabel("ES Price", fontsize=11)
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="upper left", fontsize=9)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M ET"))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    fig.autofmt_xdate()

    chart_file = OUTPUT_DIR / f"canonical_smt_{target_date}.png"
    plt.savefig(chart_file, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved pristine SMT chart to: {chart_file}")

    # Copy to root artifact directory
    root_art = Path(f"C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/canonical_smt_{target_date}.png")
    import shutil
    shutil.copy(chart_file, root_art)

if __name__ == "__main__":
    run_smt_audit("2026-08-28")
    run_smt_audit("2026-08-26")
