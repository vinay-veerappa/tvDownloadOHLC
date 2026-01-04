"""
Multi-Ticker Unified Bias Validation
=====================================
Validates the ALN + Profiler + ICT bias algorithm across ES, RTY, YM, NQ.

Output:
1. Per-ticker setup performance
2. Cross-ticker comparison
3. Overall algorithm accuracy metrics
"""

import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# --- CONFIG ---
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TICKERS = ['ES1', 'RTY1', 'YM1', 'NQ1']


def load_data(ticker: str):
    """Load profiler JSON and HOD/LOD data for a ticker."""
    profiler_file = DATA_DIR / f"{ticker}_profiler.json"
    hod_lod_file = DATA_DIR / f"{ticker}_daily_hod_lod.json"
    
    if not profiler_file.exists() or not hod_lod_file.exists():
        print(f"  ⚠️ Missing data for {ticker}")
        return {}
    
    with open(profiler_file) as f:
        profiler_data = json.load(f)
    
    with open(hod_lod_file) as f:
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
    """Parse time string like '09:35' to hour decimal."""
    if not time_str:
        return None
    try:
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return hour + minute / 60
    except:
        return None


def classify_aln(asia: dict, london: dict) -> str:
    """Classify ALN pattern."""
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


def classify_ict_profile(hod_lod: dict) -> str:
    """Classify ICT Daily Profile."""
    if not hod_lod:
        return 'Unknown'
    
    hod_time = parse_time(hod_lod.get('hod_time'))
    lod_time = parse_time(hod_lod.get('lod_time'))
    
    if hod_time is None or lod_time is None:
        return 'Unknown'
    
    AM_END = 12.0
    
    if lod_time < AM_END and hod_time >= AM_END:
        return 'Classic Buy'
    if hod_time < AM_END and lod_time >= AM_END:
        return 'Classic Sell'
    if 10.0 <= hod_time <= 14.0 and 10.0 <= lod_time <= 14.0:
        return 'Seek & Destroy'
    return 'Neutral'


def predict_bias(aln: str, broken: str, status: str) -> str:
    """
    Predict bias based on the unified algorithm.
    Returns: 'LONG', 'SHORT', or 'NEUTRAL'
    """
    # GOLD LONG: LPEU + Held/Held + L/L
    if aln == 'LPEU' and (broken == 'Held/Held' or broken == 'Broken/Held') and status == 'L/L':
        return 'LONG'
    
    # GOLD SHORT: LPEU + Broken/Held + L/S
    if aln == 'LPEU' and broken == 'Broken/Held' and status == 'L/S':
        return 'SHORT'
    
    # Bullish ALN patterns
    if aln == 'LPEU' and broken != 'Broken/Broken':
        return 'LONG'
    
    # Bearish ALN patterns
    if aln == 'LPED' and broken != 'Broken/Broken':
        return 'SHORT'
    
    # Default neutral
    return 'NEUTRAL'


def get_actual_bias(ny1: dict) -> str:
    """Get actual NY1 bias from Profiler status."""
    if not ny1:
        return 'NEUTRAL'
    
    status = ny1.get('status', 'None')
    if status == 'Long True':
        return 'LONG'
    elif status == 'Short True':
        return 'SHORT'
    return 'NEUTRAL'


def get_ict_bias(ict_profile: str) -> str:
    """Get bias from ICT daily profile."""
    if ict_profile == 'Classic Buy':
        return 'LONG'
    elif ict_profile == 'Classic Sell':
        return 'SHORT'
    return 'NEUTRAL'


def analyze_ticker(ticker: str, daily: dict):
    """Analyze a single ticker."""
    results = {
        'total': 0,
        'algo_long': 0, 'algo_short': 0, 'algo_neutral': 0,
        'actual_long': 0, 'actual_short': 0, 'actual_neutral': 0,
        'correct_long': 0, 'correct_short': 0,
        'ict_classic_buy': 0, 'ict_classic_sell': 0,
    }
    
    for date, sessions in daily.items():
        asia = sessions.get('Asia')
        london = sessions.get('London')
        ny1 = sessions.get('NY1')
        hod_lod = sessions.get('hod_lod')
        
        if not all([asia, london, ny1, hod_lod]):
            continue
        
        aln = classify_aln(asia, london)
        broken = get_broken_status(asia, london)
        status = get_status_combo(asia, london)
        ict = classify_ict_profile(hod_lod)
        
        if aln == 'Unknown':
            continue
        
        results['total'] += 1
        
        # Predicted bias
        predicted = predict_bias(aln, broken, status)
        actual = get_actual_bias(ny1)
        
        # Count predictions
        if predicted == 'LONG':
            results['algo_long'] += 1
        elif predicted == 'SHORT':
            results['algo_short'] += 1
        else:
            results['algo_neutral'] += 1
        
        # Count actual
        if actual == 'LONG':
            results['actual_long'] += 1
        elif actual == 'SHORT':
            results['actual_short'] += 1
        else:
            results['actual_neutral'] += 1
        
        # Count correct predictions
        if predicted == 'LONG' and actual == 'LONG':
            results['correct_long'] += 1
        if predicted == 'SHORT' and actual == 'SHORT':
            results['correct_short'] += 1
        
        # ICT profiles
        if ict == 'Classic Buy':
            results['ict_classic_buy'] += 1
        elif ict == 'Classic Sell':
            results['ict_classic_sell'] += 1
    
    return results


