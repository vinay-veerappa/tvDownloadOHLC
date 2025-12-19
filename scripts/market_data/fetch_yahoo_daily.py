
import yfinance as yf
import pandas as pd
import os

DATA_DIR = "C:/Users/vinay/tvDownloadOHLC/data"
TICKERS = ["DIA"]

def fetch_daily():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    for ticker in TICKERS:
        print(f"Fetching Daily for {ticker}...")
        try:
            # Fetch 5y history
            df = yf.download(ticker, period="5y", interval="1d", progress=False)
            
            if df.empty:
                print(f"No data for {ticker}")
                continue
                
            # Normalize Schema
            # YF often returns MultiIndex columns (Price, Ticker) -> Flatten or drop ticker level
            if isinstance(df.columns, pd.MultiIndex):
                # If checking just one ticker, we can drop the ticker level
                df.columns = df.columns.get_level_values(0)
            
            df.reset_index(inplace=True)
            df.columns = [c.lower() for c in df.columns] # Date, Open, High, Low, Close, Adj Close, Volume
            
            # Ensure 'close' is used (Yahoo gives Adj Close too, usually 'Close' is settlement)
            # Rename 'Date' -> 'time'? Or keep 'date'?
            # Parquet schema usually expects 'time' as int or datetime
            if 'date' in df.columns:
                df.rename(columns={'date': 'time'}, inplace=True)
            
            # Save
            path = os.path.join(DATA_DIR, f"{ticker}_1d.parquet")
            df.to_parquet(path)
            print(f"Saved {path} ({len(df)} rows)")
            
            # Audit Nov 5 2025
            try:
                # Convert 'time' to datetime if needed for lookup
                chk = pd.to_datetime(df['time'])
                mask = (chk == "2025-11-05")
                row = df.loc[mask]
                if not row.empty:
                    print(f"  Nov 5 Close: {row['close'].values[0]}")
            except Exception as e:
                print(f"  Audit failed: {e}")
                
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

if __name__ == "__main__":
    fetch_daily()
