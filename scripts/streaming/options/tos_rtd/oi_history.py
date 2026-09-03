"""
oi_history.py — read the per-session OI book history.

The OI book (raw per-contract open interest per session) is appended to
data/options/history/oi/oi_book.jsonl by the RTD coordinator on each cache
save. This module reads it back for analysis: OI deltas, position building,
recomputing historical walls under a changed methodology, etc.

Usage:
  from scripts.streaming.options.tos_rtd.oi_history import load_oi_history
  rows = load_oi_history()          # list of records, oldest first
  rows = load_oi_history(symbol="/ES")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[4]
OI_HISTORY_PATH = REPO_ROOT / "data" / "options" / "history" / "oi" / "oi_book.jsonl"


def iter_oi_history(path: Path | None = None) -> Iterator[dict[str, Any]]:
    """Yield each session's OI book record (oldest first)."""
    p = path or OI_HISTORY_PATH
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_oi_history(
    symbol: str | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Load OI history, optionally filtered to one symbol (e.g. "/ES")."""
    rows = list(iter_oi_history(path))
    if symbol is None:
        return rows
    out = []
    for r in rows:
        oi = r.get("open_interest", {})
        if symbol in oi:
            out.append({**r, "open_interest": {symbol: oi[symbol]}})
    return out


def oi_delta(
    symbol: str,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Per-session OI delta for a symbol (position building / unwinding)."""
    rows = load_oi_history(symbol, path)
    out = []
    prev: dict[str, int] = {}
    for r in rows:
        cur = r.get("open_interest", {}).get(symbol, {})
        delta = {
            k: int(cur.get(k, 0)) - int(prev.get(k, 0))
            for k in set(cur) | set(prev)
        }
        out.append({
            "session_key": r.get("session_key"),
            "cached_at": r.get("cached_at"),
            "oi": cur,
            "delta": delta,
        })
        prev = cur
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = load_oi_history()
    print(f"OI history: {len(rows)} session records")
    for r in rows[-3:]:
        oi = r.get("open_interest", {})
        n = {s: len(m) for s, m in oi.items()}
        print(f"  {r.get('session_key')}: {n}")
