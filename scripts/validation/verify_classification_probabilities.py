import pandas as pd
import json
import os
from pathlib import Path

# Config
DATA_DIR = Path("data")
DERIVED_DIR = DATA_DIR / "derived"
TICKER = "NQ1"

def load_data():
    # 1. Load Daily Classifications (Targets)
    class_path = DERIVED_DIR / f"{TICKER}_daily_classification.parquet"
    if not class_path.exists():
        print(f"Error: {class_path} not found.")
        return None, None

    df_class = pd.read_parquet(class_path)
    # Ensure date column is strictly date type (not datetime) for merging
    df_class['date'] = pd.to_datetime(df_class['date']).dt.date
    
    # 2. Load Profiler (Features)
    prof_path = DATA_DIR / f"{TICKER}_profiler.json"
    if not prof_path.exists():
        print(f"Error: {prof_path} not found.")
        return None, None
        
    with open(prof_path) as f:
        prof_data = json.load(f)
        
    df_prof_raw = pd.DataFrame(prof_data)
    df_prof_raw['date'] = pd.to_datetime(df_prof_raw['date']).dt.date
    
    # Pivot Profiler to have one row per date with session columns
    # We want columns like: NY1_status, NY1_broken, NY2_status, etc.
    
    sessions = df_prof_raw['session'].unique()
    dfs = []
    
    for sess in sessions:
        sub = df_prof_raw[df_prof_raw['session'] == sess].copy()
        # Rename columns
        sub = sub.rename(columns={
            'status': f'{sess}_status',
            'broken': f'{sess}_broken',
            # Add other cols if needed
        })
        # Keep only date and renamed cols
        cols_to_keep = ['date', f'{sess}_status', f'{sess}_broken']
        sub = sub[cols_to_keep]
        sub = sub.set_index('date')
        dfs.append(sub)
        
    df_prof = pd.concat(dfs, axis=1)
    df_prof = df_prof.reset_index()
    
    # 3. Join
    df_merged = pd.merge(df_class, df_prof, on='date', how='inner')
    
    return df_merged

def calculate_probs(df, name, condition_mask):
    subset = df[condition_mask]
    count = len(subset)
    
    if count == 0:
        print(f"\n• {name}: No samples found.")
        return
        
    # Calculate percentages for outcomes
    # Expected outcomes: R1, R2, DWP, DNP
    # Note: 'type' column in classification
    
    dist = subset['type'].value_counts(normalize=True) * 100
    
    # Find most likely
    if not dist.empty:
        top_outcome = dist.idxmax()
        top_pct = dist.max()
        print(f"\n• IF {name} THEN Current Day is likely **{top_outcome} ({top_pct:.1f}%)** (n={count}).")
        
        # Optional: Print full dist for checking
        # print(f"    Distribution: {dist.to_dict()}")

def main():
    print(f"Verifying Classification Probabilities for {TICKER}...\n")
    df = load_data()
    if df is None:
        return
        
    print(f"Loaded {len(df)} days of merged data.")
    print("-" * 50)
    print("Current Day Classification (Predicting Today)\n")
    
    # 1. NY1 Model Status is Broken
    # "Broken" logic: broken == True
    calculate_probs(df, "NY1 Model Status is Broken", df['NY1_broken'] == True)
    
    # 2. NY1 Model Status is None
    # "None" logic: status == 'None' OR maybe NaN?
    # Profiler JSON likely has literal "None" string or null.
    # Let's check for 'None' string or NaN
    mask_ny1_none = (df['NY1_status'] == 'None') | (df['NY1_status'].isna())
    calculate_probs(df, "NY1 Model Status is None", mask_ny1_none)
    
    # 3. NY2 Session is Invalid (False)
    # Interpretation: "Valid" usually means Model Held (broken=False). "Invalid" means Broken (broken=True).
    calculate_probs(df, "NY2 Session is Invalid (False)", df['NY2_broken'] == True)
    
    # 4. NY2 Session is Invalid (False) AND Direction is Short
    # Direction Short: status contains 'Short'
    mask_ny2_invalid_short = (df['NY2_broken'] == True) & (df['NY2_status'].str.contains('Short', na=False))
    calculate_probs(df, "NY2 Session is Invalid (False) AND Direction is Short", mask_ny2_invalid_short)
    
    # 5. LND Session is Invalid (False)
    # Assuming LND = London
    calculate_probs(df, "LND Session is Invalid (False)", df['London_broken'] == True)
    
    # 6. NY2 Session is Valid (True)
    # Valid = broken == False
    calculate_probs(df, "NY2 Session is Valid (True)", df['NY2_broken'] == False)
    
    # 7. NY2 Session is Valid (True) AND Direction is Long
    mask_ny2_valid_long = (df['NY2_broken'] == False) & (df['NY2_status'].str.contains('Long', na=False))
    calculate_probs(df, "NY2 Session is Valid (True) AND Direction is Long", mask_ny2_valid_long)
    
    # 8. ASA Session is Valid (True)
    # ASA = Asia
    calculate_probs(df, "ASA Session is Valid (True)", df['Asia_broken'] == False)
    
    # 9. LND Direction is None
    # Status is 'None'
    mask_lnd_none = (df['London_status'] == 'None') | (df['London_status'].isna())
    calculate_probs(df, "LND Direction is None", mask_lnd_none)
    
    print("\n" + "-" * 50)

if __name__ == "__main__":
    main()
