"""
NQStats Initial Balance (IB) Library.
Aligns Python calculations with Pine Script multi-session and streak statistics.
"""

import pandas as pd
import numpy as np
import pytz
from datetime import time, datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List

from scripts.libs_py.nqstats.sessions import (
    get_logical_trading_date,
    get_dst_flags,
    get_event_anchored_times,
    get_time_mask,
    get_time_mask_vectorized,
    normalize_to_eastern
)

# Legacy session configs for backward compatibility
SESSION_CONFIGS = {
    "Globex IB":   {"ib_start": time(18, 0), "ib_end": time(19, 0), "out_end": time(2, 0)},
    "Tokyo IB":    {"ib_start": time(20, 0), "ib_end": time(21, 0), "out_end": time(2, 0)},
    "London IB":   {"ib_start": time(3, 0),  "ib_end": time(4, 0),  "out_end": time(6, 0)},
    "Midnight OR": {"ib_start": time(0, 0),  "ib_end": time(0, 30), "out_end": time(16, 0)},
    "NY AM IB":    {"ib_start": time(9, 30), "ib_end": time(10, 30), "out_end": time(16, 0)},
    "NY PM IB":    {"ib_start": time(13, 30), "ib_end": time(14, 30), "out_end": time(16, 0)}
}

# New v5 session configs
SESSION_CONFIGS_V5 = {
    "Globex IB":   {"ib_start": time(18, 0), "ib_end": time(19, 0), "out_end": time(20, 0), "time_basis": "ET_fixed"},
    "Tokyo IB":    {"ib_start": time(20, 0), "ib_end": time(21, 0), "out_end": time(2, 0), "time_basis": "event_anchored"},
    "London IB":   {"ib_start": time(3, 0),  "ib_end": time(4, 0),  "out_end": time(6, 0),  "time_basis": "event_anchored"},
    "Midnight OR": {"ib_start": time(0, 0),  "ib_end": time(0, 30), "out_end": time(16, 0), "time_basis": "ET_fixed"},
    "NY AM IB":    {"ib_start": time(9, 30), "ib_end": time(10, 30), "out_end": time(16, 0), "time_basis": "ET_fixed"},
    "NY PM IB":    {"ib_start": time(13, 30), "ib_end": time(14, 30), "out_end": time(16, 0), "time_basis": "ET_fixed"}
}


def detect_fvgs_vectorized(df: pd.DataFrame, timeframe: str = '5min') -> pd.DataFrame:
    """Detects 3-bar Fair Value Gaps on a fixed timeframe (vectorized)."""
    resampled = df[['high', 'low']].resample(timeframe, origin='start_day').agg({
        'high': 'max',
        'low': 'min'
    }).dropna()
    
    high_1 = resampled['high'].shift(2)
    low_1 = resampled['low'].shift(2)
    high_3 = resampled['high']
    low_3 = resampled['low']
    
    bull_mask = high_1 < low_3
    bear_mask = low_1 > high_3
    
    fvg = pd.DataFrame(index=resampled.index)
    fvg['fvg_type'] = 0
    fvg.loc[bull_mask, 'fvg_type'] = 1
    fvg.loc[bear_mask, 'fvg_type'] = -1
    
    fvg['fvg_top'] = np.nan
    fvg['fvg_bottom'] = np.nan
    fvg.loc[bull_mask, 'fvg_top'] = low_3
    fvg.loc[bull_mask, 'fvg_bottom'] = high_1
    fvg.loc[bear_mask, 'fvg_top'] = low_1
    fvg.loc[bear_mask, 'fvg_bottom'] = high_3
    
    return fvg.reindex(df.index, method='ffill')

def detect_fvgs_v5(df: pd.DataFrame, timeframe: str = '5min') -> pd.DataFrame:
    """
    Detects 3-bar Fair Value Gaps on a fixed timeframe (vectorized) for v5.
    Returns a DataFrame with columns: fvg_type, fvg_top, fvg_bottom, fvg_finalized_time.
    """
    resampled = df[['high', 'low']].resample(timeframe, origin='start_day').agg({
        'high': 'max',
        'low': 'min'
    }).dropna()
    
    high_1 = resampled['high'].shift(2)
    low_1 = resampled['low'].shift(2)
    high_3 = resampled['high']
    low_3 = resampled['low']
    
    bull_mask = (high_1 < low_3) & (high_1.notna()) & (low_3.notna())
    bear_mask = (low_1 > high_3) & (low_1.notna()) & (high_3.notna())
    
    fvg = pd.DataFrame(index=resampled.index)
    fvg['fvg_type'] = 0
    fvg.loc[bull_mask, 'fvg_type'] = 1
    fvg.loc[bear_mask, 'fvg_type'] = -1
    
    fvg['fvg_top'] = np.nan
    fvg['fvg_bottom'] = np.nan
    fvg.loc[bull_mask, 'fvg_top'] = low_3
    fvg.loc[bull_mask, 'fvg_bottom'] = high_1
    fvg.loc[bear_mask, 'fvg_top'] = low_1
    fvg.loc[bear_mask, 'fvg_bottom'] = high_3
    
    fvg['fvg_finalized_time'] = fvg.index + pd.Timedelta(timeframe)
    return fvg

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
            bias_1m == 1, df['close'] < stop_1m,
            np.where(bias_1m == -1, df['close'] > stop_1m, False)
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

