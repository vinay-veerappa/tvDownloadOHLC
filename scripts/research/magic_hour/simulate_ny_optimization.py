"""
NY Session Strategy Simulation & Optimization
=============================================
Simulates the NY Session Trend Following strategy (9:30-9:40 Range Breakout)
with various Standard Deviation filters to optimize win rate.

Logic:
1. Wait for 9:30-9:40 10m Range to complete.
2. Filter: Check Hourly Standard Deviation deviation.
   - Limit = Hourly Open +/- (Mult * Hourly_SD * Hourly Open)
   - Long allowed if Close < Upper Limit
   - Short allowed if Close > Lower Limit
3. Entry: Breakout of 10m Range (Close > High or Close < Low).
4. Stop: Protected Side (Opposite side of 10m Range).
5. Target: Fixed Reward or End of Day.
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

# Hardcoded Hourly SD (from multi_timeframe_std_dev.pine for NQ)
# Index 0 = 00:00, Index 9 = 09:00, etc.
HOURLY_SDS = [
    0.00156, 0.00153, 0.00188, 0.00250, 0.00217, 0.00184, 
    0.00195, 0.00217, 0.00345, 0.00454, 0.00475, 0.00379, 
    0.00333, 0.00368, 0.00361, 0.00461, 0.00253, 0.001, 
    0.00242, 0.00165, 0.00197, 0.00209, 0.00175, 0.00132
]

# 9:00 AM SD for 9:30 setup
SD_9AM = HOURLY_SDS[9] 

@dataclass
class TradeResult:
    date: str
    direction: str
    entry_price: float
    entry_time: str
    stop_price: float
    exit_price: float
    exit_reason: str
    pnl_points: float
    filter_mult: float
    hourly_open: float
    sd_limit_upper: float
    sd_limit_lower: float
    was_filtered: bool

def load_data(start_date: str, end_date: str) -> pd.DataFrame:
    print(f"Loading data from {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    if df.index.tz is None:
        df.index = pd.to_datetime(df.index).tz_localize("UTC")
    df.index = df.index.tz_convert(TIMEZONE)
    df = df[(df.index >= start_date) & (df.index <= end_date)].copy()
    df["date_key"] = df.index.date.astype(str)
    df["hour"] = df.index.hour
    df["minute"] = df.index.minute
    return df

def simulate_day(df_day: pd.DataFrame, sd_mult: float) -> Optional[TradeResult]:
    """Simulates a single day for the NY Session strategy"""
    date_str = df_day["date_key"].iloc[0]
    
    # 1. Get Hourly Open (09:00 Open)
    # The bar timestamp is the OPEN time. So 09:00 row has the open price.
    h9_row = df_day[(df_day["hour"] == 9) & (df_day["minute"] == 0)]
    if h9_row.empty:
        return None
    
    hourly_open = h9_row.iloc[0]["open"]
    
    # Calculate Limits
    sd_val = SD_9AM
    upper_limit = hourly_open + (sd_mult * sd_val * hourly_open)
    lower_limit = hourly_open - (sd_mult * sd_val * hourly_open)
    
    # 2. Form 10m Range (9:30 - 9:40)
    # Bars included: 09:30:00 to 09:39:00 (since 09:40:00 is the start of next bar)
    # Wait, convention: 9:30-9:40 usually means up to 9:40 close.
    # We will use 09:30 <= t < 09:40
    range_mask = (df_day["hour"] == 9) & (df_day["minute"] >= 30) & (df_day["minute"] < 40)
    range_data = df_day[range_mask]
    
    if range_data.empty:
        return None
        
    r_high = range_data["high"].max()
    r_low = range_data["low"].min()
    
    # 3. Simulate Trading (09:40 onwards)
    trade_df = df_day[df_day.index >= range_data.index[-1] + pd.Timedelta(minutes=1)].copy()
    
    if trade_df.empty:
        return None
        
    for idx, row in trade_df.iterrows():
        # Stop at 15:55 (EOD)
        if row["hour"] >= 15 and row["minute"] >= 55:
            break
            
        close = row["close"]
        time_str = row.name.strftime("%H:%M")
        
        # Check Breakout
        if close > r_high:
            # LONG SIGNAL
            # Check Filter
            if close < upper_limit:
                # Valid Long
                stop = r_low
                # Simulate outcome
                return run_trade_lifecycle(trade_df, idx, "LONG", close, stop, time_str, date_str, sd_mult, hourly_open, upper_limit, lower_limit)
            else:
                # Filtered (Blocked)
                # We stop looking for trades today? Or wait for pullback? 
                # For simplicity, first breakout only.
                return TradeResult(date_str, "LONG", close, time_str, 0, 0, "FILTERED", 0, sd_mult, hourly_open, upper_limit, lower_limit, True)
                
        elif close < r_low:
            # SHORT SIGNAL
            # Check Filter
            if close > lower_limit:
                # Valid Short
                stop = r_high
                return run_trade_lifecycle(trade_df, idx, "SHORT", close, stop, time_str, date_str, sd_mult, hourly_open, upper_limit, lower_limit)
            else:
                # Filtered
                return TradeResult(date_str, "SHORT", close, time_str, 0, 0, "FILTERED", 0, sd_mult, hourly_open, upper_limit, lower_limit, True)
                
    return None

def run_trade_lifecycle(trade_df, start_idx, direction, entry_price, stop_price, entry_time, date_str, sd_mult, h_open, u_lim, l_lim):
    """Tracks the trade bar-by-bar until stop or EOD"""
    
    # Slice dataframe from NEXT bar after entry
    # (assuming entry on close, so next bar is when we are in trade)
    # Actually, we enter AT the close price.
    
    future_bars = trade_df[trade_df.index > start_idx]
    
    for _, row in future_bars.iterrows():
        # EOD Exit
        if row["hour"] >= 15 and row["minute"] >= 55:
            return TradeResult(date_str, direction, entry_price, entry_time, stop_price, row["close"], "EOD", (row["close"] - entry_price) if direction == "LONG" else (entry_price - row["close"]), sd_mult, h_open, u_lim, l_lim, False)
            
        # Check Stop
        if direction == "LONG":
            if row["low"] <= stop_price:
                return TradeResult(date_str, direction, entry_price, entry_time, stop_price, stop_price, "STOP", stop_price - entry_price, sd_mult, h_open, u_lim, l_lim, False)
        else:
            if row["high"] >= stop_price:
                return TradeResult(date_str, direction, entry_price, entry_time, stop_price, stop_price, "STOP", entry_price - stop_price, sd_mult, h_open, u_lim, l_lim, False)
                
    # If loop ends, EOD
    if not future_bars.empty:
        last_px = future_bars.iloc[-1]["close"]
        return TradeResult(date_str, direction, entry_price, entry_time, stop_price, last_px, "EOD", (last_px - entry_price) if direction == "LONG" else (entry_price - last_px), sd_mult, h_open, u_lim, l_lim, False)
    
    return None

def run_optimization(df, multipliers):
    results = []
    
    # Group by day
    # Optimization: Pre-group to avoid repeated grouping
    days = [group for _, group in df.groupby("date_key")]
    
    print(f"Simulating {len(days)} days across {len(multipliers)} multipliers...")
    
    for mult in multipliers:
        print(f"  Testing SD Mult: {mult}")
        for day_df in days:
            res = simulate_day(day_df, mult)
            if res:
                results.append(res)
                
    return pd.DataFrame(results)

def main():
    df = load_data("2023-01-01", "2024-12-31")
    
    # Multipliers to test
    # Tighter range to see if we can boost win rate
    multipliers = [0.25, 0.5, 0.75, 1.0, 2.0]
    
    results_df = run_optimization(df, multipliers)
    
    # Analyze
    print("\noptimization Results:")
    summary = []
    
    for mult in multipliers:
        subset = results_df[(results_df["filter_mult"] == mult) & (results_df["was_filtered"] == False)]
        total = len(subset)
        wins = len(subset[subset["pnl_points"] > 0])
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_pnl = subset["pnl_points"].mean() if total > 0 else 0
        
        filtered_count = len(results_df[(results_df["filter_mult"] == mult) & (results_df["was_filtered"] == True)])
        
        summary.append({
            "SD Mult": mult,
            "Trades": total,
            "Win Rate": win_rate,
            "Avg PnL": avg_pnl,
            "Filtered Out": filtered_count
        })
        
    summary_df = pd.DataFrame(summary)
    print(summary_df.to_string(index=False, float_format="%.2f"))
    
    # Save
    output_path = Path("docs/strategies/magic_hour_analysis/NY_SESSION_OPTIMIZATION.md")
    output_path.write_text(summary_df.to_string(index=False, float_format="%.2f"), encoding="utf-8")
    print(f"\nSaved to {output_path}")

if __name__ == "__main__":
    main()
