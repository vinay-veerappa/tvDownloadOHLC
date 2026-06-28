"""
weekly_narrative.py
====================
Stage 2: Weekly Macro Briefing LLM Narrative Generator.

Reads the latest weekly briefing from the Prisma DB, assembles the
in-memory TOON JSON, calls the local Ollama LLM, and stores the
generated narrative back in the DB (summaryMd field).

Usage:
    python -m scripts.trader.weekly_narrative [--model qwen3] [--discord]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.trader.briefing_core import (
    REPO_ROOT,
    load_weekly_briefing_from_db,
    save_narrative_to_db,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PROMPT_PATH = REPO_ROOT / "scripts" / "trader" / "prompts" / "weekly_briefing.md"
# Store weekly output alongside the daily levels in data/options/weekly/
# so everything is in one place (data/options/current for daily, weekly for weekly)
WEEKLY_OUTPUT_DIR = REPO_ROOT / "data" / "options" / "weekly"
DISCORD_WEBHOOKS_PATH = REPO_ROOT / "discord_webhooks.json"

# Ollama config
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "glm-5.2:cloud"
FALLBACK_MODEL = "gemma4:31b-cloud"


def load_prompt_template() -> str:
    """Load the weekly briefing prompt template."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def build_toon(briefing_data: dict) -> str:
    """Build the in-memory TOON JSON string from DB data.

    This is the only place the JSON is assembled — it's transient,
    passed to the LLM, and never persisted as a file.
    """
    return json.dumps(briefing_data, indent=2, ensure_ascii=False)


def call_ollama(prompt: str, model: str, timeout: int = 300) -> str:
    """Call the local Ollama instance to generate the narrative.

    Falls back to FALLBACK_MODEL if the primary model fails.
    """
    import requests

    for attempt_model in [model, FALLBACK_MODEL if model != FALLBACK_MODEL else None]:
        if not attempt_model:
            continue
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
                        "num_predict": -1,
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
    """Send the summary to Discord via the configured webhook.

    Uses discord_webhooks.json at the repo root. The webhook key
    determines which channel (default: "macro-alerts").
    """
    import requests

    # Load webhook URL from config
    webhook_url = None
    if DISCORD_WEBHOOKS_PATH.exists():
        with open(DISCORD_WEBHOOKS_PATH, "r", encoding="utf-8") as f:
            import json as _json
            webhooks = _json.load(f)
        webhook_url = webhooks.get(webhook_key)

    if not webhook_url:
        log.warning("No Discord webhook found for key '%s' — skipping Discord.", webhook_key)
        return

    # Split into chunks if needed (Discord 2000 char limit)
    chunks = []
    if len(summary) > 1900:
        # Split on section headers
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


def write_summary_to_disk(summary: str, briefing_id: str) -> Path:
    """Write the narrative summary to disk for easy viewing.

    Writes to:
      - data/options/weekly/latest_summary.md  (always overwritten)
      - data/options/weekly/{date}_summary.md   (dated archive)
    """
    WEEKLY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Latest (always overwrite)
    latest_path = WEEKLY_OUTPUT_DIR / "latest_summary.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(summary)
    log.info("  Written to %s", latest_path)

    # Dated archive
    dated_path = WEEKLY_OUTPUT_DIR / f"{date_str}_summary.md"
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(summary)
    log.info("  Written to %s", dated_path)

    return latest_path


async def run_narrative(model: str, week_start: date | None = None) -> str:
    """Main narrative generation flow.

    1. Load briefing from DB
    2. Build TOON in memory
    3. Call Ollama
    4. Store narrative back in DB
    5. Optionally send to Discord
    """
    # 1. Load from DB
    log.info("Loading weekly briefing from DB...")
    briefing_data = await load_weekly_briefing_from_db(week_start)
    if not briefing_data:
        raise RuntimeError("No weekly briefing found in DB. Run weekly_briefing.py first.")

    briefing_id = briefing_data["meta"]["id"]
    log.info("✓ Loaded briefing %s (%d tickers)", briefing_id, len(briefing_data["tickers"]))

    # 2. Build TOON in memory
    toon = build_toon(briefing_data)
    log.info("✓ TOON assembled (%d chars)", len(toon))

    # 3. Build prompt
    prompt_template = load_prompt_template()
    prompt = prompt_template.replace("{{INSERT_STAGE_1_JSON_TOON}}", toon)
    log.info("✓ Prompt assembled (%d chars)", len(prompt))

    # 4. Call Ollama
    summary = call_ollama(prompt, model)
    log.info("✓ Narrative generated")

    # 5. Store in DB
    await save_narrative_to_db(briefing_id, summary, is_daily=False)
    log.info("  Narrative stored in DB")

    # 6. Write to disk (always — for easy viewing)
    write_summary_to_disk(summary, briefing_id)

    # 7. Discord (always send to macro-alerts channel)
    send_discord_summary(summary, webhook_key="macro-alerts")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Weekly Macro Briefing LLM Narrative")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--week-start", type=str, default=None, help="Week start date (YYYY-MM-DD)")
    args = parser.parse_args()

    week_start = None
    if args.week_start:
        week_start = date.fromisoformat(args.week_start)

    summary = asyncio.run(run_narrative(args.model, week_start))

    # Print to console for immediate viewing
    print("\n" + "=" * 60)
    print(summary)
    print("=" * 60)

    return summary


if __name__ == "__main__":
    main()