def print_results(all_results: dict):
    """Print validation results."""
    print("\n" + "="*80)
    print("MULTI-TICKER UNIFIED BIAS VALIDATION REPORT")
    print("="*80)
    
    print("\n{:<8} {:>8} {:>10} {:>10} {:>10} {:>12} {:>12}".format(
        "Ticker", "Days", "Algo Long", "Algo Short", "Algo Neut", "Long Acc%", "Short Acc%"
    ))
    print("-"*80)
    
    for ticker, r in all_results.items():
        n = r['total']
        if n == 0:
            continue
        
        algo_long = r['algo_long']
        algo_short = r['algo_short']
        algo_neutral = r['algo_neutral']
        
        # Accuracy = correct / predicted (when we predicted something)
        long_acc = (r['correct_long'] / algo_long * 100) if algo_long > 0 else 0
        short_acc = (r['correct_short'] / algo_short * 100) if algo_short > 0 else 0
        
        print("{:<8} {:>8} {:>10} {:>10} {:>10} {:>11.1f}% {:>11.1f}%".format(
            ticker, n, algo_long, algo_short, algo_neutral, long_acc, short_acc
        ))
    
    print("\n" + "="*80)
    print("ICT DAILY PROFILE DISTRIBUTION")
    print("="*80)
    
    print("\n{:<8} {:>10} {:>12} {:>12}".format(
        "Ticker", "Days", "Classic Buy%", "Classic Sell%"
    ))
    print("-"*50)
    
    for ticker, r in all_results.items():
        n = r['total']
        if n == 0:
            continue
        
        cb = r['ict_classic_buy'] / n * 100
        cs = r['ict_classic_sell'] / n * 100
        
        print("{:<8} {:>10} {:>11.1f}% {:>11.1f}%".format(ticker, n, cb, cs))


def generate_report(all_results: dict) -> str:
    """Generate markdown report."""
    lines = [
        "# Multi-Ticker Unified Bias Validation Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Tickers Analyzed**: {', '.join(TICKERS)}",
        "",
        "---",
        "",
        "## Algorithm Accuracy by Ticker",
        "",
        "| Ticker | Days | Algo Long | Algo Short | Long Accuracy | Short Accuracy |",
        "|--------|------|-----------|------------|---------------|----------------|",
    ]
    
    for ticker, r in all_results.items():
        n = r['total']
        if n == 0:
            continue
        
        long_acc = (r['correct_long'] / r['algo_long'] * 100) if r['algo_long'] > 0 else 0
        short_acc = (r['correct_short'] / r['algo_short'] * 100) if r['algo_short'] > 0 else 0
        
        lines.append(f"| {ticker} | {n} | {r['algo_long']} | {r['algo_short']} | {long_acc:.1f}% | {short_acc:.1f}% |")
    
    lines += [
        "",
        "---",
        "",
        "## ICT Daily Profile Distribution",
        "",
        "| Ticker | Classic Buy | Classic Sell | Neutral |",
        "|--------|-------------|--------------|---------|",
    ]
    
    for ticker, r in all_results.items():
        n = r['total']
        if n == 0:
            continue
        
        cb = r['ict_classic_buy'] / n * 100
        cs = r['ict_classic_sell'] / n * 100
        neutral = 100 - cb - cs
        
        lines.append(f"| {ticker} | {cb:.1f}% | {cs:.1f}% | {neutral:.1f}% |")
    
    lines += [
        "",
        "---",
        "",
        "## Key Findings",
        "",
        "*(Summary will be filled after analysis)*",
    ]
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("="*80)
    print("MULTI-TICKER UNIFIED BIAS VALIDATION")
    print("="*80)
    
    all_results = {}
    
    for ticker in TICKERS:
        print(f"\nLoading {ticker}...")
        daily = load_data(ticker)
        print(f"  Loaded {len(daily)} trading days.")
        
        results = analyze_ticker(ticker, daily)
        all_results[ticker] = results
    
    print_results(all_results)
    
    # Generate and save report
    report = generate_report(all_results)
    report_file = Path(__file__).parent.parent.parent.parent / "docs" / "nqstats" / "BIAS_VALIDATION_REPORT.md"
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"\n✅ Report saved to: {report_file}")
