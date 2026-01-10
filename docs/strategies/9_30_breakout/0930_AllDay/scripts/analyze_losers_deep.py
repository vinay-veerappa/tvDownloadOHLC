"""
Deep Loser Forensic Tool (V3)
=============================
Author: AI Assistant
Date: 2026-01-07

Goal: Identify WHY the V3 Strategy loses by correlating failing trades with:
1. Economic News (Prisma DB)
2. Profiler Status (True/False Sessions)
3. Opening Range Context (Chop/Exhaustion)
4. VWAP Alignment (Trend Fighting)

Outputs:
- V3_Loser_Forensics.md
"""

import pandas as pd
import numpy as np
import sqlite3
import json
import os
from datetime import datetime, timedelta

# Files
V3_FILE = r'docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_620dd.xlsx'
PRISMA_DB = r"web\prisma\dev.db"
PROFILER_JSON = r"data\NQ1_profiler.json"
OPENING_RANGE_JSON = r"data\NQ1_opening_range.json"
VWAP_PARQUET = r"data\indicators\NQ1_1m_vwap.parquet"

# --- 1. LOADERS ---

def load_v3_losers():
    """Load Strategy Excel and filter for Losers only."""
    print("Loading V3 Strategy Data...")
    try:
        xl = pd.ExcelFile(V3_FILE)
        sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
        df = pd.read_excel(xl, sheet_name=sheet)
        
        # Merge Entry/Exit rows
        entries = df[df['Type'].str.contains('Entry', case=False, na=False)][['Trade #', 'Date and time', 'Signal', 'Price USD']].copy()
        entries.columns = ['Trade #', 'Entry Time', 'Signal', 'Entry Price']
        
        exits = df[df['Type'].str.contains('Exit', case=False, na=False)].copy()
        merged = pd.merge(exits, entries, on='Trade #', how='inner')
        
        # Filter for LOSERS
        losers = merged[merged['Net P&L USD'] < 0].copy()
        losers['Entry Time'] = pd.to_datetime(losers['Entry Time'])
        losers['DateStr'] = losers['Entry Time'].dt.strftime('%Y-%m-%d')
        print(f"Losers Columns: {losers.columns.tolist()}")
        print(f"Loaded {len(losers)} Losing Trades.")
        return losers
    except Exception as e:
        print(f"Error loading V3: {e}")
        return pd.DataFrame()

def load_news_events():
    """Load HIGH IMPACT news from Prisma DB."""
    print("Loading News from Prisma...")
    try:
        conn = sqlite3.connect(PRISMA_DB)
        query = "SELECT datetime, name, impact FROM EconomicEvent WHERE impact='HIGH'"
        news_df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Determine strict or unix timestamp
        # Prisma usually stores BigInt timestamp (ms) or Datetime string
        # From probe: 946836000000 (ms)
        try:
            news_df['datetime'] = pd.to_datetime(news_df['datetime'], unit='ms')
        except:
            news_df['datetime'] = pd.to_datetime(news_df['datetime'])
            
        print(f"Loaded {len(news_df)} High Impact News Events.")
        return news_df
    except Exception as e:
        print(f"Error loading News: {e}")
        return pd.DataFrame()

def load_profiler():
    """Load Profiler JSON for Session Status."""
    print("Loading Profiler Data...")
    try:
        with open(PROFILER_JSON, 'r') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        # We care about Date + Session + Status
        # Filter for NY1 (AM) and NY2 (PM)
        df = df[df['session'].isin(['NY1', 'NY2'])]
        print(f"Loaded {len(df)} Profiler Session Records.")
        return df
    except Exception as e:
        print(f"Error loading Profiler: {e}")
        return pd.DataFrame()

def load_opening_range():
    """Load Pre-computed OR Stats."""
    print("Loading Opening Range Data...")
    try:
        with open(OPENING_RANGE_JSON, 'r') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        print(f"Loaded {len(df)} Opening Range Records.")
        return df
    except Exception as e:
        print(f"Error loading OR: {e}")
        return pd.DataFrame()

def load_vwap():
    """Load 1m VWAP Parquet."""
    print("Loading VWAP Data (This might take a moment)...")
    try:
        df = pd.read_parquet(VWAP_PARQUET)
        # Ensure time is datetime for merging
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    except Exception as e:
        print(f"Error loading VWAP: {e}")
        return pd.DataFrame()

# --- 2. ENRICHMENT ENGINE ---

