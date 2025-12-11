
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from api.services.data_loader import DATA_DIR

def load_data(ticker="NQ1"):
    # 1D Data
    p1d = Path("data") / f"{ticker}_1D.parquet"
    if not p1d.exists(): p1d = DATA_DIR / f"{ticker}_1D.parquet"
    
    # 1m Data
    p1m = Path("data") / f"{ticker}_1m.parquet"
    if not p1m.exists(): p1m = DATA_DIR / f"{ticker}_1m.parquet"
    
    if not p1d.exists() or not p1m.exists():
        print("Missing data files.")
        return None, None
        
    df1d = pd.read_parquet(p1d)
    df1m = pd.read_parquet(p1m)
    
    # Timezone adjust
    if df1d.index.tz is None: df1d = df1d.tz_localize('UTC')
    df1d = df1d.tz_convert('US/Eastern')
    
    if df1m.index.tz is None: df1m = df1m.tz_localize('UTC')
    df1m = df1m.tz_convert('US/Eastern')
    
    return df1d, df1m

def main():
    df1d, df1m = load_data("NQ1")
    if df1d is None: return
    
    # Pick dates from multiple years to check systematic drift
    target_years = [2015, 2018, 2020, 2022, 2024]
    dates_to_check = []
    
    for y in target_years:
        candidates = df1d[df1d.index.year == y].index
        if len(candidates) > 0:
            # Pick mid-year
            mid_idx = len(candidates) // 2
            dates_to_check.append(candidates[mid_idx])
            
    print(f"{'DATE':<12} | {'SOURCE':<8} | {'OPEN':<10} {'HIGH':<10} {'LOW':<10} | {'NOTES'}")
    print("-" * 80)
    
    for dt in dates_to_check:
        date_str = dt.strftime('%Y-%m-%d')
        
        # 1D Data
        # Exact match index (which implies timestamp match)
        # Note: 1D index might be 00:00 or 16:00 or 17:00?
        # We look for match on DATE
        
        # Find row in 1D
        # We iterate to find matching date
        day_row = df1d[df1d.index.date == dt.date()]
        
        if day_row.empty:
            print(f"{date_str:<12} | 1D       | MISSING")
            continue
            
        r = day_row.iloc[0]
        r1d_open = r['open']
        r1d_high = r['high']
        r1d_low = r['low']
        ts_str = r.name.strftime('%H:%M')
        
        print(f"{date_str:<12} | 1D ({ts_str})| {r1d_open:<10.2f} {r1d_high:<10.2f} {r1d_low:<10.2f} | Pct {(r1d_high-r1d_open)/r1d_open*100:.2f}%")
        
        # 1m Data - ETH (Prev 18:00 to Curr 16:00)
        prev_day = dt - timedelta(days=1)
        try:
            eth_start = pd.Timestamp(f"{prev_day.date()} 18:00", tz='US/Eastern')
            eth_end = pd.Timestamp(f"{dt.date()} 16:00", tz='US/Eastern')
            
            eth_data = df1m.loc[eth_start:eth_end]
            if not eth_data.empty:
                eth_open = eth_data.iloc[0]['open']
                eth_high = eth_data['high'].max()
                eth_low = eth_data['low'].min()
                eth_open_ts = eth_data.index[0].strftime('%H:%M')
                
                match_note = ""
                if abs(eth_open - r1d_open) < 1: match_note += "[OPEN MATCH] "
                if abs(eth_high - r1d_high) < 1: match_note += "[HIGH MATCH] "
                if abs(eth_low - r1d_low) < 1: match_note += "[LOW MATCH] "
                
                print(f"{'':<12} | 1m (ETH) | {eth_open:<10.2f} {eth_high:<10.2f} {eth_low:<10.2f} | {match_note} (First {eth_open_ts}) Pct: {(eth_high-eth_open)/eth_open*100:.2f}%")
        except Exception as e:
            print(f"Error ETH: {e}")

        # 1m Data - RTH (09:30 to 16:00)
        try:
            rth_start = pd.Timestamp(f"{dt.date()} 09:30", tz='US/Eastern')
            rth_end = pd.Timestamp(f"{dt.date()} 16:00", tz='US/Eastern')
            
            rth_data = df1m.loc[rth_start:rth_end]
            if not rth_data.empty:
                rth_open = rth_data.iloc[0]['open']
                rth_high = rth_data['high'].max()
                rth_low = rth_data['low'].min()
                
                match_note = ""
                if abs(rth_open - r1d_open) < 1: match_note += "[OPEN MATCH] "
                
                print(f"{'':<12} | 1m (RTH) | {rth_open:<10.2f} {rth_high:<10.2f} {rth_low:<10.2f} | {match_note} Pct: {(rth_high-rth_open)/rth_open*100:.2f}%")
        except:
            pass
            
        print("-" * 80)

if __name__ == "__main__":
    main()
