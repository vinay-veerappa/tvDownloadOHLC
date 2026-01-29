
import pandas as pd
import numpy as np
import pytz
from datetime import time
from pathlib import Path
import tqdm

# --- CONFIG ---
DATA_DIR = Path("data")
DERIVED_DIR = DATA_DIR / "derived"
TICKER = "NQ1"
NY_TZ = pytz.timezone("America/New_York")

# --- USER DEFINITIONS ---
SESSIONS = {
    'Asia':   {'start': time(18, 00), 'end': time(19, 30)},
    'London': {'start': time(2, 30),  'end': time(3, 30)},
    'NY1':    {'start': time(7, 30),  'end': time(8, 30)},
    'NY2':    {'start': time(11, 30), 'end': time(12, 30)} 
}

# STATUS WINDOWS (Session End -> Next Session Start)
STATUS_WINDOWS = {
    'Asia':   ('19:30', '02:29'),
    'London': ('03:30', '07:29'),
    'NY1':    ('08:30', '11:29'),
    'NY2':    ('12:30', '16:00') # Matches Pine implied? Pine st_ny2 logic uses s_ny2 "1230-1659"
}

# BROKEN WINDOWS (Next Session Start -> ?? / Reference Pine Logic)
# Pine:
# bw_asia = "0230-1700"
# bw_lon  = "0730-1700"
# bw_ny1  = "1130-1700"
# bw_ny2  = "1600-1700"

BROKEN_WINDOWS = {
    'Asia':   ('02:30', '17:00'),
    'London': ('07:30', '17:00'),
    'NY1':    ('11:30', '17:00'),
    'NY2':    ('16:00', '17:00') 
}

def load_data():
    class_path = DERIVED_DIR / f"{TICKER}_daily_classification.parquet"
    if not class_path.exists():
        print("Error: Classification parquet not found.")
        return None, None
    df_class = pd.read_parquet(class_path)
    df_class['date'] = pd.to_datetime(df_class['date']).dt.date
    
    ohlc_path = DATA_DIR / f"{TICKER}_1m.parquet"
    if not ohlc_path.exists():
        print("Error: 1m parquet not found.")
        return None, None
    df_ohlc = pd.read_parquet(ohlc_path)
    if df_ohlc.index.tz is None:
        df_ohlc.index = df_ohlc.index.tz_localize(pytz.utc).tz_convert(NY_TZ)
    else:
        df_ohlc.index = df_ohlc.index.tz_convert(NY_TZ)
        
    return df_class, df_ohlc

def get_session_stats(df_day, session_name):
    cfg = SESSIONS[session_name]
    start_str = cfg['start'].strftime('%H:%M')
    end_str = cfg['end'].strftime('%H:%M')
    
    # Handle overlap day for Asia?
    # Usually assume df_day covers the full trading day (18:00 prev -> 17:00 curr)
    # If df_day is just date-based, it might miss 18:00 prev.
    # We rely on specific slicing below.
    
    mask = df_day.between_time(start_str, end_str)
    if mask.empty:
        return None
        
    h = mask['high'].max()
    l = mask['low'].min()
    return {'h': h, 'l': l, 'mid': (h+l)/2}

def check_status(df_day, stats, window_cfg):
    start_str, end_str = window_cfg
    mask = df_day.between_time(start_str, end_str)
    
    if mask.empty or stats is None:
        return 'None'
        
    h, l, mid = stats['h'], stats['l'], stats['mid']
    
    high_breaks = mask[mask['high'] > h]
    low_breaks = mask[mask['low'] < l]
    
    broke_high = not high_breaks.empty
    broke_low = not low_breaks.empty
    
    if not broke_high and not broke_low:
        return 'None'
        
    if broke_high and not broke_low:
        return 'Long True'
        
    if broke_low and not broke_high:
        return 'Short True'
        
    # Both broken
    first_hb = high_breaks.index[0]
    first_lb = low_breaks.index[0]
    
    if first_hb < first_lb:
        return 'Long False' 
    else:
        return 'Short False'

def check_broken(df_day, stats, broken_window_cfg):
    start_str, end_str = broken_window_cfg
    mask = df_day.between_time(start_str, end_str)
    
    if mask.empty or stats is None:
        return False
        
    mid = stats['mid']
    touches = mask[(mask['low'] <= mid) & (mask['high'] >= mid)]
    return not touches.empty

