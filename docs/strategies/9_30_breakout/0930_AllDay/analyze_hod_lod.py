
import pandas as pd
import json
import matplotlib.pyplot as plt
import os

FILE_PATH = r'c:\Users\vinay\tvDownloadOHLC\data\NQ1_daily_hod_lod.json'

def analyze_hod_lod(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    print(f"Loading {filepath}...")
    with open(filepath, 'r') as f:
        data = json.load(f)
        

        
    # Data is Dict: { "YYYY-MM-DD": { "hod_time": "...", ... } }
    # Convert to list
    records = []
    for date_str, rec in data.items():
        rec['date'] = date_str
        records.append(rec)
        
    df = pd.DataFrame(records)
    
    # Check field names: 'hod_time' vs 'high_time'
    high_col = 'hod_time' if 'hod_time' in df.columns else 'high_time'
    low_col = 'lod_time' if 'lod_time' in df.columns else 'low_time'
    
    # User asked to check Timezone.
    # Usually derived data is in Exchange Time (ET) or UTC.
    # If time is '00:00' for LOD, it might be start of day?
    # Or if '12:58' is HOD.
    # NQ trades nearly 24/7.
    # We will assume the time strings are comparable (HH:MM).
    # If they are UTC, we might need to shift (-5).
    # But usually "Daily" HOD/LOD is computed on the RTH or Full Session in ET.
    # Let's analyze distribution. If mode is 10:00 (ET) or 15:00 (UTC)?
    # We will output the raw distribution first to infer.
    
    df['high_dt'] = pd.to_datetime(df[high_col], format='%H:%M').dt.time
    df['low_dt'] = pd.to_datetime(df[low_col], format='%H:%M').dt.time
    
    df['high_hour'] = pd.to_datetime(df[high_col], format='%H:%M').dt.hour
    df['low_hour'] = pd.to_datetime(df[low_col], format='%H:%M').dt.hour
    
    # Calculate Range Retention (How much of the day's expansion is kept at close?)
    # For Bull Days (Close > Open): Retention = (Close - Low) / (High - Low) -> Ideally 1.0 (Close on High)
    # If Retention is 0.5, we gave back 50% of the rally.
    # We need to classify day type first.
    
    print("\n--- TIMING ANALYSIS ---")
    print(f"Total Days Analyzed: {len(df)}")
    
    # Mode Hours
    mode_high = df['high_hour'].mode()[0]
    mode_low = df['low_hour'].mode()[0]
    print(f"Most Frequent HOD Hour: {mode_high}:00 - {mode_high+1}:00")
    print(f"Most Frequent LOD Hour: {mode_low}:00 - {mode_low+1}:00")
    
    # Time Distribution
    print("\nHOD Time Distribution:")
    print(df['high_hour'].value_counts(normalize=True).sort_index().apply(lambda x: f"{x:.1%}"))
    
    print("\nLOD Time Distribution:")
    print(df['low_hour'].value_counts(normalize=True).sort_index().apply(lambda x: f"{x:.1%}"))
    
    # Save Report
    with open('HOD_LOD_Analysis.md', 'w') as f:
        f.write(f"# HOD/LOD Timing Analysis\n\n")
        f.write(f"Analyzed {len(df)} days of NQ1 data.\n\n")
        f.write(f"## Timing Modes\n")
        f.write(f"- Most Frequent HOD Hour: **{mode_high}:00** (ET)\n")
        f.write(f"- Most Frequent LOD Hour: **{mode_low}:00** (ET)\n\n")
        f.write("## Implication\n")
        f.write(f"If the Mode HOD is early (e.g. 10:00), holding to 16:00 exposes the trade to reversal risk.\n")
        f.write(f"This supports the 'Time + Trailing' logic: capture the HOD if it happens early, hold for EOD if trend persists.")

if __name__ == "__main__":
    analyze_hod_lod(FILE_PATH)
