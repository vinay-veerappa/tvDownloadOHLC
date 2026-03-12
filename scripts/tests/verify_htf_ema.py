"""
HTF EMA Analysis - Reference Verification Script
================================================
Verifies Pine Script indicator values against Python-computed baselines.

IMPORTANT DATA OFFSET NOTE:
  Our parquet data (NQ1_1d.parquet) is Mon-Fri daily bars only.
  TradingView's weekly bar includes the Sunday 18:00 ET CME open session.
  This causes Pine's weekly HIGH to be ~0.3% higher than Python's on average.
  => Python will consistently understate upPct mean by ~0.25-0.35%.
  => Use Python for DIRECTION validation and RELATIVE comparisons, not exact matching.

CONFIRMED REFERENCE VALUES (from reference indicator screenshot, 2026-03-11):
  Symbol: NQ1!, Timeframe: 1D, Lookback: 52 weeks, Zone: 2-3%
  Mean Hi:   2.67%    Mean Lo:   2.05%
  Median Hi: 2.59%    Median Lo: 0.68%
  Mode Hi:   ~0.3%    Mode Lo:   ~0.3%   (bin=0.1, nearest-mean tiebreak)
  Open Above EMA: 70.8%  (N=48, prevWeeklyEma baseline)
  Open Below EMA: 29.2%

PINE FORMULA (confirmed correct):
  upPct  = (prevWeekHigh - weeklyEma)   / weeklyEma   * 100  [weeklyEma = [1] same week]
  dnPct  = (weeklyEma   - prevWeekLow)  / weeklyEma   * 100
  openAbove = prevWeekOpen >= prevWeeklyEma                   [prevWeeklyEma = [2] prior week]
  openLookback = i_lookbackWeeks - 4 = 48
"""
import pandas as pd
import numpy as np

DATA_PATH = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1d.parquet"
EMA_LENGTH = 5
LOOKBACK = 52
OPEN_LOOKBACK = 48   # reference uses 48 (lookback - 4)
ZONE_START = 2.0
ZONE_END   = 3.0

# ── Confirmed reference targets ──────────────────────────────────────────────
REF = {
    "mean_hi":  2.67, "mean_lo":  2.05,
    "med_hi":   2.59, "med_lo":   0.68,
    "mode_hi":  0.30, "mode_lo":  0.30,
    "open_above_pct": 70.8,
    "zone_entry_up":  59.6,
    "zone_entry_dn":  34.6,
    "zone_comp_up":   53.8,
    "zone_comp_dn":   23.1,
}
# ─────────────────────────────────────────────────────────────────────────────

def pine_median(arr):
    s = np.sort(arr)
    n = len(s)
    mid = int(np.floor(n * 0.5))
    return s[mid] if n % 2 == 1 else (s[mid-1] + s[mid]) * 0.5

def pine_mode(arr, bin_size=0.1):
    if len(arr) == 0: return np.nan
    mu = np.mean(arr)
    bins = np.round(arr / bin_size) * bin_size
    u, c = np.unique(bins, return_counts=True)
    mx = c.max()
    cands = u[c == mx]
    return float(cands[np.argmin(np.abs(cands - mu))])

def hitrate(arr, threshold):
    return np.mean(np.array(arr) >= threshold) * 100

def fmt(val, ref_val, tol=0.15):
    diff = val - ref_val
    symbol = "✓" if abs(diff) <= tol else "✗"
    return f"{val:6.2f}%  (ref {ref_val:.2f}%, diff {diff:+.2f}%) {symbol}"

