"""
Unified Bias Algorithm Analysis
================================
Combines ALN + Profiler + ICT Daily Profiles to predict NY AM/PM bias and targets.

Output:
1. ICT Daily Profile classification
2. Cross-reference of ALN × Broken × ICT Profile
3. Highest probability combinations for NY AM/PM bias
"""

import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
PROFILER_FILE = DATA_DIR / "NQ1_profiler.json"
HOD_LOD_FILE = DATA_DIR / "NQ1_daily_hod_lod.json"


def load_data():
    """Load profiler JSON and HOD/LOD data, group by date."""
    with open(PROFILER_FILE) as f:
        profiler_data = json.load(f)
    
    with open(HOD_LOD_FILE) as f:
        hod_lod_data = json.load(f)
    
    # Group profiler by date
    daily = defaultdict(dict)
    for record in profiler_data:
        date = record['date']
        session = record['session']
        daily[date][session] = record
    
    # Merge HOD/LOD data
    for date, hod_lod in hod_lod_data.items():
        if date in daily:
            daily[date]['hod_lod'] = hod_lod
    
    return daily


def parse_time(time_str):
    """Parse time string like '09:35' to hour decimal (9.58)."""
    if not time_str:
        return None
    try:
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return hour + minute / 60
    except:
        return None


def classify_ict_profile(hod_lod: dict) -> str:
    """
    Classify the ICT Daily Profile based on when high/low occurred.
    Uses actual HOD/LOD timestamp data.
    
    Classic Buy: Low early (AM), High late (PM)
    Classic Sell: High early (AM), Low late (PM)
    Seek & Destroy: Both form mid-session
    Neutral: No clear pattern
    """
    if not hod_lod:
        return 'Unknown'
    
    hod_time = parse_time(hod_lod.get('hod_time'))
    lod_time = parse_time(hod_lod.get('lod_time'))
    
    if hod_time is None or lod_time is None:
        return 'Unknown'
    
    # Define session boundaries (NY Time)
    # AM = 09:30 - 12:00, PM = 12:00 - 16:00
    AM_END = 12.0
    NY_OPEN = 9.5  # 09:30
    
    # Classic Buy: Low in AM (before 12:00), High in PM (after 12:00)
    if lod_time < AM_END and hod_time >= AM_END:
        return 'Classic Buy'
    
    # Classic Sell: High in AM (before 12:00), Low in PM (after 12:00)
    if hod_time < AM_END and lod_time >= AM_END:
        return 'Classic Sell'
    
    # Seek & Destroy: Both in overlapping NY session window (10:00-14:00)
    if 10.0 <= hod_time <= 14.0 and 10.0 <= lod_time <= 14.0:
        return 'Seek & Destroy'
    
    # Neutral: Both in AM or both in PM, or pre-market
    return 'Neutral'


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
    
    if london_h > asia_h and london_l < asia_l:
        return 'LEA'
    if london_h > asia_h and london_l >= asia_l:
        return 'LPEU'
    if london_l < asia_l and london_h <= asia_h:
        return 'LPED'
    return 'AEL'


def get_broken_status(asia: dict, london: dict) -> str:
    """Get broken status combo."""
    if not asia or not london:
        return 'Unknown'
    
    a_b = 'Broken' if asia.get('broken', False) else 'Held'
    l_b = 'Broken' if london.get('broken', False) else 'Held'
    return f"{a_b}/{l_b}"


def get_status_combo(asia: dict, london: dict) -> str:
    """Get status combo (Long/Short)."""
    if not asia or not london:
        return 'Unknown'
    
    asia_status = asia.get('status', 'None')
    london_status = london.get('status', 'None')
    
    asia_s = 'L' if 'Long' in asia_status else ('S' if 'Short' in asia_status else 'N')
    london_s = 'L' if 'Long' in london_status else ('S' if 'Short' in london_status else 'N')
    
    return f"{asia_s}/{london_s}"


