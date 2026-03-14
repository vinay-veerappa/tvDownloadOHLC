import pandas as pd
import numpy as np

DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet"

def main():
    df = pd.read_parquet(DATA_PATH)
    if df.index.tz is None:
         df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('US/Eastern')
    
    # Identify trade_date exactly as the CME session date
    # Any bar starting after 17:00 Eastern belongs to the next calendar trade_date
    df['trade_date'] = (df.index + pd.Timedelta(hours=6)).floor('d')
    
    # Calculate Weekly EMA via Friday close
    weekly = df.resample('W-FRI', on='trade_date').agg({'close': 'last'}).dropna()
    weekly['ema'] = weekly['close'].ewm(span=5, adjust=False).mean()
    weekly['ema_prev'] = weekly['ema'].shift(1)
    
    # Map back to daily bars
    df['week_end'] = df['trade_date'] + pd.to_timedelta((4 - df['trade_date'].dt.weekday + 7) % 7, unit='d')
    df = df.merge(weekly[['ema_prev']], left_on='week_end', right_index=True, how='left')
    df = df.dropna(subset=['ema_prev'])
    
    # Filter 52 weeks
    start_date = df['trade_date'].max() - pd.Timedelta(weeks=52)
    df = df[df['trade_date'] > start_date]
    
    df['dUp'] = np.maximum(0, (df['high'] - df['ema_prev']) / df['ema_prev'] * 100)
    df['dDn'] = np.maximum(0, (df['ema_prev'] - df['low']) / df['ema_prev'] * 100)
    
    print("\n=== CALENDAR/TRADE DATE MAPPING (What it should be) ===")
    df['trade_dow'] = df['trade_date'].dt.dayofweek # 0=Mon,1=Tue...
    for i, name in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']):
        d = df[df['trade_dow'] == i]
        if len(d) > 0:
            hup = (d['dUp'] >= 2.0).mean() * 100
            hdn = (d['dDn'] >= 2.0).mean() * 100
            print(f"{name}: N={len(d):2}, Hit Up: {hup:5.1f}%, Hit Dn: {hdn:5.1f}%")

    print("\n=== PINE SCRIPT MAPPING (What the indicator actually does) ===")
    # Pine looks at dayofweek(time[1], 'US/Eastern')
    # time[1] for today's bar is yesterday's bar time.
    # Our df.index represents today's bar open time.
    # So dayofweek of df.index basically shifted.
    df['pine_dow'] = df.index.dayofweek
    # Pine: dow == dayofweek.sunday(6) or dow == monday(0) -> 0 (Mon)
    df['pine_idx'] = df['pine_dow'].map({6: 0, 0: 0, 1: 1, 2: 2, 3: 3, 4: 4})
    
    for i, name in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']):
        d = df[df['pine_idx'] == i]
        if len(d) > 0:
            hup = (d['dUp'] >= 2.0).mean() * 100
            hdn = (d['dDn'] >= 2.0).mean() * 100
            print(f"{name}: N={len(d):2}, Hit Up: {hup:5.1f}%, Hit Dn: {hdn:5.1f}%")

if __name__ == '__main__':
    main()
