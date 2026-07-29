"""
NQStats Initial Balance (IB) Library.
Aligns Python calculations with Pine Script multi-session and streak statistics.
"""

import pandas as pd
import numpy as np
import pytz
from datetime import time, datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List


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

from scripts.libs_py.nqstats.sessions import (
    get_logical_trading_date,
    get_dst_flags,
    get_time_mask,
    get_time_mask_vectorized,
    normalize_to_eastern
)

# Legacy session configs for backward compatibility
# NT8 parity: out_end = 15:51 so last in_out bar = 15:50 (matches NT8 FlattenBy=1550)
SESSION_CONFIGS = {
    "Globex IB":   {"ib_start": time(18, 0), "ib_end": time(19, 0), "out_end": time(2, 0)},
    "Tokyo IB":    {"ib_start": time(20, 0), "ib_end": time(21, 0), "out_end": time(2, 0)},
    "London IB":   {"ib_start": time(3, 0),  "ib_end": time(4, 0),  "out_end": time(6, 0)},
    "Midnight OR": {"ib_start": time(0, 0),  "ib_end": time(0, 30), "out_end": time(15, 51)},
    "NY AM IB":    {"ib_start": time(9, 30), "ib_end": time(10, 30), "out_end": time(15, 51)},
    "NY PM IB":    {"ib_start": time(13, 30), "ib_end": time(14, 30), "out_end": time(15, 51)}
}

# New v5 session configs
# NT8 parity: RTH sessions use out_end = 15:51 so last in_out bar = 15:50
# (matches NT8 IBStrategyBase FlattenBy=1550). The mask is (times < out_end),
# so out_end=15:51 includes the 15:50 bar but excludes 15:51+.
SESSION_CONFIGS_V5 = {
    "Globex IB":   {"ib_start": time(18, 0), "ib_end": time(19, 0), "out_end": time(20, 0), "time_basis": "ET_fixed"},
    "Tokyo IB":    {"ib_start": time(20, 0), "ib_end": time(21, 0), "out_end": time(2, 0), "time_basis": "event_anchored"},
    "London IB":   {"ib_start": time(3, 0),  "ib_end": time(4, 0),  "out_end": time(6, 0),  "time_basis": "event_anchored"},
    "Midnight OR": {"ib_start": time(0, 0),  "ib_end": time(0, 30), "out_end": time(15, 51), "time_basis": "ET_fixed"},
    "NY AM IB":    {"ib_start": time(9, 30), "ib_end": time(10, 30), "out_end": time(15, 51), "time_basis": "ET_fixed"},
    "NY PM IB":    {"ib_start": time(13, 30), "ib_end": time(14, 30), "out_end": time(15, 51), "time_basis": "ET_fixed"}
}


def detect_fvgs_vectorized(df: pd.DataFrame, timeframe: str = '5min') -> pd.DataFrame:
    """Detects 3-bar Fair Value Gaps on a fixed timeframe (vectorized).
    
    .. deprecated::
        Wrapper around ``ict_engine.core.pa.detect_fvg`` (the canonical
        library implementation). Kept for backward compatibility.
    """
    from scripts.libs_py.ict_engine import detect_fvg
    return detect_fvg(df, resample_rule=timeframe)


def detect_fvgs_v5(df: pd.DataFrame, timeframe: str = '5min') -> pd.DataFrame:
    """Detects 3-bar Fair Value Gaps on a fixed timeframe (vectorized) for v5.

    Returns a DataFrame with columns: fvg_type, fvg_top, fvg_bottom,
    fvg_finalized_time, fvg_low, fvg_high.

    .. note::
        Now delegates to ``ict_engine.core.pa.detect_fvg`` (the canonical
        library implementation). The schema is identical so all existing
        callers work unchanged.
    """
    from scripts.libs_py.ict_engine import detect_fvg
    return detect_fvg(df, resample_rule=timeframe)

def calculate_streaks(series: pd.Series) -> pd.Series:
    """Calculates signed streak lengths (positive for 1s, negative for -1s, 0 resets)."""
    is_zero = series == 0
    changed = (series != series.shift(1)) | is_zero
    streak_groups = changed.cumsum()
    streaks = series.groupby(streak_groups).cumcount() + 1
    streaks = np.where(is_zero, 0, streaks)
    return pd.Series(streaks * np.sign(series), index=series.index)

def calculate_rolling_win_rate(win_bools: pd.Series, window: int) -> pd.Series:
    """Causal rolling average of wins, ignoring NaNs."""
    return win_bools.rolling(window, min_periods=1).mean() * 100

def calculate_expanding_prob_after_streak(win_bools: pd.Series, play_streaks: pd.Series, target_streak_val: int) -> pd.Series:
    """Causal expanding average of wins conditioned on prior streak value matching target."""
    prior_streak = play_streaks.shift(1)
    current_win = win_bools == 1
    matches = prior_streak == target_streak_val
    matched_wins = pd.Series(np.where(matches, current_win.astype(float), np.nan), index=win_bools.index)
    return matched_wins.expanding(min_periods=1).mean().shift(1)

# Original calculate_ib_statistics for backward compatibility
def calculate_ib_statistics(df_1m: pd.DataFrame, session_choice: str = "NY AM IB", use_fvg: bool = True) -> pd.DataFrame:
    """
    Legacy implementation of calculate_ib_statistics.
    Computes Initial Balance stats and outcome windows for the selected session.
    """
    if session_choice not in SESSION_CONFIGS:
        raise ValueError(f"Unknown session choice: {session_choice}")
        
    cfg = SESSION_CONFIGS[session_choice]
    ib_start, ib_end, out_end = cfg["ib_start"], cfg["ib_end"], cfg["out_end"]
    
    df = df_1m.copy()
    if df.index.tz:
        df = df.tz_convert('US/Eastern')
    df['logical_date'] = get_logical_trading_date(df.index)
    df['bar_idx'] = np.arange(len(df))
    
    bar_times = df.index.time
    in_ib = get_time_mask(bar_times, ib_start, ib_end)
    in_out = get_time_mask(bar_times, ib_end, out_end)
    
    ib_bars = df[in_ib]
    ib_agg = ib_bars.groupby('logical_date').agg(
        ib_high=('high', 'max'),
        ib_low=('low', 'min'),
        ib_open=('open', 'first'),
        ib_close=('close', 'last')
    )
    ib_agg['ib_mid'] = (ib_agg['ib_high'] + ib_agg['ib_low']) / 2.0
    ib_agg['ib_range'] = ib_agg['ib_high'] - ib_agg['ib_low']
    
    high_idx = ib_bars.groupby('logical_date')['high'].idxmax()
    low_idx = ib_bars.groupby('logical_date')['low'].idxmin()
    ib_agg['high_idx'] = high_idx
    ib_agg['low_idx'] = low_idx
    
    ib_agg['bFormation'] = np.where(
        ib_agg['high_idx'] > ib_agg['low_idx'], 1,
        np.where(ib_agg['high_idx'] < ib_agg['low_idx'], -1,
                 np.where(ib_agg['ib_close'] > ib_agg['ib_open'], 1, -1))
    )
    
    ib_agg['bCloseDir'] = np.where(
        ib_agg['ib_close'] > ib_agg['ib_open'], 1,
        np.where(ib_agg['ib_close'] < ib_agg['ib_open'], -1, 0)
    )
    
    if use_fvg:
        fvg_df = detect_fvgs_vectorized(df, '5min')
        df['fvg_type'] = fvg_df['fvg_type']
        df['fvg_top'] = fvg_df['fvg_top']
        df['fvg_bottom'] = fvg_df['fvg_bottom']
        
        fvg_start_time = (datetime.combine(datetime.min, ib_start) + timedelta(minutes=10)).time()
        fvg_eligible = get_time_mask(bar_times, fvg_start_time, ib_end) & in_ib
        
        fvg_in_ib = fvg_eligible & (df['fvg_type'] != 0)
        fvg_count_cum = fvg_in_ib.groupby(df['logical_date']).cumsum()
        first_fvg_mask = fvg_in_ib & (fvg_count_cum == 1)
        
        daily_fvg = df[first_fvg_mask].groupby('logical_date').first()[['fvg_type', 'fvg_top', 'fvg_bottom', 'bar_idx']]
        ib_agg = ib_agg.join(daily_fvg, rsuffix='_fvg_first')
        
        ib_agg['fvg_type_first'] = ib_agg['fvg_type'].fillna(0).astype(int)
        ib_agg['fvg_top_first'] = ib_agg['fvg_top']
        ib_agg['fvg_bottom_first'] = ib_agg['fvg_bottom']
        ib_agg['fvg_bar_idx'] = ib_agg['bar_idx']
        
        df = df.join(ib_agg[['fvg_type_first', 'fvg_top_first', 'fvg_bottom_first', 'fvg_bar_idx']], on='logical_date')
        
        df['fvg_is_broken_bar'] = np.where(
            (df['fvg_bar_idx'].notna()) & (df['bar_idx'] > df['fvg_bar_idx']),
            np.where(
                df['fvg_type_first'] == 1, df['close'] < df['fvg_bottom_first'],
                np.where(df['fvg_type_first'] == -1, df['close'] > df['fvg_top_first'], False)
            ),
            False
        )
        df['fvg_broken'] = df.groupby('logical_date')['fvg_is_broken_bar'].cummax()
        
        df['bFVG'] = np.where(df['bar_idx'] >= df['fvg_bar_idx'], df['fvg_type_first'], 0)
        df['bFVGifvg'] = np.where(df['bar_idx'] >= df['fvg_bar_idx'], 
                                  np.where(df['fvg_broken'], -df['fvg_type_first'], df['fvg_type_first']), 0)
    else:
        df['bFVG'] = 0
        df['bFVGifvg'] = 0
        
    df = df.join(ib_agg[['bFormation', 'bCloseDir', 'ib_high', 'ib_low', 'ib_mid', 'ib_range']], on='logical_date', rsuffix='_daily')
    df['total_vote'] = df['bFormation'] + df['bCloseDir'] + df['bFVG'] + df['bFVGifvg']
    df['dominant_bias'] = np.select(
        [df['total_vote'] >= 2, df['total_vote'] <= -2],
        ['BULLISH', 'BEARISH'],
        default='NEUTRAL'
    )
    df['confidence'] = np.select(
        [df['total_vote'].abs() >= 3, df['total_vote'].abs() == 2],
        ['HIGH', 'MEDIUM'],
        default='LOW'
    )
    return df

def calculate_ib_bias(sessions_df: pd.DataFrame) -> pd.DataFrame:
    """Legacy implementation of calculate_ib_bias."""
    ib_high = sessions_df['ib_high']
    ib_low = sessions_df['ib_low']
    ib_close = sessions_df['ib_close']
    ib_mid = sessions_df['ib_mid']
    
    bias = np.where(ib_close > ib_mid, "LONG", "SHORT")
    bias_conf = np.where(ib_close > ib_mid, 0.823, 0.80)
    
    return pd.DataFrame({
        'ib_bias': bias,
        'ib_conviction': bias_conf,
        'ib_break_prob': 0.961
    }, index=sessions_df.index)


