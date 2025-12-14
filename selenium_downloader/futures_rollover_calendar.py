"""
Futures Contract Rollover Calendar Generator
Generates historical expiration and rollover dates for CL and ES futures contracts
"""

import pandas as pd
from pandas.tseries.offsets import BDay
from datetime import datetime, timedelta
from typing import List, Tuple
import warnings
warnings.filterwarnings('ignore')


class FuturesRolloverCalendar:
    """Generate rollover dates for futures contracts"""
    
    def __init__(self):
        # Contract month codes
        self.month_codes = {
            1: 'F', 2: 'G', 3: 'H', 4: 'J', 5: 'K', 6: 'M',
            7: 'N', 8: 'Q', 9: 'U', 10: 'V', 11: 'X', 12: 'Z'
        }
    
    def get_es_expiration(self, year: int, month: int) -> pd.Timestamp:
        """
        Get ES (E-mini S&P 500) expiration date
        Rule: Third Friday of contract month (Mar, Jun, Sep, Dec)
        """
        if month not in [3, 6, 9, 12]:
            raise ValueError("ES only has quarterly contracts: Mar(3), Jun(6), Sep(9), Dec(12)")
        
        # Find all Fridays in the month
        month_start = pd.Timestamp(year, month, 1)
        month_end = pd.Timestamp(year, month, 1) + pd.DateOffset(months=1) - timedelta(days=1)
        
        # Get all days in month
        days = pd.date_range(month_start, month_end, freq='D')
        
        # Filter for Fridays (dayofweek == 4)
        fridays = days[days.dayofweek == 4]
        
        if len(fridays) < 3:
            raise ValueError(f"Less than 3 Fridays found in {year}-{month}")
        
        # Return third Friday
        return fridays[2]
    
    def get_cl_expiration(self, year: int, month: int) -> pd.Timestamp:
        """
        Get CL (Crude Oil) expiration date
        Rule: Trading terminates 3 business days before the 25th calendar day 
              of the month prior to the contract month
        """
        # The 25th of the month BEFORE the delivery month
        if month == 1:
            prior_year = year - 1
            prior_month = 12
        else:
            prior_year = year
            prior_month = month - 1
        
        # 25th of prior month
        twenty_fifth = pd.Timestamp(prior_year, prior_month, 25)
        
        # Go back 3 business days
        expiration = twenty_fifth - BDay(3)
        
        return expiration
    
    def generate_es_calendar(self, start_year: int, end_year: int, 
                            rollover_days_before: int = 8) -> pd.DataFrame:
        """
        Generate ES rollover calendar
        
        Args:
            start_year: Starting year
            end_year: Ending year
            rollover_days_before: Days before expiration to roll (default 8)
        
        Returns:
            DataFrame with contract info, expiration, and rollover dates
        """
        contracts = []
        
        for year in range(start_year, end_year + 1):
            for month in [3, 6, 9, 12]:  # Quarterly
                try:
                    expiration = self.get_es_expiration(year, month)
                    rollover_date = expiration - BDay(rollover_days_before)
                    
                    # Contract code (e.g., ESH24 for March 2024)
                    year_code = str(year)[-2:]  # Last 2 digits
                    contract_code = f"ES{self.month_codes[month]}{year_code}"
                    
                    contracts.append({
                        'contract': contract_code,
                        'symbol': 'ES',
                        'year': year,
                        'month': month,
                        'month_name': pd.Timestamp(year, month, 1).strftime('%B'),
                        'expiration_date': expiration,
                        'rollover_date': rollover_date,
                        'days_before_expiry': rollover_days_before
                    })
                except Exception as e:
                    print(f"Error generating ES contract for {year}-{month}: {e}")
        
        df = pd.DataFrame(contracts)
        df = df.sort_values('expiration_date').reset_index(drop=True)
        return df
    
    def generate_cl_calendar(self, start_year: int, end_year: int,
                            rollover_days_before: int = 10) -> pd.DataFrame:
        """
        Generate CL rollover calendar
        
        Args:
            start_year: Starting year
            end_year: Ending year
            rollover_days_before: Days before expiration to roll (default 10)
        
        Returns:
            DataFrame with contract info, expiration, and rollover dates
        """
        contracts = []
        
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):  # All 12 months
                try:
                    expiration = self.get_cl_expiration(year, month)
                    rollover_date = expiration - BDay(rollover_days_before)
                    
                    # Contract code (e.g., CLH24 for March 2024)
                    year_code = str(year)[-2:]
                    contract_code = f"CL{self.month_codes[month]}{year_code}"
                    
                    contracts.append({
                        'contract': contract_code,
                        'symbol': 'CL',
                        'year': year,
                        'month': month,
                        'month_name': pd.Timestamp(year, month, 1).strftime('%B'),
                        'expiration_date': expiration,
                        'rollover_date': rollover_date,
                        'days_before_expiry': rollover_days_before
                    })
                except Exception as e:
                    print(f"Error generating CL contract for {year}-{month}: {e}")
        
        df = pd.DataFrame(contracts)
        df = df.sort_values('expiration_date').reset_index(drop=True)
        return df
    
    def get_active_contract(self, symbol: str, date: pd.Timestamp, 
                           calendar_df: pd.DataFrame) -> str:
        """
        Get the active contract for a given date
        
        Args:
            symbol: 'ES' or 'CL'
            date: Date to check
            calendar_df: Calendar DataFrame from generate_*_calendar
        
        Returns:
            Contract code (e.g., 'ESH24')
        """
        # Find contracts where date is before expiration
        active = calendar_df[calendar_df['expiration_date'] > date]
        
        if len(active) == 0:
            return None
        
        # Return the nearest expiring contract (front month)
        return active.iloc[0]['contract']
    
    def export_to_csv(self, df: pd.DataFrame, filename: str):
        """Export calendar to CSV"""
        df.to_csv(filename, index=False)
        print(f"Calendar exported to {filename}")


