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
    # NY2 start implied by end of NY1? Usually 08:30 or later.
    # User didn't give explicit NY2 time, but usually NY2 follows NY1.
    # Let's assume standard NY AM session: 09:30 - 12:00 for calculation?
    # Wait, the user image says "NY2 Session is Valid".
    # User didn't give NY2 times in the PROMPT, but let's infer from existing Pine:
    # Pine says: t_ny2 = "1130-1229" (approx).
    # Let's stick to the prompt's explicit Logic and infer NY2 as "Next Session"?
    # Actually, let's use the PineScript NY2 times for safety: 11:30 - 12:30.
    'NY2':    {'start': time(11, 30), 'end': time(12, 30)} 
}

# Next Session Starts (for Status Window):
# Asia End (19:30) -> London Start (02:30)
# London End (03:30) -> NY1 Start (07:30)
# NY1 End (08:30) -> NY2 Start (11:30)
# NY2 End (12:30) -> Close (16:00) ? 
# Let's define the "Status Window" explicitly based on gaps.

STATUS_WINDOWS = {
    'Asia':   ('19:30', '02:29'),
    'London': ('03:30', '07:29'),
    'NY1':    ('08:30', '11:29'),
    'NY2':    ('12:30', '16:00') # Estimated
}

BROKEN_WINDOWS = {
    # Broken Logic: Next Session Start -> 18:00
    # Implies we check for broken *after* the status window? 
    # Or does "Next Session Start" mean the start of the status check?
    # User said: "Broken Logic (Window: Next Session Start -> 18:00)"
    # This implies from London Start (02:30) all the way to 18:00 for Asia?
    'Asia':   ('02:30', '17:59'),
    'London': ('07:30', '17:59'),
    'NY1':    ('11:30', '17:59'),
    'NY2':    ('13:00', '17:59') # ??
}

def load_data():
    # 1. Load Classifications
    class_path = DERIVED_DIR / f"{TICKER}_daily_classification.parquet"
    df_class = pd.read_parquet(class_path)
    df_class['date'] = pd.to_datetime(df_class['date']).dt.date
    
    # 2. Load 1m Data
    ohlc_path = DATA_DIR / f"{TICKER}_1m.parquet"
    df_ohlc = pd.read_parquet(ohlc_path)
    if df_ohlc.index.tz is None:
        df_ohlc.index = df_ohlc.index.tz_localize(pytz.utc).tz_convert(NY_TZ)
    else:
        df_ohlc.index = df_ohlc.index.tz_convert(NY_TZ)
        
    return df_class, df_ohlc

def get_session_stats(df_day, session_name):
    cfg = SESSIONS[session_name]
    # Filter 
    # Note: between_time is inclusive
    # For robust minute slicing (start inclusive, end exclusive? Or inclusive?)
    # Usually standard is inclusive.
    start_str = cfg['start'].strftime('%H:%M')
    end_str = cfg['end'].strftime('%H:%M')
    
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
    
    # Check breaks
    # We need sequential "Break High then Break Low" logic?
    # Or just "Did it break?"
    # User Logic:
    # Long True: Break High, hold Low.
    # Short True: Break Low, hold High.
    # Long False: Break High, then break Low.
    # Short False: Break Low, then break High.
    
    # To do "Then", we need to iterate or find first occurrences.
    # Let's find first index of break
    
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
        
    # Both broken (Invalid)
    # Who broke first?
    first_hb = high_breaks.index[0]
    first_lb = low_breaks.index[0]
    
    if first_hb < first_lb:
        # Broke High first, then Low
        return 'Long False'
    else:
        return 'Short False'

def check_broken(df_day, stats, broken_window_cfg):
    start_str, end_str = broken_window_cfg
    mask = df_day.between_time(start_str, end_str)
    
    if mask.empty or stats is None:
        return False
        
    mid = stats['mid']
    # Broken if Price touches Mid
    # (Low <= Mid <= High)
    touches = mask[(mask['low'] <= mid) & (mask['high'] >= mid)]
    return not touches.empty

