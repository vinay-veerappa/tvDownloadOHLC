
import schwab
import json
import os
import pprint
from datetime import datetime, timedelta

def check_schwab_history():
    print("=== Checking Schwab Price History Depth ===")
    
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Error: secrets.json or token.json missing (run form root).")
        return

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    try:
        client = schwab.auth.client_from_token_file(
            token_path="token.json",
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            enforce_enums=False
        )
    except Exception as e:
        print(f"Auth Error: {e}")
        return

    # Helper to print available methods if uncertain
    # print(dir(client))

    # Test Ticker
    symbol = "SPY"
    
    # Try to fetch 6 months of 15m data
    # Schwab PriceHistory API often uses:
    # periodType, period, frequencyType, frequency
    # periodType: day, month, year, ytd
    # frequencyType: minute, daily, weekly, monthly
    
    print(f"Fetching 15m data for {symbol} (Target: 6 months)...")
    
    try:
        # Docs reference:
        # client.get_price_history(
        #   symbol,
        #   periodType=schwab.client.Client.PriceHistory.PeriodType.MONTH,
        #   period=6,
        #   frequencyType=schwab.client.Client.PriceHistory.FrequencyType.MINUTE,
        #   frequency=15
        # )
        # Since enforce_enums=False, we might use strings or just try raw
        
        # NOTE: PeriodType 'month' max is usually 6 for minute data?
        # Let's try raw values first or check response
        
        # Using string constants if library accepts them (enforce_enums=False)
        # periodType: 'month'
        # frequencyType: 'minute'
        
        # Note: Schwab API often works with timestamps too for custom ranges
        # But let's try the standard 'period' param style first.
        
        # Attempt 1: 10 Days
        print("Fetching 15m data for SPY (Target: 10 days)...")
        resp = client.get_price_history(
            symbol,
            period_type='day',
            period=10, 
            frequency_type='minute',
            frequency=15,
            need_extended_hours_data=True
        ).json()
        
        if 'candles' in resp:
            candles = resp['candles']
            print(f"Success! Fetched {len(candles)} candles.")
            if candles:
                print(f"Start: {datetime.fromtimestamp(candles[0]['datetime']/1000)}")
                print(f"End:   {datetime.fromtimestamp(candles[-1]['datetime']/1000)}")
        else:
            print("10 Day Fetch Failed:", resp)

        # Attempt 2: Max Days? Try 1 Year via Epoch?
        # Schwab 'period' max for 'day' might be limited.
        # Let's try explicit dates (start/end)
        
        print("\nAttempting 6 months via Timestamps...")
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=180) # 6 months
        
        # Convert to milliseconds
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        
        # When using start/end, periodType/period are usually ignored or implicitly custom?
        # Library doc says: 
        # "If start_datetime and end_datetime are provided, period and period_type are ignored."
        
        resp_deep = client.get_price_history(
            symbol,
            period_type='day', # Still required?
            frequency_type='minute',
            frequency=15,
            start_datetime=start_dt, # Library might handle datetime obj
            end_datetime=end_dt,
            need_extended_hours_data=True
        ).json()
        
        if 'candles' in resp_deep:
             print(f"Timestamp Fetch: {len(resp_deep['candles'])} candles.")
             if resp_deep['candles']:
                 print(f"Start: {datetime.fromtimestamp(resp_deep['candles'][0]['datetime']/1000)}")
                 print(f"End:   {datetime.fromtimestamp(resp_deep['candles'][-1]['datetime']/1000)}")
        else:
            print("Timestamp Fetch Failed:", resp_deep)

    except Exception as e:
        print(f"History Fetch Error: {e}")
        # import traceback
        # traceback.print_exc()

if __name__ == "__main__":
    check_schwab_history()
