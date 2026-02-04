import pandas as pd
import glob

def inspect_parquet():
    file_path = "data/derived/NQ1_daily_classification.parquet"
    try:
        df = pd.read_parquet(file_path)
        print(f"Columns in {file_path}:")
        for col in df.columns:
            print(f" - {col}")
        
        print("\nSample Data (first 5 rows):")
        print(df.head())
        
        print(f"\nDate Range: {df.index.min()} to {df.index.max()}")
        
    except Exception as e:
        print(f"Error reading parquet: {e}")

if __name__ == "__main__":
    inspect_parquet()
