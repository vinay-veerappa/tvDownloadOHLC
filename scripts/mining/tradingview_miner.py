"""Autonomous TradingView Strategy Miner.
Crawls TradingView public script registry for open-source strategy() implementations
and downloads full Pine Script source code via the Pine Facade API.
"""
from __future__ import annotations

import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

from scripts.mining.config import DATA_DIR, ARCHETYPE_QUERIES, DEFAULT_HEADERS

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.tradingview.com/pubscripts-suggest-json/?search={query}"
FACADE_URL = "https://pine-facade.tradingview.com/pine-facade/get/{script_id}/last"


def fetch_script_source(script_id: str) -> Optional[Dict[str, Any]]:
    """Fetch complete Pine script metadata and source code."""
    try:
        url = FACADE_URL.format(script_id=script_id)
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        log.debug(f"Failed to fetch Pine source for {script_id}: {e}")
    return None


def harvest_tradingview(
    archetype: str,
    max_strategies: int = 15,
) -> List[Dict[str, Any]]:
    """Search and download TradingView strategy() scripts for a given archetype."""
    queries = ARCHETYPE_QUERIES.get(archetype, {}).get("tradingview", [])
    if not queries:
        log.warning(f"No TradingView queries defined for archetype: {archetype}")
        return []

    out_dir = DATA_DIR / "tradingview" / archetype
    out_dir.mkdir(parents=True, exist_ok=True)

    harvested: List[Dict[str, Any]] = []
    seen_ids = set()

    for query in queries:
        log.info(f"[TradingView Miner] Searching: '{query}'")
        try:
            url = SEARCH_URL.format(query=requests.utils.quote(query))
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()
            results = data.get("results", [])

            for item in results:
                # Accept type 2 (Strategy) or high-signal type 1 (e.g. TheStrat combos/indicators)
                stype = item.get("type")
                sname = item.get("scriptName", "").lower()
                if stype != 2 and not ("strat" in sname or "combo" in sname):
                    continue

                script_id = item.get("scriptIdPart")
                if not script_id or script_id in seen_ids:
                    continue
                seen_ids.add(script_id)

                script_name = item.get("scriptName", "Unknown")

                # Fetch full Pine source
                payload = fetch_script_source(script_id)
                if not payload:
                    continue

                source_code = payload.get("source", "")
                if not source_code or len(source_code.strip()) < 100:
                    continue

                # Red Flag Checks
                has_lookahead_bug = "lookahead_on" in source_code or "barmerge.lookahead_on" in source_code
                pine_version = payload.get("version", "unknown")

                # Sanitize ID for filename
                safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', script_id)

                # Save raw .pine script
                pine_file = out_dir / f"{safe_id}.pine"
                pine_file.write_text(source_code, encoding="utf-8")

                record = {
                    "source": "tradingview",
                    "archetype": archetype,
                    "id": script_id,
                    "title": script_name,
                    "author": payload.get("extra", {}).get("author", {}).get("username", "Unknown"),
                    "pine_version": pine_version,
                    "lookahead_flag": has_lookahead_bug,
                    "url": f"https://www.tradingview.com/script/{script_id}/",
                    "lines_of_code": len(source_code.splitlines()),
                    "script_path": str(pine_file),
                }

                meta_file = out_dir / f"{safe_id}.json"
                meta_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
                harvested.append(record)
                log.info(f"  [HARVESTED] {script_name[:60]} ({script_id}) - {record['lines_of_code']} lines")

                if len(harvested) >= max_strategies:
                    break
        except Exception as e:
            log.error(f"Error querying TradingView for '{query}': {e}")

        if len(harvested) >= max_strategies:
            break

    log.info(f"[TradingView Miner] Archetype '{archetype}' finished. Harvested {len(harvested)} scripts.")
    return harvested
