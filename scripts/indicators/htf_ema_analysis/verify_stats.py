"""
Verify HTF EMA Analysis indicator statistics against TradingView OHLC exports.

Replicates the Pine Script logic in Python to identify data drift.

Pine Script offsets (on "W" timeframe):
  weeklyEma     = ta.ema(close, 5)[1]  → EMA at close of PREVIOUS week
  prevWeeklyEma = ta.ema(close, 5)[2]  → EMA at close of 2 WEEKS AGO
  prevWeekHigh  = high[1]              → previous week's high
  prevWeekLow   = low[1]              → previous week's low
  prevWeekOpen  = open[1]             → previous week's open

Weekly stats use: prevWeekHigh/Low vs prevWeeklyEma
  upPct = max(0, (prevWeekHigh - prevWeeklyEma) / prevWeeklyEma * 100)
  dnPct = max(0, (prevWeeklyEma - prevWeekLow) / prevWeeklyEma * 100)

DOW stats use: yesterday's daily H/L vs weeklyEma
  dUp = max(0, (dHighPrev - weeklyEma) / weeklyEma * 100)
  dDn = max(0, (weeklyEma - dLowPrev) / weeklyEma * 100)
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")
SCRIPT_DIR = Path(__file__).parent

# ─── Config (must match Pine defaults) ───
EMA_LENGTH = 5
LOOKBACK_WEEKS = 52
ZONE_START_PCT = 2.0
ZONE_END_PCT = 3.0
MODE_BIN_SIZE = 0.1


def ema(series: pd.Series, length: int) -> pd.Series:
    """Replicate Pine's ta.ema exactly (same as pandas ewm with adjust=False)."""
    return series.ewm(span=length, adjust=False).mean()


def mode_nearest_mean(arr, bin_size):
    """Replicate f_mode_nearest_mean: bin values, find mode, break ties by closest to mean.
    Filters out zeros (like our Pine implementation)."""
    filtered = arr[arr > 0.001]
    if len(filtered) == 0:
        return np.nan
    mu = filtered.mean()
    bins = np.round(filtered / bin_size) * bin_size
    from collections import Counter
    counts = Counter(bins)
    max_count = max(counts.values())
    candidates = [b for b, c in counts.items() if c == max_count]
    best = min(candidates, key=lambda x: abs(x - mu))
    return best


def mode_nearest_mean_all(arr, bin_size):
    """Same as mode_nearest_mean but INCLUDES zeros in binning."""
    if len(arr) == 0:
        return np.nan
    mu = arr.mean()
    bins = np.round(arr / bin_size) * bin_size
    from collections import Counter
    counts = Counter(bins)
    max_count = max(counts.values())
    candidates = [b for b, c in counts.items() if c == max_count]
    best = min(candidates, key=lambda x: abs(x - mu))
    return best


def mode_bin(arr, bin_size, include_zeros=True):
    """Return the most frequent BIN lower-edge and count.
    Mode here is the bin where values occur (histogram bin), not a raw sample value.
    """
    if len(arr) == 0:
        return np.nan, 0
    vals = np.array(arr, dtype=float)
    if not include_zeros:
        vals = vals[vals > 0.001]
    if len(vals) == 0:
        return np.nan, 0
    bins = np.floor(vals / bin_size) * bin_size
    uniq, counts = np.unique(np.round(bins, 10), return_counts=True)
    idx = int(np.argmax(counts))
    return float(uniq[idx]), int(counts[idx])


def hitrate_level(arr, level):
    """% of values >= level."""
    if len(arr) == 0:
        return np.nan
    return (arr >= level).sum() / len(arr) * 100


def hits_at_level(arr, level):
    return (arr >= level).sum()


def load_weekly():
    f = SCRIPT_DIR / "CME_MINI_NQ1!, 1W_f166a.csv"
    df = pd.read_csv(f)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET)
    df = df.sort_values("datetime").reset_index(drop=True)
    df["ema5"] = ema(df["close"], EMA_LENGTH)
    return df


