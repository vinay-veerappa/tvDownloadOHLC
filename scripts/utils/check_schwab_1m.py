import json
import os
from datetime import datetime, timedelta, timezone
from schwabdev import Client

def check_history():
    secrets_path = "secrets.json"
    if not os.path.exists(secrets_path):
        print("secrets.json not found")
        return

    with open(secrets_path, 'r') as f:
        secrets = json.load(f)

    try:
        # Initialize client using tokens.db
        client = Client(
            secrets["app_key"], 
            secrets["app_secret"], 
            secrets["callback_url"],
            tokens_db="tokens.db"
        )
        
        # Test symbols
        # VIX is $VIX on Schwab
        # VVIX is $VVIX on Schwab
        symbols = ["$VIX", "$VVIX"]
        
        # Target start: Jan 20, 2026 (slightly before the gap)
        target_start = datetime(2026, 1, 20, tzinfo=timezone.utc)
        start_ms = int(target_start.timestamp() * 1000)
        
        for sym in symbols:
            print(f"\n🔍 Checking 1m history for {sym}...")
            # frequencyType: minute, frequency: 1
            # periodType: day (for minute data we use day period or start/end)
            resp = client.price_history(
                sym, 
                periodType="day", 
                period=10, # Start with a small window to see if it works
                frequencyType="minute", 
                frequency=1
            )
            
            if resp.status_code == 200:
                data = resp.json()
                candles = data.get("candles", [])
                if candles:
                    first_candle = datetime.fromtimestamp(candles[0]['datetime'] / 1000, tz=timezone.utc)
                    last_candle = datetime.fromtimestamp(candles[-1]['datetime'] / 1000, tz=timezone.utc)
                    print(f"  ✅ Data found! Count: {len(candles)}")
                    print(f"  Range: {first_candle} to {last_candle}")
                else:
                    print("  ❌ No candles returned for small period (10 days).")
            else:
                print(f"  ❌ Error {resp.status_code}: {resp.text}")

            # Now try a specific start date from Jan 20
            print(f"  Checking specific range starting {target_start.date()}...")
            resp_long = client.price_history(
                sym,
                startDate=start_ms,
                frequencyType="minute",
                frequency=1
            )
            
            if resp_long.status_code == 200:
                data_long = resp_long.json()
                candles_long = data_long.get("candles", [])
                if candles_long:
                    first_long = datetime.fromtimestamp(candles_long[0]['datetime'] / 1000, tz=timezone.utc)
                    last_long = datetime.fromtimestamp(candles_long[-1]['datetime'] / 1000, tz=timezone.utc)
                    print(f"  ✅ History found from {first_long} to {last_long} ({len(candles_long)} bars)")
                else:
                    print(f"  ❌ No candles returned starting from {target_start.date()}. Schwab likely does not have 1m data this far back.")
            else:
                print(f"  ❌ Error {resp_long.status_code}: {resp_long.text}")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    check_history()
