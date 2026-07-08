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
import re
import sys
from pathlib import Path
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.trader.briefing_core import (
    REPO_ROOT,
    build_levels_markdown_table,
    build_compact_briefing,
    build_compact_eod,
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
DEFAULT_MODEL = "gemma4:latest"  # glm-5.2:cloud"
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


def extract_analysis_json(response: str) -> dict | None:
    """Extract structured analysis payload from the LLM response."""
    match = re.search(r"<analysis_json>(.*?)</analysis_json>", response, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError as exc:
        log.warning("Failed to decode analysis_json: %s", exc)
        return None


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


async def get_trade_plan_for_eod() -> str:
    """Fetch the morning's Trade Plan from DB and format it for the EOD prompt.

    Includes trade status and P&L for continuity — the EOD LLM needs to see
    what was planned, what triggered, and what the current drawdown state is.
    """
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
        status = t.status or "PENDING"
        res += f"- {t.ticker} {t.direction} | Entry: {t.entryPrice} | Stop: {t.stopLoss} | Target: {t.takeProfit} | Status: {status}\n"
            
    await db.disconnect()
    return res


async def get_previous_eod_plan() -> str:
    """Fetch the previous EOD's next-day plan for the open narrative.

    This provides continuity: the EOD narrative generates tomorrow's plan,
    and the next morning's open narrative should check what was planned
    overnight and whether the levels have shifted.
    """
    from prisma import Prisma
    from datetime import datetime, timedelta, timezone
    
    db = Prisma()
    await db.connect()
    
    acc = await db.account.find_first(where={'name': 'Auto Prop Firm 50K'})
    if not acc:
        await db.disconnect()
        return "No previous plan found."
    
    # Look for trades created in the last 24 hours (covers EOD plan from yesterday)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    
    trades = await db.trade.find_many(
        where={
            'accountId': acc.id,
            'createdAt': {'gte': cutoff}
        },
        include={'tradePlan': True},
        order={'createdAt': 'desc'}
    )
    
    if not trades:
        await db.disconnect()
        return "No previous EOD plan found."
    
    # Separate today's trades (already created by open narrative) from yesterday's EOD plan
    start_of_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_trades = [t for t in trades if t.createdAt < start_of_today]
    
    if not yesterday_trades:
        await db.disconnect()
        return "No previous EOD plan found."
    
    res = "Previous EOD Plan (overnight):\n"
    if yesterday_trades[0].tradePlan:
        res += f"Logic: {yesterday_trades[0].tradePlan.setup}\n\n"
    
    res += "Planned Trades:\n"
    for t in yesterday_trades:
        status = t.status or "PENDING"
        res += f"- {t.ticker} {t.direction} | Entry: {t.entryPrice} | Stop: {t.stopLoss} | Target: {t.takeProfit} | Status: {status}\n"
    
    await db.disconnect()
    return res


async def get_drawdown_status() -> str:
    """Query DB for cumulative P&L and compute trailing drawdown remaining.

    Returns a formatted string for the EOD prompt showing:
    - Cumulative P&L per instrument
    - Trailing drawdown remaining ($2000 - |cumulative loss|)
    - Trade count, win rate
    - Days to potential breach at current loss rate
    """
    from prisma import Prisma
    from datetime import datetime, timezone
    
    db = Prisma()
    await db.connect()
    
    acc = await db.account.find_first(where={'name': 'Auto Prop Firm 50K'})
    if not acc:
        await db.disconnect()
        return "Drawdown data unavailable (account not found)."
    
    # Get all closed trades for this account
    trades = await db.trade.find_many(
        where={
            'accountId': acc.id,
            'status': {'in': ['CLOSED', 'WIN', 'LOSS', 'STOPPED', 'FILLED']}
        },
        order={'entryDate': 'asc'}
    )
    
    if not trades:
        await db.disconnect()
        return "No closed trades yet. Drawdown: $2000 remaining (full)."
    
    # Compute per-instrument stats
    instruments = {}
    for t in trades:
        ticker = t.ticker or 'UNKNOWN'
        pnl = t.pnl or 0.0
        if ticker not in instruments:
            instruments[ticker] = {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0}
        instruments[ticker]['trades'] += 1
        instruments[ticker]['pnl'] += pnl
        if pnl > 0:
            instruments[ticker]['wins'] += 1
        elif pnl < 0:
            instruments[ticker]['losses'] += 1
    
    total_pnl = sum(v['pnl'] for v in instruments.values())
    total_trades = sum(v['trades'] for v in instruments.values())
    total_wins = sum(v['wins'] for v in instruments.values())
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    # Trailing drawdown: $2000 - |cumulative loss if negative|
    if total_pnl >= 0:
        dd_remaining = 2000.0
        dd_status = "Account in profit — full drawdown available."
    else:
        dd_remaining = 2000.0 - abs(total_pnl)
        if dd_remaining <= 0:
            dd_status = "ACCOUNT BLOWN — drawdown limit breached."
        else:
            avg_daily_loss = abs(total_pnl) / max(1, len(set(t.entryDate.date() for t in trades if t.entryDate)))
            days_to_breach = int(dd_remaining / avg_daily_loss) if avg_daily_loss > 0 else 999
            dd_status = f"Days to breach at current rate: ~{days_to_breach}"
    
    lines = [
        f"Drawdown Status:",
        f"  Cumulative P&L: ${total_pnl:,.2f}",
        f"  Trailing DD remaining: ${dd_remaining:,.2f} of $2,000",
        f"  Total trades: {total_trades} | Win rate: {win_rate:.1f}%",
        f"  Status: {dd_status}",
    ]
    
    for ticker, stats in sorted(instruments.items()):
        wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
        lines.append(f"  {ticker}: {stats['trades']} trades | P&L ${stats['pnl']:,.2f} | WR {wr:.0f}%")
    
    await db.disconnect()
    return "\n".join(lines)


async def get_level_accuracy(briefing_data: dict) -> str:
    """Pre-compute level accuracy audit from the EOD briefing data.

    Uses the level_flags from the compact EOD to show which levels held vs broke.
    """
    tickers = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
    
    lines = ["Level Accuracy Audit:"]
    
    for proxy_name, ticker_name in [("SPY", "MES"), ("QQQ", "MNQ")]:
        t = tickers.get(proxy_name)
        if not t:
            continue
        
        anchor = t.get("weekly_anchor", {})
        interactions = t.get("level_interactions", {})
        
        cw = anchor.get("call_wall", "?")
        pw = anchor.get("put_wall", "?")
        em_u = anchor.get("today_em_upper", "?")
        em_l = anchor.get("today_em_lower", "?")
        
        cw_tested = "TESTED" if interactions.get("call_wall_tested") else "not tested"
        cw_broken = "BROKEN" if interactions.get("call_wall_broken") else "held"
        pw_tested = "TESTED" if interactions.get("put_wall_tested") else "not tested"
        pw_broken = "BROKEN" if interactions.get("put_wall_broken") else "held"
        em_u_status = "BROKEN" if interactions.get("em_upper_broken") else ("tested" if interactions.get("em_upper_tested") else "held")
        em_l_status = "BROKEN" if interactions.get("em_lower_broken") else ("tested" if interactions.get("em_lower_tested") else "held")
        
        lines.append(f"  {proxy_name} -> {ticker_name}:")
        lines.append(f"    Call Wall {cw}: {cw_tested}, {cw_broken}")
        lines.append(f"    Put Wall {pw}: {pw_tested}, {pw_broken}")
        lines.append(f"    EM Upper {em_u}: {em_u_status}")
        lines.append(f"    EM Lower {em_l}: {em_l_status}")
    
    return "\n".join(lines)

async def extract_and_save_trade_plan(summary: str):
    """Parse JSON plan block and save to DB.

    Updated schema (v2) supports:
      - regime, stopDistancePts, contracts, dollarRisk, rewardToRisk
      - noTrade / noTradeReason for skip conditions
    Falls back gracefully if new fields are absent (v1 compatibility).
    """
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

            # Skip no-trade entries — still log them for the EOD review
            if trade.get('noTrade', False):
                reason = trade.get('noTradeReason', 'No reason provided')
                log.info("  %s: NO TRADE — %s", asset, reason)
                continue

            contracts = int(trade.get('contracts', 1))
            if contracts < 1:
                contracts = 1  # safety floor for v1 compatibility

            t = await db.trade.create(data={
                'ticker': asset,
                'entryDate': now,
                'quantity': contracts,
                'direction': trade.get('direction', 'LONG'),
                'status': 'PENDING',
                'accountId': acc.id,
                'entryPrice': float(trade.get('entryPrice', 0.0)),
                'stopLoss': float(trade.get('stopLoss', 0.0)),
                'takeProfit': float(trade.get('takeProfit', 0.0))
            })

            # Build setup string with new risk fields if available
            setup_parts = [logic]
            if trade.get('regime'):
                setup_parts.append(f"Regime: {trade['regime']}")
            if trade.get('stopDistancePts'):
                setup_parts.append(f"Stop: {trade['stopDistancePts']} pts")
            if trade.get('dollarRisk'):
                setup_parts.append(f"Risk: ${trade['dollarRisk']}")
            if trade.get('rewardToRisk'):
                setup_parts.append(f"R:R = 1:{trade['rewardToRisk']}")
            setup = " | ".join(setup_parts)

            await db.tradeplan.create(data={
                'date': now,
                'instrument': asset,
                'setup': setup,
                'linkedTradeId': t.id
            })

        log.info("✓ Trade Plan saved to DB.")
        await db.disconnect()
    except Exception as e:
        log.error(f"Failed to parse and save Trade Plan: {e}")


def _fmt_news_events(events: list[dict]) -> str:
    if not events:
        return "No market-moving economic events scheduled today."

    lines: list[str] = []
    for ev in events:
        status = "PASSED" if ev.get("passed") else "UPCOMING"
        lines.append(f"- {ev.get('time_et', '?')} [{ev.get('impact', '?')}] {ev.get('name', '?')} -- {status}")
    return "\n".join(lines)


def _default_plan_json(briefing_data: dict) -> dict:
    tickers = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
    spy_regime = tickers.get("SPY", {}).get("regime_check", {}).get("current_regime", "UNKNOWN")
    qqq_regime = tickers.get("QQQ", {}).get("regime_check", {}).get("current_regime", "UNKNOWN")

    return {
        "logic": "N/A",
        "trades": [
            {
                "asset": "MES",
                "direction": "LONG",
                "regime": spy_regime,
                "entryPrice": 0,
                "stopLoss": 0,
                "takeProfit": 0,
                "stopDistancePts": 0,
                "contracts": 0,
                "dollarRisk": 0,
                "rewardToRisk": 0,
                "noTrade": False,
                "noTradeReason": "",
            },
            {
                "asset": "MNQ",
                "direction": "LONG",
                "regime": qqq_regime,
                "entryPrice": 0,
                "stopLoss": 0,
                "takeProfit": 0,
                "stopDistancePts": 0,
                "contracts": 0,
                "dollarRisk": 0,
                "rewardToRisk": 0,
                "noTrade": False,
                "noTradeReason": "",
            },
        ],
    }


def _replace_slot(template: str, key: str, value: str) -> str:
    return template.replace(f"{{{{{key}}}}}", value if value else "N/A")


def build_open_static_template(briefing_data: dict, levels_md: str) -> str:
    """Build deterministic open markdown skeleton in Python."""
    from datetime import datetime

    tickers = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
    events = briefing_data.get("economic_events", [])
    meta = briefing_data.get("meta", {})

    # Extract date
    date_str = meta.get("date", "")
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str)
            day_name = dt.strftime("%A")
            date_label = dt.strftime("%Y-%m-%d")
        except Exception:
            date_label = date_str
            day_name = ""
    else:
        date_label = "[Date]"
        day_name = "[Day]"

    # Extract regime info from compact briefing fields
    spy = tickers.get("SPY", {})
    qqq = tickers.get("QQQ", {})

    spy_regime = spy.get("regime_check", {}).get("current_regime", "UNKNOWN")
    qqq_regime = qqq.get("regime_check", {}).get("current_regime", "UNKNOWN")
    spy_bias = spy.get("weekly_anchor", {}).get("mandated_track", "UNKNOWN")
    qqq_bias = qqq.get("weekly_anchor", {}).get("mandated_track", "UNKNOWN")

    news_section = _fmt_news_events(events)

    default_plan_json = json.dumps(_default_plan_json(briefing_data), ensure_ascii=False)

    template = f"""## RTH OPEN SETUP -- {date_label} ({day_name})

{levels_md}

### Regime
SPY->MES: {spy_regime} | Bias: {spy_bias}
QQQ->MNQ: {qqq_regime} | Bias: {qqq_bias}

### Overnight Delta
{{{{OVERNIGHT_DELTA}}}}

### News
{news_section}

### Dynamic
{{{{DYNAMIC}}}}

### Trade Plan

**MES** (SPY proxy, risk cap $150):
- Regime: {{{{MES_REGIME}}}}
- Logic: {{{{MES_LOGIC}}}}
- Entry: {{{{MES_ENTRY}}}}
- Stop: {{{{MES_STOP}}}} | Stop dist: {{{{MES_STOP_DIST}}}} pts | Contracts: {{{{MES_CONTRACTS}}}}
- Target: {{{{MES_TARGET}}}} | R:R: {{{{MES_RR}}}}

**MNQ** (QQQ proxy, risk cap $100):
- Regime: {{{{MNQ_REGIME}}}}
- Logic: {{{{MNQ_LOGIC}}}}
- Entry: {{{{MNQ_ENTRY}}}}
- Stop: {{{{MNQ_STOP}}}} | Stop dist: {{{{MNQ_STOP_DIST}}}} pts | Contracts: {{{{MNQ_CONTRACTS}}}}
- Target: {{{{MNQ_TARGET}}}} | R:R: {{{{MNQ_RR}}}}

### Risk Summary
- {{{{RISK_SUMMARY_LINE_1}}}}
- {{{{RISK_SUMMARY_LINE_2}}}}
- {{{{RISK_SUMMARY_LINE_3}}}}

<plan_json>
{{{{PLAN_JSON}}}}
</plan_json>"""

    return template.replace("{{PLAN_JSON}}", default_plan_json)


def build_eod_static_template(briefing_data: dict, levels_md: str) -> str:
    """Build deterministic EOD markdown skeleton in Python."""
    from datetime import datetime

    tickers = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
    meta = briefing_data.get("meta", {})

    date_str = meta.get("date", "")
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str)
            day_name = dt.strftime("%A")
            date_label = dt.strftime("%Y-%m-%d")
        except Exception:
            date_label = date_str
            day_name = ""
    else:
        date_label = "[Date]"
        day_name = "[Day]"

    spy_regime = tickers.get("SPY", {}).get("regime_check", {}).get("current_regime", "UNKNOWN")
    qqq_regime = tickers.get("QQQ", {}).get("regime_check", {}).get("current_regime", "UNKNOWN")
    default_plan_json = json.dumps(_default_plan_json(briefing_data), ensure_ascii=False)

    template = f"""## EOD DAILY REVIEW -- {date_label} ({day_name})

{levels_md}

### Today's Regime
SPY->MES: {spy_regime} | Levels shown below are MES levels translated from SPY
QQQ->MNQ: {qqq_regime} | Levels shown below are MNQ levels translated from QQQ

### Session Log
**MES**: {{{{SESSION_MES}}}}
**MNQ**: {{{{SESSION_MNQ}}}}
**Daily P&L**: {{{{SESSION_DAILY_PNL}}}}

### Drawdown Analysis
{{{{DRAWDOWN_ANALYSIS}}}}

### Level Accuracy Review
{{{{LEVEL_ACCURACY_REVIEW}}}}

### Trade Quality
{{{{TRADE_QUALITY}}}}

### Note of the Day
{{{{NOTE_OF_DAY}}}}

### Overnight Considerations
{{{{OVERNIGHT_CONSIDERATIONS}}}}

### Tomorrow's Setup

**MES** (SPY-derived levels) (risk cap $150):
- Regime: {{{{TM_MES_REGIME}}}}
- Logic: {{{{TM_MES_LOGIC}}}}
- Entry: {{{{TM_MES_ENTRY}}}}
- Stop: {{{{TM_MES_STOP}}}} | Stop dist: {{{{TM_MES_STOP_DIST}}}} pts | Contracts: {{{{TM_MES_CONTRACTS}}}}
- Target: {{{{TM_MES_TARGET}}}} | R:R: {{{{TM_MES_RR}}}}

**MNQ** (QQQ-derived levels) (risk cap $100):
- Regime: {{{{TM_MNQ_REGIME}}}}
- Logic: {{{{TM_MNQ_LOGIC}}}}
- Entry: {{{{TM_MNQ_ENTRY}}}}
- Stop: {{{{TM_MNQ_STOP}}}} | Stop dist: {{{{TM_MNQ_STOP_DIST}}}} pts | Contracts: {{{{TM_MNQ_CONTRACTS}}}}
- Target: {{{{TM_MNQ_TARGET}}}} | R:R: {{{{TM_MNQ_RR}}}}

### Tomorrow's Risk Budget
- {{{{TM_RISK_LINE_1}}}}
- {{{{TM_RISK_LINE_2}}}}

<plan_json>
{{{{PLAN_JSON}}}}
</plan_json>"""

    return template.replace("{{PLAN_JSON}}", default_plan_json)