def evaluate_target_vs_stop_consolidated(
    df: pd.DataFrame,
    races: Dict[str, Tuple[pd.Series, pd.Series, pd.Series, pd.Series]],  # name -> (bias, target_price, stop_price, start_time)
    ib_agg: pd.DataFrame,
    date_pos_1m: np.ndarray = None
) -> Dict[str, pd.Series]:
    """
    Evaluates target vs stop races for multiple configurations simultaneously in a single groupby.
    date_pos_1m: integer array mapping each 1m row to its position in ib_agg (avoids reindex overhead).
    """
    if not races:
        return {}
        
    logical_date = df['logical_date']
    races_df = pd.DataFrame(index=df.index)
    races_df['logical_date'] = logical_date
    
    use_pos = date_pos_1m is not None
    
    # Broadcast all races to 1m using O(n) numpy indexing
    for name, (bias, target_price, stop_price, start_time) in races.items():
        if use_pos:
            bias_1m = bias.values[date_pos_1m]
            target_1m = target_price.values[date_pos_1m]
            stop_1m = stop_price.values[date_pos_1m]
            start_1m = start_time.values[date_pos_1m]
        else:
            bias_1m = bias.reindex(logical_date).values
            target_1m = target_price.reindex(logical_date).values
            stop_1m = stop_price.reindex(logical_date).values
            start_1m = start_time.reindex(logical_date).values
        
        is_after_start = df.index >= start_1m
        is_eligible = df['in_out'] & is_after_start
        
        target_hit = is_eligible & np.where(
            bias_1m == 1, df['high'] >= target_1m,
            np.where(bias_1m == -1, df['low'] <= target_1m, False)
        )
        
        stop_hit = is_eligible & np.where(
            bias_1m == 1, df['low'] <= stop_1m,
            np.where(bias_1m == -1, df['high'] >= stop_1m, False)
        )
        
        races_df[f'tgt_{name}'] = np.where(target_hit, df['bar_idx'], len(df))
        races_df[f'stop_{name}'] = np.where(stop_hit, df['bar_idx'], len(df))
        
    # Group by once!
    races_min = races_df.groupby('logical_date').min()
    
    # Build a pos map for ib_agg-level reindex (from races_min index to ib_agg index)
    ib_agg_pos = {d: i for i, d in enumerate(ib_agg.index)}
    races_pos = np.array([ib_agg_pos.get(d, -1) for d in races_min.index])
    valid_mask = races_pos >= 0
    
    results = {}
    for name in races.keys():
        min_target_arr = np.full(len(ib_agg), len(df), dtype=np.intp)
        min_stop_arr = np.full(len(ib_agg), len(df), dtype=np.intp)
        if valid_mask.any():
            min_target_arr[races_pos[valid_mask]] = races_min[f'tgt_{name}'].values[valid_mask]
            min_stop_arr[races_pos[valid_mask]] = races_min[f'stop_{name}'].values[valid_mask]
        
        target_reached = min_target_arr < len(df)
        stop_reached = min_stop_arr < len(df)
        
        correct = target_reached & (~stop_reached | (min_target_arr < min_stop_arr))
        results[name] = pd.Series(correct, index=ib_agg.index)
        
    return results


# ── V5 IMPLEMENTATION FOR THE EDGEFUL PIPELINE ────────────────────────────────────────

def evaluate_all_plays_consolidated(
    df: pd.DataFrame,
    plays_config: List[Dict[str, Any]],  # list of dicts with active, direction, entry_price, target_price, stop_price, entry_idx
    ib_agg: pd.DataFrame,
    date_pos_1m: np.ndarray = None
) -> List[Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]]:
    """
    Evaluates play results, MAE, MFE excursions, and realized R for all plays consolidated in 3 groupbys.
    date_pos_1m: integer array mapping each 1m row to its position in ib_agg (avoids reindex overhead).
    """
    if not plays_config:
        return []
        
    logical_date = df['logical_date']
    use_pos = date_pos_1m is not None
    
    # Build ib_agg-level position map for hits_min -> ib_agg alignment
    ib_agg_dates = ib_agg.index
    ib_agg_pos = {d: i for i, d in enumerate(ib_agg_dates)}
    
    # Calculate max_out_idx once using numpy scatter
    out_bars = df[df['in_out']]
    max_out_idx_by_date = out_bars.groupby('logical_date')['bar_idx'].max()
    max_out_idx_arr = np.full(len(ib_agg), -1, dtype=np.intp)
    for d, v in max_out_idx_by_date.items():
        pos = ib_agg_pos.get(d)
        if pos is not None:
            max_out_idx_arr[pos] = v
            
    # Pre-extract closeout prices at the end of outcome window
    closeout_prices = np.where(max_out_idx_arr >= 0, df['close'].values[max_out_idx_arr], np.nan)
    
    # Broadcast max_out_idx to 1m
    max_out_idx_1m = max_out_idx_arr[date_pos_1m] if use_pos else \
        pd.Series(max_out_idx_arr, index=ib_agg_dates).reindex(logical_date).values
    
    hits_df = pd.DataFrame(index=df.index)
    hits_df['logical_date'] = logical_date
    
    for i, cfg in enumerate(plays_config):
        if use_pos:
            active_1m = cfg['active'].values[date_pos_1m]
            dir_1m = cfg['direction'].values[date_pos_1m]
            target_1m = cfg['target_price'].values[date_pos_1m]
            stop_1m = cfg['stop_price'].values[date_pos_1m]
            entry_idx_1m = cfg['entry_idx'].values[date_pos_1m]
        else:
            active_1m = cfg['active'].reindex(logical_date).values
            dir_1m = cfg['direction'].reindex(logical_date).values
            target_1m = cfg['target_price'].reindex(logical_date).values
            stop_1m = cfg['stop_price'].reindex(logical_date).values
            entry_idx_1m = cfg['entry_idx'].reindex(logical_date).values
        
        is_eligible = df['in_out'] & active_1m & (df['bar_idx'] >= entry_idx_1m)
        
        target_hit = is_eligible & np.where(
            dir_1m == 1, df['high'] >= target_1m,
            np.where(dir_1m == -1, df['low'] <= target_1m, False)
        )
        stop_hit = is_eligible & np.where(
            dir_1m == 1, df['low'] <= stop_1m,
            np.where(dir_1m == -1, df['high'] >= stop_1m, False)
        )
        
        hits_df[f'tgt_{i}'] = np.where(target_hit, df['bar_idx'], len(df))
        hits_df[f'stop_{i}'] = np.where(stop_hit, df['bar_idx'], len(df))
        
    # Group once to find first target/stop hit index
    hits_min = hits_df.groupby('logical_date').min()
    
    # Scatter hits_min back to ib_agg positions
    hits_pos = np.array([ib_agg_pos.get(d, -1) for d in hits_min.index])
    valid_hits = hits_pos >= 0
    
    exit_indices = []
    play_results = []
    realized_rs = []
    timeout_losses = []
    
    for i, cfg in enumerate(plays_config):
        min_tgt_arr = np.full(len(ib_agg), len(df), dtype=np.intp)
        min_stp_arr = np.full(len(ib_agg), len(df), dtype=np.intp)
        if valid_hits.any():
            min_tgt_arr[hits_pos[valid_hits]] = hits_min[f'tgt_{i}'].values[valid_hits]
            min_stp_arr[hits_pos[valid_hits]] = hits_min[f'stop_{i}'].values[valid_hits]
        
        target_reached = min_tgt_arr < len(df)
        stop_reached = min_stp_arr < len(df)
        
        # No-setup remains 0. Once setup is active, target-first is win; otherwise loss.
        entry_price_val = cfg['entry_price'].values
        target_first = target_reached & (~stop_reached | (min_tgt_arr < min_stp_arr))
        stop_first = stop_reached & (~target_reached | (min_stp_arr <= min_tgt_arr))
        timeout_loss = cfg['active'].values & (~target_first) & (~stop_first)
        
        play_res = np.where(
            cfg['active'].values,
            np.where(
                target_first,
                1,
                -1
            ),
            0
        )
        play_results.append(pd.Series(play_res, index=ib_agg.index))
        timeout_losses.append(pd.Series(timeout_loss, index=ib_agg.index))
        
        # Realized R calculation
        target_dist = np.abs(cfg['target_price'].values - entry_price_val)
        stop_dist = np.abs(entry_price_val - cfg['stop_price'].values)
        stop_dist = np.where(stop_dist == 0, 1e-9, stop_dist)
        target_mult = target_dist / stop_dist

        timeout_r = cfg['direction'].values * (closeout_prices - entry_price_val) / stop_dist
        # If no outcome close is available for a day, keep conservative timeout fallback.
        timeout_r = np.where(np.isfinite(closeout_prices), timeout_r, -1.0)

        realized_r = np.where(
            cfg['active'].values,
            np.where(
                target_first,
                target_mult,
                np.where(stop_first, -1.0, timeout_r)
            ),
            0.0
        )
        realized_rs.append(pd.Series(realized_r, index=ib_agg.index))
        
        exit_idx = np.minimum(
            np.minimum(min_tgt_arr, min_stp_arr),
            max_out_idx_arr
        )
        exit_indices.append(exit_idx)
        
    # Second groupby to find trade high and low
    bounds_df = pd.DataFrame(index=df.index)
    bounds_df['logical_date'] = logical_date
    
    for i, cfg in enumerate(plays_config):
        if use_pos:
            active_1m = cfg['active'].values[date_pos_1m]
            entry_idx_1m = cfg['entry_idx'].values[date_pos_1m]
        else:
            active_1m = cfg['active'].reindex(logical_date).values
            entry_idx_1m = cfg['entry_idx'].reindex(logical_date).values
        
        exit_idx_1m = exit_indices[i][date_pos_1m] if use_pos else \
            pd.Series(exit_indices[i], index=ib_agg_dates).reindex(logical_date).values
        
        in_trade = (df['bar_idx'] >= entry_idx_1m) & (df['bar_idx'] <= exit_idx_1m) & active_1m
        
        bounds_df[f'high_{i}'] = np.where(in_trade, df['high'], -np.inf)
        bounds_df[f'low_{i}'] = np.where(in_trade, df['low'], np.inf)
        
    bounds_agg = bounds_df.groupby('logical_date').agg({
        **{f'high_{i}': 'max' for i in range(len(plays_config))},
        **{f'low_{i}': 'min' for i in range(len(plays_config))}
    })
    
    # Scatter bounds_agg to ib_agg positions
    bounds_pos = np.array([ib_agg_pos.get(d, -1) for d in bounds_agg.index])
    valid_bounds = bounds_pos >= 0
    
    outputs = []
    mid_vals = ib_agg['ib_mid'].values
    
    for i, cfg in enumerate(plays_config):
        max_high_arr = np.full(len(ib_agg), -np.inf)
        min_low_arr = np.full(len(ib_agg), np.inf)
        if valid_bounds.any():
            max_high_arr[bounds_pos[valid_bounds]] = bounds_agg[f'high_{i}'].values[valid_bounds]
            min_low_arr[bounds_pos[valid_bounds]] = bounds_agg[f'low_{i}'].values[valid_bounds]
        max_high = pd.Series(max_high_arr, index=ib_agg.index)
        min_low = pd.Series(min_low_arr, index=ib_agg.index)
        
        mfe = np.where(
            cfg['active'] & (cfg['direction'] == 1), max_high - cfg['entry_price'],
            np.where(cfg['active'] & (cfg['direction'] == -1), cfg['entry_price'] - min_low, 0.0)
        )
        mae = np.where(
            cfg['active'] & (cfg['direction'] == 1), cfg['entry_price'] - min_low,
            np.where(cfg['active'] & (cfg['direction'] == -1), max_high - cfg['entry_price'], 0.0)
        )
        mfe = np.maximum(0.0, mfe)
        mae = np.maximum(0.0, mae)
        
        mfe_pct = np.where(mid_vals > 0, mfe / mid_vals * 100, 0.0)
        mae_pct = np.where(mid_vals > 0, mae / mid_vals * 100, 0.0)
        
        outputs.append((play_results[i], pd.Series(mfe_pct, index=ib_agg.index), pd.Series(mae_pct, index=ib_agg.index), realized_rs[i], timeout_losses[i]))
        
    return outputs


