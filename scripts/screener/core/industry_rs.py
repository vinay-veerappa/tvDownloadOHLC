"""
industry_rs.py
==============
Stage 1 filter component to compute the relative strength of Finviz industries.
Returns a dictionary mapping Industry Name to its RS percentile rank (0-100).
Stockbee strategies rely heavily on buying stocks in the Top 15% (RS > 85).
"""
import logging
import pandas as pd
from typing import Dict

log = logging.getLogger("screener_industry_rs")

try:
    from finvizfinance.group.performance import Performance
except ImportError:
    Performance = None

def calculate_industry_rs() -> Dict[str, float]:
    """
    Fetches industry group performance from Finviz and calculates a Relative Strength (RS) Rank.
    Returns a dictionary of { "Industry Name": 95.5 } where 95.5 is the percentile (0-100).
    """
    if Performance is None:
        log.warning("finvizfinance not installed. Returning empty industry RS map.")
        return {}
        
    try:
        perf = Performance()
        df = perf.screener_view(group='Industry')
        
        if df.empty or "Perf Half" not in df.columns:
            # Fallback to Perf Month if Half Year isn't available for some reason
            perf_col = "Perf Month" if "Perf Month" in df.columns else None
        else:
            perf_col = "Perf Half"
            
        if not perf_col:
            log.warning("Could not find performance columns in Finviz group data.")
            return {}
            
        # Parse percentage strings to floats (e.g. "15.4%" -> 15.4)
        def parse_pct(val):
            if isinstance(val, str):
                return float(val.replace('%', ''))
            return float(val) if pd.notnull(val) else 0.0
            
        df['score'] = df[perf_col].apply(parse_pct)
        
        # Calculate percentiles (0 to 1) -> multiply by 100
        df['rs_rank'] = df['score'].rank(pct=True) * 100.0
        
        # Create dict { "Software - Infrastructure": 95.5, ... }
        rankings = dict(zip(df['Name'], df['rs_rank']))
        
        log.info(f"Calculated RS rankings for {len(rankings)} industries.")
        return rankings
        
    except Exception as e:
        log.error(f"Failed to calculate industry RS: {e}")
        return {}
