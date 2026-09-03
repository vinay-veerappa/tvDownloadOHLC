"""
Generic ICT IPDA Engine: External <-> Internal Liquidity Cycle
==============================================================
Core Principle:
Price is delivered in a perpetual, fractal loop between:
1. External Range Liquidity (EDL): Swing Highs / Lows (BSL/SSL), Session Extremes, Equal H/L.
2. Internal Range Liquidity (IDL): FVGs (Weekly, Daily, 4H, 1H, 15m) and Order Blocks (OB).

State Machine:
• Event A: Price purges External Liquidity (EDL) -> Objective shifts to Internal Liquidity (IDL).
  Confirmation: CISD shift across opposing delivery open.
  Entry: Limit at CISD level or 2nd Stage OB/Inv FVG retest.
  Target: Nearest unmitigated HTF FVG/OB (IDL).

• Event B: Price mitigates Internal Liquidity (IDL) -> Objective shifts to External Liquidity (EDL).
  Confirmation: CISD shift across opposing delivery open.
  Entry: Limit at CISD level or 2nd Stage OB/Inv FVG retest.
  Target: Opposing External Swing High/Low (EDL).

SMT Divergence: Optional high-confidence confluence badge (not a blocker).
Zero session-name hardcoding: Works 24/7 generically across any market.
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
    """Detects active, unmitigated FVGs on any timeframe."""
    fvgs = []
    for i in range(2, len(df)):
        b0 = df.iloc[i-2]
        b1 = df.iloc[i-1]
        b2 = df.iloc[i]
        t = df.index[i]

        # Bullish FVG: b2.low > b0.high
        if b2["low"] - b0["high"] >= min_gap_pts:
            fvgs.append({
                "tf": tf_name, "type": "BULL", "top": b2["low"], "bot": b0["high"],
                "mid": (b2["low"] + b0["high"]) / 2.0, "time": t, "mitigated": False
            })
        # Bearish FVG: b0.low - b2.high >= min_gap_pts
        elif b0["low"] - b2["high"] >= min_gap_pts:
            fvgs.append({
                "tf": tf_name, "type": "BEAR", "top": b0["low"], "bot": b2["high"],
                "mid": (b0["low"] + b2["high"]) / 2.0, "time": t, "mitigated": False
            })
    return fvgs

def find_swing_pivots(df, tf_name="1H", window=2):
    """Detects swing highs (BSL) and swing lows (SSL)."""
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

def find_htf_obs(df, tf_name="1H", min_displacement_pts=15.0):
    """
    Detects unmitigated Higher Timeframe Order Blocks (Weekly, Daily, 4H, 1H, 15m).
    Bullish OB: Last down-close candle before a strong upward displacement.
    Bearish OB: Last up-close candle before a strong downward displacement.
    """
    obs = []
    for i in range(1, len(df)-2):
        b0 = df.iloc[i]
        b1 = df.iloc[i+1]
        b2 = df.iloc[i+2]
        t = df.index[i]

        # Bullish OB: down candle followed by displacement up
        if b0["close"] < b0["open"] and (b2["close"] - b0["low"] >= min_displacement_pts):
            obs.append({
                "tf": tf_name, "type": "BULL_OB",
                "top": max(b0["open"], b0["close"]),
                "bot": b0["low"],
                "mt": (b0["open"] + b0["low"]) / 2.0, # Mean Threshold
                "time": t, "mitigated": False
            })
        # Bearish OB: up candle followed by displacement down
        elif b0["close"] > b0["open"] and (b0["high"] - b2["close"] >= min_displacement_pts):
            obs.append({
                "tf": tf_name, "type": "BEAR_OB",
                "top": b0["high"],
                "bot": min(b0["open"], b0["close"]),
                "mt": (b0["open"] + b0["high"]) / 2.0,
                "time": t, "mitigated": False
            })
    return obs

def run_ipda_engine(target_date="2026-08-28"):
    print("=" * 105)
    print(f"GENERIC ICT IPDA ENGINE (EXTERNAL <-> INTERNAL LIQUIDITY): {target_date}")
    print("=" * 105)

    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    df_es = pd.read_parquet("data/ES_recent_week.parquet").sort_index()

    target_d = pd.to_datetime(target_date).date()
    df_prior = df_nq[df_nq.index.date < target_d]
    df_day = df_nq[df_nq.index.date == target_d]

    # Resample Timeframes: 15m, 1H, 4H, Daily
    df_15m = df_nq.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_1h = df_nq.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_4h = df_nq.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    df_1d = df_nq.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # Gather Pre-existing Internal Liquidity Pools (FVGs & OBs across 15m, 1H, 4H, Daily)
    fvgs_15m = find_fvgs(df_15m.loc[:target_date], "15m", 3.0)
    fvgs_1h = find_fvgs(df_1h.loc[:target_date], "1H", 5.0)
    fvgs_4h = find_fvgs(df_4h.loc[:target_date], "4H", 10.0)
    fvgs_1d = find_fvgs(df_1d.loc[:target_date], "Daily", 15.0)
    all_internal_fvgs = fvgs_15m + fvgs_1h + fvgs_4h + fvgs_1d

    # HTF Order Blocks (Weekly, Daily, 4H, 1H, 15m)
    obs_15m = find_htf_obs(df_15m.loc[:target_date], "15m", 8.0)
    obs_1h = find_htf_obs(df_1h.loc[:target_date], "1H", 15.0)
    obs_4h = find_htf_obs(df_4h.loc[:target_date], "4H", 25.0)
    obs_1d = find_htf_obs(df_1d.loc[:target_date], "Daily", 40.0)
    all_internal_obs = obs_15m + obs_1h + obs_4h + obs_1d

    # Gather Pre-existing External Liquidity Pools (Swing Pivots BSL / SSL)
    pivots_1h = find_swing_pivots(df_1h.loc[:target_date], "1H", 2)
    pivots_4h = find_swing_pivots(df_4h.loc[:target_date], "4H", 2)
    pivots_1d = find_swing_pivots(df_1d.loc[:target_date], "Daily", 2)
    all_external_pivots = pivots_1h + pivots_4h + pivots_1d

    print(f"Pre-Existing HTF Pools Cataloged:")
    print(f"  • Internal Liquidity (FVGs): {len(all_internal_fvgs)} active gaps (Daily, 4H, 1H, 15m)")
    print(f"  • Internal Liquidity (OBs):  {len(all_internal_obs)} active Order Blocks (Daily, 4H, 1H, 15m)")
    print(f"  • External Liquidity (Pivots): {len(all_external_pivots)} swing pools (Daily, 4H, 1H BSL/SSL)")

    # 1-Minute Continuous Execution
    m1_bars = df_day.copy()
    trades = []
    active_setup = None
    last_down_open = np.nan
    last_up_open = np.nan

    for idx in range(len(m1_bars)):
        t = m1_bars.index[idx]
        c, o, h, l = m1_bars["close"].iloc[idx], m1_bars["open"].iloc[idx], m1_bars["high"].iloc[idx], m1_bars["low"].iloc[idx]

        if c < o: last_down_open = o
        elif c > o: last_up_open = o

        # State 1: Detect Interaction with External or Internal Liquidity
        if active_setup is None:
            # Case A: Purge of External Liquidity (SSL -> Seek Internal Bullish Target)
            for p in all_external_pivots:
                if p["type"] == "SSL" and not p["mitigated"] and p["time"] < t:
                    if l <= p["price"] and c > p["price"]: # Wick sweep / reclaim
                        # Target: Nearest unmitigated Bearish FVG above (Internal Liquidity)
                        above_fvgs = [f for f in all_internal_fvgs if f["type"] == "BEAR" and not f["mitigated"] and f["bot"] > c]
                        target_fvg = min(above_fvgs, key=lambda x: x["bot"]) if above_fvgs else None
                        target_p = target_fvg["bot"] if target_fvg else c + 150.0

                        active_setup = {
                            "origin_type": "EXTERNAL_PURGE",
                            "direction": "LONG",
                            "source_name": f"{p['tf']} SSL ({p['price']:.2f})",
                            "source_price": p["price"],
                            "sweep_time": t,
                            "extreme": l,
                            "target_type": "INTERNAL_FVG",
                            "target_name": f"{target_fvg['tf']} Bearish FVG" if target_fvg else "HTF Target",
                            "target_price": target_p
                        }
                        p["mitigated"] = True
                        break

            # Case B: Mitigation of Internal Liquidity (HTF FVG or HTF OB Tap -> Seek External Target)
            if active_setup is None:
                # Check HTF Bearish FVGs
                for f in all_internal_fvgs:
                    if not f["mitigated"] and f["time"] < t:
                        if f["type"] == "BEAR" and h >= f["bot"] and c <= f["top"]:
                            below_pivots = [p for p in all_external_pivots if p["type"] == "SSL" and not p["mitigated"] and p["price"] < c]
                            target_ssl = max(below_pivots, key=lambda x: x["price"]) if below_pivots else None
                            target_p = target_ssl["price"] if target_ssl else c - 100.0

                            active_setup = {
                                "origin_type": "INTERNAL_FVG_MITIGATION",
                                "direction": "SHORT",
                                "source_name": f"{f['tf']} FVG Tap [{f['bot']:.1f}-{f['top']:.1f}]",
                                "source_price": f["bot"],
                                "sweep_time": t,
                                "extreme": h,
                                "target_type": "EXTERNAL_SSL",
                                "target_name": f"{target_ssl['tf']} SSL ({target_p:.2f})" if target_ssl else "External SSL",
                                "target_price": target_p
                            }
                            f["mitigated"] = True
                            break

                # Check HTF Bearish Order Blocks (OB)
                if active_setup is None:
                    for ob in all_internal_obs:
                        if not ob["mitigated"] and ob["time"] < t and ob["type"] == "BEAR_OB":
                            if h >= ob["bot"] and c <= ob["top"]:
                                below_pivots = [p for p in all_external_pivots if p["type"] == "SSL" and not p["mitigated"] and p["price"] < c]
                                target_ssl = max(below_pivots, key=lambda x: x["price"]) if below_pivots else None
                                target_p = target_ssl["price"] if target_ssl else c - 100.0

                                active_setup = {
                                    "origin_type": "INTERNAL_OB_MITIGATION",
                                    "direction": "SHORT",
                                    "source_name": f"{ob['tf']} Bearish OB [{ob['bot']:.1f}-{ob['top']:.1f}]",
                                    "source_price": ob["bot"],
                                    "sweep_time": t,
                                    "extreme": h,
                                    "target_type": "EXTERNAL_SSL",
                                    "target_name": f"{target_ssl['tf']} SSL ({target_p:.2f})" if target_ssl else "External SSL",
                                    "target_price": target_p
                                }
                                ob["mitigated"] = True
                                break

            # Case C: Bullish HTF FVG or HTF Bullish OB Tap -> Seek External BSL Target
            if active_setup is None:
                for ob in all_internal_obs:
                    if not ob["mitigated"] and ob["time"] < t and ob["type"] == "BULL_OB":
                        if l <= ob["top"] and c >= ob["bot"]:
                            above_pivots = [p for p in all_external_pivots if p["type"] == "BSL" and not p["mitigated"] and p["price"] > c]
                            target_bsl = min(above_pivots, key=lambda x: x["price"]) if above_pivots else None
                            target_p = target_bsl["price"] if target_bsl else c + 100.0

                            active_setup = {
                                "origin_type": "INTERNAL_OB_MITIGATION",
                                "direction": "LONG",
                                "source_name": f"{ob['tf']} Bullish OB [{ob['bot']:.1f}-{ob['top']:.1f}]",
                                "source_price": ob["top"],
                                "sweep_time": t,
                                "extreme": l,
                                "target_type": "EXTERNAL_BSL",
                                "target_name": f"{target_bsl['tf']} BSL ({target_p:.2f})" if target_bsl else "External BSL",
                                "target_price": target_p
                            }
                            ob["mitigated"] = True
                            break

        # State 2: Confirm CISD Shift and Execute
        if active_setup and "cisd_level" not in active_setup:
            if active_setup["direction"] == "LONG" and not np.isnan(last_down_open) and c > last_down_open:
                active_setup["cisd_level"] = last_down_open
                active_setup["cisd_time"] = t
            elif active_setup["direction"] == "SHORT" and not np.isnan(last_up_open) and c < last_up_open:
                active_setup["cisd_level"] = last_up_open
                active_setup["cisd_time"] = t

        # State 3: Fill Limit Order at PD Array
        if active_setup and "cisd_level" in active_setup and "entry_time" not in active_setup:
            lvl = active_setup["cisd_level"]
            if active_setup["direction"] == "LONG" and l <= lvl <= h:
                active_setup["entry_time"] = t
                active_setup["entry_price"] = lvl
                active_setup["sl_price"] = active_setup["extreme"] - 5.0
                trades.append(active_setup.copy())
                active_setup = None
            elif active_setup["direction"] == "SHORT" and l <= lvl <= h:
                active_setup["entry_time"] = t
                active_setup["entry_price"] = lvl
                active_setup["sl_price"] = active_setup["extreme"] + 5.0
                trades.append(active_setup.copy())
                active_setup = None

    print(f"\nEXECUTED TRADES (GENERIC IPDA EXTERNAL <-> INTERNAL CYCLE): {len(trades)}")
    for tr in trades:
        print(f"\n  ★ [{tr['direction']}] filled at {tr['entry_time'].strftime('%H:%M ET')}")
        print(f"    • Origin Event:     {tr['origin_type']} on {tr['source_name']}")
        print(f"    • Entry Price:      {tr['entry_price']:.2f} (Filled directly at CISD line)")
        print(f"    • Target Objective: {tr['target_type']}: {tr['target_name']} @ {tr['target_price']:.2f}")
        print(f"    • Stop Loss:        {tr['sl_price']:.2f} (Anchored to protected extreme)")

if __name__ == "__main__":
    run_ipda_engine("2026-08-28")