def process_day(date, df_day):
    # Calculate Sessions
    res = {}
    
    # Asia
    asia = get_session_stats(df_day, 'Asia')
    res['Asia_status'] = check_status(df_day, asia, STATUS_WINDOWS['Asia'])
    res['Asia_broken'] = check_broken(df_day, asia, BROKEN_WINDOWS['Asia'])
    
    # London
    london = get_session_stats(df_day, 'London')
    res['London_status'] = check_status(df_day, london, STATUS_WINDOWS['London'])
    res['London_broken'] = check_broken(df_day, london, BROKEN_WINDOWS['London'])
    
    # NY1
    ny1 = get_session_stats(df_day, 'NY1')
    res['NY1_status'] = check_status(df_day, ny1, STATUS_WINDOWS['NY1'])
    res['NY1_broken'] = check_broken(df_day, ny1, BROKEN_WINDOWS['NY1'])
    
    # NY2
    ny2 = get_session_stats(df_day, 'NY2')
    res['NY2_status'] = check_status(df_day, ny2, STATUS_WINDOWS['NY2'])
    res['NY2_broken'] = check_broken(df_day, ny2, BROKEN_WINDOWS['NY2'])
    
    return res

def main():
    print("Loading data...")
    df_class, df_ohlc = load_data()
    
    print("Calculating Daily Features (this may take a minute)...")
    grouped = df_ohlc.groupby(df_ohlc.index.date)
    
    results = []
    # Join keys
    dates = df_class['date'].unique()
    
    for d in tqdm.tqdm(dates):
        if d in grouped.groups:
            day_data = grouped.get_group(d)
            feats = process_day(d, day_data)
            feats['date'] = d
            results.append(feats)
            
    df_features = pd.DataFrame(results)
    
    # Merge
    df_merged = pd.merge(df_class, df_features, on='date')
    print(f"\nMerged {len(df_merged)} Days.")
    
    # --- ANALYSIS ---
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

    print("\n--- Current Day Classification ---")
    
    # 1. NY1 Model Status is Broken
    calc("NY1 Model Status is Broken", df_merged['NY1_broken'] == True)
    
    # 2. NY1 Model Status is None
    calc("NY1 Model Status is None", df_merged['NY1_status'] == 'None')
    
    # 3. NY2 Session is Invalid (False)
    # Invalid = Long False or Short False
    mask_ny2_inv = df_merged['NY2_status'].isin(['Long False', 'Short False'])
    calc("NY2 Session is Invalid (False)", mask_ny2_inv)
    
    # 4. NY2 Session is Invalid (False) AND Direction is Short
    # Invalid Short = Short False ? Or Invalid AND (Short True or Short False?)
    # "Direction is Short" usually implies the *attempted* direction.
    # Short False means it broke low (attempted short) then failed.
    # So 'Short False' fits "Invalid + Short".
    calc("NY2 Session is Invalid (False) AND Direction is Short", df_merged['NY2_status'] == 'Short False')
    
    # 5. LND Session is Invalid (False)
    mask_lnd_inv = df_merged['London_status'].isin(['Long False', 'Short False'])
    calc("LND Session is Invalid (False)", mask_lnd_inv)
    
    # 6. NY2 Session is Valid (True)
    mask_ny2_val = df_merged['NY2_status'].isin(['Long True', 'Short True'])
    calc("NY2 Session is Valid (True)", mask_ny2_val)
    
    # 7. NY2 Session is Valid (True) AND Direction is Long
    calc("NY2 Session is Valid (True) AND Direction is Long", df_merged['NY2_status'] == 'Long True')
    
    # 8. ASA Session is Valid (True)
    mask_asa_val = df_merged['Asia_status'].isin(['Long True', 'Short True'])
    calc("ASA Session is Valid (True)", mask_asa_val)
    
    # 9. LND Direction is None
    calc("LND Direction is None", df_merged['London_status'] == 'None')

if __name__ == "__main__":
    main()