def evaluate_target_vs_stop_vectorized(
    df: pd.DataFrame,
    bias: pd.Series,
    target_price: pd.Series,
    stop_price: pd.Series,
    start_time: pd.Series,
    out_end_time: pd.Series
) -> pd.Series:
    """
    Races target price vs stop price (opposite close) inside the outcome window.
    Only counts hits that occur at or after start_time.
    """
    if isinstance(bias, np.ndarray):
        bias = pd.Series(bias, index=df['logical_date'].unique())
    if isinstance(target_price, np.ndarray):
        target_price = pd.Series(target_price, index=bias.index)
    if isinstance(stop_price, np.ndarray):
        stop_price = pd.Series(stop_price, index=bias.index)
    if isinstance(start_time, np.ndarray) or isinstance(start_time, pd.DatetimeIndex):
        start_time = pd.Series(start_time, index=bias.index)
    if isinstance(out_end_time, np.ndarray):
        out_end_time = pd.Series(out_end_time, index=bias.index)
        
    logical_date = df['logical_date']
    
    # Broadcast to 1m
    bias_1m = bias.reindex(logical_date).values
    target_1m = target_price.reindex(logical_date).values
    stop_1m = stop_price.reindex(logical_date).values
    start_1m = start_time.reindex(logical_date).values
    
    # Bar must be in outcome window and at or after start_time
    is_after_start = df.index >= start_1m
    is_eligible = df['in_out'] & is_after_start
    
    target_hit = is_eligible & np.where(
        bias_1m == 1, df['high'] >= target_1m,
        np.where(bias_1m == -1, df['low'] <= target_1m, False)
    )
    
    stop_hit = is_eligible & np.where(
        bias_1m == 1, df['close'] < stop_1m,
        np.where(bias_1m == -1, df['close'] > stop_1m, False)
    )
    
    # Optimize min_target_idx groupby
    target_hit_bars = df[target_hit]
    if not target_hit_bars.empty:
        min_target_idx = target_hit_bars.groupby('logical_date')['bar_idx'].min().reindex(bias.index, fill_value=len(df))
    else:
        min_target_idx = pd.Series(len(df), index=bias.index)
        
    # Optimize min_stop_idx groupby
    stop_hit_bars = df[stop_hit]
    if not stop_hit_bars.empty:
        min_stop_idx = stop_hit_bars.groupby('logical_date')['bar_idx'].min().reindex(bias.index, fill_value=len(df))
    else:
        min_stop_idx = pd.Series(len(df), index=bias.index)
        
    target_reached = min_target_idx < len(df)
    stop_reached = min_stop_idx < len(df)
    
    correct = target_reached & (~stop_reached | (min_target_idx < min_stop_idx))
    return correct


def evaluate_all_plays_consolidated(
    df: pd.DataFrame,
    plays_config: List[Dict[str, Any]],  # list of dicts with active, direction, entry_price, target_price, stop_price, entry_idx
    ib_agg: pd.DataFrame,
    date_pos_1m: np.ndarray = None
) -> List[Tuple[pd.Series, pd.Series, pd.Series]]:
    """
    Evaluates play results, MAE, and MFE excursions for all plays consolidated in 3 groupbys.
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
            dir_1m == 1, df['close'] < stop_1m,
            np.where(dir_1m == -1, df['close'] > stop_1m, False)
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
    
    for i, cfg in enumerate(plays_config):
        min_tgt_arr = np.full(len(ib_agg), len(df), dtype=np.intp)
        min_stp_arr = np.full(len(ib_agg), len(df), dtype=np.intp)
        if valid_hits.any():
            min_tgt_arr[hits_pos[valid_hits]] = hits_min[f'tgt_{i}'].values[valid_hits]
            min_stp_arr[hits_pos[valid_hits]] = hits_min[f'stop_{i}'].values[valid_hits]
        
        target_reached = min_tgt_arr < len(df)
        stop_reached = min_stp_arr < len(df)
        
        play_res = np.where(
            cfg['active'].values,
            np.where(
                target_reached & (~stop_reached | (min_tgt_arr < min_stp_arr)),
                1, -1
            ),
            0
        )
        play_results.append(pd.Series(play_res, index=ib_agg.index))
        
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
        
        outputs.append((play_results[i], pd.Series(mfe_pct, index=ib_agg.index), pd.Series(mae_pct, index=ib_agg.index)))
        
    return outputs


def evaluate_play_excursions(
    df: pd.DataFrame,
    play_active: pd.Series,
    direction: pd.Series,
    entry_price: pd.Series,
    target_price: pd.Series,
    stop_price: pd.Series,
    entry_idx_series: pd.Series,
    ib_mid: pd.Series
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Computes play_result (+1, -1, 0) and MAE/MFE excursions.
    """
    if isinstance(play_active, np.ndarray):
        play_active = pd.Series(play_active, index=df['logical_date'].unique())
    if isinstance(direction, np.ndarray):
        direction = pd.Series(direction, index=play_active.index)
    if isinstance(entry_price, np.ndarray):
        entry_price = pd.Series(entry_price, index=play_active.index)
    if isinstance(target_price, np.ndarray):
        target_price = pd.Series(target_price, index=play_active.index)
    if isinstance(stop_price, np.ndarray):
        stop_price = pd.Series(stop_price, index=play_active.index)
    if isinstance(entry_idx_series, np.ndarray):
        entry_idx_series = pd.Series(entry_idx_series, index=play_active.index)
        
    logical_date = df['logical_date']
    
    # Broadcast to 1m
    active_1m = play_active.reindex(logical_date).values
    dir_1m = direction.reindex(logical_date).values
    entry_1m = entry_price.reindex(logical_date).values
    target_1m = target_price.reindex(logical_date).values
    stop_1m = stop_price.reindex(logical_date).values
    entry_idx_1m = entry_idx_series.reindex(logical_date).values
    
    is_eligible = df['in_out'] & active_1m & (df['bar_idx'] >= entry_idx_1m)
    
    target_hit = is_eligible & np.where(
        dir_1m == 1, df['high'] >= target_1m,
        np.where(dir_1m == -1, df['low'] <= target_1m, False)
    )
    
    stop_hit = is_eligible & np.where(
        dir_1m == 1, df['close'] < stop_1m,
        np.where(dir_1m == -1, df['close'] > stop_1m, False)
    )
    
    bar_idx = df['bar_idx']
    target_idx = np.where(target_hit, bar_idx, len(df))
    stop_idx = np.where(stop_hit, bar_idx, len(df))
    
    min_target_idx = pd.Series(target_idx, index=logical_date).groupby('logical_date').min().reindex(play_active.index)
    min_stop_idx = pd.Series(stop_idx, index=logical_date).groupby('logical_date').min().reindex(play_active.index)
    
    target_reached = min_target_idx < len(df)
    stop_reached = min_stop_idx < len(df)
    
    play_result = np.where(
        play_active,
        np.where(
            target_reached & (~stop_reached | (min_target_idx < min_stop_idx)),
            1, -1
        ),
        0
    )
    
    max_out_idx = df[df['in_out']].groupby('logical_date')['bar_idx'].max().reindex(play_active.index)
    
    exit_idx = np.minimum(
        np.minimum(min_target_idx.fillna(len(df)).values, min_stop_idx.fillna(len(df)).values),
        max_out_idx.fillna(len(df)).values
    )
    
    exit_idx_1m = pd.Series(exit_idx, index=play_active.index).reindex(logical_date).values
    
    in_trade = (df['bar_idx'] >= entry_idx_1m) & (df['bar_idx'] <= exit_idx_1m) & active_1m
    
    trade_high = np.where(in_trade, df['high'], -np.inf)
    trade_low = np.where(in_trade, df['low'], np.inf)
    
    max_high = pd.Series(trade_high, index=logical_date).groupby('logical_date').max().reindex(play_active.index)
    min_low = pd.Series(trade_low, index=logical_date).groupby('logical_date').min().reindex(play_active.index)
    
    mfe = np.where(
        play_active & (direction == 1), max_high - entry_price,
        np.where(play_active & (direction == -1), entry_price - min_low, 0.0)
    )
    
    mae = np.where(
        play_active & (direction == 1), entry_price - min_low,
        np.where(play_active & (direction == -1), max_high - entry_price, 0.0)
    )
    
    mfe = np.maximum(0.0, mfe)
    mae = np.maximum(0.0, mae)
    
    mid_vals = ib_mid.values
    mfe_pct = np.where(mid_vals > 0, mfe / mid_vals * 100, 0.0)
    mae_pct = np.where(mid_vals > 0, mae / mid_vals * 100, 0.0)
    
    return pd.Series(play_result, index=play_active.index), pd.Series(mfe_pct, index=play_active.index), pd.Series(mae_pct, index=play_active.index)


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