def load_daily():
    f = SCRIPT_DIR / "CME_MINI_NQ1!, 1D_a1cee.csv"
    df = pd.read_csv(f)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET)
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def weekly_stats(wdf: pd.DataFrame):
    """Replicate the Pine weekly data collection block.
    
    For week index i (the current week on chart):
      prevWeeklyEma = ema[i-2]  (EMA known at start of prev week)
      prevWeekHigh  = high[i-1]
      prevWeekLow   = low[i-1]
      prevWeekOpen  = open[i-1]
      
    We measure prev week's H/L distance from the EMA that was known
    at the START of that week (= ema at close of the week before it).
    """
    records = []
    for i in range(2, len(wdf)):
        prev_ema = wdf.loc[i - 2, "ema5"]       # prevWeeklyEma = [2]
        curr_ema = wdf.loc[i - 1, "ema5"]        # weeklyEma     = [1]
        prev_high = wdf.loc[i - 1, "high"]       # high[1]
        prev_low = wdf.loc[i - 1, "low"]         # low[1]
        prev_open = wdf.loc[i - 1, "open"]       # open[1]
        week_dt = wdf.loc[i, "datetime"]          # current week start

        if np.isnan(prev_ema) or np.isnan(curr_ema):
            continue

        up_pct = max(0.0, (prev_high - prev_ema) / prev_ema * 100)
        dn_pct = max(0.0, (prev_ema - prev_low) / prev_ema * 100)
        open_above = prev_open >= prev_ema

        records.append({
            "week_start": week_dt,
            "prev_high": prev_high,
            "prev_low": prev_low,
            "prev_open": prev_open,
            "prev_ema": prev_ema,
            "curr_ema": curr_ema,
            "up_pct": up_pct,
            "dn_pct": dn_pct,
            "open_above": open_above,
        })

    df = pd.DataFrame(records)
    return df


