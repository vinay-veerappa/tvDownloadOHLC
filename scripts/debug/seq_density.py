import json
from pathlib import Path
from collections import Counter

def get_seqs(ticker):
    prof_path = Path('data') / f'{ticker}_profiler.json'
    with open(prof_path, 'r') as f: data = json.load(f)
    
    days = {}
    for e in data:
        d = e['date']
        if d not in days: days[d] = {}
        days[d][e['session']] = e['status'] + (' BK' if e.get('broken') else '')
    
    s_a = [] # Asia
    s_al = [] # Asia, Lon
    s_aln = [] # Asia, Lon, NY1
    
    for d, s in days.items():
        if 'Asia' in s:
            s_a.append(s['Asia'])
            if 'London' in s:
                s_al.append(f"{s['Asia']} | {s['London']}")
                if 'NY1' in s:
                    s_aln.append(f"{s['Asia']} | {s['London']} | {s['NY1']}")

    def count_valid(arr, min_c=5):
        return len([s for s, c in Counter(arr).items() if c >= min_c])

    print(f"\n--- {ticker} Stats ---")
    print(f"Asia Combos (>=5 days): {count_valid(s_a)}")
    print(f"Asia+Lon Combos (>=5 days): {count_valid(s_al)}")
    print(f"Asia+Lon+NY1 Combos (>=5 days): {count_valid(s_aln)}")

get_seqs('NQ1')
get_seqs('ES1')
