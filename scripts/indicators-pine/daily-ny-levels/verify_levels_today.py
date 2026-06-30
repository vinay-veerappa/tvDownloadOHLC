"""
Verify DNL levels against Gunship levels captured 2026-06-30.

Production standard: 5m chart timeframe for ALL processing (OR building, breakout,
MFE/MAE tracking, classification). 1m LTF is NOT used.

Classification (Pine-exact):
  1. Breakout detected on 5m close crossing OR High/Low.
  2. At breakout, compute p80 MAE from ALL prior same-side bo_mae sessions.
     Fallback: if <1 sample, use 0.5%.
  3. Invalidation price = bo_px * (1 - side * p80/100).
  4. On each subsequent 5m bar:
     - LOSS (-1) if wick touches invalidation price.
     - FAKE (2) if wick crosses opposite OR boundary (overrides -1).
  5. WIN (1) if no invalidation touch before cutoff.

Arrays committed per session (matching Pine's f_commit_daily):
  - bo_mfe: from bo_px to max favorable excursion (same-side only)
  - bo_mae: from bo_px to max adverse excursion (same-side only)
  - mae_abs: from OR boundary to session extreme (entry_triggered only)
  - sig_side, sig_outcome: classification results

Percentile method: Pine's array.percentile_nearest_rank = ceil(p/100 * N), 1-indexed.
"""
import pandas as pd
import numpy as np
import math
import pytz

# ============================================================================
# Pine-exact percentile
# ============================================================================
def pine_pct(arr, p):
    """Pine's array.percentile_nearest_rank: rank = ceil(p/100 * N), 1-indexed.
    Filters out NaN and values <= 0 (matching Pine's f_build_filtered)."""
    s = np.sort(np.array([x for x in arr if not np.isnan(x) and x > 0], dtype=float))
    n = len(s)
    if n == 0:
        return np.nan
    rank = math.ceil(p / 100.0 * n)
    rank = max(1, min(rank, n))
    return s[rank - 1]

def pine_pct_raw(arr, p):
    """Same as pine_pct but does NOT filter out zeros/negatives (for MAE arrays
    where 0 values are valid and should be included)."""
    s = np.sort(np.array([x for x in arr if not np.isnan(x)], dtype=float))
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
HOLIDAYS = {
    pd.Timestamp('2026-04-03').date(),
    pd.Timestamp('2026-05-25').date(),
    pd.Timestamp('2026-06-19').date(),
}
df_1m = df_1m[~df_1m['date'].isin(HOLIDAYS)]
df_1m = df_1m[df_1m['date'] >= pd.Timestamp('2026-03-12').date()]

# Resample to 5m — the chart timeframe (production standard)
df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
).dropna()
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
        'PB Inval':    30351.03,
        'PB Entry':    30384.60,
        'BO Cashflow': 30427.87,
        'Pivot':       30441.39,
        'BO Confirm':  30446.95,
        'MED MFE':     30481.52,
        'MAX MFE':     30501.22,
        'Reversal':    30310.39,
        'Max Rev':     30085.85,
        'Midpoint':    30354.88,
        'AVG':         30469.24,
    },
    'MO Break': {
        'bo_px': 30215.75, 'side': 1, 'or_high': 30189.00, 'or_low': 30033.00,
        'PB Inval':    30129.00,
        'PB Entry':    30197.02,
        'BO Cashflow': 30313.75,
        'Pivot':       30277.12,
        'BO Confirm':  30331.29,
        'MED MFE':     30374.03,
        'MAX MFE':     30395.84,
        'Reversal':    30040.02,
        'Max Rev':     29749.65,
        'Midpoint':    30111.00,
        'AVG':         30312.02,
    },
}