def dow_stats(ddf: pd.DataFrame, wdf: pd.DataFrame):
    """Test multiple DOW collection strategies to find which matches the reference.
    
    Labeling:
      close_day: bar's close DOW (Sun bar → Mon, Mon bar → Tue, ...)
      session_name: trading session name (Sun bar → Mon session, Mon bar → Tue session, ...)
        For CME futures, close_day == session_name, so they're equivalent.
    
    EMA variants:
      EMA[1]: weeklyEma = ema at close of PREVIOUS week (our Pine DOW logic)
      EMA[2]: prevWeeklyEma = ema at close of 2 weeks ago (our Pine WEEKLY logic)
      EMA[0]: currentWeekEma = ema at close of CURRENT week (lookahead)
    
    HL source:
      prev: previous bar's H/L (Pine uses this with isNewDay trigger)
      own: each bar's own H/L
    """
    wdf = wdf.copy()
    ddf = ddf.copy()
    ddf["dow"] = ddf["datetime"].dt.dayofweek  # Mon=0 .. Sun=6
    
    # Build EMA maps for all three offsets
    # EMA[1]: ema at close of previous week
    ema1_map = []  # (start, end, ema_value)
    for i in range(1, len(wdf)):
        start = wdf.loc[i, "datetime"]
        end = wdf.loc[i + 1, "datetime"] if i + 1 < len(wdf) else pd.Timestamp("2030-01-01", tz=ET)
        ema1_map.append((start, end, wdf.loc[i - 1, "ema5"]))
    
    # EMA[2]: ema at close of 2 weeks ago
    ema2_map = []
    for i in range(2, len(wdf)):
        start = wdf.loc[i, "datetime"]
        end = wdf.loc[i + 1, "datetime"] if i + 1 < len(wdf) else pd.Timestamp("2030-01-01", tz=ET)
        ema2_map.append((start, end, wdf.loc[i - 2, "ema5"]))
    
    # EMA[0]: ema at close of CURRENT week (lookahead)
    ema0_map = []
    for i in range(len(wdf)):
        start = wdf.loc[i, "datetime"]
        end = wdf.loc[i + 1, "datetime"] if i + 1 < len(wdf) else pd.Timestamp("2030-01-01", tz=ET)
        ema0_map.append((start, end, wdf.loc[i, "ema5"]))
    
    def lookup_ema(dt, ema_map):
        for start, end, ema_val in ema_map:
            if start <= dt < end:
                return ema_val
        return np.nan
    
    ddf["ema1"] = ddf["datetime"].apply(lambda dt: lookup_ema(dt, ema1_map))
    ddf["ema2"] = ddf["datetime"].apply(lambda dt: lookup_ema(dt, ema2_map))
    ddf["ema0"] = ddf["datetime"].apply(lambda dt: lookup_ema(dt, ema0_map))
    
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    
    def day_idx_close(bar_dow_py):
        """Map close day (open_dow+1)%7 to bucket index."""
        close_dow = (bar_dow_py + 1) % 7
        if close_dow == 0 or close_dow == 6:  return 0  # Mon or Sun close → Mon
        elif close_dow == 1:  return 1
        elif close_dow == 2:  return 2
        elif close_dow == 3:  return 3
        elif close_dow == 4:  return 4
        return -1

    idx_names = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
    last_week_start = wdf.iloc[-1]["datetime"]
    
    def make_empty():
        return {name: {"up": [], "dn": [], "dn_abs": []} for name in day_names}
    
    def collect_own_hl_closeday(ema_col):
        """Own bar's H/L, labeled by bar's close day, using specified EMA column."""
        result = make_empty()
        for i in range(len(ddf)):
            bar = ddf.iloc[i]
            if bar["datetime"] >= last_week_start:
                continue
            wk_ema = bar[ema_col]
            if np.isnan(wk_ema):
                continue
            idx = day_idx_close(bar["dow"])
            if idx >= 0:
                d_up = max(0.0, (bar["high"] - wk_ema) / wk_ema * 100)
                d_dn = max(0.0, (wk_ema - bar["low"]) / wk_ema * 100)
                d_dn_abs = abs(wk_ema - bar["low"]) / wk_ema * 100
                result[idx_names[idx]]["up"].append(d_up)
                result[idx_names[idx]]["dn"].append(d_dn)
                result[idx_names[idx]]["dn_abs"].append(d_dn_abs)
        return result
    
    def collect_prev_hl_closeday(ema_col):
        """Previous bar's H/L, labeled by prev bar's close day, using specified EMA column."""
        result = make_empty()
        for i in range(1, len(ddf)):
            prev = ddf.iloc[i - 1]
            curr = ddf.iloc[i]
            if curr["datetime"] >= last_week_start:
                continue
            wk_ema = curr[ema_col]
            if np.isnan(wk_ema):
                continue
            idx = day_idx_close(prev["dow"])
            if idx >= 0:
                d_up = max(0.0, (prev["high"] - wk_ema) / wk_ema * 100)
                d_dn = max(0.0, (wk_ema - prev["low"]) / wk_ema * 100)
                d_dn_abs = abs(wk_ema - prev["low"]) / wk_ema * 100
                result[idx_names[idx]]["up"].append(d_up)
                result[idx_names[idx]]["dn"].append(d_dn)
                result[idx_names[idx]]["dn_abs"].append(d_dn_abs)
        return result

    strategies = {
        "S1_prevHL_EMA1":   collect_prev_hl_closeday("ema1"),   # Our Pine DOW logic
        "S3_ownHL_EMA1":    collect_own_hl_closeday("ema1"),    # Own HL, same EMA
        "S5_ownHL_EMA2":    collect_own_hl_closeday("ema2"),    # Own HL, prevWeeklyEma
        "S6_ownHL_EMA0":    collect_own_hl_closeday("ema0"),    # Own HL, current week EMA (lookahead)
        "S7_prevHL_EMA2":   collect_prev_hl_closeday("ema2"),   # Prev HL, prevWeeklyEma
        "S8_prevHL_EMA0":   collect_prev_hl_closeday("ema0"),   # Prev HL, current week EMA (lookahead)
    }
    return strategies


