import json
from datetime import datetime
import pytz
from collections import Counter

nyc = pytz.timezone('America/New_York')

# Check what hours appear in the final JSON output
for ticker in ['ES1_1D', 'NQ1_1D', 'CL1_1D']:
    data = json.load(open(f'web/public/data/{ticker}/chunk_0.json'))
    
    hours = []
    for bar in data:
        dt = datetime.fromtimestamp(bar['time'], tz=pytz.UTC).astimezone(nyc)
        hours.append(dt.hour)
    
    hour_counts = Counter(hours)
    print(f"\n{ticker} JSON output:")
    print(f"  Total bars: {len(data)}")
    print(f"  Hour distribution: {dict(sorted(hour_counts.items()))}")
    
    # Check last 10 bars
    print(f"  Last 10 bars:")
    for bar in data[-10:]:
        dt = datetime.fromtimestamp(bar['time'], tz=pytz.UTC).astimezone(nyc)
        print(f"    {dt.strftime('%Y-%m-%d %H:%M')} - O={bar['open']:.2f}")
