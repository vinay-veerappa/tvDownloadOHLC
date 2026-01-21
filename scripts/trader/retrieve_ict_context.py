import pandas as pd
import numpy as np
import argparse
import sys
import os
from datetime import datetime, timedelta

def get_last_session(df, ticker):
    # Assume df index is datetime
    last_date = df.index[-1].date()
    
    # Get Prior Day
    # We need strictly the previous trading day, not just yesterday
    unique_dates = sorted(df.index.date)
    curr_idx = unique_dates.index(last_date)
    
    if curr_idx > 0:
        prev_date = unique_dates[curr_idx-1]
        prev_day = df[df.index.date == prev_date]
        
        pdh = prev_day['high'].max()
        pdl = prev_day['low'].min()
        pdc = prev_day['close'].iloc[-1]
    else:
        pdh = pdl = pdc = None
        
    # Get Current Day (Midnight Open)
    curr_day = df[df.index.date == last_date]
    if not curr_day.empty:
        # Midnight Open: First bar of the day? 
        # Or specifically 00:00 (ET).
        # We need to handle timezone. data is typically UTC or ET.
        # Let's assume the parquet is processed or we handle first bar.
        
        # Try to find 00:00
        # If timestamp, we check hour/minute
        midnight_bars = curr_day[(curr_day.index.hour == 0) & (curr_day.index.minute == 0)]
        if not midnight_bars.empty:
            midnight_open = midnight_bars['open'].iloc[0]
        else:
            # Fallback to absolute first open of the session
            midnight_open = curr_day['open'].iloc[0]
            
        # 08:30 Open (News/Bond Open) - often used in ICT
        # 07:30 Open (old algo open?) - User mentioned 07:30 in previous tasks.
        open_0830 = None
        # 8*60 + 30 = 510
        bars_0830 = curr_day[(curr_day.index.hour == 8) & (curr_day.index.minute == 30)]
        if not bars_0830.empty:
            open_0830 = bars_0830['open'].iloc[0]
            
    else:
        midnight_open = None
        open_0830 = None
        
    return {
        'Date': last_date,
        'PDH': pdh,
        'PDL': pdl,
        'PDC': pdc,
        'Midnight_Open': midnight_open,
        'Open_0830': open_0830,
        'Last_Close': curr_day['close'].iloc[-1]
    }

def main(ticker):
    file_path = f"c:/Users/vinay/tvDownloadOHLC/data/{ticker}_1m.parquet"
    if not os.path.exists(file_path):
        print(f"Error: Data file not found for {ticker}")
        return

    try:
        df = pd.read_parquet(file_path)
    except Exception as e:
        print(f"Error reading parquet: {e}")
        return
        
    # Ensure Datetime Index
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df.set_index('datetime', inplace=True)
    elif not isinstance(df.index, pd.DatetimeIndex):
         # Try parsing 'date' and 'time' or just 'time' if it holds full datetime
         # Assuming parquet has standard format
         pass

    # Convert to Eastern Time for ICT levels (NY Midnight)
    try:
        df.index = df.index.tz_convert('US/Eastern')
    except:
        try:
            df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
        except:
             pass # Already naive or other issue

    data = get_last_session(df, ticker)
    
    print(f"\n💎 ICT CONTEXT SHEET: {ticker} 💎")
    print(f"Date: {data['Date']}")
    print("-----------------------------------")
    
    print("\n📍 KEY LEVELS (Liquidity):")
    if data['PDH']: print(f"   PDH:  {data['PDH']:.2f}  (Buyside Liquidity)")
    if data['PDL']: print(f"   PDL:  {data['PDL']:.2f}  (Sellside Liquidity)")
    if data['PDC']: print(f"   PDC:  {data['PDC']:.2f}  (Gap Fill)")
    
    print("\n🕒 TIME LEVELS (Magnets):")
    if data['Midnight_Open']: print(f"   Midnight Open: {data['Midnight_Open']:.2f} (Bias Pivot)")
    if data['Open_0830']:     print(f"   08:30 Open:    {data['Open_0830']:.2f}    (News Pivot)")
    
    print("\n🌊 BIAS CHECK:")
    if data['Midnight_Open']:
        curr_price = data['Last_Close']
        if curr_price > data['Midnight_Open']:
            print(f"   Current Price is ABOVE Midnight Open -> INTRA-DAY BULLISH CONTEXT")
        else:
            print(f"   Current Price is BELOW Midnight Open -> INTRA-DAY BEARISH CONTEXT")
            
    print("\n-----------------------------------")
    print("Stats Insight (from Historical Audit):")
    print("- 08:30 Open is a key reversal magnet if PDH/PDL are swept.")
    print("- Midnight Open acts as equilibrium; price often returns to it before trend continues.")
    print("-----------------------------------\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker (e.g. NQ1)")
    args = parser.parse_args()
    main(args.ticker)
