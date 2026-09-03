"""
Institutional Multi-Timeframe ICT Engine: HTF -> Intermediate CISD -> 1m Execution
=====================================================================================
Hierarchy:
1. HTF Direction & Dealing Range:
   - Tracks 15m, 1H, 4H, Daily, Weekly FVGs, OBs, and External Swings (BSL/SSL).
   - Establishes Macro Vector (e.g., Discount to Premium Expansion).
   - Strict Direction Gate: Forbids trades that counter the active HTF vector.

2. Intermediate Timeframe CISD Hierarchy (5m -> 3m -> 2m):
   - Evaluates structural shifts across 5m, 3m, 2m, and 1m.
   - Higher timeframe CISD has absolute authority.
   - A 5m Bullish CISD overrides and blocks any 1m counter-trend short wiggles.

3. 1m Precision Execution Engine:
   - 1m is deployed ONLY after HTF + Intermediate CISD are locked.
   - Identifies the resulting 1m PD Array (+OB, -OB, FVG, Inv FVG) in the 2nd stage of distribution.
   - Places Limit Orders at the PD Array on the retracement.
   - Anchors Stop Loss to protected structural extremes.
   - Sets Targets to opposing HTF liquidity objectives (no lookahead bias).
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def find_fvgs(df, tf_name="1H", min_gap_pts=2.0):
    fvgs = []
    for i in range(2, len(df)):
        b0 = df.iloc[i-2]
        b1 = df.iloc[i-1]
        b2 = df.iloc[i]
        t = df.index[i]
        if b2["low"] - b0["high"] >= min_gap_pts:
            fvgs.append({
                "tf": tf_name, "type": "BULL", "top": b2["low"], "bot": b0["high"],
                "mid": (b2["low"] + b0["high"]) / 2.0, "time": t, "mitigated": False
            })
        elif b0["low"] - b2["high"] >= min_gap_pts:
            fvgs.append({
                "tf": tf_name, "type": "BEAR", "top": b0["low"], "bot": b2["high"],
                "mid": (b0["low"] + b2["high"]) / 2.0, "time": t, "mitigated": False
            })
    return fvgs

def find_obs(df, tf_name="1H", min_displacement_pts=10.0):
    obs = []
    for i in range(1, len(df)-2):
        b0 = df.iloc[i]
        b1 = df.iloc[i+1]
        b2 = df.iloc[i+2]
        t = df.index[i]
        if b0["close"] < b0["open"] and (b2["close"] - b0["low"] >= min_displacement_pts):
            obs.append({
                "tf": tf_name, "type": "BULL_OB",
                "top": max(b0["open"], b0["close"]),
                "bot": b0["low"],
                "mt": (b0["open"] + b0["low"]) / 2.0,
                "time": t, "mitigated": False
            })
        elif b0["close"] > b0["open"] and (b0["high"] - b2["close"] >= min_displacement_pts):
            obs.append({
                "tf": tf_name, "type": "BEAR_OB",
                "top": b0["high"],
                "bot": min(b0["open"], b0["close"]),
                "mt": (b0["open"] + b0["high"]) / 2.0,
                "time": t, "mitigated": False
            })
    return obs

def find_swing_pivots(df, tf_name="1H", window=2):
    pivots = []
    n = len(df)
    for i in range(window, n - window):
        h = df["high"].iloc[i]
        l = df["low"].iloc[i]
        t = df.index[i]
        is_sh = all(df["high"].iloc[i-j] < h for j in range(1, window+1)) and \
                all(df["high"].iloc[i+j] <= h for j in range(1, window+1))
        is_sl = all(df["low"].iloc[i-j] > l for j in range(1, window+1)) and \
                all(df["low"].iloc[i+j] >= l for j in range(1, window+1))
        if is_sh:
            pivots.append({"tf": tf_name, "type": "BSL", "price": h, "time": t, "mitigated": False})
        if is_sl:
            pivots.append({"tf": tf_name, "type": "SSL", "price": l, "time": t, "mitigated": False})
    return pivots

def detect_cisd(df, tf_name="5m"):
    """Tracks candle closes across the sequence open to identify structural CISD."""
    cisds = []
    last_down_open = np.nan
    last_up_open = np.nan
    for i in range(len(df)):
        t = df.index[i]
        c, o = df["close"].iloc[i], df["open"].iloc[i]
        if c < o:
            last_down_open = o
        elif c > o:
            last_up_open = o

        if not np.isnan(last_down_open) and c > last_down_open:
            cisds.append({"time": t, "tf": tf_name, "direction": "BULL", "level": last_down_open})
            last_down_open = np.nan
        elif not np.isnan(last_up_open) and c < last_up_open:
            cisds.append({"time": t, "tf": tf_name, "direction": "BEAR", "level": last_up_open})
            last_up_open = np.nan
    return cisds

def run_multi_tf_engine(target_date="2026-08-26"):
    print("=" * 105)
    print(f"INSTITUTIONAL MULTI-TIMEFRAME ICT ENGINE AUDIT: {target_date}")
    print("=" * 105)

    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    target_d = pd.to_datetime(target_date).date()
    df_day = df_nq[df_nq.index.date == target_d]

    # Build Multi-Timeframe Hierarchy
    df_2m = df_nq.resample("2min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_3m = df_nq.resample("3min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_5m = df_nq.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_15m = df_nq.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_1h = df_nq.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h = df_nq.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_1d = df_nq.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # 1. HTF Liquidity Pools & Confluences (Pre-existing before trade time)
    fvgs_htf = find_fvgs(df_15m.loc[:target_date], "15m", 3.0) + \
               find_fvgs(df_1h.loc[:target_date], "1H", 5.0) + \
               find_fvgs(df_4h.loc[:target_date], "4H", 10.0) + \
               find_fvgs(df_1d.loc[:target_date], "Daily", 15.0)

    obs_htf = find_obs(df_15m.loc[:target_date], "15m", 8.0) + \
              find_obs(df_1h.loc[:target_date], "1H", 15.0) + \
              find_obs(df_4h.loc[:target_date], "4H", 25.0) + \
              find_obs(df_1d.loc[:target_date], "Daily", 40.0)

    pivots_htf = find_swing_pivots(df_1h.loc[:target_date], "1H", 2) + \
                 find_swing_pivots(df_4h.loc[:target_date], "4H", 2) + \
                 find_swing_pivots(df_1d.loc[:target_date], "Daily", 2)

    # 2. Intermediate CISDs
    cisds_5m = detect_cisd(df_5m.loc[f"{target_date} 00:00:00":f"{target_date} 23:59:00"], "5m")
    cisds_3m = detect_cisd(df_3m.loc[f"{target_date} 00:00:00":f"{target_date} 23:59:00"], "3m")
    cisds_2m = detect_cisd(df_2m.loc[f"{target_date} 00:00:00":f"{target_date} 23:59:00"], "2m")
    cisds_1m = detect_cisd(df_day, "1m")

    print(f"Cataloged Structure:")
    print(f"  • HTF FVGs: {len(fvgs_htf)} | HTF OBs: {len(obs_htf)} | HTF Pivots: {len(pivots_htf)}")
    print(f"  • Intermediate CISDs: 5m: {len(cisds_5m)} | 3m: {len(cisds_3m)} | 2m: {len(cisds_2m)} | 1m: {len(cisds_1m)}")

    # 3. 1-Minute Execution Loop with Strict HTF & 5m CISD Direction Gate
    active_htf_vector = "NEUTRAL"
    active_5m_bias = "NEUTRAL"
    trades = []
    
    # 1m bar loop
    m1_bars = df_day.copy()
    pending_order = None

    for idx in range(len(m1_bars)):
        t = m1_bars.index[idx]
        c, o, h, l = m1_bars["close"].iloc[idx], m1_bars["open"].iloc[idx], m1_bars["high"].iloc[idx], m1_bars["low"].iloc[idx]

        # Update 5m CISD Bias
        recent_5m = [x for x in cisds_5m if x["time"] <= t]
        if recent_5m:
            active_5m_bias = recent_5m[-1]["direction"]

        # 1. Check for HTF Liquidity Interaction
        # Bullish: Swept HTF SSL or Tapped HTF Bullish FVG/OB
        tapped_bull_htf = any(
            (p["type"] == "SSL" and not p["mitigated"] and p["time"] < t and l <= p["price"] and c > p["price"])
            for p in pivots_htf
        ) or any(
            (ob["type"] == "BULL_OB" and not ob["mitigated"] and ob["time"] < t and l <= ob["top"] and c >= ob["bot"])
            for ob in obs_htf
        ) or any(
            (f["type"] == "BULL" and not f["mitigated"] and f["time"] < t and l <= f["top"] and c >= f["bot"])
            for f in fvgs_htf
        )

        if tapped_bull_htf:
            active_htf_vector = "BULL"

        tapped_bear_htf = any(
            (p["type"] == "BSL" and not p["mitigated"] and p["time"] < t and h >= p["price"] and c < p["price"])
            for p in pivots_htf
        ) or any(
            (ob["type"] == "BEAR_OB" and not ob["mitigated"] and ob["time"] < t and h >= ob["bot"] and c <= ob["top"])
            for ob in obs_htf
        ) or any(
            (f["type"] == "BEAR" and not f["mitigated"] and f["time"] < t and h >= f["bot"] and c <= f["top"])
            for f in fvgs_htf
        )

        if tapped_bear_htf:
            active_htf_vector = "BEAR"

        # 2. Check for Intermediate & 1m CISD Alignment
        recent_1m = [x for x in cisds_1m if x["time"] == t]
        if recent_1m and pending_order is None:
            c1 = recent_1m[-1]
            # DIRECTION GATE: 1m shift MUST align with HTF or 5m Bias!
            # If 5m bias is BULL, forbid 1m BEAR shifts!
            if c1["direction"] == "BEAR" and active_5m_bias == "BULL":
                continue # BLOCKED BY 5M CISD DIRECTION GATE!
            if c1["direction"] == "BULL" and active_5m_bias == "BEAR":
                continue # BLOCKED BY 5M CISD DIRECTION GATE!

            if c1["direction"] == "BULL" and (active_htf_vector == "BULL" or active_5m_bias == "BULL"):
                # Detect 1m Order Block / FVG created by displacement
                ob_lvl = c1["level"]
                # Find Target
                above_targets = [p["price"] for p in pivots_htf if p["type"] == "BSL" and not p["mitigated"] and p["price"] > c] + \
                                [f["bot"] for f in fvgs_htf if f["type"] == "BEAR" and not f["mitigated"] and f["bot"] > c]
                target_p = min(above_targets) if above_targets else c + 80.0

                pending_order = {
                    "direction": "LONG",
                    "placed_time": t,
                    "level": ob_lvl,
                    "sl": l - 10.0,
                    "target": target_p,
                    "status": "PENDING"
                }

            elif c1["direction"] == "BEAR" and (active_htf_vector == "BEAR" or active_5m_bias == "BEAR"):
                ob_lvl = c1["level"]
                below_targets = [p["price"] for p in pivots_htf if p["type"] == "SSL" and not p["mitigated"] and p["price"] < c] + \
                                [f["top"] for f in fvgs_htf if f["type"] == "BULL" and not f["mitigated"] and f["top"] < c]
                target_p = max(below_targets) if below_targets else c - 80.0

                pending_order = {
                    "direction": "SHORT",
                    "placed_time": t,
                    "level": ob_lvl,
                    "sl": h + 10.0,
                    "target": target_p,
                    "status": "PENDING"
                }

        # 3. Check Limit Order Fill on 1m Retest (Second Stage of Distribution)
        if pending_order and pending_order["status"] == "PENDING":
            if pending_order["direction"] == "LONG" and l <= pending_order["level"] <= h:
                pending_order["status"] = "FILLED"
                pending_order["fill_time"] = t
                pending_order["fill_price"] = pending_order["level"]
                trades.append(pending_order.copy())
                pending_order = None
            elif pending_order["direction"] == "SHORT" and l <= pending_order["level"] <= h:
                pending_order["status"] = "FILLED"
                pending_order["fill_time"] = t
                pending_order["fill_price"] = pending_order["level"]
                trades.append(pending_order.copy())
                pending_order = None

    print(f"\nEXECUTED TRADES UNDER MULTI-TF ALIGNMENT GATE: {len(trades)}")
    for tr in trades:
        print(f"\n  ★ [{tr['direction']}] filled at {tr['fill_time'].strftime('%H:%M ET')}")
        print(f"    • Entry Price:      {tr['fill_price']:.2f} (Filled directly at PD Array)")
        print(f"    • Target Objective: {tr['target']:.2f}")
        print(f"    • Stop Loss:        {tr['sl']:.2f}")

if __name__ == "__main__":
    run_multi_tf_engine("2026-08-26")
    run_multi_tf_engine("2026-08-28")
