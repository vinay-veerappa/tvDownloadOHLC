import os
import sys
import json
from datetime import datetime, timezone, timedelta
from schwabdev import Client

# Ensure secrets.json and tokens.db are accessible
secrets_path = "secrets.json"
if not os.path.exists(secrets_path):
    print("secrets.json not found.")
    sys.exit(1)

with open(secrets_path, 'r') as f:
    secrets = json.load(f)

print("Initializing schwabdev client...")
client = Client(
    secrets["app_key"], 
    secrets["app_secret"], 
    secrets["callback_url"],
    tokens_db="tokens.db",
    timeout=30
)

# Target timeframe: 1-minute bars for /NQ
now = datetime.now(timezone.utc)
start_dt = now - timedelta(minutes=30)
end_dt = now - timedelta(minutes=15)

start_ms = int(start_dt.timestamp() * 1000)
end_ms = int(end_dt.timestamp() * 1000)

print(f"Requesting NQ 1m with raw startDate={start_ms}, endDate={end_ms}")
# According to Schwab API: to use startDate/endDate, do NOT pass period/periodType.
# Let's see if this works:
resp = client.price_history(
    symbol="/NQ",
    frequencyType="minute",
    frequency=1,
    startDate=start_ms,
    endDate=end_ms,
    needExtendedHoursData=True
)

if resp.status_code == 200:
    data = resp.json()
    candles = data.get('candles', [])
    print(f"Success! Returned {len(candles)} candles.")
    if candles:
        print(f"First candle: {datetime.fromtimestamp(candles[0]['datetime']/1000, tz=timezone.utc)}")
        print(f"Last candle:  {datetime.fromtimestamp(candles[-1]['datetime']/1000, tz=timezone.utc)}")
else:
    print(f"Failed: {resp.status_code} {resp.text}")

print("\nWhat if we pass startDate and endDate as parameters but in the URL or as query params?")
# Wait, client.price_history takes them as kwargs and passes them as query parameters.
# Let's inspect the request details if possible, or try passing them as string or integers.
# Let's print out if there's any other combination.
