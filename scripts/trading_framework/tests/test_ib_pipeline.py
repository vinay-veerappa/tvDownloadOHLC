import pandas as pd
import numpy as np
import pytest
from datetime import time

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.nqstats.ib import calculate_ib_statistics_v5

def test_ib_pipeline_shape_alignment_with_missing_ib_bars():
    # Day 1: Full day of 1-minute bars
    t1 = pd.date_range("2026-06-01 00:00:00", "2026-06-01 16:00:00", freq="1min", tz="US/Eastern")
    # Day 2: Only afternoon bars, NO bars in NY AM IB (09:30 - 10:30)
    t2 = pd.date_range("2026-06-02 13:00:00", "2026-06-02 16:00:00", freq="1min", tz="US/Eastern")
    
    t = t1.append(t2)
    
    df = pd.DataFrame(index=t)
    df['open'] = 100.0
    df['high'] = 101.0
    df['low'] = 99.0
    df['close'] = 100.0
    df['volume'] = 100
    
    # Run calculate_ib_statistics_v5 for NY AM IB
    facts, touches, plays = calculate_ib_statistics_v5(
        df_1m=df,
        symbol="NQ1",
        session_choice="NY AM IB",
        time_basis="ET_fixed",
        use_fvg=True
    )
    
    # It should run successfully without ValueError!
    assert not facts.empty
    
    # Day 1 should have IB stats computed
    day1_facts = facts[facts['trading_day'] == pd.Timestamp("2026-06-01").date()]
    assert not day1_facts.empty
    
    # Day 2 has no IB bars, so it should not be in the final facts
    day2_facts = facts[facts['trading_day'] == pd.Timestamp("2026-06-02").date()]
    assert day2_facts.empty


def test_play_level_columns_and_configurable_defaults():
    t = pd.date_range("2026-06-01 00:00:00", "2026-06-01 16:00:00", freq="1min", tz="US/Eastern")
    df = pd.DataFrame(index=t)
    # Deterministic monotonic structure to ensure at least one valid IB day.
    base = np.linspace(100.0, 101.0, len(df))
    df['open'] = base
    df['high'] = base + 0.5
    df['low'] = base - 0.5
    df['close'] = base + 0.1
    df['volume'] = 100

    facts, _, _ = calculate_ib_statistics_v5(
        df_1m=df,
        symbol="NQ1",
        session_choice="NY AM IB",
        time_basis="ET_fixed",
        use_fvg=True,
        legacy_default_play_levels={2: 0.25, 3: 0.75},
    )

    assert not facts.empty
    assert 'play2_result_025x' in facts.columns
    assert 'play2_result_05x' in facts.columns
    assert 'play2_result_075x' in facts.columns
    assert 'play3_result_075x' in facts.columns
    assert 'play2_with_bias_025x' in facts.columns
    assert 'play3_with_bias_075x' in facts.columns

    assert (facts['play2_default_target_lvl'] == 0.25).all()
    assert (facts['play3_default_target_lvl'] == 0.75).all()


def test_cross_midnight_fvg_invalidation_uses_full_outcome_window():
    t = pd.date_range("2026-06-01 19:00:00", "2026-06-01 22:00:00", freq="1min", tz="US/Eastern")
    df = pd.DataFrame(index=t)
    df['open'] = 100.5
    df['high'] = 101.0
    df['low'] = 100.0
    df['close'] = 100.5
    df['volume'] = 100

    # Force a bullish 5m FVG inside Tokyo IB (20:00-21:00 ET, ET_fixed).
    m0 = (df.index >= pd.Timestamp("2026-06-01 20:00:00", tz="US/Eastern")) & (df.index < pd.Timestamp("2026-06-01 20:05:00", tz="US/Eastern"))
    m1 = (df.index >= pd.Timestamp("2026-06-01 20:05:00", tz="US/Eastern")) & (df.index < pd.Timestamp("2026-06-01 20:10:00", tz="US/Eastern"))
    m2 = (df.index >= pd.Timestamp("2026-06-01 20:10:00", tz="US/Eastern")) & (df.index < pd.Timestamp("2026-06-01 20:15:00", tz="US/Eastern"))
    df.loc[m0, ['high', 'low', 'close']] = [100.0, 99.0, 99.5]
    df.loc[m1, ['high', 'low', 'close']] = [102.0, 101.0, 101.5]
    df.loc[m2, ['high', 'low', 'close']] = [105.0, 104.0, 104.5]

    # Invalidate after IB close but still inside outcome window (cross-midnight session).
    inv = df.index == pd.Timestamp("2026-06-01 21:30:00", tz="US/Eastern")
    df.loc[inv, ['high', 'low', 'close']] = [101.0, 97.0, 98.0]

    facts, _, _ = calculate_ib_statistics_v5(
        df_1m=df,
        symbol="NQ1",
        session_choice="Tokyo IB",
        time_basis="ET_fixed",
        use_fvg=True,
    )

    assert not facts.empty
    row = facts.iloc[0]
    assert row['bias_fvg'] == 1
    assert row['bias_fvg_ifvg'] == -1
    assert pd.notna(row['fvg_broken_time'])


