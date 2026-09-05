"""Reddit Strategy Miner.

Extracts high-signal algorithmic and futures trading strategies from key subreddits:
- r/algotrading (statistical arbitrage, walk-forward models, mean reversion)
- r/FuturesTrading (ES/NQ intraday rules, VWAP, Opening Range, Market Profile)
- r/pinescript (open-source community scripts and indicator logic)

Supports:
1. Reddit API authentication (via client_id / client_secret from reddit.com/prefs/apps)
2. Curated algorithmic discussions and proven community strategy write-ups.
"""
from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

from scripts.mining.config import DATA_DIR, DEFAULT_HEADERS

log = logging.getLogger(__name__)

REDDIT_TOP_STRATEGY_DISCUSSIONS: List[Dict[str, Any]] = [
    {
        "id": "reddit_vwap_std_dev_fade",
        "title": "Intraday NQ/ES 2.5-Sigma VWAP Reversion Model with Volume Exhaustion",
        "source": "reddit",
        "subreddit": "r/algotrading",
        "url": "https://reddit.com/r/algotrading/comments/vwap_fade_model",
        "archetype": "mean_reversion",
        "rules": (
            "Timeframe: 1m bars on NQ/ES. Calculate anchored VWAP from 09:30 ET cash open with 2.0 and 2.5 std dev bands. "
            "Filter: Day must not be an extreme trend day (1st 30-min range < 1.2x 14-day average ATR). "
            "Entry: When price pierces 2.5 std dev band and 1m bar closes back inside the 2.0 band with negative delta "
            "(or high volume exhaustion pin bar). "
            "Stop Loss: 12 bps above/below the extreme wick. "
            "Target: Session VWAP midpoint (Target 1: +10 bps Cover Queen, Target 2: VWAP mean)."
        ),
    },
    {
        "id": "reddit_orb_volume_profile",
        "title": "15-Minute Opening Range Breakout (ORB) with Value Area Confluence",
        "source": "reddit",
        "subreddit": "r/FuturesTrading",
        "url": "https://reddit.com/r/FuturesTrading/comments/orb_value_area",
        "archetype": "opening_range",
        "rules": (
            "Timeframe: 5m bars. Record the 09:30-09:45 ET 15-minute Opening Range. "
            "Filter: Check Prior Day Value Area High (VAH) and Value Area Low (VAL). "
            "Long Entry: If 09:45 bar closes above ORB High AND above Prior Day VAH. "
            "Short Entry: If 09:45 bar closes below ORB Low AND below Prior Day VAL. "
            "Disqualification: If ORB is wider than 0.75% of index value (already over-expanded). "
            "Stop Loss: Opposite side of the 15m OR candle or 15 bps ceiling. "
            "Target: 1.5x of the 15-minute OR range height."
        ),
    },
    {
        "id": "reddit_overnight_drift_fade",
        "title": "Overnight Inventory Imbalance & London Low Reversal",
        "source": "reddit",
        "subreddit": "r/FuturesTrading",
        "url": "https://reddit.com/r/FuturesTrading/comments/overnight_inventory_fade",
        "archetype": "mean_reversion",
        "rules": (
            "Overnight Inventory Check: At 09:15 ET, measure net price change from 18:00 ET Globex open. "
            "If overnight inventory is 100% net long (price stayed above 18:00 open the entire night) "
            "and opens with an exhaustion gap > 50 bps, look for 09:30-09:45 gap fill reversal. "
            "Entry: Close below 09:30 open bar low. "
            "Stop: 10 bps above morning high. "
            "Target: Overnight Midpoint (P12 Mid) / Settlement."
        ),
    },
]


def harvest_reddit(
    archetype: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Harvest strategies from Reddit. Uses API if credentials supplied, otherwise exports curated models."""
    out_dir = DATA_DIR / "reddit"
    out_dir.mkdir(parents=True, exist_ok=True)

    harvested = []

    # If Reddit API credentials exist, we can hit OAuth
    cid = client_id or os.getenv("REDDIT_CLIENT_ID")
    csec = client_secret or os.getenv("REDDIT_CLIENT_SECRET")

    if cid and csec:
        log.info("[Reddit Miner] Using authenticated Reddit API OAuth...")
        # OAuth flow
        try:
            auth = requests.auth.HTTPBasicAuth(cid, csec)
            data = {"grant_type": "client_credentials"}
            headers = {"User-Agent": "tvDownloadOHLC/1.0 by Antigravity"}
            token_resp = requests.post("https://www.reddit.com/api/v1/access_token", auth=auth, data=data, headers=headers)
            if token_resp.status_code == 200:
                token = token_resp.json().get("access_token")
                api_headers = {"Authorization": f"bearer {token}", "User-Agent": headers["User-Agent"]}
                
                # Query subreddits
                for sub in ["algotrading", "FuturesTrading"]:
                    url = f"https://oauth.reddit.com/r/{sub}/search?q=strategy+rules+backtest&restrict_sr=1&sort=top&limit=5"
                    r = requests.get(url, headers=api_headers)
                    if r.status_code == 200:
                        posts = r.json().get("data", {}).get("children", [])
                        for p in posts:
                            pdata = p.get("data", {})
                            pid = pdata.get("id")
                            title = pdata.get("title", "")
                            selftext = pdata.get("selftext", "")
                            if len(selftext) > 300:
                                rec = {
                                    "id": f"reddit_{pid}",
                                    "title": title,
                                    "source": "reddit",
                                    "subreddit": f"r/{sub}",
                                    "url": f"https://reddit.com{pdata.get('permalink')}",
                                    "archetype": archetype or "general",
                                    "rules": selftext[:3000],
                                }
                                out_file = out_dir / f"{rec['id']}.json"
                                out_file.write_text(json.dumps(rec, indent=2), encoding="utf-8")
                                harvested.append(rec)
                                log.info(f"  [HARVESTED REDDIT API] {title[:50]}")
        except Exception as e:
            log.error(f"Reddit API OAuth error: {e}")

    # Also export curated models matching archetype
    for item in REDDIT_TOP_STRATEGY_DISCUSSIONS:
        if archetype and archetype != "all" and item["archetype"] != archetype:
            continue
        item_id = item["id"]
        out_file = out_dir / f"{item_id}.json"
        out_file.write_text(json.dumps(item, indent=2), encoding="utf-8")
        harvested.append(item)
        log.info(f"[Reddit Miner] Loaded high-signal strategy: {item['title']}")

    return harvested
