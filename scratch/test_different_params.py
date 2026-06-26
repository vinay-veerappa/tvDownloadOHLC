import os
import sys
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from schwabdev import Client

secrets_path = "secrets.json"
if not os.path.exists(secrets_path):
    print("secrets.json not found.")
    sys.exit(1)

with open(secrets_path, 'r') as f:
    secrets = json.load(f)

client = Client(
    secrets["app_key"], 
    secrets["app_secret"], 
    secrets["callback_url"],
    tokens_db="tokens.db",
    timeout=30
)

# 1. Test SPY (ETF) with datetime objects (UTC)
now = datetime.now(timezone.utc)
start_dt = now - timedelta(minutes=40)
end_dt = now - timedelta(minutes=20)

print(f"=== TEST 1: SPY (ETF) with UTC datetimes ===")
print(f"Requesting SPY: {start_dt} -> {end_dt}")
resp1 = client.price_history(
    symbol="SPY",
    frequencyType="minute",
    frequency=1,
    startDate=start_dt,
    endDate=end_dt,
    needExtendedHoursData=True
)
if resp1.status_code == 200:
    candles = resp1.json().get('candles', [])
    print(f"Returned {len(candles)} candles.")
    if candles:
        print(f"First: {datetime.fromtimestamp(candles[0]['datetime']/1000, tz=timezone.utc)}")
        print(f"Last:  {datetime.fromtimestamp(candles[-1]['datetime']/1000, tz=timezone.utc)}")
else:
    print(f"Failed: {resp1.status_code} {resp1.text}")

print(f"\n=== TEST 2: /NQ (Future) with UTC datetimes ===")
print(f"Requesting /NQ: {start_dt} -> {end_dt}")
resp2 = client.price_history(
    symbol="/NQ",
    frequencyType="minute",
    frequency=1,
    startDate=start_dt,
    endDate=end_dt,
    needExtendedHoursData=True
)
if resp2.status_code == 200:
    candles = resp2.json().get('candles', [])
    print(f"Returned {len(candles)} candles.")
    if candles:
        print(f"First: {datetime.fromtimestamp(candles[0]['datetime']/1000, tz=timezone.utc)}")
        print(f"Last:  {datetime.fromtimestamp(candles[-1]['datetime']/1000, tz=timezone.utc)}")
else:
    print(f"Failed: {resp2.status_code} {resp2.text}")

# 3. Test /NQ with ET timezone datetimes
ET_TZ = ZoneInfo("America/New_York")
start_dt_et = start_dt.astimezone(ET_TZ)
end_dt_et = end_dt.astimezone(ET_TZ)

print(f"\n=== TEST 3: /NQ (Future) with NY datetimes ===")
print(f"Requesting /NQ in NY: {start_dt_et} -> {end_dt_et}")
resp3 = client.price_history(
    symbol="/NQ",
    frequencyType="minute",
    frequency=1,
    startDate=start_dt_et,
    endDate=end_dt_et,
    needExtendedHoursData=True
)
if resp3.status_code == 200:
    candles = resp3.json().get('candles', [])
    print(f"Returned {len(candles)} candles.")
    if candles:
        print(f"First: {datetime.fromtimestamp(candles[0]['datetime']/1000, tz=timezone.utc)}")
        print(f"Last:  {datetime.fromtimestamp(candles[-1]['datetime']/1000, tz=timezone.utc)}")
else:
    print(f"Failed: {resp3.status_code} {resp3.text}")
