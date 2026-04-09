import pandas as pd
from .config import MACRO_RECORDS_PATH

def validate_output():
    if not MACRO_RECORDS_PATH.exists():
        print(f"Error: Output file {MACRO_RECORDS_PATH} not found.")
        return
        
    df = pd.read_parquet(MACRO_RECORDS_PATH)
    
    print(f"=== Validation Summary: {MACRO_RECORDS_PATH.name} ===")
    print(f"Total Records: {len(df)}")
    
    print("\nRecords per Instrument:")
    print(df['instrument'].value_counts())
    
    print("\nRecords per Macro (Top 10):")
    print(df['macro_name'].value_counts().head(10))
    
    print("\nJudas Classification Distribution:")
    print(df['judas_classification'].value_counts())
    
    print("\nIndicator Label Distribution:")
    print(df['indicator_label'].value_counts())
    
    # Check for anomalies
    null_counts = df[['open', 'high', 'low', 'close']].isnull().sum()
    if null_counts.sum() > 0:
        print("\n!! Warning: Null values found in OHLC price data:")
        print(null_counts)
    else:
        print("\nCheck: No null OHLC values. OK.")
        
    # Check boundary consistency
    bad_boundaries = df[df['low'] > df['high']]
    if not bad_boundaries.empty:
        print(f"\n!! Warning: Found {len(bad_boundaries)} records where low > high.")
    else:
        print("Check: High/Low boundaries consistent. OK.")
        
    print("\nValidation Complete.")

if __name__ == "__main__":
    validate_output()