def enrich_losers(losers, news, profiler, or_data, vwap):
    print("\nStarting Forensic Enrichment...")
    
    analyzed = losers.copy()
    
    # A. NEWS CHECK (±30 mins)
    print("- Checking News...")
    analyzed['Has_News_30m'] = False
    analyzed['News_Event'] = None
    
    # Vectorized check is hard with ranges, doing simplistic loop for now (3k records is fine)
    # Sort news for speed?
    high_impact_times = news['datetime'].sort_values().values
    
    # Optimization: Iterate trades
    news_hits = []
    events = []
    
    for idx, row in analyzed.iterrows():
        entry = row['Entry Time']
        start = entry - timedelta(minutes=30)
        end = entry + timedelta(minutes=30)
        
        # Check if any news falls in [start, end]
        # Using searchsorted for speed
        mask = (news['datetime'] >= start) & (news['datetime'] <= end)
        matches = news[mask]
        
        if not matches.empty:
            news_hits.append(True)
            events.append(", ".join(matches['name'].unique()))
        else:
            news_hits.append(False)
            events.append(None)
            
    analyzed['Has_News_30m'] = news_hits
    analyzed['News_Event'] = events
    
    # B. PROFILER STATUS (NY1 / NY2)
    print("- Checking Profiler Status...")
    # Map Trade Time to Session
    # NY1: 09:30 - 12:00 (approx)
    # NY2: 12:00 - 16:00
    # Actually, let's just use the hour. 
    #   < 12:00 = NY1
    #   >= 12:00 = NY2
    
    profiler['DateStr'] = profiler['date']
    
    # Merge Profiler into Analyzed
    # We need to do a lookup based on Date + Session
    
    session_status = []
    is_false_break = [] # True if Short False & Short Trade, etc.
    
    for idx, row in analyzed.iterrows():
        d = row['DateStr']
        h = row['Entry Time'].hour
        direction = row['Signal_y'] # "L1..." or "S3..."
        
        sess_name = 'NY1' if h < 12 else 'NY2'
        
        # Find record
        record = profiler[(profiler['DateStr'] == d) & (profiler['session'] == sess_name)]
        
        if not record.empty:
            status = record.iloc[0]['status'] # e.g. "Short False"
            session_status.append(status)
            
            # Check "Trap" Logic
            is_trap = False
            if isinstance(status, str):
                # Check for SHORT TRAP: Status is "Short False" and Trade is Short (Starts with 'S')
                if "Short False" in status and direction.startswith('S'): is_trap = True
                # Check for LONG TRAP: Status is "Long False" and Trade is Long (Starts with 'L')
                if "Long False" in status and direction.startswith('L'): is_trap = True
            
            is_false_break.append(is_trap)
        else:
            session_status.append("Unknown")
            is_false_break.append(False)
            
    analyzed['Profiler_Status'] = session_status
    analyzed['Is_False_Break_Trap'] = is_false_break
    
    # C. OPENING RANGE CONTEXT
    print("- Checking Opening Range...")
    or_data['DateStr'] = or_data['date']
    # Merge on DateStr
    analyzed = pd.merge(analyzed, or_data[['DateStr', 'range_pts', 'range_pct']], on='DateStr', how='left')
    
    # D. VWAP CONTEXT
    print("- Checking VWAP Alignment...")
    # Merge 1m VWAP on nearest minute
    analyzed['JoinTime'] = analyzed['Entry Time'].dt.floor('min')
    
    # Prepare VWAP
    vwap_slim = vwap[['time', 'vwap']].copy()
    vwap_slim.columns = ['JoinTime', 'VWAP_Value']
    
    analyzed = pd.merge(analyzed, vwap_slim, on='JoinTime', how='left')
    
    # Calculate Deviation
    analyzed['Dist_From_VWAP'] = analyzed['Entry Price'] - analyzed['VWAP_Value']
    
    # "Fighting Trend": Shorting > VWAP or Buying < VWAP?
    # Actually, standard logic:
    #   Bullish: Price > VWAP. Buying > VWAP is "With Trend". Buying < VWAP is "Reversion".
    #   Let's define "Fighting Trend" as:
    #       Long AND Price < VWAP (Buying below value - dangerous in strong trend?) -> Actually buying below VWAP is often good value.
    #       Shorting ABOVE VWAP (Fighting Up Trend?) -> No, Shorting High is good.
    #       Buying BELOW VWAP (Fighting Down Trend?) -> No, Buying Low is good.
    #   WAIT. Momentum Strategy (Breakout).
    #   Breakout Strategy wants to go WITH MOMENTUM.
    #   So:
    #       Long Requirement: Price SHOULD BE > VWAP (Proof of strength).
    #       Short Requirement: Price SHOULD BE < VWAP (Proof of weakness).
    #   FAILURE CONDITION:
    #       Long Entry but Price < VWAP (Weakness).
    #       Short Entry but Price > VWAP (Strength).
    
    # DEBUG: Check Profiler Merge
    print(f"\nDEBUG MERGE KEYS:")
    print(f"Loser Date Sample: {analyzed['DateStr'].iloc[0]}")
    print(f"Profiler Date Range: {profiler['DateStr'].min()} to {profiler['DateStr'].max()}")
    print(f"VWAP Time Range: {vwap_slim['JoinTime'].min()} to {vwap_slim['JoinTime'].max()}")
    
    # Test Lookup
    test_d = analyzed['DateStr'].iloc[0]
    test_lookup = profiler[(profiler['DateStr'] == test_d) & (profiler['session'] == 'NY1')]
    print(f"Specific Lookup for {test_d} (NY1): Found {len(test_lookup)} records.")
    if not test_lookup.empty:
        print(f"Status: {test_lookup.iloc[0]['status']}")

    fighting_vwap = []
    for idx, row in analyzed.iterrows():
        sig = row['Signal_y']
        price = row['Entry Price']
        v = row['VWAP_Value']
        
        if pd.isna(v):
            fighting_vwap.append(False)
            continue
            
        fight = False
        # Momentum Logic:
        # Long fails if Price < VWAP (Weakness) -> But Signal starts with 'L'
        # Short fails if Price > VWAP (Strength) -> But Signal starts with 'S'
        if sig.startswith('L') and price < v: fight = True 
        if sig.startswith('S') and price > v: fight = True 
        fighting_vwap.append(fight)
        
    analyzed['Fighting_VWAP'] = fighting_vwap
    
    print("\nDEBUG ENRICHED DATA (First 5):")
    print(analyzed[['Entry Time', 'Signal_y', 'VWAP_Value', 'Profiler_Status', 'Is_False_Break_Trap', 'Fighting_VWAP']].head(5))
    
    return analyzed