def render_open_summary(static_template: str, analysis: dict) -> str:
    """Merge bounded open-session analysis slots into static template."""
    summary = static_template

    summary = _replace_slot(summary, "OVERNIGHT_DELTA", analysis.get("overnight_delta", "N/A"))
    summary = _replace_slot(summary, "DYNAMIC", analysis.get("dynamic", "N/A"))

    mes = analysis.get("mes", {}) or {}
    summary = _replace_slot(summary, "MES_REGIME", str(mes.get("regime", "N/A")))
    summary = _replace_slot(summary, "MES_LOGIC", str(mes.get("logic", "N/A")))
    summary = _replace_slot(summary, "MES_ENTRY", str(mes.get("entry", "N/A")))
    summary = _replace_slot(summary, "MES_STOP", str(mes.get("stop", "N/A")))
    summary = _replace_slot(summary, "MES_STOP_DIST", str(mes.get("stop_dist", "N/A")))
    summary = _replace_slot(summary, "MES_CONTRACTS", str(mes.get("contracts", "N/A")))
    summary = _replace_slot(summary, "MES_TARGET", str(mes.get("target", "N/A")))
    summary = _replace_slot(summary, "MES_RR", str(mes.get("rr", "N/A")))

    mnq = analysis.get("mnq", {}) or {}
    summary = _replace_slot(summary, "MNQ_REGIME", str(mnq.get("regime", "N/A")))
    summary = _replace_slot(summary, "MNQ_LOGIC", str(mnq.get("logic", "N/A")))
    summary = _replace_slot(summary, "MNQ_ENTRY", str(mnq.get("entry", "N/A")))
    summary = _replace_slot(summary, "MNQ_STOP", str(mnq.get("stop", "N/A")))
    summary = _replace_slot(summary, "MNQ_STOP_DIST", str(mnq.get("stop_dist", "N/A")))
    summary = _replace_slot(summary, "MNQ_CONTRACTS", str(mnq.get("contracts", "N/A")))
    summary = _replace_slot(summary, "MNQ_TARGET", str(mnq.get("target", "N/A")))
    summary = _replace_slot(summary, "MNQ_RR", str(mnq.get("rr", "N/A")))

    risk_summary = analysis.get("risk_summary", {}) or {}
    summary = _replace_slot(
        summary,
        "RISK_SUMMARY_LINE_1",
        str(risk_summary.get("line_1", "MES: $N/A | MNQ: $N/A")),
    )
    summary = _replace_slot(
        summary,
        "RISK_SUMMARY_LINE_2",
        str(risk_summary.get("line_2", "Combined same-dir: $N/A")),
    )
    summary = _replace_slot(
        summary,
        "RISK_SUMMARY_LINE_3",
        str(risk_summary.get("line_3", "Daily stop remaining: MES $450 | MNQ $300")),
    )

    plan_json = analysis.get("plan_json")
    if isinstance(plan_json, dict):
        summary = re.sub(
            r"<plan_json>.*?</plan_json>",
            f"<plan_json>\n{json.dumps(plan_json, ensure_ascii=False)}\n</plan_json>",
            summary,
            flags=re.DOTALL,
        )

    summary = re.sub(r"\{\{[^}]+\}\}", "N/A", summary)
    return summary


