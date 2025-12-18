import json
import os
import pandas as pd
from datetime import datetime, timedelta
from schwab.auth import easy_client
from schwab.client import Client

def get_client():
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Missing credentials")
        return None

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    try:
        return easy_client(
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            callback_url='https://127.0.0.1:8182',
            token_path='token.json',
            enforce_enums=False)
    except Exception as e:
        print(f"Auth failed: {e}")
        return None

def test_history(symbol, period_type, period, freq_type, freq):
    client = get_client()
    if not client: return

    print(f"\n--- Testing {symbol} | {period_type.name} {period.name} | {freq_type.name} {freq.name} ---")
    
    try:
        resp = client.get_price_history(symbol, 
                                        period_type=period_type,
                                        period=period,
                                        frequency_type=freq_type,
                                        frequency=freq)
        
        if resp.status_code != 200:
            print(f"Error: {resp.status_code} - {resp.text}")
            return

        data = resp.json()
        candles = data.get('candles', [])
        
        if not candles:
            print(f"No candles returned for {symbol}")
            return

        df = pd.DataFrame(candles)
        if 'datetime' in df.columns:
            df['dt'] = pd.to_datetime(df['datetime'], unit='ms')
        
        print(f"Total Candles: {len(candles)}")
        print(f"Range: {df['dt'].min()} to {df['dt'].max()}")
        
    except Exception as e:
        print(f"Exception for {symbol}: {e}")

if __name__ == "__main__":
    # 1. Standard 10 Day Minute Test
    test_history("QQQ", 
                 Client.PriceHistory.PeriodType.DAY, 
                 Client.PriceHistory.Period.TEN_DAYS, 
                 Client.PriceHistory.FrequencyType.MINUTE, 
                 Client.PriceHistory.Frequency.EVERY_MINUTE)
    
    # 2. Daily Data Depth (Usually years)
    test_history("QQQ", 
                 Client.PriceHistory.PeriodType.YEAR, 
                 Client.PriceHistory.Period.TEN_YEARS, 
                 Client.PriceHistory.FrequencyType.DAILY, 
                 Client.PriceHistory.Frequency.DAILY)
    
    # 3. Probing for higher minute depth using raw values
    # Schwab usually has 1, 2, 3, 4, 5, 10 days for minute data.
    # Let's see if we can get 1 month of minute data.
    print("\n--- Probing Max Minute Depth (20+ Days) ---")
    
    client = get_client()
    if client:
        try:
            # We use enforce_enums=False to try arbitrary periods
            # The API usually supports specific enums, but let's test.
            resp = client.get_price_history("QQQ", 
                                            period_type=Client.PriceHistory.PeriodType.DAY,
                                            period=20, # 20 days
                                            frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                                            frequency=Client.PriceHistory.Frequency.EVERY_MINUTE)
            if resp.status_code == 200:
                candles = resp.json().get('candles', [])
                print(f"20 Days 1m: Success! Fetched {len(candles)} candles.")
            else:
                print(f"20 Days 1m: Failed ({resp.status_code}) - {resp.text}")
                
            resp = client.get_price_history("QQQ", 
                                            period_type=Client.PriceHistory.PeriodType.MONTH,
                                            period=1, # 1 Month
                                            frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                                            frequency=Client.PriceHistory.Frequency.EVERY_MINUTE)
            if resp.status_code == 200:
                candles = resp.json().get('candles', [])
                print(f"1 Month 1m: Success! Fetched {len(candles)} candles.")
            else:
                print(f"1 Month 1m: Failed ({resp.status_code}) - {resp.text}")
        except Exception as e:
            print(f"Probe Exception: {e}")
