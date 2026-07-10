"""
First Presented FVG/OB Analyzer -- v5.1 (Optimized)
=====================================================
Same logic as v5 but with critical performance optimizations:
  - Inner loops use numpy arrays instead of DataFrame iteration
  - MSS detection pre-computed on rolling basis
  - Zone interaction pre-filtered using vectorized operations
  - Swing points computed once, reused everywhere
"""

import pandas as pd
import numpy as np
import os
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

# --- Constants ---
DATA_DIR = Path("data")
OUTPUT_DIR = Path("docs/first_presented_stats")

TRADE_HORIZONS = {'1H': 60, '2H': 120, '3H': 180}
MIN_STOP_PTS = 4.0
MAX_STOP_PTS = 80.0
ZONE_EXPIRY_HOUR = 16

SESSIONS = {
    'Asia':   (18, 23),
    'London': (2, 5),
    'NY_AM':  (9, 12),
    'Lunch':  (12, 14),
    'NY_PM':  (14, 16),
}

TP_PCTS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
SL_PCTS = [0.05, 0.10, 0.15, 0.20, 0.30]

SWING_LOOKBACK = 3
COOLDOWN_BARS = 5
MAX_TRADES_PER_ZONE = 4
MSS_LOOKBACK = 30  # bars to look back for MSS


def get_session(hour):
    for name, (s, e) in SESSIONS.items():
        if s <= e:
            if s <= hour < e: return name
        else:
            if hour >= s or hour < e: return name
    return 'Other'


def compute_displacement(df):
    df = df.copy()
    df['body'] = abs(df['close'] - df['open'])
    df['session'] = df.index.map(lambda x: get_session(x.hour))
    df['avg_body'] = (
        df.groupby('session')['body']
          .transform(lambda x: x.rolling(20, min_periods=5).mean())
    )
    fallback = df['body'].rolling(20, min_periods=5).mean()
    df['avg_body'] = df['avg_body'].fillna(fallback)
    df['is_displacement'] = (df['body'] > 2.0 * df['avg_body']) & (df['body'] > 0)
    return df


def compute_levels(df):
    df = df.copy()
    hourly = df.resample('1h').agg({'high':'max','low':'min'}).dropna()
    hourly['prev_hour_high'] = hourly['high'].shift(1)
    hourly['prev_hour_low'] = hourly['low'].shift(1)
    df['hour_key'] = df.index.floor('h')
    for col in ['prev_hour_high','prev_hour_low']:
        df[col] = df['hour_key'].map(hourly[col].to_dict())

    daily = df.resample('D').agg({'high':'max','low':'min'}).dropna()
    daily['pdh'] = daily['high'].shift(1)
    daily['pdl'] = daily['low'].shift(1)
    df['day_key'] = df.index.normalize()
    df['pdh'] = df['day_key'].map(daily['pdh'].to_dict())
    df['pdl'] = df['day_key'].map(daily['pdl'].to_dict())
    df = df.drop(columns=['hour_key','day_key'], inplace=False)
    return df