def print_weekly_report(ws: pd.DataFrame):
    # Take last LOOKBACK_WEEKS
    ws_lb = ws.tail(LOOKBACK_WEEKS).reset_index(drop=True)
    
    up = ws_lb["up_pct"].values
    dn = ws_lb["dn_pct"].values
    open_above = ws_lb["open_above"].values
    
    up_nz = up[up > 0.001]
    dn_nz = dn[dn > 0.001]
    
    # Distribution diagnostics
    print("=" * 70)
    print("DISTRIBUTION DIAGNOSTICS")
    print("=" * 70)
    print(f"Total samples: {len(up)}")
    print(f"Up zeros (<=0.001): {(up <= 0.001).sum()}, Nonzero: {len(up_nz)}")
    print(f"Dn zeros (<=0.001): {(dn <= 0.001).sum()}, Nonzero: {len(dn_nz)}")
    print()
    print("Up% sorted:", " ".join(f"{v:.2f}" for v in sorted(up)))
    print()
    print("Dn% sorted:", " ".join(f"{v:.2f}" for v in sorted(dn)))
    print()
    
    # ── Approach A: mean/median on NON-ZERO only (our Pine does this) ──
    up_mean_nz = np.mean(up_nz) if len(up_nz) > 0 else np.nan
    up_median_nz = np.median(up_nz) if len(up_nz) > 0 else np.nan
    dn_mean_nz = np.mean(dn_nz) if len(dn_nz) > 0 else np.nan
    dn_median_nz = np.median(dn_nz) if len(dn_nz) > 0 else np.nan

    # ── Approach B: mean/median on ALL values including zeros ──
    up_mean_all = np.mean(up)
    up_median_all = np.median(up)
    dn_mean_all = np.mean(dn)
    dn_median_all = np.median(dn)

    # ── Mode: test both with and without zeros ──
    up_mode_nz = mode_nearest_mean(up, MODE_BIN_SIZE)        # filters zeros internally
    dn_mode_nz = mode_nearest_mean(dn, MODE_BIN_SIZE)
    up_mode_all = mode_nearest_mean_all(up, MODE_BIN_SIZE)    # includes zeros
    dn_mode_all = mode_nearest_mean_all(dn, MODE_BIN_SIZE)
    
    zone_entry_up = hitrate_level(up, ZONE_START_PCT)
    zone_entry_dn = hitrate_level(dn, ZONE_START_PCT)
    zone_comp_up = hitrate_level(up, ZONE_END_PCT)
    zone_comp_dn = hitrate_level(dn, ZONE_END_PCT)
    
    hits_up = hits_at_level(up, ZONE_START_PCT)
    hits_dn = hits_at_level(dn, ZONE_START_PCT)
    comp_up = hits_at_level(up, ZONE_END_PCT)
    comp_dn = hits_at_level(dn, ZONE_END_PCT)
    conv_up = (comp_up / hits_up * 100) if hits_up > 0 else 0
    conv_dn = (comp_dn / hits_dn * 100) if hits_dn > 0 else 0
    
    # Open stats (Pine uses lookback - 4)
    open_lb = max(1, LOOKBACK_WEEKS - 4)
    open_arr = open_above[-open_lb:]
    pct_above = np.sum(open_arr) / len(open_arr) * 100 if len(open_arr) > 0 else 0
    
    # ── Reference data ──
    REF = {
        "mean_hi": 2.67, "mean_lo": 2.05,
        "med_hi": 2.59, "med_lo": 0.68,
        "mode_hi": 0.3, "mode_lo": 0.3,
    }

    print("=" * 70)
    print("COMPARISON: Which approach matches the reference?")
    print("=" * 70)
    print(f"{'Stat':<20} {'Ref':>8} {'NZ-only':>8} {'All':>8} {'NZ delta':>9} {'All delta':>9} {'Winner':>8}")
    print("-" * 72)
    rows = [
        ("Mean High", REF["mean_hi"], up_mean_nz, up_mean_all),
        ("Mean Low", REF["mean_lo"], dn_mean_nz, dn_mean_all),
        ("Median High", REF["med_hi"], up_median_nz, up_median_all),
        ("Median Low", REF["med_lo"], dn_median_nz, dn_median_all),
        ("Mode High", REF["mode_hi"], up_mode_nz, up_mode_all),
        ("Mode Low", REF["mode_lo"], dn_mode_nz, dn_mode_all),
    ]
    for label, ref, nz, all_v in rows:
        d_nz = nz - ref if not np.isnan(nz) else float('inf')
        d_all = all_v - ref if not np.isnan(all_v) else float('inf')
        winner = "ALL" if abs(d_all) < abs(d_nz) else "NZ" if abs(d_nz) < abs(d_all) else "TIE"
        fmt = "#.2f" if "mode" not in label.lower() else "#.1f"
        nz_s = f"{nz:.2f}" if not np.isnan(nz) else "nan"
        all_s = f"{all_v:.2f}" if not np.isnan(all_v) else "nan"
        print(f"{label:<20} {ref:>8.2f} {nz_s:>8} {all_s:>8} {d_nz:>+9.2f} {d_all:>+9.2f} {winner:>8}")
    print()
    
    print(f"Zone Entry      ↑ {zone_entry_up:>5.1f}%  ↓ {zone_entry_dn:>5.1f}%  (Ref: 59.6% / 34.6%)")
    print(f"Zone Complete   ↑ {zone_comp_up:>5.1f}%  ↓ {zone_comp_dn:>5.1f}%  (Ref: 46.2% / 23.1%)")
    print(f"Completion Rate ↑ {conv_up:>5.1f}%  ↓ {conv_dn:>5.1f}%  (Ref: 77.4% / 66.7%)")
    print(f"Open Above EMA: {pct_above:.1f}% ({int(np.sum(open_arr))}/{len(open_arr)})  (Ref: 70.8%)")
    print()
    
    # Print last 5 weeks for debugging
    print()
    print("=" * 70)
    print("LAST 10 WEEKLY SAMPLES (for debugging)")
    print("=" * 70)
    print(f"{'Week Start':<22} {'PrevEMA':>10} {'PrevHigh':>10} {'PrevLow':>10} {'UpPct':>8} {'DnPct':>8} {'Open':>10} {'Above?':>7}")
    for _, r in ws_lb.tail(10).iterrows():
        print(f"{str(r['week_start'])[:19]:<22} {r['prev_ema']:>10.2f} {r['prev_high']:>10.2f} {r['prev_low']:>10.2f} {r['up_pct']:>7.2f}% {r['dn_pct']:>7.2f}% {r['prev_open']:>10.2f} {'YES' if r['open_above'] else 'NO':>7}")


