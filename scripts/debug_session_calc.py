import pandas as pd
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from api.services.session_service import SessionService

def debug_calculation():
    print("Testing Hourly/3H Calculation...")
    
    # Create sample data covering a few days, starting at 18:00
    dates = pd.date_range(start='2024-12-01 18:00', end='2024-12-03 18:00', freq='1min', tz='America/New_York')
    df = pd.DataFrame(index=dates)
    df['open'] = 100
    df['high'] = 105
    df['low'] = 95
    df['close'] = 102
    
    # Run calculation
    results = SessionService.calculate_hourly(df)
    
    print(f"Generated {len(results)} periods")
    
    h1_count = len([p for p in results if p['type'] == '1H'])
    h3_count = len([p for p in results if p['type'] == '3H'])
    
    print(f"1H Periods: {h1_count}")
    print(f"3H Periods: {h3_count}")
    
    print("\nSample 3H Periods:")
    for p in results:
        if p['type'] == '3H':
            print(f"  Start: {p['start_time']} | End: {p['end_time']}")

if __name__ == "__main__":
    debug_calculation()
