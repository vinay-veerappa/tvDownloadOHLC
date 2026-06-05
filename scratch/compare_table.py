import json
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

def get_levels(fpath):
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

f1615 = 'c:/Users/vinay/tvDownloadOHLC/data/options/daily_levels_20260603_1615.json'
f1745 = 'c:/Users/vinay/tvDownloadOHLC/data/options/daily_levels.json'

data_1615 = get_levels(f1615)
data_1745 = get_levels(f1745)

print("COMPARISON OF CHART LEVELS AGAINST CALCULATED LEVELS")
print("="*120)
print(f"{'Chart Level Label':<22} | {'Chart':<6} | {'ES 16:15':<15} | {'SPX 16:15':<15} | {'ES 17:45':<15} | {'SPX 17:45':<15}")
print("-"*120)

def find_closest(levels, target, asset):
    asset_lvls = [x for x in levels if x.get('asset') == asset]
    if not asset_lvls:
        return "N/A", 9999.0
    closest = min(asset_lvls, key=lambda x: abs(x.get('level', 0) - target))
    return f"{closest.get('level'):.2f} ({closest.get('type')})", abs(closest.get('level', 0) - target)

for label, target in chart_levels.items():
    es_1615_str, _ = find_closest(data_1615['levels'], target, 'ES')
    spx_1615_str, _ = find_closest(data_1615['levels'], target, 'SPX')
    es_1745_str, _ = find_closest(data_1745['levels'], target, 'ES')
    spx_1745_str, _ = find_closest(data_1745['levels'], target, 'SPX')
    
    print(f"{label:<22} | {target:<6.1f} | {es_1615_str:<15} | {spx_1615_str:<15} | {es_1745_str:<15} | {spx_1745_str:<15}")

print("="*120)
print(f"Basis spreads: 16:15 run basis spread is 14.97 | 17:45 run basis spread is 14.97")
