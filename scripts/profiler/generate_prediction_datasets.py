import json
import os
import pandas as pd
from collections import defaultdict

# --- CONFIG ---
PROFILER_PATH = r"data/NQ1_profiler.json"
UNADJUSTED_PATH = r"data/NQ1_daily_hod_lod_unadjusted.json"
ASIA_OUTPUT_PATH = r"data/NQ1_asia_predictions.json"
LONDON_OUTPUT_PATH = r"data/NQ1_london_predictions.json"

def load_data():
    print("Loading Profiler Data...")
    with open(PROFILER_PATH, 'r') as f:
        profiler_data = json.load(f)
    
    print("Loading Unadjusted Daily Data...")
    with open(UNADJUSTED_PATH, 'r') as f:
        unadjusted_data = json.load(f)
        
    df = pd.DataFrame(profiler_data)
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort by date/time to ensure session order
    df = df.sort_values(by='start_ts')
    return df, unadjusted_data

def get_session_status(df, target_date, session_name):
    # Find specific session for a date
    row = df[(df['date'] == target_date) & (df['session'] == session_name)]
    if row.empty:
        return None
    return row.iloc[0]['status']

def safe_divide(n, d):
    return n / d if d > 0 else 0

def generate_predictions():
    df, unadjusted = load_data()
    unique_dates = df['date'].unique()
    
    # Containers
    # Key: "ContextString" (e.g. "NY1:LT|NY2:SF")
    # Value: List of outcomes (status strings)
    asia_outcomes = defaultdict(list)
    london_outcomes = defaultdict(list)
    
    print(f"Processing {len(unique_dates)} days...")
    
    for i, current_date in enumerate(unique_dates):
        if i == 0: continue # Skip first day (no context)
        
        prev_date = unique_dates[i-1]
        
        # --- 1. ASIA PREDICTION (Context: Prev NY1, Prev NY2) ---
        # Get Context
        p_ny1 = get_session_status(df, prev_date, 'NY1')
        p_ny2 = get_session_status(df, prev_date, 'NY2')
        
        # Get Target
        curr_asia = get_session_status(df, current_date, 'Asia')
        
        if p_ny1 and p_ny2 and curr_asia:
            context_key = f"{p_ny1}|{p_ny2}"
            asia_outcomes[context_key].append({
                'status': curr_asia,
                'date': str(current_date.date()) 
                # Future: Add Price stats from unadjusted here if needed for the specific session outcome
            })

        # --- 2. LONDON PREDICTION (Context: Prev NY2, Curr Asia) ---
        curr_asia = get_session_status(df, current_date, 'Asia') # Re-get explicit
        p_ny2 = get_session_status(df, prev_date, 'NY2') # Re-get explicit (London relies on Prev NY2)
        
        # Get Target
        curr_lon = get_session_status(df, current_date, 'London')
        
        if p_ny2 and curr_asia and curr_lon:
            context_key = f"{p_ny2}|{curr_asia}"
            london_outcomes[context_key].append({
                'status': curr_lon,
                'date': str(current_date.date())
            })

    # --- AGGREGATION & STATS ---
    def summarize(outcome_map):
        summary = {}
        for context, samples in outcome_map.items():
            total = len(samples)
            
            # 1. Status Probabilities
            counts = defaultdict(int)
            for s in samples:
                counts[s['status']] += 1
            
            probs = {}
            for status, count in counts.items():
                probs[status] = round(count / total, 3)
            probs = dict(sorted(probs.items(), key=lambda item: item[1], reverse=True))
            
            # 2. Price Statistics (HOD/LOD %) - Using Unadjusted Data
            # Collect % stats for each outcome status
            price_stats = defaultdict(list)
            
            for s in samples:
                d_str = s['date']
                status = s['status']
                
                if d_str in unadjusted:
                    day_data = unadjusted[d_str]
                    u_open = day_data['daily_open']
                    u_high = day_data['hod_price']
                    u_low = day_data['lod_price']
                    
                    if u_open > 0:
                        h_pct = (u_high - u_open) / u_open * 100
                        l_pct = (u_low - u_open) / u_open * 100
                        price_stats[status].append({
                            'h': round(h_pct, 2),
                            'l': round(l_pct, 2)
                        })
            
            # Summarize Price Stats (Median/Mode ranges could be added here, 
            # but for now we store the raw lists or simple aggregates?)
            # Project requirements imply histograms. Let's store deciles or similar?
            # For simplicity and flexibility in UI, let's store the RAW list of percentages for now (per status),
            # or a simplified [p50, p90].
            # Actually, to replicate the Profiler histograms, we need the distribution.
            # Let's simple aggregation: { 'Long True': {'h_avg': ..., 'l_avg': ...} }
            # Wait, user wants "Outcomes" similar to current profiler.
            # Let's accumulate:
            final_price_stats = {}
            for status, p_list in price_stats.items():
                if not p_list: continue
                h_vals = [x['h'] for x in p_list]
                l_vals = [x['l'] for x in p_list]
                
                final_price_stats[status] = {
                    'h_avg': round(sum(h_vals)/len(h_vals), 2),
                    'l_avg': round(sum(l_vals)/len(l_vals), 2),
                    'sample_count': len(p_list)
                    # We can add full histograms later if needed, keeps JSON small for now
                }

            summary[context] = {
                'samples': total,
                'probabilities': probs,
                'price_stats': final_price_stats
            }
        return summary

    print("Aggregating Asia Stats...")
    asia_json = summarize(asia_outcomes)
    
    print("Aggregating London Stats...")
    london_json = summarize(london_outcomes)
    
    # --- SAVE ---
    print(f"Saving to {ASIA_OUTPUT_PATH}...")
    with open(ASIA_OUTPUT_PATH, 'w') as f:
        json.dump(asia_json, f, indent=2)
        
    print(f"Saving to {LONDON_OUTPUT_PATH}...")
    with open(LONDON_OUTPUT_PATH, 'w') as f:
        json.dump(london_json, f, indent=2)
        
    print("Done.")

if __name__ == "__main__":
    generate_predictions()
