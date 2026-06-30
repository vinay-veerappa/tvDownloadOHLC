"""
Verify DNL levels against Gunship levels captured 2026-06-30.
Uses Pine's exact percentile_nearest_rank method (ceil(p/100*N), 1-indexed).

Tests both 1100 BO and MO Break presets.
Focus: BO Cashflow P20, Reversal Zone, PB/BO Inval P80, PB Entry P25.
"""
import pandas as pd
import numpy as np
import math
import pytz

# ============================================================================
# Pine-exact percentile
# ============================================================================
def pine_pct(arr, p):
    """Pine's array.percentile_nearest_rank: rank = ceil(p/100 * N), 1-indexed."""
    s = np.sort(np.array(arr, dtype=float))
    n = len(s)
    if n == 0:
        return np.nan
    rank = math.ceil(p / 100.0 * n)
    rank = max(1, min(rank, n))
    return s[rank - 1]

# ============================================================================
# Load data
# ============================================================================
df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hhmm'] = df_1m['et_time'].dt.hour * 100 + df_1m['et_time'].dt.minute
df_1m['et_dow'] = df_1m['et_time'].dt.dayofweek
df_1m['date'] = df_1m['et_time'].dt.date

# Date range: exclude today (2026-06-30) since session is still active
df_1m = df_1m[df_1m['date'] <= pd.Timestamp('2026-06-27').date()]
HOLIDAYS = {pd.Timestamp('2026-04-03').date(), pd.Timestamp('2026-05-25').date(), pd.Timestamp('2026-06-19').date()}
df_1m = df_1m[~df_1m['date'].isin(HOLIDAYS)]
df_1m = df_1m[df_1m['date'] >= pd.Timestamp('2026-03-12').date()]

# Resample to 5m — the chart timeframe (production standard)
df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['et_dow'] = df_5m['et_time'].dt.dayofweek
df_5m['date'] = df_5m['et_time'].dt.date

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

PRESETS = {
    '1100 BO':  {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                 'crosses_midnight': False, 'start_date': '2026-03-13'},
    'MO Break': {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                 'crosses_midnight': False, 'start_date': '2026-03-12'},
}

# Gunship levels captured 2026-06-30 via TradingView MCP
GUNSHIP_TODAY = {
    '1100 BO': {
        'bo_px': 30410.75, 'side': 1, 'or_high': 30410.00, 'or_low': 30299.75,
        'PB Inval':    30351.03,   # p80 MAE from breakout (ALL)
        'PB Entry':    30384.60,   # p25 MAE (ALL)
        'BO Cashflow': 30427.87,   # p20 MFE (0.056%)
        'Pivot':       30441.39,   # p50 fake MFE (0.101%)
        'BO Confirm':  30446.95,   # p75 fake MFE (0.119%) [9]
        'MED MFE':     30481.52,   # p50 Green
        'MAX MFE':     30501.22,   # p75 Green
        'Reversal':    30310.39,   # p25-p50 fake MAE
        'Max Rev':     30085.85,   # p90 fake MAE (1.068%)
        'Midpoint':    30354.88,
        'AVG':         30469.24,
    },
    'MO Break': {
        'bo_px': 30215.75, 'side': 1, 'or_high': 30189.00, 'or_low': 30033.00,
        'PB Inval':    30129.00,   # p80 MAE from breakout (ALL)
        'PB Entry':    30197.02,   # p25 MAE (ALL)
        'BO Cashflow': 30313.75,   # p20 MFE (0.324%)
        'Pivot':       30277.12,   # p50 fake MFE (0.203%)
        'BO Confirm':  30331.29,   # p75 fake MFE (0.382%) [26]
        'MED MFE':     30374.03,   # p50 Green
        'MAX MFE':     30395.84,   # p75 Green
        'Reversal':    30040.02,   # p25-p50 fake MAE
        'Max Rev':     29749.65,   # p90 fake MAE (1.543%)
        'Midpoint':    30111.00,
        'AVG':         30312.02,
    },
}

