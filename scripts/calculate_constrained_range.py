import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

def calculate_constrained_dates():
    # Setup Calendar
    us_bd = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    
    # 1. Find the End Date: 89th trading day of 2024
    # Start of 2024
    start_2024 = pd.Timestamp("2024-01-01")
    # If Jan 1 is a holiday/weekend, the first business day is later.
    # We want the 89th day. 
    # Example: 1st day is index 0 or offset 1? 
    # Usually "89 days in 2024" means the dataset includes 89 days.
    # So we want the date at index 88 (0-indexed) of the business days in 2024.
    
    days_2024 = pd.date_range(start="2024-01-01", end="2024-12-31", freq=us_bd)
    if len(days_2024) < 89:
        print("Error: 2024 doesn't have 89 trading days (impossible).")
        return

    target_end_date = days_2024[88] # 89th day
    
    # 2. Find the Start Date: 67 days in 2009
    # This implies the dataset covers the *end* of 2009.
    # We want the last 67 trading days of 2009.
    days_2009 = pd.date_range(start="2009-01-01", end="2009-12-31", freq=us_bd)
    
    if len(days_2009) < 67:
        print("Error: 2009 doesn't have 67 trading days.")
        return
        
    # We want the subset [start_date, ..., last_day_2009] to have length 67.
    # So start_date is at index: total_len - 67
    target_start_index = len(days_2009) - 67
    target_start_date = days_2009[target_start_index]
    
    print(f"Scenario: 'Uses only 67 days in 2009 and 89 days in 2024'")
    print("-" * 50)
    print(f"Start Date (2009): {target_start_date.strftime('%Y-%m-%d')} (First of the last 67 trading days)")
    print(f"End Date (2024):   {target_end_date.strftime('%Y-%m-%d')} (89th trading day of 2024)")
    print("-" * 50)
    
    # Calculate Total Trading Days in this range
    full_range = pd.date_range(start=target_start_date, end=target_end_date, freq=us_bd)
    print(f"Total Trading Days in Range: {len(full_range)}")
    
    # Also Check the original numbers user asked about against this range
    print(f"\nRe-verifying counts:")
    days_in_2009 = len([d for d in full_range if d.year == 2009])
    days_in_2024 = len([d for d in full_range if d.year == 2024])
    print(f"Days in 2009: {days_in_2009}")
    print(f"Days in 2024: {days_in_2024}")

if __name__ == "__main__":
    calculate_constrained_dates()
