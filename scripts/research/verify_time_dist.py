
import pandas as pd
import json
from pathlib import Path
from datetime import time

DATA_DIR = Path("data")

print("Validating NQ1 Time Distribution...")
df = pd.read_parquet(DATA_DIR / "NQ1_1m.parquet")
df['time'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert("America/New_York")
df['date'] = df['time'].dt.date
df['time_only'] = df['time'].dt.time

daily_peaks = []
for date_obj, day_df in df.groupby('date'):
    or_row = day_df[day_df['time_only'] == time(9, 30)]
    if or_row.empty: continue
    row_ref = or_row.iloc[0]
    
    window = day_df[(day_df['time_only'] >= time(9, 30)) & (day_df['time_only'] <= time(12, 0))]
    if window.empty: continue
    
    max_h = window['high'].max()
    min_l = window['low'].min()
    
    peak_h_time = window[window['high'] == max_h]['time'].iloc[0]
    peak_l_time = window[window['low'] == min_l]['time'].iloc[0]
    
    # Minutes since 09:30
    h_idx = (peak_h_time.hour * 60 + peak_h_time.minute) - (9 * 60 + 30)
    l_idx = (peak_l_time.hour * 60 + peak_l_time.minute) - (9 * 60 + 30)
    
    daily_peaks.append({'h_min': h_idx, 'l_min': l_idx})

peaks_df = pd.DataFrame(daily_peaks)

print("\n--- Bullish Peak Time (Minutes since 09:30) ---")
print(f"Mean: {peaks_df['h_min'].mean():.2f}")
print(f"Median: {peaks_df['h_min'].median():.2f}")

print("\n--- Bearish Peak Time (Minutes since 09:30) ---")
print(f"Mean: {peaks_df['l_min'].mean():.2f}")
print(f"Median: {peaks_df['l_min'].median():.2f}")

# Group into 5m bins
peaks_df['h_bin'] = (peaks_df['h_min'] // 5) * 5
h_dist = peaks_df['h_bin'].value_counts().sort_index()
print("\n--- 5m Bins Distribution (Top 10) ---")
print(h_dist.head(10))
