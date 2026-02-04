
import pandas as pd
import numpy as np
import pytz
import os
import argparse
from datetime import time, timedelta
from pathlib import Path
from tqdm import tqdm

# --- CONFIG ---
DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "derived"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
NY_TZ = pytz.timezone("America/New_York")

def load_data(ticker):
    path = DATA_DIR / f"{ticker}_1m.parquet"
    if not path.exists():
        print(f"Error: {path} not found.")
        return None
    print(f"Loading {path}...")
    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize(pytz.utc).tz_convert(NY_TZ)
    else:
        df.index = df.index.tz_convert(NY_TZ)
    return df

def process_herman_stats(ticker):
    df = load_data(ticker)
    if df is None: return

    # Shift Logic: Group "Trading Day"
    # Asia (20:00) belongs to the NEXT day's session structure.
    # Shift index + 4 hours to push 20:00 into 00:00 of the next date.
    df['metrics_date'] = (df.index + pd.Timedelta(hours=4)).date
    grouped = df.groupby('metrics_date')
    
    results = []
    
    for d, group in tqdm(grouped, desc=f"Processing {ticker} Herman Stats"):
        # 1. Asia (20:00 - 23:59)
        # Note: 00:00 is technically excluded or start of PL? Herman says 20:00-00:00.
        asia = group.between_time("20:00", "23:59")
        if asia.empty: continue
        
        asia_high = asia['high'].max()
        asia_low = asia['low'].min()
        asia_range = asia_high - asia_low
        asia_close = asia['close'].iloc[-1]
        
        # 2. Pre-London (00:00 - 02:00)
        pl = group.between_time("00:00", "01:59")
        pl_high = pl['high'].max() if not pl.empty else np.nan
        pl_low = pl['low'].min() if not pl.empty else np.nan
        
        # 3. London (02:00 - 05:00)
        lon = group.between_time("02:00", "04:59")
        lon_high = lon['high'].max() if not lon.empty else np.nan
        lon_low = lon['low'].min() if not lon.empty else np.nan
        lon_open = lon['open'].iloc[0] if not lon.empty else np.nan
        
        # 4. Opening Range (02:00 - 03:00) - Herman's Specific "London Open"
        # Herman sometimes refers to OR as 02:00-03:00 or 03:00-03:05?
        # In "London Playbook", Open Range is "02:00 – 03:00 ET".
        lon_or = group.between_time("02:00", "02:59")
        or_high = lon_or['high'].max() if not lon_or.empty else np.nan
        or_low = lon_or['low'].min() if not lon_or.empty else np.nan
        
        # 5. NY AM Session (07:00 - 10:00) - "NY Killzone"
        ny_am = group.between_time("07:00", "09:59")
        ny_am_high = ny_am['high'].max() if not ny_am.empty else np.nan
        ny_am_low = ny_am['low'].min() if not ny_am.empty else np.nan
        ny_am_range = ny_am_high - ny_am_low if not pd.isna(ny_am_high) else np.nan

        # 6. NY Lunch Session (12:00 - 13:00)
        ny_lunch = group.between_time("12:00", "12:59")
        ny_lunch_high = ny_lunch['high'].max() if not ny_lunch.empty else np.nan
        ny_lunch_low = ny_lunch['low'].min() if not ny_lunch.empty else np.nan
        ny_lunch_range = ny_lunch_high - ny_lunch_low if not pd.isna(ny_lunch_high) else np.nan

        # 7. NY PM Session (13:00 - 16:00) - "PM Macro"
        ny_pm = group.between_time("13:00", "15:59")
        ny_pm_high = ny_pm['high'].max() if not ny_pm.empty else np.nan
        ny_pm_low = ny_pm['low'].min() if not ny_pm.empty else np.nan
        ny_pm_range = ny_pm_high - ny_pm_low if not pd.isna(ny_pm_high) else np.nan

        # --- Derived Metrics ---
        # Did PL Sweep Asia?
        pl_sw_h = pl_high > asia_high if not pd.isna(pl_high) else False
        pl_sw_l = pl_low < asia_low if not pd.isna(pl_low) else False
        
        # Did London Sweep Asia?
        lon_sw_h = lon_high > asia_high if not pd.isna(lon_high) else False
        lon_sw_l = lon_low < asia_low if not pd.isna(lon_low) else False
        
        # Did NY AM Sweep London?
        ny_am_sw_lon_h = ny_am_high > lon_high if not pd.isna(ny_am_high) and not pd.isna(lon_high) else False
        ny_am_sw_lon_l = ny_am_low < lon_low if not pd.isna(ny_am_low) and not pd.isna(lon_low) else False
        
        # Did NY AM Sweep Asia?
        ny_am_sw_asia_h = ny_am_high > asia_high if not pd.isna(ny_am_high) else False
        ny_am_sw_asia_l = ny_am_low < asia_low if not pd.isna(ny_am_low) else False

        # Did NY Lunch Sweep NY AM?
        ny_lunch_sw_am_h = ny_lunch_high > ny_am_high if not pd.isna(ny_lunch_high) and not pd.isna(ny_am_high) else False
        ny_lunch_sw_am_l = ny_lunch_low < ny_am_low if not pd.isna(ny_lunch_low) and not pd.isna(ny_am_low) else False

        # Did NY PM Sweep NY AM?
        ny_pm_sw_ny_am_h = ny_pm_high > ny_am_high if not pd.isna(ny_pm_high) and not pd.isna(ny_am_high) else False
        ny_pm_sw_ny_am_l = ny_pm_low < ny_am_low if not pd.isna(ny_pm_low) and not pd.isna(ny_am_low) else False
        
        # Did NY PM Sweep Lunch?
        ny_pm_sw_lunch_h = ny_pm_high > ny_lunch_high if not pd.isna(ny_pm_high) and not pd.isna(ny_lunch_high) else False
        ny_pm_sw_lunch_l = ny_pm_low < ny_lunch_low if not pd.isna(ny_pm_low) and not pd.isna(ny_lunch_low) else False
        
        # Herman Classification
        # Asia Type
        asia_type = "Large" if asia_range > 70.9 else "Small"
        
        results.append({
            'date': d,
            'asia_high': asia_high, 'asia_low': asia_low, 'asia_range': asia_range, 'asia_type': asia_type,
            'asia_open': asia['open'].iloc[0] if not asia.empty else np.nan, 'asia_close': asia['close'].iloc[-1] if not asia.empty else np.nan,
            
            'pl_high': pl_high, 'pl_low': pl_low, 
            'pl_open': pl['open'].iloc[0] if not pl.empty else np.nan, 'pl_close': pl['close'].iloc[-1] if not pl.empty else np.nan,
            'pl_sweeps_asia_h': pl_sw_h, 'pl_sweeps_asia_l': pl_sw_l,
            
            'lon_open': lon_open, 'lon_high': lon_high, 'lon_low': lon_low, 
            'lon_close': lon['close'].iloc[-1] if not lon.empty else np.nan,
            'lon_sweeps_asia_h': lon_sw_h, 'lon_sweeps_asia_l': lon_sw_l,
            
            'or_high': or_high, 'or_low': or_low,
            
            'ny_am_high': ny_am_high, 'ny_am_low': ny_am_low, 'ny_am_range': ny_am_range,
            'ny_am_open': ny_am['open'].iloc[0] if not ny_am.empty else np.nan,
            'ny_am_close': ny_am['close'].iloc[-1] if not ny_am.empty else np.nan,
            'ny_am_sweeps_lon_h': ny_am_sw_lon_h, 'ny_am_sweeps_lon_l': ny_am_sw_lon_l,
            'ny_am_sweeps_asia_h': ny_am_sw_asia_h, 'ny_am_sweeps_asia_l': ny_am_sw_asia_l,
            
            'ny_lunch_high': ny_lunch_high, 'ny_lunch_low': ny_lunch_low, 'ny_lunch_range': ny_lunch_range,
            'ny_lunch_open': ny_lunch['open'].iloc[0] if not ny_lunch.empty else np.nan,
            'ny_lunch_close': ny_lunch['close'].iloc[-1] if not ny_lunch.empty else np.nan,
            'ny_lunch_sweeps_am_h': ny_lunch_sw_am_h, 'ny_lunch_sweeps_am_l': ny_lunch_sw_am_l,
            
            'ny_pm_high': ny_pm_high, 'ny_pm_low': ny_pm_low, 'ny_pm_range': ny_pm_range,
            'ny_pm_open': ny_pm['open'].iloc[0] if not ny_pm.empty else np.nan,
            'ny_pm_close': ny_pm['close'].iloc[-1] if not ny_pm.empty else np.nan,
            'ny_pm_sweeps_ny_am_h': ny_pm_sw_ny_am_h, 'ny_pm_sweeps_ny_am_l': ny_pm_sw_ny_am_l,
            'ny_pm_sweeps_lunch_h': ny_pm_sw_lunch_h, 'ny_pm_sweeps_lunch_l': ny_pm_sw_lunch_l
        })
        
    df_res = pd.DataFrame(results)
    out_path = OUTPUT_DIR / f"{ticker}_herman_stats.parquet"
    df_res.to_parquet(out_path)
    print(f"Saved {len(df_res)} rows to {out_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol")
    args = parser.parse_args()
    
    process_herman_stats(args.ticker)

if __name__ == "__main__":
    main()
