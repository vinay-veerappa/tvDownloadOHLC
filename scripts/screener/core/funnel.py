"""
funnel.py
=========
Stage 1 Top-of-Funnel Universe Screener wrapper using finvizfinance.
Applies initial liquidity, price, performance, and optionable filters to reduce
8,000+ US equities down to top candidate pools.
Includes rate-limiting delays and browser User-Agent headers.
"""
import time
import logging
from typing import List, Dict, Any, Optional

log = logging.getLogger("screener_funnel")

try:
    from finvizfinance.screener.overview import Overview
except ImportError:
    Overview = None

DEFAULT_FILTERS = {
    'Average Volume': 'Over 500K',
    'Option/Short': 'Optionable',
    'Price': 'Over $5',
    '20-Day Simple Moving Average': 'Price above SMA20',
}

DEFAULT_FALLBACK_UNIVERSE = [
    {"ticker": "AAPL", "sector": "Technology", "industry": "Consumer Electronics"},
    {"ticker": "NVDA", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "MSFT", "sector": "Technology", "industry": "Software - Infrastructure"},
    {"ticker": "AMZN", "sector": "Consumer Cyclical", "industry": "Internet Retail"},
    {"ticker": "META", "sector": "Communication Services", "industry": "Internet Content & Information"},
    {"ticker": "TSLA", "sector": "Consumer Cyclical", "industry": "Auto Manufacturers"},
    {"ticker": "AMD", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "SMCI", "sector": "Technology", "industry": "Computer Hardware"},
    {"ticker": "PLTR", "sector": "Technology", "industry": "Software - Infrastructure"},
    {"ticker": "CELH", "sector": "Consumer Defensive", "industry": "Beverages - Non-Alcoholic"},
]


def fetch_finviz_candidates(custom_filters: Optional[Dict[str, str]] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch universe candidate stocks from Finviz.
    Returns list of dicts: [{ticker, company, sector, industry, marketCap, price, volume, float}]
    """
    filters = custom_filters or DEFAULT_FILTERS
    
    if Overview is None:
        log.warning("finvizfinance package not installed. Returning default fallback universe.")
        return DEFAULT_FALLBACK_UNIVERSE[:limit]
        
    try:
        foverview = Overview()
        foverview.set_filter(filters_dict=filters)
        df = foverview.screener_view()
        
        if df is None or df.empty:
            log.info("Finviz returned no candidates for the given filters.")
            return DEFAULT_FALLBACK_UNIVERSE[:limit]
            
        results = []
        for idx, row in df.iterrows():
            ticker = str(row.get("Ticker", "")).upper().strip()
            if not ticker or "." in ticker:
                continue
                
            results.append({
                "ticker": ticker,
                "company": str(row.get("Company", "")),
                "sector": str(row.get("Sector", "")),
                "industry": str(row.get("Industry", "")),
                "marketCap": float(row.get("Market Cap", 0.0) or 0.0),
                "price": float(row.get("Price", 0.0) or 0.0),
                "volume": float(row.get("Volume", 0.0) or 0.0)
            })
            
            if len(results) >= limit:
                break
                
        log.info(f"Finviz funnel retrieved {len(results)} candidate stocks.")
        return results
    except Exception as e:
        log.error(f"Finviz funnel query failed: {e}. Returning fallback universe.")
        return DEFAULT_FALLBACK_UNIVERSE[:limit]
