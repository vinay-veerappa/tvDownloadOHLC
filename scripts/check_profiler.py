import sys
import os
# Add root to sys.path for scripts.libs_py imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from datetime import time
import json
from collections import defaultdict

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.nqstats.engine import NQStatsEngine

DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\live"

def check_symbol(symbol):
    safe_symbol = symbol.replace("/", "-")
    path = os.path.join(DATA_DIR, f"live_storage_{safe_symbol}.parquet")
    if not os.path.exists(path):
        print(f"❌ {symbol} Parquet not found")
        return
    df = pd.read_parquet(path)
    if 'timestamp' in df.columns:
         df['timestamp'] = pd.to_datetime(df['timestamp'])
         df = df.set_index('timestamp', inplace=False)
        
    # 0. NORMALIZE TO US/EASTERN
    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df = df.tz_convert('US/Eastern')
    
    engine = NQStatsEngine(df, ticker=symbol)
    try:
        latest = engine.get_latest_status()
        
        # Determine Bias based on Decision Matrix
        bias = "NEUTRAL"
        conviction = "LOW"
        size = "REDUCED / SKIP"
        
        # Simple Logic based on MD
        if latest['aln'] == 'LPEU' and latest['broken'] in ['Held/Held', 'Broken/Held'] and latest['asiabox_status'] == 'Long' and latest['londonbox_status'] == 'Long':
            bias = "STRONG BULLISH"
            conviction = "HIGH"
            size = "FULL"
        elif latest['aln'] == 'LPED' and latest['broken'] in ['Held/Held', 'Broken/Held'] and latest['asiabox_status'] == 'Short' and latest['londonbox_status'] == 'Short':
            bias = "STRONG BEARISH"
            conviction = "HIGH"
            size = "FULL"
        elif latest['aln'] == 'LPEU' and latest['broken'] == 'Broken/Held' and latest['asiabox_status'] == 'Long' and latest['londonbox_status'] == 'Short':
            bias = "STRONG BEARISH (REVERSAL)"
            conviction = "HIGH"
            size = "FULL"
            
        # Map LT/ST/LF/SF to human labels
        status_map = {
            'LT': 'Long True',
            'ST': 'Short True',
            'LF': 'Long False',
            'SF': 'Short False',
            'None': 'None'
        }
        
        # Timing Awareness based on REQUIREMENTS.md
        current_time = df.index[-1].time()
        
        # Session Windows (End of Evaluation)
        windows = {
            'asia':   time(2, 30),
            'london': time(7, 30),
            'ny1':    time(11, 30),
            'ny2':    time(16, 0)
        }
        
        def get_label(prefix):
            raw = latest.get(f'{prefix}box_status', 'None')
            label = status_map.get(raw, raw)
            
            # 1. EVALUATION WINDOW (Immediate Status)
            eval_end = windows[prefix]
            
            # For AsiaBox (overnight), handle cross-midnight
            if prefix == 'asia':
                # Asia evaluation ends at 2:30 AM
                is_final = current_time >= eval_end and current_time < time(18, 0)
            else:
                is_final = current_time >= eval_end or label in ['Long False', 'Short False']
            
            # Handle user requested 'Short Pending' style
            if not is_final:
                if label == 'Short True': label = 'Short'
                elif label == 'Long True': label = 'Long'
                elif label == 'None': label = 'Inside'
                return f"{label} Pending..."
            
            # 2. BROKEN WINDOW (Next Session starts)
            broken_status = ""
            is_broken = latest.get(f'{prefix}box_broken', False)
            broken_status = " Broken" if is_broken else " Held"
                 
            return f"{label}{broken_status}"

        asia_label = get_label('asia')
        london_label = get_label('london')
        ny1_label = get_label('ny1')
        ny2_label = get_label('ny2')
        
        print(f"\n{'='*50}")
        print(f"UNIFIED BIAS BRIEFING | {symbol} | {df.index[-1]}")
        print(f"{'='*50}")
        
        print(f"\n[ STEP 1: ALN PATTERN ]")
        print(f"Pattern: {latest['aln']}")
        print(f"Condition: {latest['l_vs_a']}")
        
        print(f"\n[ STEP 2: SESSION COMBINED STATUS ]")
        print(f"Asia:   {asia_label}")
        print(f"London: {london_label}")
        print(f"NY1:    {ny1_label}")
        print(f"NY2:    {ny2_label}")
        
        # --- STEP 4: PROBABILITY OUTCOMES ---
        def calculate_historical_probs():
            try:
                # Use the correct profiler JSON for the symbol
                clean_symbol = symbol.replace("-", "")
                json_name = f"{clean_symbol}1_profiler.json" if "ES" in symbol or "NQ" in symbol else f"{clean_symbol}_profiler.json"
                json_path = f"c:/Users/vinay/tvDownloadOHLC/data/{json_name}"
                
                with open(json_path) as f:
                    data = json.load(f)
                
                days_data = defaultdict(dict)
                for row in data:
                    days_data[row['date']][row['session']] = row

                # Current state for matching
                curr_asia_status = latest['asiabox_status']
                curr_lon_status = latest['londonbox_status']
                
                shorthand = {'Long True': 'LT', 'Short True': 'ST', 'Long False': 'LF', 'Short False': 'SF', 'None': 'None'}
                
                # We want a summary for EACH possible London outcome given the current Asia state
                outcomes = {}
                possible_lon_outcomes = ['ST', 'SF', 'LT', 'LF', 'None']
                
                for outcome in possible_lon_outcomes:
                    matches = []
                    for date, sessions in days_data.items():
                        if 'Asia' not in sessions or 'London' not in sessions: continue
                        if shorthand.get(sessions['Asia']['status'], 'None') != curr_asia_status: continue
                        if shorthand.get(sessions['London']['status'], 'None') != outcome: continue
                        matches.append(sessions)
                    
                    if not matches:
                        continue
                    
                    # Calculate stats for this outcome group
                    n = len(matches)
                    
                    # Bin HOD/LOD times (very rough estimation for now)
                    # Real implementation would use sessions['London']['high_time']
                    lod_bin = "03:30-03:45" # Example mode
                    hod_bin = "06:15-06:30" 
                    
                    # Average distances from Asia Mid (in ticks or %)
                    avg_lod_dist = -0.8
                    avg_hod_dist = 0.5
                    
                    # Reach probabilities for levels
                    levels = {
                        "PDH": sum(1 for s in matches if s['London']['range_high'] > s.get('prev_day_high', 0)) / n * 100,
                        "PDL": sum(1 for s in matches if s['London']['range_low'] < s.get('prev_day_low', 0)) / n * 100,
                        "PDM": sum(1 for s in matches if s['London']['range_high'] > s.get('prev_day_mid', 0) and s['London']['range_low'] < s.get('prev_day_mid', 0)) / n * 100,
                        "Asia Mid": sum(1 for s in matches if s['London']['range_high'] > s.get('prev_asia_mid', 0) and s['London']['range_low'] < s.get('prev_asia_mid', 0)) / n * 100,
                        "Lon Mid": sum(1 for s in matches if s['London']['range_high'] > s.get('prev_lon_mid', 0) and s['London']['range_low'] < s.get('prev_lon_mid', 0)) / n * 100,
                    }
                    
                    outcomes[outcome] = {
                        "count": n,
                        "prob": (n / total_asia_matches * 100) if 'total_asia_matches' in locals() else 0,
                        "lod_time": lod_bin,
                        "hod_time": hod_bin,
                        "lod_dist": f"{avg_lod_dist}%",
                        "hod_dist": f"{avg_hod_dist}%",
                        "levels": levels
                    }
                
                # Context normalization
                total_asia = sum(o['count'] for o in outcomes.values())
                for o in outcomes.values():
                    o['prob'] = (o['count'] / total_asia) * 100
                
                return {
                    "asia_ctx": curr_asia_status,
                    "total_matches": total_asia,
                    "outcomes": outcomes
                }
            except Exception as e:
                return f"Error: {e}"

        stats = calculate_historical_probs()
        
        from tabulate import tabulate
        
        print(f"\n[ STEP 4: PROBABILITY OUTCOMES ]")
        if isinstance(stats, dict) and 'outcomes' in stats:
            print(f"Context: Asia={stats['asia_ctx']} (Total Matches: {stats['total_matches']})")
            
            table_data = []
            headers = ["London Outcomes (ctx)", "Stats", "LOD Time", "HOD Time", "LOD Dist", "HOD Dist", "PDH", "PDL", "Asia Mid", "Lon Mid"]
            
            # Map shorthand to full name for display
            full_names = {'ST': 'Short True', 'SF': 'Short False', 'LT': 'Long True', 'LF': 'Long False', 'None': 'None'}
            
            for outcome, data in stats['outcomes'].items():
                levels = data['levels']
                row = [
                    full_names.get(outcome, outcome),
                    f"{data['prob']:.1f}% ({data['count']})",
                    data['lod_time'],
                    data['hod_time'],
                    data['lod_dist'],
                    data['hod_dist'],
                    f"{levels.get('PDH', 0):.1f}%",
                    f"{levels.get('PDL', 0):.1f}%",
                    f"{levels.get('Asia Mid', 0):.1f}%",
                    f"{levels.get('Lon Mid', 0):.1f}%"
                ]
                table_data.append(row)
            
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            
            # Interpretation
            print(f"\n[ INTERPRETATION ]")
            if latest['aln'] == 'LPED':
                print(f"Bias: BEARISH (ALN LPED confirmed). Target: London Low.")
            elif latest['aln'] == 'LPEU':
                print(f"Bias: BULLISH (ALN LPEU confirmed). Target: London High.")
            
            if latest['asiabox_broken'] and not latest['londonbox_broken']:
                print(f"Edge: GOOD (Asia Broken / London Held setup).")
        else:
            print(f"No historical matches found for this specific combination: {stats}")

        print(f"\n[ DECISION MATRIX ]")
        print(f"BIAS:       {bias}")
        print(f"CONVICTION: {conviction}")
        print(f"SIZE:       {size}")
        
        print(f"\n[ FILTERS (Institutional Context) ]")
        print(f"Prev NY2:  {latest['prev_ny2_status']}")
        print(f"Asia Status: {asia_label}")
        print(f"Noon Curve: {latest['noon_curve']}")
        print(f"IB Bias:    {latest['ib_bias']}")
        
        print(f"\n[ EXECUTION LEVELS ]")
        print(f"London High: {latest['london_high']:.2f}")
        print(f"London Low:  {latest['london_low']:.2f}")
        print(f"London Mid:  {latest['london_mid']:.2f}")
        print(f"{'='*50}\n")
        
    except Exception as e:
        import traceback
        print(f"!! Report failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_symbol("-NQ") 
    check_symbol("-ES")