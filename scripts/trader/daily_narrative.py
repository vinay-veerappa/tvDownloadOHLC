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


# Side-effect import: ensures the repo root is on sys.path so
# `from scripts.trader import ...` works without a per-file hack.
# See scripts/trader/_path_setup.py for the full rationale.
from scripts.trader import _path_setup  # noqa: F401

from scripts.trader.briefing_core import (
    REPO_ROOT,
    build_levels_markdown_table,
    build_compact_briefing,
    build_compact_eod,
    load_daily_eod_from_db,
    save_narrative_to_db,
    resolve_narrative_ticker,
)
from scripts.libs_py.risk.narrative import insert_risk_params
from scripts.libs_py.discord import send_summary as _send_discord_summary

# Prisma is imported at module level so the unit tests can patch it
# via `monkeypatch.setattr(daily_narrative, "Prisma", ...)`. The
# previous pattern (per-function import) worked at runtime but
# prevented mocking.
try:
    from prisma import Prisma
except ImportError:  # pragma: no cover - allows module import without prisma
    Prisma = None  # type: ignore[assignment]

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PROMPT_PATHS = {
    "open": REPO_ROOT / "scripts" / "trader" / "prompts" / "daily_open_update.md",
    "eod":  REPO_ROOT / "scripts" / "trader" / "prompts" / "daily_eod_update.md",
}

DAILY_OUTPUT_DIR = REPO_ROOT / "data" / "options" / "daily"

# Ollama config — defaults sourced from the unified LLM section
# in `narrative_stats.yaml` (audit §2.6). The audit found that the
# two narrative chains had drifted to different defaults
# (`deepseek-v4-pro:cloud` vs `gemma4:latest`), producing
# inconsistent voice and JSON adherence. We now read from a
# single source of truth via `config_loader.get_llm_config()`.
from scripts.trader.config_loader import get_llm_config  # noqa: E402

_llm_cfg = get_llm_config()
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
# `default_model` and `fallback_model` are required keys in the
# `llm:` section (see narrative_stats.yaml). Hardcoded fallbacks
# below are a defensive net for the case where the config is
# missing or has been hand-edited into an invalid state.
DEFAULT_MODEL = _llm_cfg.get("default_model") or "gemma4:latest"
FALLBACK_MODEL = _llm_cfg.get("fallback_model") or "gemma4:31b-cloud"

# ── Instrument mapping ─────────────────────────────────────────────
# Single source of truth for narrative-ticker → futures identity.
#
# The narrative chain deals in three different "names" for each
# futures product, and conflating them is the source of a long
# history of slot-name bugs (e.g. `MNQ_REGIME` slots in templates
# that narrate the *NQ* chart, not the *micro-NQ* contract).
#
# The three names are:
#
#   `pipeline`  — the label used by the options pipeline (e.g. "NQ",
#                 "ES"). This is what the trader WATCHES on the chart,
#                 what the regime / levels / walls talk about, and what
#                 slot names in the static template use. The LLM
#                 thinks in this language for everything except the
#                 actual trade execution.
#
#   `micro`     — the prop-firm tradeable contract (e.g. "MNQ",
#                 "MES"). This is the `asset` field in
#                 `plan_json.trades[]` and the only place a micro
#                 label should appear in the prompt or rendered output.
#
#   `description` — human-readable string for the static template's
#                 "trade plan" header line.
#
# Adding a new ticker (e.g. YM1 → pipeline "YM", micro "MYM") is a
# single line here. Every loop in this module picks it up.
NARRATIVE_INSTRUMENT_MAP: dict[str, dict[str, str]] = {
    "NQ1": {"pipeline": "NQ",  "micro": "MNQ", "description": "Nasdaq-100 futures (MNQ micro)"},
    "ES1": {"pipeline": "ES",  "micro": "MES", "description": "S&P 500 futures (MES micro)"},
}

# Convenience reverse maps for callers that need to map back from a
# pipeline or micro label to the narrative ticker.
PIPELINE_TO_NARRATIVE: dict[str, str] = {
    spec["pipeline"]: ticker
    for ticker, spec in NARRATIVE_INSTRUMENT_MAP.items()
}
MICRO_TO_NARRATIVE: dict[str, str] = {
    spec["micro"]: ticker
    for ticker, spec in NARRATIVE_INSTRUMENT_MAP.items()
}
# Convenience map for the trade-plan path: which micro contract does
# a given narrative ticker use?
NARRATIVE_TO_MICRO: dict[str, str] = {
    ticker: spec["micro"]
    for ticker, spec in NARRATIVE_INSTRUMENT_MAP.items()
}


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
    """Send the summary to Discord via the configured webhook.

    Thin shim — the actual delivery + chunking logic lives in
    `scripts.libs_py.discord.send_summary` (audit §3.5).
    """
    _send_discord_summary(
        summary,
        webhook_key=webhook_key,
        repo_root=REPO_ROOT,
    )


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


