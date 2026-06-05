import json
import glob
import os
import sys

# Reconfigure stdout to use UTF-8
sys.stdout.reconfigure(encoding='utf-8')

files = sorted(glob.glob('c:/Users/vinay/tvDownloadOHLC/data/options/daily_levels_20260603_*.json'))
files.append('c:/Users/vinay/tvDownloadOHLC/data/options/daily_levels.json')

for fpath in files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("="*60)
        print(f"File: {os.path.basename(fpath)}")
        print(f"Generated at: {data.get('generated_at')}")
        print(f"Run Label: {data.get('run_label')}")
        
        for asset in ['ES', 'SPX']:
            levels = [x for x in data.get('levels', []) if x.get('asset') == asset]
            if not levels:
                continue
            print(f"  Asset: {asset}")
            for lvl in sorted(levels, key=lambda x: x.get('level', 0), reverse=True):
                ltype = lvl.get('type')
                val = lvl.get('level')
                print(f"    {ltype:25s}: {val}")
    except Exception as e:
        print(f"Error reading {fpath}: {e}")
