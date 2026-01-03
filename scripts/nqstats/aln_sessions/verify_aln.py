
import pandas as pd
import numpy as np
import os
from datetime import datetime
import glob
from collections import defaultdict

# --- Constants ---
# Sessions in ET (US/Eastern)
ASIA_START = "20:00" # Prior Day
ASIA_END   = "02:00" # Current Day
LONDON_START = "02:00"
LONDON_END   = "08:00"
NY_START     = "08:00"
NY_END       = "16:00" # RTH Close

SESSION_MAPPING = {
    'Asia': (ASIA_START, ASIA_END),
    'London': (LONDON_START, LONDON_END),
    'NY': (NY_START, NY_END)
}

def load_data(ticker_path):
    """Loads 1m parquet data and converts to US/Eastern."""
    if not os.path.exists(ticker_path):
        print(f"File not found: {ticker_path}")
        return None
    
    print(f"Loading {ticker_path}...")
    df = pd.read_parquet(ticker_path)
    
    # Identify datetime column
    time_col = None
    if 'time' in df.columns: time_col = 'time'
    elif 'date' in df.columns: time_col = 'date'
    elif 'Date' in df.columns: time_col = 'Date'
    
    if time_col:
        # Check if unit is seconds or ms
        if df[time_col].iloc[0] > 1e10: # likely ms
             df['datetime'] = pd.to_datetime(df[time_col], unit='ms')
        else:
             df['datetime'] = pd.to_datetime(df[time_col], unit='s')
        df = df.set_index('datetime')
    elif not isinstance(df.index, pd.DatetimeIndex):
        print("Error: Could not identify datetime index or column.")
        return None
        
    # Standardize to US/Eastern
    if df.index.tz is None:
        df = df.tz_localize('UTC')
    df = df.tz_convert('US/Eastern')
    
    return df.sort_index()

def get_session_ranges(df):
    """
    Groups data by 'Trading Day' (ending at 16:00 ET).
    Extracts High/Low for Asia, London, NY.
    """
    days_stats = []
    
    # Resample to daily to iterate, but we need custom boundaries
    # Strategy: Iterate by actual calendar days, but handle the generic logic
    # Actually, simpler: 
    # 1. Identify "Session Date". For Asia (20:00-02:00), it belongs to the *following* trading day.
    #    e.g. Data from Sunday 20:00 is part of Monday's session.
    # 2. We can assign a 'TradingDate' column.
    
    df['TradingDate'] = df.index.date
    # Adjust: If hour >= 17 (5 PM ET), it belongs to next day (Next Day Session)
    # But Asia starts at 20:00, so > 17 is safe for Futures.
    
    # Logic: 
    # Asia: Prev Day 20:00 - Current Day 02:00
    # London: Current Day 02:00 - 08:00
    # NY: Current Day 08:00 - 16:00
    
    # We will iterate through unique dates in the dataset
    unique_dates = df.index.normalize().unique()
    
    print(f"Processing {len(unique_dates)} days...")
    
    for current_date in unique_dates:
        try:
            # Define time windows for this specific date
            # Asia starts previous day at 20:00
            prev_date = current_date - pd.Timedelta(days=1)
            
            asia_start = pd.Timestamp.combine(prev_date.date(), datetime.strptime(ASIA_START, "%H:%M").time()).tz_localize('US/Eastern')
            asia_end   = pd.Timestamp.combine(current_date.date(), datetime.strptime(ASIA_END, "%H:%M").time()).tz_localize('US/Eastern')
            
            london_start = asia_end # 02:00
            london_end   = pd.Timestamp.combine(current_date.date(), datetime.strptime(LONDON_END, "%H:%M").time()).tz_localize('US/Eastern')
            
            ny_start = london_end # 08:00
            ny_end   = pd.Timestamp.combine(current_date.date(), datetime.strptime(NY_END, "%H:%M").time()).tz_localize('US/Eastern')
            
            # Extract slices
            asia_slice = df[asia_start:asia_end]
            london_slice = df[london_start:london_end]
            ny_slice = df[ny_start:ny_end]
            
            # Must have data for all sessions to be valid
            if len(asia_slice) == 0 or len(london_slice) == 0 or len(ny_slice) == 0:
                continue
                
            stats = {
                'Date': current_date.date(),
                'Asia_High': asia_slice['high'].max(),
                'Asia_Low': asia_slice['low'].min(),
                'London_High': london_slice['high'].max(),
                'London_Low': london_slice['low'].min(),
                'NY_High': ny_slice['high'].max(),
                'NY_Low': ny_slice['low'].min()
            }
            days_stats.append(stats)
            
        except Exception as e:
            # print(f"Error processing {current_date}: {e}")
            continue
            
    return pd.DataFrame(days_stats)

