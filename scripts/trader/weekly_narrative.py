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
import re
import sys
from pathlib import Path
from datetime import date, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# Side-effect import: ensures the repo root is on sys.path so
# `from scripts.trader import ...` works without a per-file hack.
# See scripts/trader/_path_setup.py for the full rationale.
from scripts.trader import _path_setup  # noqa: F401

from scripts.trader.briefing_core import (
    REPO_ROOT,
    build_weekly_static_template,
    build_compact_weekly,
    get_prior_week_performance,
    load_weekly_briefing_from_db,
    save_narrative_to_db,
)

from scripts.libs_py.discord import send_summary as _send_discord_summary

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PROMPT_PATH = REPO_ROOT / "scripts" / "trader" / "prompts" / "weekly_briefing.md"
# Store weekly output alongside the daily levels in data/options/weekly/
# so everything is in one place (data/options/current for daily, weekly for weekly)
WEEKLY_OUTPUT_DIR = REPO_ROOT / "data" / "options" / "weekly"

# Ollama config
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
##DEFAULT_MODEL = "glm-5.2:cloud"
DEFAULT_MODEL = "gemma4:latest"
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


def extract_analysis_json(response: str) -> dict | None:
    """Extract structured weekly analysis payload from the LLM response."""
    match = re.search(r"<analysis_json>(.*?)</analysis_json>", response, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError as exc:
        log.warning("Failed to decode analysis_json: %s", exc)
        return None


def render_weekly_summary(static_template: str, analysis: dict, tickers: list[dict], events: list[dict]) -> str:
    """Merge bounded LLM analysis slots into the Python-rendered weekly template."""
    summary = static_template
    summary = summary.replace("{{PRIOR_WEEK_REVIEW_ANALYSIS}}", analysis.get("prior_week_review_analysis", "N/A"))
    summary = summary.replace("{{EXECUTIVE_RISK_CORE}}", analysis.get("executive_risk_core", "N/A"))

    event_impacts = analysis.get("event_impacts", {}) or {}
    for index, _event in enumerate(events):
        summary = summary.replace(f"{{{{EVENT_IMPACT_{index}}}}}", event_impacts.get(str(index), "N/A"))

    ticker_analysis = analysis.get("ticker_analysis", {}) or {}
    for ticker_block in tickers:
        ticker = ticker_block.get("ticker", "UNKNOWN")
        entry = ticker_analysis.get(ticker, {}) or {}
        summary = summary.replace(f"{{{{TRACK_NOTE_{ticker}}}}}", entry.get("track_note", "N/A"))
        summary = summary.replace(f"{{{{BULLISH_SCENARIO_{ticker}}}}}", entry.get("bullish", "N/A"))
        summary = summary.replace(f"{{{{BEARISH_SCENARIO_{ticker}}}}}", entry.get("bearish", "N/A"))
        summary = summary.replace(f"{{{{RANGE_SCENARIO_{ticker}}}}}", entry.get("range", "N/A"))

    weekly_trade_plan = analysis.get("weekly_trade_plan", []) or []
    if isinstance(weekly_trade_plan, list):
        trade_plan_md = "\n".join(f"- {item}" for item in weekly_trade_plan) if weekly_trade_plan else "- N/A"
    else:
        trade_plan_md = str(weekly_trade_plan)
    summary = summary.replace("{{WEEKLY_TRADE_PLAN}}", trade_plan_md)

    key_risks = analysis.get("key_risks", []) or []
    if isinstance(key_risks, list):
        key_risks_md = "\n".join(f"- {item}" for item in key_risks) if key_risks else "- N/A"
    else:
        key_risks_md = str(key_risks)
    summary = summary.replace("{{KEY_RISKS}}", key_risks_md)

    watch_list = analysis.get("watch_list", []) or []
    if isinstance(watch_list, list):
        watch_list_md = "\n".join(f"{idx}. {item}" for idx, item in enumerate(watch_list, start=1)) if watch_list else "1. N/A"
    else:
        watch_list_md = str(watch_list)
    summary = summary.replace("{{WATCH_LIST}}", watch_list_md)

    summary = re.sub(r"\{\{[^}]+\}\}", "N/A", summary)
    return summary


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
    """Send the summary to Discord via the configured webhook.

    Thin shim — actual delivery + chunking lives in
    `scripts.libs_py.discord.send_summary` (audit §3.5).
    """
    _send_discord_summary(
        summary,
        webhook_key=webhook_key,
        repo_root=REPO_ROOT,
    )


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
    selected_week_start = week_start
    if selected_week_start is None:
        today = date.today()
        selected_week_start = today - timedelta(days=today.weekday())

    briefing_data = await load_weekly_briefing_from_db(selected_week_start)
    if not briefing_data:
        log.warning("No briefing found for week_start=%s; falling back to latest.", selected_week_start)
        briefing_data = await load_weekly_briefing_from_db(None)
    if not briefing_data:
        raise RuntimeError("No weekly briefing found in DB. Run weekly_briefing.py first.")

    briefing_id = briefing_data["meta"]["id"]
    log.info("✓ Loaded briefing %s (%d tickers)", briefing_id, len(briefing_data["tickers"]))

    # 2. Build compact weekly briefing (saves ~800+ tokens vs raw TOON)
    toon = build_compact_weekly(briefing_data)
    log.info("✓ Compact briefing assembled (%d chars)", len(toon))

    static_template = build_weekly_static_template(briefing_data)
    log.info("✓ Static weekly template assembled (%d chars)", len(static_template))

    # 3. Build prompt
    briefing_week_start = date.fromisoformat(briefing_data["meta"]["week_start_date"][0:10])
    prior_week_review = await get_prior_week_performance(reference_week_start=briefing_week_start)
    prompt_template = load_prompt_template()
    prompt = prompt_template.replace("{{INSERT_STAGE_1_JSON_TOON}}", toon)
    prompt = prompt.replace("{{INSERT_PRIOR_WEEK_REVIEW}}", prior_week_review)
    prompt = prompt.replace("{{INSERT_STATIC_WEEKLY_TEMPLATE}}", static_template)
    log.info("✓ Prompt assembled (%d chars)", len(prompt))

    # 4. Call Ollama
    llm_response = call_ollama(prompt, model)
    analysis = extract_analysis_json(llm_response)
    if analysis:
        summary = render_weekly_summary(
            static_template,
            analysis,
            briefing_data.get("tickers", []),
            briefing_data.get("economic_events", []),
        )
        log.info("✓ Structured weekly summary rendered")
    else:
        summary = llm_response
        log.warning("Structured analysis missing; falling back to raw LLM output")

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