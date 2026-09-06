"""
funnel.py
=========
Stage 1 Top-of-Funnel Universe Screener wrapper using finvizfinance.
Applies initial liquidity, price, performance, and optionable filters to reduce
8,000+ US equities down to top candidate pools.
Includes rate-limiting delays and browser User-Agent headers.
"""
import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

log = logging.getLogger("screener_funnel")

REPO_ROOT = Path(__file__).resolve().parents[3]
FUNNEL_CACHE_DIR = REPO_ROOT / "data" / "universe"


def _get_funnel_cache(strat_key: str, max_age_secs: float = 14400) -> Optional[List[Dict[str, Any]]]:
    cache_file = FUNNEL_CACHE_DIR / f"funnel_{strat_key}.json"
    if cache_file.exists():
        try:
            mtime = cache_file.stat().st_mtime
            if (datetime.now().timestamp() - mtime) < max_age_secs:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    log.info(f"Loaded {len(data)} candidates for '{strat_key}' from local funnel cache.")
                    return data
        except Exception:
            pass
    return None


def _save_funnel_cache(strat_key: str, candidates: List[Dict[str, Any]]):
    try:
        FUNNEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = FUNNEL_CACHE_DIR / f"funnel_{strat_key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(candidates, f, indent=2)
    except Exception:
        pass

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

STRATEGY_FUNNEL_FILTERS = {
    "qullamaggie_hft": {
        'Industry': 'Stocks only (ex-Funds)',
        'Average Volume': 'Over 500K',
        'Price': 'Over $7',
        'Performance': 'Half +50%',
        '20-Day Simple Moving Average': 'Price above SMA20',
    },
    "stockbee_ep": {
        'Industry': 'Stocks only (ex-Funds)',
        'Average Volume': 'Over 500K',
        'Price': 'Over $5',
        'Relative Volume': 'Over 1.5',
    },
    "minervini_trend": {
        'Industry': 'Stocks only (ex-Funds)',
        'Average Volume': 'Over 500K',
        'Price': 'Over $10',
        '200-Day Simple Moving Average': 'Price above SMA200',
        '50-Day Simple Moving Average': 'Price above SMA50',
        '52-Week High/Low': '0-10% below High',
    },
    "parabolic_short": {
        'Industry': 'Stocks only (ex-Funds)',
        'Average Volume': 'Over 500K',
        'Price': 'Over $7',
        'Performance': 'Month +30%',
        'RSI (14)': 'Overbought (70)',
    },
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


def _get_fallback_candidates(limit: int = 100) -> List[Dict[str, Any]]:
    candidates = []
    for item in DEFAULT_FALLBACK_UNIVERSE[:limit]:
        t = item["ticker"]
        candidates.append({
            "ticker": t,
            "company": item.get("company", f"{t} Corp"),
            "sector": item.get("sector", "Technology"),
            "industry": item.get("industry", "General"),
            "marketCap": 10_000_000_000.0,
            "price": 100.0,
            "volume": 2_000_000.0
        })
    return candidates


def fetch_finviz_candidates(
    custom_filters: Optional[Dict[str, str]] = None,
    strategy_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch universe candidate stocks from Finviz.
    Returns list of dicts: [{ticker, company, sector, industry, marketCap, price, volume, float}]
    """
    strat_key = strategy_id or "default"
    if not custom_filters:
        cached = _get_funnel_cache(strat_key)
        if cached:
            return cached[:limit]

    if custom_filters:
        filters = custom_filters
    elif strategy_id and strategy_id in STRATEGY_FUNNEL_FILTERS:
        filters = STRATEGY_FUNNEL_FILTERS[strategy_id]
        log.info(f"Using strategy-specific Finviz funnel for '{strategy_id}'.")
    else:
        filters = DEFAULT_FILTERS
    
    if Overview is None:
        log.warning("finvizfinance package not installed. Returning default fallback universe.")
        return _get_fallback_candidates(limit)
        
    try:
        foverview = Overview()
        foverview.set_filter(filters_dict=filters)
        df = foverview.screener_view()
        
        if df is None or df.empty:
            log.info("Finviz returned no candidates for the given filters.")
            return _get_fallback_candidates(limit)
            
        # Strategy-aware sorting
        if strategy_id in ("stockbee_ep", "parabolic_short") and "Change" in df.columns:
            df = df.sort_values(by="Change", ascending=False)
        elif strategy_id == "qullamaggie_hft" and "Volume" in df.columns:
            df = df.sort_values(by="Volume", ascending=False)
        elif "Market Cap" in df.columns:
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
        if results:
            _save_funnel_cache(strat_key, results)
        return results
    except Exception as e:
        log.error(f"Finviz funnel query failed: {e}. Returning fallback universe.")
        return _get_fallback_candidates(limit)

