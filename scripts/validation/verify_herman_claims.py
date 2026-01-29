
import pandas as pd
import numpy as np
import pytz
from datetime import time, timedelta
import tqdm

# --- CONFIG ---
TICKER = "NQ1"
DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
NY_TZ = pytz.timezone("America/New_York")

# Herman Session Definitions (ET)
# Asia: 20:00 - 00:00
# Pre-London: 00:00 - 02:00
# London: 02:00 - 05:00

def load_data():
    print(f"Loading {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    if df.index.tz is None:
        df.index = df.index.tz_localize(pytz.utc).tz_convert(NY_TZ)
    else:
        df.index = df.index.tz_convert(NY_TZ)
    return df

def get_session_stats(df_day_subset, start_time_str, end_time_str):
    # This function assumes df_day_subset covers the relevant times
    # Note: Asia (20:00-00:00) crosses midnight? 
    # Herman definition: "Asia Session: 20:00 – 00:00". 
    # Usually this means 20:00 prev day to 00:00 current day.
    # Pre-London: 00:00 – 02:00 (Current Day)
    
    # We will slice properly in the main loop
    mask = df_day_subset.between_time(start_time_str, end_time_str)
    if mask.empty:
        return None
        
    return {
        'high': mask['high'].max(),
        'low': mask['low'].min(),
        'range': mask['high'].max() - mask['low'].min()
    }

def process_data(df):
    # We need to iterate by Trading Day.
    # A trading day for this purpose centers around the London session (02:00).
    # Asia starts 20:00 previous day.
    # So let's group by "Shifted Date" where we shift back by, say, 10 hours?
    # 02:00 - 10h = 16:00 prev day.
    # 20:00 - 10h = 10:00 prev day.
    # Let's shift index by -10 hours? No.
    # If we want 20:00 prev day to belong to "Today", we shift times FORWARD logic or BACKWARD logic.
    # 20:00 (Day 1) -> belongs to Day 2 structure.
    # So if we add hours, 20:00 + 4 = 24:00 (Day 2).
    # Let's shift index + 4 hours.
    
    df['metrics_date'] = (df.index + pd.Timedelta(hours=4)).date
    grouped = df.groupby('metrics_date')
    
    results = []
    
    for d, group in tqdm.tqdm(grouped):
        # 1. Asia (20:00 - 23:59 approx)
        # In this group (shifted +4h), 20:00 real time is 24:00 shifted. 
        # Wait, if we shift +4h:
        # 20:00 real -> 00:00 next day metric.
        # 00:00 real -> 04:00 next day metric.
        # 05:00 real -> 09:00 next day metric.
        # So effectively, all these sessions fall into the SAME 'metrics_date'. Perfect.
        
        # Recover real times
        # Asia: 20:00 - 00:00 (exclusive of 00:00 typically? or inclusive 23:59)
        # Let's use string slicing on the group which has real datetime index
        
        # Asia: 20:00 (prev) to 00:00 (curr). 
        # But 'group' contains multiple days? No, groupby date splits them.
        # However, 'between_time' handles time of day.
        # Combining 20:00 and 00:00 in one between_time call ONLY works if on same day OR check logic.
        # Actually, since we grouped by a shifted date, the '20:00' rows are at the start of the block (conceptually earlier real time).
        # We can just extract by time.
        
        # Asia: 20:00 - 23:59
        asia_part1 = group.between_time("20:00", "23:59")
        # Asia Part 2: 00:00? Herman says 20:00-00:00.
        # Usually 00:00 is start of Pre-London.
        # Let's assume Asia ends at 23:59:59.
        
        asia_high = asia_part1['high'].max() if not asia_part1.empty else None
        asia_low = asia_part1['low'].min() if not asia_part1.empty else None
        
        if pd.isna(asia_high): continue
        
        asia_range = asia_high - asia_low
        
        # Pre-London: 00:00 - 02:00
        pl = group.between_time("00:00", "01:59")
        if pl.empty: continue
        
        pl_high = pl['high'].max()
        pl_low = pl['low'].min()
        
        # London: 02:00 - 05:00
        lon = group.between_time("02:00", "04:59")
        if lon.empty: continue
        
        lon_high = lon['high'].max()
        lon_low = lon['low'].min()
        
        # --- METRICS ---
        res = {
            'date': d,
            'asia_range': asia_range,
            # PL Sweeps
            'pl_sweeps_asia_h': pl_high > asia_high,
            'pl_sweeps_asia_l': pl_low < asia_low,
            # London Sweeps (Cumulative? Herman "London Session... Sweeps Asia High" usually implies solely within session or cumulative?)
            # Herman distincts "London Session" from "Combined Session".
            # "London Session (02:00-05:00) ... Sweeps Asia High: 59%".
            # This implies the London price action ITSELF exceeds Asia High.
            'lon_sweeps_asia_h': lon_high > asia_high,
            'lon_sweeps_asia_l': lon_low < asia_low,
            # Combined (PL + Lon)
            'combined_sweeps_asia_h': max(pl_high, lon_high) > asia_high,
            'combined_sweeps_asia_l': min(pl_low, lon_low) < asia_low,
            
            # Continuation Logic
            # If PL Swept High -> Did London Sweep High?
            # (Requires PL to have swept high).
        }
        results.append(res)
        
    return pd.DataFrame(results)

def analyze_results(df):
    print("\n--- HERMAN VERIFICATION RESULTS ---")
    print(f"Sample Size: {len(df)} days")
    
    # 1. Asia Range
    avg_asia = df['asia_range'].mean()
    # Approx 5 years recent
    recent_qs = df['date'] > (df['date'].max() - timedelta(days=365*5))
    avg_asia_5y = df[recent_qs]['asia_range'].mean()
    
    print(f"\n1. Asia Range Avg:")
    print(f"   Full History: {avg_asia:.2f} pts")
    print(f"   Last 5 Years: {avg_asia_5y:.2f} pts (Herman Ref: 78.45)")
    
    # 2. Pre-London Sweeps
    pl_sw_h = df['pl_sweeps_asia_h'].mean() * 100
    pl_sw_l = df['pl_sweeps_asia_l'].mean() * 100
    
    print(f"\n2. Pre-London (00:00-02:00) Sweeps:")
    print(f"   Sweeps Asia High: {pl_sw_h:.1f}% (Herman Ref: 34.4%)")
    print(f"   Sweeps Asia Low:  {pl_sw_l:.1f}% (Herman Ref: 27.3%)")
    
    # 3. London Sweeps
    lon_sw_h = df['lon_sweeps_asia_h'].mean() * 100
    lon_sw_l = df['lon_sweeps_asia_l'].mean() * 100
    
    print(f"\n3. London (02:00-05:00) Sweeps:")
    print(f"   Sweeps Asia High: {lon_sw_h:.1f}% (Herman Ref: 59.8%)")
    print(f"   Sweeps Asia Low:  {lon_sw_l:.1f}% (Herman Ref: 49.5%)")

    # 4. Continuation
    # "If Pre took Asia High -> London takes same high again: 77.16%"
    # Note: This usually means "London ALSO exceeds the Asia High". 
    # Since Asia High is fixed, if PL > AsiaH, and we check if Lon > AsiaH.
    
    # Filter: Days where PL Swept High
    pl_high_sweep_days = df[df['pl_sweeps_asia_h']]
    if not pl_high_sweep_days.empty:
        cont_h = pl_high_sweep_days['lon_sweeps_asia_h'].mean() * 100
        print(f"\n4. Continuation (PL -> London):")
        print(f"   If PL Swept High -> London Sweeps High: {cont_h:.1f}% (Herman Ref: 77.2%)")
        
    pl_low_sweep_days = df[df['pl_sweeps_asia_l']]
    if not pl_low_sweep_days.empty:
        cont_l = pl_low_sweep_days['lon_sweeps_asia_l'].mean() * 100
        print(f"   If PL Swept Low  -> London Sweeps Low:  {cont_l:.1f}% (Herman Ref: 69.6%)")
        
    # 5. Combined
    c_sw_h = df['combined_sweeps_asia_h'].mean() * 100
    c_sw_l = df['combined_sweeps_asia_l'].mean() * 100
    print(f"\n5. Combined (Pre+Lon) Sweeps:")
    print(f"   Sweeps High: {c_sw_h:.1f}% (Herman Ref: 65.3%)")
    print(f"   Sweeps Low:  {c_sw_l:.1f}% (Herman Ref: 55.4%)")

def main():
    df = load_data()
    df_res = process_data(df)
    analyze_results(df_res)

if __name__ == "__main__":
    main()