# DNL levels captured 2026-06-30 via TradingView MCP
DNL_TODAY = {
    '1100 BO': {
        'bo_px': 30410.75, 'or_high': 30410.00, 'or_low': 30299.75,
        'PB Inval Wins':   30331.79,
        'PB Inval Losses': 30285.52,
        'PB Entry':        30375.79,
        'BO Cashflow':     30424.69,  # 0.05%
        'Pivot':           30441.39,  # 0.10%
        'BO Confirm':      30460.02,  # 0.16%
        'MED MFE':         30466.56,  # 0.19%
        'Stretch P90':     30555.06,  # 0.48%
        'Reversal':        30305.77,  # 0.23-0.34%
        'Midpoint':        30354.88,
        'AVG':             30481.16,  # 0.23%
    },
    'MO Break': {
        'bo_px': 30215.75, 'or_high': 30189.00, 'or_low': 30033.00,
        'PB Inval Wins':   30114.15,
        'PB Inval Losses': 29844.90,
        'PB Entry':        30155.33,
        'BO Cashflow':     30261.92,  # 0.15%
        'Pivot':           30277.12,  # 0.20%
        'BO Confirm':      30331.29,  # 0.38%
        'MED MFE':         30302.03,  # 0.37%
        'Stretch P90':     30444.59,  # 0.85%
        'Reversal':        30020.17,  # 0.43-0.56%
        'Midpoint':        30111.00,
        'AVG':             30328.66,  # 0.46%
    },
}

def build_sessions(cfg):
    """Build sessions using 5m chart timeframe for ALL processing."""
    valid_dows = days_to_python_dow(cfg['days'])
    start_date = pd.Timestamp(cfg['start_date']).date()
    sessions = []

    for date in sorted(df_5m['date'].unique()):
        if date < start_date:
            continue
        if date in HOLIDAYS:
            continue
        if date.weekday() not in valid_dows:
            continue

        if cfg['crosses_midnight']:
            next_date = date + pd.Timedelta(days=1)
            session_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start'])],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cfg['cutoff'])]
            ])
        else:
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start']) & (df_5m['et_hhmm'] < cfg['cutoff'])]

        if session_5m.empty:
            continue

        # OR building from 5m chart bars
        or_bars = session_5m[(session_5m['et_hhmm'] >= cfg['or_start']) & (session_5m['et_hhmm'] < cfg['or_end'])]
        if or_bars.empty:
            continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()

        # Data window (post-OR to cutoff)
        data_5m = session_5m[session_5m['et_hhmm'] >= cfg['or_end']]
        if data_5m.empty:
            continue

        # Breakout detection on 5m close
        bo_side = 0; bo_px = None; bo_idx = None
        for idx, row in data_5m.iterrows():
            if row['close'] > or_high:
                bo_side = 1; bo_px = row['close']; bo_idx = idx; break
            elif row['close'] < or_low:
                bo_side = -1; bo_px = row['close']; bo_idx = idx; break
        if bo_side == 0:
            continue

        # Post-breakout tracking on 5m bars
        post_bo = data_5m.loc[bo_idx:]

        if bo_side == 1:
            bo_mfe = ((post_bo['high'].max() - bo_px) / bo_px) * 100
            bo_mae = ((bo_px - post_bo['low'].min()) / bo_px) * 100
            mae_or = ((or_high - post_bo['low'].min()) / or_high) * 100
        else:
            bo_mfe = ((bo_px - post_bo['low'].min()) / bo_px) * 100
            bo_mae = ((post_bo['high'].max() - bo_px) / bo_px) * 100
            mae_or = ((post_bo['high'].max() - or_low) / or_low) * 100

        # Classification: verified rule = wick-touch invalidation
        # For now, use R3 (touch opp OR) as proxy for fakeout classification
        r3_fail = False
        for idx, row in post_bo.iterrows():
            if bo_side == 1 and row['low'] < or_low:
                r3_fail = True; break
            elif bo_side == -1 and row['high'] > or_high:
                r3_fail = True; break

        # Fakeout = R3 fail (wick crossed opposite OR)
        is_fake = r3_fail

        # Win = not failed (no invalidation touch) — simplified for level computation
        is_win = not r3_fail

        sessions.append({
            'date': date, 'side': bo_side, 'or_high': or_high, 'or_low': or_low,
            'bo_px': bo_px, 'bo_mfe': bo_mfe, 'bo_mae': bo_mae, 'mae_or': mae_or,
            'is_win': is_win, 'is_fake': is_fake,
        })

    return pd.DataFrame(sessions)


