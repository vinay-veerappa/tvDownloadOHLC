"""Compare OHLC values between daily CSV and 1m parquet to check timestamp offset"""
import pandas as pd

# Load data
es_1m = pd.read_parquet("data/ES1_1m.parquet")
daily_csv = pd.read_csv("data/TV_OHLC/CME_MINI_ES1!, 1D_33a40.csv")

print("=== Daily CSV last 3 rows ===")
for i in range(-3, 0):
    row = daily_csv.iloc[i]
    ts = pd.to_datetime(row["time"], unit="s")
    print(f"{ts.date()}: O={row['open']}, H={row['high']}, L={row['low']}, C={row['close']}")

print()

# Check Dec 5th from 1m
dec5_data = es_1m[es_1m.index.date == pd.Timestamp("2025-12-05").date()]
if len(dec5_data) > 0:
    print("=== Dec 5th from 1m data (aggregated) ===")
    print(f"O={dec5_data['open'].iloc[0]}, H={dec5_data['high'].max()}, L={dec5_data['low'].min()}, C={dec5_data['close'].iloc[-1]}")
    print(f"Bars: {len(dec5_data)}")

print()

# Check Dec 4th from 1m
dec4_data = es_1m[es_1m.index.date == pd.Timestamp("2025-12-04").date()]
if len(dec4_data) > 0:
    print("=== Dec 4th from 1m data (aggregated) ===")
    print(f"O={dec4_data['open'].iloc[0]}, H={dec4_data['high'].max()}, L={dec4_data['low'].min()}, C={dec4_data['close'].iloc[-1]}")
    print(f"Bars: {len(dec4_data)}")

print()

# Check first few rows of 1m
print("=== 1m parquet first 5 rows ===")
print(es_1m.head())

print()

# Check last few rows of 1m
print("=== 1m parquet last 5 rows ===")
print(es_1m.tail())
