"""Futures.io (NexusFi) Strategy & NinjaScript Miner.

Crawls NexusFi/Futures.io for high-signal futures strategies, Market Profile discussions,
and NinjaTrader 8 (.cs / .zip) indicator/strategy attachments using authenticated session cookies.

Supports:
- Loading from `data/strategies/raw_mined/futures_io_cookies.json` or Netscape `nexusfi.com_cookies.txt`.
- Crawling NT8 Downloads repository (catid=27) and saving .zip / .cs packages.
- Crawling forum threads for rulebooks, indicators, and setups.
"""
from __future__ import annotations

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests
except ImportError:
    import requests  # fallback

from scripts.mining.config import DATA_DIR, DEFAULT_HEADERS

log = logging.getLogger(__name__)

FUTURES_IO_BASE = "https://nexusfi.com"
COOKIE_JSON = DATA_DIR / "futures_io_cookies.json"
COOKIE_TXT = Path.home() / "Downloads" / "nexusfi.com_cookies.txt"

# Target download categories
NT8_DOWNLOAD_CATS = [
    {"catid": 27, "name": "NinjaTrader 8 Indicators & Strategies"},
    {"catid": 26, "name": "NinjaTrader Free Section"},
]

TARGET_FORUMS = [
    {"name": "Platforms & Indicators", "url": "https://nexusfi.com/platforms-indicators/"},
    {"name": "Trading Journals", "url": "https://nexusfi.com/trading-journals/"},
]


def load_session_cookies() -> Dict[str, str]:
    """Load exported cookies from JSON or Netscape txt file."""
    # 1. Try JSON in data dir
    if COOKIE_JSON.exists():
        try:
            data = json.loads(COOKIE_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            elif isinstance(data, list):
                return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
        except Exception as e:
            log.warning(f"Could not parse {COOKIE_JSON}: {e}")

    # 2. Try Netscape txt in Downloads
    if COOKIE_TXT.exists():
        try:
            cookies = {}
            for line in COOKIE_TXT.read_text(encoding="utf-8").splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
            if cookies:
                COOKIE_JSON.parent.mkdir(parents=True, exist_ok=True)
                COOKIE_JSON.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
                return cookies
        except Exception as e:
            log.warning(f"Could not parse Netscape cookie file {COOKIE_TXT}: {e}")

    # 3. Fallback to env var
    env_cookie = os.getenv("FUTURES_IO_COOKIE")
    if env_cookie:
        cookies = {}
        for item in env_cookie.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies[k] = v
        return cookies

    return {}


def harvest_futures_io(
    query: Optional[str] = None,
    max_items: int = 10,
    download_files: bool = True,
) -> List[Dict[str, Any]]:
    """Crawl NexusFi/Futures.io for NT8 strategies, indicators, and discussions."""
    cookies = load_session_cookies()
    out_dir = DATA_DIR / "futures_io"
    dl_dir = out_dir / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    dl_dir.mkdir(parents=True, exist_ok=True)

    if not cookies:
        log.warning("[Futures.io Miner] No session cookies found.")
        return []

    harvested: List[Dict[str, Any]] = []
    seen_ids = set()

    # 1. Crawl NT8 Downloads Section (catid=27)
    for cat in NT8_DOWNLOAD_CATS:
        cat_id = cat["catid"]
        cat_name = cat["name"]
        cat_url = f"{FUTURES_IO_BASE}/local_links.php?catid={cat_id}"
        log.info(f"[Futures.io Miner] Crawling {cat_name} ({cat_url})...")

        try:
            resp = requests.get(cat_url, cookies=cookies, headers=DEFAULT_HEADERS, impersonate="chrome120", timeout=15)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            links = [(a.text.strip(), a["href"]) for a in soup.find_all("a", href=True) if "linkid=" in a["href"]]

            for title, href in links:
                m = re.search(r"linkid=(\d+)", href)
                if not m or not title:
                    continue
                link_id = m.group(1)
                if link_id in seen_ids:
                    continue
                seen_ids.add(link_id)

                detail_url = f"{FUTURES_IO_BASE}/local_links.php?catid={cat_id}&linkid={link_id}"
                log.info(f"  Found NT8 item: {title} (ID: {link_id})")

                # Fetch detail page
                d_resp = requests.get(detail_url, cookies=cookies, headers=DEFAULT_HEADERS, impersonate="chrome120", timeout=12)
                file_path = None

                if download_files and d_resp.status_code == 200:
                    jump_url = f"{FUTURES_IO_BASE}/local_links.php?action=jump&catid={cat_id}&id={link_id}"
                    try:
                        file_resp = requests.get(jump_url, cookies=cookies, headers=DEFAULT_HEADERS, impersonate="chrome120", timeout=20)
                        if file_resp.status_code == 200:
                            cd = file_resp.headers.get("content-disposition", "")
                            fn_match = re.search(r'filename="?([^"]+)"?', cd)
                            filename = fn_match.group(1) if fn_match else f"nt8_item_{link_id}.zip"
                            save_file = dl_dir / filename
                            save_file.write_bytes(file_resp.content)
                            file_path = str(save_file)
                            log.info(f"    [DOWNLOADED] {filename} ({len(file_resp.content)} bytes)")
                    except Exception as e:
                        log.debug(f"Could not download file {link_id}: {e}")

                record = {
                    "source": "futures_io",
                    "archetype": "futures_indicator_strategy",
                    "id": f"fio_{link_id}",
                    "title": title,
                    "category": cat_name,
                    "url": detail_url,
                    "file_path": file_path,
                }

                meta_file = out_dir / f"fio_{link_id}.json"
                meta_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
                harvested.append(record)

                if len(harvested) >= max_items:
                    break
        except Exception as e:
            log.error(f"Error crawling {cat_name}: {e}")

        if len(harvested) >= max_items:
            break

    log.info(f"[Futures.io Miner] Finished. Harvested {len(harvested)} items.")
    return harvested