# ── Trade outcome states (for EOD review) ──────────────────────────
# A trade's `status` field is a free-form String in the Prisma schema.
# We classify it into one of four high-level states for the LLM prompt.
_FILLED_STATUSES: frozenset[str] = frozenset({
    "FILLED", "OPEN", "WIN", "LOSS", "STOPPED", "TARGET_HIT", "CLOSED",
})
_CLOSED_STATUSES: frozenset[str] = frozenset({
    "WIN", "LOSS", "STOPPED", "TARGET_HIT", "CLOSED",
})
_STOP_REASON_STATUSES: frozenset[str] = frozenset({"STOPPED", "LOSS"})
_TARGET_REASON_STATUSES: frozenset[str] = frozenset({"TARGET_HIT", "WIN"})
_NEVER_FILLED_STATUSES: frozenset[str] = frozenset({
    "PENDING", "EXPIRED", "CANCELLED", "REJECTED",
})


def _utc_to_et_str(dt, fmt: str = "%H:%M") -> str:
    """Convert a UTC datetime (or None) to 'HH:MM' ET, or '?' if None.

    Uses pytz for ET conversion (matches the codebase convention in
    scripts/enrich_macro.py and scripts/analysis/*). Trade timestamps
    in the Prisma DB are stored in UTC; the LLM thinks in ET, so we
    always display in ET.
    """
    if dt is None:
        return "?"
    try:
        import pytz
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        eastern = pytz.timezone("US/Eastern")
        return dt.astimezone(eastern).strftime(fmt)
    except Exception:
        # Fallback: best-effort str() so the LLM still gets a hint
        return str(dt)


def _format_trade_outcome_line(t, now) -> str:
    """Format a single trade as a one-line outcome string for the EOD prompt.

    Derived states (see _FILLED_STATUSES etc.):
      - FILLED + CLOSED  → "FILLED @HH:MM → STOPPED/TARGET/CLOSED @HH:MM (P&L: $X)"
      - FILLED + OPEN    → "FILLED @HH:MM → STILL OPEN (MFE=+X, MAE=-Y)"
      - NEVER FILLED     → "PLANNED entry=X stop=Y target=Z | NEVER FILLED (reason)"
      - UNKNOWN status   → treated as never filled, with the raw status surfaced
    """
    ticker = t.ticker or "?"
    direction = t.direction or "LONG"
    entry = t.entryPrice
    stop = t.stopLoss
    target = t.takeProfit
    status = (t.status or "PENDING").upper()
    qty = int(t.quantity or 0)

    # Filled and closed
    if status in _CLOSED_STATUSES and t.entryDate:
        entry_str = _utc_to_et_str(t.entryDate)
        exit_str = _utc_to_et_str(t.exitDate) if t.exitDate else "?"
        exit_price = t.exitPrice

        if status in _STOP_REASON_STATUSES:
            outcome = f"STOPPED {exit_price} @{exit_str}"
        elif status in _TARGET_REASON_STATUSES:
            outcome = f"TARGET {exit_price} @{exit_str}"
        else:
            outcome = f"CLOSED {exit_price} @{exit_str}"

        if t.pnl is not None:
            pnl_str = f" P&L=${t.pnl:+.0f}"
        else:
            pnl_str = " P&L=unrecorded"

        mae = float(t.mae) if t.mae is not None else 0.0
        mfe = float(t.mfe) if t.mfe is not None else 0.0
        return (
            f"- {ticker} {direction} qty={qty}: "
            f"FILLED {entry} @{entry_str} → {outcome}{pnl_str} "
            f"[MAE={mae:.0f} MFE={mfe:.0f}]"
        )
    # Filled but still open
    if status in _FILLED_STATUSES and t.entryDate:
        entry_str = _utc_to_et_str(t.entryDate)
        mfe = float(t.mfe) if t.mfe is not None else 0.0
        mae = float(t.mae) if t.mae is not None else 0.0
        return (
            f"- {ticker} {direction} qty={qty}: "
            f"FILLED {entry} @{entry_str} → STILL OPEN "
            f"(MFE={mfe:+.0f}, MAE={mae:+.0f})"
        )

    # Never filled (PENDING / EXPIRED / CANCELLED / REJECTED / unknown)
    if status in _NEVER_FILLED_STATUSES or not t.entryDate:
        if status == "PENDING":
            reason = "limit not hit"
        else:
            reason = f"status={status}"
        return (
            f"- {ticker} {direction} qty={qty}: "
            f"PLANNED entry={entry} stop={stop} target={target} | "
            f"NEVER FILLED ({reason})"
        )

    # Unknown status with entryDate set — treat as "in flight"
    entry_str = _utc_to_et_str(t.entryDate)
    return (
        f"- {ticker} {direction} qty={qty}: "
        f"status={status} entry={entry} @{entry_str} (unclassified)"
    )


