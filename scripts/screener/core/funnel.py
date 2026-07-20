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
    'Industry': 'Stocks only (ex-Funds)',
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
    {"ticker": "GOOGL", "sector": "Communication Services", "industry": "Internet Content & Information"},
    {"ticker": "AVGO", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "AMD", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "PLTR", "sector": "Technology", "industry": "Software - Infrastructure"},
    {"ticker": "SMCI", "sector": "Technology", "industry": "Computer Hardware"},
    {"ticker": "LLY", "sector": "Healthcare", "industry": "Drug Manufacturers - General"},
    {"ticker": "COST", "sector": "Consumer Defensive", "industry": "Discount Stores"},
    {"ticker": "NFLX", "sector": "Communication Services", "industry": "Entertainment"},
    {"ticker": "CRM", "sector": "Technology", "industry": "Software - Application"},
    {"ticker": "ORCL", "sector": "Technology", "industry": "Software - Infrastructure"},
    {"ticker": "ARM", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "APP", "sector": "Technology", "industry": "Software - Application"},
    {"ticker": "VRT", "sector": "Industrials", "industry": "Electrical Equipment & Parts"},
    {"ticker": "CEG", "sector": "Utilities", "industry": "Utilities - Renewable"},
    {"ticker": "MSTR", "sector": "Technology", "industry": "Software - Application"},
    {"ticker": "COIN", "sector": "Financial", "industry": "Financial Data & Stock Exchanges"},
    {"ticker": "HOOD", "sector": "Financial", "industry": "Financial Data & Stock Exchanges"},
    {"ticker": "CRWD", "sector": "Technology", "industry": "Software - Infrastructure"},
    {"ticker": "PANW", "sector": "Technology", "industry": "Software - Infrastructure"},
    {"ticker": "ANET", "sector": "Technology", "industry": "Computer Hardware"},
    {"ticker": "MU", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "QCOM", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "AMAT", "sector": "Technology", "industry": "Semiconductor Equipment & Materials"},
    {"ticker": "LRCX", "sector": "Technology", "industry": "Semiconductor Equipment & Materials"},
    {"ticker": "KLAC", "sector": "Technology", "industry": "Semiconductor Equipment & Materials"},
    {"ticker": "NOW", "sector": "Technology", "industry": "Software - Application"},
    {"ticker": "INTU", "sector": "Technology", "industry": "Software - Application"},
    {"ticker": "ISRG", "sector": "Healthcare", "industry": "Medical Instruments & Supplies"},
    {"ticker": "JPM", "sector": "Financial", "industry": "Banks - Diversified"},
    {"ticker": "V", "sector": "Financial", "industry": "Credit Services"},
    {"ticker": "MA", "sector": "Financial", "industry": "Credit Services"},
    {"ticker": "UNH", "sector": "Healthcare", "industry": "Healthcare Plans"},
    {"ticker": "CAT", "sector": "Industrials", "industry": "Farm & Heavy Construction Machinery"},
    {"ticker": "GE", "sector": "Industrials", "industry": "Aerospace & Defense"},
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
            
        # Sort by Market Cap descending to get the most liquid/real companies first instead of alphabetical junk
        if "Market Cap" in df.columns:
            df = df.sort_values(by="Market Cap", ascending=False)
        elif "Volume" in df.columns:
            df = df.sort_values(by="Volume", ascending=False)
            
        # Check if finvizfinance has the "duplicated first letter" bug (e.g. MMSFT instead of MSFT)
        bug_active = False
        if not df.empty and "Ticker" in df.columns:
            doubled_count = sum(1 for t in df["Ticker"].astype(str) if len(t) > 1 and t[0] == t[1])
            if len(df) > 0 and doubled_count / len(df) > 0.5:
                bug_active = True

        results = []
        for idx, row in df.iterrows():
            ticker = str(row.get("Ticker", "")).upper().strip()
            if not ticker or "." in ticker:
                continue
                
            if bug_active and len(ticker) > 1:
                ticker = ticker[1:]
                
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
