"""
trader_narrative.py
===================
Trader Narrative Layer — the "Clean Read" for the trading day.

Two-phase approach (see docs/architecture/TRADER_NARRATIVE_PLAN.md):
  Phase 1: Python pre-digests all data sources into a "cheat sheet"
           (~800-1200 tokens) via briefing_core.build_trader_cheat_sheet()
  Phase 2: LLM writes the narrative (~400 words) from the cheat sheet

v1 scope: Open mode only. File + Discord output. No DB storage. No RTD.

Usage:
    python -m scripts.trader.trader_narrative --mode open
    python -m scripts.trader.trader_narrative --mode open --model gemma4:latest
    python -m scripts.trader.trader_narrative --mode open --no-discord
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.trader.briefing_core import (
    REPO_ROOT,
    build_ticker_cheat_sheet,
    build_intraday_context,
    build_eod_context,
    build_premarket_context,
    get_dataloader,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ET_TZ = "America/New_York"

PROMPT_DIR = REPO_ROOT / "scripts" / "trader" / "prompts"
PROMPT_PATHS = {
    "premarket": PROMPT_DIR / "trader_premarket.md",
    "open": PROMPT_DIR / "trader_morning.md",
    # v1.5/v2 placeholders — not yet implemented
    "intraday": PROMPT_DIR / "trader_intraday.md",
    "close": PROMPT_DIR / "trader_close.md",
}

OUTPUT_DIR = REPO_ROOT / "data" / "options" / "daily"
DISCORD_WEBHOOKS_PATH = REPO_ROOT / "discord_webhooks.json"
UNIFIED_LEVELS_OPEN_TXT = REPO_ROOT / "data" / "options" / "current" / "unified_levels_open.txt"

# Ollama config (mirrors daily_narrative.py)
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "deepseek-v4-pro:cloud"
FALLBACK_MODEL = "deepseek-v4-flash:cloud"
LOCAL_FALLBACK_MODEL = "gemma4:latest"

# Sync gate: max seconds to wait for the 09:30 open snapshot
OPEN_SNAPSHOT_TIMEOUT_SECONDS = 120
OPEN_SNAPSHOT_POLL_INTERVAL = 5


def _wait_for_open_snapshot(timeout: int = OPEN_SNAPSHOT_TIMEOUT_SECONDS) -> bool:
    """Block until the 09:30 unified_levels_open.txt snapshot is fresh.

    Returns True if the file exists and was modified after 09:30 ET today.
    Returns False if timeout expires.
    """
    import time as _time
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo

    et = ZoneInfo(ET_TZ)
    deadline = _time.monotonic() + timeout
    today_930 = _dt.now(et).replace(hour=9, minute=30, second=0, microsecond=0)

    while _time.monotonic() < deadline:
        if UNIFIED_LEVELS_OPEN_TXT.exists():
            mtime = _dt.fromtimestamp(UNIFIED_LEVELS_OPEN_TXT.stat().st_mtime, tz=et)
            if mtime >= today_930:
                log.info("✓ Open snapshot ready (mtime: %s)", mtime.strftime("%H:%M:%S ET"))
                return True
        log.info("Waiting for 09:30 open snapshot... (%s)", UNIFIED_LEVELS_OPEN_TXT)
        _time.sleep(OPEN_SNAPSHOT_POLL_INTERVAL)

    log.warning("Timed out waiting for open snapshot after %ds — proceeding with available data", timeout)
    return False


def load_prompt_template(mode: str) -> str:
    """Load the narrative prompt template for the given mode."""
    path = PROMPT_PATHS.get(mode.lower())
    if not path or not path.exists():
        raise FileNotFoundError(f"Prompt template not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def call_ollama(prompt: str, model: str, timeout: int = 300) -> str:
    """Call the local Ollama instance to generate the narrative.

    Fallback chain: requested model → FALLBACK_MODEL (cloud) → LOCAL_FALLBACK_MODEL (local).
    """
    import requests

    # Build ordered fallback chain, deduplicating
    candidates = []
    seen = set()
    for m in [model, FALLBACK_MODEL, LOCAL_FALLBACK_MODEL]:
        if m and m not in seen:
            candidates.append(m)
            seen.add(m)

    for attempt_model in candidates:
        try:
            log.info("Calling Ollama with model: %s ...", attempt_model)
            response = requests.post(
                OLLAMA_ENDPOINT,
                json={
                    "model": attempt_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_ctx": 32768,
                        "num_predict": 16384,
                    },
                },
                timeout=timeout,
            )
            if response.status_code == 200:
                result = response.json().get("response", "")
                if result:
                    log.info("✓ LLM response received (%d chars)", len(result))
                    return result
            else:
                log.warning("Ollama returned HTTP %d: %s", response.status_code, response.text[:200])
        except Exception as e:
            log.warning("Ollama call failed with model %s: %s", attempt_model, e)

    raise RuntimeError("All LLM model attempts failed")


def send_discord_summary(summary: str, webhook_key: str = "macro-alerts") -> None:
    """Send the narrative to Discord via the configured webhook.

    Splits into chunks if needed (Discord 2000 char limit).
    """
    import requests

    webhook_url = None
    if DISCORD_WEBHOOKS_PATH.exists():
        import json
        with open(DISCORD_WEBHOOKS_PATH, "r", encoding="utf-8") as f:
            webhooks = json.load(f)
        webhook_url = webhooks.get(webhook_key)

    if not webhook_url:
        log.warning("No Discord webhook found for key '%s' — skipping Discord.", webhook_key)
        return

    chunks = []
    if len(summary) > 1900:
        sections = summary.split("\n## ")
        current_chunk = ""
        for section in sections:
            if len(current_chunk) + len(section) + 4 > 1900:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = "## " + section if not section.startswith("#") else section
            else:
                current_chunk = current_chunk + "\n## " + section if current_chunk else section
        if current_chunk:
            chunks.append(current_chunk)
    else:
        chunks = [summary]

    for i, chunk in enumerate(chunks):
        try:
            requests.post(webhook_url, json={"content": chunk}, timeout=15)
            log.info("  Discord chunk %d/%d sent to %s", i + 1, len(chunks), webhook_key)
        except Exception as e:
            log.warning("  Discord delivery failed for chunk %d: %s", i + 1, e)


def write_narrative_to_disk(summary: str, mode: str, ticker: str) -> Path:
    """Write the narrative to disk: latest (overwrite) + dated archive."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")

    latest_path = OUTPUT_DIR / f"latest_trader_narrative_{mode}_{ticker}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(summary)
    log.info("  Written to %s", latest_path)

    dated_path = OUTPUT_DIR / f"{date_str}_trader_narrative_{mode}_{ticker}.md"
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(summary)
    log.info("  Written to %s", dated_path)

    return latest_path


