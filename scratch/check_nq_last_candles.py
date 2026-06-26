import pandas as pd
import datetime

parquet_path = "data/live/live_storage_-NQ.parquet"
df = pd.read_parquet(parquet_path)
print("Columns:", df.columns)
print("Total rows:", len(df))

# Convert time to UTC datetime
df['utc_time'] = pd.to_datetime(df['time'], unit='ms', utc=True)
df_filtered = df[df['utc_time'] >= '2026-06-23 21:50:00+00:00']

print("\nLast candles since 21:50 UTC:")
for idx, row in df_filtered.iterrows():
    print(f"Time: {row['utc_time']} | MS: {row['time']} | O: {row['open']} | H: {row['high']} | L: {row['low']} | C: {row['close']} | V: {row['volume']}")