async def get_trade_outcomes(tickers: list[str] | None = None) -> str:
    """Fetch today's trade executions and format them for the EOD prompt.

    For each trade created today for the Auto Prop Firm 50K account,
    derive one of four states (FILLED+CLOSED / FILLED+OPEN / NEVER
    FILLED / UNKNOWN) and emit a one-line outcome summary. The LLM
    uses this block to review the morning's plan against the day's
    actual execution — closing the feedback loop.

    Args:
        tickers: optional list of user-facing narrative tickers
            (e.g. ['NQ1', 'ES1']). If provided, the query is filtered
            to the corresponding micro instruments (MNQ, MES). If
            None, all of today's trades are returned.

    Returns:
        A multi-line string ready to drop into the EOD prompt's
        `{{INSERT_TRADE_OUTCOMES}}` slot. Returns a short message
        if there are no trades or the account is not found.
    """
    from datetime import datetime, timezone

    if Prisma is None:
        return "Trade outcomes unavailable (Prisma not importable)."

    db = Prisma()
    await db.connect()

    acc = await db.account.find_first(where={'name': 'Auto Prop Firm 50K'})
    if not acc:
        await db.disconnect()
        return "Trade outcomes unavailable (account 'Auto Prop Firm 50K' not found)."

    start_of_day = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    now = datetime.now(timezone.utc)

    where: dict = {
        'accountId': acc.id,
        'createdAt': {'gte': start_of_day},
    }
    if tickers:
        mapped = {NARRATIVE_TO_MICRO.get(t, t) for t in tickers}
        where['ticker'] = {'in': sorted(mapped)}

    trades = await db.trade.find_many(
        where=where,
        order={'createdAt': 'asc'},
    )

    if not trades:
        await db.disconnect()
        return "No trades were tracked today for this account."

    lines = [_format_trade_outcome_line(t, now) for t in trades]
    await db.disconnect()
    return "\n".join(lines)


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


async def get_level_accuracy(briefing_data: dict, tickers: list[str] | None = None) -> str:
    """Pre-compute level accuracy audit from the EOD briefing data.

    Uses the level_flags from the compact EOD to show which levels held vs broke.
    Expects user-facing tickers (e.g. NQ1, ES1); resolves each to its pipeline
    key for lookup while keeping the friendly label in output.
    """
    all_data = {t["ticker"]: t for t in briefing_data.get("tickers", [])}

    if tickers is None:
        tickers = ["NQ1", "ES1"]

    lines = ["Level Accuracy Audit:"]
    for user_ticker in tickers:
        pipeline_ticker = resolve_narrative_ticker(user_ticker)
        t = all_data.get(pipeline_ticker) or all_data.get(user_ticker)
        if not t:
            lines.append(f"  {user_ticker} -> {pipeline_ticker}: no data")
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

        lines.append(f"  {user_ticker} -> {pipeline_ticker}:")
        lines.append(f"    Call Wall {cw}: {cw_tested}, {cw_broken}")
        lines.append(f"    Put Wall {pw}: {pw_tested}, {pw_broken}")
        lines.append(f"    EM Upper {em_u}: {em_u_status}")
        lines.append(f"    EM Lower {em_l}: {em_l_status}")

    return "\n".join(lines)

# Source-tag values for `Trade.originalSource`. Used by the
# dedup logic in `extract_and_save_trade_plan` (audit issue §2.2)
# to distinguish a morning PENDING trade from a same-day EOD
# PENDING trade that was generated for the next day. Same-source
# (OPEN,OPEN) or (EOD_TOMORROW,EOD_TOMORROW) duplicates are skipped.
# Cross-source (OPEN then EOD_TOMORROW) is allowed — the EOD plan
# is a different commitment.
TRADE_SOURCE_OPEN: str = "OPEN"
TRADE_SOURCE_EOD_TOMORROW: str = "EOD_TOMORROW"
_VALID_TRADE_SOURCES: frozenset[str] = frozenset({
    TRADE_SOURCE_OPEN, TRADE_SOURCE_EOD_TOMORROW,
})


