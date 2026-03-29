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
        
        feature_df = pd.DataFrame(index=stats.index)
        
        # 1. Map session box statuses
        for session in ['asia', 'london', 'ny1', 'ny2']:
            col = f'{session}box_status'
            feature_df[f'feat_{session}_status'] = stats[col].map(status_map).fillna(0)
            
            # 2. Add 'broken' status as binary
            feature_df[f'feat_{session}_broken'] = stats[f'{session}box_broken'].astype(int)
            
        # 3. Add ALN Pattern as a feature (Categorical or One-Hot could be used later)
        # For now, just pass through essential context
        feature_df['feat_aln_raw'] = stats['aln']
        
        # 4. Stationarity: Mid-points are normalized to % distance from current price
        # This keeps the feature stationary for ML models.
        for session in ['asia', 'london', 'ny1']:
            mid_col = f'{session}box_mid'
            if mid_col in stats.columns:
                feature_df[f'feat_{session}_mid_dist'] = (stats[mid_col] - stats['close']) / stats['close']
        
        return feature_df
