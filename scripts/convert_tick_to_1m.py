import pandas as pd
import os
import time

def convert_tick_to_1m_csv():
    input_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP500_tickData\SP.csv"
    output_file = r"C:\Users\vinay\tvDownloadOHLC\data\SP_1m_verification.csv"
    
    print(f"Reading {input_file}...")
    start_t = time.time()
    
    # Read CSV
    # Columns: date,time,price,volume
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} rows in {time.time() - start_t:.2f}s")
    
    # Parse DateTime
    print("Parsing timestamps...")
    # Vectorized string combination + to_datetime is usually fastest for this scale
    # Format: 01/03/2000 08:30:34.000
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%m/%d/%Y %H:%M:%S.%f')
    
    # Set Index
    df.set_index('datetime', inplace=True)
    
    # Resample to 1 Minute
    print("Resampling to 1min OHLCV...")
    ohlc = df['price'].resample('1min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })
    
    vol = df['volume'].resample('1min').sum()
    
    result = pd.concat([ohlc, vol], axis=1)
    
    # Drop NaNs (empty minutes) or Keep?
    # Usually for OHLC files used in backtesting/charting, we might want to drop empty rows
    # or forward fill close, etc.
    # For now, we dropna to only produce bars where ticks existed.
    result.dropna(inplace=True)
    
    # Reset index to make datetime a column
    result.reset_index(inplace=True)
    
    # Rename columns to standard lowercase
    result.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
    
    # Save to CSV
    print(f"Saving to {output_file}...")
    result.to_csv(output_file, index=False)
    print("Done!")
    
    # Preview
    print("\nFirst 5 rows:")
    print(result.head())

if __name__ == "__main__":
    convert_tick_to_1m_csv()
