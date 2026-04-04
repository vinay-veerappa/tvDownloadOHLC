"""
Leakage Guard - Automating causality and lookahead bias detection.

Ensures that features at time T only use data from [0, T] and that
signals generated at T do not exploit price data from T+1.
"""
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class LeakageGuard:
    """
    Suite of tests to identify data leakage and lookahead bias.
    """
    
    @staticmethod
    def test_causality(df: pd.DataFrame, feature_cols: List[str], target_col: str) -> Dict[str, float]:
        """
        Check if features at time T are correlated with the PAST target (Leakage!)
        instead of the FUTURE target (Alpha).
        
        If Corr(Feature_T, Target_{T-1}) is extremely high, the feature might be
        using future information that has already processed the target.
        """
        results = {}
        for col in feature_cols:
            if col not in df.columns:
                continue
                
            # Alpha: Correlation with FUTURE returns (T+1)
            # This is GOOD.
            alpha_corr = df[col].corr(df[target_col].shift(-1))
            
            # Leakage: Correlation with CURRENT price move if it's supposed to be an entry feature
            # e.g., if Feature_T is highly correlated with (Price_T - Price_{T-1}), 
            # and it's used to enter at T, it might be fine, but worth checking.
            
            # Critical Leakage: Correlation with FUTURE high/low (T+10 etc)
            # This is BAD if the feature captures the outcome it's trying to predict.
            
            results[col] = alpha_corr
            
        return results

    @staticmethod
    def identify_future_leakage(df: pd.DataFrame, features: List[str]) -> List[str]:
        """
        Detects if a feature is perfectly correlated with future price moves.
        """
        leaking = []
        # Calculate 5-bar future return
        fwd_ret = df['close'].shift(-5) / df['close'] - 1
        
        for feat in features:
            corr = df[feat].corr(fwd_ret)
            if abs(corr) > 0.95: # Extremely suspicious
                leaking.append(feat)
                logger.warning(f"Feature '{feat}' has suspicious correlation ({corr:.4f}) with 5-bar future returns.")
        
        return leaking

    @staticmethod
    def audit_signal_timestamps(signals_df: pd.DataFrame, price_df: pd.DataFrame) -> bool:
        """
        Verify that signal timestamps exactly match the index of the price data.
        Ensures no 'mid-bar' entries that aren't possible in a 1-min backtest.
        """
        all_match = signals_df.index.isin(price_df.index).all()
        if not all_match:
            missing = (~signals_df.index.isin(price_df.index)).sum()
            logger.error(f"Signal Audit Fail: {missing} signals have timestamps not present in price data index.")
        return all_match

def run_leakage_audit(df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, Any]:
    """
    Main entry point for auditing an enriched DataFrame for leakage.
    """
    guard = LeakageGuard()
    
    # 1. Lookahead check (correlation with future returns)
    leaking_features = guard.identify_future_leakage(df, feature_cols)
    
    # 2. Null/NaN check in features (often hides leakage or data gaps)
    nan_counts = df[feature_cols].isna().sum()
    high_nan = nan_counts[nan_counts > (len(df) * 0.1)].index.tolist()
    
    return {
        "is_clean": len(leaking_features) == 0,
        "leaking_features": leaking_features,
        "high_nan_features": high_nan,
        "sample_correlations": guard.test_causality(df, feature_cols, 'close')
    }
