"""Quick VWAP benchmark script"""
import time
import pandas as pd
import sys
sys.path.insert(0, '.')
from api.services.data_loader import load_parquet
from api.services.vwap import calculate_vwap_with_settings

df = load_parquet('ES1', '1m')
print(f'Data: {len(df):,} rows')

# Test session anchor
times = []
for _ in range(5):
    start = time.perf_counter()
    result = calculate_vwap_with_settings(df, anchor='session', bands=[1.0, 2.0])
    times.append((time.perf_counter() - start) * 1000)
print(f'VWAP (session, 2 bands): {sum(times)/len(times):.2f}ms avg (was 1491ms)')

# Test week anchor
times = []
for _ in range(5):
    start = time.perf_counter()
    result = calculate_vwap_with_settings(df, anchor='week')
    times.append((time.perf_counter() - start) * 1000)
print(f'VWAP (week): {sum(times)/len(times):.2f}ms avg (was 8096ms)')

# Verify output
vwap_vals = result.get('vwap', [])
print(f'Output has {len(vwap_vals)} values')
first_valid = next((i for i,v in enumerate(vwap_vals) if v is not None), -1)
print(f'First non-null at index: {first_valid}')
