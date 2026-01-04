"""
ALN + Profiler Session Unification Analysis
============================================
This script analyzes how Asia + London session data predicts NY AM/PM behavior.

Output:
1. ALN Pattern Distribution (LEA, LPEU, LPED, AEL)
2. NY1/NY2 Outcomes by ALN Pattern
3. NY1/NY2 Outcomes by Profiler Status Combinations
"""

import json
from collections import defaultdict
from pathlib import Path

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
PROFILER_FILE = DATA_DIR / "NQ1_profiler.json"

def load_profiler_data():
    """Load profiler JSON and group by date."""
    with open(PROFILER_FILE) as f:
        data = json.load(f)
    
    # Group by date
    daily = defaultdict(dict)
    for record in data:
        date = record['date']
        session = record['session']
        daily[date][session] = record
    
    return daily


def classify_aln(asia: dict, london: dict) -> str:
    """Classify the ALN pattern based on Asia-London range comparison."""
    if not asia or not london:
        return 'Unknown'
    
    asia_h = asia.get('range_high')
    asia_l = asia.get('range_low')
    london_h = london.get('range_high')
    london_l = london.get('range_low')
    
    if None in (asia_h, asia_l, london_h, london_l):
        return 'Unknown'
    
    # LEA: London Engulfs Asia (breaks BOTH extremes)
    if london_h > asia_h and london_l < asia_l:
        return 'LEA'
    
    # LPEU: Partial Engulf Up (breaks Asia High, holds Asia Low)
    if london_h > asia_h and london_l >= asia_l:
        return 'LPEU'
    
    # LPED: Partial Engulf Down (breaks Asia Low, holds Asia High)
    if london_l < asia_l and london_h <= asia_h:
        return 'LPED'
    
    # AEL: Asia Engulfs London (London inside Asia)
    return 'AEL'


def analyze_by_aln_pattern(daily: dict):
    """Analyze NY outcomes by ALN pattern."""
    results = defaultdict(lambda: {
        'count': 0,
        'ny1_long_true': 0, 'ny1_short_true': 0, 'ny1_none': 0,
        'ny1_broken': 0,
        'ny2_long_true': 0, 'ny2_short_true': 0, 'ny2_none': 0,
        'ny2_broken': 0,
    })
    
    for date, sessions in daily.items():
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        ny2 = sessions.get('NY2')
        
        pattern = classify_aln(asia, london)
        if pattern == 'Unknown':
            continue
        
        results[pattern]['count'] += 1
        
        # NY1 Outcomes
        if ny1:
            status = ny1.get('status', 'None')
            if status == 'Long True':
                results[pattern]['ny1_long_true'] += 1
            elif status == 'Short True':
                results[pattern]['ny1_short_true'] += 1
            else:
                results[pattern]['ny1_none'] += 1
            
            if ny1.get('broken'):
                results[pattern]['ny1_broken'] += 1
        
        # NY2 Outcomes
        if ny2:
            status = ny2.get('status', 'None')
            if status == 'Long True':
                results[pattern]['ny2_long_true'] += 1
            elif status == 'Short True':
                results[pattern]['ny2_short_true'] += 1
            else:
                results[pattern]['ny2_none'] += 1
            
            if ny2.get('broken'):
                results[pattern]['ny2_broken'] += 1
    
    return dict(results)


def analyze_by_status_combo(daily: dict):
    """Analyze NY outcomes by Asia+London status combinations."""
    results = defaultdict(lambda: {
        'count': 0,
        'ny1_long_true': 0, 'ny1_short_true': 0,
        'ny2_long_true': 0, 'ny2_short_true': 0,
    })
    
    for date, sessions in daily.items():
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        ny2 = sessions.get('NY2')
        
        if not asia or not london:
            continue
        
        asia_status = asia.get('status', 'None')
        london_status = london.get('status', 'None')
        
        # Simplify to L/S/N
        asia_s = 'L' if 'Long' in asia_status else ('S' if 'Short' in asia_status else 'N')
        london_s = 'L' if 'Long' in london_status else ('S' if 'Short' in london_status else 'N')
        
        combo = f"Asia={asia_s}, London={london_s}"
        results[combo]['count'] += 1
        
        if ny1:
            status = ny1.get('status', 'None')
            if status == 'Long True':
                results[combo]['ny1_long_true'] += 1
            elif status == 'Short True':
                results[combo]['ny1_short_true'] += 1
        
        if ny2:
            status = ny2.get('status', 'None')
            if status == 'Long True':
                results[combo]['ny2_long_true'] += 1
            elif status == 'Short True':
                results[combo]['ny2_short_true'] += 1
    
    return dict(results)