def analyze_unified(daily: dict):
    """
    Analyze all combinations of ALN + Broken + ICT Profile.
    """
    results = defaultdict(lambda: {
        'count': 0,
        'ny1_long': 0, 'ny1_short': 0,
        'ny2_long': 0, 'ny2_short': 0,
        'classic_buy': 0, 'classic_sell': 0,
    })
    
    ict_dist = defaultdict(int)  # ICT profile distribution
    
    for date, sessions in daily.items():
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        ny2 = sessions.get('NY2')
        
        if not all([asia, london, ny1]):
            continue
        
        # Classifications
        aln = classify_aln(asia, london)
        broken = get_broken_status(asia, london)
        status = get_status_combo(asia, london)
        ict = classify_ict_profile(sessions.get('hod_lod'))
        
        if aln == 'Unknown' or ict == 'Unknown':
            continue
        
        ict_dist[ict] += 1
        
        # Create combo key: ALN + Broken + Status
        combo = f"{aln} | {broken} | {status}"
        results[combo]['count'] += 1
        
        # NY1 outcomes
        ny1_status = ny1.get('status', 'None')
        if ny1_status == 'Long True':
            results[combo]['ny1_long'] += 1
        elif ny1_status == 'Short True':
            results[combo]['ny1_short'] += 1
        
        # NY2 outcomes
        if ny2:
            ny2_status = ny2.get('status', 'None')
            if ny2_status == 'Long True':
                results[combo]['ny2_long'] += 1
            elif ny2_status == 'Short True':
                results[combo]['ny2_short'] += 1
        
        # ICT Profile
        if ict == 'Classic Buy':
            results[combo]['classic_buy'] += 1
        elif ict == 'Classic Sell':
            results[combo]['classic_sell'] += 1
    
    return dict(results), dict(ict_dist)


def find_best_setups(results: dict, min_count: int = 100):
    """
    Find highest probability setups for NY AM Long and Short.
    """
    long_setups = []
    short_setups = []
    
    for combo, r in results.items():
        n = r['count']
        if n < min_count:
            continue
        
        ny1_long_pct = r['ny1_long'] / n * 100
        ny1_short_pct = r['ny1_short'] / n * 100
        ny2_long_pct = r['ny2_long'] / n * 100 if r['ny2_long'] else 0
        ny2_short_pct = r['ny2_short'] / n * 100 if r['ny2_short'] else 0
        classic_buy_pct = r['classic_buy'] / n * 100
        classic_sell_pct = r['classic_sell'] / n * 100
        
        long_setups.append({
            'combo': combo,
            'count': n,
            'ny1_long': ny1_long_pct,
            'ny1_short': ny1_short_pct,
            'ny2_long': ny2_long_pct,
            'classic_buy': classic_buy_pct,
        })
        
        short_setups.append({
            'combo': combo,
            'count': n,
            'ny1_short': ny1_short_pct,
            'ny1_long': ny1_long_pct,
            'ny2_short': ny2_short_pct,
            'classic_sell': classic_sell_pct,
        })
    
    # Sort by NY1 Long % for long setups
    long_setups.sort(key=lambda x: x['ny1_long'], reverse=True)
    # Sort by NY1 Short % for short setups
    short_setups.sort(key=lambda x: x['ny1_short'], reverse=True)
    
    return long_setups, short_setups


def print_results(results: dict, ict_dist: dict):
    """Print analysis results."""
    print("\n" + "="*70)
    print("ICT DAILY PROFILE DISTRIBUTION")
    print("="*70)
    total = sum(ict_dist.values())
    for profile in ['Classic Buy', 'Classic Sell', 'Seek & Destroy', 'Neutral']:
        count = ict_dist.get(profile, 0)
        pct = count / total * 100 if total > 0 else 0
        print(f"  {profile}: {count} days ({pct:.1f}%)")
    
    print("\n" + "="*70)
    print("TOP 10 BULLISH SETUPS (Highest NY1 Long %)")
    print("="*70)
    long_setups, short_setups = find_best_setups(results)
    
    for i, setup in enumerate(long_setups[:10], 1):
        print(f"\n{i}. {setup['combo']}")
        print(f"   Days: {setup['count']}")
        print(f"   NY AM: Long={setup['ny1_long']:.1f}%, Short={setup['ny1_short']:.1f}%")
        print(f"   NY PM: Long={setup['ny2_long']:.1f}%")
        print(f"   Classic Buy Days: {setup['classic_buy']:.1f}%")
    
    print("\n" + "="*70)
    print("TOP 10 BEARISH SETUPS (Highest NY1 Short %)")
    print("="*70)
    
    for i, setup in enumerate(short_setups[:10], 1):
        print(f"\n{i}. {setup['combo']}")
        print(f"   Days: {setup['count']}")
        print(f"   NY AM: Short={setup['ny1_short']:.1f}%, Long={setup['ny1_long']:.1f}%")
        print(f"   NY PM: Short={setup['ny2_short']:.1f}%")
        print(f"   Classic Sell Days: {setup['classic_sell']:.1f}%")


if __name__ == "__main__":
    print("Loading Profiler + HOD/LOD Data...")
    daily = load_data()
    print(f"Loaded {len(daily)} trading days.\n")
    
    # Unified Analysis
    results, ict_dist = analyze_unified(daily)
    print_results(results, ict_dist)
