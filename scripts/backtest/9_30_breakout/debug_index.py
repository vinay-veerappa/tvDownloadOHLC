
import pandas as pd
import os

def check_index_debug():
    path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    df = pd.read_parquet(path)
    print("Raw head:")
    print(df.head(5))
    
    # Simulating the backtest logic
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df = df.tz_convert('US/Eastern')
    
    print("\nLocalized head:")
    print(df.head(5))
    
    print("\nLocalized tail:")
    print(df.tail(5))

if __name__ == "__main__":
    check_index_debug()