async def extract_and_save_trade_plan(
    summary: str,
    mandated_tracks: dict[str, str] | None = None,
    micro_to_pipeline: dict[str, str] | None = None,
    source: str = TRADE_SOURCE_OPEN,
):
    """Parse JSON plan block, validate, and save to DB.

    Updated schema (v2) supports:
      - regime, stopDistancePts, contracts, dollarRisk, rewardToRisk
      - noTrade / noTradeReason for skip conditions
    Falls back gracefully if new fields are absent (v1 compatibility).

    v3 (added 2026-07-14, audit issue #1): LLM output is passed through
    `validate_trade_plan()` from `scripts.libs_py.risk.narrative`
    before any DB write. The validator:
      - drops trades with bad geometry (zero entry, wrong-side stop,
        wrong-side target, unknown instrument, non-numeric prices);
      - caps oversized contract counts to the per-instrument risk cap;
      - computes stopDistancePts / dollarRisk / rewardToRisk from
        Python truth (the LLM is not trusted to do this math);
      - blocks trades whose R:R is below the active phase's hard
        threshold.

    v4 (added 2026-07-14, audit issue #1.4): plan is also passed through
    `validate_track_mandate()` which enforces the per-ticker
    `mandated_track` computed in Python from the GEX regime:
      - TRACK C (observation only) → forces noTrade=True on every
        trade for that ticker (hard rule).
      - TRACK A or B → flags obvious contradictions in plain text but
        does not drop (soft warning).
    The `mandated_tracks` arg is a `{pipeline: track_string}` dict;
    `micro_to_pipeline` bridges `trades[].asset` (micro) to the
    mandate lookup key (pipeline). Both default to NARRATIVE_INSTRUMENT_MAP
    if not passed.

    v5 (added 2026-07-14, audit issue §2.2): the `source` arg tags
    each new Trade's `originalSource` with one of:
      - "OPEN"         (default) — the morning RTH open plan
      - "EOD_TOMORROW" — the EOD plan for the NEXT session
    Before inserting a new Trade, the function checks for an
    existing PENDING trade with the same
    (ticker, direction, entryPrice, accountId, originalSource) and
    skips the insert if one exists. This prevents the
    double-PENDING-pollution that previously happened when the EOD
    narrative re-emitted the morning's plan unchanged. Cross-source
    pairs (OPEN + EOD_TOMORROW) are always allowed; same-source
    pairs (OPEN+OPEN or EOD_TOMORROW+EOD_TOMORROW) are de-duplicated.

    Validation warnings are logged via the module logger only and are
    NOT included in the Discord summary.
    """
    import re
    import json
    from prisma import Prisma
    from datetime import datetime, timezone
    from scripts.libs_py.risk.narrative import (
        validate_trade_plan,
        validate_track_mandate,
    )

    # Default the bridges from NARRATIVE_INSTRUMENT_MAP if not provided.
    if micro_to_pipeline is None:
        micro_to_pipeline = {
            spec["micro"]: spec["pipeline"]
            for spec in NARRATIVE_INSTRUMENT_MAP.values()
        }
    if mandated_tracks is None:
        mandated_tracks = {}

    # Validate the source tag. Reject anything that is not in the
    # allow-list so a typo from a caller doesn't silently tag every
    # trade with a string that the dedup query can't see.
    if source not in _VALID_TRADE_SOURCES:
        log.error(
            "extract_and_save_trade_plan: invalid source=%r (must be one of %s)",
            source, sorted(_VALID_TRADE_SOURCES),
        )
        return

    match = re.search(r'<plan_json>(.*?)</plan_json>', summary, re.DOTALL)
    if not match:
        log.warning("No <plan_json> found in Open narrative output.")
        return

    try:
        raw_plan = json.loads(match.group(1).strip())
    except json.JSONDecodeError as exc:
        log.error(f"Failed to decode plan_json: {exc}")
        return

    # Log no-trade entries BEFORE validation — these do not enter the
    # validator and we want them visible in the console for EOD review.
    for nt in raw_plan.get('trades', []):
        if nt.get('noTrade', False):
            asset = nt.get('asset', '?')
            reason = nt.get('noTradeReason', 'No reason provided')
            log.info("  %s: NO TRADE — %s", asset, reason)

    # ── Validate and correct the plan in Python ────────────────────
    validated_plan, _warnings = validate_trade_plan(raw_plan)
    # Enforce the per-ticker `mandated_track` next (issue §1.4). This
    # runs on the post-geometry plan so the mandate check only sees
    # trades that survived risk validation.
    plan_data, _track_warnings = validate_track_mandate(
        validated_plan, mandated_tracks, micro_to_pipeline,
    )
    # `warnings` were already emitted by the validators; no need to
    # re-log here. Discord stays clean — the operator sees the
    # warnings in the scheduler console.

    try:
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
            asset = trade['asset']
            contracts = int(trade['contracts'])
            direction = trade['direction']
            entry_price = float(trade['entryPrice'])

            # ── Dedup: skip if a same-source PENDING trade with the
            # same (ticker, direction, entryPrice, accountId) already
            # exists (audit issue §2.2). Cross-source pairs (OPEN +
            # EOD_TOMORROW) are NOT considered duplicates because
            # they are different commitments: the morning plan is
            # for today's session, the EOD plan is for tomorrow's.
            existing = await db.trade.find_first(where={
                'ticker': asset,
                'direction': direction,
                'entryPrice': entry_price,
                'accountId': acc.id,
                'status': 'PENDING',
                'originalSource': source,
            })
            if existing is not None:
                log.info(
                    "  %s %s @ %s source=%s: skipping — duplicate of trade %s",
                    asset, direction, entry_price, source, existing.id,
                )
                continue

            t = await db.trade.create(data={
                'ticker': asset,
                'entryDate': now,
                'quantity': contracts,
                'direction': direction,
                'status': 'PENDING',
                'accountId': acc.id,
                'entryPrice': entry_price,
                'stopLoss': float(trade['stopLoss']),
                'takeProfit': float(trade['takeProfit']),
                'originalSource': source,
            })

            # Build setup string with new risk fields (Python-computed)
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
        log.error(f"Failed to save Trade Plan: {e}")


def _fmt_news_events(events: list[dict]) -> str:
    if not events:
        return "No market-moving economic events scheduled today."

    lines: list[str] = []
    for ev in events:
        status = "PASSED" if ev.get("passed") else "UPCOMING"
        lines.append(f"- {ev.get('time_et', '?')} [{ev.get('impact', '?')}] {ev.get('name', '?')} -- {status}")
    return "\n".join(lines)


