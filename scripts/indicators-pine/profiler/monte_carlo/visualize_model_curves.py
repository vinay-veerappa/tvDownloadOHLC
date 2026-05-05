import json
import os
import sys
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = r"c:\Users\vinay\tvDownloadOHLC"
DATA_DIR = os.path.join(BASE_DIR, "data")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts", "profiler")
MODEL_FILES = {
    'LT': os.path.join(SCRIPTS_DIR, "ProfilerData_Model_LT.pine"),
    'LF': os.path.join(SCRIPTS_DIR, "ProfilerData_Model_LF.pine"),
    'ST': os.path.join(SCRIPTS_DIR, "ProfilerData_Model_ST.pine"),
    'SF': os.path.join(SCRIPTS_DIR, "ProfilerData_Model_SF.pine"),
}
ARTIFACTS_DIR = r"c:\Users\vinay\.gemini\antigravity\brain\3e5d7058-e84e-4d5d-9db3-c5426dd9f917"

def parse_pine_floats(filepath, var_name_fragment):
    # These model files usually contain float arrays, not packed ints.
    # Pattern: func _get_high_0() => array.from(0.001, 0.002...)
    with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
    
    full_vals = []
    lines = content.split('\n')
    in_func = False
    
    import re
    # Scan for all lines with array.from
    for line in lines:
        if var_name_fragment in line and "=>" in line:
            in_func = True
            
        if in_func and "array.from" in line:
            start = line.find('(')
            end = line.rfind(')')
            if start != -1 and end != -1:
                vals_str = line[start+1:end]
                # Floats
                vals = [float(x.strip()) for x in vals_str.split(',') if x.strip()]
                full_vals.extend(vals)
            in_func = False
    return full_vals

import requests

def fetch_api_model(outcome):
    try:
        url = "http://localhost:8000/stats/filtered-price-model"
        payload = {
            "ticker": "NQ1",
            "target_session": "Daily",
            "filters": {"Asia": outcome},
            "bucket_minutes": 5
        }
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        # Extract median path
        highs = [round(x['high'], 3) for x in data.get('median', [])]
        lows = [round(x['low'], 3) for x in data.get('median', [])]
        return highs, lows
    except Exception as e:
        print(f"API Fetch Error for {outcome}: {e}")
        return [], []

def plot_model_comparison():
    outcomes = [ ('LT', 'Long True'), ('LF', 'Long False'), 
                 ('ST', 'Short True'), ('SF', 'Short False') ]
    
    for key, name in outcomes:
        print(f"Comparing {name}...")
        
        # 1. Pine Data
        fpath = MODEL_FILES[key]
        p_highs = parse_pine_floats(fpath, "_get_high_")
        p_lows = parse_pine_floats(fpath, "_get_low_")
        
        # 2. Source Data (API)
        s_highs, s_lows = fetch_api_model(name)
        
        # Plot
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Source (Solid Thick)
        ax.plot(s_highs, label=f'API High (n={len(s_highs)})', color='blue', linewidth=3, alpha=0.4)
        ax.plot(s_lows, label=f'API Low', color='blue', linewidth=3, alpha=0.4)
        
        # Pine (Dashed Thin)
        ax.plot(p_highs, label=f'Pine High (n={len(p_highs)})', color='lime', linestyle='--', linewidth=1.5)
        ax.plot(p_lows, label=f'Pine Low', color='red', linestyle='--', linewidth=1.5)
        
        ax.set_title(f"Price Model Verification: {name} (API vs Pine)")
        ax.set_ylabel("Price Change %")
        ax.set_xlabel("Time Bucket (5m)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        fname = f"model_compare_{key}.png"
        out_path = os.path.join(ARTIFACTS_DIR, fname)
        plt.tight_layout()
        plt.savefig(out_path)
        print(f"Saved: {out_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--text":
        print_model_text_report()
    else:
        plot_model_comparison()

    print(f"Saved: {out_path}")

def print_model_text_report():
    print("\n" + "="*80)
    print("PRICE MODEL CURVE DATA (TEXTUAL VERIFICATION)")
    print("Values are Median High% / Median Low% at specific intraday checkpoints.")
    print("="*80)
    
    # Load all data
    data = {}
    for key, name in [('LT','Long True'), ('LF','Long False'), ('ST','Short True'), ('SF','Short False')]:
        fpath = MODEL_FILES[key]
        highs = parse_pine_floats(fpath, "_get_high_")
        lows = parse_pine_floats(fpath, "_get_low_")
        data[name] = (highs, lows)
        
    # Determine max length (assuming all same length for NQ usually, typically 78 for 5m bars in 6.5h session?)
    # or just sample proportional.
    # Let's check length of LT
    l = len(data['Long True'][0])
    print(f"Curve Length: {l} buckets (approx {l*5} mins)")
    
    # Sample points: Start, 25%, 50%, 75%, End
    indices = [0, int(l*0.25), int(l*0.50), int(l*0.75), l-1]
    
    print(f"{'Outcome':<15} | {'Start (0%)':<15} | {'25% Time':<15} | {'50% Time':<15} | {'75% Time':<15} | {'End (100%)':<15}")
    print("-" * 100)
    
    for name, (hs, ls) in data.items():
        row_str = f"{name:<15} | "
        for idx in indices:
            if idx < len(hs):
                val_str = f"{hs[idx]:.2f}/{ls[idx]:.2f}%"
            else:
                val_str = "N/A"
            row_str += f"{val_str:<15} | "
        print(row_str)
    print("-" * 100)
    print("Format: MedianHigh% / MedianLow%")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--text":
        print_model_text_report()
    else:
        plot_model_curves()
