
import pandas as pd
from pathlib import Path

CSV_PATH = Path("data/NinjaTrader/24Dec2025/ES Thursday 857.csv")

try:
    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, on_bad_lines='skip', low_memory=False)
    
    print(f"Rows: {len(df):,}")
    print("Columns:", df.columns.tolist())
    
    # Check headers matching import_ninjatrader logic
    df.columns = [c.strip().lower() for c in df.columns]
    
    if 'date' in df.columns and 'time' in df.columns:
        print("Required columns found.")
        print("Head:", df[['date', 'time']].head(3))
        print("Tail:", df[['date', 'time']].tail(3))
        
        # Test combined parsing
        combined = df['date'].astype(str) + ' ' + df['time'].astype(str)
        print("Combined sample:", combined.iloc[0])
        
    else:
        print("MISSING required columns 'Date'/'Time'")

except Exception as e:
    print(f"Error: {e}")
