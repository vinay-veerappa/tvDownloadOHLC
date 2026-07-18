"""Check if raw unadjusted JSON matches WebUI unadjusted API."""
import json, urllib.request

# Raw unadjusted JSON
raw = json.load(open(r'C:\Users\vinay\tvDownloadOHLC\data\NQ1_daily_hod_lod_unadjusted.json'))

# WebUI API
with urllib.request.urlopen('http://127.0.0.1:8000/stats/daily-hod-lod/NQ1?unadjusted=true', timeout=30) as resp:
    api = json.loads(resp.read().decode())

# Check 5 LT dates
lt_dates = ['2006-08-02', '2007-11-13', '2008-03-18', '2010-03-17', '2012-11-01']

for d in lt_dates:
    if d in raw and d in api["dates"]:
        raw_e = raw[d]
        api_idx = api["dates"].index(d)
        api_open = api["daily_open"][api_idx]
        api_high = api["daily_high"][api_idx]
        api_low = api["daily_low"][api_idx]
        raw_open = raw_e.get("daily_open")
        raw_high = raw_e.get("daily_high")
        raw_low = raw_e.get("daily_low")
        print(f"{d}:")
        print(f"  Raw: open={raw_open} high={raw_high} low={raw_low}")
        print(f"  API: open={api_open} high={api_high} low={api_low}")
        print(f"  Match: {raw_open == api_open and raw_high == api_high and raw_low == api_low}")
        print()