import json
import os
import datetime

path = "data/live/live_chart_-NQ.json"

if not os.path.exists(path):
    print("❌ File not found")
    exit()

with open(path, "r") as f:
    data = json.load(f)

candles = data.get("candles", [])
print(f"Total candles: {len(candles)}")

if not candles:
    print("Empty")
    exit()

# Sort
candles.sort(key=lambda x: x['time'])

# Check Jan 14-21
start_ms = 1736812800000 # Jan 14
end_ms = 1737417600000 # Jan 21

range_candles = [c for c in candles if start_ms <= c['time'] <= end_ms]

print(f"Candles in Jan 14-21 window: {len(range_candles)}")
if range_candles:
    print("First:", range_candles[0])
    print("Last:", range_candles[-1])

# Check Head/Tail of file
print("\nFile Head (First 3):", candles[:3])
print("File Tail (Last 3):", candles[-3:])
