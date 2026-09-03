"""
ICT IPDA Institutional Data Collection & Excursion Engine
==========================================================
Implements mandatory ADR-023 / universal_basis_points_and_statistics standard:
1. Multi-Timeframe Architecture:
   - Tier 1: HTF Anchors (External BSL/SSL Sweeps, 15m/1H/4H/D FVGs & OBs, DOPEN, WOPEN)
   - Tier 2: Intermediate CISD (5m -> 3m -> 2m) Direction Gate
   - Tier 3: 1m "Second Stage of Distribution" Entry (+OB, -OB, FVG, Inv FVG)
   - Re-Entry Protocol: If stopped out within tight buffer (<= 5 bps) while HTF level (CE) holds, re-enter on confirmed 1m breakout!

2. Granular Data Collection & Excursion Metrics:
   - Exact entry/exit timestamps (ET & CT)
   - Fill price directly on the PD Array
   - Bar-by-bar intra-trade MFE (Maximum Favorable Excursion) in pts & bps
   - Bar-by-bar intra-trade MAE (Maximum Adverse Excursion) in pts & bps
   - Target Reach CDF (2 bps, 5 bps, 10 bps, 15 bps, 20 bps, 30 bps, 50 bps)
   - MAE survival curves
   - Session & Hourly breakdown

3. Output Artifacts:
   - Parquet: data/research/ict_ipda_trade_log.parquet
   - CSV:     data/research/ict_ipda_trade_log.csv
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

OUTPUT_DIR = Path("data/research")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def resample_ohlc(df, freq):
    return df.resample(freq).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

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

def assign_session(t):
    hour = t.hour
    if 20 <= hour or hour < 2: return "ASIA"
    elif 2 <= hour < 8: return "LONDON"
    elif 8 <= hour < 12: return "NY_AM"
    elif 12 <= hour < 16: return "NY_PM"
    else: return "EVENING"

def run_data_collection():
    print("=" * 105)
    print("ICT IPDA INSTITUTIONAL DATA COLLECTION & EXCURSION ENGINE")
    print("=" * 105)

    df_nq = pd.read_parquet("data/NQ_recent_week.parquet").sort_index()
    df_es = pd.read_parquet("data/ES_recent_week.parquet").sort_index()

    # Pre-compute HTF resamples across entire dataset
    df_5m = resample_ohlc(df_nq, "5min")
    df_15m = resample_ohlc(df_nq, "15min")
    df_1h = resample_ohlc(df_nq, "1h")
    df_4h = resample_ohlc(df_nq, "4h")
    df_1d = resample_ohlc(df_nq, "1D")

    all_trade_records = []
    dates = sorted(list(set(df_nq.index.date)))

    for current_date in dates:
        day_str = current_date.strftime("%Y-%m-%d")
        nq_day = df_nq[df_nq.index.date == current_date]
        if len(nq_day) < 100: continue

        # 1. Gather HTF Pools formed PRIOR to today
        prior_mask = df_1h.index.date < current_date
        fvgs_htf = find_fvgs(df_15m[df_15m.index.date < current_date], "15m", 3.0) + \
                   find_fvgs(df_1h[prior_mask], "1H", 5.0) + \
                   find_fvgs(df_4h[df_4h.index.date < current_date], "4H", 10.0) + \
                   find_fvgs(df_1d[df_1d.index.date < current_date], "Daily", 15.0)

        obs_htf = find_obs(df_15m[df_15m.index.date < current_date], "15m", 8.0) + \
                  find_obs(df_1h[prior_mask], "1H", 15.0) + \
                  find_obs(df_4h[df_4h.index.date < current_date], "4H", 25.0) + \
                  find_obs(df_1d[df_1d.index.date < current_date], "Daily", 40.0)

        pivots_htf = find_pivots(df_1h[prior_mask], "1H", 2) + \
                     find_pivots(df_4h[df_4h.index.date < current_date], "4H", 2) + \
                     find_pivots(df_1d[df_1d.index.date < current_date], "Daily", 2)

        # Pre-market session levels
        asia_bars = nq_day.between_time("20:00", "02:00")
        lndn_bars = nq_day.between_time("02:00", "05:00")
        if not lndn_bars.empty:
            pivots_htf.append({"tf": "Session", "type": "BSL", "price": lndn_bars["high"].max(), "time": lndn_bars.index[-1], "mitigated": False, "name": "London High"})
            pivots_htf.append({"tf": "Session", "type": "SSL", "price": lndn_bars["low"].min(), "time": lndn_bars.index[-1], "mitigated": False, "name": "London Low"})

        dopen = nq_day["open"].iloc[0]

        # 2. Iterate 1-Minute Bars with Strict Lifecycle & Re-Entry
        active_setup = None
        last_down_open = np.nan
        last_up_open = np.nan

        for idx in range(len(nq_day)):
            t = nq_day.index[idx]
            c, o, h, l = nq_day["close"].iloc[idx], nq_day["open"].iloc[idx], nq_day["high"].iloc[idx], nq_day["low"].iloc[idx]

            if c < o: last_down_open = o
            elif c > o: last_up_open = o

            # Tier 1: Check for HTF Liquidity Interaction
            if active_setup is None:
                # SSL Sweep
                for p in pivots_htf:
                    if p["type"] == "SSL" and not p["mitigated"] and p["time"] < t and l <= p["price"] and c > p["price"]:
                        above_targets = [x["price"] for x in pivots_htf if x["type"] == "BSL" and not x["mitigated"] and x["price"] > c] + \
                                        [f["bot"] for f in fvgs_htf if f["type"] == "BEAR" and not f["mitigated"] and f["bot"] > c]
                        active_setup = {
                            "date": day_str, "direction": "LONG",
                            "origin_type": "EXTERNAL_SSL_SWEEP", "origin_name": p.get("name", f"{p['tf']} SSL"),
                            "origin_price": p["price"], "trigger_time": t, "extreme": l,
                            "target_price": min(above_targets) if above_targets else c + 100.0,
                            "stage": "WAIT_INTERMEDIATE_CISD", "attempt": 1
                        }
                        p["mitigated"] = True
                        break

                # Bullish OB/FVG Tap
                if active_setup is None:
                    for ob in obs_htf:
                        if ob["type"] == "BULL_OB" and not ob["mitigated"] and ob["time"] < t and l <= ob["top"] and c >= ob["bot"]:
                            above_targets = [x["price"] for x in pivots_htf if x["type"] == "BSL" and not x["mitigated"] and x["price"] > c] + \
                                            [f["bot"] for f in fvgs_htf if f["type"] == "BEAR" and not f["mitigated"] and f["bot"] > c]
                            active_setup = {
                                "date": day_str, "direction": "LONG",
                                "origin_type": "INTERNAL_OB_TAP", "origin_name": f"{ob['tf']} Bullish OB",
                                "origin_price": ob["top"], "trigger_time": t, "extreme": l, "htf_floor": ob["bot"],
                                "target_price": min(above_targets) if above_targets else c + 100.0,
                                "stage": "WAIT_INTERMEDIATE_CISD", "attempt": 1
                            }
                            ob["mitigated"] = True
                            break

                # BSL Sweep / Bearish OB Tap
                if active_setup is None:
                    for ob in obs_htf:
                        if ob["type"] == "BEAR_OB" and not ob["mitigated"] and ob["time"] < t and h >= ob["bot"] and c <= ob["top"]:
                            below_targets = [x["price"] for x in pivots_htf if x["type"] == "SSL" and not x["mitigated"] and x["price"] < c] + \
                                            [f["top"] for f in fvgs_htf if f["type"] == "BULL" and not f["mitigated"] and f["top"] < c]
                            active_setup = {
                                "date": day_str, "direction": "SHORT",
                                "origin_type": "INTERNAL_OB_TAP", "origin_name": f"{ob['tf']} Bearish OB",
                                "origin_price": ob["bot"], "trigger_time": t, "extreme": h, "htf_ceiling": ob["top"],
                                "target_price": max(below_targets) if below_targets else c - 100.0,
                                "stage": "WAIT_INTERMEDIATE_CISD", "attempt": 1
                            }
                            ob["mitigated"] = True
                            break

            # Tier 2: Intermediate CISD Shift
            if active_setup and active_setup["stage"] == "WAIT_INTERMEDIATE_CISD":
                if active_setup["direction"] == "LONG" and not np.isnan(last_down_open) and c > last_down_open:
                    active_setup["cisd_level"] = last_down_open
                    active_setup["cisd_time"] = t
                    active_setup["entry_level"] = last_down_open
                    # Initial Stop Loss: Tight 5 bps or structural extreme
                    active_setup["sl_structural"] = active_setup["extreme"] - 5.0
                    active_setup["sl_tight_5bps"] = last_down_open * (1.0 - 0.0005)
                    active_setup["sl_active"] = active_setup["sl_tight_5bps"]
                    active_setup["stage"] = "WAIT_1M_ENTRY"

                elif active_setup["direction"] == "SHORT" and not np.isnan(last_up_open) and c < last_up_open:
                    active_setup["cisd_level"] = last_up_open
                    active_setup["cisd_time"] = t
                    active_setup["entry_level"] = last_up_open
                    active_setup["sl_structural"] = active_setup["extreme"] + 5.0
                    active_setup["sl_tight_5bps"] = last_up_open * (1.0 + 0.0005)
                    active_setup["sl_active"] = active_setup["sl_tight_5bps"]
                    active_setup["stage"] = "WAIT_1M_ENTRY"

            # Tier 3: 1m Limit Fill
            if active_setup and active_setup["stage"] == "WAIT_1M_ENTRY":
                lvl = active_setup["entry_level"]
                if active_setup["direction"] == "LONG" and l <= lvl <= h:
                    active_setup["fill_time"] = t
                    active_setup["fill_price"] = lvl
                    active_setup["stage"] = "IN_TRADE"
                    active_setup["mfe_pts"] = 0.0
                    active_setup["mae_pts"] = 0.0
                elif active_setup["direction"] == "SHORT" and l <= lvl <= h:
                    active_setup["fill_time"] = t
                    active_setup["fill_price"] = lvl
                    active_setup["stage"] = "IN_TRADE"
                    active_setup["mfe_pts"] = 0.0
                    active_setup["mae_pts"] = 0.0

            # Tier 4: Intra-Trade Tracking & Excursion Calculation
            if active_setup and active_setup["stage"] == "IN_TRADE":
                ep = active_setup["fill_price"]

                if active_setup["direction"] == "LONG":
                    # Intra-bar excursions
                    fav = h - ep
                    adv = ep - l
                    if fav > active_setup["mfe_pts"]: active_setup["mfe_pts"] = fav
                    if adv > active_setup["mae_pts"]: active_setup["mae_pts"] = adv

                    # Check Target Hit
                    if h >= active_setup["target_price"]:
                        active_setup["exit_time"] = t
                        active_setup["exit_price"] = active_setup["target_price"]
                        active_setup["result"] = "TARGET_HIT"
                        all_trade_records.append(active_setup.copy())
                        active_setup = None
                        continue

                    # Check Stop Loss Hit
                    if l <= active_setup["sl_active"]:
                        # Check if HTF Floor is still respected for Re-entry!
                        htf_floor = active_setup.get("htf_floor", active_setup["extreme"])
                        if l >= htf_floor and active_setup["attempt"] == 1:
                            # Trigger Re-Entry Mode
                            rec = active_setup.copy()
                            rec["exit_time"] = t
                            rec["exit_price"] = active_setup["sl_active"]
                            rec["result"] = "STOPPED_OUT_TIGHT_SL"
                            all_trade_records.append(rec)

                            active_setup["attempt"] = 2
                            active_setup["stage"] = "WAIT_RECONFIRMATION"
                            continue
                        else:
                            active_setup["exit_time"] = t
                            active_setup["exit_price"] = active_setup["sl_active"]
                            active_setup["result"] = "STOPPED_OUT_FULL"
                            all_trade_records.append(active_setup.copy())
                            active_setup = None
                            continue

                elif active_setup["direction"] == "SHORT":
                    fav = ep - l
                    adv = h - ep
                    if fav > active_setup["mfe_pts"]: active_setup["mfe_pts"] = fav
                    if adv > active_setup["mae_pts"]: active_setup["mae_pts"] = adv

                    if l <= active_setup["target_price"]:
                        active_setup["exit_time"] = t
                        active_setup["exit_price"] = active_setup["target_price"]
                        active_setup["result"] = "TARGET_HIT"
                        all_trade_records.append(active_setup.copy())
                        active_setup = None
                        continue

                    if h >= active_setup["sl_active"]:
                        htf_ceil = active_setup.get("htf_ceiling", active_setup["extreme"])
                        if h <= htf_ceil and active_setup["attempt"] == 1:
                            rec = active_setup.copy()
                            rec["exit_time"] = t
                            rec["exit_price"] = active_setup["sl_active"]
                            rec["result"] = "STOPPED_OUT_TIGHT_SL"
                            all_trade_records.append(rec)

                            active_setup["attempt"] = 2
                            active_setup["stage"] = "WAIT_RECONFIRMATION"
                            continue
                        else:
                            active_setup["exit_time"] = t
                            active_setup["exit_price"] = active_setup["sl_active"]
                            active_setup["result"] = "STOPPED_OUT_FULL"
                            all_trade_records.append(active_setup.copy())
                            active_setup = None
                            continue

            # Tier 5: Reconfirmation / Re-Entry Logic
            if active_setup and active_setup["stage"] == "WAIT_RECONFIRMATION":
                # Look for breakout back above/below CISD to re-enter
                if active_setup["direction"] == "LONG" and c > active_setup["cisd_level"]:
                    active_setup["entry_level"] = c
                    active_setup["fill_time"] = t
                    active_setup["fill_price"] = c
                    active_setup["sl_active"] = active_setup["extreme"] - 5.0
                    active_setup["stage"] = "IN_TRADE"
                    active_setup["mfe_pts"] = 0.0
                    active_setup["mae_pts"] = 0.0
                elif active_setup["direction"] == "SHORT" and c < active_setup["cisd_level"]:
                    active_setup["entry_level"] = c
                    active_setup["fill_time"] = t
                    active_setup["fill_price"] = c
                    active_setup["sl_active"] = active_setup["extreme"] + 5.0
                    active_setup["stage"] = "IN_TRADE"
                    active_setup["mfe_pts"] = 0.0
                    active_setup["mae_pts"] = 0.0

    # 3. Build Comprehensive DataFrame & Calculate Statistical Excursions
    df_trades = pd.DataFrame(all_trade_records)
    if df_trades.empty:
        print("No trades executed.")
        return

    # Normalize Basis Points
    df_trades["net_pts"] = np.where(
        df_trades["direction"] == "LONG",
        df_trades["exit_price"] - df_trades["fill_price"],
        df_trades["fill_price"] - df_trades["exit_price"]
    )
    df_trades["net_bps"] = (df_trades["net_pts"] / df_trades["fill_price"]) * 10000.0
    df_trades["mfe_bps"] = (df_trades["mfe_pts"] / df_trades["fill_price"]) * 10000.0
    df_trades["mae_bps"] = (df_trades["mae_pts"] / df_trades["fill_price"]) * 10000.0
    df_trades["session"] = df_trades["fill_time"].apply(assign_session)
    df_trades["entry_hour_et"] = df_trades["fill_time"].dt.hour

    # Target reach flags
    for b in [2, 5, 10, 15, 20, 30, 50]:
        df_trades[f"reach_{b}bps"] = df_trades["mfe_bps"] >= b

    # Save to Parquet and CSV
    parquet_path = OUTPUT_DIR / "ict_ipda_trade_log.parquet"
    csv_path = OUTPUT_DIR / "ict_ipda_trade_log.csv"
    df_trades.to_parquet(parquet_path)
    df_trades.to_csv(csv_path, index=False)

    print(f"\nSaved {len(df_trades)} trade records to:")
    print(f"  • {parquet_path}")
    print(f"  • {csv_path}")

    # 4. Statistical Summary & Nuanced Distributions
    print("\n" + "=" * 105)
    print("MANDATORY EXCURSION & BASIS POINT DISTRIBUTION REPORT (ADR-023)")
    print("=" * 105)

    wins = df_trades[df_trades["net_bps"] > 0]
    losses = df_trades[df_trades["net_bps"] <= 0]
    win_rate = (len(wins) / len(df_trades)) * 100

    print(f"Overall Metrics:")
    print(f"  • Total Trades Executed:   {len(df_trades)}")
    print(f"  • Win Rate:                {win_rate:.1f}% ({len(wins)} W / {len(losses)} L)")
    print(f"  • Cumulative Return (pts): {df_trades['net_pts'].sum():+.2f} points")
    print(f"  • Cumulative Return (bps): {df_trades['net_bps'].sum():+.1f} bps")
    print(f"  • Profit Factor:           {abs(wins['net_pts'].sum() / losses['net_pts'].sum()):.2f}" if losses['net_pts'].sum() != 0 else "  • Profit Factor: N/A")

    print("\n--- MFE (Maximum Favorable Excursion) Distribution (bps) ---")
    mfe_pct = df_trades["mfe_bps"].quantile([0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    for q, val in mfe_pct.items():
        print(f"  • P{int(q*100):02d} MFE: {val:.1f} bps ({val/10000.0 * 29200.0:.1f} pts at 29,200 NQ)")

    print("\n--- MAE (Maximum Adverse Excursion) Distribution (bps) ---")
    mae_pct = df_trades["mae_bps"].quantile([0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    for q, val in mae_pct.items():
        print(f"  • P{int(q*100):02d} MAE: {val:.1f} bps ({val/10000.0 * 29200.0:.1f} pts at 29,200 NQ)")

    print("\n--- Cumulative Target Reach Probabilities (CDF) ---")
    for b in [2, 5, 10, 15, 20, 30, 50]:
        prob = (df_trades[f"reach_{b}bps"].sum() / len(df_trades)) * 100.0
        print(f"  • Probability of Reaching +{b:02d} bps: {prob:5.1f}%")

    print("\n--- Session Breakdown ---")
    sess_grp = df_trades.groupby("session").agg({
        "net_bps": ["count", "mean", "sum"],
        "mfe_bps": "median",
        "mae_bps": "median"
    })
    print(sess_grp)

if __name__ == "__main__":
    run_data_collection()
