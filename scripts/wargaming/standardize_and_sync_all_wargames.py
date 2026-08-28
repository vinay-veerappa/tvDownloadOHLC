"""Standardized Date-Based Transcript Sync & Normalizer

Enforces strict chronological naming standards:
    `YYYY-MM-DD_{stream_type}_{clean_topic}.txt`
    (e.g., `2026-08-27_wargaming_Jobless_Claims_PreMarket.txt`)

Archives locally in `data/wargaming/transcripts/raw/{wargaming,reengineering}/`,
uploads directly to Google Drive `My Drive/Trading/PackVideos/`,
and logs master ground truth to `data/wargaming/db/mickey_ground_truth.sqlite`.
"""
from __future__ import annotations

import re
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wargaming.wargame_db import save_mickey_ground_truth, init_all_databases
from scripts.wargaming.gdrive_sync import upload_to_drive

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

RAW_DIR = REPO_ROOT / "data" / "wargaming" / "transcripts" / "raw"

MONTH_MAP = {
    'jan': '01', 'january': '01', 'feb': '02', 'february': '02', 'mar': '03', 'march': '03',
    'apr': '04', 'april': '04', 'may': '05', 'jun': '06', 'june': '06', 'jul': '07', 'july': '07',
    'aug': '08', 'august': '08', 'sep': '09', 'september': '09', 'oct': '10', 'october': '10',
    'nov': '11', 'november': '11', 'dec': '12', 'december': '12'
}


def derive_date_and_clean_title(title: str, default_year: int = 2026) -> Tuple[str, str]:
    """Extract standard ISO date (YYYY-MM-DD) and clean topic slug from YouTube/NotebookLM titles."""
    # Pattern 1: (M/D/YYYY) or (M/D/YY)
    m1 = re.search(r'\((\d{1,2})/(\d{1,2})/(\d{2,4})\)', title)
    if m1:
        month, day, year = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        if year < 100:
            year += 2000
        dt = f"{year:04d}-{month:02d}-{day:02d}"
        clean_topic = re.sub(r'\(.*?\)', '', title)
        return dt, sanitize_topic(clean_topic)

    # Pattern 2: Month Day Year (e.g. 'Aug 27 2026' or 'July 29')
    m2 = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:,?\s*(\d{4}))?', title, re.IGNORECASE)
    if m2:
        m_str = m2.group(1).lower()
        month = MONTH_MAP.get(m_str, '01')
        day = int(m2.group(2))
        year = int(m2.group(3)) if m2.group(3) else default_year
        dt = f"{year:04d}-{month}-{day:02d}"
        return dt, sanitize_topic(title)

    # Pattern 3: M-D-YY
    m3 = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', title)
    if m3:
        month, day, year = int(m3.group(1)), int(m3.group(2)), int(m3.group(3))
        if year < 100:
            year += 2000
        dt = f"{year:04d}-{month:02d}-{day:02d}"
        return dt, sanitize_topic(title)

    # Fallback to today
    return datetime.now().strftime("%Y-%m-%d"), sanitize_topic(title)


def sanitize_topic(topic: str) -> str:
    """Strip emojis, bracket markers, and non-alphanumeric noise."""
    t = re.sub(r"^(Daily\s*\$NQ'?s\s*Analysis\s*before\s*Market\s*Open!?|Live\s*NQ\s*Analysis\s*Pre-Market\s*Open!?|Reengineering\s*-\s*|Daily\s*Wargaming\s*)", "", topic, flags=re.IGNORECASE).strip()
    t = re.sub(r'[^a-zA-Z0-9_\-\s]', ' ', t)
    t = re.sub(r'\s+', '_', t).strip('_')
    return t[:50] if t else "Session"



def format_standardized_filename(title: str, stream_type: str = "wargaming") -> Tuple[str, str]:
    """Generate canonical `YYYY-MM-DD_{stream_type}_{clean_topic}.txt`."""
    dt, clean_topic = derive_date_and_clean_title(title)
    filename = f"{dt}_{stream_type}_{clean_topic}.txt"
    return dt, filename


def save_and_mirror_transcript(
    source_id: str,
    title: str,
    raw_content: str,
    stream_type: str = "wargaming",
    ticker: str = "NQ1",
    upload_gdrive: bool = True
) -> Dict[str, Any]:
    """Save with strict date-based filename, mirror to Google Drive, and insert to SQLite."""
    dt, filename = format_standardized_filename(title, stream_type=stream_type)
    sub_dir = RAW_DIR / stream_type
    sub_dir.mkdir(parents=True, exist_ok=True)

    file_path = sub_dir / filename
    file_path.write_text(raw_content, encoding="utf-8")
    log.info(f"Saved local file: {filename} ({len(raw_content)} chars)")

    gdrive_id = None
    if upload_gdrive:
        try:
            res = upload_to_drive(file_path, folder_type=stream_type)
            gdrive_id = res.get("id")
            log.info(f"Uploaded to Google Drive ({stream_type}): {filename} (ID: {gdrive_id})")
        except Exception as e:
            log.warning(f"Google Drive mirror skipped/failed: {e}")

    session_id = f"{dt}_{ticker}_{stream_type}"
    save_mickey_ground_truth({
        "session_id": session_id,
        "session_date": dt,
        "ticker": ticker,
        "stream_type": stream_type,
        "title": title,
        "notebook_source_id": source_id,
        "gdrive_file_id": gdrive_id,
        "raw_transcript": raw_content,
        "char_count": len(raw_content),
        "p12_bias": "BEARISH" if "false" in raw_content.lower() and "short" in raw_content.lower() else "BULLISH",
        "primary_scenario": "FALSE_REVERSION" if "false" in raw_content.lower() else "TRUE_CONTINUATION",
        "key_levels": {"source": "ground_truth_sync"},
    })

    return {"session_id": session_id, "filename": filename, "gdrive_id": gdrive_id}
