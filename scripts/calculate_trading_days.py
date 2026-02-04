import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

def calculate_dates():
    # Define end date
    end_date = pd.Timestamp("2024-12-31")
    
    # Create US business day calendar (standard for "trading days")
    us_bd = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    
    # We need to go back 4584 trading days. 
    # To be safe, let's generate a range of business days going back far enough.
    # 4600 trading days is roughly 18-20 years.
    # Let's generate a date_range of BUSINESS days ending at 2024-12-31
    # We can just count backwards using the offset.
    
    # 3773 trading days back
    date_3773 = end_date - 3773 * us_bd
    
    # 4584 trading days back
    date_4584 = end_date - 4584 * us_bd
    
    print(f"End Date: {end_date.strftime('%Y-%m-%d')}")
    print("-" * 30)
    print(f"3773 trading days back: {date_3773.strftime('%Y-%m-%d')}")
    print(f"4584 trading days back: {date_4584.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    calculate_dates()
