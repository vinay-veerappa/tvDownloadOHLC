"""
daily_narrative.py
==================
Stage 2: Daily Macro Briefing LLM Narrative Generator (Open & EOD).

Reads the latest daily EOD/Open briefing from the Prisma DB, assembles the
in-memory TOON JSON, calls the local Ollama LLM, and stores the
generated narrative back in the DB (summaryMd field).

Usage:
    python -m scripts.trader.daily_narrative --session eod [--model gemma4:31b-cloud]
    python -m scripts.trader.daily_narrative --session open [--model gemma4:31b-cloud]
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
    build_levels_markdown_table,
    load_daily_eod_from_db,
    save_narrative_to_db,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PROMPT_PATHS = {
    "open": REPO_ROOT / "scripts" / "trader" / "prompts" / "daily_open_update.md",
    "eod":  REPO_ROOT / "scripts" / "trader" / "prompts" / "daily_eod_update.md",
}

DAILY_OUTPUT_DIR = REPO_ROOT / "data" / "options" / "daily"
DISCORD_WEBHOOKS_PATH = REPO_ROOT / "discord_webhooks.json"

# Ollama config
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "glm-5.2:cloud"
FALLBACK_MODEL = "gemma4:31b-cloud"


def load_prompt_template(session: str) -> str:
    """Load the daily briefing prompt template (open or eod)."""
    path = PROMPT_PATHS.get(session.lower())
    if not path or not path.exists():
        raise FileNotFoundError(f"Prompt template not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_toon(briefing_data: dict) -> str:
    """Build the in-memory TOON JSON string from DB data."""
    return json.dumps(briefing_data, indent=2, ensure_ascii=False)


def call_ollama(prompt: str, model: str, timeout: int = 300) -> str:
    """Call the local Ollama instance to generate the narrative."""
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
                        "num_predict": 8192,
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
    """Send the summary to Discord via the configured webhook."""
    import requests

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


def write_summary_to_disk(summary: str, session: str) -> Path:
    """Write the narrative summary to disk for easy viewing."""
    DAILY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Latest (always overwrite)
    latest_path = DAILY_OUTPUT_DIR / f"latest_summary_{session}.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(summary)
    log.info("  Written to %s", latest_path)

    # Dated archive
    dated_path = DAILY_OUTPUT_DIR / f"{date_str}_summary_{session}.md"
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(summary)
    log.info("  Written to %s", dated_path)

    return latest_path


    return latest_path

async def get_trade_plan_for_eod() -> str:
    """Fetch the morning's Trade Plan from DB and format it for the EOD prompt."""
    from prisma import Prisma
    from datetime import datetime, timedelta, timezone
    
    db = Prisma()
    await db.connect()
    
    # Get trades created today for the Auto Prop Firm 50K account
    acc = await db.account.find_first(where={'name': 'Auto Prop Firm 50K'})
    if not acc:
        await db.disconnect()
        return "No Trade Plan found for today."
        
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    trades = await db.trade.find_many(
        where={
            'accountId': acc.id,
            'createdAt': {'gte': start_of_day}
        },
        include={'tradePlan': True},
        order={'createdAt': 'desc'}
    )
    
    if not trades:
        await db.disconnect()
        return "No Trade Plan found for today."
        
    res = "Morning Trade Plan Logic:\n"
    # Just take the first plan logic
    if trades[0].tradePlan:
        res += f"{trades[0].tradePlan.setup}\n\n"
        
    res += "Trades Scheduled:\n"
    for t in trades:
        res += f"- {t.ticker} {t.direction} | Entry: {t.entryPrice} | Stop: {t.stopLoss} | Target: {t.takeProfit}\n"
            
    await db.disconnect()
    return res

