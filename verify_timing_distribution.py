import pandas as pd
import numpy as np
from pathlib import Path

# Check if the parquet file exists
parquet_file = Path('data') / 'derived' / 'macro_records.parquet'
if not parquet_file.exists():
    print(f'File not found: {parquet_file}')
    print('Available files in processed/:')
    import os
    for f in sorted(os.listdir('processed'))[:30]:
        print(f'  {f}')
else:
    df = pd.read_parquet(parquet_file)
    
    # Check the timing columns
    print('=== JUDAS INFLECTION TIMING DISTRIBUTION ===')
    print(f'Total rows: {len(df)}')
    print(f'Non-null judas_inflection_m: {df["judas_inflection_m"].notna().sum()}')
    print(f'Null judas_inflection_m: {df["judas_inflection_m"].isna().sum()}')
    
    # Show distribution
    print('\nValue counts for judas_inflection_m (top 25):')
    print(df['judas_inflection_m'].value_counts().head(25))
    
    print('\n=== MODE ANALYSIS ===')
    timing_nonull = df[df['judas_inflection_m'].notna()]['judas_inflection_m']
    if len(timing_nonull) > 0:
        mode_val = timing_nonull.mode()
        print(f'Mode: {mode_val.values[0] if len(mode_val) > 0 else "None"}')
        print(f'Count at mode: {(timing_nonull == mode_val.values[0]).sum() if len(mode_val) > 0 else 0}')
    
    print('\n=== ZERO-MINUTE ANALYSIS ===')
    zero_count = (df['judas_inflection_m'] == 0).sum()
    print(f'Count at 0m: {zero_count}')
    print(f'Percentage of all rows: {zero_count / len(df) * 100:.2f}%')
    
    judas_only = df[df['judas_classification'].isin(['bullish_judas', 'bearish_judas'])]
    zero_judas = (judas_only['judas_inflection_m'] == 0).sum()
    print(f'Count at 0m (Judas only): {zero_judas}')
    print(f'Percentage of Judas rows: {zero_judas / len(judas_only) * 100:.2f}%')
    
    # Check for null timestamps in raw data
    print('\n=== TIMESTAMP NULLABILITY ===')
    print(f'Null high_time_last: {df["high_time_last"].isna().sum()}')
    print(f'Null low_time_last: {df["low_time_last"].isna().sum()}')
    print(f'Null macro_start: {df["macro_start"].isna().sum()}')
    
    # Check high_offset_m and low_offset_m nullability  
    print(f'Null high_offset_m: {df["high_offset_m"].isna().sum()}')
    print(f'Null low_offset_m: {df["low_offset_m"].isna().sum()}')
    
    # Sample some zero-minute records
    print('\n=== SAMPLE ZERO-MINUTE JUDAS RECORDS ===')
    zero_recs = df[(df['judas_inflection_m'] == 0) & 
                   (df['judas_classification'].isin(['bullish_judas', 'bearish_judas']))].head(5)
    for idx, row in zero_recs.iterrows():
        print(f'Date: {row["trading_date"]}, Macro: {row["macro_name_raw"]}')
        print(f'  Classification: {row["judas_classification"]}')
        print(f'  Macro Start: {row["macro_start"]}')
        print(f'  High Time (last): {row["high_time_last"]}')
        print(f'  Low Time (last): {row["low_time_last"]}')
        print(f'  High Offset: {row["high_offset_m"]}, Low Offset: {row["low_offset_m"]}')
        print(f'  Judas Inflection: {row["judas_inflection_m"]}')
        print()