def main():
    """Example usage"""
    calendar = FuturesRolloverCalendar()
    
    # Generate calendars from 2020 to 2025
    print("Generating ES (E-mini S&P 500) Calendar...")
    es_calendar = calendar.generate_es_calendar(2020, 2025, rollover_days_before=8)
    print(f"\nES Calendar: {len(es_calendar)} contracts generated")
    print("\nFirst 5 ES contracts:")
    print(es_calendar.head())
    print("\nLast 5 ES contracts:")
    print(es_calendar.tail())
    
    print("\n" + "="*80 + "\n")
    
    print("Generating CL (Crude Oil) Calendar...")
    cl_calendar = calendar.generate_cl_calendar(2020, 2025, rollover_days_before=10)
    print(f"\nCL Calendar: {len(cl_calendar)} contracts generated")
    print("\nFirst 5 CL contracts:")
    print(cl_calendar.head())
    print("\nLast 5 CL contracts:")
    print(cl_calendar.tail())
    
    # Example: Find active contract for a specific date
    print("\n" + "="*80 + "\n")
    test_date = pd.Timestamp('2024-12-13')
    es_active = calendar.get_active_contract('ES', test_date, es_calendar)
    cl_active = calendar.get_active_contract('CL', test_date, cl_calendar)
    print(f"Active contracts on {test_date.date()}:")
    print(f"  ES: {es_active}")
    print(f"  CL: {cl_active}")
    
    # Export to CSV
    print("\n" + "="*80 + "\n")
    calendar.export_to_csv(es_calendar, '/home/claude/es_rollover_calendar.csv')
    calendar.export_to_csv(cl_calendar, '/home/claude/cl_rollover_calendar.csv')
    
    # Show rollover windows for 2024
    print("\n" + "="*80 + "\n")
    print("ES 2024 Rollover Windows:")
    es_2024 = es_calendar[es_calendar['year'] == 2024]
    for _, row in es_2024.iterrows():
        print(f"  {row['contract']}: Roll on {row['rollover_date'].date()} "
              f"(expires {row['expiration_date'].date()})")
    
    print("\nCL 2024 Rollover Windows (showing Q4 only):")
    cl_2024_q4 = cl_calendar[(cl_calendar['year'] == 2024) & (cl_calendar['month'] >= 10)]
    for _, row in cl_2024_q4.iterrows():
        print(f"  {row['contract']}: Roll on {row['rollover_date'].date()} "
              f"(expires {row['expiration_date'].date()})")


if __name__ == "__main__":
    main()
