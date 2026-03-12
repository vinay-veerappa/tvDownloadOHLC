import pandas as pd
import numpy as np

DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet"
EMA_LENGTH = 5
LOOKBACK = 52
Z_START = 2.0
Z_END = 3.0

def hit_rate(arr, threshold):
    return (np.array(arr) >= threshold).mean() * 100

def mean_safe(arr):
    return np.mean(arr) if len(arr) > 0 else np.nan

def median_safe(arr):
    return np.median(arr) if len(arr) > 0 else np.nan

def mode_nearest_mean(arr, bin_size=0.1):
    if len(arr) == 0: return np.nan
    mu = np.mean(arr)
    bins = np.round(np.array(arr) / bin_size) * bin_size
    unique, counts = np.unique(bins, return_counts=True)
    candidates = unique[counts == counts.max()]
    return float(candidates[np.argmin(np.abs(candidates - mu))])

def main():
    df = pd.read_parquet(DATA_PATH)
    # Ensure timezone is Eastern like the chart
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('US/Eastern')
    
    # Generate weekly boundary markers
    # We want weekly EMA from previous week, but same-week EMA[1] means 
    # the EMA value at the end of the previous week.
    weekly = df.resample('W-FRI').agg({'close': 'last'})
    weekly['ema'] = weekly['close'].ewm(span=EMA_LENGTH, adjust=False).mean()
    weekly['ema_prev'] = weekly['ema'].shift(1)  # this is what [1] does in pine script for weekly tf
    
    # Map previous week's EMA to each daily bar
    # We do this by creating a week identifier
    df['week_end'] = df.index + pd.to_timedelta((4 - df.index.weekday + 7) % 7, unit='d')
    df['week_end'] = df['week_end'].dt.floor('d')
    
    weekly['week_end'] = weekly.index.floor('d')
    df = df.merge(weekly[['week_end', 'ema_prev']], on='week_end', how='left')
    df.index = df['datetime']  # Restore index, assuming we must keep track
    
    # Actually, the merge drops index. Let's do it cleaner.
    
if __name__ == '__main__':
    main()
