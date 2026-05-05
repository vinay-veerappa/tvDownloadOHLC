"""
NQStats Profiler Module - Statistical Aggregation for Daily Profiling.
Implements the core logic for filtering and generating conditional probabilities.
Matches Institutional Web UI standards for Ranges and Level Reach.
"""

import os
import json
import pandas as pd
import numpy as np
from collections import defaultdict

# Standard session boxes for reach verification (matching manual tester)
PROFILER_BOX_CONFIG = {
    'Asia': {'start': '18:00', 'end': '19:30'},
    'London': {'start': '02:30', 'end': '03:30'},
    'NY1': {'start': '07:30', 'end': '08:30'},
    'NY2': {'start': '11:15', 'end': '12:15'}
}

def calculate_time_range(times, bucket_mins=15):
    """
    Standard UI Logic: Range = Mode to Mode + bucket_mins.
    """
    if not times: return "-"
    
    buckets = {}
    for t in times:
        if not t or ":" not in t: continue
        try:
            h, m = map(int, t.split(':')[:2])
            total_mins = h * 60 + m
            b_start = (total_mins // bucket_mins) * bucket_mins
            b_str = f"{b_start//60:02d}:{b_start%60:02d}"
            buckets[b_str] = buckets.get(b_str, 0) + 1
        except: continue
            
    if not buckets: return "-"
    
    # Find Mode
    sorted_buckets = sorted(buckets.items(), key=lambda x: x[1], reverse=True)
    mode_start = sorted_buckets[0][0]
    
    h, m = map(int, mode_start.split(':'))
    start_total = h * 60 + m
    end_total = start_total + bucket_mins
    mode_end = f"{(end_total//60)%24:02d}:{end_total%60:02d}"
    
    return f"{mode_start}-{mode_end}"

def calculate_price_range(values, bucket_size=0.1):
    """
    Standard UI Logic: Range = min(Mode, Median) to max(Mode, Median).
    """
    if not values: return "-"
    
    vals = [v for v in values if v is not None and not np.isnan(v)]
    if not vals: return "-"
    
    clamped = np.clip(vals, -5.0, 5.0)
    
    buckets = {}
    for v in clamped:
        b = (np.floor(v / bucket_size) * bucket_size)
        b_str = f"{b:.1f}"
        buckets[b_str] = buckets.get(b_str, 0) + 1
    
    mode_val = float(sorted(buckets.items(), key=lambda x: x[1], reverse=True)[0][0])
    median_val = np.median(clamped)
    median_bucket = np.floor(median_val / bucket_size) * bucket_size
    
    start = min(mode_val, median_bucket)
    end = max(mode_val, median_bucket)
    
    return f"{start:.1f} to {end:.1f}%"

class ProfilerAnalyzer:
    """
    Core library class for analyzing historical profiler data.
    Decouples calculation logic from display scripts.
    """
    def __init__(self, ticker, base_path):
        self.ticker = ticker
        self.base_path = base_path
        self.profiler_data = self._load_json("profiler")
        self.touch_data = self._load_json("level_touches")
        self.shorthand_map = {'Long True': 'LT', 'Short True': 'ST', 'Long False': 'LF', 'Short False': 'SF'}

    def _load_json(self, suffix):
        clean_ticker = self.ticker.replace("-", "").replace("/", "")
        names = [f"{clean_ticker}1_{suffix}.json", f"{clean_ticker}_{suffix}.json"]
        for name in names:
            path = os.path.join(self.base_path, name)
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)
        return None

    def get_briefing(self, target_session, filters):
        """
        Calculates all briefing metrics for matching days.
        """
        if self.profiler_data is None:
            return None

        # Group by date
        days = defaultdict(dict)
        for row in self.profiler_data:
            days[row['date']][row['session']] = row

        matches = []
        for date, sessions in days.items():
            if target_session not in sessions: continue
                
            is_match = True
            for key, val in filters.items():
                if "_broken" in key:
                    sess_name = key.split('_')[0]
                    if sess_name not in sessions:
                        is_match = False; break
                    actual_broken = sessions[sess_name].get('broken', False)
                    if isinstance(actual_broken, str): actual_broken = "Broken" in actual_broken
                    if actual_broken != val:
                        is_match = False; break
                else:
                    if key not in sessions:
                        is_match = False; break
                    actual_status = self.shorthand_map.get(sessions[key]['status'], sessions[key]['status'])
                    if actual_status != val:
                        is_match = False; break
            
            if is_match:
                m = sessions[target_session].copy()
                m['touches'] = {}
                if self.touch_data and date in self.touch_data:
                    day_touches = self.touch_data[date]
                    start_str = m.get('start_time', "").split('T')[-1][:5] if 'T' in m.get('start_time', "") else ""
                    end_str = m.get('end_time', "").split('T')[-1][:5] if 'T' in m.get('end_time', "") else ""
                    
                    if not start_str:
                        start_str = PROFILER_BOX_CONFIG.get(target_session, {}).get('start', '')
                        end_str = PROFILER_BOX_CONFIG.get(target_session, {}).get('end', '')

                    for lvl_key in ['pdh', 'pdl', 'pdm', 'midnight_open', 'open_0730', 'p12h', 'p12m', 'p12l']:
                        info = day_touches.get(lvl_key, {})
                        if not isinstance(info, dict) or 'touch_times' not in info: continue
                        hit = False
                        for t in info['touch_times']:
                            if start_str <= t <= end_str:
                                hit = True; break
                        m['touches'][lvl_key] = hit
                matches.append(m)

        if not matches:
            return None

        # Calculate Aggregate Stats
        total = len(matches)
        outcome_groups = defaultdict(list)
        for m in matches:
            outcome_groups[m['status']].append(m)

        summary_rows = []
        rank = {'Long True': 1, 'Short True': 2, 'Long False': 3, 'Short False': 4}
        sorted_outcomes = sorted(outcome_groups.keys(), key=lambda x: rank.get(x, 99))
        lvl_keys = ['pdh', 'pdl', 'pdm', 'midnight_open', 'open_0730', 'p12h', 'p12m', 'p12l']

        for outcome in sorted_outcomes:
            subset = outcome_groups[outcome]
            count = len(subset)
            pct = (count / total) * 100

            lod_times = [s.get('low_time') for s in subset if s.get('low_time')]
            hod_times = [s.get('high_time') for s in subset if s.get('high_time')]
            lod_dists = [s.get('low_pct', 0) for s in subset]
            hod_dists = [s.get('high_pct', 0) for s in subset]

            reach_pcts = {}
            for l_key in lvl_keys:
                hits = sum(1 for s in subset if s.get('touches', {}).get(l_key, False))
                reach_pcts[l_key] = (hits / count * 100)

            summary_rows.append({
                'outcome': outcome,
                'pct': pct,
                'count': count,
                'lod_time_range': calculate_time_range(lod_times),
                'hod_time_range': calculate_time_range(hod_times),
                'lod_dist_range': calculate_price_range(lod_dists),
                'hod_dist_range': calculate_price_range(hod_dists),
                'rev_pct': (sum(1 for s in subset if s.get('broken', False)) / count * 100) if count > 0 else 0,
                'reach_pcts': reach_pcts,
                'raw_subset': subset
            })

        return {
            'total_matches': total,
            'outcomes': summary_rows
        }

def calculate_touch_matrix(df_1m: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """
    Kept for backward compatibility with live processing scripts.
    Checks per-minute level touches.
    """
    level_cols = ['pdh', 'pdl', 'pdm', 'settle', 'open_glob', 'open_mid', 'open_0730', 'p12h', 'p12m', 'p12l']
    level_cols = [c for c in level_cols if c in stats.columns]
    
    low_vals = df_1m['low'].values
    high_vals = df_1m['high'].values
    touch_matrix = pd.DataFrame(index=df_1m.index)
    
    for lvl in level_cols:
        l_vals = stats[lvl].values
        touch_matrix[f'touch_{lvl}'] = (low_vals <= l_vals) & (high_vals >= l_vals)
        
    return touch_matrix