# ============================================================================
# Session builder with Pine-exact rolling classification
# ============================================================================
def build_sessions(cfg):
    """Build sessions using 5m chart timeframe with Pine-exact rolling classification."""
    valid_dows = days_to_python_dow(cfg['days'])
    start_date = pd.Timestamp(cfg['start_date']).date()
    sessions = []

    # Rolling history arrays (match Pine's ExcursionHistory)
    hist_bo_mae = []     # bo_mae for all sessions (NaN for non-matching side)
    hist_sig_side = []
    hist_sig_outcome = []

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
            session_5m = df_5m[
                (df_5m['date'] == date) &
                (df_5m['et_hhmm'] >= cfg['or_start']) &
                (df_5m['et_hhmm'] < cfg['cutoff'])
            ]

        if session_5m.empty:
            continue

        # OR building from 5m chart bars
        or_bars = session_5m[
            (session_5m['et_hhmm'] >= cfg['or_start']) &
            (session_5m['et_hhmm'] < cfg['or_end'])
        ]
        if or_bars.empty:
            continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()

        # Data window (post-OR to cutoff)
        data_5m = session_5m[session_5m['et_hhmm'] >= cfg['or_end']]
        if data_5m.empty:
            continue

        # --- Track mae_abs from first data bar (Pine: f_track_mae_abs) ---
        mae_bull_abs = 0.0
        mae_bear_abs = 0.0
        entry_triggered_bull = False
        entry_triggered_bear = False
        session_low_data = np.inf
        session_high_data = -np.inf

        # --- Breakout detection on 5m close ---
        bo_side = 0
        bo_px = None
        bo_idx = None
        for idx, row in data_5m.iterrows():
            # Track mae_abs (from OR boundary) on every data bar
            bull_ae = (or_high - row['low']) / or_high * 100.0
            bear_ae = (row['high'] - or_low) / or_low * 100.0
            if bull_ae > 0:
                mae_bull_abs = max(mae_bull_abs, bull_ae)
            if bear_ae > 0:
                mae_bear_abs = max(mae_bear_abs, bear_ae)
            if row['high'] > or_high:
                entry_triggered_bull = True
            if row['low'] < or_low:
                entry_triggered_bear = True
            session_low_data = min(session_low_data, row['low'])
            session_high_data = max(session_high_data, row['high'])

            if bo_side == 0:
                if row['close'] > or_high:
                    bo_side = 1; bo_px = row['close']; bo_idx = idx; break
                elif row['close'] < or_low:
                    bo_side = -1; bo_px = row['close']; bo_idx = idx; break

        if bo_side == 0:
            hist_sig_side.append(0)
            hist_sig_outcome.append(0)
            hist_bo_mae.append(np.nan)
            continue

        # --- Compute rolling p80 MAE for invalidation ---
        # Pine: f_filter_breakout_all filters by side and outcome=0 (Any)
        prior_bo_mae = []
        n_hist = min(len(hist_bo_mae), min(len(hist_sig_side), len(hist_sig_outcome)))
        if n_hist > 0:
            src_off = len(hist_bo_mae) - n_hist
            side_off = len(hist_sig_side) - n_hist
            outcome_off = len(hist_sig_outcome) - n_hist
            for i in range(n_hist):
                val = hist_bo_mae[src_off + i]
                s = hist_sig_side[side_off + i]
                if not np.isnan(val) and s == bo_side:
                    prior_bo_mae.append(val)

        if len(prior_bo_mae) > 0:
            p80_mae = pine_pct_raw(prior_bo_mae, 80)
        else:
            p80_mae = 0.5  # Pine fallback default

        invalid_px = bo_px * (1 - bo_side * p80_mae / 100.0)

        # --- Post-breakout tracking on 5m bars ---
        post_bo = data_5m.loc[bo_idx:]
        sig_outcome = 0  # PENDING

        bo_mfe = 0.0
        bo_mae = 0.0

        for idx, row in post_bo.iterrows():
            # Track bo_mfe and bo_mae from breakout price
            if bo_side == 1:
                bo_mfe = max(bo_mfe, (row['high'] - bo_px) / bo_px * 100.0)
                bo_mae = max(bo_mae, (bo_px - row['low']) / bo_px * 100.0)
            else:
                bo_mfe = max(bo_mfe, (bo_px - row['low']) / bo_px * 100.0)
                bo_mae = max(bo_mae, (row['high'] - bo_px) / bo_px * 100.0)

            # Continue tracking mae_abs and entry_triggered
            bull_ae = (or_high - row['low']) / or_high * 100.0
            bear_ae = (row['high'] - or_low) / or_low * 100.0
            if bull_ae > 0:
                mae_bull_abs = max(mae_bull_abs, bull_ae)
            if bear_ae > 0:
                mae_bear_abs = max(mae_bear_abs, bear_ae)
            if row['high'] > or_high:
                entry_triggered_bull = True
            if row['low'] < or_low:
                entry_triggered_bear = True
            session_low_data = min(session_low_data, row['low'])
            session_high_data = max(session_high_data, row['high'])

            # Classification checks (only if still pending)
            if sig_outcome <= 0:
                # 1. Invalidation wick-touch
                if bo_side == 1 and row['low'] <= invalid_px:
                    sig_outcome = -1  # LOSS
                elif bo_side == -1 and row['high'] >= invalid_px:
                    sig_outcome = -1  # LOSS
                # 2. Fakeout — opposite OR wick cross (overrides -1 -> 2)
                crossed_opposite = (bo_side == 1 and row['low'] < or_low) or \
                                   (bo_side == -1 and row['high'] > or_high)
                if crossed_opposite:
                    sig_outcome = 2  # FAKE

        # Cutoff finalization: no invalidation = WIN
        if sig_outcome == 0:
            sig_outcome = 1  # WIN (FULL)

        # --- Compute fake_mae (f_fakeout_reversal_depth) ---
        if sig_outcome == 2:
            if bo_side == 1:
                fake_mae = max(0.0, (or_high - session_low_data) / or_high * 100.0)
            else:
                fake_mae = max(0.0, (session_high_data - or_low) / or_low * 100.0)
        else:
            fake_mae = np.nan

        # --- Commit to rolling history ---
        hist_bo_mae.append(bo_mae)
        hist_sig_side.append(bo_side)
        hist_sig_outcome.append(sig_outcome)

        # mae_abs committed only if entry_triggered
        mae_abs_committed = mae_bull_abs if (bo_side == 1 and entry_triggered_bull) else \
                            mae_bear_abs if (bo_side == -1 and entry_triggered_bear) else np.nan

        sessions.append({
            'date': date,
            'side': bo_side,
            'or_high': or_high,
            'or_low': or_low,
            'bo_px': bo_px,
            'bo_mfe': bo_mfe,
            'bo_mae': bo_mae,
            'mae_abs': mae_abs_committed,
            'fake_mae': fake_mae,
            'sig_outcome': sig_outcome,
            'is_win': sig_outcome == 1,
            'is_fake': sig_outcome == 2,
            'is_loss': sig_outcome == -1,
            'p80_mae_at_bo': p80_mae,
            'invalid_px': invalid_px,
        })

    return pd.DataFrame(sessions)