def _default_plan_json(briefing_data: dict, tickers: list[str] | None = None) -> dict:
    """Return a default plan JSON driven by the configured tickers.

    The `asset` field in each trade uses the MICRO label (MNQ, MES)
    — that is the actual contract the prop-firm account trades. The
    rest of the narrative uses the pipeline label (NQ, ES).
    """
    if tickers is None:
        tickers = list(NARRATIVE_INSTRUMENT_MAP.keys())

    all_data = {t["ticker"]: t for t in briefing_data.get("tickers", [])}

    trades = []
    for ticker in tickers:
        spec = NARRATIVE_INSTRUMENT_MAP.get(ticker, {})
        micro = spec.get("micro", ticker)
        pipeline = spec.get("pipeline", ticker)
        # Use whatever key the briefing actually has — some payloads
        # store the pipeline label ("NQ"), others the narrative
        # ticker ("NQ1"). Prefer the pipeline key.
        regime = (
            all_data.get(pipeline, {}).get("regime_check", {}).get("current_regime")
            or all_data.get(ticker, {}).get("regime_check", {}).get("current_regime")
            or "UNKNOWN"
        )
        trades.append({
            "asset": micro,
            "direction": "LONG",
            "regime": regime,
            "entryPrice": 0,
            "stopLoss": 0,
            "takeProfit": 0,
            "stopDistancePts": 0,
            "contracts": 0,
            "dollarRisk": 0,
            "rewardToRisk": 0,
            "noTrade": False,
            "noTradeReason": "",
        })

    return {"logic": "N/A", "trades": trades}


def _replace_slot(template: str, key: str, value: str) -> str:
    return template.replace(f"{{{{{key}}}}}", value if value else "N/A")


def build_open_static_template(briefing_data: dict, levels_md: str, tickers: list[str] | None = None) -> str:
    """Build deterministic open markdown skeleton in Python."""
    from datetime import datetime

    if tickers is None:
        tickers = ["NQ1", "ES1"]

    all_data = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
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

    # Per-ticker regime/bias lines and trade-plan blocks.
    # We build each slot string at Python level (`{{NQ_REGIME}}`) so the
    # f-string's brace doubling doesn't insert spaces inside the slot.
    # Slot names use the PIPELINE label (NQ, ES) — that's the futures
    # product the trader watches. The micro label (MNQ, MES) only
    # appears in the trade-plan `asset` field.
    regime_lines = []
    trade_blocks = []
    for ticker in tickers:
        spec = NARRATIVE_INSTRUMENT_MAP.get(ticker, {})
        pipeline = spec.get("pipeline", ticker)
        micro = spec.get("micro", ticker)
        description = spec.get("description", f"{pipeline} futures")
        # Look up by pipeline key (the canonical briefing label) first,
        # then fall back to narrative ticker.
        data = all_data.get(pipeline) or all_data.get(ticker) or {}
        regime = data.get("regime_check", {}).get("current_regime", "UNKNOWN")
        bias = data.get("weekly_anchor", {}).get("mandated_track", "UNKNOWN")
        regime_lines.append(f"{ticker}->{pipeline}: {regime} | Bias: {bias}")

        slots = {
            "REGIME": f"{{{{{pipeline}_REGIME}}}}",
            "LOGIC": f"{{{{{pipeline}_LOGIC}}}}",
            "ENTRY": f"{{{{{pipeline}_ENTRY}}}}",
            "STOP": f"{{{{{pipeline}_STOP}}}}",
            "STOP_DIST": f"{{{{{pipeline}_STOP_DIST}}}}",
            "CONTRACTS": f"{{{{{pipeline}_CONTRACTS}}}}",
            "TARGET": f"{{{{{pipeline}_TARGET}}}}",
            "RR": f"{{{{{pipeline}_RR}}}}",
        }
        trade_blocks.append(
            f"**{pipeline}** ({description}, contract: {micro}):\n"
            f"- Regime: {slots['REGIME']}\n"
            f"- Logic: {slots['LOGIC']}\n"
            f"- Entry: {slots['ENTRY']}\n"
            f"- Stop: {slots['STOP']} | Stop dist: {slots['STOP_DIST']} pts | Contracts: {slots['CONTRACTS']}\n"
            f"- Target: {slots['TARGET']} | R:R: {slots['RR']}"
        )

    news_section = _fmt_news_events(events)

    default_plan_json = json.dumps(_default_plan_json(briefing_data, tickers), ensure_ascii=False)

    template = f"""## RTH OPEN SETUP -- {date_label} ({day_name})

{levels_md}

### Regime
{"\n".join(regime_lines)}

### Overnight Delta
{{{{OVERNIGHT_DELTA}}}}

### News
{news_section}

### Dynamic
{{{{DYNAMIC}}}}

### Trade Plan

{"\n\n".join(trade_blocks)}

### Risk Summary
- {{{{RISK_SUMMARY_LINE_1}}}}
- {{{{RISK_SUMMARY_LINE_2}}}}
- {{{{RISK_SUMMARY_LINE_3}}}}

<plan_json>
{{{{PLAN_JSON}}}}
</plan_json>"""

    return template.replace("{{PLAN_JSON}}", default_plan_json)


