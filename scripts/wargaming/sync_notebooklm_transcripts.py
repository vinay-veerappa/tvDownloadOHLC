"""NotebookLM to Local Storage & Google Drive Synchronization Engine

Synchronizes all historical and newly added transcripts from Google NotebookLM:
1. Downloads full transcript text via NotebookLM MCP.
2. Archives locally in `data/wargaming/transcripts/raw/{wargaming,reengineering}/`.
3. Uploads / mirrors each file to Google Drive (`My Drive/Trading/PackVideos/`).
4. Ingests structured session records into `data/wargaming/db/mickey_ground_truth.sqlite`.

Usage:
    python scripts/wargaming/sync_notebooklm_transcripts.py --type all
    python scripts/wargaming/sync_notebooklm_transcripts.py --type wargaming --limit 10
"""
from __future__ import annotations

import re
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wargaming.wargame_db import save_mickey_ground_truth, init_all_databases
from scripts.wargaming.gdrive_sync import upload_to_drive

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

RAW_DIR = REPO_ROOT / "data" / "wargaming" / "transcripts" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def parse_date_from_title(title: str, default_year: int = 2026) -> str:
    """Extract standard YYYY-MM-DD date from titles like '(6/25/2026)' or 'July 29'."""
    # Pattern 1: (M/D/YYYY) or (M/D/YY)
    m = re.search(r'\((\d{1,2})/(\d{1,2})/(\d{2,4})\)', title)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        return f"{year:04d}-{month:02d}-{day:02d}"

    # Pattern 2: Month Name Day (e.g. 'July 29' or 'June 2')
    month_names = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
        'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
        'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'october': 10, 'oct': 10,
        'november': 11, 'nov': 11, 'december': 12, 'dec': 12
    }
    m2 = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', title, re.IGNORECASE)
    if m2:
        m_str = m2.group(1).lower()
        month = month_names.get(m_str, 1)
        day = int(m2.group(2))
        return f"{default_year:04d}-{month:02d}-{day:02d}"

    # Fallback to today's date
    return datetime.now().strftime("%Y-%m-%d")


def sanitize_filename(name: str) -> str:
    """Clean title to safe ASCII filename."""
    cleaned = re.sub(r'[^a-zA-Z0-9_\-\. ]', '', name).strip()
    return cleaned[:80]


def process_and_archive_transcript(
    source_id: str,
    title: str,
    raw_content: str,
    stream_type: str = "wargaming",
    ticker: str = "NQ1",
    upload_gdrive: bool = True,
) -> Dict[str, Any]:
    """Save raw text, upload to Google Drive, and insert to SQLite."""
    session_date = parse_date_from_title(title)
    sub_dir = RAW_DIR / stream_type
    sub_dir.mkdir(parents=True, exist_ok=True)

    safe_title = sanitize_filename(title)
    file_name = f"{session_date}_{safe_title}.txt"
    file_path = sub_dir / file_name

    # 1. Write local raw text
    file_path.write_text(raw_content, encoding="utf-8")
    log.info(f"Saved local transcript: {file_path.name} ({len(raw_content)} chars)")

    # 2. Upload to Google Drive
    gdrive_id = None
    if upload_gdrive:
        try:
            res = upload_to_drive(file_path, folder_type=stream_type)
            gdrive_id = res.get("id")
        except Exception as e:
            log.warning(f"Google Drive upload skipped/failed: {e}")

    # 3. Save to SQLite Ground Truth DB
    session_id = f"{session_date}_{ticker}_{stream_type}"
    db_record = {
        "session_id": session_id,
        "session_date": session_date,
        "ticker": ticker,
        "stream_type": stream_type,
        "title": title,
        "notebook_source_id": source_id,
        "gdrive_file_id": gdrive_id,
        "raw_transcript": raw_content,
        "char_count": len(raw_content),
        "p12_bias": "BEARISH" if "false" in raw_content.lower() and "short" in raw_content.lower() else "BULLISH",
        "primary_scenario": "FALSE_REVERSION" if "false" in raw_content.lower() else "TRUE_CONTINUATION",
        "key_levels": {"source": "notebooklm_extracted"},
    }

    save_mickey_ground_truth(db_record)
    log.info(f"Logged to mickey_ground_truth.sqlite: {session_id}")

    return {"session_id": session_id, "file_path": str(file_path), "gdrive_id": gdrive_id}
