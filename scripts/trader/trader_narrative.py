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
from datetime import date, datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# Side-effect import: ensures the repo root is on sys.path so
# `from scripts.trader import ...` works without a per-file hack.
# See scripts/trader/_path_setup.py for the full rationale.
from scripts.trader import _path_setup  # noqa: F401

from scripts.trader.briefing_core import (
    REPO_ROOT,
    build_ticker_cheat_sheet,
    build_intraday_context,
    build_eod_context,
    build_premarket_context,
    get_dataloader,
)
from scripts.libs_py.risk.narrative import insert_risk_params
from scripts.libs_py.discord import send_summary as _send_discord_summary

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
UNIFIED_LEVELS_OPEN_TXT = REPO_ROOT / "data" / "options" / "current" / "unified_levels_open.txt"
UNIFIED_LEVELS_CLOSE_TXT = REPO_ROOT / "data" / "options" / "current" / "unified_levels_close.txt"

# Ollama config — defaults sourced from the unified LLM section
# in `narrative_stats.yaml` (audit §2.6). The audit found that the
# two narrative chains had drifted to different defaults
# (`deepseek-v4-pro:cloud` vs `gemma4:latest`), producing
# inconsistent voice and JSON adherence. We now read from a
# single source of truth via `config_loader.get_llm_config()`.
from scripts.trader.config_loader import get_llm_config  # noqa: E402

_llm_cfg = get_llm_config()
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
# `default_trader_model` is the trader-narrative-specific key;
# `default_model` is the daily-narrative-specific key. Both point
# at the same model on purpose — a trader reading the morning
# "clean read" and the daily EOD sees the same prose voice. The
# --model CLI flag still allows per-run override.
DEFAULT_MODEL = (
    _llm_cfg.get("default_trader_model")
    or _llm_cfg.get("default_model")
    or "gemma4:latest"
)
FALLBACK_MODEL = _llm_cfg.get("fallback_model") or "gemma4:31b-cloud"
LOCAL_FALLBACK_MODEL = _llm_cfg.get("local_fallback_model") or "gemma4:latest"

# Sync gate: max seconds to wait for the 09:30 open snapshot
OPEN_SNAPSHOT_TIMEOUT_SECONDS = 120
OPEN_SNAPSHOT_POLL_INTERVAL = 5

# Sync gate: max seconds to wait for the 16:15 close snapshot.
# The 10-minute cron gap (16:15 pipeline → 16:25 narrative) usually
# gives us 10 minutes of headroom; 180s (3 min) is generous and still
# short enough to keep the narrative on schedule.
CLOSE_SNAPSHOT_TIMEOUT_SECONDS = 180
CLOSE_SNAPSHOT_POLL_INTERVAL = 5


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


def _wait_for_close_snapshot(timeout: int = CLOSE_SNAPSHOT_TIMEOUT_SECONDS) -> bool:
    """Block until the 16:15 unified_levels_close.txt snapshot is fresh.

    Mirrors `_wait_for_open_snapshot` for the EOD path. The 10-minute
    cron gap between the 16:15 pipeline run and the 16:25 EOD
    narrative usually means the file is already there, but if the
    16:15 run slips (e.g. broker latency), this gate prevents the
    narrative from grading the day against the 16:00 snapshot.

    Returns True if the file exists and was modified after 16:15 ET
    today. Returns False if timeout expires; caller proceeds with
    whatever is on disk and logs a warning.
    """
    import time as _time
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo

    et = ZoneInfo(ET_TZ)
    deadline = _time.monotonic() + timeout
    today_1615 = _dt.now(et).replace(hour=16, minute=15, second=0, microsecond=0)

    while _time.monotonic() < deadline:
        if UNIFIED_LEVELS_CLOSE_TXT.exists():
            mtime = _dt.fromtimestamp(UNIFIED_LEVELS_CLOSE_TXT.stat().st_mtime, tz=et)
            if mtime >= today_1615:
                log.info("✓ Close snapshot ready (mtime: %s)", mtime.strftime("%H:%M:%S ET"))
                return True
        log.info("Waiting for 16:15 close snapshot... (%s)", UNIFIED_LEVELS_CLOSE_TXT)
        _time.sleep(CLOSE_SNAPSHOT_POLL_INTERVAL)

    log.warning(
        "Timed out waiting for close snapshot after %ds — proceeding with available data",
        timeout,
    )
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

    Thin shim — actual delivery + chunking lives in
    `scripts.libs_py.discord.send_summary` (audit §3.5).
    """
    _send_discord_summary(
        summary,
        webhook_key=webhook_key,
        repo_root=REPO_ROOT,
    )


def write_narrative_to_disk(summary: str, mode: str, ticker: str) -> Path:
    """Write the narrative to disk: latest (overwrite) + dated archive."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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


