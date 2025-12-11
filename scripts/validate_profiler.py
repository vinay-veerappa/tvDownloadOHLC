"""Validate profiler data against reference."""
import json
from pathlib import Path

# Load reference data
ref_path = Path("docs/ReferenceAll.json")  
my_path = Path("data/NQ1_profiler.json")

if not ref_path.exists():
    print(f"Reference file not found: {ref_path}")
    exit(1)

with open(ref_path) as f:
    ref_data = json.load(f)

with open(my_path) as f:
    my_data = json.load(f)

ref_count = ref_data.get('meta', {}).get('count', 0)
print(f"Reference total days: {ref_count}")
print(f"My profiler records: {len(my_data)}")

# Count by session in my data
my_counts = {
    'asia': {'long': 0, 'short': 0, 'none': 0, 'true': 0, 'false': 0, 'broken': 0, 'complete': 0},
    'london': {'long': 0, 'short': 0, 'none': 0, 'true': 0, 'false': 0, 'broken': 0, 'complete': 0},
    'ny1': {'long': 0, 'short': 0, 'none': 0, 'true': 0, 'false': 0, 'broken': 0, 'complete': 0},
    'ny2': {'long': 0, 'short': 0, 'none': 0, 'true': 0, 'false': 0}  # NY2 has no broken
}

undirected_false_count = 0

for record in my_data:
    session = record.get('session', '').lower()
    status = record.get('status', '')
    broken = record.get('broken', '')
    
    if session not in my_counts:
        continue
    
    # Direction and session outcome
    if status == 'Long True':
        my_counts[session]['long'] += 1
        my_counts[session]['true'] += 1
    elif status == 'Long False':
        my_counts[session]['long'] += 1
        my_counts[session]['false'] += 1
    elif status == 'Short True':
        my_counts[session]['short'] += 1
        my_counts[session]['true'] += 1
    elif status == 'Short False':
        my_counts[session]['short'] += 1
        my_counts[session]['false'] += 1
    elif status == 'False':
        # Undirected False - this is a bug
        undirected_false_count += 1
        my_counts[session]['false'] += 1
    elif status == 'None' or status is None:
        my_counts[session]['none'] += 1
    
    # Broken status (boolean in my data)
    if session != 'ny2':  # NY2 doesn't have broken
        if broken is True:
            my_counts[session]['broken'] += 1
        elif broken is False:
            my_counts[session]['complete'] += 1

ref_probs = ref_data.get('probabilities', {})

print("\n" + "="*70)
print("COMPARISON: MY DATA vs REFERENCE")
print("="*70)

for session in ['asia', 'london', 'ny1', 'ny2']:
    ref_session = ref_probs.get(session, {})
    my_session = my_counts.get(session, {})
    
    print(f"\n--- {session.upper()} ---")
    
    # Direction
    ref_dir = ref_session.get('direction', {})
    print(f"  Direction:")
    print(f"    Long:  Mine={my_session.get('long', 0):5}  Ref={ref_dir.get('long', 0):5}  Diff={my_session.get('long', 0) - ref_dir.get('long', 0):+5}")
    print(f"    Short: Mine={my_session.get('short', 0):5}  Ref={ref_dir.get('short', 0):5}  Diff={my_session.get('short', 0) - ref_dir.get('short', 0):+5}")
    print(f"    None:  Mine={my_session.get('none', 0):5}  Ref={ref_dir.get('none', 0):5}  Diff={my_session.get('none', 0) - ref_dir.get('none', 0):+5}")
    
    # Session outcome
    ref_sess = ref_session.get('session', {})
    print(f"  Session Outcome:")
    print(f"    True:  Mine={my_session.get('true', 0):5}  Ref={ref_sess.get('true', 0):5}  Diff={my_session.get('true', 0) - ref_sess.get('true', 0):+5}")
    print(f"    False: Mine={my_session.get('false', 0):5}  Ref={ref_sess.get('false', 0):5}  Diff={my_session.get('false', 0) - ref_sess.get('false', 0):+5}")
    
    # Broken (not for NY2)
    if session != 'ny2':
        ref_brk = ref_session.get('broken', {})
        print(f"  Broken Status:")
        print(f"    Broken:   Mine={my_session.get('broken', 0):5}  Ref={ref_brk.get('broken', 0):5}  Diff={my_session.get('broken', 0) - ref_brk.get('broken', 0):+5}")
        print(f"    Complete: Mine={my_session.get('complete', 0):5}  Ref={ref_brk.get('complete', 0):5}  Diff={my_session.get('complete', 0) - ref_brk.get('complete', 0):+5}")

# My total days
my_dates = set(r.get('date') for r in my_data if r.get('date'))
print(f"\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"My unique dates: {len(my_dates)}")
print(f"Reference days: {ref_count}")
print(f"Undirected 'False' statuses (bug): {undirected_false_count}")

if my_dates:
    dates_sorted = sorted(my_dates)
    print(f"My date range: {dates_sorted[0]} to {dates_sorted[-1]}")
