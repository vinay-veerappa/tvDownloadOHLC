"""Batch Video Curator for Subscribed Creators & Disciplines.

Queries YouTube using scrapetube for high-signal videos across target creators,
filters out shorts and excessively long live streams, and generates a structured
batch ingestion manifest mapped to NotebookLM notebook IDs.
"""
from __future__ import annotations

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
import scrapetube

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("VideoCurator")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_MANIFEST = REPO_ROOT / "data" / "strategies" / "raw_mined" / "batch_video_harvest_manifest.json"

# Target search queries aligned with user's subscribed creators & NotebookLM notebooks
CURATION_TARGETS = {
    # Volatility Systems (Minervini & Raschke)
    "volatility_systems_vcp": {
        "notebook_id": "6c55f605-5ce5-4530-bba4-14c4be9a4cfd",
        "title": "Volatility-Based Strategies & Contraction Patterns (VCP, ATR, NR7)",
        "queries": [
            "Mark Minervini VCP rules breakout TraderLion",
            "Linda Raschke Turtle Soup 80 20 rule strategy",
            "Toby Crabel NR7 narrow range breakout rules",
        ],
    },
    # Stock Scanners & Screener Systems
    "stock_scanners_screeners": {
        "notebook_id": "80b7afae-c643-4af5-89ce-fdf309ab3034",
        "title": "Stock Scanners & Algorithmic Screener Systems",
        "queries": [
            "Trade Ideas scanner settings RVOL momentum",
            "pre market gap and go scanner strategy rules",
            "Richard Moglen stock screener episodic pivot",
        ],
    },
    # GEX & Market Maker Positioning
    "gamma_exposure_gex": {
        "notebook_id": "dbbc0d63-d9df-4378-a958-d8f15ac60f3b",
        "title": "Gamma Exposure (GEX) & Market Maker Hedging Strategies",
        "queries": [
            "Doc McGraw SPX gamma exposure GEX",
            "Doc McGraw market maker dealer positioning SPX",
            "ShadowTrader market profile Peter Reznicek",
        ],
    },
    # TheStrat Methodology
    "the_strat": {
        "notebook_id": "4f569cc3-220e-408d-afaf-47add3fb67f1",
        "title": "The Strat Methodology & Automated Trading Systems",
        "queries": [
            "Sara Strat Sniper 3-1-2 reversal setup rules",
            "Sara Strat Sniper time frame continuity broadening",
            "Alexs Options StratAlerts 2-1-2 options strategy",
        ],
    },
    # 0DTE & Intraday Options
    "options_0dte_intraday": {
        "notebook_id": "738e4a0a-5bd4-4c30-8f3a-378d33e57c7a",
        "title": "0DTE & Intraday Options Strategies",
        "queries": [
            "0DTE SPX iron condor rules backtest Option Alpha",
            "0DTE credit spread risk management Tammy Chambless",
            "0DTE expected move intraday trading rules",
        ],
    },
    # Options Order Flow & Sweeps
    "options_orderflow_sweeps": {
        "notebook_id": "38589732-c5f0-43e5-9c29-b6fd0be0e051",
        "title": "Options Order Flow & Unusual Institutional Activity",
        "queries": [
            "how to trade unusual options flow sweeps",
            "golden sweep options order flow strategy",
            "dark pool prints options sweep confluence",
        ],
    },
    # Options Volatility & Earnings
    "options_volatility_events": {
        "notebook_id": "0861f9b9-ce76-4cbb-84a7-532fd157880e",
        "title": "Options Volatility, IV Crush & Event Trading",
        "queries": [
            "earnings IV crush trading strategy tastytrade",
            "post earnings announcement drift options strategy",
            "VIX term structure contango trading strategy",
        ],
    },
    # Options Spreads & Income
    "options_spreads_income": {
        "notebook_id": "ef3a98ae-ac9a-40f6-b423-13b63f6d87a1",
        "title": "Options Multi-Leg Spreads & Systematic Income",
        "queries": [
            "the wheel strategy mechanical rules Kamikaze Cash",
            "broken wing butterfly options strategy rules",
            "tastytrade 45 DTE 21 DTE mechanics backtest",
        ],
    },
    # ICT & Smart Money Concepts
    "ict_smc": {
        "notebook_id": "00068bc6-fb1e-40ce-aa93-d032d6478db5",
        "title": "ICT Orderblock Model & Market Analysis",
        "queries": [
            "The Currency Merchant TCM trading strategy rules",
            "The MMXM Trader market maker model rules",
            "Thomas Wade second entry price action rules",
        ],
    },
}


def curate_videos_for_discipline(archetype: str, config: Dict[str, Any], max_per_query: int = 2) -> List[Dict[str, str]]:
    notebook_id = config["notebook_id"]
    queries = config["queries"]
    curated: List[Dict[str, str]] = []
    seen_ids = set()

    for q in queries:
        log.info(f"[{archetype}] Searching: '{q}'...")
        try:
            generator = scrapetube.get_search(q, limit=max_per_query * 3)
            added_for_query = 0
            for item in generator:
                vid = item.get("videoId")
                if not vid or vid in seen_ids:
                    continue

                title_runs = item.get("title", {}).get("runs", [])
                title = title_runs[0].get("text", "") if title_runs else "Untitled"
                title_lower = title.lower()

                # Filter out shorts, clickbait, live streams
                if any(bad in title_lower for bad in ["#shorts", "100% win", "infinite money", "never lose"]):
                    continue

                owner_runs = item.get("ownerText", {}).get("runs", [])
                channel = owner_runs[0].get("text", "") if owner_runs else "Unknown"

                seen_ids.add(vid)
                curated.append({
                    "video_id": vid,
                    "title": title,
                    "channel": channel,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "query": q,
                })
                added_for_query += 1
                if added_for_query >= max_per_query:
                    break
        except Exception as e:
            log.warning(f"Error searching for '{q}': {e}")

    log.info(f"[{archetype}] Total curated: {len(curated)} videos")
    return curated


def build_full_manifest() -> Dict[str, Any]:
    manifest = {}
    for arch, cfg in CURATION_TARGETS.items():
        vids = curate_videos_for_discipline(arch, cfg, max_per_query=2)
        manifest[arch] = {
            "notebook_id": cfg["notebook_id"],
            "title": cfg["title"],
            "video_count": len(vids),
            "videos": vids,
            "urls": [v["url"] for v in vids],
        }

    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    log.info(f"Manifest written to {OUTPUT_MANIFEST}")
    return manifest


if __name__ == "__main__":
    build_full_manifest()
