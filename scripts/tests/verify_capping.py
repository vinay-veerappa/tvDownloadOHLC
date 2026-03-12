import pandas as pd, numpy as np
df = pd.read_parquet(r'c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet')
if df.index.tz is None: df.index = df.index.tz_localize('UTC')
df.index = df.index.tz_convert('US/Eastern')
df['trade_date'] = (df.index + pd.Timedelta(hours=6)).floor('d')
weekly = df.resample('W-FRI', on='trade_date').agg({'close': 'last'}).dropna()
weekly['ema'] = weekly['close'].ewm(span=5, adjust=False).mean()
weekly['ema_prev'] = weekly['ema'].shift(1)
df['week_end'] = df['trade_date'] + pd.to_timedelta((4 - df['trade_date'].dt.weekday + 7) % 7, unit='d')
df = df.merge(weekly[['ema_prev']], left_on='week_end', right_index=True, how='left')
df = df.dropna(subset=['ema_prev'])
df['dUp_raw'] = np.maximum(0, (df['high'] - df['ema_prev']) / df['ema_prev'] * 100)
df['dDn_raw'] = np.maximum(0, (df['ema_prev'] - df['low']) / df['ema_prev'] * 100)

# Shift to Old Reference Map
df['open_dow'] = df.index.dayofweek
def map_ref(x):
    if x == 0: return 'Mon' 
    if x == 1: return 'Tue' 
    if x == 2: return 'Wed' 
    if x == 3: return 'Thu' 
    if x == 6: return 'Fri'
    return None
df['ref_mapped'] = df['open_dow'].map(map_ref)

CAP_VAL = 3.0
df['dUp'] = np.minimum(df['dUp_raw'], CAP_VAL)
df['dDn'] = np.minimum(df['dDn_raw'], CAP_VAL)

print('\n=== OLD APP MAP: CAPPED AT 3.0 (Includes Zeros) ===')
for name in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
    d = df[df['ref_mapped'] == name].tail(52)
    if len(d) > 0:
        m_hi, m_lo = np.mean(d['dUp']), np.mean(d['dDn'])
        print(f'{name} | MeanHi {m_hi:5.2f} | MeanLo {m_lo:5.2f}')

print('\n=== OLD APP MAP: CAPPED AT 3.0 (Filtered Zeros) ===')
for name in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
    d = df[df['ref_mapped'] == name].tail(52)
    if len(d) > 0:
        dup_nz = d['dUp'][d['dUp_raw'] > 0]
        ddn_nz = d['dDn'][d['dDn_raw'] > 0]
        m_hi, m_lo = np.mean(dup_nz), np.mean(ddn_nz)
        med_hi, med_lo = np.median(dup_nz), np.median(ddn_nz)
        print(f'{name} | MeanHi {m_hi:5.2f} | MeanLo {m_lo:5.2f} | MedHi {med_hi:5.2f} | MedLo {med_lo:5.2f}')