def print_aln_results(results: dict):
    """Print ALN pattern analysis."""
    print("\n" + "="*60)
    print("ALN PATTERN ANALYSIS (NQ1)")
    print("="*60)
    
    for pattern in ['LPEU', 'LPED', 'LEA', 'AEL']:
        if pattern not in results:
            continue
        r = results[pattern]
        n = r['count']
        if n == 0:
            continue
        
        ny1_l = r['ny1_long_true'] / n * 100
        ny1_s = r['ny1_short_true'] / n * 100
        ny1_b = r['ny1_broken'] / n * 100
        ny2_l = r['ny2_long_true'] / n * 100
        ny2_s = r['ny2_short_true'] / n * 100
        
        print(f"\n--- {pattern} ({n} days) ---")
        print(f"  NY1 (AM): Long={ny1_l:.1f}%, Short={ny1_s:.1f}%, Broken={ny1_b:.1f}%")
        print(f"  NY2 (PM): Long={ny2_l:.1f}%, Short={ny2_s:.1f}%")
        
        # Interpretation
        if pattern == 'LPEU':
            cont = ny1_l
            print(f"  → BULLISH Continuation: {cont:.1f}% (NQStats claims 82%)")
        elif pattern == 'LPED':
            cont = ny1_s
            print(f"  → BEARISH Continuation: {cont:.1f}% (NQStats claims 76%)")


def print_combo_results(results: dict):
    """Print Status Combo analysis."""
    print("\n" + "="*60)
    print("PROFILER STATUS COMBO ANALYSIS")
    print("="*60)
    print("Format: Asia Status + London Status → NY1/NY2 Outcomes\n")
    
    # Sort by count
    sorted_combos = sorted(results.items(), key=lambda x: x[1]['count'], reverse=True)
    
    for combo, r in sorted_combos:
        n = r['count']
        if n < 50:  # Skip rare combos
            continue
        
        ny1_l = r['ny1_long_true'] / n * 100
        ny1_s = r['ny1_short_true'] / n * 100
        ny2_l = r['ny2_long_true'] / n * 100
        ny2_s = r['ny2_short_true'] / n * 100
        
        print(f"{combo} ({n} days)")
        print(f"  NY1: Long={ny1_l:.1f}%, Short={ny1_s:.1f}%")
        print(f"  NY2: Long={ny2_l:.1f}%, Short={ny2_s:.1f}%")
        
        # Key insight
        if ny1_l > 55:
            print(f"  ✅ BULLISH BIAS for NY AM")
        elif ny1_s > 55:
            print(f"  ✅ BEARISH BIAS for NY AM")
        print()


def analyze_london_break(daily: dict):
    """
    Analyze if NY breaks London High/Low based on ALN pattern.
    This validates the NQStats 82% claim for LPEU.
    """
    results = defaultdict(lambda: {
        'count': 0,
        'ny_breaks_london_high': 0,
        'ny_breaks_london_low': 0,
        'ny_breaks_both': 0,
    })
    
    for date, sessions in daily.items():
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        
        pattern = classify_aln(asia, london)
        if pattern == 'Unknown' or not london or not ny1:
            continue
        
        london_h = london.get('range_high')
        london_l = london.get('range_low')
        # Use daily_high/low which spans full NY session
        ny_h = ny1.get('daily_high')
        ny_l = ny1.get('daily_low')
        
        if None in (london_h, london_l, ny_h, ny_l):
            continue
        
        results[pattern]['count'] += 1
        
        if ny_h > london_h:
            results[pattern]['ny_breaks_london_high'] += 1
        if ny_l < london_l:
            results[pattern]['ny_breaks_london_low'] += 1
        if ny_h > london_h and ny_l < london_l:
            results[pattern]['ny_breaks_both'] += 1
    
    return dict(results)


