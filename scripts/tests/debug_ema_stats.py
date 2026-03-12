"""
Debug script to validate HTF EMA Analysis statistics against reference indicator.
Tests different EMA offset scenarios for "Opened Above EMA" and weekly stats.
"""
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats

DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet"
EMA_LENGTH = 5
LOOKBACK_WEEKS = 52

def calculate_ema(series, period):
    """Match Pine Script ta.ema: ewm with adjust=False"""
    return series.ewm(span=period, adjust=False).mean()

def mode_nearest_mean(arr, bin_size=0.1):
    """Match Pine Script f_mode_nearest_mean"""
    if len(arr) == 0:
        return np.nan
    mu = np.mean(arr)
    bins = np.round(arr / bin_size) * bin_size
    unique, counts = np.unique(bins, return_counts=True)
    max_count = counts.max()
    candidates = unique[counts == max_count]
    # Pick the one nearest to mean
    best = candidates[np.argmin(np.abs(candidates - mu))]
    return best

def main():
    print("=" * 70)
    print("HTF EMA Analysis - Python Validation")
    print("=" * 70)
    
    # Load daily data
    df = pd.read_parquet(DATA_PATH)
    df.index = df.index.tz_convert('US/Eastern')
    print(f"Daily data: {df.index[0].date()} to {df.index[-1].date()} ({len(df)} bars)")
    
    # Resample to weekly (W-FRI = week ending Friday)
    # For NQ futures, the exchange week runs Sun-Fri
    # Try multiple resample anchors to see which matches
    for anchor in ['W-FRI', 'W-SAT', 'W-SUN']:
        weekly = df.resample(anchor).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        weekly['ema5'] = calculate_ema(weekly['close'], EMA_LENGTH)
        
        # Get last 52 completed weeks (exclude the current/last partial week)
        # Assume last row might be partial
        completed = weekly.iloc[:-1]
        last_n = completed.iloc[-LOOKBACK_WEEKS:]
        
        print(f"\n{'=' * 70}")
        print(f"ANCHOR: {anchor} | Completed weeks: {len(completed)} | Last {LOOKBACK_WEEKS}: {len(last_n)}")
        print(f"Period: {last_n.index[0].date()} to {last_n.index[-1].date()}")
        
        # ============================================
        # Scenario A: open[i] vs ema[i] (same week's final EMA)
        # This is what open[1] vs ta.ema(close,5)[1] with lookahead=on gives
        # ============================================
        above_a = (last_n['open'] >= last_n['ema5']).sum()
        pct_a = above_a / len(last_n) * 100
        
        # ============================================
        # Scenario B: open[i] vs ema[i-1] (previous week's final EMA) 
        # This is what open[1] vs ta.ema(close,5)[2] with lookahead=on gives
        # Our current code (prevWeeklyEma = [2])
        # ============================================
        ema_shifted = weekly['ema5'].shift(1)
        completed_b = pd.DataFrame({
            'open': weekly['open'],
            'ema_prev': ema_shifted
        }).dropna().iloc[:-1]
        last_n_b = completed_b.iloc[-LOOKBACK_WEEKS:]
        above_b = (last_n_b['open'] >= last_n_b['ema_prev']).sum()
        pct_b = above_b / len(last_n_b) * 100
        
        # ============================================
        # Weekly stats: upPct and dnPct
        # Scenario B style: (high - ema[i-1]) / ema[i-1] * 100
        # ============================================
        stats_df = pd.DataFrame({
            'high': weekly['high'],
            'low': weekly['low'],
            'open': weekly['open'],
            'ema_prev': ema_shifted,
            'ema_same': weekly['ema5']
        }).dropna().iloc[:-1]
        stats_last = stats_df.iloc[-LOOKBACK_WEEKS:]
        
        # Using ema[i-1] (our current [2] approach)
        up_pct_b = ((stats_last['high'] - stats_last['ema_prev']) / stats_last['ema_prev'] * 100).values
        dn_pct_b = ((stats_last['ema_prev'] - stats_last['low']) / stats_last['ema_prev'] * 100).values
        
        # Using ema[i] (the [1] approach)
        up_pct_a = ((stats_last['high'] - stats_last['ema_same']) / stats_last['ema_same'] * 100).values
        dn_pct_a = ((stats_last['ema_same'] - stats_last['low']) / stats_last['ema_same'] * 100).values
        
        print(f"\n--- Opened Above EMA ---")
        print(f"  Scenario A (open vs same-week EMA):  {above_a}/{len(last_n)} = {pct_a:.1f}%")
        print(f"  Scenario B (open vs prev-week EMA):   {above_b}/{len(last_n_b)} = {pct_b:.1f}%")
        print(f"  Reference target:                     70.8%")
        
        print(f"\n--- Weekly Stats (using prev-week EMA = [2]) ---")
        print(f"  Mean  High%: {np.mean(up_pct_b):.2f}  Low%: {np.mean(dn_pct_b):.2f}")
        print(f"  Median High%: {np.median(up_pct_b):.2f}  Low%: {np.median(dn_pct_b):.2f}")
        print(f"  Mode  High%: {mode_nearest_mean(up_pct_b):.1f}  Low%: {mode_nearest_mean(dn_pct_b):.1f}")
        
        print(f"\n--- Weekly Stats (using same-week EMA = [1]) ---")
        print(f"  Mean  High%: {np.mean(up_pct_a):.2f}  Low%: {np.mean(dn_pct_a):.2f}")
        print(f"  Median High%: {np.median(up_pct_a):.2f}  Low%: {np.median(dn_pct_a):.2f}")
        print(f"  Mode  High%: {mode_nearest_mean(up_pct_a):.1f}  Low%: {mode_nearest_mean(dn_pct_a):.1f}")
        
        # Zone analysis (2-3%)
        zone_start, zone_end = 2.0, 3.0
        zone_hit_up_b = np.sum(up_pct_b >= zone_start) / len(up_pct_b) * 100
        zone_comp_up_b = np.sum(up_pct_b >= zone_end) / len(up_pct_b) * 100
        zone_hit_dn_b = np.sum(dn_pct_b >= zone_start) / len(dn_pct_b) * 100
        zone_comp_dn_b = np.sum(dn_pct_b >= zone_end) / len(dn_pct_b) * 100
        
        print(f"\n--- Zone 2-3% (using prev-week EMA) ---")
        print(f"  Zone Entry ↑: {zone_hit_up_b:.1f}%  ↓: {zone_hit_dn_b:.1f}%")
        print(f"  Zone Complete ↑: {zone_comp_up_b:.1f}%  ↓: {zone_comp_dn_b:.1f}%")
        
        # Show last few weeks for manual verification
        print(f"\n--- Last 5 weeks detail ---")
        for i in range(-5, 0):
            row = stats_last.iloc[i]
            print(f"  {stats_last.index[i].date()}: open={row['open']:.2f} high={row['high']:.2f} low={row['low']:.2f} ema_prev={row['ema_prev']:.2f} ema_same={row['ema_same']:.2f}")

if __name__ == "__main__":
    main()
