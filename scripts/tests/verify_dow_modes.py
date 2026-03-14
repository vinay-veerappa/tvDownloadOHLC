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
df['dUp'] = np.maximum(0, (df['high'] - df['ema_prev']) / df['ema_prev'] * 100)
df['dDn'] = np.maximum(0, (df['ema_prev'] - df['low']) / df['ema_prev'] * 100)
df['dow'] = df['trade_date'].dt.dayofweek

def pine_mode(arr, bin_size=0.5):
    if len(arr) == 0: return np.nan
    mu = np.mean(arr)
    bins = np.floor(arr / bin_size) * bin_size  # typical binning
    u, c = np.unique(bins, return_counts=True)
    cands = u[c == c.max()]
    return float(cands[np.argmin(np.abs(cands - mu))])

def pine_median(arr):
    if len(arr) == 0: return np.nan
    s = np.sort(arr)
    n = len(s)
    mid = n // 2
    if n % 2 == 1: return s[mid]
    return (s[mid-1] + s[mid]) / 2.0

print('\n=== TRUE CALENDAR MATCH ===')
print('Day | MeanHi | MeanLo | MedHi | MedLo | ModeHi | ModeLo')
for i, name in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']):
    d = df[df['dow'] == i].tail(52)
    if len(d) > 0:
        dup = d['dUp'].values
        ddn = d['dDn'].values
        m_hi, m_lo = np.mean(dup), np.mean(ddn)
        med_hi, med_lo = pine_median(dup), pine_median(ddn)
        mod_hi, mod_lo = pine_mode(dup, 0.5), pine_mode(ddn, 0.5)
        
        # bin formatter
        def fmt_mode(val): return f"{val:.1f}-{val+0.5:.1f}" if not np.isnan(val) else "?"
        
        print(f'{name:3} |  {m_hi:5.2f} |  {m_lo:5.2f} | {med_hi:5.2f} | {med_lo:5.2f} | {fmt_mode(mod_hi):7} | {fmt_mode(mod_lo):7}')

print('\n=== OLD REFERENCE MAP (Shifted by 1 Day) ===')
df['open_dow'] = df.index.dayofweek
def map_ref(x):
    if x == 0: return 'Mon' 
    if x == 1: return 'Tue' 
    if x == 2: return 'Wed' 
    if x == 3: return 'Thu' 
    if x == 6: return 'Fri'
    return None

df['ref_mapped'] = df['open_dow'].map(map_ref)
for name in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
    d = df[df['ref_mapped'] == name].tail(52)
    if len(d) > 0:
        dup = d['dUp'].values
        ddn = d['dDn'].values
        m_hi, m_lo = np.mean(dup), np.mean(ddn)
        med_hi, med_lo = pine_median(dup), pine_median(ddn)
        mod_hi, mod_lo = pine_mode(dup, 0.5), pine_mode(ddn, 0.5)
        
        def fmt_mode(val): return f"{val:.1f}-{val+0.5:.1f}" if not np.isnan(val) else "?"
        
        print(f'{name:3} |  {m_hi:5.2f} |  {m_lo:5.2f} | {med_hi:5.2f} | {med_lo:5.2f} | {fmt_mode(mod_hi):7} | {fmt_mode(mod_lo):7}')
