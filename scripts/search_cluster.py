
import json
import os

PROFILER_PATH = r'c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json'
LEVEL_TOUCHES_PATH = r'c:\Users\vinay\tvDownloadOHLC\data\NQ1_level_touches.json'

def get_status_code(status):
    mapping = {'Long True': 1, 'Long False': 2, 'Short True': 3, 'Short False': 4, 'Neutral': 0, 'Pending': 0}
    return mapping.get(status, 0)

def search_cluster():
    with open(PROFILER_PATH, 'r') as f:
        all_sessions = json.load(f)
    with open(LEVEL_TOUCHES_PATH, 'r') as f:
        level_touches = json.load(f)

    # Context: A:LF(B), L:ST(U), N1:SF(B)
    live = {
        'Asia': {'s': 'Long False', 'b': True},
        'London': {'s': 'Short True', 'b': False},
        'NY1': {'s': 'Short False', 'b': True},
        'NY2': {'s': 'Long False', 'b': False} # Target
    }

    day_pivots = {}
    for s in all_sessions:
        d = s['date']
        if d not in day_pivots: day_pivots[d] = {}
        day_pivots[d][s['session']] = s

    def test_filter(a_strict_b, l_strict_b, n1_strict_b):
        matches = []
        for date, sessions in day_pivots.items():
            if date >= '2026-02-01': continue # Skip recent
            
            # Asia
            s_a = sessions.get('Asia')
            if not s_a or s_a['status'] != live['Asia']['s']: continue
            if a_strict_b and s_a['broken'] != live['Asia']['b']: continue
            if not a_strict_b and live['Asia']['b'] and not s_a['broken']: continue # Adaptive: If live broken, hist must be broken
            
            # London
            s_l = sessions.get('London')
            if not s_l or s_l['status'] != live['London']['s']: continue
            if l_strict_b and s_l['broken'] != live['London']['b']: continue
            if not l_strict_b and live['London']['b'] and not s_l['broken']: continue
            
            # NY1
            s_n1 = sessions.get('NY1')
            if not s_n1 or s_n1['status'] != live['NY1']['s']: continue
            if n1_strict_b and s_n1['broken'] != live['NY1']['b']: continue
            if not n1_strict_b and live['NY1']['b'] and not s_n1['broken']: continue

            # Target NY2 must be LF for the N=4 cluster they mention
            s_n2 = sessions.get('NY2')
            if not s_n2 or s_n2['status'] != 'Long False': continue

            matches.append(date)
        
        if len(matches) == 4:
            # Calculate hit rates for P12H and P12L
            p12h_hits = sum(1 for d in matches if level_touches.get(d, {}).get('p12h', {}).get('touched'))
            p12l_hits = sum(1 for d in matches if level_touches.get(d, {}).get('p12l', {}).get('touched'))
            print(f"Cluster N=4 FOUND! A:{'S' if a_strict_b else 'A'}, L:{'S' if l_strict_b else 'A'}, N1:{'S' if n1_strict_b else 'A'}")
            print(f"  Dates: {matches}")
            print(f"  P12H: {p12h_hits/4*100}%, P12L: {p12l_hits/4*100}%")
            print("-" * 20)

    print("SEARCHING FOR N=4 CLUSTER WITH P12H=25%, P12L=75%...")
    for a in [True, False]:
        for l in [True, False]:
            for n1 in [True, False]:
                test_filter(a, l, n1)

if __name__ == "__main__":
    search_cluster()
