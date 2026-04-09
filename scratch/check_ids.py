import pandas as pd
df = pd.read_parquet('data/derived/macro_records.parquet')
print("Columns in macro_records.parquet:")
print(df.columns.tolist())
print("\nUnique values in 'instrument' column:")
print(df['instrument'].unique())
if 'ticker' in df.columns:
    print("\nUnique values in 'ticker' column:")
    print(df['ticker'].unique())
