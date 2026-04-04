import pandas as pd
import numpy as np
from typing import Dict, Any, Callable

def KillZoneFilter(start_hour: int, start_min: int, end_hour: int, end_min: int) -> Callable:
    """
    Modular filter for ICT Kill Zones or specific session windows.
    Expects data in US/Eastern (institutional standard).
    """
    def filter_func(data: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
        # Extract time for the entire series
        times = data.index.time
        start = pd.Timestamp(f"2021-01-01 {start_hour:02}:{start_min:02}").time()
        end = pd.Timestamp(f"2021-01-01 {end_hour:02}:{end_min:02}").time()
        
        # Vectorized time check
        return pd.Series((times >= start) & (times <= end), index=data.index)
    
    return filter_func

def VolatilityRegimeFilter(max_regime: int = 2) -> Callable:
    """
    Filter signals based on the HMM/Volatility Regime (if present in data).
    Regime 0: Low, 1: Normal, 2: High/Crisis.
    """
    def filter_func(data: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
        if 'regime' not in data.columns:
            return pd.Series(True, index=data.index)
        return data['regime'] <= max_regime
    
    return filter_func

def NewsProximityFilter(min_seconds: int = 3600) -> Callable:
    """
    Filter signals based on proximity to high-impact economic news (if present).
    Default: 60 minutes.
    """
    def filter_func(data: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
        if 'sec_to_news' not in data.columns:
            return pd.Series(True, index=data.index)
        return data['sec_to_news'] > min_seconds
    
    return filter_func

def ADRFilter(max_adr_pct: float = 0.9) -> Callable:
    """
    Filter signals if the symbol has already moved more than X% of its ADR today.
    """
    def filter_func(data: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
        if 'adr_pct' not in data.columns:
            return pd.Series(True, index=data.index)
        return data['adr_pct'] <= max_adr_pct
    
    return filter_func
