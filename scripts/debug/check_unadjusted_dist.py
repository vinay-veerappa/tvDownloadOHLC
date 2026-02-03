
import json
import statistics
from pathlib import Path

def analyze_distribution():
    json_path = Path(r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_daily_hod_lod_unadjusted.json")
    if not json_path.exists():
        print(f"File not found: {json_path}")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)

    high_pcts = []
    low_pcts = []

    print(f"Analyzing {len(data)} days...")

    for date, stats in data.items():
        d_open = stats.get('daily_open')
        d_high = stats.get('daily_high')
        d_low = stats.get('daily_low')
        
        # Use hod_price if daily_high missing (as per logic)
        if d_high is None: d_high = stats.get('hod_price')
        if d_low is None: d_low = stats.get('lod_price')

        if d_open and d_open > 0 and d_high is not None:
             pct = (d_high - d_open) / d_open * 100
             high_pcts.append(pct)
        
        if d_open and d_open > 0 and d_low is not None:
             pct = (d_low - d_open) / d_open * 100
             low_pcts.append(pct)

    print(f"Valid High Pcts: {len(high_pcts)}")
    
    # Calculate Stats
    h_median = statistics.median(high_pcts)
    h_mean = statistics.mean(high_pcts)
    h_max = max(high_pcts)
    
    # Mode (Method: Binning 0.1%)
    def get_mode(arr):
        counts = {}
        for v in arr:
            b = round(v * 10) / 10 # 0.1 bin
            counts[b] = counts.get(b, 0) + 1
        return max(counts, key=counts.get)

    h_mode = get_mode(high_pcts)

    print(f"HIGH Distribution:")
    print(f"  Median: {h_median:.2f}%")
    print(f"  Mode (0.1% bin): {h_mode:.1f}%")
    print(f"  Max: {h_max:.2f}%")
    
    over_5 = len([x for x in high_pcts if x > 5])
    print(f"  Count > 5%: {over_5} ({over_5/len(high_pcts)*100:.2f}%)")

if __name__ == "__main__":
    analyze_distribution()
