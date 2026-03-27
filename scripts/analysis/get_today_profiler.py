"""
NQStats Profiler - Today's Status Briefing.
Loads the latest Parquet data and calculates Profiler (LT/ST/LF/SF) status for the current day.
"""

import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.getcwd())

from api.features.profiler.service import ProfilerService

def get_today_briefing(ticker="NQ1"):
    print(f"🔍 Fetching Profiler Status for {ticker}...")
    
    # 1. Run analysis for the last 3 days (to catch Asia from yesterday)
    # force=True ensures we calculate from the latest parquet data
    result = ProfilerService.analyze_profiler_stats(ticker, days=3, force=True)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return

    sessions = result.get("sessions", [])
    if not sessions:
        print("⚠️ No sessions found for the last 3 days.")
        return

    # 2. Get the unique dates and sort them
    # We want the latest one
    dates = sorted(list(set(s['date'] for s in sessions)))
    latest_date = dates[-1]
    
    print(f"\n📅 Trading Date: {latest_date}")
    print("-" * 40)
    
    # 3. Print session statuses for the latest date
    today_sessions = [s for s in sessions if s['date'] == latest_date]
    
    for s in today_sessions:
        session_name = s['session']
        status = s['status']
        broken = "💔 BROKEN" if s['broken'] else "💎 HELD"
        
        # Color coding/Emoji based on status
        emoji = "⚪"
        if "Long True" in status: emoji = "🟢"
        elif "Short True" in status: emoji = "🔴"
        elif "Long False" in status: emoji = "🟡"
        elif "Short False" in status: emoji = "🔵"
        
        print(f"{emoji} {session_name:6} | Status: {status:12} | {broken}")
        print(f"   Range: {s['range_high']:.2f} - {s['range_low']:.2f} (Mid: {s['mid']:.2f})")
        if s['broken_time']:
            print(f"   Broken at: {s['broken_time']}")
        print("-" * 20)

    print(f"\n✅ All times in US/Eastern.")
    print(f"Data source: {ticker}_1m.parquet")

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    get_today_briefing(ticker)