# ============================================================================
# Filter helpers (matching Pine's f_build_filtered_by_outcome)
# ============================================================================
def filter_by_outcome(df, side, outcome):
    if outcome == 0:
        return df[df['side'] == side]
    return df[(df['side'] == side) & (df['sig_outcome'] == outcome)]

def filter_wins(df, side):
    return filter_by_outcome(df, side, 1)

def filter_fakes(df, side):
    return filter_by_outcome(df, side, 2)

def filter_all(df, side):
    return filter_by_outcome(df, side, 0)


# ============================================================================
# Run verification
# ============================================================================
for preset_name, cfg in PRESETS.items():
    df_p = build_sessions(cfg)
    g = GUNSHIP_TODAY[preset_name]
    bo_px = g['bo_px']
    side = g['side']
    or_high = g['or_high']
    or_low = g['or_low']

    same_all = filter_all(df_p, side)
    same_win = filter_wins(df_p, side)
    same_fake = filter_fakes(df_p, side)
    same_loss = filter_by_outcome(df_p, side, -1)

    print("=" * 100)
    print(f"PRESET: {preset_name} | N={len(df_p)} | BO px={bo_px} | side={'bull' if side==1 else 'bear'}")
    print(f"  Same-side: {len(same_all)} total, {len(same_win)} wins, {len(same_loss)} losses, {len(same_fake)} fakes")
    print("=" * 100)

    # ---- BO Cashflow P20 (MFE from BO px, Wins only) ----
    print(f"\n  BO CASHFLOW P20 (Gunship: {g['BO Cashflow']:.2f})")
    for label, sample in [('Wins', same_win), ('ALL', same_all), ('Fakes', same_fake)]:
        if len(sample) == 0:
            continue
        p20 = pine_pct(sample['bo_mfe'].values, 20)
        price = bo_px * (1 + side * p20 / 100)
        delta_g = price - g['BO Cashflow']
        print(f"    {label:6s} N={len(sample):3d} P20={p20:.4f}% -> {price:.2f}  dGun={delta_g:+.2f}")

    # ---- PB/BO Inval P80 (MAE from BO px) ----
    print(f"\n  PB/BO INVAL P80 (Gunship: {g['PB Inval']:.2f})")
    for label, sample in [('ALL', same_all), ('Wins', same_win), ('Losses', same_loss), ('Fakes', same_fake)]:
        if len(sample) == 0:
            continue
        p80 = pine_pct(sample['bo_mae'].values, 80)
        price = bo_px * (1 - side * p80 / 100)
        delta_g = price - g['PB Inval']
        print(f"    {label:7s} N={len(sample):3d} P80={p80:.4f}% -> {price:.2f}  dGun={delta_g:+.2f}")

    # ---- PB Entry P25 (MAE from BO px, Wins only) ----
    print(f"\n  PB ENTRY P25 (Gunship: {g['PB Entry']:.2f})")
    for label, sample in [('Wins', same_win), ('ALL', same_all), ('Fakes', same_fake)]:
        if len(sample) == 0:
            continue
        p25 = pine_pct(sample['bo_mae'].values, 25)
        price = bo_px * (1 - side * p25 / 100)
        delta_g = price - g['PB Entry']
        print(f"    {label:6s} N={len(sample):3d} P25={p25:.4f}% -> {price:.2f}  dGun={delta_g:+.2f}")

    # ---- Reversal Zone P25-P50 (fake MAE from OR boundary) ----
    print(f"\n  REVERSAL ZONE P25-P50 (Gunship: {g['Reversal']:.2f})")
    if len(same_fake) > 0:
        for metric, anchor_name, anchor_px in [
            ('fake_mae', 'OR_Boundary', or_high if side == 1 else or_low),
            ('mae_abs', 'OR_Boundary', or_high if side == 1 else or_low),
            ('bo_mae', 'BO_px', bo_px),
        ]:
            vals = same_fake[metric].dropna().values
            if len(vals) == 0:
                continue
            p25 = pine_pct_raw(vals, 25)
            p50 = pine_pct_raw(vals, 50)
            price25 = anchor_px * (1 - p25 / 100)
            price50 = anchor_px * (1 - p50 / 100)
            delta25_g = price25 - g['Reversal']
            delta50_g = price50 - g['Reversal']
            print(f"    Fakes N={len(vals):3d} {metric}@{anchor_name}: P25={p25:.4f}%->{price25:.2f}(dG={delta25_g:+.2f})  P50={p50:.4f}%->{price50:.2f}(dG={delta50_g:+.2f})")

    # ---- Max Rev P90 (fake MAE from OR boundary) ----
    print(f"\n  MAX REV P90 (Gunship: {g['Max Rev']:.2f})")
    if len(same_fake) > 0:
        for metric, anchor_name, anchor_px in [
            ('fake_mae', 'OR_Boundary', or_high if side == 1 else or_low),
            ('mae_abs', 'OR_Boundary', or_high if side == 1 else or_low),
        ]:
            vals = same_fake[metric].dropna().values
            if len(vals) == 0:
                continue
            p90 = pine_pct_raw(vals, 90)
            price = anchor_px * (1 - p90 / 100)
            delta_g = price - g['Max Rev']
            print(f"    Fakes N={len(vals):3d} {metric}@{anchor_name}: P90={p90:.4f}%->{price:.2f}(dG={delta_g:+.2f})")

    # ---- Pivot P50 (fake MFE from BO px) ----
    print(f"\n  PIVOT P50 (Gunship: {g['Pivot']:.2f})")
    if len(same_fake) > 0:
        p50 = pine_pct(same_fake['bo_mfe'].values, 50)
        price = bo_px * (1 + side * p50 / 100)
        delta_g = price - g['Pivot']
        print(f"    Fakes N={len(same_fake):3d} P50={p50:.4f}% -> {price:.2f}  dGun={delta_g:+.2f}")

    # ---- BO Confirm P75 (fake MFE from BO px) ----
    print(f"\n  BO CONFIRM P75 (Gunship: {g['BO Confirm']:.2f})")
    if len(same_fake) > 0:
        p75 = pine_pct(same_fake['bo_mfe'].values, 75)
        price = bo_px * (1 + side * p75 / 100)
        delta_g = price - g['BO Confirm']
        print(f"    Fakes N={len(same_fake):3d} P75={p75:.4f}% -> {price:.2f}  dGun={delta_g:+.2f}")

    # ---- MED MFE P50 (Green = wins) ----
    print(f"\n  MED MFE P50 Green (Gunship: {g['MED MFE']:.2f})")
    for label, sample in [('Wins(Green)', same_win), ('ALL', same_all)]:
        if len(sample) == 0:
            continue
        p50 = pine_pct(sample['bo_mfe'].values, 50)
        price = bo_px * (1 + side * p50 / 100)
        delta_g = price - g['MED MFE']
        print(f"    {label:12s} N={len(sample):3d} P50={p50:.4f}% -> {price:.2f}  dGun={delta_g:+.2f}")

    # ---- MAX MFE P75 (Green = wins) ----
    print(f"\n  MAX MFE P75 Green (Gunship: {g['MAX MFE']:.2f})")
    for label, sample in [('Wins(Green)', same_win), ('ALL', same_all)]:
        if len(sample) == 0:
            continue
        p75 = pine_pct(sample['bo_mfe'].values, 75)
        price = bo_px * (1 + side * p75 / 100)
        delta_g = price - g['MAX MFE']
        print(f"    {label:12s} N={len(sample):3d} P75={p75:.4f}% -> {price:.2f}  dGun={delta_g:+.2f}")

    # ---- AVG MFE (Green = wins, simple mean) ----
    print(f"\n  AVG MFE Green (Gunship: {g['AVG']:.2f})")
    if len(same_win) > 0:
        avg_mfe = same_win['bo_mfe'].mean()
        price = bo_px * (1 + side * avg_mfe / 100)
        delta_g = price - g['AVG']
        print(f"    Wins(Green) N={len(same_win):3d} AVG={avg_mfe:.4f}% -> {price:.2f}  dGun={delta_g:+.2f}")

    # ---- Classification detail ----
    print(f"\n  CLASSIFICATION DETAIL (first 10 same-side sessions):")
    for _, row in same_all.head(10).iterrows():
        outcome_str = {1: 'WIN', -1: 'LOSS', 2: 'FAKE'}.get(row['sig_outcome'], '?')
        print(f"    {row['date']} side={row['side']} outcome={outcome_str} bo_mae={row['bo_mae']:.4f}% p80_at_bo={row['p80_mae_at_bo']:.4f}% invalid={row['invalid_px']:.2f}")

    print()