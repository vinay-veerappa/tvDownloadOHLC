import json
with open('data/options/daily_levels.json') as f:
    data = json.load(f)

for entry in data['market_structure']:
    if entry.get('asset') == 'QQQ':
        ems = entry.get('expected_moves', [])
        print(f'QQQ has {len(ems)} EM entries:')
        for i, em in enumerate(ems[:3]):
            dte = em.get('dte')
            em_upper = em.get('em_upper')
            em_lower = em.get('em_lower')
            em_value = em.get('em_value')
            print(f'  [{i}] DTE={dte}, em_upper={em_upper}, em_lower={em_lower}, em_value={em_value}')
        print()
        print(f'Other fields: gamma_magnet={entry.get("gamma_magnet")}, call_volume_centroid={entry.get("call_volume_centroid")}')
        break
