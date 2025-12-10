
import pandas as pd

def debug_london_dec3():
    df = pd.read_parquet('data/NQ1_1m.parquet')
    if df.index.tz:
        df = df.tz_convert('US/Eastern')
    
    # Dec 3 London
    # Session: 02:30 - 03:30
    # Monitor: 03:30 - 07:30
    
    start_time = pd.Timestamp("2025-12-03 02:30").tz_localize('US/Eastern')
    end_time = pd.Timestamp("2025-12-03 03:30").tz_localize('US/Eastern')
    mon_end = pd.Timestamp("2025-12-03 07:30").tz_localize('US/Eastern')
    
    if df.index.tz is None:
         # Localize if read as naive (depends on parquet, usually UTC in this project but let's be safe)
         # Actually previous script used 'US/Eastern' conversion so index must be aware or handled.
         # Let's re-read and handle carefully.
         df = pd.read_parquet('data/NQ1_1m.parquet')
         # Assuming data is in correct timezone or UTC. Project convention says "US/Eastern".
         # For this debug, I'll print raw rows around 03:30.
         pass

    # Re-read raw to be sure of timezones
    df = pd.read_parquet('data/NQ1_1m.parquet')
    
    # Filter by string match for simplicity if index is naive/UTC
    # 2025-12-03
    day_data = df[df.index.astype(str).str.startswith('2025-12-03')]
    
    # Custom slice
    sess = day_data[(day_data.index.hour * 60 + day_data.index.minute >= 2*60 + 30) & 
                    (day_data.index.hour * 60 + day_data.index.minute < 3*60 + 30)]
                    
    mon = day_data[(day_data.index.hour * 60 + day_data.index.minute >= 3*60 + 30) & 
                   (day_data.index.hour * 60 + day_data.index.minute < 7*60 + 30)]

    print("Session OHLC:")
    print(sess[['high', 'low']].agg(['max', 'min']))
    
    high = sess['high'].max()
    low = sess['low'].min()
    print(f"Session Range: {high} - {low}")
    
    print("\nMonitoring Data (First 10 mins):")
    print(mon[['high', 'low']].head(10))
    
    print("\nViolations:")
    high_break = mon[mon['high'] > high]
    low_break = mon[mon['low'] < low]
    
    if not high_break.empty:
        print(f"High Broken at: {high_break.index[0]}")
    else:
        print("High NOT Broken")
        
    if not low_break.empty:
        print(f"Low Broken at: {low_break.index[0]}")
    else:
        print("Low NOT Broken")

if __name__ == "__main__":
    debug_london_dec3()