# --- 3. REPORTING ---

def generate_markdown(df):
    lines = []
    lines.append("# 🕵️ V3 Deep Loser Forensics")
    lines.append(f"**Analyzed Trades**: {len(df)}")
    lines.append("")
    
    # 1. NEWS SHOCK
    n_news = df['Has_News_30m'].sum()
    lines.append("## 1. The News Factor")
    lines.append(f"- **Losers on High Impact News**: {n_news} ({n_news/len(df):.1%})")
    lines.append("- *Correlation*: Are these losses just volatility stop-outs?")
    if n_news > 0:
        top_events = df[df['Has_News_30m']]['News_Event'].value_counts().head(5)
        lines.append("\n**Top Killer Events**:")
        for ev, count in top_events.items():
            lines.append(f"- {ev}: {count} losses")
    lines.append("")
    
    # 2. PROFILER TRAP
    n_traps = df['Is_False_Break_Trap'].sum()
    lines.append("## 2. The Profiler Trap (False Breakouts)")
    lines.append(f"- **Trap Trades**: {n_traps} ({n_traps/len(df):.1%})")
    lines.append("- Definition: *Taking a Short when the session ends up 'Short False' (or Long/Long False)*.")
    lines.append("- **Insight**: These are reversals where the breakout failed and reversed.")
    lines.append("")
    
    # 3. OPENING RANGE CONTEXT
    lines.append("## 3. Opening Range Context")
    avg_or = df['range_pts'].mean()
    lines.append(f"- **Avg OR Size (Losers)**: {avg_or:.2f} pts")
    
    chops = df[df['range_pts'] < 20]
    fatigues = df[df['range_pts'] > 100]
    
    lines.append(f"- **Small OR (< 20 pts) Losses**: {len(chops)} ({len(chops)/len(df):.1%})")
    lines.append(f"- **Huge OR (> 100 pts) Losses**: {len(fatigues)} ({len(fatigues)/len(df):.1%})")
    lines.append("")
    
    # 4. TREND FIGHTING (VWAP)
    n_fight = df['Fighting_VWAP'].sum()
    lines.append("## 4. Fighting the Trend (VWAP)")
    lines.append(f"- **Misaligned Trades**: {n_fight} ({n_fight/len(df):.1%})")
    lines.append("- Definition: *Going Long when Price < VWAP* or *Going Short when Price > VWAP*.")
    lines.append("")
    
    # 5. RECOMMENDATIONS
    lines.append("## 💡 Forensic Conclusions")
    lines.append("Based on the data above, here are the filters to test:")
    lines.append(f"1. **News Filter**: Avoid trading ±30m around the 'Killer Events'. Estimate Savings: {n_news} losers.")
    lines.append(f"2. **Trap Avoidance**: If we can predict 'False' sessions (e.g. by identifying chop early), we save {n_traps} trades.")
    lines.append(f"3. **VWAP Filter**: Only take Longs > VWAP and Shorts < VWAP. Estimate Savings: {n_fight} losers.")
    
    return "\n".join(lines)

if __name__ == '__main__':
    # Load
    losers = load_v3_losers()
    news = load_news_events()
    profiler = load_profiler()
    or_data = load_opening_range()
    vwap = load_vwap()
    
    if not losers.empty:
        # Enrich
        enriched = enrich_losers(losers, news, profiler, or_data, vwap)
        
        # Report
        report = generate_markdown(enriched)
        
        with open("V3_Loser_Forensics.md", "w", encoding="utf-8") as f:
            f.write(report)
            
        print("Done. Report saved to V3_Loser_Forensics.md")
    else:
        print("No losers found or failed to load.")
