
import json
import math
import pandas as pd

UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
START_DATE = "2006-11-15"
END_DATE = "2025-01-16"

def get_bucket(val):
    if pd.isna(val) or val < 0: return 0.0
    b = math.floor(val * 10) / 10.0
    return b if b < 5.0 else 5.0

def analyze():
    with open(UNADJUSTED_JSON, 'r') as f:
        data = json.load(f)
    
    dates = sorted([d for d in data.keys() if START_DATE <= d <= END_DATE])
    
    print(f"Analyzing {len(dates)} days...")
    
    target_bucket = 0.5
    bucket_dates = []
    
    for d in dates:
        e = data[d]
        op = e['daily_open']
        hi = e['daily_high']
        if op > 0:
            pct = (hi - op) / op * 100
            b = get_bucket(pct)
            if b == target_bucket:
                bucket_dates.append({
                    'date': d,
                    'pct': pct,
                    'vol': e.get('volume', 0),
                    'range': (e['daily_high'] - e['daily_low']) / op * 100
                })
                
    print(f"\nExample Days in {target_bucket}% Bucket (N={len(bucket_dates)}):")
    df = pd.DataFrame(bucket_dates)
    df['date'] = pd.to_datetime(df['date'])
    df['day_name'] = df['date'].dt.day_name()
    
    # Sort by lowest volume
    print(df.sort_values('vol').head(20))
    
    print("\nDay of Week Distribution in Bucket:")
    print(df['day_name'].value_counts())

if __name__ == "__main__":
    analyze()
