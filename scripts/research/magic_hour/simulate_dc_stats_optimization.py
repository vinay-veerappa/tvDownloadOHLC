"""
NY Session Strategy Simulation: DC Session Stats Optimization
=============================================================
Comparing Session Definitions (RTH vs Full Day) & Manipulation Reversal Logic.

Logic:
1. Calculate Daily Stats for:
   - RTH (09:30 - 16:00 ET)
   - Full Day (00:00 - 16:00 ET)
2. Metrics: Rolling 20-Day Median Manipulation & Distribution.
3. Strategy: 
   - Wait for 9:30-9:40 Range Breakout.
   - Setup A: Baseline (Breakout).
   - Setup B: Manip Reversal (Must touch Open - Median_Manip before breakout).
4. Optimization: Compare Win Rate/PnL across Session Types and Setups.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

# =============================================================================
# Configuration
# =============================================================================

DATA_PATH = Path("data/NQ1_1m.parquet")
TIMEZONE = "America/New_York"
ROLLING_WINDOW = 20

@dataclass
class TradeResult:
    date: str
    direction: str
    pnl_points: float
    session_def: str # "RTH" or "FullDay"
    setup_type: str  # "Baseline" or "Manip Reversal"
    filtered: bool

def load_data(start_date: str, end_date: str) -> pd.DataFrame:
    print(f"Loading data from {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    if df.index.tz is None:
        df.index = pd.to_datetime(df.index).tz_localize("UTC")
    df.index = df.index.tz_convert(TIMEZONE)
    # Filter for RTH/Full Day Relevant Times (e.g., ignore > 16:15 for simplicity unless needed)
    df = df[(df.index >= start_date) & (df.index <= end_date)].copy()
    
    df["date"] = df.index.date
    df["hour"] = df.index.hour
    df["minute"] = df.index.minute
    return df

def get_session_stats(df: pd.DataFrame, session_type: str) -> pd.DataFrame:
    """Calculates Daily Dist/Manip Stats for a given session definition"""
    
    if session_type == "RTH":
        # 09:30 - 16:00
        mask = ((df["hour"] == 9) & (df["minute"] >= 30)) | ((df["hour"] >= 10) & (df["hour"] < 16))
    else: # "FullDay"
        # 00:00 - 16:00 (Midnight to Close)
        mask = (df["hour"] < 16) | ((df["hour"] == 16) & (df["minute"] == 0))
        
    sess_data = df[mask]
    
    daily = sess_data.groupby("date").agg(
        day_open=("open", "first"),
        day_high=("high", "max"),
        day_low=("low", "min"),
        day_close=("close", "last")
    )
    
    # Calculate Dist/Manip
    # Green Day: Manip = Open - Low, Dist = High - Open
    # Red Day: Manip = High - Open, Dist = Open - Low
    daily["manipulation"] = np.where(
        daily["day_close"] > daily["day_open"],
        daily["day_open"] - daily["day_low"],
        daily["day_high"] - daily["day_open"]
    )
    
    daily["distribution"] = np.where(
        daily["day_close"] > daily["day_open"],
        daily["day_high"] - daily["day_open"],
        daily["day_open"] - daily["day_low"]
    )
    
    # Rolling Medians (Shift 1 = Previous Days)
    daily["med_manip"] = daily["manipulation"].rolling(window=ROLLING_WINDOW).median().shift(1)
    daily["med_dist"] = daily["distribution"].rolling(window=ROLLING_WINDOW).median().shift(1)
    
    return daily

def simulate_day(day_df: pd.DataFrame, rth_stats: pd.Series, full_stats: pd.Series) -> List[TradeResult]:
    results = []
    date_str = str(day_df["date"].iloc[0])
    
    # Needs valid stats
    has_rth = not pd.isna(rth_stats["med_manip"]) if not rth_stats.empty else False
    has_full = not pd.isna(full_stats["med_manip"]) if not full_stats.empty else False
    
    if not has_rth and not has_full:
        return []

    # 1. Logic for Breakout (9:30-9:40 Range)
    range_mask = (day_df["hour"] == 9) & (day_df["minute"] >= 30) & (day_df["minute"] < 40)
    range_data = day_df[range_mask]
    if range_data.empty: return []
    
    r_high = range_data["high"].max()
    r_low = range_data["low"].min()
    
    # 2. Get 9:30 Open (Session Open for the Strategy Execution)
    # The user strategy usually anchors to the 9:30 Open for the "NY Session Trade".
    open_930 = range_data.iloc[0]["open"]

    # 3. Define Levels for Each Session Definition
    configs = []
    if has_rth: configs.append({"type": "RTH", "stats": rth_stats})
    if has_full: configs.append({"type": "FullDay", "stats": full_stats})
    
    for cfg in configs:
        stype = cfg["type"]
        stats = cfg["stats"]
        
        manip_val = stats["med_manip"]
        dist_val = stats["med_dist"]
        
        # Levels relative to 9:30 Open (Strategy Assumption: We trade the NY Session)
        long_manip_level = open_930 - manip_val
        short_manip_level = open_930 + manip_val
        
        long_dist_limit = open_930 + dist_val
        short_dist_limit = open_930 - dist_val
        
        # Did we touch Manipulation Level?
        # Check Pre-Breakout (00:00 -> 9:40)? Or just 9:30-9:40?
        # "Entire trading day" suggests we check if the manipulation occurred earlier in the day too (electronic session).
        # Let's check from Midnight (start of `day_df`) up until the breakout moment.
        
        pre_trade = day_df[day_df.index < range_data.index[-1]] # Up to 9:39
        touched_long_manip = pre_trade["low"].min() <= long_manip_level
        touched_short_manip = pre_trade["high"].max() >= short_manip_level
        
        # Trade Execution
        trade_df = day_df[day_df.index >= range_data.index[-1] + pd.Timedelta(minutes=1)]
        
        for idx, row in trade_df.iterrows():
            if row["hour"] >= 15 and row["minute"] >= 55: break
            
            close = row["close"]
            
            # Update Touch (Late Manipulation)
            if row["low"] <= long_manip_level: touched_long_manip = True
            if row["high"] >= short_manip_level: touched_short_manip = True
            
            # LONG Breakout
            if close > r_high:
                # Filter: Don't buy if > Dist Limit
                if close < long_dist_limit:
                    stop = r_low
                    pnl = run_trade(trade_df, idx, "LONG", close, stop)
                    
                    # Baseline Result
                    results.append(TradeResult(date_str, "LONG", pnl, stype, "Baseline", False))
                    
                    # Manip Reversal Result
                    if touched_long_manip:
                         results.append(TradeResult(date_str, "LONG", pnl, stype, "Manip Reversal", False))
                else:
                    results.append(TradeResult(date_str, "LONG", 0, stype, "Baseline", True))
                # Break loop after first signal
                break

            # SHORT Breakout
            elif close < r_low:
                if close > short_dist_limit:
                    stop = r_high
                    pnl = run_trade(trade_df, idx, "SHORT", close, stop)
                    
                    results.append(TradeResult(date_str, "SHORT", pnl, stype, "Baseline", False))
                    
                    if touched_short_manip:
                        results.append(TradeResult(date_str, "SHORT", pnl, stype, "Manip Reversal", False))
                else:
                    results.append(TradeResult(date_str, "SHORT", 0, stype, "Baseline", True))
                break
                
    return results

def run_trade(trade_df, start_idx, direction, entry, stop):
    future_bars = trade_df[trade_df.index > start_idx]
    for _, row in future_bars.iterrows():
        if row["hour"] >= 15 and row["minute"] >= 55:
            return (row["close"] - entry) if direction == "LONG" else (entry - row["close"])
        
        if direction == "LONG":
            if row["low"] <= stop: return stop - entry
        else:
            if row["high"] >= stop: return entry - stop
            
    if not future_bars.empty:
        last = future_bars.iloc[-1]["close"]
        return (last - entry) if direction == "LONG" else (entry - last)
    return 0.0

def main():
    df = load_data("2023-01-01", "2024-12-31")
    
    print("Calculating RTH Stats...")
    stats_rth = get_session_stats(df, "RTH")
    print("Calculating Full Day Stats...")
    stats_full = get_session_stats(df, "FullDay")
    
    results = []
    days = [group for _, group in df.groupby("date")]
    print(f"Simulating {len(days)} days...")
    
    for day_df in days:
        date_obj = day_df["date"].iloc[0]
        
        rth_s = stats_rth.loc[date_obj] if date_obj in stats_rth.index else pd.Series()
        full_s = stats_full.loc[date_obj] if date_obj in stats_full.index else pd.Series()
        
        day_res = simulate_day(day_df, rth_s, full_s)
        results.extend(day_res)
        
    res_df = pd.DataFrame(results)
    
    print("\noptimization Results:")
    summary = []
    
    for stype in ["RTH", "FullDay"]:
        for setup in ["Baseline", "Manip Reversal"]:
            subset = res_df[(res_df["session_def"] == stype) & (res_df["setup_type"] == setup) & (res_df["filtered"] == False)]
            total = len(subset)
            wins = len(subset[subset["pnl_points"] > 0])
            win_rate = (wins / total * 100) if total > 0 else 0
            avg_pnl = subset["pnl_points"].mean() if total > 0 else 0
            
            summary.append({
                "Session": stype,
                "Setup": setup,
                "Trades": total,
                "Win Rate": win_rate,
                "Avg PnL": avg_pnl
            })
            
    sum_df = pd.DataFrame(summary)
    print(sum_df.to_string(index=False, float_format="%.2f"))
    
    out_path = Path("docs/strategies/magic_hour_analysis/SESSION_DEF_OPTIMIZATION.md")
    out_path.write_text(sum_df.to_string(index=False, float_format="%.2f"), encoding="utf-8")

if __name__ == "__main__":
    main()
