import json
from pathlib import Path

p = Path('data/options/daily_levels.json')
if p.exists():
    with open(p) as f:
        data = json.load(f)
    
    print(f'Keys: {list(data.keys())}')
    if 'market_structure' in data:
        print(f'Market structure entries: {len(data["market_structure"])}')
        # Show first entry
        for i, entry in enumerate(data['market_structure'][:3]):
            ticker = entry.get('ticker')
            print(f'\n[{i}] ticker={ticker}')
            if 'expected_moves' in entry:
                ems = entry['expected_moves']
                print(f'  Expected moves: {len(ems)} entries')
                if ems:
                    em = ems[0]
                    print(f'    First EM: DTE={em.get("dte")}, expiry={em.get("expiry")}, em_upper={em.get("em_upper")}, em_lower={em.get("em_lower")}')
else:
    print(f'File not found: {p}')
