import pandas as pd
import numpy as np
from typing import Dict, Any
import sys
import os

# Ensure legacy path is available
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from scripts.libs.nqstats.engine import NQStatsEngine

class NQStatsAdapter:
    """
    Bridge between legacy NQStats (points-based binary statuses) 
    and the new Statistical Trading Framework (vectorized features).
    """
    
    @staticmethod
    def get_box_features(df_1m: pd.DataFrame, ticker: str = "NQ1") -> pd.DataFrame:
        """
        Takes raw 1m data and returns a DataFrame of box statuses mapped 
        to numeric/binary features for the Framework.
        
        Mapping logic:
        - LT (Long True): 2
        - ST (Short True): -2
        - LF (Long False): 1
        - SF (Short False): -1
        - None/Pending: 0
        """
        engine = NQStatsEngine(df_1m, ticker=ticker)
        # NQStats process() handles the US/Eastern conversion internally
        stats = engine.process()
        
        # Define status mapping
        status_map = {
            "LT": 2,
            "ST": -2,
            "LF": 1,
            "SF": -1,
            "None": 0,
            "Pending": 0
        }
        
        # 0. Align index Timezones and forward-fill Daily stats to the 1m timeline
        if stats.index.tz is not None:
            stats.index = stats.index.tz_convert('US/Eastern').tz_localize(None)
            
        stats_aligned = stats.reindex(df_1m.index, method='ffill')
        feature_df = pd.DataFrame(index=df_1m.index)
        
        # 1. Map session box statuses
        for session in ['asia', 'london', 'ny1', 'ny2']:
            col = f'{session}box_status'
            if col in stats_aligned.columns:
                feature_df[f'feat_{session}_status'] = stats_aligned[col].map(status_map).fillna(0)
            else:
                feature_df[f'feat_{session}_status'] = 0
            
            # 2. Add 'broken' status as binary
            broken_col = f'{session}box_broken'
            if broken_col in stats_aligned.columns:
                feature_df[f'feat_{session}_broken'] = stats_aligned[broken_col].fillna(0).astype(int)
            else:
                feature_df[f'feat_{session}_broken'] = 0
            
        # 3. Add ALN Pattern as a feature
        feature_df['feat_aln_raw'] = stats_aligned['aln']
        
        # 4. Stationarity: Mid-points are normalized to % distance from current price
        # IMPORTANT: We use 'close' from the input df_1m because it is the actual 1m price.
        price_close = df_1m['close']
        for session in ['asia', 'london', 'ny1']:
            mid_col = f'{session}_mid'
            if mid_col in stats_aligned.columns:
                feature_df[f'feat_{session}_mid_dist'] = (stats_aligned[mid_col] - price_close) / price_close
        
        return feature_df