def test_play2_same_bar_entry_and_stop_is_loss_not_nosetup():
    t = pd.date_range("2026-06-01 09:30:00", "2026-06-01 16:00:00", freq="1min", tz="US/Eastern")
    df = pd.DataFrame(index=t)
    df['open'] = 99.5
    df['high'] = 100.0
    df['low'] = 99.0
    df['close'] = 99.5
    df['volume'] = 100

    # Breakout close-confirmed at 10:31.
    b = df.index == pd.Timestamp("2026-06-01 10:31:00", tz="US/Eastern")
    df.loc[b, ['high', 'low', 'close']] = [100.2, 99.6, 100.1]

    # Next bar touches mid (entry) and opposite boundary stop on same bar.
    e = df.index == pd.Timestamp("2026-06-01 10:32:00", tz="US/Eastern")
    df.loc[e, ['high', 'low', 'close']] = [100.2, 98.9, 99.2]

    facts, _, _ = calculate_ib_statistics_v5(
        df_1m=df,
        symbol="NQ1",
        session_choice="NY AM IB",
        time_basis="ET_fixed",
        use_fvg=True,
    )

    assert not facts.empty
    row = facts.iloc[0]
    assert row['play2_result_05x'] == -1


def test_play3_same_bar_fill_and_stop_is_loss_not_nosetup():
    t = pd.date_range("2026-06-01 09:30:00", "2026-06-01 16:00:00", freq="1min", tz="US/Eastern")
    df = pd.DataFrame(index=t)
    df['open'] = 99.5
    df['high'] = 100.0
    df['low'] = 99.0
    df['close'] = 99.5
    df['volume'] = 100

    # Breakout close-confirmed at 10:31.
    b = df.index == pd.Timestamp("2026-06-01 10:31:00", tz="US/Eastern")
    df.loc[b, ['high', 'low', 'close']] = [100.2, 99.6, 100.1]

    # Overshoot first (for play3 lvl=0.25 uses overshoot=0.125x).
    o = df.index == pd.Timestamp("2026-06-01 10:32:00", tz="US/Eastern")
    df.loc[o, ['high', 'low', 'close']] = [100.2, 99.7, 100.15]

    # Next bar has close-confirmed fill and stop exceed on the same bar.
    f = df.index == pd.Timestamp("2026-06-01 10:33:00", tz="US/Eastern")
    df.loc[f, ['high', 'low', 'close']] = [100.3, 99.0, 99.9]

    facts, _, _ = calculate_ib_statistics_v5(
        df_1m=df,
        symbol="NQ1",
        session_choice="NY AM IB",
        time_basis="ET_fixed",
        use_fvg=True,
    )

    assert not facts.empty
    row = facts.iloc[0]
    assert row['play3_result_025x'] == -1


def test_legacy_precomputed_fvg_without_pattern_extremes_is_supported():
    t = pd.date_range("2026-06-01 09:30:00", "2026-06-01 16:00:00", freq="1min", tz="US/Eastern")
    df = pd.DataFrame(index=t)
    df['open'] = 100.0
    df['high'] = 101.0
    df['low'] = 99.0
    df['close'] = 100.0
    df['volume'] = 100

    # Simulate legacy precomputed FVG schema (missing fvg_low/fvg_high).
    fvg_precalc = pd.DataFrame(index=t)
    fvg_precalc['fvg_type'] = 0
    fvg_precalc['fvg_top'] = np.nan
    fvg_precalc['fvg_bottom'] = np.nan
    fvg_precalc['fvg_finalized_time'] = fvg_precalc.index + pd.Timedelta('5min')
    fvg_precalc['logical_date'] = pd.to_datetime(fvg_precalc.index.date).date

    facts, touches, plays = calculate_ib_statistics_v5(
        df_1m=df,
        symbol="NQ1",
        session_choice="NY AM IB",
        time_basis="ET_fixed",
        use_fvg=True,
        fvg_df_precalc=fvg_precalc,
    )

    assert not facts.empty
    assert 'fvg_low' in facts.columns
    assert 'fvg_high' in facts.columns
