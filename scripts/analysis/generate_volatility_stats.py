
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta

DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\data"
SOURCE_1D = "NQ1_1d.parquet"

def verify_stats():
    print("--- Loading Data for Volatility Analysis ---")
    path_1d = os.path.join(DATA_DIR, SOURCE_1D)
    df = pd.read_parquet(path_1d)
    
    # Cleaning
    if df.index.tz is None:
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df = df.set_index('datetime')
    df.index = df.index.tz_convert('US/Eastern')
    
    # EMA Calc
    df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['prev_ema5'] = df['ema5'].shift(1)
    
    # Filter Last 52 Weeks
    end_date = df.index[-1]
    start_date = end_date - timedelta(weeks=52)
    df_yr = df[df.index >= start_date].copy()
    
    # --- WEEKLY AGGREGATION (Final Logic) ---
    # Resample to Weekly (Ending Friday)
    df_weekly = df_yr.resample('W-FRI').agg({'open':'first', 'high':'max', 'low':'min', 'close':'last'})
    df_weekly['ema5'] = df_weekly['close'].ewm(span=5, adjust=False).mean()
    df_weekly['prev_ema5'] = df_weekly['ema5'].shift(1)
    
    # Filter valid rows (where we have prev_ema5)
    df_stats = df_weekly.dropna(subset=['prev_ema5'])
    
    print(f"\n--- Weekly Analysis ({len(df_stats)} weeks) ---")
    
    # 1. Hit Rate Table (0.5% steps)
    levels = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    hit_rates = []
    
    for lvl in levels:
        # Up: High >= PrevEMA * (1 + lvl)
        hit_up = (df_stats['high'] >= df_stats['prev_ema5'] * (1 + lvl/100)).mean() * 100
        # Down: Low <= PrevEMA * (1 - lvl)
        hit_down = (df_stats['low'] <= df_stats['prev_ema5'] * (1 - lvl/100)).mean() * 100
        
        status_up = "Good" if hit_up > 70 else "Fair" if hit_up > 40 else "Rare"
        status_down = "Good" if hit_down > 70 else "Fair" if hit_down > 40 else "Rare"
        
        hit_rates.append({
            "level": f"{lvl}%",
            "hit_rate_up": round(hit_up, 1),
            "hit_rate_down": round(hit_down, 1),
            "status_up": status_up,
            "status_down": status_down
        })

    # 2. Zone Analysis
    
    def calc_zone_stats(start_pct, end_pct):
        # UP
        entries_up = (df_stats['high'] >= df_stats['prev_ema5'] * (1 + start_pct/100))
        completes_up = (df_stats['high'] >= df_stats['prev_ema5'] * (1 + end_pct/100))
        
        u_entry = entries_up.mean() * 100
        u_comp = completes_up.mean() * 100
        u_cond = (completes_up[entries_up].sum() / entries_up.sum()) * 100 if entries_up.sum() > 0 else 0
        
        # DOWN (Negative Pcts)
        entries_down = (df_stats['low'] <= df_stats['prev_ema5'] * (1 - start_pct/100))
        completes_down = (df_stats['low'] <= df_stats['prev_ema5'] * (1 - end_pct/100))
        
        d_entry = entries_down.mean() * 100
        d_comp = completes_down.mean() * 100
        d_cond = (completes_down[entries_down].sum() / entries_down.sum()) * 100 if entries_down.sum() > 0 else 0
        
        return {
            "zone": f"{start_pct}-{end_pct}%",
            "up": {"entry": round(u_entry, 1), "complete": round(u_comp, 1), "rate": round(u_cond, 1)},
            "down": {"entry": round(d_entry, 1), "complete": round(d_comp, 1), "rate": round(d_cond, 1)}
        }

    zone_2_3 = calc_zone_stats(2.0, 3.0)
    zone_25_3 = calc_zone_stats(2.5, 3.0)
    
    # 3. Output JSON
    output = {
        "timestamp": datetime.now().isoformat(),
        "weeks_analyzed": len(df_stats),
        "hit_rates": hit_rates,
        "zones": [zone_2_3, zone_25_3],
        "statistics": {
             "mean_avg": {"up": 2.75, "down": 2.05}, # Placeholder or calc real?
             "median": {"up": 2.68, "down": 0.63}
        }
    }
    
    # Calc Real Statistics (Mean/Median Excursion from EMA)
    # Excursion % = (High - EMA) / EMA * 100
    exc_up = ((df_stats['high'] - df_stats['prev_ema5']) / df_stats['prev_ema5'] * 100)
    exc_down = ((df_stats['prev_ema5'] - df_stats['low']) / df_stats['prev_ema5'] * 100) # Positive value for distance
    
    output["statistics"]["mean_avg"]["up"] = round(exc_up.mean(), 2)
    output["statistics"]["mean_avg"]["down"] = round(exc_down.mean(), 2)
    output["statistics"]["median"]["up"] = round(exc_up.median(), 2)
    output["statistics"]["median"]["down"] = round(exc_down.median(), 2)
    
    # Save
    out_path = os.path.join(r"c:\Users\vinay\tvDownloadOHLC\data\derived", "volatility_stats.json")
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
        
    print(f"Saved Volatility Stats to {out_path}")
    print("Zone 2-3% UP:", zone_2_3['up'])
    print("Zone 2.5-3% UP:", zone_25_3['up'])


if __name__ == "__main__":
    verify_stats()
