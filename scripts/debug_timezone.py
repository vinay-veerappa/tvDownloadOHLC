import pandas as pd
import sys
from pathlib import Path
import pytz

def debug_tz():
    ticker = 'NQ1'
    data_file = Path(f'data/{ticker}_5m.parquet')
    df = pd.read_parquet(data_file)
    tz_et = pytz.timezone('US/Eastern')
    
    # Localize like the engine does
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(tz_et)
    else:
        df.index = df.index.tz_convert(tz_et)
    
    # Pick the day the user mentioned: 2025-11-03
    day_target = '2025-11-03'
    day_data = df[df.index.date == pd.to_datetime(day_target).date()]
    
    print(f"Debug for {day_target}:")
    print(f"Index TZ: {df.index.tz}")
    print(f"First few bars of the day (ET):")
    print(day_data.head(5))
    
    # Sample IB calculation
    ib_start = pd.Timestamp(day_target + ' 09:30:00').tz_localize(tz_et)
    ib_end = ib_start + pd.Timedelta(minutes=45)
    
    print(f"\nCalculated IB Start (ET): {ib_start}")
    print(f"Calculated IB End (ET):   {ib_end}")
    
    ib_slice = day_data[ib_start:ib_end]
    print(f"\nBars found in IB window: {len(ib_slice)}")
    if not ib_slice.empty:
        print(f"First IB bar: {ib_slice.index[0]}")
        print(f"Last IB bar:  {ib_slice.index[-1]}")

if __name__ == "__main__":
    debug_tz()
