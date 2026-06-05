import json
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# The chart levels
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

for fpath in files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print("="*80)
        print(f"File: {os.path.basename(fpath)}")
        print(f"Run Label: {data.get('run_label')}")
        
        # Check ES and SPX levels
        for asset in ['ES', 'SPX']:
            asset_levels = [x for x in data.get('levels', []) if x.get('asset') == asset]
            if not asset_levels:
                continue
                
            print(f"  Asset: {asset}")
            matches = []
            for target_name, target_val in chart_levels.items():
                # Find closest level
                closest_lvl = None
                min_diff = 99999.0
                for lvl in asset_levels:
                    diff = abs(lvl.get('level', 0) - target_val)
                    if diff < min_diff:
                        min_diff = diff
                        closest_lvl = lvl
                if closest_lvl:
                    matches.append((target_name, target_val, closest_lvl.get('level'), closest_lvl.get('type'), min_diff))
            
            # Print matches
            total_diff = 0.0
            for target_name, target_val, actual_val, actual_type, diff in matches:
                total_diff += diff
                print(f"    {target_name:20s} ({target_val:.1f}) -> Actual: {actual_val:7.2f} | Type: {actual_type:28s} | Diff: {diff:.2f}")
            print(f"    Total Absolute Difference: {total_diff:.2f}")
            
    except Exception as e:
        print(f"Error reading {fpath}: {e}")