def write_cheatsheet_to_disk(cheat_sheet: str, mode: str, ticker: str) -> Path:
    """Write the cheat sheet to disk alongside the narrative for debugging/testing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")

    latest_path = OUTPUT_DIR / f"latest_cheatsheet_{mode}_{ticker}.txt"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(cheat_sheet)

    dated_path = OUTPUT_DIR / f"{date_str}_cheatsheet_{mode}_{ticker}.txt"
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(cheat_sheet)
    log.info("  Cheat sheet saved to %s", dated_path)

    return latest_path


def run_narrative(
    mode: str,
    model: str,
    tickers: list[str],
    target_date: date | None = None,
    send_discord: bool = True,
    test_mode: bool = False,
    sim_time: str | None = None,
) -> list[str]:
    """Main narrative generation flow (synchronous wrapper) for multiple tickers.

    When test_mode=True: saves the cheat sheet to disk but skips the LLM call
    and Discord send. This lets us iterate on the cheat sheet format without
    spending LLM tokens or spamming Discord.

    When sim_time is set (e.g. "2026-07-16 12:00"): simulates running at that
    ET date+time. Filters 1m data to <= sim_time, sets target_date to the
    correct trading day, and skips snapshot wait gates.
    """
    import pytz
    ET = pytz.timezone("America/New_York")

    # Parse simulation time if provided
    sim_dt = None
    if sim_time:
        try:
            # Parse "YYYY-MM-DD HH:MM" as ET time
            sim_dt = ET.localize(datetime.strptime(sim_time, "%Y-%m-%d %H:%M"))
            log.info("[SIM] Simulating run at %s ET", sim_dt.strftime("%Y-%m-%d %H:%M"))
        except ValueError:
            log.error("Invalid --time format. Use 'YYYY-MM-DD HH:MM' e.g. '2026-07-16 12:00'")
            return []

    # Determine trading day from sim_time or use target_date or today
    if sim_dt:
        # Trading day logic: if sim time is in the overnight session
        # (18:00-02:00 ET), the trading day is the NEXT calendar day.
        # Otherwise the trading day is the same calendar day.
        sim_hour = sim_dt.hour
        if sim_hour >= 18:
            # Asia session starts at 18:00 → trading day is next day
            target_date = sim_dt.date() + timedelta(days=1)
            # Skip weekends
            while target_date.weekday() in (5, 6):
                target_date += timedelta(days=1)
        else:
            target_date = sim_dt.date()
        log.info("[SIM] Trading day resolved to %s (weekday=%s)", target_date, target_date.weekday())
    elif target_date is None:
        target_date = datetime.now(ET).date()

    loader = get_dataloader(lookback_days=5)

    # Skip wait gates in test/sim mode
    if not test_mode and not sim_dt:
        if mode == "open":
            _wait_for_open_snapshot()
        elif mode == "close":
            _wait_for_close_snapshot()

    prompt_template = load_prompt_template(mode)
    
    results = []

    for ticker in tickers:
        log.info("Building cheat sheet for %s (mode: %s)...", ticker, mode)
        try:
            if mode == "intraday":
                cheat_sheet = build_intraday_context(loader=loader, ticker=ticker, target_date=target_date, now_et=sim_dt)
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
                    now_et=sim_dt,
                )
            
            log.info("✓ Cheat sheet assembled for %s (%d chars)", ticker, len(cheat_sheet))

            # Always save the cheat sheet for debugging/testing
            write_cheatsheet_to_disk(cheat_sheet, mode, ticker)

            # In test mode: skip LLM + Discord, just save the cheat sheet
            if test_mode:
                log.info("  [TEST MODE] Skipping LLM call — cheat sheet saved only.")
                results.append(cheat_sheet)
                continue

            # Skip LLM if the cheat sheet indicates markets closed or session complete
            if cheat_sheet.startswith("== MARKETS CLOSED ==") or cheat_sheet.startswith("== SESSION COMPLETE =="):
                log.info("  Skipping LLM — %s", cheat_sheet.split("\n")[0])
                write_narrative_to_disk(cheat_sheet, mode, ticker)
                if send_discord:
                    send_discord_summary(cheat_sheet)
                results.append(cheat_sheet)
                continue
            
            if mode == "close" and datetime.now().weekday() in [4, 5, 6]:  # Friday, Saturday, Sunday
                cheat_sheet += "\n\n== WEEK AHEAD CONTEXT ==\nSince it's the weekend, incorporate a 'Week Ahead' outlook focusing on upcoming macro events and structural setups for the week. The focus should be on Monday/Tuesday structure and the broader weekly thesis."
            
            prompt = prompt_template.replace("{{INSERT_CHEAT_SHEET}}", cheat_sheet)
            # Inject the per-instrument risk-params block (audit issue
            # §1.7). If the prompt doesn't have the
            # `{{INSERT_RISK_PARAMS}}` placeholder, `insert_risk_params`
            # is a no-op. The instruments are derived from the
            # NARRATIVE tickers via the NQ1→MNQ, ES1→MES map.
            _micro_map = {"NQ1": "MNQ", "ES1": "MES"}
            micro_instruments = [_micro_map.get(t, t) for t in tickers]
            prompt = insert_risk_params(prompt, instruments=micro_instruments)
            
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
    parser.add_argument("--test", action="store_true", help="Test mode: save cheat sheet only, skip LLM + Discord")
    parser.add_argument("--time", type=str, default=None, help="Simulate run at this ET time (format: 'YYYY-MM-DD HH:MM' e.g. '2026-07-16 12:00')")
    parser.add_argument("--tickers", type=str, nargs="+", default=["NQ1", "ES1"], help="List of tickers to process")
    args = parser.parse_args()

    try:
        run_narrative(
            mode=args.mode,
            model=args.model,
            tickers=args.tickers,
            send_discord=not args.no_discord and not args.test,
            test_mode=args.test,
            sim_time=args.time,
        )
    except KeyboardInterrupt:
        log.info("\\nCancelled by user")
    except Exception as e:
        log.error("Fatal error: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()