async def extract_and_save_trade_plan(summary: str):
    """Parse JSON plan block and save to DB."""
    import re
    import json
    from prisma import Prisma
    from datetime import datetime, timezone
    
    match = re.search(r'<plan_json>(.*?)</plan_json>', summary, re.DOTALL)
    if not match:
        log.warning("No <plan_json> found in Open narrative output.")
        return
        
    try:
        plan_data = json.loads(match.group(1).strip())
        db = Prisma()
        await db.connect()
        
        acc = await db.account.find_first(where={'name': 'Auto Prop Firm 50K'})
        if not acc:
            log.warning("Account 'Auto Prop Firm 50K' not found!")
            await db.disconnect()
            return
            
        now = datetime.now(timezone.utc)
        logic = plan_data.get('logic', 'No logic provided')
        
        for trade in plan_data.get('trades', []):
            asset = trade.get('asset', 'MES')
            t = await db.trade.create(data={
                'ticker': asset,
                'entryDate': now,
                'quantity': 1,
                'direction': trade.get('direction', 'LONG'),
                'status': 'PENDING',
                'accountId': acc.id,
                'entryPrice': float(trade.get('entryPrice', 0.0)),
                'stopLoss': float(trade.get('stopLoss', 0.0)),
                'takeProfit': float(trade.get('takeProfit', 0.0))
            })
            
            await db.tradeplan.create(data={
                'date': now,
                'instrument': asset,
                'setup': logic,
                'linkedTradeId': t.id
            })
            
        log.info("✓ Trade Plan saved to DB.")
        await db.disconnect()
    except Exception as e:
        log.error(f"Failed to parse and save Trade Plan: {e}")

async def run_narrative(model: str, session: str, target_date: date | None = None) -> str:
    """Main narrative generation flow.

    1. Load daily EOD/Open update from DB
    2. Build TOON in memory
    3. Call Ollama
    4. Store narrative back in DB
    5. Optionally send to Discord
    """
    log.info("Loading daily update from DB (session: %s)...", session)
    briefing_data = await load_daily_eod_from_db(target_date, session_type=session)
    if not briefing_data:
        raise RuntimeError(f"No daily update found in DB. Run daily_eod_update.py --session {session} first.")

    eod_id = briefing_data["meta"]["id"]
    log.info("✓ Loaded daily update %s (%d tickers)", eod_id, len(briefing_data["tickers"]))

    # Build TOON in memory
    toon = build_toon(briefing_data)
    log.info("✓ TOON assembled (%d chars)", len(toon))

    # Build tables
    nq_table = build_levels_markdown_table("QQQ")
    es_table = build_levels_markdown_table("SPY")
    levels_md = f"{nq_table}\n\n{es_table}"

    # Build prompt
    prompt_template = load_prompt_template(session)
    placeholder = "{{INSERT_DAILY_OPEN_JSON}}" if session.lower() == "open" else "{{INSERT_DAILY_EOD_JSON}}"
    prompt = prompt_template.replace(placeholder, toon)
    prompt = prompt.replace("{{INSERT_LEVELS_TABLE}}", levels_md)
    
    if session.lower() == "eod":
        trade_plan_md = await get_trade_plan_for_eod()
        prompt = prompt.replace("{{INSERT_TRADE_PLAN}}", trade_plan_md)
        
    log.info("✓ Prompt assembled (%d chars)", len(prompt))

    # Call Ollama
    summary = call_ollama(prompt, model)
    log.info("✓ Narrative generated")
    
    if session.lower() == "open":
        await extract_and_save_trade_plan(summary)

    # Store in DB
    await save_narrative_to_db(briefing_id="", summary_md=summary, is_daily=True, eod_id=eod_id)
    log.info("  Narrative stored in DB")

    # Write to disk
    write_summary_to_disk(summary, session)

    # Discord (always send to macro-alerts channel)
    send_discord_summary(summary, webhook_key="macro-alerts")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Daily Macro Briefing LLM Narrative")
    parser.add_argument("--session", required=True, choices=["open", "eod"], help="Daily session type")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--date", type=str, default=None, help="Target date (YYYY-MM-DD)")
    args = parser.parse_args()

    target_date = None
    if args.date:
        target_date = date.fromisoformat(args.date)

    summary = asyncio.run(run_narrative(args.model, args.session, target_date))

    # Print to console for immediate viewing
    print("\n" + "=" * 60)
    print(summary)
    print("=" * 60)

    return summary


if __name__ == "__main__":
    main()
