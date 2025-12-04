import pandas as pd
import time
from tvDatafeed import TvDatafeed, Interval

def download_ohlc_data(symbol, exchange, interval, total_bars):
    tv = TvDatafeed()
    
    all_data = pd.DataFrame()
    bars_per_request = 5000 # Max usually allowed per request
    
    # We can't easily loop by date with this library as it takes n_bars.
    # So we will just request n_bars in a loop if the library supports offset, 
    # BUT standard tvDatafeed usually just gets the *latest* n_bars.
    # 
    # However, some forks support 'end_date' or similar, OR we might have to rely on 
    # the fact that we can't easily paginate backwards without a specific feature.
    #
    # Let's check if the installed library supports fetching historical data with an offset or date.
    # If not, we might only be able to get the most recent X bars.
    #
    # Actually, standard tvDatafeed `get_hist` usually fetches the *latest* data.
    # To get older data, we might need to use a different method or this library might be limited.
    #
    # Let's try to fetch a large number first. If `n_bars` can be large (e.g. 10000), 
    # the library might handle pagination internally or we might hit a limit.
    #
    # Wait, if we want to "loop through time", we usually need an `end_date` parameter.
    # Let's assume for now we can just request a large number of bars. 
    # If we need to implement manual pagination, we'd need to see if `get_hist` accepts a starting point.
    #
    # Looking at common usage: tv.get_hist(symbol, exchange, interval, n_bars)
    # Some forks add `fut_contract` or `extended_session`.
    #
    # Let's try to download a set amount for now.
    
    print(f"Downloading {total_bars} bars for {symbol}:{exchange}...")
    
    # Fetch data
    # Note: The library might not support fetching arbitrary history deep in the past 
    # without a specific 'to_date' parameter which isn't standard in the base version.
    # We will try to fetch the requested amount.
    
    try:
        df = tv.get_hist(symbol=symbol, exchange=exchange, interval=interval, n_bars=total_bars)
        if df is None or df.empty:
            print("No data returned.")
            return None
        
        print(f"Downloaded {len(df)} rows.")
        return df
        
    except Exception as e:
        print(f"Error downloading data: {e}")
        return None

if __name__ == "__main__":
    # Example: Download 1 minute data for NIFTY
    symbol = 'NIFTY'
    exchange = 'NSE'
    interval = Interval.in_1_minute
    total_bars = 10000 # Try a larger number to see if it works
    
    df = download_ohlc_data(symbol, exchange, interval, total_bars)
    
    if df is not None:
        filename = "data_lib.csv"
        df.to_csv(filename)
        print(f"Saved to {filename}")
        print(df.head())
        print(df.tail())