def print_london_break_results(results: dict):
    """Print London Range Break analysis (NQStats validation)."""
    print("\n" + "="*60)
    print("LONDON RANGE BREAK ANALYSIS (NQStats Validation)")
    print("="*60)
    print("Does NY break London High/Low during the day?\n")
    
    for pattern in ['LPEU', 'LPED', 'LEA', 'AEL']:
        if pattern not in results:
            continue
        r = results[pattern]
        n = r['count']
        if n == 0:
            continue
        
        break_h = r['ny_breaks_london_high'] / n * 100
        break_l = r['ny_breaks_london_low'] / n * 100
        break_both = r['ny_breaks_both'] / n * 100
        
        print(f"--- {pattern} ({n} days) ---")
        print(f"  NY Breaks London HIGH: {break_h:.1f}%")
        print(f"  NY Breaks London LOW:  {break_l:.1f}%")
        print(f"  NY Breaks BOTH:        {break_both:.1f}%")
        
        # NQStats comparison
        if pattern == 'LPEU':
            print(f"  → NQStats Claim: 82% break London High. Actual: {break_h:.1f}%")
        elif pattern == 'LPED':
            print(f"  → NQStats Claim: 76% break London Low. Actual: {break_l:.1f}%")
        print()


def analyze_by_broken_status(daily: dict):
    """
    Analyze NY outcomes based on whether Asia/London ranges were broken.
    'broken' = True means the session's range was broken by the next session.
    """
    results = defaultdict(lambda: {
        'count': 0,
        'ny1_long_true': 0, 'ny1_short_true': 0,
        'ny1_broken': 0,
        'ny_breaks_london_high': 0, 'ny_breaks_london_low': 0,
    })
    
    for date, sessions in daily.items():
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        
        if not asia or not london or not ny1:
            continue
        
        asia_broken = asia.get('broken', False)
        london_broken = london.get('broken', False)
        
        # Create combo key
        a_b = 'Broken' if asia_broken else 'Held'
        l_b = 'Broken' if london_broken else 'Held'
        combo = f"Asia={a_b}, London={l_b}"
        
        results[combo]['count'] += 1
        
        # NY1 Status
        status = ny1.get('status', 'None')
        if status == 'Long True':
            results[combo]['ny1_long_true'] += 1
        elif status == 'Short True':
            results[combo]['ny1_short_true'] += 1
        
        if ny1.get('broken'):
            results[combo]['ny1_broken'] += 1
        
        # London Range Break
        london_h = london.get('range_high')
        london_l = london.get('range_low')
        ny_h = ny1.get('daily_high')
        ny_l = ny1.get('daily_low')
        
        if london_h and london_l and ny_h and ny_l:
            if ny_h > london_h:
                results[combo]['ny_breaks_london_high'] += 1
            if ny_l < london_l:
                results[combo]['ny_breaks_london_low'] += 1
    
    return dict(results)


def print_broken_results(results: dict):
    """Print Broken Status analysis."""
    print("\n" + "="*60)
    print("ASIA/LONDON BROKEN STATUS ANALYSIS")
    print("="*60)
    print("'Broken' = Session range was broken by next session.\n")
    
    # Sort by count
    sorted_combos = sorted(results.items(), key=lambda x: x[1]['count'], reverse=True)
    
    for combo, r in sorted_combos:
        n = r['count']
        if n < 50:
            continue
        
        ny1_l = r['ny1_long_true'] / n * 100
        ny1_s = r['ny1_short_true'] / n * 100
        ny1_b = r['ny1_broken'] / n * 100
        break_h = r['ny_breaks_london_high'] / n * 100
        break_l = r['ny_breaks_london_low'] / n * 100
        
        print(f"{combo} ({n} days)")
        print(f"  NY1 Status: Long={ny1_l:.1f}%, Short={ny1_s:.1f}%")
        print(f"  NY1 Broken: {ny1_b:.1f}%")
        print(f"  NY Breaks London: High={break_h:.1f}%, Low={break_l:.1f}%")
        
        # Interpretation
        if ny1_b > 55:
            print(f"  ⚡ HIGH VOLATILITY (NY range often broken)")
        elif ny1_b < 40:
            print(f"  📉 LOW VOLATILITY (NY range usually holds)")
        print()


if __name__ == "__main__":
    print("Loading Profiler Data...")
    daily = load_profiler_data()
    print(f"Loaded {len(daily)} trading days.\n")
    
    # Analysis 1: ALN Patterns (Profiler Status)
    aln_results = analyze_by_aln_pattern(daily)
    print_aln_results(aln_results)
    
    # Analysis 2: Status Combos
    combo_results = analyze_by_status_combo(daily)
    print_combo_results(combo_results)
    
    # Analysis 3: London Range Breaks (NQStats Validation)
    london_break_results = analyze_london_break(daily)
    print_london_break_results(london_break_results)
    
    # Analysis 4: Broken Status Combos
    broken_results = analyze_by_broken_status(daily)
    print_broken_results(broken_results)
