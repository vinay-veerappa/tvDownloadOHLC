import pandas as pd
import numpy as np
from datetime import timedelta

def generate_calendar(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Produces one row per trading date with:
    
    OpEx flags (deterministic):
    - is_monthly_opex: third Friday of month
    - is_triple_witching: third Friday of Mar/Jun/Sep/Dec
    - is_opex_week: Mon-Fri of monthly opex week
    - is_opex_minus_1: Thursday before monthly opex
    - days_to_monthly_opex: integer countdown
    
    Economic events: (Initial build: OpEx flags; Economic events can be added later)
    """
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    df = pd.DataFrame({'date': date_range})
    df['date'] = df['date'].dt.date
    
    # helper for 3rd Friday
    def get_third_friday(year, month):
        # find the first of month
        first_day = pd.Timestamp(year, month, 1)
        # first friday
        # weekday(): 0=Mon, 4=Fri, 6=Sun
        first_friday = first_day + timedelta(days=((4 - first_day.weekday()) % 7))
        return (first_friday + timedelta(days=14)).date()

    # Precompute all monthly opex dates in range
    years_months = df[['date']].copy()
    years_months['year'] = pd.to_datetime(years_months['date']).dt.year
    years_months['month'] = pd.to_datetime(years_months['date']).dt.month
    unique_ym = years_months[['year', 'month']].drop_duplicates()
    
    opex_dates = [get_third_friday(row.year, row.month) for row in unique_ym.itertuples()]
    
    df['is_monthly_opex'] = df['date'].isin(opex_dates)
    
    # Triple Witching (Mar, Jun, Sep, Dec)
    df['is_triple_witching'] = df.apply(
        lambda r: r['is_monthly_opex'] and pd.to_datetime(r['date']).month in [3, 6, 9, 12],
        axis=1
    )
    
    # OpEx Minus 1 (Thursday)
    opex_minus_1 = [d - timedelta(days=1) for d in opex_dates]
    df['is_opex_minus_1'] = df['date'].isin(opex_minus_1)
    
    # OpEx Week (Mon-Fri)
    # Start: Mon (Fri-4), End: Fri
    opex_weeks = []
    for d in opex_dates:
        mon = d - timedelta(days=4)
        opex_weeks.extend(pd.date_range(mon, d).date.tolist())
    df['is_opex_week'] = df['date'].isin(opex_weeks)
    
    # Days to monthly opex (trading days would be better, but calendar days for now)
    # Find next opex date for each date
    all_opex_sorted = sorted(opex_dates)
    
    def get_days_to(d):
        future_opex = [o for o in all_opex_sorted if o >= d]
        if not future_opex:
            return np.nan
        return (future_opex[0] - d).days

    df['days_to_monthly_opex'] = df['date'].apply(get_days_to)
    
    # Basic Position
    df_dt = pd.to_datetime(df['date'])
    df['day_of_month'] = df_dt.dt.day
    df['week_of_month'] = (df['day_of_month'] - 1) // 7 + 1
    
    # Month positions
    df['is_month_end'] = df_dt.dt.is_month_end
    
    # trading_date key consistency
    df['trading_date'] = pd.to_datetime(df['date'])
    
    return df
