import pandas as pd
import numpy as np

def analyze_first_strike(df: pd.DataFrame):
    """Analyze which levels are hit first in each session."""
    
    print("\n" + "="*50)
    print("FIRST STRIKE ANALYSIS (WHICH LEVEL HITS FIRST?)")
    print("="*50)
    
    sessions = {
        'NY Session (09:30-16:00)': '',
        'Lunch Session (12:00-13:30)': 'lunch_',
        'PM Session (13:30-16:00)': 'pm_',
        'Next Asia Session': 'asia_'
    }
    
    for session_name, prefix in sessions.items():
        print(f"\n--- {session_name} ---")
        
        # Identify all hit_time columns for this session
        time_cols = [c for c in df.columns if c.startswith(f"{prefix}hit_") and c.endswith("_time")]
        
        if not time_cols:
            print(f"No hit time columns found for {session_name}.")
            continue
            
        # Convert to datetime if they are strings (using utc=True for mixed timezones)
        session_times_df = df[time_cols].apply(pd.to_datetime, errors='coerce', utc=True)
        
        # Ensure only datetime columns are processed.
        session_times_df = session_times_df.select_dtypes(include=['datetime', 'datetimetz'])
        
        if session_times_df.empty:
            print("No valid hit times found.")
            continue

        # Drop rows where all columns are NaT before indexing
        valid_rows = session_times_df.dropna(how='all')
        
        if valid_rows.empty:
            print("No hits recorded in this session.")
            continue

        # Find the earliest time for each row and the name of the column
        # min(axis=1) on datetime64 correctly handles NaT
        first_strike_times = valid_rows.min(axis=1)
        first_strike_cols = valid_rows.idxmin(axis=1)
        
        # Clean up names (remove prefix and _time)
        fixed_names = first_strike_cols.str.replace(prefix, "").str.replace("hit_", "").str.replace("_time", "")
        
        # Distribution
        counts = fixed_names.value_counts()
        pcts = fixed_names.value_counts(normalize=True) * 100
        
        summary = pd.DataFrame({
            'Level': counts.index,
            'Count': counts.values,
            'Percentage': pcts.values
        })
        
        if not summary.empty:
            print(summary.to_string(index=False))
        else:
            print("No hits recorded in this session.")

if __name__ == "__main__":
    # Test with dummy data if needed
    pass
