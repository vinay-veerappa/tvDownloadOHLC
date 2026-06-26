import json
import math
from zoneinfo import ZoneInfo
from datetime import datetime, time

# Load versioned profiles and daily levels
with open('data/options/gex_profiles_versioned.json') as f:
    data_profiles = json.load(f)

with open('data/options/daily_levels_versioned.json') as f:
    data_levels = json.load(f)

profiles = data_profiles['profiles']

# Helper function to get spot price from daily_levels_versioned.json
spot_prices = {}
for asset_struct in data_levels['market_structure']:
    asset = asset_struct['asset']
    # Let's find spot price. Wait, does it have spot price?
    # Let's check what keys are in asset_struct
    # print(asset_struct.keys())
    # Wait, daily levels has spot price in other places? Let's check.
    pass

# Actually, let's write a python snippet to find spot prices in daily_levels_versioned.json
# and print them
print("Asset keys in daily_levels_versioned.json:")
for item in data_levels['market_structure']:
    print(f"Asset: {item.get('asset')}, Cash Ticker: {item.get('cash_ticker')}")
    # Let's see if we can find spot price inside