def build_eod_static_template(briefing_data: dict, levels_md: str, tickers: list[str] | None = None) -> str:
    """Build deterministic EOD markdown skeleton in Python."""
    from datetime import datetime

    if tickers is None:
        tickers = ["NQ1", "ES1"]

    all_data = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
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

    regime_lines = []
    session_log_lines = []
    tomorrow_blocks = []
    for ticker in tickers:
        spec = NARRATIVE_INSTRUMENT_MAP.get(ticker, {})
        pipeline = spec.get("pipeline", ticker)
        micro = spec.get("micro", ticker)
        description = spec.get("description", f"{pipeline} futures")
        # Look up by pipeline key (canonical briefing label) first.
        data = all_data.get(pipeline) or all_data.get(ticker) or {}
        regime = data.get("regime_check", {}).get("current_regime", "UNKNOWN")
        regime_lines.append(
            f"{ticker}->{pipeline}: {regime} | Levels shown below are {pipeline} levels"
        )
        session_log_lines.append(f"**{pipeline}**: {{{{SESSION_{pipeline}}}}}")

        # Build slot strings at Python level so the f-string brace
        # doubling doesn't insert spaces inside the slot name.
        # Slot names use the PIPELINE label (NQ, ES).
        slots = {
            "REGIME": f"{{{{TM_{pipeline}_REGIME}}}}",
            "LOGIC": f"{{{{TM_{pipeline}_LOGIC}}}}",
            "ENTRY": f"{{{{TM_{pipeline}_ENTRY}}}}",
            "STOP": f"{{{{TM_{pipeline}_STOP}}}}",
            "STOP_DIST": f"{{{{TM_{pipeline}_STOP_DIST}}}}",
            "CONTRACTS": f"{{{{TM_{pipeline}_CONTRACTS}}}}",
            "TARGET": f"{{{{TM_{pipeline}_TARGET}}}}",
            "RR": f"{{{{TM_{pipeline}_RR}}}}",
        }
        tomorrow_blocks.append(
            f"**{pipeline}** ({description}, contract: {micro}):\n"
            f"- Regime: {slots['REGIME']}\n"
            f"- Logic: {slots['LOGIC']}\n"
            f"- Entry: {slots['ENTRY']}\n"
            f"- Stop: {slots['STOP']} | Stop dist: {slots['STOP_DIST']} pts | Contracts: {slots['CONTRACTS']}\n"
            f"- Target: {slots['TARGET']} | R:R: {slots['RR']}"
        )

    default_plan_json = json.dumps(_default_plan_json(briefing_data, tickers), ensure_ascii=False)

    template = f"""## EOD DAILY REVIEW -- {date_label} ({day_name})

{levels_md}

### Today's Regime
{"\n".join(regime_lines)}

### Session Log
{"\n".join(session_log_lines)}
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

{"\n\n".join(tomorrow_blocks)}

### Tomorrow's Risk Budget
- {{{{TM_RISK_LINE_1}}}}
- {{{{TM_RISK_LINE_2}}}}

<plan_json>
{{{{PLAN_JSON}}}}
</plan_json>"""

    return template.replace("{{PLAN_JSON}}", default_plan_json)


