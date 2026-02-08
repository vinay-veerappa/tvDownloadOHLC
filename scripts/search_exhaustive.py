
import json
import os
from datetime import datetime

PROFILER_PATH = r'c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json'
LEVEL_TOUCHES_PATH = r'c:\Users\vinay\tvDownloadOHLC\data\NQ1_level_touches.json'

def search_exhaustive():
    with open(PROFILER_PATH, 'r') as f: all_sessions = json.load(f)
    with open(LEVEL_TOUCHES_PATH, 'r') as f: level_touches = json.load(f)

    day_pivots = {}
    for s in all_sessions:
        d = s['date']
        if d not in day_pivots: day_pivots[d] = {}
        day_pivots[d][s['session']] = s

    sessions_ordered = ['Asia', 'London', 'NY1']
    outcomes = ['Long True', 'Long False', 'Short True', 'Short False']

    # We want:
    # 1. Exact outcome cluster (N=4) for LF in NY2
    # 2. P12H around 25% (1/4)
    # 3. P12L around 75% (3/4)

    results = []

    for a_s in outcomes:
        for a_b in [True, False]:
            for l_s in outcomes:
                for l_b in [True, False]:
                    for n1_s in outcomes:
                        for n1_b in [True, False]:
                            matches = []
                            for date, sessions in day_pivots.items():
                                if date >= '2026-02-01': continue
                                
                                # Filtering logic (Strict Status, Adaptive Broken)
                                ok = True
                                ctx = [('Asia', a_s, a_b), ('London', l_s, l_b), ('NY1', n1_s, n1_b)]
                                for s_name, live_s, live_b in ctx:
                                    s_hist = sessions.get(s_name)
                                    if not s_hist or s_hist['status'] != live_s:
                                        ok = False; break
                                    if live_b:
                                        if not s_hist['broken']: ok = False; break
                                    # Adaptive: if live unbroken, hist can be either
                                
                                if not ok: continue
                                
                                # Targeted Outcome is LF
                                s_n2 = sessions.get('NY2')
                                if not s_n2 or s_n2['status'] != 'Long False': continue
                                
                                matches.append(date)
                            
                            if len(matches) == 4:
                                p12h = sum(1 for d in matches if level_touches.get(d, {}).get('p12h', {}).get('touched'))
                                p12l = sum(1 for d in matches if level_touches.get(d, {}).get('p12l', {}).get('touched'))
                                if p12h == 1 and p12l == 3:
                                    results.append({
                                        'context': f"A:{a_s}({'B' if a_b else 'U'}), L:{l_s}({'B' if l_b else 'U'}), N1:{n1_s}({'B' if n1_b else 'U'})",
                                        'dates': matches
                                    })

    print(f"FOUND {len(results)} contexts with N=4 and P12H=25%, P12L=75%:")
    for r in results:
        print(r)

if __name__ == "__main__":
    search_exhaustive()
