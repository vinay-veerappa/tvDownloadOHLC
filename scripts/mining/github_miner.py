"""Autonomous GitHub Strategy Miner.
Crawls GitHub public repositories for open-source strategy code,
fetching repository summaries, topics, and README definitions.
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

SEARCH_URL = "https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"


def fetch_readme_text(owner: str, repo: str) -> Optional[str]:
    """Fetch raw README from main/master branch."""
    for branch in ["main", "master"]:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=8)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
    return None


def harvest_github(
    archetype: str,
    max_repos: int = 10,
) -> List[Dict[str, Any]]:
    """Search GitHub for strategy repositories matching the archetype."""
    queries = ARCHETYPE_QUERIES.get(archetype, {}).get("github", [])
    if not queries:
        log.warning(f"No GitHub queries defined for archetype: {archetype}")
        return []

    out_dir = DATA_DIR / "github" / archetype
    out_dir.mkdir(parents=True, exist_ok=True)

    harvested: List[Dict[str, Any]] = []
    seen_repos = set()

    for query in queries:
        log.info(f"[GitHub Miner] Searching: '{query}'")
        try:
            url = SEARCH_URL.format(query=requests.utils.quote(query), limit=max_repos)
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
            if resp.status_code != 200:
                log.warning(f"GitHub API returned status {resp.status_code}")
                continue

            items = resp.json().get("items", [])
            for item in items:
                full_name = item.get("full_name")
                if not full_name or full_name in seen_repos:
                    continue
                seen_repos.add(full_name)

                owner, repo_name = full_name.split("/", 1)
                desc = item.get("description") or ""
                stars = item.get("stargazers_count", 0)
                html_url = item.get("html_url", "")
                topics = item.get("topics", [])

                # Fetch README
                readme = fetch_readme_text(owner, repo_name) or ""

                safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', full_name)
                record = {
                    "source": "github",
                    "archetype": archetype,
                    "id": safe_name,
                    "full_name": full_name,
                    "stars": stars,
                    "url": html_url,
                    "description": desc,
                    "topics": topics,
                    "readme_excerpt": readme[:2000] if readme else desc,
                }

                out_file = out_dir / f"{safe_name}.json"
                out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
                harvested.append(record)
                log.info(f"  [HARVESTED] {full_name} ({stars} stars)")

                if len(harvested) >= max_repos:
                    break
        except Exception as e:
            log.error(f"Error querying GitHub for '{query}': {e}")

        if len(harvested) >= max_repos:
            break

    log.info(f"[GitHub Miner] Archetype '{archetype}' finished. Harvested {len(harvested)} repositories.")
    return harvested