def render_eod_summary(static_template: str, analysis: dict) -> str:
    """Merge bounded EOD-session analysis slots into static template."""
    summary = static_template

    session_log = analysis.get("session_log", {}) or {}
    summary = _replace_slot(summary, "SESSION_MES", str(session_log.get("mes", "N/A")))
    summary = _replace_slot(summary, "SESSION_MNQ", str(session_log.get("mnq", "N/A")))
    summary = _replace_slot(summary, "SESSION_DAILY_PNL", str(session_log.get("daily_pnl", "N/A")))

    summary = _replace_slot(summary, "DRAWDOWN_ANALYSIS", str(analysis.get("drawdown_analysis", "N/A")))
    summary = _replace_slot(summary, "LEVEL_ACCURACY_REVIEW", str(analysis.get("level_accuracy_review", "N/A")))
    summary = _replace_slot(summary, "TRADE_QUALITY", str(analysis.get("trade_quality", "N/A")))
    summary = _replace_slot(summary, "NOTE_OF_DAY", str(analysis.get("note_of_day", "N/A")))
    summary = _replace_slot(summary, "OVERNIGHT_CONSIDERATIONS", str(analysis.get("overnight_considerations", "N/A")))

    tm_mes = analysis.get("tomorrow_mes", {}) or {}
    summary = _replace_slot(summary, "TM_MES_REGIME", str(tm_mes.get("regime", "N/A")))
    summary = _replace_slot(summary, "TM_MES_LOGIC", str(tm_mes.get("logic", "N/A")))
    summary = _replace_slot(summary, "TM_MES_ENTRY", str(tm_mes.get("entry", "N/A")))
    summary = _replace_slot(summary, "TM_MES_STOP", str(tm_mes.get("stop", "N/A")))
    summary = _replace_slot(summary, "TM_MES_STOP_DIST", str(tm_mes.get("stop_dist", "N/A")))
    summary = _replace_slot(summary, "TM_MES_CONTRACTS", str(tm_mes.get("contracts", "N/A")))
    summary = _replace_slot(summary, "TM_MES_TARGET", str(tm_mes.get("target", "N/A")))
    summary = _replace_slot(summary, "TM_MES_RR", str(tm_mes.get("rr", "N/A")))

    tm_mnq = analysis.get("tomorrow_mnq", {}) or {}
    summary = _replace_slot(summary, "TM_MNQ_REGIME", str(tm_mnq.get("regime", "N/A")))
    summary = _replace_slot(summary, "TM_MNQ_LOGIC", str(tm_mnq.get("logic", "N/A")))
    summary = _replace_slot(summary, "TM_MNQ_ENTRY", str(tm_mnq.get("entry", "N/A")))
    summary = _replace_slot(summary, "TM_MNQ_STOP", str(tm_mnq.get("stop", "N/A")))
    summary = _replace_slot(summary, "TM_MNQ_STOP_DIST", str(tm_mnq.get("stop_dist", "N/A")))
    summary = _replace_slot(summary, "TM_MNQ_CONTRACTS", str(tm_mnq.get("contracts", "N/A")))
    summary = _replace_slot(summary, "TM_MNQ_TARGET", str(tm_mnq.get("target", "N/A")))
    summary = _replace_slot(summary, "TM_MNQ_RR", str(tm_mnq.get("rr", "N/A")))

    tm_risk = analysis.get("tomorrow_risk_budget", {}) or {}
    summary = _replace_slot(summary, "TM_RISK_LINE_1", str(tm_risk.get("line_1", "MES: $N/A | MNQ: $N/A")))
    summary = _replace_slot(summary, "TM_RISK_LINE_2", str(tm_risk.get("line_2", "Daily stop remaining: MES $450 | MNQ $300")))

    plan_json = analysis.get("plan_json")
    if isinstance(plan_json, dict):
        summary = re.sub(
            r"<plan_json>.*?</plan_json>",
            f"<plan_json>\n{json.dumps(plan_json, ensure_ascii=False)}\n</plan_json>",
            summary,
            flags=re.DOTALL,
        )

    summary = re.sub(r"\{\{[^}]+\}\}", "N/A", summary)
    return summary


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

    # Build compact pre-processed summary (saves ~1000 tokens vs raw TOON JSON)
    # For open session: use compact briefing (only SPY/QQQ, pre-computed fields)
    # For eod session: use compact EOD (drops SPX, strips review-only fields)
    if session.lower() == "open":
        toon = build_compact_briefing(briefing_data)
    else:
        toon = build_compact_eod(briefing_data)
    log.info("✓ Briefing assembled (%d chars)", len(toon))

    # Build tables
    nq_table = build_levels_markdown_table("QQQ")
    es_table = build_levels_markdown_table("SPY")
    levels_md = f"{nq_table}\n\n{es_table}"

    # Build static template and prompt
    if session.lower() == "open":
        static_template = build_open_static_template(briefing_data, levels_md)
    else:
        static_template = build_eod_static_template(briefing_data, levels_md)

    prompt_template = load_prompt_template(session)
    placeholder = "{{INSERT_DAILY_OPEN_JSON}}" if session.lower() == "open" else "{{INSERT_DAILY_EOD_JSON}}"
    prompt = prompt_template.replace(placeholder, toon)
    prompt = prompt.replace("{{INSERT_STATIC_DAILY_TEMPLATE}}", static_template)
    
    if session.lower() == "eod":
        trade_plan_md = await get_trade_plan_for_eod()
        prompt = prompt.replace("{{INSERT_TRADE_PLAN}}", trade_plan_md)
        # Inject drawdown status and level accuracy audit
        drawdown_md = await get_drawdown_status()
        prompt = prompt.replace("{{INSERT_DRAWDOWN_STATUS}}", drawdown_md)
        level_audit_md = await get_level_accuracy(briefing_data)
        prompt = prompt.replace("{{INSERT_LEVEL_AUDIT}}", level_audit_md)
    elif session.lower() == "open":
        # Inject previous EOD's next-day plan for overnight continuity
        prev_plan = await get_previous_eod_plan()
        prompt = prompt.replace("{{INSERT_PREVIOUS_EOD_PLAN}}", prev_plan)
        
    log.info("✓ Prompt assembled (%d chars)", len(prompt))

    # Call Ollama
    llm_response = call_ollama(prompt, model)
    analysis = extract_analysis_json(llm_response)
    if analysis:
        if session.lower() == "open":
            summary = render_open_summary(static_template, analysis)
        else:
            summary = render_eod_summary(static_template, analysis)
        log.info("✓ Structured daily summary rendered")
    else:
        summary = llm_response
        log.warning("Structured analysis missing; falling back to raw LLM output")
    
    if session.lower() == "open":
        await extract_and_save_trade_plan(summary)
    elif session.lower() == "eod":
        # EOD also generates tomorrow's plan — extract and save it
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
