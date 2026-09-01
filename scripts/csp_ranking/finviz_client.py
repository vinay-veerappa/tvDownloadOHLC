"""
Finviz Data Client
Fast snapshot scraper for fundamentals, earnings dates, quarterly growth, and SMA distances.
Includes disk-based caching to prevent redundant requests.
"""

import re
import json
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import requests
import bs4

CACHE_DIR = Path("data/csp_ranking/cache")


class FinvizTickerProfile:
    def __init__(self, ticker: str, raw_data: Dict[str, Any]):
        self.ticker: str = ticker.upper()
        self.raw_data: Dict[str, Any] = raw_data
        
        self.price: float = self._parse_float(raw_data.get("Price"))
        self.pe: Optional[float] = self._parse_opt_float(raw_data.get("P/E"))
        self.eps_qq: float = self._parse_pct(raw_data.get("EPS Q/Q"))
        self.sales_qq: float = self._parse_pct(raw_data.get("Sales Q/Q"))
        self.eps_next_y: float = self._parse_pct(raw_data.get("EPS next Y"))
        self.eps_this_y: float = self._parse_pct(raw_data.get("EPS this Y"))
        
        self.sma50_pct: float = self._parse_pct(raw_data.get("SMA50"))
        self.sma200_pct: float = self._parse_pct(raw_data.get("SMA200"))
        self.sma20_pct: float = self._parse_pct(raw_data.get("SMA20"))
        self.rsi: float = self._parse_float(raw_data.get("RSI (14)"))
        self.rel_volume: float = self._parse_float(raw_data.get("Rel Volume"))
        self.short_float: float = self._parse_pct(raw_data.get("Short Float"))
        self.market_cap: str = str(raw_data.get("Market Cap", ""))
        self.sector: str = str(raw_data.get("Sector", ""))
        self.industry: str = str(raw_data.get("Industry", ""))
        
        self.earnings_str: str = str(raw_data.get("Earnings", "")).strip()
        self.earnings_date: Optional[date] = self._parse_earnings_date(self.earnings_str)

    def _parse_float(self, val: Any) -> float:
        if val is None:
            return 0.0
        s = str(val).strip().replace(",", "")
        if s == "" or s == "-" or s.lower() == "none":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _parse_opt_float(self, val: Any) -> Optional[float]:
        if val is None:
            return None
        s = str(val).strip().replace(",", "")
        if s == "" or s == "-" or s.lower() == "none":
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def _parse_pct(self, val: Any) -> float:
        if val is None:
            return 0.0
        s = str(val).strip().replace("%", "").replace("+", "").replace(",", "")
        if s == "" or s == "-" or s.lower() == "none":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _parse_earnings_date(self, earn_str: str) -> Optional[date]:
        if not earn_str or earn_str == "-" or earn_str.lower() == "none":
            return None
        
        # Clean string, e.g. "Sep 01 AMC", "Sep 01 BMO", "Sep 01/a", "Oct 15"
        clean = re.sub(r"\s+(AMC|BMO|amc|bmo|/a|/b)$", "", earn_str).strip()
        clean = clean.replace("/a", "").replace("/b", "").strip()
        
        today = date.today()
        # Try parsing e.g. "Sep 01" or "Sep 1" or "09/01/2026"
        for fmt in ("%b %d", "%B %d", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(clean, fmt)
                if fmt in ("%b %d", "%B %d"):
                    # Determine appropriate year
                    year = today.year
                    target = date(year, dt.month, dt.day)
                    # If target is more than 60 days in past, it's likely next year
                    if (today - target).days > 60:
                        target = date(year + 1, dt.month, dt.day)
                    return target
                return dt.date()
            except Exception:
                continue
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "price": self.price,
            "pe": self.pe,
            "eps_qq": self.eps_qq,
            "sales_qq": self.sales_qq,
            "sma50_pct": self.sma50_pct,
            "sma200_pct": self.sma200_pct,
            "sma20_pct": self.sma20_pct,
            "rsi": self.rsi,
            "rel_volume": self.rel_volume,
            "short_float": self.short_float,
            "earnings_str": self.earnings_str,
            "earnings_date": self.earnings_date.isoformat() if self.earnings_date else "",
            "sector": self.sector,
            "industry": self.industry,
        }


class FinvizClient:
    def __init__(self, cache_ttl_seconds: int = 14400): # 4 hours cache
        self.cache_ttl = cache_ttl_seconds
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def get_ticker_profile(self, ticker: str, force_refresh: bool = False) -> Optional[FinvizTickerProfile]:
        ticker = ticker.upper().strip()
        cache_file = CACHE_DIR / f"{ticker}_finviz.json"
        
        # Check cache
        if not force_refresh and cache_file.exists():
            try:
                mtime = cache_file.stat().st_mtime
                if time.time() - mtime < self.cache_ttl:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return FinvizTickerProfile(ticker, data)
            except Exception:
                pass

        # Fetch from Finviz
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None

            soup = bs4.BeautifulSoup(resp.text, "html.parser")
            tables = soup.find_all("table", class_="snapshot-table2")
            data = {}
            for t in tables:
                rows = t.find_all("tr")
                for row in rows:
                    tds = row.find_all("td")
                    for i in range(0, len(tds), 2):
                        if i + 1 < len(tds):
                            k = tds[i].text.strip()
                            v = tds[i + 1].text.strip()
                            data[k] = v

            if not data:
                return None

            # Cache to disk
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            return FinvizTickerProfile(ticker, data)
        except Exception as e:
            print(f"[FinvizClient] Error fetching {ticker}: {e}")
            return None
