import json
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

targets = [7611, 7534]
files = sorted(glob.glob('c:/Users/vinay/tvDownloadOHLC/data/options/daily_levels_20260603_*.json'))
files.append('c:/Users/vinay/tvDownloadOHLC/data/options/daily_levels.json')

for fpath in files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Check all level items in 'levels'
        for lvl in data.get('levels', []):
            val = lvl.get('level', 0)
            for t in targets:
                if abs(val - t) <= 1.0:
                    print(f"File: {os.path.basename(fpath)} | Asset: {lvl.get('asset')} | Type: {lvl.get('type')} | Val: {val:.2f} | Target: {t}")
                    
        # Check expected moves in market_structure
        for ms in data.get('market_structure', []):
            asset = ms.get('asset')
            for em in ms.get('expected_moves', []):
                u = em.get('em_upper', 0)
                l = em.get('em_lower', 0)
                for t in targets:
                    if abs(u - t) <= 1.0:
                        print(f"File: {os.path.basename(fpath)} | MS Asset: {asset} | EM Upper (Expiry {em.get('expiry')}): {u:.2f} | Target: {t}")
                    if abs(l - t) <= 1.0:
                        print(f"File: {os.path.basename(fpath)} | MS Asset: {asset} | EM Lower (Expiry {em.get('expiry')}): {l:.2f} | Target: {t}")
    except Exception as e:
        print(f"Error: {e}")
