import pandas as pd
import numpy as np
import json
from .config import ICT_RESEARCH_DIR, OHLCV_DATA_DIR

def join_daily_data(macro_df: pd.DataFrame, instrument: str) -> pd.DataFrame:
    """
    Joins external daily-level data:
    1. Daily Scenarios enhanced CSV
    2. VIX daily close (prior day)
    3. 9:30 RTH Opening Bar
    """
    res_df = macro_df.copy()
    
    # ensure trading_date is datetime for join
    res_df['trading_date'] = pd.to_datetime(res_df['trading_date']).astype('datetime64[ns]')

    # 1. Daily Scenarios CSV
    # Mapping instrument to the enhanced CSV (NQ1 -> NQ)
    inst_short = instrument.replace('1', '')
    csv_path = ICT_RESEARCH_DIR / f"trading_days_enhanced_{inst_short}.csv"
    
    if csv_path.exists():
        daily_csv = pd.read_csv(csv_path)
        daily_csv['trading_date'] = pd.to_datetime(daily_csv['date']).astype('datetime64[ns]')
        
        # Select key columns to avoid naming collisions and clutter
        # We pull the specific institutional and bias traits requested
        cols_to_join = [
            'trading_date', 'pm_manipulation', 'is_judas_pm', 
            'manipulation_reversed', 'manipulation', 'is_judas_london', 
            'asia_pm_manip_reversed', 'r1', 'r2', 'dwp', 'dnp', 'bias',
            'rth_gap', 'rth_gap_pct', 'cbdr_l', 'cbdr_h', 'p12_l', 'p12_h',
            'pattern', 'ny_position'
        ]
        existing_cols = [c for c in cols_to_join if c in daily_csv.columns]
        
        res_df = res_df.merge(daily_csv[existing_cols], on='trading_date', how='left')

    # 2. VIX Daily (Prior Day Close)
    vix_path = OHLCV_DATA_DIR / "VIX_1d.parquet"
    if vix_path.exists():
        vix_df = pd.read_parquet(vix_path)
        vix_df.index = pd.to_datetime(vix_df.index).date
        
        # We need prior trading day. 
        # Simpler: Map VIX close to the NEXT trading day
        vix_mapped = vix_df[['close']].copy()
        vix_mapped.columns = ['vix_prior_close']
        
        # In this workflow, we can join by date - 1, or just shift the VIX index
        # But for institutional trading days, shift(1) on sorted index is safest
        vix_mapped = vix_mapped.sort_index()
        vix_mapped['vix_at_macro'] = vix_mapped['vix_prior_close'] # This is the close of 'date'
        
        # Join: macro.trading_date needs the VIX close of the PREVIOUS trading session
        # We'll use merge_asof for safety or a shifted lookup
        vix_lookup = vix_mapped[['vix_at_macro']].reset_index().rename(columns={'index': 'vix_date'})
        vix_lookup['vix_date'] = pd.to_datetime(vix_lookup['vix_date'])
        
        res_df = res_df.sort_values(['instrument', 'trading_date'])
        res_df = pd.merge_asof(
            res_df, 
            vix_lookup, 
            left_on='trading_date', 
            right_on='vix_date', 
            direction='backward', 
            allow_exact_matches=False
        ).drop(columns=['vix_date'])

        # VIX Regimes (Stable 20-Year Percentiles: 14.05, 17.56, 22.61)
        res_df['vix_regime'] = np.where(res_df['vix_at_macro'] < 14.05, 'low',
                               np.where(res_df['vix_at_macro'] < 17.56, 'medium',
                               np.where(res_df['vix_at_macro'] < 22.61, 'high', 'extreme')))

    # 3. 9:30 Opening Bar JSON
    json_path = OHLCV_DATA_DIR / f"{instrument}_opening_range.json"
    if json_path.exists():
        with open(json_path, 'r') as f:
            orb_data = json.load(f)
        
        orb_df = pd.DataFrame(orb_data)
        orb_df['trading_date'] = pd.to_datetime(orb_df['date']).astype('datetime64[ns]')
        
        # Validate columns before renaming to prevent KeyError
        rename_map = {
            'open': 'rth_bar_open',
            'high': 'rth_bar_high',
            'low': 'rth_bar_low',
            'close': 'rth_bar_close',
            'range_pct': 'rth_bar_range_pct'
        }
        actual_renames = {k: v for k, v in rename_map.items() if k in orb_df.columns}
        orb_df = orb_df.rename(columns=actual_renames)
        
        if 'rth_bar_high' in orb_df.columns and 'rth_bar_low' in orb_df.columns:
            orb_df['rth_bar_mid'] = (orb_df['rth_bar_high'] + orb_df['rth_bar_low']) / 2
        
        # Merge only what exists
        target_cols = ['trading_date', 'rth_bar_open', 'rth_bar_high', 'rth_bar_low', 'rth_bar_close', 'rth_bar_mid', 'rth_bar_range_pct']
        actual_cols = [c for c in target_cols if c in orb_df.columns]
        
        res_df = res_df.merge(
            orb_df[actual_cols], 
            on='trading_date', 
            how='left'
        )
        
        # Comparative Flags (Vectorized)
        res_df['macro_open_vs_rth_bar'] = None
        res_df['macro_open_vs_rth_bar_mid'] = None
        
        # Comparative Flags (Vectorized)
        res_df['macro_open_vs_rth_bar'] = None
        res_df['macro_open_vs_rth_bar_mid'] = None
        
        # High-precision is_rth: 9:30 to 17:00 ET
        h = res_df['macro_start'].dt.hour
        m = res_df['macro_start'].dt.minute
        res_df['is_rth'] = ((h > 9) | ((h == 9) & (m >= 30))) & (h < 17)
        
        # Ensure RTH bar columns actually EXIST in the dataframe before comparing
        if 'rth_bar_high' in res_df.columns:
            is_rth_mask = res_df['is_rth'] & res_df['rth_bar_high'].notna()
            
            if is_rth_mask.any():
                res_df.loc[is_rth_mask, 'macro_open_vs_rth_bar'] = np.where(
                    res_df.loc[is_rth_mask, 'open'] > res_df.loc[is_rth_mask, 'rth_bar_high'], 'above',
                    np.where(res_df.loc[is_rth_mask, 'open'] < res_df.loc[is_rth_mask, 'rth_bar_low'], 'below', 'inside')
                )
                if 'rth_bar_mid' in res_df.columns:
                    res_df.loc[is_rth_mask, 'macro_open_vs_rth_bar_mid'] = np.where(
                        res_df.loc[is_rth_mask, 'open'] > res_df.loc[is_rth_mask, 'rth_bar_mid'], 'above', 'below'
                    )

    return res_df