def compute_swing_and_mss(highs, lows, lb=SWING_LOOKBACK):
    """
    Pre-compute swing points AND rolling MSS flags for the entire array.
    Returns:
      swing_highs: array of swing high prices (NaN where not)
      swing_lows: array of swing low prices (NaN where not)
      mss_bull: array of bools - True where bullish MSS detected in recent bars
      mss_bear: array of bools - True where bearish MSS detected in recent bars
    """
    n = len(highs)
    swing_highs = np.full(n, np.nan)
    swing_lows = np.full(n, np.nan)

    # Detect swing points
    for i in range(lb, n - lb):
        is_sh = True
        is_sl = True
        for j in range(1, lb + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_sh = False
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_sl = False
            if not is_sh and not is_sl:
                break
        if is_sh:
            swing_highs[i] = highs[i]
        if is_sl:
            swing_lows[i] = lows[i]

    # Pre-compute rolling MSS
    mss_bull = np.zeros(n, dtype=bool)
    mss_bear = np.zeros(n, dtype=bool)

    # Track last confirmed swing high/low and their indices
    last_sh_val = np.nan
    last_sh_idx = -1
    last_sl_val = np.nan
    last_sl_idx = -1

    for i in range(n):
        # Update last swing points (only confirmed ones, with lb bars of confirmation)
        check_idx = i - lb  # The swing at check_idx is confirmed at bar i
        if check_idx >= 0:
            if not np.isnan(swing_highs[check_idx]):
                last_sh_val = swing_highs[check_idx]
                last_sh_idx = check_idx
            if not np.isnan(swing_lows[check_idx]):
                last_sl_val = swing_lows[check_idx]
                last_sl_idx = check_idx

        # Bullish MSS: current bar breaks above last swing high
        if not np.isnan(last_sh_val) and (i - last_sh_idx) <= MSS_LOOKBACK:
            if highs[i] > last_sh_val:
                mss_bull[i] = True

        # Bearish MSS: current bar breaks below last swing low
        if not np.isnan(last_sl_val) and (i - last_sl_idx) <= MSS_LOOKBACK:
            if lows[i] < last_sl_val:
                mss_bear[i] = True

    return swing_highs, swing_lows, mss_bull, mss_bear


def find_fvg(subset):
    if len(subset) < 3: return None
    idf = subset.reset_index()
    for i in range(2, len(idf)):
        if not idf.at[i-1, 'is_displacement']: continue
        c1_open, c1_close = idf.at[i-1, 'open'], idf.at[i-1, 'close']
        if c1_close > c1_open:
            gap_low, gap_high = idf.at[i-2, 'high'], idf.at[i, 'low']
            if gap_high > gap_low:
                return {'type': 'Bullish FVG', 'time': idf.at[i, 'datetime'],
                        'zone_high': gap_high, 'zone_low': gap_low,
                        'original_dir': 'long'}
        elif c1_close < c1_open:
            gap_high, gap_low = idf.at[i-2, 'low'], idf.at[i, 'high']
            if gap_low < gap_high:
                return {'type': 'Bearish FVG', 'time': idf.at[i, 'datetime'],
                        'zone_high': gap_high, 'zone_low': gap_low,
                        'original_dir': 'short'}
    return None


def find_ob(subset):
    if len(subset) < 3: return None
    idf = subset.reset_index()
    for i in range(2, len(idf)):
        if not idf.at[i-1, 'is_displacement']: continue
        if idf.at[i-1, 'close'] > idf.at[i-1, 'open']:
            if idf.at[i-2, 'close'] < idf.at[i-2, 'open']:
                return {'type': 'Bullish OB', 'time': idf.at[i-1, 'datetime'],
                        'zone_high': idf.at[i-2, 'high'], 'zone_low': idf.at[i-2, 'low'],
                        'original_dir': 'long'}
        elif idf.at[i-1, 'close'] < idf.at[i-1, 'open']:
            if idf.at[i-2, 'close'] > idf.at[i-2, 'open']:
                return {'type': 'Bearish OB', 'time': idf.at[i-1, 'datetime'],
                        'zone_high': idf.at[i-2, 'high'], 'zone_low': idf.at[i-2, 'low'],
                        'original_dir': 'short'}
    return None


def simulate_pct_trade_numpy(entry_price, is_long, bar_highs, bar_lows, bar_opens, max_horizon):
    """
    Pure numpy trade simulation. No pandas overhead.
    bar_highs/lows/opens are numpy arrays starting from the entry bar.
    """
    n_bars = min(len(bar_highs), max_horizon + 1)
    if n_bars == 0:
        return None

    tp_levels = {}
    sl_levels = {}
    for tp in TP_PCTS:
        tp_levels[tp] = entry_price * (1 + tp/100) if is_long else entry_price * (1 - tp/100)
    for sl in SL_PCTS:
        sl_levels[sl] = entry_price * (1 - sl/100) if is_long else entry_price * (1 + sl/100)

    # Vectorized MFE/MAE
    if is_long:
        favor = bar_highs[:n_bars] - entry_price
        adverse = entry_price - bar_lows[:n_bars]
    else:
        favor = entry_price - bar_lows[:n_bars]
        adverse = bar_highs[:n_bars] - entry_price

    favor = np.maximum(favor, 0)
    adverse = np.maximum(adverse, 0)

    cum_mfe = np.maximum.accumulate(favor)
    cum_mae = np.maximum.accumulate(adverse)

    result = {}

    # Horizon snapshots
    for h_label, h_bars in TRADE_HORIZONS.items():
        idx = min(h_bars, n_bars - 1)
        result[f'mfe_pct_{h_label}'] = (cum_mfe[idx] / entry_price) * 100 if entry_price > 0 else 0
        result[f'mae_pct_{h_label}'] = (cum_mae[idx] / entry_price) * 100 if entry_price > 0 else 0

    # TP/SL first-hit detection (vectorized)
    tp_first_bar = {}
    sl_first_bar = {}

    for tp in TP_PCTS:
        if is_long:
            hits = np.where(bar_highs[:n_bars] >= tp_levels[tp])[0]
        else:
            hits = np.where(bar_lows[:n_bars] <= tp_levels[tp])[0]
        tp_first_bar[tp] = int(hits[0]) if len(hits) > 0 else None

    for sl in SL_PCTS:
        if is_long:
            hits = np.where(bar_lows[:n_bars] <= sl_levels[sl])[0]
        else:
            hits = np.where(bar_highs[:n_bars] >= sl_levels[sl])[0]
        sl_first_bar[sl] = int(hits[0]) if len(hits) > 0 else None

    # Store bar indices
    for tp in TP_PCTS:
        result[f'tp_{tp}_bar'] = tp_first_bar[tp]
    for sl in SL_PCTS:
        result[f'sl_{sl}_bar'] = sl_first_bar[sl]

    # Outcomes
    for h_label, h_bars in TRADE_HORIZONS.items():
        for tp in TP_PCTS:
            for sl in SL_PCTS:
                tp_b = tp_first_bar[tp]
                sl_b = sl_first_bar[sl]
                tp_in = tp_b if (tp_b is not None and tp_b <= h_bars) else None
                sl_in = sl_b if (sl_b is not None and sl_b <= h_bars) else None
                if tp_in is not None and sl_in is not None:
                    outcome = 'win' if tp_in < sl_in else 'loss'
                elif tp_in is not None:
                    outcome = 'win'
                elif sl_in is not None:
                    outcome = 'loss'
                else:
                    outcome = 'timeout'
                result[f'o_{h_label}_{tp}_{sl}'] = outcome

    # Return the earliest exit bar for cooldown calculation
    ref_tp = tp_first_bar.get(0.10)
    ref_sl = sl_first_bar.get(0.30)
    exit_bar = 60
    if ref_tp is not None and ref_tp < exit_bar: exit_bar = ref_tp
    if ref_sl is not None and ref_sl < exit_bar: exit_bar = ref_sl
    result['_exit_bar'] = exit_bar

    return result


def process_day(args):
    date_val, chunk_df = args
    if len(chunk_df) < 60:
        return []

    day_results = []
    day_only = chunk_df[chunk_df.index.date == date_val]
    if day_only.empty:
        return []

    day_anchor = day_only.index[0]

    try:
        expiry_time = day_anchor.normalize().replace(hour=ZONE_EXPIRY_HOUR)
        if expiry_time <= day_anchor:
            expiry_time += timedelta(days=1)
    except Exception:
        expiry_time = day_anchor + timedelta(hours=20)

    # Pre-extract numpy arrays for the full chunk (MUCH faster than DataFrame access)
    full_highs = chunk_df['high'].values
    full_lows = chunk_df['low'].values
    full_opens = chunk_df['open'].values
    full_closes = chunk_df['close'].values
    full_times = chunk_df.index
    n_total = len(full_highs)

    # Pre-compute MSS for entire chunk
    _, _, mss_bull, mss_bear = compute_swing_and_mss(full_highs, full_lows)

    # Pre-extract level arrays
    ph_high = chunk_df['prev_hour_high'].values if 'prev_hour_high' in chunk_df.columns else np.full(n_total, np.nan)
    ph_low = chunk_df['prev_hour_low'].values if 'prev_hour_low' in chunk_df.columns else np.full(n_total, np.nan)
    pdh_arr = chunk_df['pdh'].values if 'pdh' in chunk_df.columns else np.full(n_total, np.nan)
    pdl_arr = chunk_df['pdl'].values if 'pdl' in chunk_df.columns else np.full(n_total, np.nan)

    # Build time-to-index mapping for fast lookups
    time_to_idx = {t: i for i, t in enumerate(full_times)}

    # 1. Discover zones
    zones = []
    seen = set()

    for h in range(24):
        try:
            window_start = day_anchor.normalize().replace(hour=h, minute=0, second=0)
        except Exception:
            continue

        window_end = window_start + timedelta(hours=1)
        discovery = chunk_df[(chunk_df.index >= window_start) & (chunk_df.index < window_end)]
        if len(discovery) < 5:
            continue

        for find_fn, cat in [(find_fvg, 'FVG'), (find_ob, 'OB')]:
            setup = find_fn(discovery)
            if setup is None:
                continue

            sid = f"{setup['type']}_{setup['time']}_{setup['zone_high']:.2f}"
            if sid in seen:
                continue
            seen.add(sid)

            zones.append({
                'zone_high': setup['zone_high'],
                'zone_low': setup['zone_low'],
                'original_dir': setup['original_dir'],
                'setup_type': setup['type'],
                'category': cat,
                'discovery_time': setup['time'],
                'discovery_hour': h,
                'session_name': get_session(h),
            })

    if not zones:
        return []

    max_horizon = max(TRADE_HORIZONS.values())

    # 2. For each zone, scan using numpy arrays
    for zone in zones:
        zh = zone['zone_high']
        zl = zone['zone_low']

        # Find start index in the full array
        disc_time = zone['discovery_time']
        if disc_time not in time_to_idx:
            # Find nearest
            start_idx = np.searchsorted(full_times, disc_time)
        else:
            start_idx = time_to_idx[disc_time]
        start_idx = max(start_idx + 1, 0)  # Start after discovery

        # Find end index (expiry)
        end_idx = np.searchsorted(full_times, expiry_time)
        end_idx = min(end_idx, n_total)

        if start_idx >= end_idx:
            continue

        # Vectorized zone touch detection
        touches_zone = (full_lows[start_idx:end_idx] <= zh) & (full_highs[start_idx:end_idx] >= zl)
        touch_indices = np.where(touches_zone)[0] + start_idx  # Absolute indices

        if len(touch_indices) == 0:
            continue

        trade_count = 0
        cooldown_until_idx = -1

        for abs_idx in touch_indices:
            if trade_count >= MAX_TRADES_PER_ZONE:
                break
            if abs_idx <= cooldown_until_idx:
                continue

            # Check MSS in recent bars
            # Use the most recent MSS signal in the lookback window
            lb_start = max(abs_idx - MSS_LOOKBACK, 0)
            recent_bull = mss_bull[lb_start:abs_idx + 1]
            recent_bear = mss_bear[lb_start:abs_idx + 1]

            has_bull = recent_bull.any()
            has_bear = recent_bear.any()

            if not has_bull and not has_bear:
                continue

            # Determine direction from most recent MSS
            if has_bull and has_bear:
                last_bull_idx = lb_start + np.where(recent_bull)[0][-1]
                last_bear_idx = lb_start + np.where(recent_bear)[0][-1]
                trade_dir = 'long' if last_bull_idx > last_bear_idx else 'short'
            elif has_bull:
                trade_dir = 'long'
            else:
                trade_dir = 'short'

            is_original = (trade_dir == zone['original_dir'])
            trade_type = 'original' if is_original else 'inverse'

            # Entry on next bar
            entry_idx = abs_idx + 1
            if entry_idx >= n_total:
                break

            entry_price = full_opens[entry_idx]
            if entry_price <= 0:
                continue

            # Entry at zone edge
            if trade_dir == 'long':
                entry_price = min(entry_price, zl + (zh - zl) * 0.5)  # Enter at zone mid or better
            else:
                entry_price = max(entry_price, zh - (zh - zl) * 0.5)

            # Trade bars
            trade_end = min(entry_idx + max_horizon + 1, n_total)
            trade_highs = full_highs[entry_idx:trade_end]
            trade_lows = full_lows[entry_idx:trade_end]
            trade_opens = full_opens[entry_idx:trade_end]

            if len(trade_highs) < 2:
                continue

            # Check liquidity sweep
            liq_swept = False
            liq_level = None
            if trade_dir == 'long':
                check_lows = full_lows[lb_start:abs_idx + 1]
                phl = ph_low[abs_idx]
                pdl_val = pdl_arr[abs_idx]
                if not np.isnan(phl) and check_lows.min() <= phl:
                    liq_swept, liq_level = True, 'prev_hour_low'
                elif not np.isnan(pdl_val) and check_lows.min() <= pdl_val:
                    liq_swept, liq_level = True, 'pdl'
            else:
                check_highs = full_highs[lb_start:abs_idx + 1]
                phh = ph_high[abs_idx]
                pdh_val = pdh_arr[abs_idx]
                if not np.isnan(phh) and check_highs.max() >= phh:
                    liq_swept, liq_level = True, 'prev_hour_high'
                elif not np.isnan(pdh_val) and check_highs.max() >= pdh_val:
                    liq_swept, liq_level = True, 'pdh'

            # Simulate
            sim = simulate_pct_trade_numpy(entry_price, trade_dir == 'long',
                                           trade_highs, trade_lows, trade_opens, max_horizon)
            if sim is None:
                continue

            trade_count += 1

            # Cooldown
            exit_bar = sim.pop('_exit_bar', 60)
            cooldown_until_idx = entry_idx + exit_bar + COOLDOWN_BARS

            interaction_time = full_times[abs_idx]

            result = {
                'triggered': True,
                'date': date_val,
                'zone_high': zh,
                'zone_low': zl,
                'original_dir': zone['original_dir'],
                'trade_dir': trade_dir,
                'trade_type': trade_type,
                'setup_type': zone['setup_type'],
                'setup_category': zone['category'],
                'discovery_hour': zone['discovery_hour'],
                'session_name': zone['session_name'],
                'interaction_time': str(interaction_time),
                'interaction_hour': interaction_time.hour if hasattr(interaction_time, 'hour') else 0,
                'entry_price': entry_price,
                'touch_number': trade_count,
                'has_mss': True,
                'liq_swept': liq_swept,
                'liq_level': liq_level,
                'has_confluence': liq_swept,
            }
            result.update(sim)
            day_results.append(result)

    return day_results


# --- Report helper ---
def grid_table(subset, horizon, tp_list, sl_list, lines):
    header = "| TP \\\\ SL |"
    sep = "|---|"
    for sl in sl_list:
        header += f" {sl:.2f}% |"; sep += "---|"
    lines.append(header); lines.append(sep)
    for tp in tp_list:
        row = f"| **{tp:.2f}%** |"
        for sl in sl_list:
            col = f'o_{horizon}_{tp}_{sl}'
            if col in subset.columns:
                w=(subset[col]=='win').sum(); l=(subset[col]=='loss').sum(); t=(subset[col]=='timeout').sum()
                total=w+l+t
                if total > 0:
                    wp=w/total*100; exp=(w*tp-l*sl)/total
                    row += f" {wp:.0f}%/{exp:+.03f}% |"
                else: row += " - |"
            else: row += " - |"
        lines.append(row)


class FirstPresentedAnalyzerV5:
    def __init__(self, ticker="NQ1"):
        self.ticker = ticker
        self.df = None
        self.stats_df = pd.DataFrame()
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_data(self):
        path = DATA_DIR / f"{self.ticker}_1m.parquet"
        print(f"Loading {path}...")
        df = pd.read_parquet(path)
        if 'time' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
            df = df.set_index('datetime')
        elif 'datetime' in df.columns:
            df = df.set_index('datetime')
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            df.index = df.index.tz_convert('America/New_York')
        df = df.sort_index()
        start_date = df.index[-1] - timedelta(days=730)
        df = df[df.index >= start_date].copy()
        print("Computing indicators...")
        df = compute_displacement(df)
        df = compute_levels(df)
        self.df = df
        print(f"Loaded: {len(self.df):,} bars")

    def run_analysis(self):
        if self.df is None: self.load_data()
        dates = np.unique(self.df.index.date)
        tasks = []
        print(f"Preparing {len(dates)} days...")
        for d in dates:
            ts_start = pd.Timestamp(d).tz_localize(self.df.index.tz)
            ts_end = ts_start + timedelta(days=1, hours=6)
            chunk = self.df[(self.df.index >= ts_start) & (self.df.index < ts_end)]
            if len(chunk) > 60:
                tasks.append((d, chunk))

        n_cores = max(1, os.cpu_count() - 1)
        print(f"Processing {len(tasks)} days with {n_cores} cores...")

        results = []
        with ProcessPoolExecutor(max_workers=n_cores) as executor:
            for i, day_res in enumerate(executor.map(process_day, tasks)):
                results.extend(day_res)
                if (i + 1) % 100 == 0:
                    print(f"  {i+1}/{len(tasks)} days done, {len(results)} trades so far...")

        self.stats_df = pd.DataFrame(results)
        print(f"\nDone: {len(self.stats_df):,} trades")
        if not self.stats_df.empty:
            df = self.stats_df
            print(f"  Original: {(df['trade_type']=='original').sum():,}")
            print(f"  Inverse:  {(df['trade_type']=='inverse').sum():,}")
            print(f"  Touch 1: {(df['touch_number']==1).sum():,}  Touch 2: {(df['touch_number']==2).sum():,}  Touch 3+: {(df['touch_number']>=3).sum():,}")

    def save_report(self):
        if self.stats_df.empty:
            print("No data."); return
        df = self.stats_df.copy()
        col = 'o_1H_0.1_0.3'

        lines = [
            f"# First Presented v5: {self.ticker}",
            "## Persistent Zones + Inverse + MSS",
            "",
            f"**Total trades**: {len(df):,}",
            f"**Original**: {(df['trade_type']=='original').sum():,} | **Inverse**: {(df['trade_type']=='inverse').sum():,}",
            f"**With liq sweep**: {df['liq_swept'].sum():,} ({df['liq_swept'].mean()*100:.1f}%)",
            "",
        ]

        lines.append("## Overall: 1H TP=0.10% SL=0.30%")
        lines.append("| Filter | N | Win% | Loss% | Exp(pts) |")
        lines.append("|---|---|---|---|---|")
        for label, sub in [
            ('All', df), ('Original', df[df['trade_type']=='original']),
            ('Inverse', df[df['trade_type']=='inverse']),
            ('Touch 1', df[df['touch_number']==1]), ('Touch 2', df[df['touch_number']==2]),
            ('Touch 3+', df[df['touch_number']>=3]),
            ('Liq swept', df[df['liq_swept']==True]),
            ('FVG zones', df[df['setup_category']=='FVG']),
            ('OB zones', df[df['setup_category']=='OB']),
        ]:
            if len(sub)<5 or col not in sub.columns: continue
            w=(sub[col]=='win').sum(); l=(sub[col]=='loss').sum(); t=(sub[col]=='timeout').sum()
            total=w+l+t
            if total==0: continue
            lines.append(f"| {label} | {total} | {w/total*100:.1f}% | {l/total*100:.1f}% | {(w*0.10-l*0.30)/total*22000/100:+.1f} |")
        lines.append("")

        lines.append("## By Discovery Hour")
        lines.append("| Hour | Sess | All N | Win% | Orig N | Orig W% | Inv N | Inv W% |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for h in [18,19,20,21,22,23,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17]:
            s=df[df['discovery_hour']==h]
            if len(s)<5: continue
            o=s[s['trade_type']=='original']; inv=s[s['trade_type']=='inverse']
            def wr(sub):
                if len(sub)==0 or col not in sub.columns: return '-'
                w=(sub[col]=='win').sum(); total=len(sub)
                return f"{w/total*100:.0f}%" if total>0 else '-'
            lines.append(f"| {h:02d} | {get_session(h)} | {len(s)} | {wr(s)} | {len(o)} | {wr(o)} | {len(inv)} | {wr(inv)} |")
        lines.append("")

        lines.append("## By Interaction Hour")
        lines.append("| Hour | N | Win% | Exp(pts) | Orig% |")
        lines.append("|---|---|---|---|---|")
        for h in range(24):
            s=df[df['interaction_hour']==h]
            if len(s)<5: continue
            w=(s[col]=='win').sum(); l=(s[col]=='loss').sum(); t=(s[col]=='timeout').sum()
            total=w+l+t
            if total==0: continue
            lines.append(f"| {h:02d} | {total} | {w/total*100:.1f}% | {(w*0.10-l*0.30)/total*22000/100:+.1f} | {(s['trade_type']=='original').mean()*100:.0f}% |")
        lines.append("")

        for label, sub in [('All',df),('Original',df[df['trade_type']=='original']),('Inverse',df[df['trade_type']=='inverse'])]:
            if len(sub)<30: continue
            lines.append(f"## TP/SL Grid: {label} (N={len(sub)}, 1H)")
            lines.append("")
            grid_table(sub, '1H', TP_PCTS, SL_PCTS, lines)
            lines.append("")

        lines.append("## Touch Number")
        lines.append("| Touch | N | Win% | Exp(pts) |")
        lines.append("|---|---|---|---|")
        for t_num in [1,2,3,4]:
            s=df[df['touch_number']==t_num]
            if len(s)<10: continue
            w=(s[col]=='win').sum(); l=(s[col]=='loss').sum(); t=(s[col]=='timeout').sum()
            total=w+l+t
            if total>0:
                lines.append(f"| {t_num} | {total} | {w/total*100:.1f}% | {(w*0.10-l*0.30)/total*22000/100:+.1f} |")
        lines.append("")

        report_path = self.output_dir / f"{self.ticker}_REPORT_v5.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Report -> {report_path}")
        csv_path = self.output_dir / f"{self.ticker}_raw_trades_v5.csv"
        df.to_csv(csv_path, index=False)
        print(f"Raw CSV -> {csv_path}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    analyzer = FirstPresentedAnalyzerV5("NQ1")
    analyzer.run_analysis()
    analyzer.save_report()
