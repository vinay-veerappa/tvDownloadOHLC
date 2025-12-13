import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from api.services.session_service import SessionService

def test_session_calculation():
    print("Generating mock data...")
    # Create 1-minute data for year boundary
    # Start at Dec 31 18:00
    start_time = pd.Timestamp("2023-12-31 18:00:00").tz_localize("US/Eastern")
    end_time = start_time + timedelta(hours=23)
    
    dates = pd.date_range(start=start_time, end=end_time, freq="1min")
    
    # Create simple price movement to easily track max/min
    # Price = minute of hour (0-59)
    prices = [t.minute for t in dates]
    
    # Specific manipulation:
    # 18:00 - 18:59 -> Max 59, Min 0
    # 19:00 - 19:59 -> Max 59, Min 0
    # 20:00 - 20:59 -> Max 59, Min 0
    
    # Make 19:30 spike to 100 to verify Max aggregation
    spike_idx = 90 # 18:00 + 90 mins = 19:30
    prices[spike_idx] = 100
    
    df = pd.DataFrame({
        'open': prices,
        'high': prices,
        'low': prices,
        'close': prices
    }, index=dates)
    
    print(f"Data range: {df.index[0]} to {df.index[-1]}")
    
    print("\nCalculating Hourly...")
    results = SessionService.calculate_hourly(df)
    
    hourly = [r for r in results if r['type'] == '1H']
    three_hour = [r for r in results if r['type'] == '3H']
    
    print(f"Generated {len(hourly)} hourly periods and {len(three_hour)} 3H periods")
    
    # Debug 1H periods
    print("\n--- 1H Periods ---")
    for r in hourly[:5]:
        print(f"{r['start_time']} -> {r['end_time']} | H:{r['high']} L:{r['low']}")

    # Debug 3H periods
    print("\n--- 3H Periods ---")
    for r in three_hour[:2]:
        print(f"{r['start_time']} -> {r['end_time']} | H:{r['high']} L:{r['low']}")
        
    # Check discrepancy
    # 18:00-21:00 3H block should include 18-19, 19-20, 20-21
    # Max should be 100 (from 19:30 spike)
    
    h18 = next((r for r in hourly if r['start_time'].startswith('2023-12-31T18:00')), None)
    h19 = next((r for r in hourly if r['start_time'].startswith('2023-12-31T19:00')), None)
    h20 = next((r for r in hourly if r['start_time'].startswith('2023-12-31T20:00')), None)
    
    th18 = next((r for r in three_hour if r['start_time'].startswith('2023-12-31T18:00')), None)
    
    if h18 and h19 and h20 and th18:
        # Check High
        max_1h = max(h18['high'], h19['high'], h20['high'])
        print(f"\nComparing 18:00-21:00 Block:")
        print(f"High: 1H Max ({max_1h}) vs 3H ({th18['high']})")
        if max_1h != th18['high']: print("❌ HIGH DISCREPANCY!")
        else: print("✅ High matches.")
        
        # Check Low
        min_1h = min(h18['low'], h19['low'], h20['low'])
        print(f"Low: 1H Min ({min_1h}) vs 3H ({th18['low']})")
        if min_1h != th18['low']: print("❌ LOW DISCREPANCY!")
        else: print("✅ Low matches.")
        
        # Check Open (Should match 18:00 1H Open)
        print(f"Open: 1H 18:00 ({h18['open']}) vs 3H ({th18['open']})")
        if h18['open'] != th18['open']: print("❌ OPEN DISCREPANCY!")
        else: print("✅ Open matches.")
        
        # Check Close (Should match 20:00 1H Close)
        print(f"Close: 1H 20:00 ({h20['close']}) vs 3H ({th18['close']})")
        if h20['close'] != th18['close']: print("❌ CLOSE DISCREPANCY!")
        else: print("✅ Close matches.")
            
    # Check Alignment
    print(f"\n3H Start Time: {th18['start_time'] if th18 else 'Missing'}")

if __name__ == "__main__":
    test_session_calculation()
