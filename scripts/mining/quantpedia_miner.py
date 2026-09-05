"""Autonomous Quantpedia Strategy Miner.
Crawls Quantpedia screener, extracts quantitative research profiles,
and parses simple trading strategy rules and academic papers.
"""
from __future__ import annotations

import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup

from scripts.mining.config import DATA_DIR, ARCHETYPE_QUERIES, DEFAULT_HEADERS

log = logging.getLogger(__name__)

SCREENER_URL = "https://quantpedia.com/screener/"
BASE_URL = "https://quantpedia.com"


def fetch_strategy_detail(url: str) -> Optional[Dict[str, Any]]:
    """Fetch individual Quantpedia strategy rules and metadata."""
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.replace(" - Quantpedia", "").strip() if soup.title else "Unknown"

        # Extract 'Simple trading strategy' section
        rules_text = ""
        rule_heading = soup.find(
            lambda tag: tag.name in ["h2", "h3"] and "simple trading strategy" in tag.text.lower()
        )
        if rule_heading:
            sibling = rule_heading.find_next_sibling()
            if sibling:
                rules_text = sibling.text.strip()

        # Extract Fundamental reason / Abstract
        reason_text = ""
        reason_heading = soup.find(
            lambda tag: tag.name in ["h2", "h3"] and "fundamental reason" in tag.text.lower()
        )
        if reason_heading:
            sibling = reason_heading.find_next_sibling()
            if sibling:
                reason_text = sibling.text.strip()

        # Extract Keywords
        keywords = []
        kw_heading = soup.find(
            lambda tag: tag.name in ["h2", "h3"] and "keywords" in tag.text.lower()
        )
        if kw_heading:
            sib = kw_heading.find_next_sibling()
            if sib:
                keywords = [k.strip() for k in sib.text.split(",") if k.strip()]

        return {
            "title": title,
            "rules": rules_text,
            "rationale": reason_text,
            "keywords": keywords,
        }
    except Exception as e:
        log.debug(f"Error parsing Quantpedia page {url}: {e}")
        return None


def harvest_quantpedia(
    archetype: str,
    max_strategies: int = 15,
) -> List[Dict[str, Any]]:
    """Crawl Quantpedia screener and parse strategies matching archetype keywords."""
    tag_keywords = ARCHETYPE_QUERIES.get(archetype, {}).get("quantpedia", [])
    if not tag_keywords:
        log.warning(f"No Quantpedia tags defined for archetype: {archetype}")
        return []

    out_dir = DATA_DIR / "quantpedia" / archetype
    out_dir.mkdir(parents=True, exist_ok=True)

    harvested: List[Dict[str, Any]] = []
    seen_slugs = set()

    try:
        resp = requests.get(SCREENER_URL, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code != 200:
            log.error(f"Quantpedia screener returned status {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a", href=True)

        candidate_links = []
        for l in links:
            href = l["href"]
            if "/strategies/" in href and href != "/strategies/" and not href.endswith("/strategies"):
                candidate_links.append((l.text.strip(), href))

        for text, href in candidate_links:
            slug = href.strip("/").split("/")[-1]
            if not slug or slug in seen_slugs:
                continue

            # Check matching keywords in slug or link text
            slug_match = any(kw in slug.lower() or kw in text.lower() for kw in tag_keywords)
            if not slug_match and archetype != "mean_reversion":
                continue

            seen_slugs.add(slug)
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            log.info(f"[Quantpedia Miner] Fetching: {slug} ({full_url})")

            details = fetch_strategy_detail(full_url)
            if not details or not details["rules"]:
                continue

            record = {
                "source": "quantpedia",
                "archetype": archetype,
                "id": slug,
                "title": details["title"],
                "url": full_url,
                "rules": details["rules"],
                "rationale": details["rationale"],
                "keywords": details["keywords"],
            }

            out_file = out_dir / f"{slug}.json"
            out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
            harvested.append(record)
            log.info(f"  [HARVESTED] {details['title'][:60]}")

            if len(harvested) >= max_strategies:
                break
    except Exception as e:
        log.error(f"Error mining Quantpedia for '{archetype}': {e}")

    log.info(f"[Quantpedia Miner] Archetype '{archetype}' finished. Harvested {len(harvested)} strategies.")
    return harvested
