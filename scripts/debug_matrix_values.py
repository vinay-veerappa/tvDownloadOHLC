
import json
from datetime import datetime

LEVEL_TOUCHES_PATH = r'c:\Users\vinay\tvDownloadOHLC\data\NQ1_level_touches.json'

def get_session_hit(day_levels, level_key, start_min, end_min):
    level_data = day_levels.get(level_key, {})
    if not level_data.get('touched'): return False
    
    # Check touch times
    times = level_data.get('touch_times', [])
    for t in times:
        try:
            h, m = map(int, t.split(':'))
            mins = h * 60 + m
            
            # NY2 Range: 11:30 - 16:00
            # 11:30 = 690 mins
            # 16:00 = 960 mins
            if 690 <= mins < 960:
                return True
        except: continue
    return False

def debug_hitrates():
    with open(LEVEL_TOUCHES_PATH, 'r') as f: level_data = json.load(f)
    
    # The 4 dates identified for LF in the current context
    target_dates = ['2018-11-16', '2020-05-19', '2022-12-16', '2024-09-11']
    
    metrics = ['p12h', 'p12l', 'midnight_open', 'open_0730', 'asia_mid', 'london_mid', 'pdh', 'pdm', 'pdl']
    
    print(f"Session-Specific Hit Rates (NY2) for LF cluster (N=4):")
    for m in metrics:
        hits = 0
        for d in target_dates:
            day_l = level_data.get(d, {})
            if get_session_hit(day_l, m, 690, 960):
                hits += 1
        rate = (hits / 4) * 100
        print(f"  {m}: {rate:.1f}% ({hits}/4)")

if __name__ == '__main__':
    debug_hitrates()
