
import pandas as pd
import numpy as np

def analyze_last_n_sessions(days=3):
    # Load Data
    print("Loading data/NQ1_1m.parquet...")
    df = pd.read_parquet('data/NQ1_1m.parquet')
    df = df.sort_index()
    
    # Ensure US/Eastern
    if df.index.tz is None:
         # If naive, assume UTC and convert -> OR assume user wants Eastern
         # Project standard is US/Eastern.
         # For safety, let's localize to UTC then convert:
         df = df.tz_localize('UTC').tz_convert('US/Eastern')
    else:
         df = df.tz_convert('US/Eastern')
         
    # Get timezone
    tz = df.index.tz

    # Define Sessions (Start, End, NextStart)
    sessions_def = [
        {"name": "Asia",   "start": "18:00", "end": "19:30", "next_start": "02:30", "day_offset": 1}, 
        {"name": "London", "start": "02:30", "end": "03:30", "next_start": "07:30", "day_offset": 0},
        {"name": "NY1",    "start": "07:30", "end": "08:30", "next_start": "11:30", "day_offset": 0},
        {"name": "NY2",    "start": "11:30", "end": "12:30", "next_start": "16:00", "day_offset": 0}, 
    ]

    # Find the last few days
    unique_dates = sorted(list(set(df.index.date)))
    target_dates = unique_dates[-days:] 
    
    # Get timezone
    tz = df.index.tz

    collected_stats = []

    for date in target_dates: 
        date_str = date.strftime('%Y-%m-%d')
        
        for sess in sessions_def:
            print(f"DEBUG LOOP: Date={date_str} Sess={sess['name']}")
            # Construct timestamps ensuring exact TZ match
            start_naive = pd.Timestamp(f"{date_str} {sess['start']}")
            end_naive = pd.Timestamp(f"{date_str} {sess['end']}")
            
            start_ts = start_naive.tz_localize(tz)
            end_ts = end_naive.tz_localize(tz)
            
            if date_str == '2025-12-03' and sess['name'] == 'London':
                print(f"DEBUG DEC 3 LONDON: {start_ts} -> {end_ts}")
                temp_mask = (df.index >= start_ts) & (df.index < end_ts)
                temp_data = df[temp_mask]
                if not temp_data.empty:
                    print(f"DEBUG DATA: MaxHigh={temp_data['high'].max()} MinLow={temp_data['low'].min()}")
                    print(f"DEBUG HEAD: {temp_data.head(1)}")
                else:
                    print("DEBUG DATA: EMPTY")
            mon_start = end_ts
            
            # Monitoring End logic
            next_start_time = sess['next_start']
            mon_end_day = date
            if sess['day_offset'] == 1:
                mon_end_day = date + pd.Timedelta(days=1)
            
            mon_end_naive = pd.Timestamp(f"{mon_end_day.strftime('%Y-%m-%d')} {next_start_time}")
            mon_end = mon_end_naive.tz_localize(tz)


            # 1. Get Session Data to determine Range
            sess_mask = (df.index >= start_ts) & (df.index < end_ts)
            sess_data = df[sess_mask]
            
            if sess_data.empty: continue
            
            high = sess_data['high'].max()
            low = sess_data['low'].min()
            mid = (high + low) / 2
            
            # --- DEFINE WINDOWS ---
            # Status Window: End of Current Range -> Start of Next Range
            status_start = end_ts
            status_end = mon_end # This is 'next_start'
            
            # Broken Window: Start of Next Session -> Start of Asia (18:00)
            # User: "Broken gets reset when Asia session starts again"
            # Asia Start is 18:00 same day (for London/NY sessions)
            # For Asia session itself? It starts prior day 18:00. Next Asia is Day 18:00.
            
            # Define "Reset Time" (Next Asia 18:00)
            reset_time = pd.Timestamp(f"{date_str} 18:00")
            if df.index.tz:
                 try: reset_time = reset_time.tz_localize(df.index.tz)
                 except: pass

            # If reset_time is before status_end (e.g. Asia session case), add 1 day
            if reset_time <= status_end:
                 reset_time += pd.Timedelta(days=1)

            broken_start = status_end # Broken check starts when Next Session Starts
            broken_end = reset_time # Ends when Asia Start (Reset)
            
            # Handle NY2 case: NY2 Next Start is 16:00 (Close). 
            # If NY2 resets at 18:00, then window is 16:00-18:00?
            # Or does Broken Check start immediately after NY2 ends (12:30)?
            # User: "NY1 cannot be broken until NY2 starts". 
            # Implies window starts at Next Session Start.
    
            # 2. ANALYSIS: TRUE / FALSE STATUS (In Status Window)
            status_mask = (df.index >= status_start) & (df.index < status_end)
            status_data = df[status_mask]
            
            status = 'None'
            triggered_side = None 
            
            if not status_data.empty:
                for ts, row in status_data.iterrows():
                    h, l = row['high'], row['low']
                    
                    if triggered_side is None:
                        if h > high and l < low:
                             status = 'False' 
                             triggered_side = 'Both'
                             break
                        elif h > high:
                            triggered_side = 'High'
                            status = 'True Long' 
                        elif l < low:
                            triggered_side = 'Low'
                            status = 'True Short'
                    else:
                        if triggered_side == 'High':
                            if l < low:
                                status = 'False Long' 
                                break 
                        elif triggered_side == 'Low':
                            if h > high:
                                status = 'False Short' 
                                break

            # 3. ANALYSIS: BROKEN STATS (In Broken Window)
            broken_mask = (df.index >= broken_start) & (df.index < broken_end)
            broken_data = df[broken_mask]
            
            broken = False
            broken_time = None
            
            if not broken_data.empty:
                # Find first time Low <= Mid <= High
                break_mask = (broken_data['low'] <= mid) & (broken_data['high'] >= mid)
                if break_mask.any():
                    broken = True
                    broken_idx = break_mask.idxmax()
                    broken_time = broken_idx

            collected_stats.append({
                "Date": date_str,
                "StartTime": start_ts, 
                "Session": sess['name'],
                "Range": f"{high:.2f} - {low:.2f}",
                "Mid": f"{mid:.2f}",
                "RangeTime": f"{sess['start']}-{sess['end']}",
                "Status": status,
                "StatusWindow": f"{status_start.strftime('%H:%M')}-{status_end.strftime('%H:%M')}",
                "Broken": broken,
                "BrokenTime": broken_time.strftime('%H:%M') if broken_time else "-",
                "BrokenWindowStart": broken_start.strftime('%H:%M'),
                "BrokenWindowEnd": broken_end.strftime('%H:%M') # For debug
            })

    # Sort by time
    collected_stats.sort(key=lambda x: x['StartTime'])
    
    # Return Last 3 Days (approx 12 sessions)
    # Filter for dates in target_dates
    final_stats = [s for s in collected_stats if s['Date'] in [d.strftime('%Y-%m-%d') for d in target_dates]]
    return final_stats


