"""Autonomous YouTube Strategy Harvester.
Crawls YouTube using scrapetube, enforces duration/content filters,
and downloads spoken transcripts via YouTubeTranscriptApi.
"""
from __future__ import annotations

import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi

from scripts.mining.config import DATA_DIR, ARCHETYPE_QUERIES

log = logging.getLogger(__name__)


def parse_duration_seconds(length_dict: Optional[Dict[str, Any]]) -> int:
    """Parse lengthText like '12:34' or '1:02:15' into seconds."""
    if not length_dict or "simpleText" not in length_dict:
        return 0
    text = length_dict["simpleText"]
    parts = text.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return 0
    return 0


def fetch_transcript(video_id: str) -> Optional[str]:
    """Fetch full English transcript text."""
    try:
        api = YouTubeTranscriptApi()
        ts = api.fetch(video_id)
        return " ".join([snippet.text for snippet in ts.snippets])
    except Exception as e:
        log.debug(f"No transcript for {video_id}: {e}")
        return None


def harvest_youtube(
    archetype: str,
    max_videos: int = 15,
    min_duration_sec: int = 480,    # 8 minutes
    max_duration_sec: int = 2400,   # 40 minutes
) -> List[Dict[str, Any]]:
    """Mine YouTube strategy videos for a specific archetype."""
    queries = ARCHETYPE_QUERIES.get(archetype, {}).get("youtube", [])
    if not queries:
        log.warning(f"No YouTube queries defined for archetype: {archetype}")
        return []

    out_dir = DATA_DIR / "youtube" / archetype
    out_dir.mkdir(parents=True, exist_ok=True)

    harvested: List[Dict[str, Any]] = []
    seen_ids = set()

    for query in queries:
        log.info(f"[YouTube Miner] Searching: '{query}'")
        try:
            generator = scrapetube.get_search(query, limit=max_videos)
            for item in generator:
                vid = item.get("videoId")
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)

                # Extract title
                title_runs = item.get("title", {}).get("runs", [])
                title = title_runs[0].get("text", "") if title_runs else "Unknown"

                # Check duration
                dur = parse_duration_seconds(item.get("lengthText"))
                if dur > 0 and (dur < min_duration_sec or dur > max_duration_sec):
                    log.debug(f"Skipping {vid} due to duration: {dur}s")
                    continue

                # Title anti-clickbait check
                title_lower = title.lower()
                if any(bad in title_lower for bad in ["100% win", "infinite money", "never lose", "#shorts"]):
                    continue

                # Channel / Creator
                channel_runs = item.get("ownerText", {}).get("runs", [])
                channel = channel_runs[0].get("text", "") if channel_runs else "Unknown"

                # Fetch Transcript
                transcript = fetch_transcript(vid)
                if not transcript or len(transcript.split()) < 300:
                    continue

                # Quant Feasibility Pre-filter: must mention stop loss or risk
                t_lower = transcript.lower()
                if not ("stop loss" in t_lower or "risk" in t_lower):
                    continue

                record = {
                    "source": "youtube",
                    "archetype": archetype,
                    "id": vid,
                    "title": title,
                    "channel": channel,
                    "duration_seconds": dur,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "transcript": transcript,
                    "word_count": len(transcript.split()),
                }

                out_file = out_dir / f"{vid}.json"
                out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
                harvested.append(record)
                log.info(f"  [HARVESTED] {title[:60]} ({vid})")

                if len(harvested) >= max_videos:
                    break
        except Exception as e:
            log.error(f"Error during YouTube search for '{query}': {e}")

        if len(harvested) >= max_videos:
            break

    log.info(f"[YouTube Miner] Archetype '{archetype}' finished. Harvested {len(harvested)} videos.")
    return harvested
