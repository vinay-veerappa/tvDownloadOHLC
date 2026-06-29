import pandas as pd
import numpy as np
import pytz
import os
import shutil

csv_path = r'C:\Users\vinay\tvDownloadOHLC\data\NinjaTrader\MNQ Monday 1029.csv'
live_path = r'C:\Users\vinay\tvDownloadOHLC\data\live\live_storage_-NQ.parquet'
backup_path = live_path + '.bak'

# 1. Create a backup of live storage
if os.path.exists(live_path):
    print(f"Creating backup of {live_path}...")
    shutil.copyfile(live_path, backup_path)
else:
    print(f"Error: {live_path} does not exist!")
    exit(1)

# 2. Read NinjaTrader CSV robustly
print("Reading NinjaTrader CSV...")
col_names = ['date_str', 'time_str', 'open', 'high', 'low', 'close', 'volume']
df_csv = pd.read_csv(csv_path, sep=',', usecols=range(7), names=col_names, skiprows=1, index_col=False)
print(f"Loaded {len(df_csv)} rows from NinjaTrader CSV.")

# 3. Parse DateTime and Shift back 1 minute (End of Bar -> Start of Bar)
print("Parsing Datetime...")
df_csv['datetime'] = pd.to_datetime(df_csv['date_str'] + ' ' + df_csv['time_str'])
df_csv = df_csv.dropna(subset=['datetime'])

print("Shifting timestamps back by 1 minute...")
df_csv['datetime'] = df_csv['datetime'] - pd.Timedelta(minutes=1)

# 4. Convert timezone: America/New_York (Naive) -> UTC (Naive)
# Note: The CSV is exported in EST/EDT (America/New_York)
print("Converting timezone to UTC...")
et = pytz.timezone('America/New_York')
df_csv['datetime_tz'] = df_csv['datetime'].dt.tz_localize(et, ambiguous='infer', nonexistent='shift_forward')
df_csv['utc_datetime'] = df_csv['datetime_tz'].dt.tz_convert('UTC').dt.tz_localize(None)

# 5. Format to match live storage schema
df_live_format = pd.DataFrame()
df_live_format['timestamp'] = df_csv['utc_datetime']
# Convert to milliseconds epoch
df_live_format['time'] = df_live_format['timestamp'].astype(np.int64) // 10**6  # epoch ms
df_live_format['open'] = df_csv['open'].astype(float)
df_live_format['high'] = df_csv['high'].astype(float)
df_live_format['low'] = df_csv['low'].astype(float)
df_live_format['close'] = df_csv['close'].astype(float)
df_live_format['volume'] = df_csv['volume'].astype(int)

# 6. Read existing live storage
df_live = pd.read_parquet(live_path)
print(f"Original Live Storage rows: {len(df_live)}")

# 7. Merge and deduplicate
# We want NinjaTrader data to fill gaps. If there are duplicates, we keep the existing live storage values (from Schwab)
combined = pd.concat([df_live, df_live_format], ignore_index=True)
combined = combined.drop_duplicates(subset=['time'], keep='first')
combined = combined.sort_values('time')

# Save merged file
combined.to_parquet(live_path, index=False)
print(f"Merged successfully. New Live Storage rows: {len(combined)} (Added {len(combined) - len(df_live)} rows).")

# 8. Verify Sunday evening data presence in the merged file
combined['datetime_utc'] = pd.to_datetime(combined['timestamp'], utc=True)
combined_et = combined.set_index('datetime_utc')
combined_et['et_time'] = combined_et.index.tz_convert(et)
combined_et['et_hhmm'] = combined_et['et_time'].dt.hour * 100 + combined_et['et_time'].dt.minute
combined_et['date'] = combined_et['et_time'].dt.date
combined_et['dow'] = combined_et['et_time'].dt.dayofweek + 2
combined_et.loc[combined_et['dow'] == 8, 'dow'] = 1

sundays = combined_et[(combined_et['dow'] == 1) & (combined_et['et_hhmm'] == 1800)]['date'].unique()
print(f"Sundays with 18:00 data in merged file: {len(sundays)}")
print(sorted(list(sundays)))
