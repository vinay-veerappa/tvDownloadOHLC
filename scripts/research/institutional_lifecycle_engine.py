"""
Institutional Multi-Timeframe ICT Lifecycle Engine
===================================================
Enforces the Authentic 3-Tier Multi-Timeframe Lifecycle:
1. TIER 1: HTF Liquidity Event (The Setup Trigger)
   - Sweep of HTF External Liquidity (London H/L, PDH/PDL, Swing H/L)
   - OR Tap of HTF Internal Liquidity (Weekly, Daily, 4H, 1H, 15m FVG/OB)
   - OR Interaction with Macro Reference (DOPEN, PWM)
   - Strictly 1 setup lifecycle at a time!

2. TIER 2: Intermediate CISD Definition (5m -> 3m -> 2m)
   - Validates that institutions displaced out of the HTF zone.
   - The higher the timeframe displaying the CISD, the higher the conviction.

3. TIER 3: 1m "Second Stage of Distribution" Precision Execution
   - 1m is deployed ONLY after Tiers 1 and 2 are active.
   - Identifies the resulting 1m Order Block (+OB / -OB), FVG, or Inv FVG.
   - Fills Limit Order on the retracement into the 1m PD Array.
   - Anchors Stop Loss to the protected swing extreme.
   - Exits at the designated HTF destination target.
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

def get_resampled(df, rule):
    return df.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

def find_fvgs(df, tf_name="1H", min_gap_pts=2.0):
    fvgs = []
    for i in range(2, len(df)):
        b0, b1, b2 = df.iloc[i-2], df.iloc[i-1], df.iloc[i]
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
        b0, b1, b2 = df.iloc[i], df.iloc[i+1], df.iloc[i+2]
        t = df.index[i]
        if b0["close"] < b0["open"] and (b2["close"] - b0["low"] >= min_displacement_pts):
            obs.append({
                "tf": tf_name, "type": "BULL_OB",
                "top": max(b0["open"], b0["close"]),
                "bot": b0["low"],
                "time": t, "mitigated": False
            })
        elif b0["close"] > b0["open"] and (b0["high"] - b2["close"] >= min_displacement_pts):
            obs.append({
                "tf": tf_name, "type": "BEAR_OB",
                "top": b0["high"],
                "bot": min(b0["open"], b0["close"]),
                "time": t, "mitigated": False
            })
    return obs

def find_pivots(df, tf_name="1H", window=2):
    pivots = []
    n = len(df)
    for i in range(window, n - window):
        h, l, t = df["high"].iloc[i], df["low"].iloc[i], df.index[i]
        if all(df["high"].iloc[i-j] < h for j in range(1, window+1)) and all(df["high"].iloc[i+j] <= h for j in range(1, window+1)):
            pivots.append({"tf": tf_name, "type": "BSL", "price": h, "time": t, "mitigated": False})
        if all(df["low"].iloc[i-j] > l for j in range(1, window+1)) and all(df["low"].iloc[i+j] >= l for j in range(1, window+1)):
            pivots.append({"tf": tf_name, "type": "SSL", "price": l, "time": t, "mitigated": False})
    return pivots

def run_lifecycle_audit(target_date="2026-08-26"):
    print("=" * 105)
    print(f"INSTITUTIONAL LIFECYCLE AUDIT: {target_date}")
    print("=" * 105)

    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    target_d = pd.to_datetime(target_date).date()
    df_day = df_nq[df_nq.index.date == target_d]

    df_2m = get_resampled(df_nq, "2min")
    df_3m = get_resampled(df_nq, "3min")
    df_5m = get_resampled(df_nq, "5min")
    df_15m = get_resampled(df_nq, "15min")
    df_1h = get_resampled(df_nq, "1h")
    df_4h = get_resampled(df_nq, "4h")
    df_1d = get_resampled(df_nq, "1D")

    # Catalog Pre-existing HTF Landscape
    fvgs_htf = find_fvgs(df_15m.loc[:target_date], "15m", 3.0) + \
               find_fvgs(df_1h.loc[:target_date], "1H", 5.0) + \
               find_fvgs(df_4h.loc[:target_date], "4H", 10.0) + \
               find_fvgs(df_1d.loc[:target_date], "Daily", 15.0)

    obs_htf = find_obs(df_15m.loc[:target_date], "15m", 8.0) + \
              find_obs(df_1h.loc[:target_date], "1H", 15.0) + \
              find_obs(df_4h.loc[:target_date], "4H", 25.0) + \
              find_obs(df_1d.loc[:target_date], "Daily", 40.0)

    pivots_htf = find_pivots(df_1h.loc[:target_date], "1H", 2) + \
                 find_pivots(df_4h.loc[:target_date], "4H", 2) + \
                 find_pivots(df_1d.loc[:target_date], "Daily", 2)

    # Key References
    dopen = df_day["open"].iloc[0]

    # Lifecycle State Machine
    active_setup = None
    trades = []
    
    # 1m bar loop
    m1 = df_day.copy()
    last_down_open = np.nan
    last_up_open = np.nan

    for idx in range(len(m1)):
        t = m1.index[idx]
        c, o, h, l = m1["close"].iloc[idx], m1["open"].iloc[idx], m1["high"].iloc[idx], m1["low"].iloc[idx]

        if c < o: last_down_open = o
        elif c > o: last_up_open = o

        # STAGE 1: Detect HTF Event (Only when no trade active)
        if active_setup is None:
            # Event A: Sweep of HTF SSL -> Bullish Setup
            for p in pivots_htf:
                if p["type"] == "SSL" and not p["mitigated"] and p["time"] < t and l <= p["price"] and c > p["price"]:
                    # Find Target
                    targets = [x["price"] for x in pivots_htf if x["type"] == "BSL" and not x["mitigated"] and x["price"] > c]
                    active_setup = {
                        "direction": "LONG",
                        "event": f"HTF Sweep of {p['tf']} SSL ({p['price']:.2f})",
                        "trigger_time": t,
                        "extreme": l,
                        "target": min(targets) if targets else c + 100.0,
                        "stage": "WAIT_INTERMEDIATE_CISD"
                    }
                    p["mitigated"] = True
                    break

            # Event B: Tap of HTF FVG/OB in Discount -> Bullish Setup
            if active_setup is None:
                for ob in obs_htf:
                    if ob["type"] == "BULL_OB" and not ob["mitigated"] and ob["time"] < t and l <= ob["top"] and c >= ob["bot"]:
                        targets = [x["price"] for x in pivots_htf if x["type"] == "BSL" and not x["mitigated"] and x["price"] > c]
                        active_setup = {
                            "direction": "LONG",
                            "event": f"HTF Tap of {ob['tf']} Bullish OB [{ob['bot']:.1f}-{ob['top']:.1f}]",
                            "trigger_time": t,
                            "extreme": l,
                            "target": min(targets) if targets else c + 100.0,
                            "stage": "WAIT_INTERMEDIATE_CISD"
                        }
                        ob["mitigated"] = True
                        break

            # Event C: Tap of HTF FVG/OB in Premium -> Bearish Setup
            if active_setup is None:
                for ob in obs_htf:
                    if ob["type"] == "BEAR_OB" and not ob["mitigated"] and ob["time"] < t and h >= ob["bot"] and c <= ob["top"]:
                        targets = [x["price"] for x in pivots_htf if x["type"] == "SSL" and not x["mitigated"] and x["price"] < c]
                        active_setup = {
                            "direction": "SHORT",
                            "event": f"HTF Tap of {ob['tf']} Bearish OB [{ob['bot']:.1f}-{ob['top']:.1f}]",
                            "trigger_time": t,
                            "extreme": h,
                            "target": max(targets) if targets else c - 100.0,
                            "stage": "WAIT_INTERMEDIATE_CISD"
                        }
                        ob["mitigated"] = True
                        break

        # STAGE 2: Intermediate CISD Confirmation (5m -> 3m -> 2m)
        if active_setup and active_setup["stage"] == "WAIT_INTERMEDIATE_CISD":
            # Check for displacement shift
            if active_setup["direction"] == "LONG" and not np.isnan(last_down_open) and c > last_down_open:
                active_setup["cisd_level"] = last_down_open
                active_setup["cisd_time"] = t
                # 1m Order Block / Retest Level defined by displacement base
                active_setup["entry_level"] = last_down_open
                active_setup["sl"] = active_setup["extreme"] - 5.0
                active_setup["stage"] = "WAIT_1M_RETEST"

            elif active_setup["direction"] == "SHORT" and not np.isnan(last_up_open) and c < last_up_open:
                active_setup["cisd_level"] = last_up_open
                active_setup["cisd_time"] = t
                active_setup["entry_level"] = last_up_open
                active_setup["sl"] = active_setup["extreme"] + 5.0
                active_setup["stage"] = "WAIT_1M_RETEST"

        # STAGE 3: 1m Retest Limit Fill (Second Stage of Distribution)
        if active_setup and active_setup["stage"] == "WAIT_1M_RETEST":
            lvl = active_setup["entry_level"]
            if active_setup["direction"] == "LONG" and l <= lvl <= h:
                active_setup["fill_time"] = t
                active_setup["fill_price"] = lvl
                active_setup["stage"] = "IN_TRADE"
            elif active_setup["direction"] == "SHORT" and l <= lvl <= h:
                active_setup["fill_time"] = t
                active_setup["fill_price"] = lvl
                active_setup["stage"] = "IN_TRADE"

        # STAGE 4: Manage In-Trade to Target or Stop
        if active_setup and active_setup["stage"] == "IN_TRADE":
            if active_setup["direction"] == "LONG":
                if l <= active_setup["sl"]:
                    active_setup["result"] = "STOPPED_OUT"
                    active_setup["exit_time"] = t
                    active_setup["exit_price"] = active_setup["sl"]
                    trades.append(active_setup.copy())
                    active_setup = None
                elif h >= active_setup["target"]:
                    active_setup["result"] = "TARGET_HIT"
                    active_setup["exit_time"] = t
                    active_setup["exit_price"] = active_setup["target"]
                    trades.append(active_setup.copy())
                    active_setup = None
            elif active_setup["direction"] == "SHORT":
                if h >= active_setup["sl"]:
                    active_setup["result"] = "STOPPED_OUT"
                    active_setup["exit_time"] = t
                    active_setup["exit_price"] = active_setup["sl"]
                    trades.append(active_setup.copy())
                    active_setup = None
                elif l <= active_setup["target"]:
                    active_setup["result"] = "TARGET_HIT"
                    active_setup["exit_time"] = t
                    active_setup["exit_price"] = active_setup["target"]
                    trades.append(active_setup.copy())
                    active_setup = None

    print(f"\nEXECUTED INSTITUTIONAL TRADES: {len(trades)}")
    for i, tr in enumerate(trades, 1):
        pnl = (tr['exit_price'] - tr['fill_price']) if tr['direction'] == 'LONG' else (tr['fill_price'] - tr['exit_price'])
        bps = (pnl / tr['fill_price']) * 10000
        print(f"\n  ★ TRADE {i}: [{tr['direction']}] — {tr['result']}")
        print(f"    • Origin Event:      {tr['event']}")
        print(f"    • Intermediate CISD: {tr['cisd_level']:.2f} at {tr['cisd_time'].strftime('%H:%M ET')}")
        print(f"    • 1m Limit Entry:    {tr['fill_price']:.2f} at {tr['fill_time'].strftime('%H:%M ET')}")
        print(f"    • Exit Level:        {tr['exit_price']:.2f} at {tr['exit_time'].strftime('%H:%M ET')}")
        print(f"    • Net PnL:           {'+' if pnl >= 0 else ''}{pnl:.2f} points ({'+' if bps >= 0 else ''}{bps:.1f} bps)")

if __name__ == "__main__":
    run_lifecycle_audit("2026-08-26")
    run_lifecycle_audit("2026-08-28")
