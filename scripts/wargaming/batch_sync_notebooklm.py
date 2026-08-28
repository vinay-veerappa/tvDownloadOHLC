"""Batch NotebookLM Transcripts Synchronizer

Downloads transcripts from NotebookLM, writes local text files,
uploads them directly to Google Drive (My Drive/Trading/PackVideos/Wargaming & Reengineering),
and inserts structured records into mickey_ground_truth.sqlite.
"""
from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wargaming.sync_notebooklm_transcripts import process_and_archive_transcript

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def sync_source_payload(payload: Dict[str, Any], stream_type: str = "wargaming", upload_gdrive: bool = True) -> Dict[str, Any]:
    """Process a single source content payload."""
    source_id = payload.get("source_id", "unknown")
    title = payload.get("title", "Untitled Session")
    content = payload.get("content", "")

    if not content:
        log.warning(f"Empty content for source: {title}")
        return {"status": "skipped", "title": title}

    res = process_and_archive_transcript(
        source_id=source_id,
        title=title,
        raw_content=content,
        stream_type=stream_type,
        ticker="NQ1",
        upload_gdrive=upload_gdrive,
    )
    return {"status": "success", "result": res}
