import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional

try:
    import yfinance as yf
except ImportError:
    yf = None

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

# Top 15 QQQ holdings by index weight (as of mid-2026 approximation)
QQQ_WEIGHTS = {
    "MSFT": 0.088,
    "AAPL": 0.082,
    "NVDA": 0.076,
    "AMZN": 0.053,
    "META": 0.048,
    "GOOGL": 0.035,
    "GOOG": 0.034,
    "TSLA": 0.029,
    "AVGO": 0.024,
    "COST": 0.021,
    "NFLX": 0.020,
    "AMD": 0.018,
    "PEP": 0.017,
    "TMUS": 0.016,
    "CSCO": 0.015,
}

def get_previous_trading_day(d: date) -> date:
    """Find the previous weekday."""
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5: # Saturday/Sunday
        prev -= timedelta(days=1)
    return prev

async def fetch_earnings_events(
    target_date: date,
    db_path: str,
    broker_service: Any
) -> List[Dict[str, Any]]:
    """Fetch and enrich earnings events for a target date."""
    events = []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch all earnings calendar entries
    query = "SELECT ticker, earningsDate, beforeMarket, company, marketCap FROM EarningsCalendar"
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    prev_date = get_previous_trading_day(target_date)
    
    prev_iso = prev_date.isoformat()
    target_iso = target_date.isoformat()

    # Process and filter events
    for ticker, dt_val, before_market, company, market_cap in rows:
        ticker = ticker.upper().strip()
        
        # Parse DB date
        dt_str = ""
        if isinstance(dt_val, (int, float)):
            dt_str = datetime.fromtimestamp(dt_val / 1000, tz=timezone.utc).date().isoformat()
        elif isinstance(dt_val, str):
            dt_str = dt_val[:10]

        # Determine session timing
        session_timing = None
        bmo = bool(before_market)
        
        if dt_str == prev_iso and not bmo:
            session_timing = "AMC_YESTERDAY"
        elif dt_str == target_iso:
            if bmo:
                session_timing = "BMO_TODAY"
            else:
                session_timing = "AMC_TODAY"
                
        if not session_timing:
            continue

        # Top 15 QQQ holdings check
        index_critical = ticker in QQQ_WEIGHTS
        index_weight = QQQ_WEIGHTS.get(ticker, 0.0)

        events.append({
            "ticker": ticker,
            "company": company or "Unknown Company",
            "market_cap": market_cap or 0.0,
            "session_timing": session_timing,
            "index_critical": index_critical,
            "index_weight": index_weight,
            "timing_label": "BMO" if bmo else "AMC"
        })

    # Resolve pre-market price changes and Expected Move checks
    enriched_events = []
    for ev in events:
        ticker = ev["ticker"]
        # Only AMC_YESTERDAY and BMO_TODAY act as morning catalysts
        if ev["session_timing"] not in ("AMC_YESTERDAY", "BMO_TODAY"):
            enriched_events.append(ev)
            continue

        # Fetch straddle expected move and basis price from DB first to validate quotes
        expected_move = None
        basis_price = None
        beyond_em = False
        premkt_move_pct = 0.0

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT straddle, price, adjEm FROM ExpectedMove WHERE ticker = ? ORDER BY calculationDate DESC LIMIT 1",
            (ticker,)
        )
        em_row = cursor.fetchone()
        conn.close()

        if em_row:
            straddle, price, adj_em = em_row
            expected_move = adj_em if adj_em and adj_em > 0 else (straddle * 0.85 if straddle else 0.0)
            basis_price = price

        # Fetch current price from Schwab API with yfinance fallback
        last_price = None
        quote_source = None
        
        if broker_service:
            try:
                quote = await broker_service.get_stock_quote(ticker)
                if quote and quote.get("last") is not None:
                    candidate_price = quote["last"]
                    # Sanity check: discard if price deviates by > 50% from basis (weekend/stale Schwab quote bug)
                    if basis_price and basis_price > 0:
                        if abs(candidate_price / basis_price - 1.0) < 0.5:
                            last_price = candidate_price
                            quote_source = "schwab"
                    elif candidate_price > 1.0:
                        last_price = candidate_price
                        quote_source = "schwab"
            except Exception as e:
                logger.warning(f"Schwab quote failed for {ticker}: {e}")

        if last_price is None and yf is not None:
            try:
                t_obj = yf.Ticker(ticker)
                last_price = t_obj.fast_info.last_price
                quote_source = "yfinance_fallback"
            except Exception as e:
                logger.warning(f"yfinance fallback quote failed for {ticker}: {e}")

        if last_price is not None and basis_price and basis_price > 0:
            premkt_move_pct = (last_price / basis_price) - 1
            premkt_move_pts = abs(last_price - basis_price)
            if expected_move and expected_move > 0:
                beyond_em = premkt_move_pts > expected_move

        ev.update({
            "last_price": last_price,
            "quote_source": quote_source,
            "expected_move": expected_move,
            "basis_price": basis_price,
            "premkt_move_pct": premkt_move_pct,
            "beyond_em": beyond_em
        })
        enriched_events.append(ev)

    # Sort primarily by index_critical (True first) then by index_weight desc, then market_cap desc
    enriched_events.sort(key=lambda x: (x["index_critical"], x["index_weight"], x["market_cap"]), reverse=True)
    return enriched_events