def extract_fvg_reuse_details(df: pd.DataFrame, fvg_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts horizontal zone touch/reuse details for all detected FVGs (fully vectorized global merge).
    """
    fvg_df = fvg_df[fvg_df['fvg_type'] != 0].copy()
    if fvg_df.empty:
        return pd.DataFrame(columns=['trading_day', 'fvg_id', 'touch_n', 'formed_time', 'dir', 'top', 'bot', 'formed_phase', 'touch_time', 'touch_phase', 'reaction', 'inverted'])
        
    fvg_df['fvg_id'] = fvg_df.groupby('logical_date').cumcount() + 1
    
    # Calculate formed_phase using integer minutes for speed
    fvg_fin_mins = fvg_df['fvg_finalized_time'].dt.hour * 60 + fvg_df['fvg_finalized_time'].dt.minute
    fvg_df['formed_phase'] = np.where(fvg_fin_mins <= fvg_df['ib_end_mins'], 'formation', 'outcome')
    
    # Filter fvg_df to keep only dates present in df
    valid_dates = df['logical_date'].unique()
    fvg_df = fvg_df[fvg_df['logical_date'].isin(valid_dates)].copy()
    
    if fvg_df.empty:
        return pd.DataFrame(columns=['trading_day', 'fvg_id', 'touch_n', 'formed_time', 'dir', 'top', 'bot', 'formed_phase', 'touch_time', 'touch_phase', 'reaction', 'inverted'])
        
    fvg_cols = ['logical_date', 'fvg_id', 'fvg_finalized_time', 'fvg_type', 'fvg_top', 'fvg_bottom', 'ib_end_mins', 'out_end_mins', 'formed_phase']
    fvg_sub = fvg_df[fvg_cols].copy()
    
    # Use numpy searchsorted group approach instead of pd.merge cross-join.
    # Both df_1m_sub and fvg_sub are sorted by logical_date (time-series invariant).
    # np.searchsorted finds group boundaries O(log n); per-group broadcasting is pure numpy.
    #
    # IMPORTANT: use ALL 1m bars for each logical_date (no in_ib/in_out filter).
    # The baseline includes overnight bars (touch_time can be 00:00:00) because overnight
    # FVGs are touched by bars from their formation time up to session end.
    # The after_fin check in the loop correctly excludes bars before the FVG formed.
    df_1m_sub = df[['high', 'low', 'close', 'logical_date', 'minutes_from_midnight']].copy()
    df_1m_sub['timestamp'] = df_1m_sub.index
    df_dates_raw = df_1m_sub['logical_date'].values    # Python datetime.date objects
    fvg_dates_raw = fvg_sub['logical_date'].values     # Python datetime.date objects

    # Convert to int32 ordinals for reliable numpy searchsorted / intersect1d
    # (numpy's object-array comparisons for datetime.date are not stable across versions)
    df_date_ords  = np.fromiter((d.toordinal() for d in df_dates_raw),  dtype=np.int32, count=len(df_dates_raw))
    fvg_date_ords = np.fromiter((d.toordinal() for d in fvg_dates_raw), dtype=np.int32, count=len(fvg_dates_raw))

    # Unique sorted ordinals present in both
    unique_ords = np.intersect1d(df_date_ords, fvg_date_ords)  # int32, sorted
    if len(unique_ords) == 0:
        return pd.DataFrame(columns=['trading_day', 'fvg_id', 'touch_n', 'formed_time', 'dir', 'top', 'bot', 'formed_phase', 'touch_time', 'touch_phase', 'reaction', 'inverted'])

    # Map ordinals back to Python date objects (needed for result arrays)
    _ord_to_date: dict[int, object] = {}
    for _ord, _dt in zip(df_date_ords, df_dates_raw):
        if _ord not in _ord_to_date:
            _ord_to_date[_ord] = _dt
    unique_dates = [_ord_to_date[o] for o in unique_ords]  # list[datetime.date], len == unique_ords

    # Build group boundary arrays using int32 ordinals (reliable searchsorted)
    df_lo = np.searchsorted(df_date_ords,  unique_ords, side='left')
    df_hi = np.searchsorted(df_date_ords,  unique_ords, side='right')
    fv_lo = np.searchsorted(fvg_date_ords, unique_ords, side='left')
    fv_hi = np.searchsorted(fvg_date_ords, unique_ords, side='right')

    # Pre-extract numpy arrays for zero-copy inner loops
    bar_ts    = df_1m_sub['timestamp'].values
    bar_high  = df_1m_sub['high'].values
    bar_low   = df_1m_sub['low'].values
    bar_close = df_1m_sub['close'].values
    bar_mins  = df_1m_sub['minutes_from_midnight'].values

    fvg_fin_time     = fvg_sub['fvg_finalized_time'].values
    fvg_type         = fvg_sub['fvg_type'].values
    fvg_top          = fvg_sub['fvg_top'].values
    fvg_bot          = fvg_sub['fvg_bottom'].values
    fvg_id           = fvg_sub['fvg_id'].values
    fvg_ib_end       = fvg_sub['ib_end_mins'].values
    fvg_out_end      = fvg_sub['out_end_mins'].values
    fvg_formed_phase = fvg_sub['formed_phase'].values

    # Per-day numpy broadcasting: (nb, nf) boolean matrix per day, no Python cross-join.
    # Bars and FVGs are pre-sorted by logical_date; searchsorted gives O(log n) boundaries.
    # Global hit index arrays built via concatenation — no per-day Python list overhead.
    all_bar_idx, all_fvg_idx, all_day_idx = [], [], []

    for i in range(len(unique_dates)):
        bi0, bi1 = df_lo[i], df_hi[i]
        fi0, fi1 = fv_lo[i], fv_hi[i]
        if bi0 == bi1 or fi0 == fi1:
            continue

        b_mn = bar_mins[bi0:bi1]
        day_out_end = int(fvg_out_end[fi0])
        in_sess = b_mn <= day_out_end
        if not in_sess.any():
            continue

        # Local (within-day) indices for bars passing the session filter
        local_bar_pos = np.where(in_sess)[0]       # positions within bi0:bi1
        b_ts_d = bar_ts[bi0:bi1][local_bar_pos]
        b_hi_d = bar_high[bi0:bi1][local_bar_pos]
        b_lo_d = bar_low[bi0:bi1][local_bar_pos]

        f_fin = fvg_fin_time[fi0:fi1]
        f_tp  = fvg_top[fi0:fi1]
        f_bt  = fvg_bot[fi0:fi1]

        # SIMD-vectorized (nb_d, nf) boolean matrix — numpy BLAS-level throughput
        touches = (b_ts_d[:, None] > f_fin[None, :]) & \
                  (b_lo_d[:, None] <= f_tp[None, :]) & \
                  (b_hi_d[:, None] >= f_bt[None, :])

        local_bi, local_fi = np.where(touches)
        if len(local_bi) == 0:
            continue

        # Sort by (fvg, bar) so output is in (logical_date, fvg_id, timestamp) order
        sort_ord = np.lexsort((local_bi, local_fi))
        local_bi = local_bi[sort_ord]
        local_fi = local_fi[sort_ord]

        # Map back to global flat indices
        all_bar_idx.append(bi0 + local_bar_pos[local_bi])   # global bar index
        all_fvg_idx.append(fi0 + local_fi)                  # global fvg index
        all_day_idx.append(np.full(len(local_bi), i, dtype=np.intp))

    if not all_bar_idx:
        merged = pd.DataFrame(columns=['logical_date', 'fvg_id', 'fvg_finalized_time', 'fvg_type',
                                        'fvg_top', 'fvg_bottom', 'formed_phase', 'timestamp',
                                        'high', 'low', 'close', 'minutes_from_midnight', 'ib_end_mins'])
    else:
        hit_bar = np.concatenate(all_bar_idx)
        hit_fvg = np.concatenate(all_fvg_idx)
        # Direct numpy indexing — no per-day list appends of full column arrays
        merged = pd.DataFrame({
            'logical_date':          df_dates_raw[hit_bar],
            'fvg_id':                fvg_id[hit_fvg],
            'fvg_finalized_time':    fvg_fin_time[hit_fvg],
            'fvg_type':              fvg_type[hit_fvg],
            'fvg_top':               fvg_top[hit_fvg],
            'fvg_bottom':            fvg_bot[hit_fvg],
            'formed_phase':          fvg_formed_phase[hit_fvg],
            'timestamp':             bar_ts[hit_bar],
            'high':                  bar_high[hit_bar],
            'low':                   bar_low[hit_bar],
            'close':                 bar_close[hit_bar],
            'minutes_from_midnight': bar_mins[hit_bar],
            'ib_end_mins':           fvg_ib_end[hit_fvg],
        })
    
    if merged.empty:
        # No touches at all — all FVGs untouched
        untouched_out = pd.DataFrame({
            'trading_day': fvg_df['logical_date'],
            'fvg_id':      fvg_df['fvg_id'],
            'touch_n':     0,
            'formed_time': fvg_df['fvg_finalized_time'],
            'dir':         fvg_df['fvg_type'].astype(int),
            'top':         fvg_df['fvg_top'],
            'bot':         fvg_df['fvg_bottom'],
            'formed_phase': fvg_df['formed_phase'],
            'touch_time':  pd.NaT,
            'touch_phase': None,
            'reaction':    None,
            'inverted':    False
        })
        return untouched_out[['trading_day', 'fvg_id', 'touch_n', 'formed_time', 'dir', 'top', 'bot', 'formed_phase', 'touch_time', 'touch_phase', 'reaction', 'inverted']]

    # --- O(n) numpy post-processing (no sort_values / groupby) ---
    # The loop pre-sorted each day's output by (fvg_ii, bar_ii), and unique_dates
    # is sorted, so merged is already in (logical_date, fvg_id, timestamp) order.

    ld_arr = merged['logical_date'].values
    fi_arr = merged['fvg_id'].values

    # Group-change mask: True at the start of each (logical_date, fvg_id) group
    group_start = np.empty(len(merged), dtype=bool)
    group_start[0] = True
    group_start[1:] = (ld_arr[1:] != ld_arr[:-1]) | (fi_arr[1:] != fi_arr[:-1])

    # O(n) cumcount: global_pos - group_start_pos_of_this_element
    group_start_pos = np.where(group_start)[0]
    group_sizes     = np.diff(np.append(group_start_pos, len(merged)))
    start_per_elem  = np.repeat(group_start_pos, group_sizes)
    touch_n_arr     = np.arange(len(merged)) - start_per_elem + 1   # 1-indexed

    # Close-through check (vectorized, no groupby)
    fvg_type_arr = merged['fvg_type'].values
    close_arr    = merged['close'].values
    fvg_top_arr  = merged['fvg_top'].values
    fvg_bot_arr  = merged['fvg_bottom'].values
    is_break_arr = np.where(
        fvg_type_arr == 1,
        close_arr < fvg_bot_arr,
        close_arr > fvg_top_arr
    )

    # O(n) cummax-with-resets (cumany per group) using cumsum offset trick:
    #   cumsum_break[i] > cumsum_at_group_start[i]  iff  any break since group start
    cumsum_break = np.cumsum(is_break_arr.astype(np.int32))
    # cumsum value at end of previous group (= 0 for first group)
    prev_end_cs = np.zeros(len(merged), dtype=np.int32)
    prev_end_cs[group_start_pos[1:]] = cumsum_break[group_start_pos[1:] - 1]
    # Each element's "group start cumsum offset" = cumsum_break value just before its group started.
    # Stored as sparse deltas at group boundaries; np.repeat broadcasts them per-element.
    group_start_cs_vals = np.concatenate([[0], cumsum_break[group_start_pos[1:] - 1]])
    group_cs_offset     = np.repeat(group_start_cs_vals, group_sizes)
    inverted_arr        = (cumsum_break - group_cs_offset) > 0

    # touch_phase and reaction (fully vectorized)
    mins_arr        = merged['minutes_from_midnight'].values
    ib_end_mins_arr = merged['ib_end_mins'].values
    touch_phase_arr = np.where(mins_arr <= ib_end_mins_arr, 'formation', 'outcome')
    reaction_arr    = np.where(is_break_arr, 'closed_through', 'held')

    touched_out = pd.DataFrame({
        'trading_day':  ld_arr,
        'fvg_id':       fi_arr,
        'touch_n':      touch_n_arr,
        'formed_time':  merged['fvg_finalized_time'].values,
        'dir':          fvg_type_arr.astype(int),
        'top':          fvg_top_arr,
        'bot':          fvg_bot_arr,
        'formed_phase': merged['formed_phase'].values,
        'touch_time':   merged['timestamp'].values,
        'touch_phase':  touch_phase_arr,
        'reaction':     reaction_arr,
        'inverted':     inverted_arr,
    })

    # Untouched FVG detection: numpy isin instead of pd.merge + drop_duplicates
    # Build unique (logical_date, fvg_id) set from first-touch rows (touch_n == 1)
    first_touch_mask = group_start   # group_start coincides with touch_n == 1
    touched_ld = ld_arr[first_touch_mask]
    touched_fi = fi_arr[first_touch_mask]
    # Composite integer key: date_ordinal * 100000 + fvg_id (fvg_id << 17 bits safe for <131072 FVGs/day)
    def _composite(ld_a, fi_a):
        # logical_date is datetime.date; convert to ordinal for hashing
        return np.array([d.toordinal() for d in ld_a], dtype=np.int64) * 100000 + fi_a.astype(np.int64)

    touched_keys_set  = _composite(touched_ld, touched_fi)
    fvg_keys          = _composite(fvg_df['logical_date'].values, fvg_df['fvg_id'].values)
    is_untouched      = ~np.isin(fvg_keys, touched_keys_set)
    untouched_fvg     = fvg_df[is_untouched]

    untouched_out = pd.DataFrame({
        'trading_day':  untouched_fvg['logical_date'].values,
        'fvg_id':       untouched_fvg['fvg_id'].values,
        'touch_n':      0,
        'formed_time':  untouched_fvg['fvg_finalized_time'].values,
        'dir':          untouched_fvg['fvg_type'].values.astype(int),
        'top':          untouched_fvg['fvg_top'].values,
        'bot':          untouched_fvg['fvg_bottom'].values,
        'formed_phase': untouched_fvg['formed_phase'].values,
        'touch_time':   pd.NaT,
        'touch_phase':  None,
        'reaction':     None,
        'inverted':     False,
    })

    # Concat and final sort (only on the small untouched_out, already sorted)
    res_df = pd.concat([touched_out, untouched_out], ignore_index=True)
    # touched_out is already sorted by (trading_day, fvg_id, touch_n);
    # untouched_out has touch_n=0 and needs to be interspersed.
    res_df = res_df.sort_values(by=['trading_day', 'fvg_id', 'touch_n']).reset_index(drop=True)

    expected_cols = ['trading_day', 'fvg_id', 'touch_n', 'formed_time', 'dir', 'top', 'bot', 'formed_phase', 'touch_time', 'touch_phase', 'reaction', 'inverted']
    return res_df[expected_cols]


def calculate_ib_statistics_v5(
    df_1m: pd.DataFrame,
    symbol: str,
    session_choice: str = "NY AM IB",
    time_basis: str = "ET_fixed",
    use_fvg: bool = True,
    vix_series: Optional[pd.Series] = None,
    df_1m_precalc: Optional[pd.DataFrame] = None,
    fvg_df_precalc: Optional[pd.DataFrame] = None,
    daily_atr_precalc: Optional[pd.Series] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Computes complete Initial Balance stats and details for the selected session (v5 Spec).
    Returns (facts_df, level_touch_df, fvg_detail_df).
    """
    if session_choice not in SESSION_CONFIGS_V5:
        raise ValueError(f"Unknown session choice: {session_choice}")
        
    cfg = SESSION_CONFIGS_V5[session_choice]
    
    # 1. Normalize timezone and dates
    if df_1m_precalc is not None:
        df = df_1m_precalc.copy()
        us_dst = df['us_dst']
        uk_dst = df['uk_dst']
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
    
    tie_breaker = np.where(ib_agg['ib_close'] > ib_agg['ib_open'], 1, -1)
    
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
    
    # Broadcast to 1m — build integer positional map once to replace all .reindex(logical_date) calls
    logical_date = df['logical_date']
    # date_pos_1m[i] = position of logical_date[i] in ib_agg.index (O(n) numpy lookup)
    # Dates not in ib_agg (weekends, holidays outside session) default to 0 — safe because
    # those bars always have in_ib=False/in_out=False, so they never affect outputs.
    _ib_agg_date_to_pos = {d: i for i, d in enumerate(ib_agg.index)}
    date_pos_1m = np.array([_ib_agg_date_to_pos.get(d, 0) for d in logical_date], dtype=np.intp)
    df = df.join(ib_agg[['ib_high', 'ib_low', 'ib_mid', 'ib_range']], on='logical_date')
    
    # 4. FVG Calculations
    if fvg_df_precalc is not None:
        fvg_df = fvg_df_precalc.copy()
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
        first_ib_fvg[['fvg_type', 'fvg_top', 'fvg_bottom', 'fvg_finalized_time']].rename(
            columns={
                'fvg_type': 'bias_fvg',
                'fvg_top': 'ib_fvg_top',
                'fvg_bottom': 'ib_fvg_bottom',
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
            first_1011_fvg[['fvg_type', 'fvg_top', 'fvg_bottom', 'fvg_finalized_time']].rename(
                columns={
                    'fvg_type': 'bias_fvg_1011',
                    'fvg_top': 'fvg_1011_top',
                    'fvg_bottom': 'fvg_1011_bottom',
                    'fvg_finalized_time': 'fvg_1011_fin_time'
                }
            )
        )
        ib_agg['bias_fvg_1011'] = ib_agg['bias_fvg_1011'].fillna(0).astype(int)
    else:
        ib_agg['bias_fvg_rth'] = 0
        ib_agg['bias_fvg_1011'] = 0
        ib_agg['fvg_1011_fin_time'] = pd.NaT
        
    # Check if first FVG is broken
    df = df.join(
        ib_agg[['bias_fvg', 'ib_fvg_top', 'ib_fvg_bottom', 'ib_fvg_fin_time']],
        on='logical_date'
    )
    
    is_after_fvg = df.index >= df['ib_fvg_fin_time'].values
    is_before_out_end = df['minutes_from_midnight'].values < df['out_end_mins'].values
    
    df['fvg_broken_bar'] = np.where(
        is_after_fvg & is_before_out_end & (df['bias_fvg'] == 1),
        df['close'] < df['ib_fvg_bottom'],
        np.where(
            is_after_fvg & is_before_out_end & (df['bias_fvg'] == -1),
            df['close'] > df['ib_fvg_top'],
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
    break_high_bar = df['in_out'] & (df['high'] > df['ib_high'])
    break_low_bar = df['in_out'] & (df['low'] < df['ib_low'])
    
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
    target_reached_high_bar = df['in_out'] & (df['high'] >= df['ib_high'] + 0.5 * df['ib_range'])
    target_reached_high_bars = df[target_reached_high_bar]
    if not target_reached_high_bars.empty:
        target_reached_high_idx = target_reached_high_bars.groupby('logical_date')['bar_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    else:
        target_reached_high_idx = pd.Series(len(df), index=ib_agg.index)
        
    # Optimize target_reached_low_idx groupby
    target_reached_low_bar = df['in_out'] & (df['low'] <= df['ib_low'] - 0.5 * df['ib_range'])
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
    
    # 7. Level extension hits (consolidated single groupby on 16 columns)
    levels = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
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
    
    # Level touch and mid touch calculations
    level_touch_df = extract_level_touch_details(df, ib_agg)
    
    # Promote 50% touches to ib_agg (numpy positional indexing)
    low_1m = ib_agg['ib_low'].values[date_pos_1m]
    range_1m = ib_agg['ib_range'].values[date_pos_1m]
    mid_lock_1m = ib_agg['mid_lock_time'].values[date_pos_1m]
    
    mid_lvl_price = low_1m + 0.5 * range_1m
    mid_touch_bar = (df['low'] <= mid_lvl_price) & (df['high'] >= mid_lvl_price)
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
    
    ib_agg['mid_touch_first_time'] = mid_touch_bars.groupby('logical_date')['datetime'].first().reindex(ib_agg.index)
    ib_agg['mid_touch_first_phase'] = mid_touch_bars.groupby('logical_date')['phase'].first().reindex(ib_agg.index)
    
    is_form_touch = mid_touch_bars['phase'].isin(['formation_pre_lock', 'formation_post_lock'])
    ib_agg['mid_touch_last_formation_time'] = mid_touch_bars[is_form_touch].groupby('logical_date')['datetime'].last().reindex(ib_agg.index)
    
    ib_agg['mid_touch_count_formation'] = mid_touch_bars[is_form_touch].groupby('logical_date').size().reindex(ib_agg.index)
    ib_agg['mid_touch_count_outcome'] = mid_touch_bars[mid_touch_bars['phase'] == 'outcome'].groupby('logical_date').size().reindex(ib_agg.index)
    ib_agg['mid_touch_count_formation'] = ib_agg['mid_touch_count_formation'].fillna(0).astype(int)
    ib_agg['mid_touch_count_outcome'] = ib_agg['mid_touch_count_outcome'].fillna(0).astype(int)
    
    ib_agg['mid_touched_again'] = mid_touch_bars.groupby('logical_date').size().reindex(ib_agg.index) > 1
    ib_agg['mid_touched_again'] = ib_agg['mid_touched_again'].fillna(False)
    
    ib_agg['mid_touch_count_post_lock'] = mid_touch_bars[mid_touch_bars['phase'] == 'formation_post_lock'].groupby('logical_date').size().reindex(ib_agg.index)
    ib_agg['mid_touch_count_post_lock'] = ib_agg['mid_touch_count_post_lock'].fillna(0).astype(int)
    
    ib_agg['early_mid_event'] = (ib_agg['mid_lock_frac'] <= 2.0/3.0) & (ib_agg['mid_touch_count_post_lock'] > 0)
    
    # 10. Bias Outcomes Grading (0.5x and 1.0x targets) (consolidated race evaluation)
    variants = ['formation_firstreach', 'formation_lasttouch', 'close_dir', 'fvg', 'fvg_ifvg']
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
        elif v == 'fvg_ifvg':
            # It flips if broken. If broken, it is finalized at fvg_broken_time.
            # Otherwise finalized at ib_fvg_fin_time.
            fin_time = np.where(ib_agg['fvg_broken_time'].notna(), ib_agg['fvg_broken_time'], ib_agg['ib_fvg_fin_time'])
            # Use ndarray cast instead of pd.to_datetime() (avoids slow object-array inference)
            fin_time = fin_time.astype('datetime64[ns]')
        else:
            fin_time = ib_end_time
        fin_time = pd.Series(fin_time, index=ib_agg.index)
        fin_time = fin_time.combine_first(ib_end_time)
        
        for lvl in [0.5, 1.0]:
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
    
    # Assign correct boolean to ib_agg
    for v in variants:
        for lvl in [0.5, 1.0]:
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
                
            ib_agg[f'bias_correct_{v}_{lvl_col}x'] = correct
            
    # 11. Plays Evaluation
    # Broadcast to 1m (O(n) numpy positional indexing)
    mid_1m = ib_agg['ib_mid'].values[date_pos_1m]
    high_1m = ib_agg['ib_high'].values[date_pos_1m]
    low_1m = ib_agg['ib_low'].values[date_pos_1m]
    range_1m = ib_agg['ib_range'].values[date_pos_1m]
    first_break_dir_1m = ib_agg['first_break_dir'].values[date_pos_1m]
    first_break_idx_1m = ib_agg['first_break_idx'].values[date_pos_1m]
    bar_idx = df['bar_idx']
    
    # 1. Play 2 entry index and Play 3 overshoot index (consolidated in one groupby)
    df_play_indices = pd.DataFrame(index=df.index)
    df_play_indices['logical_date'] = logical_date
    
    p2_touch = df['in_out'] & (df['bar_idx'] > first_break_idx_1m) & (df['low'] <= mid_1m) & (df['high'] >= mid_1m)
    df_play_indices['p2_entry'] = np.where(p2_touch, df['bar_idx'], len(df))
    
    overshoot_lvl = np.where(first_break_dir_1m == 1, high_1m + 0.25 * range_1m, low_1m - 0.25 * range_1m)
    overshoot_cond = df['in_out'] & np.where(
        first_break_dir_1m == 1, df['high'] >= overshoot_lvl,
        np.where(first_break_dir_1m == -1, df['low'] <= overshoot_lvl, False)
    )
    df_play_indices['p3_overshoot'] = np.where(overshoot_cond, df['bar_idx'], len(df))
    
    play_indices_min = df_play_indices.groupby('logical_date').min()
    
    p2_entry_idx = play_indices_min['p2_entry'].reindex(ib_agg.index, fill_value=len(df))
    overshoot_idx = play_indices_min['p3_overshoot'].reindex(ib_agg.index, fill_value=len(df))
    overshoot_idx_1m = overshoot_idx.reindex(logical_date).values
    
    # 3. Play 3 fill index (requires overshoot first)
    fill_lvl = np.where(first_break_dir_1m == 1, high_1m, low_1m)
    fill_cond = df['in_out'] & (df['bar_idx'] > overshoot_idx_1m) & (df['low'] <= fill_lvl) & (df['high'] >= fill_lvl)
    
    df_fill = pd.DataFrame(index=df.index)
    df_fill['logical_date'] = logical_date
    df_fill['fill_idx'] = np.where(fill_cond, df['bar_idx'], len(df))
    fill_idx = df_fill.groupby('logical_date')['fill_idx'].min().reindex(ib_agg.index, fill_value=len(df))
    
    # Build configurations for all 3 plays to evaluate them consolidated
    plays_config = [
        {
            'active': ib_agg['first_break_dir'] != 0,
            'direction': ib_agg['first_break_dir'],
            'entry_price': pd.Series(np.where(ib_agg['first_break_dir'] == 1, ib_agg['ib_high'], ib_agg['ib_low']), index=ib_agg.index),
            'target_price': pd.Series(np.where(ib_agg['first_break_dir'] == 1, ib_agg['ib_high'] + ib_agg['ib_range'], ib_agg['ib_low'] - ib_agg['ib_range']), index=ib_agg.index),
            'stop_price': pd.Series(np.where(ib_agg['first_break_dir'] == 1, ib_agg['ib_low'], ib_agg['ib_high']), index=ib_agg.index),
            'entry_idx': ib_agg['first_break_idx']
        },
        {
            'active': (ib_agg['first_break_dir'] != 0) & (p2_entry_idx < len(df)),
            'direction': ib_agg['first_break_dir'],
            'entry_price': ib_agg['ib_mid'],
            'target_price': pd.Series(np.where(ib_agg['first_break_dir'] == 1, ib_agg['ib_high'] + 0.5 * ib_agg['ib_range'], ib_agg['ib_low'] - 0.5 * ib_agg['ib_range']), index=ib_agg.index),
            'stop_price': pd.Series(np.where(ib_agg['first_break_dir'] == 1, ib_agg['ib_low'], ib_agg['ib_high']), index=ib_agg.index),
            'entry_idx': p2_entry_idx
        },
        {
            'active': (ib_agg['first_break_dir'] != 0) & (fill_idx < len(df)),
            'direction': -ib_agg['first_break_dir'],
            'entry_price': pd.Series(np.where(ib_agg['first_break_dir'] == 1, ib_agg['ib_high'], ib_agg['ib_low']), index=ib_agg.index),
            'target_price': ib_agg['ib_mid'],
            'stop_price': pd.Series(np.where(ib_agg['first_break_dir'] == 1, ib_agg['ib_high'] + 0.5 * ib_agg['ib_range'], ib_agg['ib_low'] - 0.5 * ib_agg['ib_range']), index=ib_agg.index),
            'entry_idx': fill_idx
        }
    ]
    
    play_results = evaluate_all_plays_consolidated(df, plays_config, ib_agg, date_pos_1m)
    
    p1_res, p1_mfe, p1_mae = play_results[0]
    ib_agg['play1_result'] = p1_res
    ib_agg['play1_rr'] = 1.0
    ib_agg['play1_mfe'] = p1_mfe
    ib_agg['play1_mae'] = p1_mae
    
    p2_res, p2_mfe, p2_mae = play_results[1]
    ib_agg['play2_result'] = p2_res
    ib_agg['play2_rr'] = 2.0
    ib_agg['play2_mfe'] = p2_mfe
    ib_agg['play2_mae'] = p2_mae
    
    p3_res, p3_mfe, p3_mae = play_results[2]
    ib_agg['play3_result'] = p3_res
    ib_agg['play3_rr'] = 1.0
    ib_agg['play3_mfe'] = p3_mfe
    ib_agg['play3_mae'] = p3_mae
    
    # 12. FVG Reuse long-format tracking
    fvg_detail_df = extract_fvg_reuse_details(df, fvg_df)
    
    # 13. Clean and build final output fact table
    facts_df = ib_agg.reset_index().rename(columns={'logical_date': 'trading_day'})
    facts_df['symbol'] = symbol
    facts_df['session_slot'] = session_choice
    facts_df['time_basis'] = time_basis
    
    # Add calendar/DST info
    daily_dst_info = df.groupby('logical_date')[['us_dst', 'uk_dst', 'et_window_offset_hours', 'dst_regime']].first().reset_index()
    facts_df = facts_df.merge(daily_dst_info.rename(columns={'logical_date': 'trading_day'}), on='trading_day')
    
    # DOW — compute directly from date objects (no pd.to_datetime conversion needed)
    _DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    facts_df['dow'] = [_DAY_NAMES[d.weekday()] for d in facts_df['trading_day']]
    
    # Prior day same-slot result (streak calculation support)
    facts_df['prior_day_result'] = np.sign(facts_df['play1_result'].shift(1))
    
    # Event timings clock buckets
    # Map first_break_idx and mid_lock_time to 15-minute clock buckets
    facts_df['first_break_time_val'] = facts_df['first_break_idx'].map(lambda idx: df.index[int(idx)] if not pd.isna(idx) and idx < len(df) else pd.NaT)
    facts_df['first_break_bucket'] = facts_df['first_break_time_val'].dt.floor('15min').dt.time
    facts_df['mid_touch_bucket'] = facts_df['mid_touch_first_time'].dt.floor('15min').dt.time
    
    # Cleanup level_touch_df
    level_touch_df['symbol'] = symbol
    level_touch_df['session_slot'] = session_choice
    level_touch_df['time_basis'] = time_basis
    level_touch_df = level_touch_df.rename(columns={'logical_date': 'trading_day'})
    
    # Cleanup fvg_detail_df
    fvg_detail_df['symbol'] = symbol
    fvg_detail_df['session_slot'] = session_choice
    fvg_detail_df['time_basis'] = time_basis
    
    return facts_df, level_touch_df, fvg_detail_df