def extract_level_touch_details(df: pd.DataFrame, ib_agg: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts touch details for structural levels {0, 25, 50, 75, 100}% across phases (consolidated single groupby).
    """
    logical_date = df['logical_date']
    
    low_1m = ib_agg['ib_low'].reindex(logical_date).values
    range_1m = ib_agg['ib_range'].reindex(logical_date).values
    mid_lock_1m = ib_agg['mid_lock_time'].reindex(logical_date).values
    
    is_pre_lock = df['in_ib'] & (df.index < mid_lock_1m)
    is_post_lock = df['in_ib'] & (df.index >= mid_lock_1m)
    is_outcome = df['in_out']
    
    phase_arr = np.select(
        [is_pre_lock, is_post_lock, is_outcome],
        ['formation_pre_lock', 'formation_post_lock', 'outcome'],
        default='outside'
    )
    
    df_touches = []
    levels = [0, 25, 50, 75, 100]
    
    for lvl in levels:
        lvl_frac = lvl / 100.0
        lvl_price = low_1m + lvl_frac * range_1m
        
        is_touch = (df['low'] <= lvl_price) & (df['high'] >= lvl_price) & (phase_arr != 'outside')
        if is_touch.any():
            df_touches.append(pd.DataFrame({
                'logical_date': logical_date[is_touch],
                'level_pct': lvl,
                'phase': phase_arr[is_touch],
                'is_touch': True,
                'timestamp': df.index[is_touch]
            }))
            
    if not df_touches:
        return pd.DataFrame(columns=['logical_date', 'level_pct', 'phase', 'first_touch_time', 'last_touch_time', 'touch_count'])
        
    df_all_touches = pd.concat(df_touches, ignore_index=True)
    res_df = df_all_touches.groupby(['logical_date', 'level_pct', 'phase']).agg(
        first_touch_time=('timestamp', 'min'),
        last_touch_time=('timestamp', 'max'),
        touch_count=('is_touch', 'count')
    ).reset_index()
    
    return res_df


def calculate_ib_statistics_v5(
    df_1m: pd.DataFrame,
    symbol: str,
    session_choice: str = "NY AM IB",
    time_basis: str = "ET_fixed",
    false_break_min_ext: float = 0.5,
    use_fvg: bool = True,
    vix_series: Optional[pd.Series] = None,
    df_1m_precalc: Optional[pd.DataFrame] = None,
    fvg_df_precalc: Optional[pd.DataFrame] = None,
    daily_atr_precalc: Optional[pd.Series] = None,
    legacy_default_play_levels: Optional[Dict[int, float]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Computes complete Initial Balance stats and details for the selected session (v5 Spec).
    Returns (facts_df, level_touch_df, play_detail_df).
    """
    if session_choice not in SESSION_CONFIGS_V5:
        raise ValueError(f"Unknown session choice: {session_choice}")
        
    cfg = SESSION_CONFIGS_V5[session_choice]
    
    # 1. Normalize timezone and dates
    if df_1m_precalc is not None:
        df = df_1m_precalc.copy()
        if 'timestamp' not in df.columns:
            df['timestamp'] = df.index
        if 'datetime' not in df.columns:
            df['datetime'] = df.index
        if 'logical_date' not in df.columns:
            df['logical_date'] = get_logical_trading_date(df.index)
        if 'bar_idx' not in df.columns:
            df['bar_idx'] = np.arange(len(df))
        if 'minutes_from_midnight' not in df.columns:
            df['minutes_from_midnight'] = df.index.hour * 60 + df.index.minute

        if 'us_dst' in df.columns and 'uk_dst' in df.columns:
            us_dst = df['us_dst']
            uk_dst = df['uk_dst']
        else:
            us_dst, uk_dst = get_dst_flags(df.index)
            df['us_dst'] = us_dst
            df['uk_dst'] = uk_dst
    else:
        df = normalize_to_eastern(df_1m).copy()
        df = df[~df.index.isna()]
        df['timestamp'] = df.index
        df['datetime'] = df.index
        df['logical_date'] = get_logical_trading_date(df.index)
        df['bar_idx'] = np.arange(len(df))
        
        # Get DST flags
        us_dst, uk_dst = get_dst_flags(df.index)
        df['us_dst'] = us_dst
        df['uk_dst'] = uk_dst
    
    # Session starts, ends, outcomes (using integer minutes from midnight)
    bar_minutes = df['minutes_from_midnight'].values if 'minutes_from_midnight' in df.columns else (df.index.hour * 60 + df.index.minute).values
    
    if time_basis == "event_anchored" and session_choice in ["Tokyo IB", "London IB"]:
        if session_choice == "Tokyo IB":
            ib_start_mins = np.where(us_dst, 20 * 60, 19 * 60)
            ib_end_mins = np.where(us_dst, 21 * 60, 20 * 60)
            out_end_mins = np.repeat(2 * 60, len(df))
            
            ib_start_arr = np.where(us_dst, time(20, 0), time(19, 0))
            ib_end_arr = np.where(us_dst, time(21, 0), time(20, 0))
            out_end_arr = np.repeat(time(2, 0), len(df))
            dst_regime = np.where(us_dst, "aligned", "shifted")
            offset_arr = np.where(us_dst, 0, -1)
        else: # London IB
            ib_start_mins = np.select(
                [us_dst == uk_dst, us_dst & ~uk_dst, ~us_dst & uk_dst],
                [3 * 60, 4 * 60, 2 * 60],
                default=3 * 60
            )
            ib_end_mins = np.select(
                [us_dst == uk_dst, us_dst & ~uk_dst, ~us_dst & uk_dst],
                [4 * 60, 5 * 60, 3 * 60],
                default=4 * 60
            )
            out_end_mins = np.repeat(6 * 60, len(df))
            
            ib_start_arr = np.select(
                [us_dst == uk_dst, us_dst & ~uk_dst, ~us_dst & uk_dst],
                [time(3, 0), time(4, 0), time(2, 0)],
                default=time(3, 0)
            )
            ib_end_arr = np.select(
                [us_dst == uk_dst, us_dst & ~uk_dst, ~us_dst & uk_dst],
                [time(4, 0), time(5, 0), time(3, 0)],
                default=time(4, 0)
            )
            out_end_arr = np.repeat(time(6, 0), len(df))
            dst_regime = np.select(
                [us_dst == uk_dst, us_dst & ~uk_dst, ~us_dst & uk_dst],
                ["aligned", "shifted", "shifted"],
                default="aligned"
            )
            offset_arr = np.select(
                [us_dst == uk_dst, us_dst & ~uk_dst, ~us_dst & uk_dst],
                [0, 1, -1],
                default=0
            )
    else:
        cfg_start_min = cfg["ib_start"].hour * 60 + cfg["ib_start"].minute
        cfg_end_min = cfg["ib_end"].hour * 60 + cfg["ib_end"].minute
        cfg_out_min = cfg["out_end"].hour * 60 + cfg["out_end"].minute
        
        ib_start_mins = np.repeat(cfg_start_min, len(df))
        ib_end_mins = np.repeat(cfg_end_min, len(df))
        out_end_mins = np.repeat(cfg_out_min, len(df))
        
        ib_start_arr = np.repeat(cfg["ib_start"], len(df))
        ib_end_arr = np.repeat(cfg["ib_end"], len(df))
        out_end_arr = np.repeat(cfg["out_end"], len(df))
        dst_regime = np.repeat("aligned", len(df))
        offset_arr = np.repeat(0, len(df))
        
    df['ib_start_t'] = ib_start_arr
    df['ib_end_t'] = ib_end_arr
    df['out_end_t'] = out_end_arr
    df['dst_regime'] = dst_regime
    df['et_window_offset_hours'] = offset_arr
    df['time_basis'] = time_basis
    df['ib_start_mins'] = ib_start_mins
    df['ib_end_mins'] = ib_end_mins
    df['out_end_mins'] = out_end_mins
    
    # 2. Masking (using vectorized integer minutes for 1000x speedup)
    in_ib = get_time_mask_vectorized(bar_minutes, ib_start_mins, ib_end_mins)
    in_out = get_time_mask_vectorized(bar_minutes, ib_end_mins, out_end_mins)
    
    df['in_ib'] = in_ib
    df['in_out'] = in_out
    df['minutes_from_midnight'] = bar_minutes
    
    # Extract IB ranges
    ib_bars = df[in_ib]
    if ib_bars.empty:
        # Return empty sets
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
    ib_agg = ib_bars.groupby('logical_date').agg(
        ib_high=('high', 'max'),
        ib_low=('low', 'min'),
        ib_open=('open', 'first'),
        ib_close=('close', 'last')
    )
    ib_agg['ib_mid'] = (ib_agg['ib_high'] + ib_agg['ib_low']) / 2.0
    ib_agg['ib_range'] = ib_agg['ib_high'] - ib_agg['ib_low']
    ib_agg['range_pts'] = ib_agg['ib_range']
    ib_agg['range_pct'] = ib_agg['range_pts'] / ib_agg['ib_mid'] * 100
    
    # Calculate daily ATR (Wilder's 14)
    if daily_atr_precalc is not None:
        ib_agg['range_atr'] = ib_agg['range_pts'] / daily_atr_precalc.reindex(ib_agg.index)
    else:
        daily_ohlc = df.groupby('logical_date').agg(
            high=('high', 'max'),
            low=('low', 'min'),
            close=('close', 'last')
        )
        prev_close = daily_ohlc['close'].shift(1)
        tr = pd.concat([
            daily_ohlc['high'] - daily_ohlc['low'],
            (daily_ohlc['high'] - prev_close).abs(),
            (daily_ohlc['low'] - prev_close).abs()
        ], axis=1).max(axis=1)
        daily_atr = tr.ewm(com=14 - 1, adjust=False, min_periods=14).mean()
        ib_agg['range_atr'] = ib_agg['range_pts'] / daily_atr
    
    # Trailing quantiles for range
    ib_agg['range_pctile_20'] = ib_agg['range_pts'].rolling(20, min_periods=1).rank(pct=True) * 100
    ib_agg['range_pctile_60'] = ib_agg['range_pts'].rolling(60, min_periods=1).rank(pct=True) * 100
    
    # Tercile buckets
    q1_3 = ib_agg['range_pct'].quantile(1/3)
    q2_3 = ib_agg['range_pct'].quantile(2/3)
    ib_agg['range_bucket_full'] = np.select(
        [ib_agg['range_pct'] <= q1_3, ib_agg['range_pct'] <= q2_3],
        ['Small', 'Medium'],
        default='Large'
    )
    
    q1_3_trailing = ib_agg['range_pct'].expanding(min_periods=20).quantile(1/3).shift(1)
    q2_3_trailing = ib_agg['range_pct'].expanding(min_periods=20).quantile(2/3).shift(1)
    first_q1 = q1_3_trailing.dropna().iloc[0] if not q1_3_trailing.dropna().empty else q1_3
    first_q2 = q2_3_trailing.dropna().iloc[0] if not q2_3_trailing.dropna().empty else q2_3
    q1_3_trailing = q1_3_trailing.fillna(first_q1)
    q2_3_trailing = q2_3_trailing.fillna(first_q2)
    ib_agg['range_bucket_trailing'] = np.select(
        [ib_agg['range_pct'] <= q1_3_trailing, ib_agg['range_pct'] <= q2_3_trailing],
        ['Small', 'Medium'],
        default='Large'
    )
    
    # 3. Extremes
    high_first_idx = ib_bars.groupby('logical_date')['high'].idxmax().reindex(ib_agg.index)
    low_first_idx = ib_bars.groupby('logical_date')['low'].idxmin().reindex(ib_agg.index)
    ib_agg['high_first_idx'] = high_first_idx
    ib_agg['low_first_idx'] = low_first_idx
    
    ib_bars_rev = ib_bars.iloc[::-1]
    high_last_idx = ib_bars_rev.groupby('logical_date')['high'].idxmax().reindex(ib_agg.index)
    low_last_idx = ib_bars_rev.groupby('logical_date')['low'].idxmin().reindex(ib_agg.index)
    ib_agg['high_last_idx'] = high_last_idx
    ib_agg['low_last_idx'] = low_last_idx
    
    tie_breaker = np.where(
        ib_agg['ib_close'] > ib_agg['ib_open'],
        1,
        np.where(ib_agg['ib_close'] < ib_agg['ib_open'], -1, 0)
    )
    
    ib_agg['bias_formation_firstreach'] = np.where(
        ib_agg['low_first_idx'] < ib_agg['high_first_idx'], 1,
        np.where(ib_agg['high_first_idx'] < ib_agg['low_first_idx'], -1, tie_breaker)
    )
    
    ib_agg['bias_formation_lasttouch'] = np.where(
        ib_agg['low_last_idx'] < ib_agg['high_last_idx'], 1,
        np.where(ib_agg['high_last_idx'] < ib_agg['low_last_idx'], -1, tie_breaker)
    )
    
    ib_agg['bias_close_dir'] = np.where(
        ib_agg['ib_close'] > ib_agg['ib_open'], 1,
        np.where(ib_agg['ib_close'] < ib_agg['ib_open'], -1, 0)
    )
    
    # Broadcast to 1m — build integer positional map once to replace all .reindex(logical_date) calls.
    # Keep a has-IB mask so orphan dates cannot leak into ungated computations.
    logical_date = df['logical_date']
    # date_pos_1m[i] = position of logical_date[i] in ib_agg.index (O(n) numpy lookup)
    _ib_agg_date_to_pos = {d: i for i, d in enumerate(ib_agg.index)}
    date_pos_1m = np.array([_ib_agg_date_to_pos.get(d, 0) for d in logical_date], dtype=np.intp)
    has_ib_1m = logical_date.isin(ib_agg.index).to_numpy()
    df = df.join(ib_agg[['ib_high', 'ib_low', 'ib_mid', 'ib_range']], on='logical_date')
    
    # 4. FVG Calculations
    if fvg_df_precalc is not None:
        fvg_df = fvg_df_precalc.copy()
        if 'logical_date' not in fvg_df.columns:
            fvg_df['logical_date'] = get_logical_trading_date(fvg_df.index)

        # Backward compatibility: legacy precomputed FVG parquet may not include
        # pattern-extreme columns introduced in v6.
        required_fvg_cols = ['fvg_type', 'fvg_top', 'fvg_bottom', 'fvg_finalized_time', 'fvg_low', 'fvg_high']
        missing_fvg_cols = [c for c in required_fvg_cols if c not in fvg_df.columns]
        if missing_fvg_cols:
            detected_fvg = detect_fvgs_v5(df, '5min')
            for col in missing_fvg_cols:
                fvg_df[col] = detected_fvg[col].reindex(fvg_df.index)
    else:
        fvg_df = detect_fvgs_v5(df, '5min')
        fvg_df['logical_date'] = get_logical_trading_date(fvg_df.index)
    
    # Join dynamic session times to FVG
    daily_session_times = df.groupby('logical_date')[['ib_start_t', 'ib_end_t', 'out_end_t', 'ib_start_mins', 'ib_end_mins', 'out_end_mins']].first()
    fvg_df = fvg_df.join(daily_session_times, on='logical_date')
    
    # Eligible inside the IB window (using integer minutes)
    fvg_idx_mins = fvg_df.index.hour * 60 + fvg_df.index.minute
    fvg_fin_mins = fvg_df['fvg_finalized_time'].dt.hour * 60 + fvg_df['fvg_finalized_time'].dt.minute
    fvg_df['is_eligible_ib'] = (fvg_df['fvg_type'] != 0) & \
                               (fvg_idx_mins >= fvg_df['ib_start_mins']) & \
                               (fvg_fin_mins <= fvg_df['ib_end_mins'])
                               
    ib_fvgs = fvg_df[fvg_df['is_eligible_ib']].sort_index()
    first_ib_fvg = ib_fvgs.groupby('logical_date').first()
    
    # Join first FVG details to ib_agg
    ib_agg = ib_agg.join(
        first_ib_fvg[['fvg_type', 'fvg_top', 'fvg_bottom', 'fvg_low', 'fvg_high', 'fvg_finalized_time']].rename(
            columns={
                'fvg_type': 'bias_fvg',
                'fvg_top': 'ib_fvg_top',
                'fvg_bottom': 'ib_fvg_bottom',
                'fvg_low': 'fvg_low',
                'fvg_high': 'fvg_high',
                'fvg_finalized_time': 'ib_fvg_fin_time'
            }
        )
    )
    ib_agg['bias_fvg'] = ib_agg['bias_fvg'].fillna(0).astype(int)
    
    # RTH/1011 dual FVG for NY AM IB
    if session_choice == "NY AM IB":
        ib_agg['bias_fvg_rth'] = ib_agg['bias_fvg']
        
        # 1011 window (09:50 - 11:00) using integer minutes
        fvg_df['is_eligible_1011'] = (fvg_df['fvg_type'] != 0) & \
                                     (fvg_idx_mins >= 9 * 60 + 50) & \
                                     (fvg_fin_mins <= 11 * 60)
        ib_fvgs_1011 = fvg_df[fvg_df['is_eligible_1011']].sort_index()
        first_1011_fvg = ib_fvgs_1011.groupby('logical_date').first()
        
        ib_agg = ib_agg.join(
            first_1011_fvg[['fvg_type', 'fvg_top', 'fvg_bottom', 'fvg_low', 'fvg_high', 'fvg_finalized_time']].rename(
                columns={
                    'fvg_type': 'bias_fvg_1011',
                    'fvg_top': 'fvg_1011_top',
                    'fvg_bottom': 'fvg_1011_bottom',
                    'fvg_low': 'fvg_1011_low',
                    'fvg_high': 'fvg_1011_high',
                    'fvg_finalized_time': 'fvg_1011_fin_time'
                }
            )
        )
        ib_agg['bias_fvg_1011'] = ib_agg['bias_fvg_1011'].fillna(0).astype(int)
    else:
        ib_agg['bias_fvg_rth'] = 0
        ib_agg['bias_fvg_1011'] = 0
        ib_agg['fvg_1011_fin_time'] = pd.NaT
        ib_agg['fvg_1011_low'] = np.nan
        ib_agg['fvg_1011_high'] = np.nan
        
    # Check if first FVG is broken
    df = df.join(
        ib_agg[['bias_fvg', 'ib_fvg_top', 'ib_fvg_bottom', 'fvg_low', 'fvg_high', 'ib_fvg_fin_time']],
        on='logical_date'
    )
    
    is_after_fvg = df.index >= df['ib_fvg_fin_time'].values
    is_in_out = df['in_out'].values
    
    df['fvg_broken_bar'] = np.where(
        is_after_fvg & is_in_out & (df['bias_fvg'] == 1),
        df['close'] < df['fvg_low'],
        np.where(
            is_after_fvg & is_in_out & (df['bias_fvg'] == -1),
            df['close'] > df['fvg_high'],
            False
        )
    )
    
    fvg_broken_days = df[df['fvg_broken_bar']].groupby('logical_date').first()
    ib_agg['fvg_broken_time'] = fvg_broken_days['timestamp'].reindex(ib_agg.index)
    ib_agg['bias_fvg_ifvg'] = np.where(
        ib_agg['fvg_broken_time'].notna(),
        -ib_agg['bias_fvg'],
        ib_agg['bias_fvg']
    )
    
    # Calculate combined bias (equal weights)
    ib_agg['bias_combined'] = np.sign(
        ib_agg['bias_formation_firstreach'] +
        ib_agg['bias_formation_lasttouch'] +
        ib_agg['bias_close_dir'] +
        ib_agg['bias_fvg'] +
        ib_agg['bias_fvg_ifvg']
    ).fillna(0).astype(int)
    
    # 5. Prior Session Close & Gap
    if session_choice == "NY AM IB":
        is_1559 = (df.index.hour == 15) & (df.index.minute == 59)
        rth_closes = df['close'].where(is_1559).groupby(logical_date).last()
        ib_agg['prior_session_close'] = rth_closes.shift(1)
    else:
        ib_agg['prior_session_close'] = ib_agg['ib_close'].shift(1)
        
    ib_agg['gap_pts'] = ib_agg['ib_open'] - ib_agg['prior_session_close']
    ib_agg['gap_pct'] = np.where(
        ib_agg['prior_session_close'] > 0,
        ib_agg['gap_pts'] / ib_agg['prior_session_close'] * 100,
        0.0
    )
    ib_agg['gap_dir'] = np.sign(ib_agg['gap_pts'])
    
    # Check gap filled (use numpy positional indexing)
    prior_close_1m = ib_agg['prior_session_close'].values[date_pos_1m]
    gap_dir_1m = ib_agg['gap_dir'].values[date_pos_1m]
    
    is_filled_bar = df['in_out'] & np.where(
        gap_dir_1m == 1, df['low'] <= prior_close_1m,
        np.where(gap_dir_1m == -1, df['high'] >= prior_close_1m, True)
    )
    
    # Optimize min_fill_idx groupby
    filled_bars = df[is_filled_bar]
    if not filled_bars.empty:
        min_fill_idx = filled_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        min_fill_idx = pd.Series(len(df), index=ib_agg.index)
        
    ib_agg['gap_filled'] = min_fill_idx < len(df)
    
    ib_end_idx = df[in_ib].groupby('logical_date')['bar_idx'].max().reindex(ib_agg.index)
    ib_agg['gap_fill_minutes'] = np.where(
        ib_agg['gap_filled'],
        min_fill_idx - ib_end_idx,
        np.nan
    )
    
    # 6. Breakouts
    break_high_bar = df['in_out'] & (df['close'] > df['ib_high'])
    break_low_bar = df['in_out'] & (df['close'] < df['ib_low'])
    
    # Optimize high_break_idx groupby
    break_high_bars = df[break_high_bar]
    if not break_high_bars.empty:
        high_break_idx = break_high_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        high_break_idx = pd.Series(len(df), index=ib_agg.index)
        
    # Optimize low_break_idx groupby
    break_low_bars = df[break_low_bar]
    if not break_low_bars.empty:
        low_break_idx = break_low_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        low_break_idx = pd.Series(len(df), index=ib_agg.index)
        
    ib_agg['high_break_idx'] = high_break_idx
    ib_agg['low_break_idx'] = low_break_idx
    
    ib_agg['first_break_dir'] = np.select(
        [high_break_idx < low_break_idx, low_break_idx < high_break_idx],
        [1, -1],
        default=0
    )
    ib_agg['first_break_idx'] = np.minimum(high_break_idx, low_break_idx)
    ib_agg['first_break_minutes'] = np.where(
        ib_agg['first_break_dir'] != 0,
        ib_agg['first_break_idx'] - ib_end_idx,
        np.nan
    )
    ib_agg['double_break'] = (high_break_idx < len(df)) & (low_break_idx < len(df))
    ib_agg['double_break_order'] = np.select(
        [ib_agg['double_break'] & (high_break_idx < low_break_idx), ib_agg['double_break'] & (low_break_idx < high_break_idx)],
        ["HL", "LH"],
        default=None
    )
    
    # Mid retest & retrace calculations
    first_break_dir_1m = ib_agg['first_break_dir'].values[date_pos_1m]
    first_break_idx_1m = ib_agg['first_break_idx'].values[date_pos_1m]
    mid_1m = ib_agg['ib_mid'].values[date_pos_1m]
    
    is_mid_retest_bar = df['in_out'] & (df['bar_idx'] > first_break_idx_1m) & np.where(
        first_break_dir_1m == 1, df['low'] <= mid_1m,
        np.where(first_break_dir_1m == -1, df['high'] >= mid_1m, False)
    )
    
    mid_retest_bars = df[is_mid_retest_bar]
    if not mid_retest_bars.empty:
        min_retest_idx = mid_retest_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        min_retest_idx = pd.Series(len(df), index=ib_agg.index)
        
    ib_agg['mid_retest'] = min_retest_idx < len(df)
    ib_agg['mid_retest_minutes'] = np.where(ib_agg['mid_retest'], min_retest_idx - ib_agg['first_break_idx'], np.nan)
    
    # Retrace depth pct & behavior
    post_break_bar = df['in_out'] & (df['bar_idx'] >= first_break_idx_1m) & (first_break_dir_1m != 0)
    post_break_bars = df[post_break_bar]
    if not post_break_bars.empty:
        post_break_agg = post_break_bars.groupby('logical_date').agg(
            pb_high=('high', 'max'),
            pb_low=('low', 'min')
        ).reindex(ib_agg.index)
    else:
        post_break_agg = pd.DataFrame(index=ib_agg.index)
        post_break_agg['pb_high'] = np.nan
        post_break_agg['pb_low'] = np.nan
        
    pb_high = post_break_agg['pb_high']
    pb_low = post_break_agg['pb_low']
    
    ib_agg['retrace_depth_pct'] = np.where(
        (ib_agg['first_break_dir'] != 0) & (ib_agg['ib_range'] > 0),
        (pb_high - pb_low) / ib_agg['ib_range'] * 100,
        0.0
    )
    ib_agg['behavior'] = np.where(
        ib_agg['first_break_dir'] == 0,
        "none",
        np.where(ib_agg['retrace_depth_pct'] >= 50.0, "fade", "trend")
    )
    
    # Optimize close_below_low_idx groupby
    close_below_low_bar = df['in_out'] & (df['close'] < df['ib_low'])
    close_below_low_bars = df[close_below_low_bar]
    if not close_below_low_bars.empty:
        close_below_low_idx = close_below_low_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        close_below_low_idx = pd.Series(len(df), index=ib_agg.index)
        
    # Optimize close_above_high_idx groupby
    close_above_high_bar = df['in_out'] & (df['close'] > df['ib_high'])
    close_above_high_bars = df[close_above_high_bar]
    if not close_above_high_bars.empty:
        close_above_high_idx = close_above_high_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        close_above_high_idx = pd.Series(len(df), index=ib_agg.index)
        
    # Optimize target_reached_high_idx groupby
    target_reached_high_bar = df['in_out'] & (df['high'] >= df['ib_high'] + false_break_min_ext * df['ib_range'])
    target_reached_high_bars = df[target_reached_high_bar]
    if not target_reached_high_bars.empty:
        target_reached_high_idx = target_reached_high_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        target_reached_high_idx = pd.Series(len(df), index=ib_agg.index)
        
    # Optimize target_reached_low_idx groupby
    target_reached_low_bar = df['in_out'] & (df['low'] <= df['ib_low'] - false_break_min_ext * df['ib_range'])
    target_reached_low_bars = df[target_reached_low_bar]
    if not target_reached_low_bars.empty:
        target_reached_low_idx = target_reached_low_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        target_reached_low_idx = pd.Series(len(df), index=ib_agg.index)
        
    ib_agg['false_break_high'] = (high_break_idx < len(df)) & (
        ((close_below_low_idx > high_break_idx) & (close_below_low_idx < len(df))) |
        (target_reached_high_idx == len(df))
    )
    ib_agg['false_break_low'] = (low_break_idx < len(df)) & (
        ((close_above_high_idx > low_break_idx) & (close_above_high_idx < len(df))) |
        (target_reached_low_idx == len(df))
    )
    
    # Max extensions reached
    out_bars = df[in_out]
    out_agg = out_bars.groupby('logical_date').agg(
        max_high=('high', 'max'),
        min_low=('low', 'min')
    )
    if not out_bars.empty:
        out_close_idx = out_bars.groupby('logical_date')['datetime'].idxmax()
        out_close = out_bars.loc[out_close_idx, ['logical_date', 'close']].set_index('logical_date')['close']
        out_agg = out_agg.join(out_close.rename('outcome_close'))
    ib_agg = ib_agg.join(out_agg)
    ib_agg['max_ext_up'] = np.where(
        (ib_agg['max_high'] > ib_agg['ib_high']) & (ib_agg['ib_range'] > 0),
        (ib_agg['max_high'] - ib_agg['ib_high']) / ib_agg['ib_range'],
        0.0
    )
    ib_agg['max_ext_down'] = np.where(
        (ib_agg['min_low'] < ib_agg['ib_low']) & (ib_agg['ib_range'] > 0),
        (ib_agg['ib_low'] - ib_agg['min_low']) / ib_agg['ib_range'],
        0.0
    )
    ib_agg['realized_dir_break'] = ib_agg['first_break_dir'].fillna(0).astype(int)
    ib_agg['realized_dir_close'] = np.where(
        ib_agg['outcome_close'] > ib_agg['ib_close'],
        1,
        np.where(ib_agg['outcome_close'] < ib_agg['ib_close'], -1, 0)
    ).astype(int)
    ib_agg['realized_dir_ext'] = np.where(
        ib_agg['max_ext_up'] > ib_agg['max_ext_down'],
        1,
        np.where(ib_agg['max_ext_up'] < ib_agg['max_ext_down'], -1, 0)
    ).astype(int)
    
    # 7. Level extension hits (consolidated single groupby on 18 columns)
    levels = [0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    df_levels = pd.DataFrame(index=df.index)
    df_levels['logical_date'] = df['logical_date']
    
    for lvl in levels:
        col_lvl = str(lvl).replace('.', '')
        up_tgt_1m = (ib_agg['ib_high'].values + lvl * ib_agg['ib_range'].values)[date_pos_1m]
        dn_tgt_1m = (ib_agg['ib_low'].values - lvl * ib_agg['ib_range'].values)[date_pos_1m]
        
        df_levels[f'up_{col_lvl}'] = np.where(df['in_out'] & (df['high'] >= up_tgt_1m), df['bar_idx'], len(df))
        df_levels[f'dn_{col_lvl}'] = np.where(df['in_out'] & (df['low'] <= dn_tgt_1m), df['bar_idx'], len(df))
        
    levels_min = df_levels.groupby('logical_date').min()
    
    for lvl in levels:
        col_lvl = str(lvl).replace('.', '')
        hit_up_idx = levels_min[f'up_{col_lvl}'].reindex(ib_agg.index, fill_value=len(df))
        hit_dn_idx = levels_min[f'dn_{col_lvl}'].reindex(ib_agg.index, fill_value=len(df))
        
        ib_agg[f'ext_up_{col_lvl}_hit'] = hit_up_idx < len(df)
        ib_agg[f'ext_up_{col_lvl}_minutes'] = np.where(ib_agg[f'ext_up_{col_lvl}_hit'], hit_up_idx - ib_end_idx, np.nan)
        
        ib_agg[f'ext_down_{col_lvl}_hit'] = hit_dn_idx < len(df)
        ib_agg[f'ext_down_{col_lvl}_minutes'] = np.where(ib_agg[f'ext_down_{col_lvl}_hit'], hit_dn_idx - ib_end_idx, np.nan)
        
        ib_agg[f'either_side_{col_lvl}_hit'] = ib_agg[f'ext_up_{col_lvl}_hit'] | ib_agg[f'ext_down_{col_lvl}_hit']
        
    # 8. VIX Close alignment
    if vix_series is not None:
        vix_daily = vix_series.groupby(vix_series.index.date).last()
        prior_vix = vix_daily.shift(1)
        ib_agg['vix_close'] = pd.Series(ib_agg.index.map(prior_vix), index=ib_agg.index).ffill()
    else:
        ib_agg['vix_close'] = np.nan
        
    # VIX Buckets
    vix_q1 = ib_agg['vix_close'].dropna().quantile(1/3) if not ib_agg['vix_close'].dropna().empty else 15.0
    vix_q2 = ib_agg['vix_close'].dropna().quantile(2/3) if not ib_agg['vix_close'].dropna().empty else 20.0
    
    ib_agg['vix_bucket_full'] = np.select(
        [ib_agg['vix_close'] <= vix_q1, ib_agg['vix_close'] <= vix_q2],
        ['Low', 'Medium'],
        default='High'
    )
    
    vix_q1_trailing = ib_agg['vix_close'].expanding(min_periods=20).quantile(1/3).shift(1)
    vix_q2_trailing = ib_agg['vix_close'].expanding(min_periods=20).quantile(2/3).shift(1)
    first_vix_q1 = vix_q1_trailing.dropna().iloc[0] if not vix_q1_trailing.dropna().empty else vix_q1
    first_vix_q2 = vix_q2_trailing.dropna().iloc[0] if not vix_q2_trailing.dropna().empty else vix_q2
    vix_q1_trailing = vix_q1_trailing.fillna(first_vix_q1)
    vix_q2_trailing = vix_q2_trailing.fillna(first_vix_q2)
    ib_agg['vix_bucket_trailing'] = np.select(
        [ib_agg['vix_close'] <= vix_q1_trailing, ib_agg['vix_close'] <= vix_q2_trailing],
        ['Low', 'Medium'],
        default='High'
    )
    
    # 9. Mid lock and front-running tracking
    ib_agg['mid_lock_time'] = np.maximum(high_first_idx, low_first_idx)
    ib_agg['mid_end_ts'] = df[in_ib].groupby('logical_date')['datetime'].max().reindex(ib_agg.index)
    ib_agg['mid_start_ts'] = df[in_ib].groupby('logical_date')['datetime'].min().reindex(ib_agg.index)
    ib_agg['ib_duration_mins'] = (ib_agg['mid_end_ts'] - ib_agg['mid_start_ts']).dt.total_seconds() / 60.0
    ib_agg['mid_lock_frac'] = (ib_agg['mid_lock_time'] - ib_agg['mid_start_ts']).dt.total_seconds() / 60.0 / ib_agg['ib_duration_mins']
    
    # Front-Running logic: first touch inside the IB window before it closes when provisional_mid == final_mid
    ib_bars = df[in_ib].copy()
    ib_bars['run_high'] = ib_bars.groupby('logical_date')['high'].cummax()
    ib_bars['run_low'] = ib_bars.groupby('logical_date')['low'].cummin()
    ib_bars['run_mid'] = (ib_bars['run_high'] + ib_bars['run_low']) / 2.0
    
    mid_matches = np.isclose(ib_bars['run_mid'], ib_bars['ib_mid'], rtol=0.0, atol=1e-9)
    mid_touched = (ib_bars['low'] <= ib_bars['run_mid']) & (ib_bars['high'] >= ib_bars['run_mid'])
    
    ib_end_idx_series = ib_bars.groupby('logical_date')['bar_idx'].max()
    ib_bars['ib_end_idx'] = ib_end_idx_series.reindex(ib_bars['logical_date']).values
    is_before_close = ib_bars['bar_idx'] < ib_bars['ib_end_idx']
    
    ib_bars['front_run_active_bar'] = mid_matches & mid_touched & is_before_close
    
    front_run_bars = ib_bars[ib_bars['front_run_active_bar']]
    if not front_run_bars.empty:
        first_front_run = front_run_bars.groupby('logical_date').first()
        ib_agg['front_run_active'] = True
        ib_agg['front_run_time'] = first_front_run['datetime']
        ib_start_ts = ib_bars.groupby('logical_date')['datetime'].min()
        ib_agg['front_run_activation_mins'] = (first_front_run['datetime'] - ib_start_ts.reindex(first_front_run.index)).dt.total_seconds() / 60.0
    else:
        ib_agg['front_run_active'] = False
        ib_agg['front_run_time'] = pd.NaT
        ib_agg['front_run_activation_mins'] = np.nan
        
    ib_agg['front_run_active'] = ib_agg['front_run_active'].fillna(False)
    ib_agg['front_run_time'] = ib_agg['front_run_time'].fillna(pd.NaT)
    ib_agg['front_run_activation_mins'] = ib_agg['front_run_activation_mins'].fillna(np.nan)

    # Level touch and mid touch calculations
    level_touch_df = extract_level_touch_details(df, ib_agg)
    
    # Promote 50% touches to ib_agg (numpy positional indexing)
    low_1m = ib_agg['ib_low'].values[date_pos_1m]
    range_1m = ib_agg['ib_range'].values[date_pos_1m]
    mid_lock_1m = ib_agg['mid_lock_time'].values[date_pos_1m]
    
    mid_lvl_price = low_1m + 0.5 * range_1m
    in_scope_bar = (df['in_ib'] | df['in_out']).to_numpy()
    mid_touch_bar = has_ib_1m & in_scope_bar & (df['low'] <= mid_lvl_price) & (df['high'] >= mid_lvl_price)
    mid_touch_bars = df[mid_touch_bar].copy()
    
    is_pre_lock = df['in_ib'] & (df.index < mid_lock_1m)
    is_post_lock = df['in_ib'] & (df.index >= mid_lock_1m)
    is_outcome = df['in_out']
    
    phase_arr = np.select(
        [is_pre_lock, is_post_lock, is_outcome],
        ['formation_pre_lock', 'formation_post_lock', 'outcome'],
        default='outside'
    )
    mid_touch_bars['phase'] = phase_arr[mid_touch_bar]
    
    mid_touch_valid = mid_touch_bars[mid_touch_bars['phase'] != 'outside']
    is_form_touch = mid_touch_bars['phase'].isin(['formation_pre_lock', 'formation_post_lock'])

    ib_agg['mid_touch_first_time'] = mid_touch_valid.groupby('logical_date')['datetime'].first().reindex(ib_agg.index)
    ib_agg['mid_touch_first_phase'] = mid_touch_valid.groupby('logical_date')['phase'].first().reindex(ib_agg.index)
    ib_agg['mid_touch_first_formation_time'] = mid_touch_bars[is_form_touch].groupby('logical_date')['datetime'].first().reindex(ib_agg.index)
    ib_agg['mid_touch_first_outcome_time'] = mid_touch_bars[mid_touch_bars['phase'] == 'outcome'].groupby('logical_date')['datetime'].first().reindex(ib_agg.index)

    ib_agg['mid_touch_last_formation_time'] = mid_touch_bars[is_form_touch].groupby('logical_date')['datetime'].last().reindex(ib_agg.index)
    
    ib_agg['mid_touch_count_formation'] = mid_touch_bars[is_form_touch].groupby('logical_date').size().reindex(ib_agg.index)
    ib_agg['mid_touch_count_outcome'] = mid_touch_bars[mid_touch_bars['phase'] == 'outcome'].groupby('logical_date').size().reindex(ib_agg.index)
    ib_agg['mid_touch_count_formation'] = ib_agg['mid_touch_count_formation'].fillna(0).astype(int)
    ib_agg['mid_touch_count_outcome'] = ib_agg['mid_touch_count_outcome'].fillna(0).astype(int)
    
    ib_agg['mid_touched_again'] = mid_touch_valid.groupby('logical_date').size().reindex(ib_agg.index) > 1
    ib_agg['mid_touched_again'] = ib_agg['mid_touched_again'].fillna(False)
    
    ib_agg['mid_touch_count_post_lock'] = mid_touch_bars[mid_touch_bars['phase'] == 'formation_post_lock'].groupby('logical_date').size().reindex(ib_agg.index)
    ib_agg['mid_touch_count_post_lock'] = ib_agg['mid_touch_count_post_lock'].fillna(0).astype(int)
    
    ib_agg['early_mid_event'] = (ib_agg['mid_lock_frac'] <= 2.0/3.0) & (ib_agg['mid_touch_count_post_lock'] > 0)

    # FVG touch timing split by formation/outcome (analogous to split mid-touch timing).
    fvg_top_1m = ib_agg['ib_fvg_top'].values[date_pos_1m]
    fvg_bottom_1m = ib_agg['ib_fvg_bottom'].values[date_pos_1m]
    fvg_low_1m = ib_agg['fvg_low'].values[date_pos_1m]
    fvg_high_1m = ib_agg['fvg_high'].values[date_pos_1m]
    fvg_fin_1m = ib_agg['ib_fvg_fin_time'].values[date_pos_1m]
    bias_fvg_1m = ib_agg['bias_fvg'].values[date_pos_1m]
    fvg_fin_valid = pd.notna(fvg_fin_1m)

    fvg_touch_bar = has_ib_1m & fvg_fin_valid & (bias_fvg_1m != 0) & (df.index.values >= fvg_fin_1m) & np.where(
        bias_fvg_1m == 1,
        (df['low'].values <= fvg_top_1m) & (df['close'].values >= fvg_low_1m),
        np.where(
            bias_fvg_1m == -1,
            (df['high'].values >= fvg_bottom_1m) & (df['close'].values <= fvg_high_1m),
            False
        )
    )
    fvg_touch_formation = df[fvg_touch_bar & df['in_ib'].values]
    fvg_touch_outcome = df[fvg_touch_bar & df['in_out'].values]
    ib_agg['fvg_touch_first_formation_time'] = fvg_touch_formation.groupby('logical_date')['datetime'].first().reindex(ib_agg.index)
    ib_agg['fvg_touch_first_outcome_time'] = fvg_touch_outcome.groupby('logical_date')['datetime'].first().reindex(ib_agg.index)

    if session_choice == "NY AM IB":
        fvg1011_top_1m = ib_agg['fvg_1011_top'].values[date_pos_1m]
        fvg1011_bottom_1m = ib_agg['fvg_1011_bottom'].values[date_pos_1m]
        fvg1011_low_1m = ib_agg['fvg_1011_low'].values[date_pos_1m]
        fvg1011_high_1m = ib_agg['fvg_1011_high'].values[date_pos_1m]
        fvg1011_fin_1m = ib_agg['fvg_1011_fin_time'].values[date_pos_1m]
        bias_fvg1011_1m = ib_agg['bias_fvg_1011'].values[date_pos_1m]
        fvg1011_fin_valid = pd.notna(fvg1011_fin_1m)

        fvg1011_touch_bar = has_ib_1m & fvg1011_fin_valid & (bias_fvg1011_1m != 0) & (df.index.values >= fvg1011_fin_1m) & np.where(
            bias_fvg1011_1m == 1,
            (df['low'].values <= fvg1011_top_1m) & (df['close'].values >= fvg1011_low_1m),
            np.where(
                bias_fvg1011_1m == -1,
                (df['high'].values >= fvg1011_bottom_1m) & (df['close'].values <= fvg1011_high_1m),
                False
            )
        )
        fvg1011_touch_formation = df[fvg1011_touch_bar & df['in_ib'].values]
        fvg1011_touch_outcome = df[fvg1011_touch_bar & df['in_out'].values]
        ib_agg['fvg_1011_touch_first_formation_time'] = fvg1011_touch_formation.groupby('logical_date')['datetime'].first().reindex(ib_agg.index)
        ib_agg['fvg_1011_touch_first_outcome_time'] = fvg1011_touch_outcome.groupby('logical_date')['datetime'].first().reindex(ib_agg.index)
    else:
        ib_agg['fvg_1011_touch_first_formation_time'] = pd.NaT
        ib_agg['fvg_1011_touch_first_outcome_time'] = pd.NaT
    
    # 10. Bias Outcomes Grading (0.5x and 1.0x targets) (consolidated race evaluation)
    variants = ['formation_firstreach', 'formation_lasttouch', 'close_dir', 'fvg', 'fvg_ifvg', 'combined']
    if session_choice == "NY AM IB":
        variants += ['fvg_rth', 'fvg_1011']
        
    ib_end_time = ib_agg['mid_end_ts']
    races = {}
    
    for v in variants:
        bias_val = ib_agg[f'bias_{v}'] if f'bias_{v}' in ib_agg.columns else ib_agg[v]
        
        # Determine finalized time
        if v == 'fvg' or v == 'fvg_rth':
            fin_time = ib_agg['ib_fvg_fin_time']
        elif v == 'fvg_1011':
            fin_time = ib_agg['fvg_1011_fin_time']
        else:
            fin_time = ib_end_time
        fin_time = pd.Series(fin_time, index=ib_agg.index)
        fin_time = fin_time.combine_first(ib_end_time)
        
        for lvl in [0.0, 0.25, 0.5, 0.75, 1.0]:
            lvl_col = str(lvl).replace('.', '')
            
            tgt_up = ib_agg['ib_high'] + lvl * ib_agg['ib_range']
            tgt_dn = ib_agg['ib_low'] - lvl * ib_agg['ib_range']
            
            if v == 'fvg_ifvg':
                # Special IFVG logic:
                # 1. Evaluate original race
                orig_name = f'fvg_ifvg_orig_{lvl_col}'
                orig_bias = ib_agg['bias_fvg']
                orig_tgt = np.where(orig_bias == 1, tgt_up, tgt_dn)
                orig_stop = np.where(orig_bias == 1, ib_agg['ib_low'], ib_agg['ib_high'])
                orig_start = ib_agg['ib_fvg_fin_time'].fillna(ib_end_time)
                races[orig_name] = (orig_bias, pd.Series(orig_tgt, index=ib_agg.index), pd.Series(orig_stop, index=ib_agg.index), orig_start)
                
                # 2. Evaluate flipped race
                flipped_name = f'fvg_ifvg_flipped_{lvl_col}'
                flipped_bias = -ib_agg['bias_fvg']
                flipped_tgt = np.where(flipped_bias == 1, tgt_up, tgt_dn)
                flipped_stop = np.where(flipped_bias == 1, ib_agg['ib_low'], ib_agg['ib_high'])
                flipped_start = ib_agg['fvg_broken_time'].fillna(ib_end_time)
                races[flipped_name] = (flipped_bias, pd.Series(flipped_tgt, index=ib_agg.index), pd.Series(flipped_stop, index=ib_agg.index), flipped_start)
            else:
                name = f'{v}_{lvl_col}'
                tgt_price = np.where(bias_val == 1, tgt_up, tgt_dn)
                stop_price = np.where(bias_val == 1, ib_agg['ib_low'], ib_agg['ib_high'])
                races[name] = (bias_val, pd.Series(tgt_price, index=ib_agg.index), pd.Series(stop_price, index=ib_agg.index), fin_time)
                
    # Run all races consolidated (pass date_pos_1m for O(n) numpy broadcasting)
    race_results = evaluate_target_vs_stop_consolidated(df, races, ib_agg, date_pos_1m)
    
    # Assign bias correctness columns in one batch to avoid DataFrame fragmentation.
    bias_correct_cols = {}
    for v in variants:
        for lvl in [0.0, 0.25, 0.5, 0.75, 1.0]:
            lvl_col = str(lvl).replace('.', '')
            
            if v == 'fvg_ifvg':
                orig_correct = race_results[f'fvg_ifvg_orig_{lvl_col}']
                flipped_correct = race_results[f'fvg_ifvg_flipped_{lvl_col}']
                correct = np.where(
                    orig_correct, True,
                    np.where(ib_agg['fvg_broken_time'].notna(), flipped_correct, False)
                )
            else:
                correct = race_results[f'{v}_{lvl_col}']

            bias_correct_cols[f'bias_correct_{v}_{lvl_col}x'] = pd.Series(correct, index=ib_agg.index)

    if bias_correct_cols:
        ib_agg = pd.concat([ib_agg, pd.DataFrame(bias_correct_cols, index=ib_agg.index)], axis=1)

    # Keep block layout compact before subsequent column additions.
    ib_agg = ib_agg.copy()
            
    # 11. Plays Evaluation
    play_levels = [0.25, 0.5, 0.75, 1.0]
    
    mid_1m = ib_agg['ib_mid'].values[date_pos_1m]
    high_1m = ib_agg['ib_high'].values[date_pos_1m]
    low_1m = ib_agg['ib_low'].values[date_pos_1m]
    range_1m = ib_agg['ib_range'].values[date_pos_1m]
    first_break_dir_1m = ib_agg['first_break_dir'].values[date_pos_1m]
    first_break_idx_1m = ib_agg['first_break_idx'].values[date_pos_1m]

    first_break_dir = ib_agg['first_break_dir']
    first_break_idx = ib_agg['first_break_idx']
    ib_high = ib_agg['ib_high']
    ib_low = ib_agg['ib_low']
    ib_mid = ib_agg['ib_mid']
    ib_range = ib_agg['ib_range']
    bias_combined = ib_agg['bias_combined']

    # Calculate Play 2 entry index (mid touch after breakout)
    p2_touch = df['in_out'] & (df['bar_idx'] > first_break_idx_1m) & (df['low'] <= mid_1m) & (df['high'] >= mid_1m)
    df_p2 = pd.DataFrame(index=df.index)
    df_p2['logical_date'] = logical_date
    df_p2['p2_entry'] = np.where(p2_touch, df['bar_idx'], len(df))
    p2_entry_idx = df_p2.groupby('logical_date')['p2_entry'].min().reindex(ib_agg.index, fill_value=len(df))
    
    # Calculate opposite boundary violation for Play 2 invalidation
    opp_close_stop = np.where(first_break_dir == 1, ib_low, ib_high)
    opp_close_stop_1m = opp_close_stop[date_pos_1m]
    opp_close_violation = df['in_out'] & (df['bar_idx'] > first_break_idx_1m) & np.where(
        first_break_dir_1m == 1, df['low'] <= opp_close_stop_1m,
        np.where(first_break_dir_1m == -1, df['high'] >= opp_close_stop_1m, False)
    )
    df_violation = pd.DataFrame(index=df.index)
    df_violation['logical_date'] = logical_date
    df_violation['viol_idx'] = np.where(opp_close_violation, df['bar_idx'], len(df))
    first_viol_idx = df_violation.groupby('logical_date')['viol_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    
    # Compile the 12 play configurations
    plays_config = []
    config_meta = []  # List of tuples (play_n, target_lvl)
    
    for lvl in play_levels:
        # Play 1
        p1_active = first_break_dir != 0
        p1_dir = first_break_dir
        p1_entry_price = np.where(first_break_dir == 1, ib_high, ib_low)
        p1_target_price = p1_entry_price + p1_dir * lvl * ib_range
        p1_stop_price = np.where(p1_dir == 1, ib_low, ib_high)
        
        plays_config.append({
            'active': pd.Series(p1_active, index=ib_agg.index),
            'direction': pd.Series(p1_dir, index=ib_agg.index),
            'entry_price': pd.Series(p1_entry_price, index=ib_agg.index),
            'target_price': pd.Series(p1_target_price, index=ib_agg.index),
            'stop_price': pd.Series(p1_stop_price, index=ib_agg.index),
            'entry_idx': first_break_idx
        })
        config_meta.append((1, lvl))
        
        # Play 2
        # If entry and invalidation occur on the same bar, classify as triggered and loss later.
        p2_active = (first_break_dir != 0) & (p2_entry_idx < len(df)) & (p2_entry_idx <= first_viol_idx)
        p2_dir = first_break_dir
        p2_entry_price = ib_mid
        p2_target_price = np.where(p2_dir == 1, ib_high + lvl * ib_range, ib_low - lvl * ib_range)
        p2_stop_price = np.where(p2_dir == 1, ib_low, ib_high)
        
        plays_config.append({
            'active': pd.Series(p2_active, index=ib_agg.index),
            'direction': pd.Series(p2_dir, index=ib_agg.index),
            'entry_price': pd.Series(p2_entry_price, index=ib_agg.index),
            'target_price': pd.Series(p2_target_price, index=ib_agg.index),
            'stop_price': pd.Series(p2_stop_price, index=ib_agg.index),
            'entry_idx': p2_entry_idx
        })
        config_meta.append((2, lvl))
        
        # Play 3
        # Overshoot is lvl / 2, stop is lvl (relative to boundary).
        overshoot_lvl_1m = np.where(first_break_dir_1m == 1, high_1m + (lvl / 2.0) * range_1m, low_1m - (lvl / 2.0) * range_1m)
        overshoot_cond = df['in_out'] & (df['bar_idx'] > first_break_idx_1m) & np.where(
            first_break_dir_1m == 1, df['high'] >= overshoot_lvl_1m,
            np.where(first_break_dir_1m == -1, df['low'] <= overshoot_lvl_1m, False)
        )
        df_os = pd.DataFrame(index=df.index)
        df_os['logical_date'] = logical_date
        df_os['overshoot_idx'] = np.where(overshoot_cond, df['bar_idx'], len(df))
        p3_overshoot_idx = df_os.groupby('logical_date')['overshoot_idx'].min().reindex(ib_agg.index, fill_value=len(df))
        p3_overshoot_idx_1m = p3_overshoot_idx.values[date_pos_1m]
        
        # Touch-back fill condition: close-confirmed boundary re-entry after overshoot
        boundary_1m = np.where(first_break_dir_1m == 1, high_1m, low_1m)
        fill_cond = df['in_out'] & (df['bar_idx'] > p3_overshoot_idx_1m) & np.where(
            first_break_dir_1m == 1, df['close'] <= boundary_1m,
            np.where(first_break_dir_1m == -1, df['close'] >= boundary_1m, False)
        )
        df_fl = pd.DataFrame(index=df.index)
        df_fl['logical_date'] = logical_date
        df_fl['fill_idx'] = np.where(fill_cond, df['bar_idx'], len(df))
        p3_fill_idx = df_fl.groupby('logical_date')['fill_idx'].min().reindex(ib_agg.index, fill_value=len(df))
        
        # Invalidation condition: touch or exceed stop level after overshoot but before fill
        stop_lvl_1m = np.where(first_break_dir_1m == 1, high_1m + lvl * range_1m, low_1m - lvl * range_1m)
        stop_exceed_cond = df['in_out'] & (df['bar_idx'] > p3_overshoot_idx_1m) & np.where(
            first_break_dir_1m == 1, df['high'] >= stop_lvl_1m,
            np.where(first_break_dir_1m == -1, df['low'] <= stop_lvl_1m, False)
        )
        df_se = pd.DataFrame(index=df.index)
        df_se['logical_date'] = logical_date
        df_se['stop_exceed_idx'] = np.where(stop_exceed_cond, df['bar_idx'], len(df))
        p3_stop_exceed_idx = df_se.groupby('logical_date')['stop_exceed_idx'].min().reindex(ib_agg.index, fill_value=len(df))
        
        # NT8 parity fix: IBFadeBot enters via EnterLong()/EnterShort() (market
        # order) on the bar AFTER the close-back-inside signal. The fill happens
        # at the next bar's open, NOT at the IB boundary price. This removes the
        # Class B price-inflation artifact (Python was entering at boundary, NT8
        # enters at next-bar-open which is already inside the range).
        # p3_fill_idx = signal bar (close crosses back inside boundary)
        # p3_fill_next_idx = entry bar (next bar after signal; NT8 market-order fill)
        p3_fill_next_idx = np.where(p3_fill_idx < len(df), p3_fill_idx + 1, len(df))
        p3_fill_next_idx_safe = np.minimum(p3_fill_next_idx, len(df) - 1)
        # Must have a next bar available to enter; if fill is on the last bar, no entry
        p3_has_next = (p3_fill_idx < len(df)) & (p3_fill_next_idx < len(df))
        # If fill and stop-exceed occur on the same bar, classify as triggered and loss later.
        p3_active = (first_break_dir != 0) & p3_has_next & (p3_fill_idx <= p3_stop_exceed_idx)
        p3_dir = -first_break_dir
        # Entry price = open of the bar AFTER the close-back-inside signal (NT8 market fill)
        p3_entry_price = df['open'].values[p3_fill_next_idx_safe]
        p3_target_price = ib_mid
        p3_stop_price = np.where(first_break_dir == 1, ib_high + lvl * ib_range, ib_low - lvl * ib_range)
        
        plays_config.append({
            'active': pd.Series(p3_active, index=ib_agg.index),
            'direction': pd.Series(p3_dir, index=ib_agg.index),
            'entry_price': pd.Series(p3_entry_price, index=ib_agg.index),
            'target_price': pd.Series(p3_target_price, index=ib_agg.index),
            'stop_price': pd.Series(p3_stop_price, index=ib_agg.index),
            'entry_idx': pd.Series(p3_fill_next_idx, index=ib_agg.index)
        })
        config_meta.append((3, lvl))
        
    # Run all plays consolidated
    evaluated_plays = evaluate_all_plays_consolidated(df, plays_config, ib_agg, date_pos_1m)
    
    # Build plays detail long-format DataFrame
    play_records = []
    
    default_play_cols = {}
    default_lvl_targets = {1: 1.0, 2: 0.5, 3: 0.5}
    if legacy_default_play_levels is not None:
        for play_n, lvl in legacy_default_play_levels.items():
            if play_n in default_lvl_targets:
                default_lvl_targets[play_n] = float(lvl)

    selected_default_lvl = {
        play_n: min(play_levels, key=lambda x: abs(x - target))
        for play_n, target in default_lvl_targets.items()
    }

    def _structural_rr(play_n: int, lvl: float) -> float:
        if play_n == 1:
            # Entry at boundary, stop at opposite boundary -> risk = 1.0x range.
            return float(lvl)
        if play_n == 2:
            # Entry at mid, stop at opposite boundary -> risk = 0.5x range; reward = (0.5+lvl)x.
            return float((0.5 + lvl) / 0.5)
        if play_n == 3:
            # Entry at boundary, target at mid -> reward = 0.5x; stop = lvl x.
            return float(0.5 / lvl) if lvl > 0 else np.nan
        return np.nan

    for idx, (play_n, lvl) in enumerate(config_meta):
        res, mfe, mae, realized_r, timeout_loss = evaluated_plays[idx]
        lvl_col = str(lvl).replace('.', '')
        
        play_dir = np.where(play_n == 3, -first_break_dir, first_break_dir)
        with_bias = np.where(bias_combined == 0, 0, np.where(play_dir == bias_combined, 1, -1))
        
        play_df = pd.DataFrame({
            'trading_day': ib_agg.index,
            'play': play_n,
            'target_lvl': lvl,
            'result': res.values,
            'mfe': mfe.values,
            'mae': mae.values,
            'realized_r': realized_r.values,
            'timeout_loss': timeout_loss.values,
            'with_bias': with_bias
        })
        play_df['loss_reason'] = np.select(
            [
                play_df['result'] == 0,
                (play_df['result'] == -1) & play_df['timeout_loss'],
                play_df['result'] == -1,
                play_df['result'] == 1,
            ],
            ['no_setup', 'timeout', 'stop', 'target'],
            default='unknown'
        )
        play_records.append(play_df)

        # Always expose level-specific outputs for transparent level-vs-bias analysis.
        default_play_cols[f'play{play_n}_result_{lvl_col}x'] = res
        default_play_cols[f'play{play_n}_with_bias_{lvl_col}x'] = pd.Series(with_bias, index=ib_agg.index)
        
        # Collect default play columns for backward compatibility and assign in one batch.
        if play_n == 1 and np.isclose(lvl, selected_default_lvl[1]):
            default_play_cols['play1_result'] = res
            default_play_cols['play1_rr'] = pd.Series(_structural_rr(1, lvl), index=ib_agg.index)
            default_play_cols['play1_mfe'] = mfe
            default_play_cols['play1_mae'] = mae
            default_play_cols['play1_timeout_loss'] = timeout_loss
        elif play_n == 2 and np.isclose(lvl, selected_default_lvl[2]):
            default_play_cols['play2_result'] = res
            default_play_cols['play2_rr'] = pd.Series(_structural_rr(2, lvl), index=ib_agg.index)
            default_play_cols['play2_mfe'] = mfe
            default_play_cols['play2_mae'] = mae
            default_play_cols['play2_timeout_loss'] = timeout_loss
        elif play_n == 3 and np.isclose(lvl, selected_default_lvl[3]):
            default_play_cols['play3_result'] = res
            default_play_cols['play3_rr'] = pd.Series(_structural_rr(3, lvl), index=ib_agg.index)
            default_play_cols['play3_mfe'] = mfe
            default_play_cols['play3_mae'] = mae
            default_play_cols['play3_timeout_loss'] = timeout_loss

    if default_play_cols:
        ib_agg = pd.concat([ib_agg, pd.DataFrame(default_play_cols, index=ib_agg.index)], axis=1)
            
    play_detail_df = pd.concat(play_records, ignore_index=True)
    
    # 12. Clean and build final output fact table
    facts_df = ib_agg.reset_index().rename(columns={'logical_date': 'trading_day'})
    facts_df['symbol'] = symbol
    facts_df['session_slot'] = session_choice
    facts_df['time_basis'] = time_basis
    facts_df['play1_default_target_lvl'] = selected_default_lvl[1]
    facts_df['play2_default_target_lvl'] = selected_default_lvl[2]
    facts_df['play3_default_target_lvl'] = selected_default_lvl[3]
    
    # Add calendar/DST info
    daily_dst_info = df.groupby('logical_date')[['us_dst', 'uk_dst', 'et_window_offset_hours', 'dst_regime']].first().reset_index()
    facts_df = facts_df.merge(daily_dst_info.rename(columns={'logical_date': 'trading_day'}), on='trading_day')
    
    # DOW — compute directly from date objects
    _DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    facts_df['dow'] = [_DAY_NAMES[d.weekday()] for d in facts_df['trading_day']]
    
    # Prior day same-slot result (streak calculation support)
    facts_df['prior_day_result'] = np.sign(facts_df['play1_result'].shift(1))
    
    # Event timings clock buckets
    facts_df['first_break_time_val'] = facts_df['first_break_idx'].map(lambda idx: df.index[int(idx)] if not pd.isna(idx) and idx < len(df) else pd.NaT)
    facts_df['first_break_bucket'] = facts_df['first_break_time_val'].dt.floor('5min').dt.time
    facts_df['mid_touch_bucket'] = facts_df['mid_touch_first_time'].dt.floor('5min').dt.time
    facts_df['mid_touch_first_formation_bucket'] = facts_df['mid_touch_first_formation_time'].dt.floor('5min').dt.time
    facts_df['mid_touch_first_outcome_bucket'] = facts_df['mid_touch_first_outcome_time'].dt.floor('5min').dt.time
    facts_df['fvg_touch_first_formation_bucket'] = facts_df['fvg_touch_first_formation_time'].dt.floor('5min').dt.time
    facts_df['fvg_touch_first_outcome_bucket'] = facts_df['fvg_touch_first_outcome_time'].dt.floor('5min').dt.time
    facts_df['fvg_1011_touch_first_formation_bucket'] = facts_df['fvg_1011_touch_first_formation_time'].dt.floor('5min').dt.time
    facts_df['fvg_1011_touch_first_outcome_bucket'] = facts_df['fvg_1011_touch_first_outcome_time'].dt.floor('5min').dt.time
    
    # Cleanup level_touch_df
    level_touch_df['symbol'] = symbol
    level_touch_df['session_slot'] = session_choice
    level_touch_df['time_basis'] = time_basis
    level_touch_df = level_touch_df.rename(columns={'logical_date': 'trading_day'})
    
    # Cleanup play_detail_df
    play_detail_df['symbol'] = symbol
    play_detail_df['session_slot'] = session_choice
    play_detail_df['time_basis'] = time_basis
    
    return facts_df, level_touch_df, play_detail_df