def process_day(date, df_day):
    # This DF needs to cover the FULL trading session (18:00 prev to 17:00 curr)
    # The 'groupby(date)' usually groups by midnight-to-midnight or 'Trading Date'.
    # IMPORTANT: Ensure the dataframe passed here has the right rows.
    # The calling function uses 'groupby(df.index.date)' which is MIDNIGHT based.
    # So for Asia (18:00 prev), we need the previous day's rows?
    # Actually, grouped by date 2023-01-05 contains 00:00 -> 23:59.
    # Asia (18:00) is on the Previous Calendar Day relative to the trading day?
    # Wait, 18:00 on Jan 4 is part of Jan 5 Trading Day.
    # If we group by Calendar Date Jan 5, we MISS the Asia session on Jan 4!
    
    # FIX: We need a custom Grouper or iterate intelligently.
    # Let's assume the passed df_day is purely Calendar Day for now, which is WRONG for Futures.
    
    # QUICK FIX for Verification script:
    # We will iterate linear or use a proper Trading Day mapper.
    pass 

def main():
    print("Loading data...")
    df_class, df_ohlc = load_data()
    if df_class is None: return
    
    # --- TRADING DAY ADJUSTMENT ---
    # Shift times: anything after 18:00 belongs to NEXT day.
    # So we can group by (Timestamp + 6 hours).date ?
    # 18:00 + 6h = 24:00 (Next Day). 17:59 + 6h = 23:59 (Current Day).
    # Yes, shift by +6 hours to align trading day.
    
    df_ohlc['trading_date'] = (df_ohlc.index + pd.Timedelta(hours=6)).date
    grouped = df_ohlc.groupby('trading_date')
    
    print("Calculating Daily Features...")
    results = []
    
    # Filter to only dates in classification
    valid_dates = set(df_class['date'])
    
    for d, df_day in tqdm.tqdm(grouped):
        if d not in valid_dates:
            continue
            
        res = {'date': d}
        
        # Asia
        asia = get_session_stats(df_day, 'Asia')
        # ... logic ...
        # Need to handle case where Asia is actually on 'd-1' calendar wise?
        # The 'trading_date' shift handles this. 18:00 Jan 4 becomes Jan 5.
        # So df_day for Jan 5 contains 18:00 Jan 4.
        # `between_time` works on the time component, ignoring date day.
        # So `between_time('18:00', '19:30')` will find 18:00 Jan 4 rows inside Jan 5 group.
        # Correct.
        
        # Calculate Features
        asia = get_session_stats(df_day, 'Asia')
        res['Asia_status'] = check_status(df_day, asia, STATUS_WINDOWS['Asia'])
        res['Asia_broken'] = check_broken(df_day, asia, BROKEN_WINDOWS['Asia'])
        
        london = get_session_stats(df_day, 'London')
        res['London_status'] = check_status(df_day, london, STATUS_WINDOWS['London'])
        res['London_broken'] = check_broken(df_day, london, BROKEN_WINDOWS['London'])
        
        ny1 = get_session_stats(df_day, 'NY1')
        res['NY1_status'] = check_status(df_day, ny1, STATUS_WINDOWS['NY1'])
        res['NY1_broken'] = check_broken(df_day, ny1, BROKEN_WINDOWS['NY1'])
        
        ny2 = get_session_stats(df_day, 'NY2')
        res['NY2_status'] = check_status(df_day, ny2, STATUS_WINDOWS['NY2'])
        res['NY2_broken'] = check_broken(df_day, ny2, BROKEN_WINDOWS['NY2'])
        
        results.append(res)
            
    df_features = pd.DataFrame(results)
    df_merged = pd.merge(df_class, df_features, on='date')
    
    print(f"\nMerged {len(df_merged)} Days.")
    
    def calc(title, mask):
        sub = df_merged[mask]
        n = len(sub)
        if n == 0:
            print(f"• {title}: No samples.")
            return
        dist = sub['type'].value_counts(normalize=True) * 100
        top = dist.idxmax()
        val = dist.max()
        print(f"• IF {title} THEN Likely **{top} ({val:.1f}%)** (n={n})")

    
    def calc_dist(title, dataframe, mask):
        # Allow mask to be a Series (needs alignment) or boolean array
        if hasattr(mask, 'index') and not mask.index.equals(dataframe.index):
             # Try re-aligning or assume boolean list
             pass
        
        try:
            sub = dataframe[mask]
        except:
            return # Skip if index mismatch
            
        n = len(sub)
        if n == 0:
            print(f"• {title}: No samples.")
            return
            
        counts = sub['type'].value_counts(normalize=True) * 100
        top = counts.idxmax()
        val = counts.max()
        
        # Format distribution string
        dist_str = ", ".join([f"{k}={v:.1f}%" for k, v in counts.items()])
        print(f"• {title}")
        print(f"  → Likely: **{top} ({val:.1f}%)** (n={n})")
        print(f"  → Dist:   {dist_str}")

    
    # --- HIERARCHY & LOGIC SIMULATION ---
    # User Requirement: "R1 is the first 4 hours including the 9 hour should touch the 930 opening range else it is not a R1"
    # Interpretation: 
    # 1. Include 09:30-10:00 in tracking.
    # 2. To be R1, the price must touch the OR during the "First 4 Hours" (09:00, 10:00, 11:00, 12:00 indices).
    #    Actually current script analyzes 10, 11, 12, 13, 14, 15.
    #    We need data on WHICH hours touched. The current parquet might count 'touches' but doesn't store 'touches_per_hour'.
    #    However, we might have 'first_touch_hour' or similar? No.
    #    We *do* have 'time_in_range'? No.
    
    # We might need to modify precompute to store "early_touches" boolean.
    # But first, let's revert the hierarchy in this script and see if we can filter "Good R1" vs "Bad R1".
    
    # Actually, verify script just joins existing parquet. Parquet was generated with R1 > R2 priority but standard "4+ touches" logic (starting 10am).
    # If the user wants 09:00 included, I MUST modify precompute and regenerate.
    # I cannot simulate "9 hour touch" here because the parquet doesn't have it.
    
    pass

    print("\n" + "="*50)
    print("ANALYSIS: FULL HISTORY")
    print("="*50)
    
    calc_dist("NY1 Model Status is Broken", df_merged, df_merged['NY1_broken'] == True)
    calc_dist("NY1 Model Status is None", df_merged, df_merged['NY1_status'] == 'None')
    calc_dist("NY2 Session is Invalid (False)", df_merged, df_merged['NY2_status'].str.contains('False'))
    calc_dist("LND Session is Invalid (False)", df_merged, df_merged['London_status'].str.contains('False'))
    calc_dist("ASA Session is Valid (True)", df_merged, df_merged['Asia_status'].str.contains('True'))

    print("\n" + "="*50)
    print("ANALYSIS: LAST 500 DAYS")
    print("="*50)
    
    df_recent = df_merged.sort_values('date').iloc[-500:].copy()
    
    calc_dist("NY1 Model Status is Broken", df_recent, df_recent['NY1_broken'] == True)
    calc_dist("NY1 Model Status is None", df_recent, df_recent['NY1_status'] == 'None')
    calc_dist("NY2 Session is Invalid (False)", df_recent, df_recent['NY2_status'].str.contains('False'))
    calc_dist("LND Session is Invalid (False)", df_recent, df_recent['London_status'].str.contains('False'))
    calc_dist("ASA Session is Valid (True)", df_recent, df_recent['Asia_status'].str.contains('True'))

    print("\n" + "="*50)
    print("ANALYSIS: ASIA x LONDON COMBINATIONS")
    print("="*50)
    
    # helper to simplify status
    def simplify_status(s):
        if 'True' in s: return 'Valid'
        if 'False' in s: return 'Invalid'
        return 'None'
        
    df_merged['Asia_Simple'] = df_merged['Asia_status'].apply(simplify_status)
    df_merged['London_Simple'] = df_merged['London_status'].apply(simplify_status)
    
    # Combinations of Validity
    # Asia (Valid/Invalid) x London (Valid/Invalid/Broken/Held)
    
    # 1. Validity Matrix
    asia_states = ['Valid', 'Invalid']
    lon_states = ['Valid', 'Invalid']
    
    for a in asia_states:
        for l in lon_states:
            mask = (df_merged['Asia_Simple'] == a) & (df_merged['London_Simple'] == l)
            calc_dist(f"Asia {a} + London {l}", df_merged, mask)
            
    # 2. Broken Matrix (Broken vs Held)
    # User said "ignore broken where it does not make a difference"
    # Let's check Asia Broken/Held + London Broken/Held
    
    df_merged['Asia_Brk_Str'] = df_merged['Asia_broken'].apply(lambda x: 'Broken' if x else 'Held')
    df_merged['Lon_Brk_Str'] = df_merged['London_broken'].apply(lambda x: 'Broken' if x else 'Held')
    
    for a in ['Broken', 'Held']:
        for l in ['Broken', 'Held']:
            mask = (df_merged['Asia_Brk_Str'] == a) & (df_merged['Lon_Brk_Str'] == l)
            calc_dist(f"Asia {a} + London {l}", df_merged, mask)

if __name__ == "__main__":
    main()
