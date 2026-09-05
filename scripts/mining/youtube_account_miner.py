"""YouTube User Account Miner.

Extracts subscribed channels and recent viewing history using user's exported cookies,
classifies channels by trading domain, and outputs creator handles to config.
"""
from __future__ import annotations

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Set
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("YTAccountMiner")

COOKIE_FILE = Path(r"C:\Users\vinay\Downloads\www.youtube.com_cookies (1).txt")
OUTPUT_DIR = Path(r"C:\Users\vinay\tvDownloadOHLC\data\strategies\raw_mined")
OUTPUT_COOKIES_JSON = OUTPUT_DIR / "youtube_cookies.json"


def load_cookies() -> Dict[str, str]:
    if not COOKIE_FILE.exists():
        raise FileNotFoundError(f"Cookie file not found at {COOKIE_FILE}")

    cookies = {}
    for line in COOKIE_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]

    OUTPUT_COOKIES_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_COOKIES_JSON, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    log.info(f"Loaded {len(cookies)} cookies and saved to {OUTPUT_COOKIES_JSON}")
    return cookies


def get_authenticated_session() -> requests.Session:
    cookies = load_cookies()
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def extract_yt_initial_data(html: str) -> Dict[str, Any]:
    match = re.search(r"var ytInitialData\s*=\s*({.*?});</script>", html)
    if not match:
        match = re.search(r"window\[\"ytInitialData\"\]\s*=\s*({.*?});</script>", html)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception as e:
            log.warning(f"Error decoding ytInitialData JSON: {e}")
    return {}


def find_objects_by_key(data: Any, target_key: str) -> List[Any]:
    """Recursively find all dictionaries that contain a specific key."""
    results = []
    if isinstance(data, dict):
        if target_key in data:
            results.append(data[target_key])
        for v in data.values():
            results.extend(find_objects_by_key(v, target_key))
    elif isinstance(data, list):
        for item in data:
            results.extend(find_objects_by_key(item, target_key))
    return results


def fetch_subscriptions(session: requests.Session) -> List[Dict[str, str]]:
    url = "https://www.youtube.com/feed/channels"
    log.info(f"Fetching subscriptions from {url}...")
    res = session.get(url, allow_redirects=True)
    if "signin" in res.url.lower():
        log.error("Redirected to signin page. Cookies may lack proper auth or expired.")
        return []

    data = extract_yt_initial_data(res.text)
    channel_renderers = find_objects_by_key(data, "channelRenderer")
    grid_renderers = find_objects_by_key(data, "gridChannelRenderer")
    all_renderers = channel_renderers + grid_renderers

    channels: List[Dict[str, str]] = []
    seen_ids: Set[str] = set()

    for r in all_renderers:
        title_runs = r.get("title", {}).get("runs", []) or r.get("title", {}).get("simpleText")
        title = title_runs[0].get("text") if isinstance(title_runs, list) and title_runs else str(title_runs)
        
        channel_id = r.get("channelId", "")
        endpoint = r.get("navigationEndpoint", {}).get("browseEndpoint", {})
        canonical_url = endpoint.get("canonicalBaseUrl", "")
        
        sub_count = r.get("subscriberCountText", {}).get("simpleText", "")
        desc_runs = r.get("descriptionSnippet", {}).get("runs", [])
        desc = desc_runs[0].get("text") if desc_runs else ""

        if channel_id and channel_id not in seen_ids:
            seen_ids.add(channel_id)
            channels.append({
                "title": title,
                "channel_id": channel_id,
                "handle": canonical_url.replace("/", "") if canonical_url else "",
                "subscribers": sub_count,
                "description": desc,
            })

    # If renderers was empty, try regex fallback for title/channelId
    if not channels:
        log.info("Direct JSON renderers empty; attempting regex fallback across page...")
        raw_matches = re.findall(r'\"channelId\":\"(UC[a-zA-Z0-9_-]{22})\"[^\}]*?\"title\":\{\"simpleText\":\"([^\"]+)\"', res.text)
        for cid, name in raw_matches:
            if cid not in seen_ids:
                seen_ids.add(cid)
                channels.append({
                    "title": name,
                    "channel_id": cid,
                    "handle": "",
                    "subscribers": "",
                    "description": "",
                })

    log.info(f"Successfully extracted {len(channels)} subscribed channels!")
    return channels


def fetch_watch_history(session: requests.Session) -> List[Dict[str, str]]:
    url = "https://www.youtube.com/feed/history"
    log.info(f"Fetching watch history from {url}...")
    res = session.get(url, allow_redirects=True)
    if "signin" in res.url.lower():
        log.error("Redirected to signin page for watch history.")
        return []

    data = extract_yt_initial_data(res.text)
    video_renderers = find_objects_by_key(data, "videoRenderer")

    history_items: List[Dict[str, str]] = []
    seen_videos: Set[str] = set()

    for v in video_renderers:
        vid = v.get("videoId", "")
        title_runs = v.get("title", {}).get("runs", [])
        title = title_runs[0].get("text") if title_runs else ""
        
        owner_runs = v.get("ownerText", {}).get("runs", [])
        channel = owner_runs[0].get("text") if owner_runs else ""

        if vid and vid not in seen_videos:
            seen_videos.add(vid)
            history_items.append({
                "video_id": vid,
                "title": title,
                "channel": channel,
                "url": f"https://www.youtube.com/watch?v={vid}",
            })

    log.info(f"Successfully extracted {len(history_items)} recent watch history items!")
    return history_items


def mine_user_youtube() -> Dict[str, Any]:
    session = get_authenticated_session()
    subs = fetch_subscriptions(session)
    history = fetch_watch_history(session)

    result = {
        "subscriptions_count": len(subs),
        "history_count": len(history),
        "subscriptions": subs,
        "recent_history": history,
    }

    out_file = OUTPUT_DIR / "user_youtube_profile.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    log.info(f"Saved complete profile to {out_file}")

    return result


if __name__ == "__main__":
    mine_user_youtube()
