"""
Forensics Module
================
Enriches trade data with external context to identify correlation patterns.
Contexts:
1. News (High Impact events within +/- 30m)
2. Profiler Status (Session True/False/Trap)
3. Opening Range (Chop/Trend)
4. VWAP Alignment (Trend Fighting)
"""

import pandas as pd
import numpy as np
from datetime import timedelta

def enrich_with_context(trades_df, news_df, profiler_df, or_df, vwap_df):
    """
    Apply all forensic enrichments to the trades dataframe.
    Returns a copy with added columns.
    """
    if trades_df.empty: return trades_df
    
    analyzed = trades_df.copy()
    
    # --- 1. NEWS CORRELATION ---
    # Vectorized loop (simplest for disparate timelines)
    analyzed['Has_News_30m'] = False
    analyzed['News_Event'] = None
    
    if not news_df.empty:
        news_hits = []
        events = []
        for idx, row in analyzed.iterrows():
            entry = row['Entry Time']
            start = entry - timedelta(minutes=30)
            end = entry + timedelta(minutes=30)
            
            mask = (news_df['datetime'] >= start) & (news_df['datetime'] <= end)
            matches = news_df[mask]
            
            if not matches.empty:
                news_hits.append(True)
                events.append(", ".join(matches['name'].unique()))
            else:
                news_hits.append(False)
                events.append(None)
        analyzed['Has_News_30m'] = news_hits
        analyzed['News_Event'] = events
        
    # --- 2. PROFILER TRAPS ---
    # Map Trade Time to Session (NY1 < 12:00, NY2 >= 12:00)
    if not profiler_df.empty:
        profiler_df['DateStr'] = profiler_df['date']
        
        session_status = []
        is_trap = []
        
        for idx, row in analyzed.iterrows():
            d = row['DateStr']
            h = row['Entry Time'].hour
            sig = row.get('Entry Signal', '')
            if pd.isna(sig): sig = ''
            
            sess_name = 'NY1' if h < 12 else 'NY2'
            
            record = profiler_df[(profiler_df['DateStr'] == d) & (profiler_df['session'] == sess_name)]
            
            if not record.empty:
                status = record.iloc[0]['status']
                session_status.append(status)
                
                # Trap Logic: "Short False" + Short Signal | "Long False" + Long Signal
                # Signal format assumed: "L1...", "S1..." or "Long", "Short"
                trap = False
                if isinstance(status, str):
                    is_short_sig = sig.startswith('S') or 'Short' in sig
                    is_long_sig = sig.startswith('L') or 'Long' in sig
                    
                    if "Short False" in status and is_short_sig: trap = True
                    if "Long False" in status and is_long_sig: trap = True
                
                is_trap.append(trap)
            else:
                session_status.append("Unknown")
                is_trap.append(False)
                
        analyzed['Profiler_Status'] = session_status
        analyzed['Is_Profiler_Trap'] = is_trap
        
    # --- 3. OPENING RANGE ---
    if not or_df.empty:
        or_df['DateStr'] = or_df['date']
        # Merge on DateStr
        if 'range_pts' not in analyzed.columns:
            analyzed = pd.merge(analyzed, or_df[['DateStr', 'range_pts', 'range_pct']], on='DateStr', how='left')
            
    # --- 4. VWAP ALIGNMENT ---
    if not vwap_df.empty:
        # Match on nearest minute
        analyzed['JoinTime'] = analyzed['Entry Time'].dt.floor('min')
        
        vwap_slim = vwap_df[['time', 'vwap']].copy()
        vwap_slim.columns = ['JoinTime', 'VWAP_Value']
        
        analyzed = pd.merge(analyzed, vwap_slim, on='JoinTime', how='left')
        
        # Fighter Logic
        fighting = []
        for idx, row in analyzed.iterrows():
            v = row['VWAP_Value']
            p = row['Entry Price']
            sig = row.get('Entry Signal', '')
            
            if pd.isna(v) or pd.isna(p):
                fighting.append(False)
                continue
                
            is_fight = False
            # Buying below VWAP (Fighting Trend - technically reversion, but V3 is breakout)
            # Shorting above VWAP 
            
            is_long = sig.startswith('L') or 'Long' in sig
            is_short = sig.startswith('S') or 'Short' in sig
            
            # Note: "Trend Fighting" definition from V3 Forensics
            # Long < VWAP
            # Short > VWAP
            if is_long and p < v: is_fight = True
            if is_short and p > v: is_fight = True
            
            fighting.append(is_fight)
            
        analyzed['Fighting_VWAP'] = fighting
        
    return analyzed

def generate_forensic_summary(df):
    """Generate text stats for the forensic report."""
    if df.empty: return "No data."
    
    lines = []
    lines.append(f"analyzed {len(df)} trades.")
    
    # News
    if 'Has_News_30m' in df.columns:
        n = df['Has_News_30m'].sum()
        lines.append(f"- News Shock (±30m): {n} ({n/len(df):.1%})")
        
    # Trap
    if 'Is_Profiler_Trap' in df.columns:
        n = df['Is_Profiler_Trap'].sum()
        lines.append(f"- Profiler Traps (False Session): {n} ({n/len(df):.1%})")
        
    # VWAP
    if 'Fighting_VWAP' in df.columns:
        n = df['Fighting_VWAP'].sum()
        lines.append(f"- Trend Fighters (Vs VWAP): {n} ({n/len(df):.1%})")
        
    # Chop (OR < 20)
    if 'range_pts' in df.columns:
        chop = df[df['range_pts'] < 20]
        lines.append(f"- Market Chop (OR < 20pts): {len(chop)} ({len(chop)/len(df):.1%})")
        
    return "\n".join(lines)