def run_narrative(
    mode: str,
    model: str,
    tickers: list[str],
    target_date: date | None = None,
    send_discord: bool = True,
) -> list[str]:
    """Main narrative generation flow (synchronous wrapper) for multiple tickers."""
    
    loader = get_dataloader(lookback_days=5)

    if mode == "open":
        _wait_for_open_snapshot()

    prompt_template = load_prompt_template(mode)
    
    results = []

    for ticker in tickers:
        log.info("Building cheat sheet for %s (mode: %s)...", ticker, mode)
        try:
            if mode == "intraday":
                cheat_sheet = build_intraday_context(loader=loader, ticker=ticker, target_date=target_date)
            elif mode == "close":
                cheat_sheet = build_eod_context(loader=loader, ticker=ticker, target_date=target_date)
            elif mode == "premarket":
                cheat_sheet = build_premarket_context(loader=loader, nq_ticker=ticker, target_date=target_date)
            else:
                cheat_sheet = build_ticker_cheat_sheet(
                    ticker=ticker,
                    mode=mode,
                    loader=loader,
                    target_date=target_date,
                )
            
            log.info("✓ Cheat sheet assembled for %s (%d chars)", ticker, len(cheat_sheet))
            
            # Skip LLM if the cheat sheet indicates markets closed or session complete
            if cheat_sheet.startswith("== MARKETS CLOSED ==") or cheat_sheet.startswith("== SESSION COMPLETE =="):
                log.info("  Skipping LLM — %s", cheat_sheet.split("\n")[0])
                write_narrative_to_disk(cheat_sheet, mode, ticker)
                if send_discord:
                    send_discord_summary(cheat_sheet)
                results.append(cheat_sheet)
                continue
            
            from datetime import datetime
            if mode == "close" and datetime.now().weekday() in [4, 5, 6]:  # Friday, Saturday, Sunday
                cheat_sheet += "\n\n== WEEK AHEAD CONTEXT ==\nSince it's the weekend, incorporate a 'Week Ahead' outlook focusing on upcoming macro events and structural setups for the week. The focus should be on Monday/Tuesday structure and the broader weekly thesis."
            
            prompt = prompt_template.replace("{{INSERT_CHEAT_SHEET}}", cheat_sheet)
            
            summary = call_ollama(prompt, model)
            write_narrative_to_disk(summary, mode, ticker)
            
            if send_discord:
                log.info("Sending narrative to Discord for %s...", ticker)
                send_discord_summary(summary)
            
            results.append(summary)
        except Exception as e:
            log.error("Failed to generate narrative for %s: %s", ticker, e)

    return results


def main():
    parser = argparse.ArgumentParser(description="Trader Narrative Generator")
    parser.add_argument("--mode", type=str, choices=["premarket", "open", "intraday", "close"], default="open")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Ollama model to use")
    parser.add_argument("--no-discord", action="store_true", help="Disable Discord output")
    parser.add_argument("--tickers", type=str, nargs="+", default=["NQ1", "ES1"], help="List of tickers to process")
    args = parser.parse_args()

    try:
        run_narrative(
            mode=args.mode,
            model=args.model,
            tickers=args.tickers,
            send_discord=not args.no_discord,
        )
    except KeyboardInterrupt:
        log.info("\\nCancelled by user")
    except Exception as e:
        log.error("Fatal error: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()