def summarize_stats(stats):
    # Convert list of dicts to DataFrame for easy aggregation
    df = pd.DataFrame(stats)
    
    # Standardize Status strings to User Terminology
    # My script: "True Long" -> User: "Long True"
    # My script: "False Short" -> User: "Short False" (Broke Low then High)
    
    def map_status(s):
        if s == 'True Long': return 'Long True'
        if s == 'True Short': return 'Short True'
        if s == 'False Long': return 'Long False'  # Broke High then Low
        if s == 'False Short': return 'Short False' # Broke Low then High
        return s
        
    df['Status'] = df['Status'].apply(map_status)
    
    # Group by Session and Status
    summary = df.groupby(['Session', 'Status']).size().unstack(fill_value=0)
    
    # Add Total col
    summary['Total'] = summary.sum(axis=1)
    
    # Calculate Percentages
    # We want % of Total Sessions
    cols = [c for c in summary.columns if c != 'Total']
    for c in cols:
        summary[f'{c} %'] = (summary[c] / summary['Total'] * 100).round(1)
        
    return summary

if __name__ == "__main__":
    # Analyze all available data (e.g. 50 days)
    results = analyze_last_n_sessions(days=50)
    
    summary_df = summarize_stats(results)
    
    # Write to file
    with open('docs/profiler_summary_stats.md', 'w') as f:
        f.write("# Profiler Summary Stats (Last 50 Days of Data)\n\n")
        f.write(f"Generated from `data/NQ1_1m.parquet`.\n\n")
        
        f.write("## Aggregate Probabilities\n\n")
        f.write("```\n")
        f.write(summary_df.to_string())
        f.write("\n```\n\n")
        
        f.write("## Detailed Session Log (Last 10 Days)\n\n")
        f.write(f"| Date | Session | Range | Mid | Status | Broken? |\n")
        f.write(f"|---|---|---|---|---|---|\n")
        
        # Sort results by time for log
        results.sort(key=lambda x: x['StartTime'])
        
        # Helper map again for log
        def map_status_log(s):
            if s == 'True Long': return 'Long True'
            if s == 'True Short': return 'Short True'
            if s == 'False Long': return 'Long False'
            if s == 'False Short': return 'Short False'
            return s
            
        for r in results[-40:]: # Last ~10 days (4 sessions/day)
            brk = "Yes" if r['Broken'] else "No"
            st = map_status_log(r['Status'])
            st_disp = f"**{st}**" if "False" in st else st
            f.write(f"| {r['Date']} | {r['Session']} | {r['Range']} | {r['Mid']} | {st_disp} | {brk} |\n")
            
    print("Analysis complete. Saved to docs/profiler_summary_stats.md")
    print("\nSummary Preview:")
    print(summary_df)
