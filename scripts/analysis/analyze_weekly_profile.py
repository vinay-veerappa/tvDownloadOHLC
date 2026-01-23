import pandas as pd
import argparse
import os
from datetime import datetime, timedelta

# Import the unified data loader
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
from fused_data_loader import load_fused_data

def analyze_weekly_profile(ticker, target_date_str=None):
    """
    Analyzes the weekly profile relative to the target date.
    Determines if High of Week (HOW) or Low of Week (LOW) is likely set.
    """
    
    # 1. Load Data (Live + Historical fused)
    df = load_fused_data(ticker, require_historical=False) # Weekly analysis needs recent data primarily
    
    if df.empty:
        print(f"Error: No data found for {ticker}")
        return
    
    try:
        df.index = df.index.tz_convert('US/Eastern')
    except:
        try:
            df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
        except:
             pass

    # 2. Determine Scope (Current Week up to Target Date)
    if target_date_str:
        target_date = pd.to_datetime(target_date_str).date()
    else:
        target_date = datetime.now().date() # Default to today
        
    # Get start of week (Sunday or Monday?)
    # Markets often open Sunday 6pm ET, but let's count Monday as Day 1 for weekly range usually,
    # or Sunday Globex as start.
    # ISO Calendar: Monday is 1.
    # Start of this week:
    start_of_week = target_date - timedelta(days=target_date.weekday()) # Monday
    # Optional: include Sunday globex data? 
    # Let's simple filter: Data >= Start of Week 00:00 ET
    
    # Filter DF for this week up to (but not including?) target session if it's "next day" prev context?
    # If we are analyzing FOR "Tomorrow" (Target Date), we have data UP TO "Today".
    # So we analyze the COMPLETED data for the week so far.
    
    week_mask = (df.index.date >= start_of_week) & (df.index.date < target_date)
    week_data = df[week_mask]
    
    if week_data.empty:
        # Maybe it's Monday and we are prepping for Tuesday?
        # Or it's Sunday prepping for Monday?
        # If prepping for Monday, no weekly data exists yet.
        print(f"   (New Week: No prior weekly data for {target_date})")
        return

    # 3. Calculate Stats
    week_high = week_data['high'].max()
    week_low = week_data['low'].min()
    week_open = week_data['open'].iloc[0]
    last_close = week_data['close'].iloc[-1]
    
    # Identify Days High/Low were formed
    # We need to find the specific bar
    high_idx = week_data['high'].idxmax()
    low_idx = week_data['low'].idxmin()
    
    day_name = target_date.strftime("%A") # Day we are prepping FOR
    current_day_name = (target_date - timedelta(days=1)).strftime("%A") # Day just finished
    
    print(f"\n📅 WEEKLY PROFILE: {day_name.upper()} Analysis")
    print(f"   (Data from {start_of_week} to {current_day_name})")
    print(f"   WTD High: {week_high:.2f} ({high_idx.strftime('%A')})")
    print(f"   WTD Low:  {week_low:.2f}  ({low_idx.strftime('%A')})")
    print(f"   WTD Open: {week_open:.2f}")
    
    # 4. Heuristics (ICT Style)
    # "Tuesday Low of Week" or "Tuesday High of Week" is classic.
    # If it's Wednesday, and Low was Tuesday -> Likely LOW is in.
    
    bias_up = last_close > week_open
    
    print("\n🧐 PROJECTION:")
    if bias_up:
        print("   Structure: BULLISH (Above Week Open)")
        if low_idx.weekday() <= 1: # Low on Mon or Tue
            print("   Scenario:  Classic 'Tuesday/Monday Low' in effect?")
            print(f"   --> Expect Expansion toward Week High ({week_high:.2f})")
        else:
             print(f"   Scenario:  Low formed late ({low_idx.strftime('%A')}). Careful of reversal.")
    else:
        print("   Structure: BEARISH (Below Week Open)")
        if high_idx.weekday() <= 1: # High on Mon or Tue
            print("   Scenario:  Classic 'Tuesday/Monday High' in effect?")
            print(f"   --> Expect Expansion toward Week Low ({week_low:.2f})")
        else:
             print(f"   Scenario:  High formed late ({high_idx.strftime('%A')}). Careful of reversal.")
             
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker")
    parser.add_argument("--date", help="Target Date YYYY-MM-DD", required=False)
    args = parser.parse_args()
    
    analyze_weekly_profile(args.ticker, args.date)
