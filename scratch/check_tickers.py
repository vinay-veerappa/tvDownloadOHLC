import pandas as pd
df = pd.read_parquet('data/derived/macro_records.parquet')
print("Tickers in macro_records.parquet:")
print(df['instrument'].value_counts())
