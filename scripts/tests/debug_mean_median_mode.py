"""
Scenario test for Mean/Median/Mode of weekly % deviation from EMA(5).
Tests different weekly anchors, EMA variants, and mode calculation methods.
Run this to identify which combination matches the reference indicator.

USAGE: Set TARGET_* to the reference indicator's displayed values, then compare.
"""
import pandas as pd
import numpy as np

DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet"
EMA_LENGTH = 5
LOOKBACK_WEEKS = 52

# ── Set these to the REFERENCE indicator's displayed values ──────────────────
TARGET_MEAN_HI  = None   # e.g. 2.21
TARGET_MEAN_LO  = None   # e.g. 2.05
TARGET_MED_HI   = None   # e.g. 3.14
TARGET_MED_LO   = None   # e.g. 1.95
TARGET_MODE_HI  = None   # e.g. 3.1
TARGET_MODE_LO  = None   # e.g. 1.8
# ────────────────────────────────────────────────────────────────────────────

def ema(series, span, adjust=False):
    return series.ewm(span=span, adjust=adjust).mean()

def pine_median(arr):
    """Match Pine f_median: sort, midpoint average for even N."""
    s = np.sort(arr)
    n = len(s)
    mid = int(np.floor(n * 0.5))
    if n % 2 == 1:
        return s[mid]
    else:
        return (s[mid - 1] + s[mid]) * 0.5

def pine_mode(arr, bin_size=0.1):
    """Match Pine f_mode_nearest_mean: bin, find max freq, nearest-to-mean tiebreak."""
    if len(arr) == 0:
        return np.nan
    mu = np.mean(arr)
    bins = np.round(arr / bin_size) * bin_size
    unique, counts = np.unique(bins, return_counts=True)
    max_count = counts.max()
    candidates = unique[counts == max_count]
    return candidates[np.argmin(np.abs(candidates - mu))]

def score(val, target, tol=0.1):
    if target is None or val is None or np.isnan(val):
        return ""
    return " ✓ MATCH" if abs(val - target) <= tol else f" (diff {val - target:+.3f})"

def run_scenario(label, up_pct, dn_pct):
    n = len(up_pct)
    mean_hi  = np.mean(up_pct)
    mean_lo  = np.mean(dn_pct)
    med_hi   = pine_median(up_pct)
    med_lo   = pine_median(dn_pct)
    
    results = {}
    for bsz in [0.1, 0.25, 0.5, 1.0]:
        mhi = pine_mode(up_pct, bsz)
        mlo = pine_mode(dn_pct, bsz)
        results[bsz] = (mhi, mlo)
    
    print(f"\n{'─'*60}")
    print(f"Scenario: {label}  (N={n})")
    print(f"  Mean  Hi={mean_hi:.2f}{score(mean_hi, TARGET_MEAN_HI)}  Lo={mean_lo:.2f}{score(mean_lo, TARGET_MEAN_LO)}")
    print(f"  Median Hi={med_hi:.2f}{score(med_hi, TARGET_MED_HI)}  Lo={med_lo:.2f}{score(med_lo, TARGET_MED_LO)}")
    for bsz, (mhi, mlo) in results.items():
        print(f"  Mode(bin={bsz}) Hi={mhi:.2f}{score(mhi, TARGET_MODE_HI)}  Lo={mlo:.2f}{score(mlo, TARGET_MODE_LO)}")
    return mean_hi, mean_lo, med_hi, med_lo

def main():
    df = pd.read_parquet(DATA_PATH)
    df.index = df.index.tz_convert('US/Eastern')
    print(f"Data: {df.index[0].date()} to {df.index[-1].date()}  ({len(df)} daily bars)")

    for anchor in ['W-FRI', 'W-SAT', 'W-SUN']:
        weekly = df.resample(anchor).agg(
            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
        ).dropna()

        for adj in [False, True]:
            e5       = ema(weekly['close'], EMA_LENGTH, adjust=adj)
            e5_p1    = e5              # same week's closing EMA ([1] offset in Pine)
            e5_p2    = e5.shift(1)    # prior week's closing EMA ([2] offset in Pine)

            for ema_label, ref_ema in [('[2] prev-week EMA', e5_p2), ('[1] same-week EMA', e5_p1)]:
                df_w = pd.DataFrame({
                    'high': weekly['high'],
                    'low':  weekly['low'],
                    'ref_ema': ref_ema,
                }).dropna().iloc[:-1]   # drop last (possibly incomplete) week

                last = df_w.iloc[-LOOKBACK_WEEKS:]
                up  = ((last['high'] - last['ref_ema']) / last['ref_ema'] * 100).values
                dn  = ((last['ref_ema'] - last['low'])  / last['ref_ema'] * 100).values

                label = f"{anchor} | adjust={adj} | {ema_label}"
                run_scenario(label, up, dn)

    print("\n" + "="*60)
    print("Done. Set TARGET_* variables to reference values to identify the match.")

if __name__ == "__main__":
    main()