def main():
    df = pd.read_parquet(DATA_PATH)
    df.index = df.index.tz_convert('US/Eastern')
    print(f"Data: {df.index[0].date()} → {df.index[-1].date()}")
    print("NOTE: Python uses Mon-Fri daily data; Pine includes Sunday session.")
    print("      Expect Python upPct to be ~0.25-0.35% lower than Pine's values.")
    print()

    weekly = df.resample('W-FRI').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna()

    ema     = weekly['close'].ewm(span=EMA_LENGTH, adjust=False).mean()
    ema_p1  = ema              # [1] same-week EMA  (Pine: weeklyEma)
    ema_p2  = ema.shift(1)    # [2] prior-week EMA (Pine: prevWeeklyEma)

    # Drop last (possibly incomplete) week, then take last 52
    data = pd.DataFrame({
        'high':   weekly['high'],
        'low':    weekly['low'],
        'open':   weekly['open'],
        'ema_p1': ema_p1,
        'ema_p2': ema_p2,
    }).dropna().iloc[:-1]

    w52 = data.iloc[-LOOKBACK:]     # N=52 for distances
    w48 = data.iloc[-OPEN_LOOKBACK:]  # N=48 for open tracking

    # ── Distance stats (Pine uses weeklyEma=[1]) ──────────────────────────────
    up = ((w52['high'] - w52['ema_p1']) / w52['ema_p1'] * 100).values
    dn = ((w52['ema_p1'] - w52['low'])  / w52['ema_p1'] * 100).values

    print("=" * 65)
    print("STATISTICAL SUMMARY  (N=52, weeklyEma=[1] for distances)")
    print("=" * 65)
    print(f"  Mean  Hi: {fmt(np.mean(up), REF['mean_hi'])}")
    print(f"  Mean  Lo: {fmt(np.mean(dn), REF['mean_lo'])}")
    print(f"  Median Hi: {fmt(pine_median(up), REF['med_hi'])}")
    print(f"  Median Lo: {fmt(pine_median(dn), REF['med_lo'])}")
    print(f"  Mode  Hi (bin=0.1): {fmt(pine_mode(up, 0.1), REF['mode_hi'])}")
    print(f"  Mode  Lo (bin=0.1): {fmt(pine_mode(dn, 0.1), REF['mode_lo'])}")

    # ── Opening position (Pine uses prevWeeklyEma=[2], N=48) ─────────────────
    open_above = (w48['open'] >= w48['ema_p2']).mean() * 100
    print()
    print(f"OPENING POSITION  (N={OPEN_LOOKBACK}, prevWeeklyEma=[2])")
    print(f"  Open Above EMA: {fmt(open_above, REF['open_above_pct'], tol=0.5)}")

    # ── Zone metrics ──────────────────────────────────────────────────────────
    print()
    print("ZONE METRICS  (zone 2-3%, weeklyEma=[1])")
    # Zone hit = EITHER high crossed above zone start OR low dipped below zone start
    # (symmetric: for upside, high >= ema*(1+zoneStart/100); downside similarly)
    # Zone logic (matches Pine): upside positive, downside negative from EMA
    # Entry ↑:    high >= ema * (1 + zoneStart/100)
    # Complete ↑: high >= ema * (1 + zoneEnd/100)
    # Entry ↓:    low  <= ema * (1 - zoneStart/100)
    # Complete ↓: low  <= ema * (1 - zoneEnd/100)
    entry_up  = (w52['high'] >= w52['ema_p1'] * (1 + ZONE_START / 100)).mean() * 100
    entry_dn  = (w52['low']  <= w52['ema_p1'] * (1 - ZONE_START / 100)).mean() * 100
    comp_up   = (w52['high'] >= w52['ema_p1'] * (1 + ZONE_END   / 100)).mean() * 100
    comp_dn   = (w52['low']  <= w52['ema_p1'] * (1 - ZONE_END   / 100)).mean() * 100

    print(f"  Zone Entry ↑: {fmt(entry_up, REF['zone_entry_up'], tol=1.5)}")
    print(f"  Zone Entry ↓: {fmt(entry_dn, REF['zone_entry_dn'], tol=1.5)}")
    print(f"  Zone Comp  ↑: {fmt(comp_up,  REF['zone_comp_up'],  tol=1.5)}")
    print(f"  Zone Comp  ↓: {fmt(comp_dn,  REF['zone_comp_dn'],  tol=1.5)}")

    print()
    print("NOTE: ✓ = within tolerance, ✗ = needs investigation")
    print("      upPct values consistently ~0.3% lower than Pine due to missing Sunday data.")

if __name__ == "__main__":
    main()
