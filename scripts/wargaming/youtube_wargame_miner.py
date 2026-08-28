"""YouTube Playlist Transcript Miner & Multi-Cloud Ingest Engine

Scrapes all video transcripts from active Mickey & Austin Wargaming and Reengineering YouTube playlists:
1. Extracts full spoken transcript text via YouTubeTranscriptApi.
2. Formats and saves local raw archives under `data/wargaming/transcripts/raw/`.
3. Uploads / mirrors each file to Google Drive (`My Drive/Trading/PackVideos/`).
4. Logs ground truth entries into `data/wargaming/db/mickey_ground_truth.sqlite`.

Usage:
    python scripts/wargaming/youtube_wargame_miner.py --playlist PLNsd-wh14sP4 --type reengineering
"""
from __future__ import annotations

import re
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wargaming.sync_notebooklm_transcripts import process_and_archive_transcript

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def fetch_video_transcript(video_id: str) -> Optional[str]:
    """Fetch complete transcript text for a YouTube video."""
    try:
        api = YouTubeTranscriptApi()
        ts = api.fetch(video_id)
        full_text = " ".join([snippet.text for snippet in ts.snippets])
        return full_text
    except Exception as e:
        log.warning(f"Failed to fetch transcript for video {video_id}: {e}")
        return None


def mine_playlist(videos: List[Dict[str, Any]], stream_type: str = "reengineering", upload_gdrive: bool = True) -> List[Dict[str, Any]]:
    """Download transcripts, upload to Google Drive, and record in database."""
    results = []
    for idx, v in enumerate(videos, 1):
        vid = v.get("video_id")
        title = v.get("title", f"Session {vid}")
        log.info(f"[{idx}/{len(videos)}] Mining transcript for '{title}' ({vid})...")

        text = fetch_video_transcript(vid)
        if not text:
            log.warning(f"Skipping {vid} (no transcript available)")
            continue

        res = process_and_archive_transcript(
            source_id=f"yt_{vid}",
            title=title,
            raw_content=text,
            stream_type=stream_type,
            ticker="NQ1",
            upload_gdrive=upload_gdrive,
        )
        results.append(res)
        log.info(f"Successfully processed and archived: {title}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Mine YouTube Transcripts for Pack Wargaming / Reengineering")
    parser.add_argument("--playlist-json", default="docs/profiler/youtube_transcripts/latest_reengineering_playlist.json", help="Path to parsed playlist JSON")
    parser.add_argument("--type", default="reengineering", choices=["wargaming", "reengineering"], help="Stream type")
    parser.add_argument("--no-gdrive", action="store_true", help="Do not upload to Google Drive")
    args = parser.parse_args()

    json_path = REPO_ROOT / args.playlist_json
    if not json_path.exists():
        log.error(f"Playlist JSON not found at: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        videos = json.load(f)

    log.info(f"Found {len(videos)} videos to mine from {json_path.name}")
    results = mine_playlist(videos, stream_type=args.type, upload_gdrive=not args.no_gdrive)
    print(f"Successfully mined and archived {len(results)}/{len(videos)} transcripts!")


if __name__ == "__main__":
    main()

