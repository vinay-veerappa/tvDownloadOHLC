import json
import os
import pandas as pd
from datetime import datetime, timezone
from schwab.auth import easy_client
from schwab.client import Client
from pathlib import Path

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

def main():
    client = get_client()
    if not client:
        print("Could not init client")
        return

    # Check if Schwab API allows fetching futures history
    print("\n--- Testing /NQ ---")
    resp = client.get_price_history("/NQ", 
                                    period_type=Client.PriceHistory.PeriodType.YEAR,
                                    period=Client.PriceHistory.Period.ONE_YEAR,
                                    frequency_type=Client.PriceHistory.FrequencyType.DAILY,
                                    frequency=Client.PriceHistory.Frequency.DAILY)
    
    if resp.status_code == 200:
        data = resp.json()
        candles = data.get('candles', [])
        print(f"Success! /NQ returned {len(candles)} candles.")
        if len(candles) > 0:
            print("First:", datetime.fromtimestamp(candles[0]['datetime']/1000, tz=timezone.utc))
            print("Last:", datetime.fromtimestamp(candles[-1]['datetime']/1000, tz=timezone.utc))
    else:
        print(f"Failed /NQ: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    main()