# ============================================================================
# Run verification
# ============================================================================
for preset_name, cfg in PRESETS.items():
    df_p = build_sessions(cfg)
    g = GUNSHIP_TODAY[preset_name]
    d = DNL_TODAY[preset_name]
    bo_px = g['bo_px']
    side = g['side']
    or_high = g['or_high']
    or_low = g['or_low']

    same_side = df_p[df_p['side'] == side]
    same_win = same_side[same_side['is_win']]
    same_fake = same_side[same_side['is_fake']]
    same_all = same_side  # ALL = win + fail

    print("=" * 100)
    print(f"PRESET: {preset_name} | N={len(df_p)} | BO px={bo_px} | side={'bull' if side==1 else 'bear'}")
    print(f"  Same-side: {len(same_side)} total, {len(same_win)} wins, {len(same_fake)} fakes")
    print("=" * 100)

    # ---- BO Cashflow P20 (MFE from BO px) ----
    print(f"\n  📊 BO CASHFLOW P20 (Gunship: {g['BO Cashflow']:.2f}, DNL: {d['BO Cashflow']:.2f})")
    for label, sample in [('ALL', same_all), ('Wins', same_win), ('Fakes', same_fake)]:
        if len(sample) == 0:
            continue
        p20 = pine_pct(sample['bo_mfe'].values, 20)
        price = bo_px * (1 + side * p20 / 100)
        delta_g = price - g['BO Cashflow']
        delta_d = price - d['BO Cashflow']
        print(f"    {label:6s} N={len(sample):3d} P20={p20:.4f}% → {price:.2f}  ΔGunship={delta_g:+.2f}  ΔDNL={delta_d:+.2f}")

    # ---- PB/BO Inval P80 (MAE from BO px) ----
    print(f"\n  📊 PB/BO INVAL P80 (Gunship: {g['PB Inval']:.2f}, DNL Wins: {d['PB Inval Wins']:.2f})")
    for label, sample in [('ALL', same_all), ('Wins', same_win), ('Fakes', same_fake)]:
        if len(sample) == 0:
            continue
        p80 = pine_pct(sample['bo_mae'].values, 80)
        price = bo_px * (1 - side * p80 / 100)
        delta_g = price - g['PB Inval']
        delta_d = price - d['PB Inval Wins']
        print(f"    {label:6s} N={len(sample):3d} P80={p80:.4f}% → {price:.2f}  ΔGunship={delta_g:+.2f}  ΔDNL={delta_d:+.2f}")

    # ---- PB Entry P25 (MAE from BO px) ----
    print(f"\n  📊 PB ENTRY P25 (Gunship: {g['PB Entry']:.2f}, DNL: {d['PB Entry']:.2f})")
    for label, sample in [('ALL', same_all), ('Wins', same_win), ('Fakes', same_fake)]:
        if len(sample) == 0:
            continue
        p25 = pine_pct(sample['bo_mae'].values, 25)
        price = bo_px * (1 - side * p25 / 100)
        delta_g = price - g['PB Entry']
        delta_d = price - d['PB Entry']
        print(f"    {label:6s} N={len(sample):3d} P25={p25:.4f}% → {price:.2f}  ΔGunship={delta_g:+.2f}  ΔDNL={delta_d:+.2f}")

    # ---- Reversal Zone P25-P50 (fakeout MAE from OR boundary) ----
    print(f"\n  📊 REVERSAL ZONE P25-P50 (Gunship: {g['Reversal']:.2f}, DNL: {d['Reversal']:.2f})")
    for label, sample in [('Fakes', same_fake), ('ALL', same_all)]:
        if len(sample) == 0:
            continue
        for metric, anchor_name, anchor_px in [
            ('mae_or', 'OR_High', or_high),
            ('bo_mae', 'BO_px', bo_px),
        ]:
            p25 = pine_pct(sample[metric].values, 25)
            p50 = pine_pct(sample[metric].values, 50)
            # Bull: reversal is BELOW anchor (price goes down past OR)
            price25 = anchor_px * (1 - p25 / 100)
            price50 = anchor_px * (1 - p50 / 100)
            delta25_g = price25 - g['Reversal']
            delta50_g = price50 - g['Reversal']
            delta50_d = price50 - d['Reversal']
            print(f"    {label:6s} N={len(sample):3d} {metric}@{anchor_name}: P25={p25:.4f}%→{price25:.2f}(ΔG={delta25_g:+.2f})  P50={p50:.4f}%→{price50:.2f}(ΔG={delta50_g:+.2f} ΔD={delta50_d:+.2f})")

    # ---- Pivot P50 (fake MFE from BO px) — CONFIRMED EXACT ----
    print(f"\n  📊 PIVOT P50 (Gunship: {g['Pivot']:.2f}, DNL: {d['Pivot']:.2f}) — should be EXACT")
    if len(same_fake) > 0:
        p50 = pine_pct(same_fake['bo_mfe'].values, 50)
        price = bo_px * (1 + side * p50 / 100)
        delta_g = price - g['Pivot']
        delta_d = price - d['Pivot']
        print(f"    Fakes N={len(same_fake):3d} P50={p50:.4f}% → {price:.2f}  ΔGunship={delta_g:+.2f}  ΔDNL={delta_d:+.2f}")

    # ---- BO Confirm P75 (fake MFE from BO px) ----
    print(f"\n  📊 BO CONFIRM P75 (Gunship: {g['BO Confirm']:.2f}, DNL: {d['BO Confirm']:.2f})")
    if len(same_fake) > 0:
        p75 = pine_pct(same_fake['bo_mfe'].values, 75)
        price = bo_px * (1 + side * p75 / 100)
        delta_g = price - g['BO Confirm']
        delta_d = price - d['BO Confirm']
        print(f"    Fakes N={len(same_fake):3d} P75={p75:.4f}% → {price:.2f}  ΔGunship={delta_g:+.2f}  ΔDNL={delta_d:+.2f}")

    # ---- MED MFE P50 (Green = wins) ----
    print(f"\n  📊 MED MFE P50 Green (Gunship: {g['MED MFE']:.2f}, DNL: {d['MED MFE']:.2f})")
    for label, sample in [('Wins(Green)', same_win), ('ALL', same_all), ('Fakes', same_fake)]:
        if len(sample) == 0:
            continue
        p50 = pine_pct(sample['bo_mfe'].values, 50)
        price = bo_px * (1 + side * p50 / 100)
        delta_g = price - g['MED MFE']
        print(f"    {label:12s} N={len(sample):3d} P50={p50:.4f}% → {price:.2f}  ΔGunship={delta_g:+.2f}")

    # ---- MAX MFE P75 (Green = wins) ----
    print(f"\n  📊 MAX MFE P75 Green (Gunship: {g['MAX MFE']:.2f}, DNL Stretch P90: {d['Stretch P90']:.2f})")
    for label, sample in [('Wins(Green)', same_win), ('ALL', same_all)]:
        if len(sample) == 0:
            continue
        p75 = pine_pct(sample['bo_mfe'].values, 75)
        price = bo_px * (1 + side * p75 / 100)
        delta_g = price - g['MAX MFE']
        print(f"    {label:12s} N={len(sample):3d} P75={p75:.4f}% → {price:.2f}  ΔGunship={delta_g:+.2f}")

    print()