import pandas as pd
import numpy as np

def analyze_timing(df):
    """When do reversals happen? Timing distribution analysis."""
    
    print("=" * 60)
    print("REVERSAL TIMING ANALYSIS")
    print("=" * 60)
    
    if 'reversal_time' not in df.columns:
        print("Reversal time data missing.")
        return
        
    valid = df[df['reversal_time'].notna()].copy()
    # Coerce to datetime, handle errors
    valid['rev_dt'] = pd.to_datetime(valid['reversal_time'], errors='coerce')
    valid = valid.dropna(subset=['rev_dt'])
    
    if valid.empty:
        print("No valid reversal times found.")
        return
    
    # 1. Overall Timing Distribution
    print("\n--- 1. Timing Distribution ---")
    
    def bucket_time(dt):
        if pd.isna(dt): return "Unknown"
        t = dt.time()
        if t < datetime.time(10, 0): return "09:30-10:00"
        if t < datetime.time(10, 30): return "10:00-10:30"
        if t < datetime.time(11, 0): return "10:30-11:00"
        if t < datetime.time(12, 0): return "11:00-12:00"
        if t < datetime.time(13, 30): return "12:00-13:30 (Lunch)"
        return "13:30-16:00 (PM)"
        
    import datetime
    valid['window'] = valid['rev_dt'].apply(bucket_time)
    
    counts = valid['window'].value_counts().sort_index()
    total = len(valid)
    cum = 0
    for w, c in counts.items():
        pct = c/total*100
        cum += pct
        print(f"{w:<20} : {c:>4} ({pct:>5.1f}%) Cum: {cum:>5.1f}%")
        
    # 2. By Manipulation Type
    print("\n--- 2. Timing by Manipulation Type ---")
    if 'manipulation' in valid.columns:
        print(valid.groupby('manipulation')['window'].value_counts(normalize=True).unstack().fillna(0) * 100)
        
    # 3. By Pattern
    print("\n--- 3. Timing by Pattern ---")
    if 'pattern' in valid.columns:
        # Filter top patterns
        top_pats = valid['pattern'].value_counts().head(3).index
        sub = valid[valid['pattern'].isin(top_pats)]
        print(sub.groupby('pattern')['window'].value_counts(normalize=True).unstack().fillna(0) * 100)
        
    # 4. By Day of Week
    print("\n--- 4. Timing by Day of Week ---")
    # Use apply instead of .dt accessor to avoid object-dtype issues
    valid['dow'] = valid['rev_dt'].apply(lambda x: x.day_name())
    
    # Sort dow
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    valid['dow'] = pd.Categorical(valid['dow'], categories=days, ordered=True)
    
    print(valid.groupby('dow')['window'].value_counts(normalize=True).unstack().fillna(0) * 100)