def render_open_summary(static_template: str, analysis: dict, tickers: list[str] | None = None) -> str:
    """Merge bounded open-session analysis slots into static template.

    Slot names use the PIPELINE label (NQ, ES) — that's the futures
    product the trader watches. Reads per-instrument trade-plan data
    from `analysis["tickers"][PIPELINE]` (the new contract) or, for
    backward compatibility, falls back to the legacy `analysis["mes"]`
    / `analysis["mnq"]` keys.

    The loop is driven by `tickers` (or the configured narrative
    tickers), so adding a new instrument is purely a
    `NARRATIVE_INSTRUMENT_MAP` change — no edits to this function
    are required.
    """
    if tickers is None:
        tickers = list(NARRATIVE_INSTRUMENT_MAP.keys())

    summary = static_template

    summary = _replace_slot(summary, "OVERNIGHT_DELTA", analysis.get("overnight_delta", "N/A"))
    summary = _replace_slot(summary, "DYNAMIC", analysis.get("dynamic", "N/A"))

    # Per-instrument trade-plan slots. Prefer the new `tickers` dict
    # (keyed by pipeline label) and fall back to the legacy flat
    # `mes` / `mnq` keys for backward compatibility.
    tickers_payload = analysis.get("tickers") or {}
    for ticker in tickers:
        spec = NARRATIVE_INSTRUMENT_MAP.get(ticker, {})
        pipeline = spec.get("pipeline", ticker)
        micro = spec.get("micro", "")
        block = (
            tickers_payload.get(pipeline)
            or tickers_payload.get(micro)
            or analysis.get(micro.lower())
            or analysis.get(pipeline.lower())
            or {}
        )
        for field in ("REGIME", "LOGIC", "ENTRY", "STOP", "STOP_DIST", "CONTRACTS", "TARGET", "RR"):
            summary = _replace_slot(
                summary,
                f"{pipeline}_{field}",
                str(block.get(field.lower(), "N/A")),
            )

    risk_summary = analysis.get("risk_summary", {}) or {}
    summary = _replace_slot(
        summary,
        "RISK_SUMMARY_LINE_1",
        str(risk_summary.get("line_1", "ES: $N/A | NQ: $N/A")),
    )
    summary = _replace_slot(
        summary,
        "RISK_SUMMARY_LINE_2",
        str(risk_summary.get("line_2", "Combined same-dir: $N/A")),
    )
    summary = _replace_slot(
        summary,
        "RISK_SUMMARY_LINE_3",
        str(risk_summary.get("line_3", "Daily stop remaining: ES $450 | NQ $300")),
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


def render_eod_summary(static_template: str, analysis: dict, tickers: list[str] | None = None) -> str:
    """Merge bounded EOD-session analysis slots into static template.

    Slot names use the PIPELINE label (NQ, ES). Reads per-instrument
    tomorrow-plan data from `analysis["tomorrow"][PIPELINE]` (the new
    contract) or, for backward compatibility, falls back to the legacy
    `analysis["tomorrow_mes"]` / `analysis["tomorrow_mnq"]` keys.

    Session log lines are read from `analysis["session_log"][PIPELINE]`
    (preferred) or the legacy `analysis["session_log"]["mes"]` /
    `["mnq"]` keys.

    The loop is driven by `tickers` (or the configured narrative
    tickers) via the module-level `NARRATIVE_INSTRUMENT_MAP`, so
    adding a new instrument is purely a `NARRATIVE_INSTRUMENT_MAP`
    change — no edits to this function.
    """
    if tickers is None:
        tickers = list(NARRATIVE_INSTRUMENT_MAP.keys())

    summary = static_template

    session_log = analysis.get("session_log", {}) or {}
    summary = _replace_slot(summary, "SESSION_DAILY_PNL", str(session_log.get("daily_pnl", "N/A")))

    # Per-instrument session-log lines.
    for ticker in tickers:
        spec = NARRATIVE_INSTRUMENT_MAP.get(ticker, {})
        pipeline = spec.get("pipeline", ticker)
        micro = spec.get("micro", "")
        line = (
            session_log.get(pipeline)
            or session_log.get(micro)
            or session_log.get(micro.lower())
            or session_log.get(pipeline.lower())
            or "N/A"
        )
        summary = _replace_slot(summary, f"SESSION_{pipeline}", str(line))

    summary = _replace_slot(summary, "DRAWDOWN_ANALYSIS", str(analysis.get("drawdown_analysis", "N/A")))
    summary = _replace_slot(summary, "LEVEL_ACCURACY_REVIEW", str(analysis.get("level_accuracy_review", "N/A")))
    summary = _replace_slot(summary, "TRADE_QUALITY", str(analysis.get("trade_quality", "N/A")))
    summary = _replace_slot(summary, "NOTE_OF_DAY", str(analysis.get("note_of_day", "N/A")))
    summary = _replace_slot(summary, "OVERNIGHT_CONSIDERATIONS", str(analysis.get("overnight_considerations", "N/A")))

    # Per-instrument tomorrow-plan slots. Prefer the new `tomorrow` dict
    # (keyed by pipeline label) and fall back to the legacy flat
    # `tomorrow_mes` / `tomorrow_mnq` keys.
    tomorrow_payload = analysis.get("tomorrow") or {}
    for ticker in tickers:
        spec = NARRATIVE_INSTRUMENT_MAP.get(ticker, {})
        pipeline = spec.get("pipeline", ticker)
        micro = spec.get("micro", "")
        legacy_key = f"tomorrow_{micro.lower()}"  # tomorrow_mnq, tomorrow_mes
        block = (
            tomorrow_payload.get(pipeline)
            or tomorrow_payload.get(micro)
            or analysis.get(legacy_key)
            or {}
        )
        for field in ("REGIME", "LOGIC", "ENTRY", "STOP", "STOP_DIST", "CONTRACTS", "TARGET", "RR"):
            summary = _replace_slot(
                summary,
                f"TM_{pipeline}_{field}",
                str(block.get(field.lower(), "N/A")),
            )

    tm_risk = analysis.get("tomorrow_risk_budget", {}) or {}
    summary = _replace_slot(summary, "TM_RISK_LINE_1", str(tm_risk.get("line_1", "ES: $N/A | NQ: $N/A")))
    summary = _replace_slot(summary, "TM_RISK_LINE_2", str(tm_risk.get("line_2", "Daily stop remaining: ES $450 | NQ $300")))

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


async def run_narrative(model: str, session: str, tickers: list[str], target_date: date | None = None) -> str:
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
    if session.lower() == "open":
        toon = build_compact_briefing(briefing_data, tickers)
    else:
        toon = build_compact_eod(briefing_data, tickers)
    log.info("✓ Briefing assembled (%d chars)", len(toon))

    # Build levels tables for the configured tickers.
    # The pipeline stores futures under NQ/ES; narrative tickers are NQ1/ES1.
    # build_levels_markdown_table consumes the pipeline key AND a session
    # argument so it can read the right snapshot:
    #   - "open"      → 09:30 RTH-open snapshot (morning narrative)
    #   - "eod"       → 16:15 RTH-close snapshot (EOD narrative — fixes §1.3)
    #   - "intraday"  → latest live mirror (any other mode)
    # The session value is propagated from the caller's --session arg.
    levels_session = session.lower() if session.lower() in ("open", "eod") else "intraday"
    tables = []
    for ticker in tickers:
        pipeline_ticker = resolve_narrative_ticker(ticker)
        tables.append(build_levels_markdown_table(pipeline_ticker, session=levels_session))
    levels_md = "\n\n".join(tables)

    # Build static template and prompt
    if session.lower() == "open":
        static_template = build_open_static_template(briefing_data, levels_md, tickers)
    else:
        static_template = build_eod_static_template(briefing_data, levels_md, tickers)

    prompt_template = load_prompt_template(session)
    placeholder = "{{INSERT_DAILY_OPEN_JSON}}" if session.lower() == "open" else "{{INSERT_DAILY_EOD_JSON}}"
    prompt = prompt_template.replace(placeholder, toon)
    prompt = prompt.replace("{{INSERT_STATIC_DAILY_TEMPLATE}}", static_template)
    # Inject the per-instrument risk-params block (audit issue §1.7).
    # The block is rendered from the typed risk config so the numbers
    # are sourced from `scripts/libs_py/risk/narrative/constants.py`
    # — the same source the validator reads. If a prompt doesn't have
    # the `{{INSERT_RISK_PARAMS}}` placeholder, `insert_risk_params`
    # is a no-op.
    micro_instruments = [NARRATIVE_TO_MICRO.get(t, t) for t in tickers]
    prompt = insert_risk_params(prompt, instruments=micro_instruments)
    
    if session.lower() == "eod":
        # Today's actual execution (filled/closed/open/never-filled).
        # This is read FIRST by the LLM per the prompt's RULES section,
        # then the morning's plan is graded in light of these outcomes.
        trade_outcomes_md = await get_trade_outcomes(tickers)
        prompt = prompt.replace("{{INSERT_TRADE_OUTCOMES}}", trade_outcomes_md)
        trade_plan_md = await get_trade_plan_for_eod()
        prompt = prompt.replace("{{INSERT_TRADE_PLAN}}", trade_plan_md)
        # Inject drawdown status and level accuracy audit
        drawdown_md = await get_drawdown_status()
        prompt = prompt.replace("{{INSERT_DRAWDOWN_STATUS}}", drawdown_md)
        level_audit_md = await get_level_accuracy(briefing_data, tickers)
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
            summary = render_open_summary(static_template, analysis, tickers)
        else:
            summary = render_eod_summary(static_template, analysis, tickers)
        log.info("✓ Structured daily summary rendered")
    else:
        summary = llm_response
        log.warning("Structured analysis missing; falling back to raw LLM output")
    
    # Build the per-pipeline `mandated_track` map from the briefing
    # data. The GEX regime was already resolved to a track in Python
    # (`briefing_core.resolve_track`); this is the authoritative input
    # for the validator. Keys must be the PIPELINE label (NQ, ES) so
    # they match the keys in `validate_track_mandate`'s micro→pipeline
    # bridge. We pull from each ticker's `weekly_anchor.mandated_track`
    # (set by the bias signal generator) and from `bias.mandated_track`
    # (set by the compact EOD briefing) as a fallback.
    mandated_tracks: dict[str, str] = {}
    for t in briefing_data.get("tickers", []):
        ticker_key = t.get("ticker", "")
        track = (
            (t.get("weekly_anchor") or {}).get("mandated_track")
            or (t.get("bias") or {}).get("mandated_track")
            or ""
        )
        if ticker_key and track:
            mandated_tracks[ticker_key] = track
    if mandated_tracks:
        log.info(
            "  Mandated tracks (from briefing): %s",
            ", ".join(f"{k}={v[:24]}..." for k, v in mandated_tracks.items()),
        )
    else:
        log.warning("  No mandated tracks found in briefing data; track mandate enforcement is a no-op.")

    if session.lower() == "open":
        # Open narrative → morning plan for today’s session.
        # Tag with TRADE_SOURCE_OPEN so the EOD’s same-structure
        # EOD_TOMORROW plan is NOT treated as a duplicate (audit §2.2).
        await extract_and_save_trade_plan(
            summary,
            mandated_tracks=mandated_tracks,
            source=TRADE_SOURCE_OPEN,
        )
    elif session.lower() == "eod":
        # EOD narrative → tomorrow’s plan. Tagged with
        # TRADE_SOURCE_EOD_TOMORROW so re-running the EOD with the
        # same plan_json does not create duplicate PENDING rows.
        await extract_and_save_trade_plan(
            summary,
            mandated_tracks=mandated_tracks,
            source=TRADE_SOURCE_EOD_TOMORROW,
        )

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
    parser.add_argument("--tickers", type=str, nargs="+", default=["NQ1", "ES1"], help="Tickers to process (default: NQ1 ES1)")
    args = parser.parse_args()

    target_date = None
    if args.date:
        target_date = date.fromisoformat(args.date)

    summary = asyncio.run(run_narrative(args.model, args.session, args.tickers, target_date))

    # Print to console for immediate viewing
    print("\n" + "=" * 60)
    print(summary)
    print("=" * 60)

    return summary


if __name__ == "__main__":
    main()