def classify_and_verify(stats_df):
    """
    Classifies the relationship between Asia and London.
    Verifies NY outcomes against the logic.
    """
    results = []
    
    for idx, row in stats_df.iterrows():
        # 1. Classification
        london_high, london_low = row['London_High'], row['London_Low']
        asia_high, asia_low = row['Asia_High'], row['Asia_Low']
        ny_high, ny_low = row['NY_High'], row['NY_Low']
        
        category = "Unknown"
        
        # Engulfs
        london_engulfs_asia = (london_high > asia_high) and (london_low < asia_low)
        asia_engulfs_london = (london_high <= asia_high) and (london_low >= asia_low)
        
        # Partials
        # Check explicit logic from transcript
        # "London Partially Engulfs Up": Takes Asia High, but NOT Asia Low
        london_partial_up = (london_high > asia_high) and (london_low >= asia_low)
        
        # "London Partially Engulfs Down": Takes Asia Low, but NOT Asia High
        london_partial_down = (london_low < asia_low) and (london_high <= asia_high)
        
        if london_engulfs_asia:
            category = "LEA (London Engulfs Asia)"
        elif asia_engulfs_london:
            category = "AEL (Asia Engulfs London)"
        elif london_partial_up:
            category = "LPEU (London Partial Up)"
        elif london_partial_down:
            category = "LPED (London Partial Down)"
        
        # 2. Verification (Did NY break levels?)
        # For LEA: Did NY break London High/Low?
        # For AEL: Did NY break Asia High/Low?
        # For LPEU: Did NY break London High (Continuation) / London Low (Reversal)?
        # For LPED: Did NY break London Low (Continuation) / London High (Reversal)?
        
        res = {
            'Date': row['Date'],
            'Category': category,
            'NyBreaks_LondonHigh': ny_high > london_high,
            'NyBreaks_LondonLow': ny_low < london_low,
            'NyBreaks_AsiaHigh': ny_high > asia_high,
            'NyBreaks_AsiaLow': ny_low < asia_low
        }
        results.append(res)
        
    return pd.DataFrame(results)

def generate_report(results_df, ticker):
    if results_df.empty:
        print(f"No results for {ticker}")
        return
        
    print(f"\n--- {ticker} ALN Verification Report ---")
    print(f"Total Days Analyzed: {len(results_df)}")
    
    categories = ['LEA (London Engulfs Asia)', 'AEL (Asia Engulfs London)', 
                  'LPEU (London Partial Up)', 'LPED (London Partial Down)']
    
    report_data = []
    
    for cat in categories:
        subset = results_df[results_df['Category'] == cat]
        count = len(subset)
        if count == 0: continue
        
        print(f"\nCategory: {cat} (n={count}, {count/len(results_df):.1%})")
        
        # Define relevant metrics based on category logic
        metrics = {}
        
        if "LEA" in cat:
            # Claim: NY breaks London High OR Low (~80%), Both (~64%)
            broken_any = subset.apply(lambda r: r['NyBreaks_LondonHigh'] or r['NyBreaks_LondonLow'], axis=1).mean()
            broken_both = subset.apply(lambda r: r['NyBreaks_LondonHigh'] and r['NyBreaks_LondonLow'], axis=1).mean()
            metrics['Break London Hi/Lo (Any)'] = broken_any
            metrics['Engulf London (Both)'] = broken_both
            print(f"  NY Breaks London Hi or Lo: {broken_any:.1%} (Claim: ~80%)")
            print(f"  NY Engulfs London Both:    {broken_both:.1%} (Claim: ~64%)")
            
        elif "AEL" in cat:
            # Claim: NY breaks Asia High (~74%), Asia Low (~63%), Both (~42%)
            brk_high = subset['NyBreaks_AsiaHigh'].mean()
            brk_low = subset['NyBreaks_AsiaLow'].mean()
            brk_both = subset.apply(lambda r: r['NyBreaks_AsiaHigh'] and r['NyBreaks_AsiaLow'], axis=1).mean()
            metrics['Break Asia High'] = brk_high
            metrics['Break Asia Low'] = brk_low
            metrics['Engulf Asia (Both)'] = brk_both
            print(f"  NY Breaks Asia High: {brk_high:.1%} (Claim: ~74%)")
            print(f"  NY Breaks Asia Low:  {brk_low:.1%} (Claim: ~63%)")
            print(f"  NY Engulfs Asia:     {brk_both:.1%} (Claim: ~42%)")
            
        elif "LPEU" in cat:
            # Claim: NY breaks London High (Continuation ~78%), London Low (Reversal ~63%)
            cont = subset['NyBreaks_LondonHigh'].mean()
            rev = subset['NyBreaks_LondonLow'].mean()
            metrics['Continuation (Brk Lon Hi)'] = cont
            metrics['Reversal (Brk Lon Lo)'] = rev
            print(f"  Continuation (Brk Lon Hi): {cont:.1%} (Claim: ~78%)")
            print(f"  Reversal (Brk Lon Lo):     {rev:.1%} (Claim: ~63%)")

        elif "LPED" in cat:
            # Claim: NY breaks London Low (Continuation ~82%), London High (Reversal ~58%)
            cont = subset['NyBreaks_LondonLow'].mean()
            rev = subset['NyBreaks_LondonHigh'].mean()
            metrics['Continuation (Brk Lon Lo)'] = cont
            metrics['Reversal (Brk Lon Hi)'] = rev
            print(f"  Continuation (Brk Lon Lo): {cont:.1%} (Claim: ~82%)")
            print(f"  Reversal (Brk Lon Hi):     {rev:.1%} (Claim: ~58%)")
            
        # Add to consolidated report
        for m, val in metrics.items():
            report_data.append({'Ticker': ticker, 'Category': cat, 'Metric': m, 'Value': val, 'Count': count})

    return pd.DataFrame(report_data)

# --- Main Execution ---
if __name__ == "__main__":
    # Tickers to verify
    tickers = ['NQ1', 'ES1', 'YM1', 'RTY1', 'GC1', 'CL1']
    all_reports = []
    
    for t in tickers:
        file_path = f"data/{t}_1m.parquet"
        if os.path.exists(file_path):
            df = load_data(file_path)
            if df is not None:
                stats = get_session_ranges(df)
                if not stats.empty:
                    res = classify_and_verify(stats)
                    rep = generate_report(res, t)
                    if rep is not None:
                        all_reports.append(rep)
    
    if all_reports:
        final_df = pd.concat(all_reports)
        out_path = "scripts/nqstats/results/aln_verification_summary.csv"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        final_df.to_csv(out_path, index=False)
        print(f"\nSaved consolidated report to {out_path}")
