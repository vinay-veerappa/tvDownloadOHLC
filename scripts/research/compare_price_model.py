
import asyncio
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from api.services.profiler_service import ProfilerService
from datetime import timedelta
import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.getcwd())


import asyncio
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from api.services.profiler_service import ProfilerService
from datetime import timedelta
import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

async def run_comparison():
    ticker = "NQ1" 
    
    # --- CONFIG ---
    BUCKET_MIN = 5
    LONDON_START_T = "03:00" # EST
    LONDON_END_T = "08:00" # EST (London Close is later, but measuring range usually stops at US open?)
    # Users def: "The london O/U is the mid of the London range."
    # London session 03:00 - 11:30? Usually London range is taken 03:00-08:00 (Pre-US).
    
    # Time shifts (Minutes from 18:00 prev day)
    # 18:00 = 0
    # 03:00 = 9 * 60 = 540
    # 08:00 = 14 * 60 = 840
    # 09:30 = 15.5 * 60 = 930
    
    M_1800 = 0
    M_0300 = 540
    M_0800 = 840
    M_0930 = 930
    M_1600 = 1320 # End of Full Session (approx)

    print(f"Comparison: Ticker={ticker}, Bucket={BUCKET_MIN}m")

    # 1. Load Reference Data
    ref_path = r"docs/reference_data/ReferenceMedian.json"
    if not os.path.exists(ref_path):
        print(f"Ref file missing: {ref_path}")
        return

    with open(ref_path, 'r') as f:
        ref_json = json.load(f)
    
    ref_rows = []
    for item in ref_json.get('medians', []):
        t_str = item['time']
        h, m, s = map(int, t_str.split(':'))
        total_m = h * 60 + m
        if total_m < 1080: total_m += 1440
        time_idx = total_m - 1080
        
        ref_rows.append({
            'time_idx': time_idx,
            'ref_high': item['med_high_pct'],
            'ref_low': item['med_low_pct']
        })
    df_ref = pd.DataFrame(ref_rows).sort_values('time_idx')
    

    # 2. Fetch History
    # Increase to 10000 to capture full history (2008+)
    stats_result = ProfilerService.analyze_profiler_stats(ticker, days=10000)
    all_sessions = stats_result.get("sessions", [])
    from api.services.data_loader import DATA_DIR
    file_path = DATA_DIR / f"{ticker}_1m.parquet"
    df = pd.read_parquet(file_path).sort_index()

    # 2. Timezone Conversion (UTC -> US/Eastern)
    # The 'time' column is Unix timestamp (UTC).
    df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
    df.dropna(subset=['datetime'], inplace=True)
    
    # 3. Filter for Session Start (18:00 EST)
    sess_start_mask = (df['datetime'].dt.hour == 18) & (df['datetime'].dt.minute == 0)
    
    # We need INTEGER INDICES for numpy slicing
    sess_start_indices = np.where(sess_start_mask)[0]
    
    print(f"Found {len(sess_start_indices)} sessions starting at 18:00 EST.")

    # Convert columns to numpy for speed
    np_open   = df['open'].to_numpy()
    np_high   = df['high'].to_numpy()
    np_low    = df['low'].to_numpy()
    np_close  = df['close'].to_numpy()
    # Ensure this is timezone-aware numpy array of datetimes
    np_dt     = df['datetime'].to_numpy() 

    # V19: Track Previous Asia Mid (18:00-19:30) to use as Anchor
    prev_asia_mid_price = None

    paths_ny_anchored = []
    
    for start_idx in sess_start_indices:
        # End index (approx 23H = 1380m)
        end_idx = start_idx + 1440 
        if end_idx >= len(df): continue
        
        # --- Logic V19: Anchor = Previous Asia Mid (if available) ---
        # Fallback to Prior Close (V14) if no previous Asia Mid
        
        anchor_type = "PriorClose"
        if prev_asia_mid_price is not None:
             sess_anchor = prev_asia_mid_price
             anchor_type = "PrevAsiaMid"
        elif start_idx > 0:
            sess_anchor = np_close[start_idx - 1]
        else:
            sess_anchor = np_open[start_idx]

        # Normalization
        # V17 High refers to the path anchored to PrevNY2Mid
        chunk_high_v17 = (np_high[start_idx:end_idx] - sess_anchor) / sess_anchor * 100.0
        chunk_low_v17  = (np_low[start_idx:end_idx]  - sess_anchor) / sess_anchor * 100.0
        
        # Use EST datetimes for TimeDelta
        chunk_dt = np_dt[start_idx:end_idx] 
        base_dt  = chunk_dt[0]
        
        # Calculate minutes
        ts_series = pd.Series(chunk_dt)
        time_deltas = (ts_series - base_dt).dt.total_seconds().div(60).fillna(0).astype(int).to_numpy()

        # V24 Logic: Chained Session O/U Anchors
        # 1. Asia O/U (18:00-19:30) -> Mins 0-90. Anchors London (540+)
        # 2. London O/U (02:30-03:30) -> Mins 510-570. Anchors NY AM (810+)
        # 3. NY AM O/U (08:00-09:30) -> Mins 840-930. Anchors NY PM (1080+)
        
        # Calculate Logic
        asia_ou_start, asia_ou_end   = 0, 90
        lon_ou_start,  lon_ou_end    = 510, 570
        ny_ou_start,   ny_ou_end     = 840, 930
        
        asia_ou_mid = None
        lon_ou_mid  = None
        ny_ou_mid   = None
        
        # Calc Asia O/U Mid
        mask_asia = (time_deltas >= asia_ou_start) & (time_deltas < asia_ou_end)
        if mask_asia.any():
            h, l = np_high[start_idx:end_idx][mask_asia], np_low[start_idx:end_idx][mask_asia]
            if len(h)>0: asia_ou_mid = (h.max() + l.min()) / 2.0
            
        # Calc London O/U Mid
        mask_lon = (time_deltas >= lon_ou_start) & (time_deltas < lon_ou_end)
        if mask_lon.any():
            h, l = np_high[start_idx:end_idx][mask_lon], np_low[start_idx:end_idx][mask_lon]
            if len(h)>0: lon_ou_mid = (h.max() + l.min()) / 2.0
            
        # Calc NY O/U Mid
        mask_ny = (time_deltas >= ny_ou_start) & (time_deltas < ny_ou_end)
        if mask_ny.any():
            h, l = np_high[start_idx:end_idx][mask_ny], np_low[start_idx:end_idx][mask_ny]
            if len(h)>0: ny_ou_mid = (h.max() + l.min()) / 2.0

        # Arrays for V24 Results
        chunk_high_v24 = np.zeros_like(chunk_high_v17)
        chunk_low_v24  = np.zeros_like(chunk_low_v17)
        
        # Anchors Array Initialized to Prior Close
        sess_anchor_v14 = sess_anchor 
        anchors = np.full(len(chunk_dt), sess_anchor_v14)
        
        # Apply Switches
        # 1. London (540+) -> Switch to Asia O/U Mid
        if asia_ou_mid is not None:
            mask_london = (time_deltas >= 540)
            anchors[mask_london] = asia_ou_mid
            
        # 2. NY AM (810+) -> Switch to London O/U Mid (Overwrites London anchor for NY)
        if lon_ou_mid is not None:
             mask_ny_am = (time_deltas >= 810)
             anchors[mask_ny_am] = lon_ou_mid
             
        # 3. NY PM (1080+) -> Switch to NY AM O/U Mid (Overwrites NY AM anchor for PM)
        if ny_ou_mid is not None:
            mask_ny_pm = (time_deltas >= 1080)
            anchors[mask_ny_pm] = ny_ou_mid
        
        chunk_abs_high = np_high[start_idx:end_idx]
        chunk_abs_low  = np_low[start_idx:end_idx]
        
        chunk_high_v24 = (chunk_abs_high - anchors) / anchors * 100.0
        chunk_low_v24  = (chunk_abs_low  - anchors) / anchors * 100.0
        
        new_df = pd.DataFrame({
            'time_idx': time_deltas,
            'v24_high': chunk_high_v24,
            'v24_low': chunk_low_v24
        })
        paths_ny_anchored.append(new_df)

    print(f"Aggregating {len(paths_ny_anchored)} paths (V24 - Chained Session O/U Anchors)...")
    
    if not paths_ny_anchored:
        print("No valid paths found.")
        return

    df_all = pd.concat(paths_ny_anchored)
    grouped = df_all.groupby('time_idx')
    
    # --- Logic V24: Median (Chained Anchor) ---
    agg = grouped.agg({
        'v24_high': ['median', 'mean', 'std'],
        'v24_low':  ['median', 'mean', 'std']
    })
    
    agg.columns = ['v24_high', 'v24_high_mean', 'v24_high_std', 'v24_low', 'v24_low_mean', 'v24_low_std']
    agg = agg.reset_index()

    # --- Plotting ---
    fig = make_subplots(rows=1, cols=1)  
    
    # Helper to convert mins to time string
    def m_to_str(m):
        # m=0 -> 18:00
        base = pd.Timestamp("2000-01-01 18:00:00")
        t = base + timedelta(minutes=int(m))
        return t.strftime("%H:%M")
    
    agg['time_label'] = agg['time_idx'].apply(m_to_str)
    
    ZOOM_START = 0  # 18:00
    ZOOM_END = 1080 + 240   # 16:00 Next Day
    
    mask_zoom = (agg['time_idx'] >= ZOOM_START) & (agg['time_idx'] <= ZOOM_END)
    view_data = agg[mask_zoom]
    
    if view_data.empty: return
        
    x_vals = view_data['time_label']
    
    # V24 Logic (Chained O/U Anchors)
    fig.add_trace(go.Scatter(x=x_vals, y=view_data['v24_high'], mode='lines', line=dict(color='#a855f7', width=3), name='V24 (Chained O/U Anchors)'))
    fig.add_trace(go.Scatter(x=x_vals, y=view_data['v24_low'], mode='lines', line=dict(color='#d946ef', width=3), name='V24 Low'))
    
    fig.add_hline(y=0, line_color="gray", line_width=1)
    
    # Session Lines
    # Switches: 03:00 (540), 07:30 (810), 12:00 (1080)
    for t in [540, 810, 840, 1080]: 
        t_str = m_to_str(t)
        fig.add_vline(x=t_str, line_dash="dash", line_color="gray")

    # Reference Overlay
    mask_ref = (df_ref['time_idx'] >= ZOOM_START) & (df_ref['time_idx'] <= ZOOM_END)
    ref_view = df_ref[mask_ref].copy()
    ref_view['time_label'] = ref_view['time_idx'].apply(m_to_str)
    
    fig.add_trace(go.Scatter(x=ref_view['time_label'], y=ref_view['ref_high'], line=dict(color='yellow', width=2, dash='dot'), name='Ref High'))
    fig.add_trace(go.Scatter(x=ref_view['time_label'], y=ref_view['ref_low'], line=dict(color='orange', width=2, dash='dot'), name='Ref Low'))

    fig.update_layout(
        title="Price Model V24: Chained Session O/U Anchors vs Reference",
        xaxis_title="Time (EST)",
        yaxis_title="% Change from Chained Anchors",
        template="plotly_dark",
        height=600,
        margin=dict(l=50, r=50, t=80, b=50)
    )

    out_path = "reports/price_model_comparison_v24.html"
    os.makedirs("reports", exist_ok=True)
    fig.write_html(out_path)
    print(f"Saved v24 chart to {out_path}")

    # --- 6. Numeric Comparison ---
    print("\n--- Numeric Comparison (V24 vs Ref) ---")
    
    ref_merge = df_ref[['time_idx', 'ref_high']].copy()
    exp_merge = agg[['time_idx', 'v24_high']].copy()
    
    merged = pd.merge(ref_merge, exp_merge, on='time_idx', how='inner')
    merged = merged[(merged['time_idx'] >= ZOOM_START) & (merged['time_idx'] <= ZOOM_END)]
    
    print(f"{'Time':<10} | {'Ref High':<10} | {'V24 (Chained)':<10} | {'Diff':<10}")
    print("-" * 60)
    
    key_times = [0, 540, 810, 840, 930, 1080] 
    
    for _, row in merged.iterrows():
        t_idx = int(row['time_idx'])
        if t_idx in key_times or (t_idx % 60 == 0 and t_idx > 500):
             t_str = m_to_str(t_idx)
             diff = row['v24_high'] - row['ref_high']
             print(f"{t_str:<10} | {row['ref_high']:.4f}     | {row['v24_high']:.4f}      | {diff:.4f}")

    csv_path = "reports/price_model_comparison_values_v24.csv"
    merged.to_csv(csv_path, index=False)
    print(f"\nFull CSV saved to {csv_path}")

if __name__ == "__main__":
    asyncio.run(run_comparison())
