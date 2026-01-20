
import pandas as pd
import numpy as np
import json
import os

def analyze_reversal_timing(ticker="NQ1"):
    print(f"--- Starting Reversal Timing Analysis for {ticker} ---")
    
    # 1. Load Data
    base_dir = "c:/Users/vinay/tvDownloadOHLC/data"
    parquet_path = f"{base_dir}/{ticker}_1m.parquet"
    sessions_path = f"{base_dir}/sessions/{ticker}_sessions.json"
    
    if not os.path.exists(parquet_path):
        print("Error: Missing 1m data.")
        return

    print("Loading 1m Data...")
    df_1m = pd.read_parquet(parquet_path)
    
    # Timezone Handling
    if not isinstance(df_1m.index, pd.DatetimeIndex):
        df_1m.index = pd.to_datetime(df_1m['datetime'])
        
    try:
        df_1m.index = df_1m.index.tz_localize('UTC').tz_convert('US/Eastern')
    except TypeError:
        df_1m.index = df_1m.index.tz_convert('US/Eastern')
    
    df_1m['date'] = df_1m.index.date
    # Minute of day
    df_1m['mod'] = df_1m.index.hour * 60 + df_1m.index.minute
    
    # 2. Identify Daily Trend (Green vs Red)
    # We define "Direction" based on RTH Open to RTH Close
    # RTH = 09:30 (570) to 16:00 (960)
    
    rth_mask = (df_1m['mod'] >= 570) & (df_1m['mod'] < 960) # Up to 15:59
    
    daily_stats = df_1m[rth_mask].groupby('date').agg({
        'open': 'first',
        'close': 'last',
        'high': 'max',
        'low': 'min'
    }).rename(columns={'open':'RTH_Open', 'close':'RTH_Close', 'high':'RTH_High', 'low':'RTH_Low'})
    
    daily_stats['Color'] = np.where(daily_stats['RTH_Close'] > daily_stats['RTH_Open'], 'Green', 'Red')
    daily_stats['Body_Pct'] = abs(daily_stats['RTH_Close'] - daily_stats['RTH_Open']) / daily_stats['RTH_Open']
    
    # Filter for "Expansion" days? Let's just take all Green/Red days first.
    # User said "direction of daily expansion".
    
    # 3. Find AM Session Low/High Time (09:30 - 12:00)
    # AM Window: 570 to 720
    am_mask = (df_1m['mod'] >= 570) & (df_1m['mod'] < 720)
    am_data = df_1m[am_mask].copy()
    
    # We need the EXACT TIME of the Low (for Green days) or High (for Red days)
    # Group by date and find idxmin/idxmax
    
    # For Green Days -> We want the AM Low (The "Dip" to buy)
    am_lows = am_data.groupby('date')['low'].agg(['min', 'idxmin'])
    am_lows.columns = ['AM_Low_Price', 'AM_Low_Time']
    
    # For Red Days -> We want the AM High (The "Rip" to sell)
    am_highs = am_data.groupby('date')['high'].agg(['max', 'idxmax'])
    am_highs.columns = ['AM_High_Price', 'AM_High_Time']
    
    # Merge back to Daily
    df = daily_stats.join(am_lows).join(am_highs)
    
    # 4. Load Magnets (Midnight, 07:30, Asia Mid)
    # Extract Midnight Open from 1m
    midnight_mask = (df_1m.index.hour == 0) & (df_1m.index.minute == 0)
    midnight_opens = df_1m[midnight_mask].groupby('date')['open'].first().rename("Midnight_Open")
    
    # Extract Session Levels
    with open(sessions_path, 'r') as f:
        sess_data = json.load(f)
    df_sess = pd.DataFrame(sess_data)
    relevant = ['Asia', 'London', 'Open730']
    df_sess_filt = df_sess[df_sess['session'].isin(relevant)]
    pivoted = df_sess_filt.pivot_table(index='date', columns='session', values=['price', 'mid'], aggfunc='first')
    # Flatten: price_Open730, mid_Asia
    pivoted.columns = [f"{c[0]}_{c[1]}" for c in pivoted.columns]
    pivoted.index = pd.to_datetime(pivoted.index).date
    
    df = df.join(midnight_opens).join(pivoted)
    
    # 5. Analysis: Timing Distribution & Magnet Confluence
    
    reversal_events = []
    
    # Iterate through days
    for date, row in df.iterrows():
        if pd.isna(row['Color']): continue
        
        event_time = None
        event_price = None
        reversal_type = None
        
        if row['Color'] == 'Green':
            # Look at AM Low
            event_time = row['AM_Low_Time']
            event_price = row['AM_Low_Price']
            reversal_type = "Buy Dip (Green Day)"
        else:
            # Look at AM High
            event_time = row['AM_High_Time']
            event_price = row['AM_High_Price']
            reversal_type = "Sell Rip (Red Day)"
            
        if pd.isna(event_time): continue
        
        # Check Time (US/Eastern)
        # event_time is a Timestamp
        
        # Round to nearest 15 mins for binning
        minute = event_time.minute
        hour = event_time.hour
        
        # Simple Binning
        time_str = f"{hour:02d}:{minute:02d}"
        
        # Check Confluence (Did it touch a magnet?)
        # Magnets: Midnight_Open, price_Open730, mid_Asia
        magnets = {
            'Midnight Open': row['Midnight_Open'],
            '07:30 Open': row.get('price_Open730', np.nan),
            'Asia Mid': row.get('mid_Asia', np.nan)
        }
        
        closest_magnet = None
        min_dist_pct = 999
        
        for m_name, m_val in magnets.items():
            if pd.isna(m_val): continue
            dist_pct = abs(event_price - m_val) / m_val * 100
            if dist_pct < min_dist_pct:
                min_dist_pct = dist_pct
                closest_magnet = m_name
                
        # Define "Touch" as within 0.1%? or 0.05%?
        is_magnet_touch = (min_dist_pct <= 0.10)
        
        reversal_events.append({
            'Date': date,
            'Type': reversal_type,
            'Time': event_time,
            'Hour': hour,
            'Minute': minute,
            'Price': event_price,
            'Magnet': closest_magnet if is_magnet_touch else "None",
            'Dist_Pct': min_dist_pct
        })
        
    res_df = pd.DataFrame(reversal_events)
    
    # 6. Aggregate Results
    print("\n## Part 10: Reversal Timing Analysis")
    print(f"Total Days Analyzed: {len(res_df)}")
    
    # A. Timing Histogram (15 min bins)
    # Create bins: 09:30, 09:45, 10:00, 10:15...
    # We map minutes 0-14 -> :00, 15-29 -> :15, etc.
    res_df['Time_Bin'] = res_df['Time'].apply(lambda t: f"{t.hour:02d}:{(t.minute // 15 * 15):02d}")
    
    timing_dist = res_df['Time_Bin'].value_counts(normalize=True).sort_index() * 100
    print("\n### When is the High/Low made? (Probability)")
    print(timing_dist.head(10).to_string())
    
    # B. Magnet Confluence
    magnet_hits = res_df[res_df['Magnet'] != "None"]
    magnet_prob = len(magnet_hits) / len(res_df) * 100
    
    print(f"\n### Magnet Confluence (Bounce at Level)")
    print(f"Probability AM Extreme occurs at a Magnet (+/- 0.1%): {magnet_prob:.1f}%")
    
    print("\nTop Magnets for Reversals:")
    print(magnet_hits['Magnet'].value_counts(normalize=True) * 100)
    
    # C. Combined "Golden Setup" (09:45-10:15 + Magnet)
    # Time Bins 09:45, 10:00
    golden_window = ['09:45', '10:00']
    in_window = res_df[res_df['Time_Bin'].isin(golden_window)]
    
    print(f"\n### The '09:45 Reversal' Setup")
    print(f"Probability of Low/High occurring 09:45-10:15: {(len(in_window)/len(res_df)*100):.1f}%")
    
    magnet_in_window = in_window[in_window['Magnet'] != "None"]
    print(f"Probability of Magnet Touch GIVEN it's in the window: {(len(magnet_in_window)/len(in_window)*100):.1f}%")

if __name__ == "__main__":
    analyze_reversal_timing("NQ1")
