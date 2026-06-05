import json
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

chart_levels = {
    'Upper Extreme': 7650.0,
    'Call Wall': 7640.0,
    'Flip': 7630.0,
    'Upper Implied Move': 7611.0,
    'Sticky Strike': 7590.0,
    'Put Support 1': 7580.0,
    'Put Support 2': 7570.0,
    'Lower Implied Move': 7534.0,
    'Put Support 3': 7530.0,
    'Lower Extreme': 7480.0
}

files = sorted(glob.glob('c:/Users/vinay/tvDownloadOHLC/data/options/daily_levels_20260603_*.json'))
files.append('c:/Users/vinay/tvDownloadOHLC/data/options/daily_levels.json')

results = []

for fpath in files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for asset in ['ES', 'SPX']:
            asset_levels = [x for x in data.get('levels', []) if x.get('asset') == asset]
            if not asset_levels:
                continue
                
            total_diff = 0.0
            matches = []
            for target_name, target_val in chart_levels.items():
                closest_lvl = None
                min_diff = 99999.0
                for lvl in asset_levels:
                    diff = abs(lvl.get('level', 0) - target_val)
                    if diff < min_diff:
                        min_diff = diff
                        closest_lvl = lvl
                if closest_lvl:
                    matches.append((target_name, target_val, closest_lvl.get('level'), closest_lvl.get('type'), min_diff))
                    total_diff += min_diff
                    
            results.append({
                'file': os.path.basename(fpath),
                'run_label': data.get('run_label'),
                'asset': asset,
                'total_diff': total_diff,
                'matches': matches
            })
    except Exception as e:
        pass

# Sort results by total_diff ascending
results.sort(key=lambda x: x['total_diff'])

print("TOP 5 BEST MATCHING RUNS:")
for r in results[:5]:
    print("="*80)
    print(f"File: {r['file']} | Run: {r['run_label']} | Asset: {r['asset']}")
    print(f"Total Absolute Difference: {r['total_diff']:.2f}")
    for name, target, actual, ltype, diff in r['matches']:
        print(f"  {name:20s} ({target:.1f}) -> Actual: {actual:7.2f} | Type: {ltype:25s} | Diff: {diff:.2f}")
