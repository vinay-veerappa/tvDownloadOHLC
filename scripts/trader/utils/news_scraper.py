import logging
import re
from datetime import datetime, timezone
import urllib.request
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from typing import List, Dict, Any

try:
    import yfinance as yf
except ImportError:
    yf = None

logger = logging.getLogger(__name__)

# Macro-driver keywords with weights
HIGH_WEIGHT_KEYWORDS = {
    r"\bfomc\b": 2.0,
    r"\bfed\b": 2.0,
    r"\bpowell\b": 2.0,
    r"\bcpi\b": 2.0,
    r"\bpce\b": 2.0,
    r"\bnfp\b": 2.0,
    r"\bjobless claims\b": 2.0,
    r"\btreasury auction\b": 2.0,
    r"\binflation\b": 2.0,
    r"\binterest rates\b": 2.0,
}

LOW_WEIGHT_KEYWORDS = {
    r"\boil\b": 1.0,
    r"\bbrent\b": 1.0,
    r"\bstrike\b": 1.0,
    r"\biran\b": 1.0,
    r"\bmideast\b": 1.0,
    r"\bgeopolitical\b": 1.0,
    r"\bcrude\b": 1.0,
    r"\bgulf\b": 1.0,
    r"\bconflict\b": 1.0,
}

def clean_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    return " ".join(t.split())

def calculate_similarity(title1: str, title2: str) -> float:
    """Fuzzy matching ratio between two titles."""
    return SequenceMatcher(None, clean_title(title1), clean_title(title2)).ratio()

def score_headline(title: str, summary: str, pub_date: datetime) -> float:
    """Calculate the score based on classifier_score / hours_old."""
    text = (title + " " + (summary or "")).lower()
    classifier_score = 0.0

    for pattern, weight in HIGH_WEIGHT_KEYWORDS.items():
        if re.search(pattern, text):
            classifier_score += weight
    
    for pattern, weight in LOW_WEIGHT_KEYWORDS.items():
        if re.search(pattern, text):
            classifier_score += weight

    if classifier_score == 0.0:
        return 0.0

    now = datetime.now(timezone.utc)
    delta = now - pub_date
    hours_old = delta.total_seconds() / 3600.0
    # Guard against negative delta or division by zero, min hours_old = 0.1
    hours_old = max(hours_old, 0.1)

    return classifier_score / hours_old

def parse_rss_feed(url: str = "https://finance.yahoo.com/news/rss") -> List[Dict[str, Any]]:
    """Fetch headlines from Yahoo Finance News RSS."""
    headlines = []
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        for item in root.findall(".//item"):
            title = item.find("title")
            title_text = title.text if title is not None else ""
            
            link = item.find("link")
            link_text = link.text if link is not None else ""
            
            desc = item.find("description")
            desc_text = desc.text if desc is not None else ""
            
            pub_date = item.find("pubDate")
            pub_date_text = pub_date.text if pub_date is not None else ""
            
            if not title_text:
                continue
            
            # Parse RFC 822 date format (e.g. Fri, 10 Jul 2026 17:07:58 GMT)
            dt = None
            if pub_date_text:
                for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
                    try:
                        # Strip trailing timezone names like GMT/EST or parse timezone offset
                        clean_date = pub_date_text.strip()
                        dt = datetime.strptime(clean_date, fmt).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
            
            if dt is None:
                dt = datetime.now(timezone.utc)
                
            headlines.append({
                "title": title_text,
                "summary": desc_text,
                "link": link_text,
                "pub_date": dt,
                "source": "rss_yahoo"
            })
    except Exception as e:
        logger.warning(f"Failed to parse RSS feed {url}: {e}")
    return headlines

def parse_yfinance_news() -> List[Dict[str, Any]]:
    """Fetch news for NQ/ES proxies via yfinance news API."""
    headlines = []
    if yf is None:
        return headlines
        
    tickers = ["QQQ", "SPY", "BZ=F", "^TNX"]
    for t in tickers:
        try:
            ticker = yf.Ticker(t)
            news_items = ticker.news
            if not news_items:
                continue
                
            for item in news_items:
                content = item.get("content", {})
                title = content.get("title", "")
                summary = content.get("summary", "")
                pub_date_str = content.get("pubDate", "")
                link = content.get("canonicalUrl", {}).get("url", "")
                
                if not title:
                    continue
                
                # Parse ISO date format (e.g. 2026-07-10T17:07:58Z)
                dt = None
                if pub_date_str:
                    try:
                        dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                
                if dt is None:
                    dt = datetime.now(timezone.utc)
                    
                headlines.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "pub_date": dt,
                    "source": f"yf_{t}"
                })
        except Exception as e:
            logger.warning(f"Failed to fetch news for {t} from yfinance: {e}")
    return headlines

def get_macro_headlines(min_score: float = 1.0, max_headlines: int = 5) -> List[Dict[str, Any]]:
    """Aggregate, score, deduplicate, and rank headlines."""
    raw = parse_rss_feed() + parse_yfinance_news()
    if not raw:
        return []
        
    # Score each headline
    scored_items = []
    for item in raw:
        score = score_headline(item["title"], item["summary"], item["pub_date"])
        if score >= min_score:
            item["score"] = score
            scored_items.append(item)
            
    # Sort by score descending (high score first)
    scored_items.sort(key=lambda x: x["score"], reverse=True)
    
    # Deduplicate based on title similarity
    deduped: List[Dict[str, Any]] = []
    for item in scored_items:
        is_duplicate = False
        for existing in deduped:
            if calculate_similarity(item["title"], existing["title"]) >= 0.85:
                is_duplicate = True
                # If newer, replace the older one
                if item["pub_date"] > existing["pub_date"]:
                    # Swap the item
                    existing.update(item)
                break
        if not is_duplicate:
            deduped.append(item)
            
    # Sort again after updates/deduping
    deduped.sort(key=lambda x: x["score"], reverse=True)
    
    return deduped[:max_headlines]