def print_dow_report(strategies: dict):
    print()
    print("=" * 70)
    print("DOW STRATEGY COMPARISON (Hit↑, Hit↓, Complete↑, Complete↓)")
    print("=" * 70)
    
    # Reference DOW data (from closed-source indicator)
    ref_dow = {
        "Mon": {"h_up": 42.3, "h_dn": 19.2, "c_up": 36.5, "c_dn": 23.1, "mn_hi": 1.38, "mn_lo": 2.28, "md_hi": 1.74, "md_lo": 0.53},
        "Tue": {"h_up": 55.8, "h_dn": 25.0, "c_up": 42.3, "c_dn": 25.0, "mn_hi": 1.84, "mn_lo": 2.33, "md_hi": 2.21, "md_lo": 0.63},
        "Wed": {"h_up": 57.7, "h_dn": 34.6, "c_up": 55.8, "c_dn": 34.6, "mn_hi": 1.74, "mn_lo": 2.62, "md_hi": 2.23, "md_lo": 0.35},
        "Thu": {"h_up": 44.2, "h_dn": 36.5, "c_up": 55.8, "c_dn": 28.8, "mn_hi": 1.37, "mn_lo": 2.85, "md_hi": 1.75, "md_lo": 0.32},
    }

    header = f"{'Day':<6} {'Hit↑':>7} {'Hit↓':>7} {'Cmp↑':>7} {'Cmp↓':>7} {'MnHi':>7} {'MnLo':>7} {'MdHi':>7} {'MdLo':>7} {'MoHi':>8} {'MoLo':>8} {'N':>4}"

    best_strat = "S3_ownHL_EMA1"
    if best_strat not in strategies:
        return

    day_data = strategies[best_strat]
    for name in day_data:
        day_data[name]["up"] = day_data[name]["up"][-LOOKBACK_WEEKS:]
        day_data[name]["dn"] = day_data[name]["dn"][-LOOKBACK_WEEKS:]
        day_data[name]["dn_abs"] = day_data[name]["dn_abs"][-LOOKBACK_WEEKS:]

    print(f"\n--- {best_strat}: using absolute low extension distance ---")
    print("Complete is computed as extension >= 3.0%.")
    print(header)
    print("-" * len(header))

    def fmt(v, p=2):
        return "-" if np.isnan(v) else f"{v:.{p}f}"

    for name in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
        u = np.array(day_data[name]["up"])
        d = np.array(day_data[name]["dn_abs"])
        n = len(u)
        if n == 0:
            print(f"{name:<6} {'-':>7} {'-':>7} {'-':>7} {'-':>7} {'-':>7} {'-':>7} {'-':>7} {'-':>7} {'-':>8} {'-':>8} {0:>4}")
            continue

        mo_hi, _ = mode_bin(u, MODE_BIN_SIZE, include_zeros=True)
        mo_lo, _ = mode_bin(d, MODE_BIN_SIZE, include_zeros=True)
        mo_hi_lbl = f"{mo_hi:.1f}-{(mo_hi + MODE_BIN_SIZE):.1f}" if not np.isnan(mo_hi) else "-"
        mo_lo_lbl = f"{mo_lo:.1f}-{(mo_lo + MODE_BIN_SIZE):.1f}" if not np.isnan(mo_lo) else "-"

        print(
            f"{name:<6} "
            f"{hitrate_level(u, ZONE_START_PCT):>6.1f}% "
            f"{hitrate_level(d, ZONE_START_PCT):>6.1f}% "
            f"{hitrate_level(u, ZONE_END_PCT):>6.1f}% "
            f"{hitrate_level(d, ZONE_END_PCT):>6.1f}% "
            f"{fmt(np.mean(u)):>7} {fmt(np.mean(d)):>7} {fmt(np.median(u)):>7} {fmt(np.median(d)):>7} "
            f"{mo_hi_lbl:>8} {mo_lo_lbl:>8} {n:>4}"
        )

    print(f"\n--- Reference rows provided ---")
    print(f"{'Day':<6} {'Hit↑':>7} {'Hit↓':>7} {'Cmp↑':>7} {'Cmp↓':>7} {'MnHi':>7} {'MnLo':>7} {'MdHi':>7} {'MdLo':>7}")
    print("-" * 76)
    for name in ["Mon", "Tue", "Wed", "Thu"]:
        rv = ref_dow[name]
        print(
            f"{name:<6} {rv['h_up']:>6.1f}% {rv['h_dn']:>6.1f}% {rv['c_up']:>6.1f}% {rv['c_dn']:>6.1f}% "
            f"{rv['mn_hi']:>7.2f} {rv['mn_lo']:>7.2f} {rv['md_hi']:>7.2f} {rv['md_lo']:>7.2f}"
        )

    print(f"\n--- Day-shift check (current day and +1 day) against provided Thursday row ---")
    thu_ref = ref_dow["Thu"]
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    print(f"{'CalcDay':<7} {'ShiftedTo':<9} {'Hit↑':>7} {'Hit↓':>7} {'Cmp↑':>7} {'Cmp↓':>7} {'MnHi':>7} {'MnLo':>7} {'MdHi':>7} {'MdLo':>7}")
    print("-" * 88)
    for i, day in enumerate(days):
        u = np.array(day_data[day]["up"])
        d = np.array(day_data[day]["dn_abs"])
        if len(u) == 0:
            continue
        shifted = days[(i + 1) % len(days)]
        print(
            f"{day:<7} {shifted:<9} "
            f"{hitrate_level(u, ZONE_START_PCT):>6.1f}% {hitrate_level(d, ZONE_START_PCT):>6.1f}% "
            f"{hitrate_level(u, ZONE_END_PCT):>6.1f}% {hitrate_level(d, ZONE_END_PCT):>6.1f}% "
            f"{np.mean(u):>7.2f} {np.mean(d):>7.2f} {np.median(u):>7.2f} {np.median(d):>7.2f}"
        )

    print("\nReference Thu:")
    print(
        f"Hit↑={thu_ref['h_up']:.1f}% Hit↓={thu_ref['h_dn']:.1f}% Cmp↑={thu_ref['c_up']:.1f}% Cmp↓={thu_ref['c_dn']:.1f}% "
        f"MnHi={thu_ref['mn_hi']:.2f} MnLo={thu_ref['mn_lo']:.2f} MdHi={thu_ref['md_hi']:.2f} MdLo={thu_ref['md_lo']:.2f}"
    )


def main():
    print("Loading data...")
    wdf = load_weekly()
    ddf = load_daily()
    print(f"Weekly rows: {len(wdf)}, Daily rows: {len(ddf)}")
    print(f"Weekly range: {wdf.iloc[0]['datetime']} -> {wdf.iloc[-1]['datetime']}")
    print(f"Daily range:  {ddf.iloc[0]['datetime']} -> {ddf.iloc[-1]['datetime']}")
    print()

    ws = weekly_stats(wdf)
    print(f"Weekly samples generated: {len(ws)}")
    print_weekly_report(ws)
    
    day_data = dow_stats(ddf, wdf)
    print_dow_report(day_data)


if __name__ == "__main__":
    main()
