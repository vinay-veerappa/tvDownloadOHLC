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
import re
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
# The EOD narrative now fires at 17:10 ET (moved from 16:25 in 2026-07-20),
# so the 16:15 close snapshot is guaranteed to be on disk long before the
# narrative runs. 180s is a generous safety net for the rare case where the
# 16:15 pipeline slips (e.g. broker latency).
CLOSE_SNAPSHOT_TIMEOUT_SECONDS = 180
CLOSE_SNAPSHOT_POLL_INTERVAL = 5


def _wait_for_open_snapshot(timeout: int = OPEN_SNAPSHOT_TIMEOUT_SECONDS) -> bool:
    """Block until the 09:30 unified_levels_open.txt snapshot is fresh.

    Returns True if the file exists and was modified after 09:30 ET on the
    most recent trading day. If the current ET time is before 09:30 (e.g.
    the narrative is run overnight or pre-market), the gate looks for
    yesterday's 09:30 snapshot instead of today's.

    Returns False if timeout expires.
    """
    import time as _time
    from datetime import datetime as _dt, timedelta as _td
    from zoneinfo import ZoneInfo

    et = ZoneInfo(ET_TZ)
    deadline = _time.monotonic() + timeout
    now_et = _dt.now(et)
    target_930 = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    # If we haven't reached 09:30 ET yet today, the relevant snapshot is
    # from the previous trading day (e.g. running at 04:00 ET looks for
    # yesterday's 09:30 snapshot).
    if now_et < target_930:
        # Walk back to the most recent weekday
        prev = now_et.date() - _td(days=1)
        while prev.weekday() >= 5:  # Skip Sat/Sun
            prev -= _td(days=1)
        target_930 = _dt.combine(prev, _dt.min.time(), tzinfo=et).replace(
            hour=9, minute=30, second=0, microsecond=0
        )

    while _time.monotonic() < deadline:
        if UNIFIED_LEVELS_OPEN_TXT.exists():
            mtime = _dt.fromtimestamp(UNIFIED_LEVELS_OPEN_TXT.stat().st_mtime, tz=et)
            if mtime >= target_930:
                log.info("✓ Open snapshot ready (mtime: %s)", mtime.strftime("%H:%M:%S ET"))
                return True
        log.info("Waiting for 09:30 open snapshot... (%s)", UNIFIED_LEVELS_OPEN_TXT)
        _time.sleep(OPEN_SNAPSHOT_POLL_INTERVAL)

    log.warning("Timed out waiting for open snapshot after %ds — proceeding with available data", timeout)
    return False


def _wait_for_close_snapshot(timeout: int = CLOSE_SNAPSHOT_TIMEOUT_SECONDS) -> bool:
    """Block until the 16:15 unified_levels_close.txt snapshot is fresh.

    Mirrors `_wait_for_open_snapshot` for the EOD path. The EOD narrative
    now runs at 17:10 ET (moved from 16:25 in 2026-07-20), so the 16:15
    close snapshot has ~55 minutes of headroom — this gate is a safety net
    for the rare case where the 16:15 pipeline slips.

    If the current ET time is before 16:15 (e.g. the narrative is run
    overnight), the gate looks for the most recent weekday's 16:15
    snapshot instead of today's.

    Returns True if the file exists and was modified after 16:15 ET on
    the most recent trading day. Returns False if timeout expires;
    caller proceeds with whatever is on disk and logs a warning.
    """
    import time as _time
    from datetime import datetime as _dt, timedelta as _td
    from zoneinfo import ZoneInfo

    et = ZoneInfo(ET_TZ)
    deadline = _time.monotonic() + timeout
    now_et = _dt.now(et)
    target_1615 = now_et.replace(hour=16, minute=15, second=0, microsecond=0)
    # If we haven't reached 16:15 ET yet today, the relevant snapshot is
    # from the previous trading day (e.g. running the EOD narrative at
    # 00:30 ET looks for yesterday's 16:15 snapshot).
    if now_et < target_1615:
        prev = now_et.date() - _td(days=1)
        while prev.weekday() >= 5:  # Skip Sat/Sun
            prev -= _td(days=1)
        target_1615 = _dt.combine(prev, _dt.min.time(), tzinfo=et).replace(
            hour=16, minute=15, second=0, microsecond=0
        )

    while _time.monotonic() < deadline:
        if UNIFIED_LEVELS_CLOSE_TXT.exists():
            mtime = _dt.fromtimestamp(UNIFIED_LEVELS_CLOSE_TXT.stat().st_mtime, tz=et)
            if mtime >= target_1615:
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
                        "num_ctx": 262144,
                        "num_predict": 32768,
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


def _infer_probability_source(summary: str) -> str:
    """Infer single probability source from the existing narrative text."""
    lower = summary.lower()

    explicit = re.search(
        r"active\s+probability\s+source\s*:\s*(?:\*\*)?\s*`?(overnight|sequential)`?",
        lower,
    )
    if explicit:
        return explicit.group(1)

    overnight_hits = len(re.findall(r"\bovernight\b|\bglobex\b|trajectory", lower))
    sequential_hits = len(re.findall(r"\br1\b|\br2\b|\bsequential\b|classification", lower))

    if overnight_hits > sequential_hits:
        return "overnight"
    if sequential_hits > overnight_hits:
        return "sequential"
    # Keep fallback inside the allowed contract values.
    return "sequential"


def _enforce_narrative_contract(summary: str, mode: str) -> str:
    """Apply a minimal deterministic contract guard to LLM output.

    Prompts already require these items. This guard ensures output remains
    actionable when the model omits them.
    """
    required_heading = (
        "Tomorrow Most Likely vs Alternate"
        if mode == "close"
        else "Most Likely vs Alternate Outcome"
    )
    additions: list[str] = []

    if required_heading.lower() not in summary.lower():
        additions.append(
            f"### {required_heading}\n"
            "- Most Likely: missing from model output; keep directional read conditional until validation trigger is met.\n"
            "- Alternate: if the primary validation fails, switch to the alternate scenario using structural invalidation levels from the cheat sheet."
        )

    if mode == "premarket":
        inferred_source = _infer_probability_source(summary)
        if "execution card" not in summary.lower():
            additions.append(
                "### Execution Card\n"
                f"- Active Probability Source: `{inferred_source}`.\n"
                "- Bias Inputs Used: Herman, ALN, SMA stance, Classification/Weekly context, GEX (FTFC optional).\n"
                "- Primary Setup (rank #1): wait for M5 confirmation at the named trigger level; invalidate on opposite-side reclaim.\n"
                "- Alternate Setup (rank #2): only if primary fails and a fresh MSS forms.\n"
                "- Time Invalidation: if unresolved by 10:10 ET, downgrade conviction; if still unresolved by 10:30 ET, stand down.\n"
                "- Attempt Budget: max 2 attempts per setup; no third probe in same direction.\n"
                "- Re-entry Rule: re-entry only after fresh MSS + M5 close at/through a named level.\n"
                "- Stand-Down Rule: no-trade / wait for confirmation when neither trigger validates by cutoff."
            )
        else:
            has_probability_phrase = "active probability source" in summary.lower()
            has_probability_source = re.search(
                r"active\s+probability\s+source\s*:\s*(?:\*\*)?\s*`?(overnight|sequential)`?",
                summary,
                flags=re.IGNORECASE,
            )
            if has_probability_source is None and not has_probability_phrase:
                additions.append(
                    f"- Active Probability Source: `{inferred_source}` (single-source mode)."
                )

            if "bias inputs used" not in summary.lower():
                additions.append(
                    "- Bias Inputs Used: explicitly state Herman, ALN, SMA stance, Classification/Weekly context, and GEX before final directional language (FTFC optional)."
                )

            has_bias_inputs_section = re.search(
                r"(^|\n)##\s+Bias\s+Inputs\s+Transparency|(^|\n)##\s+Bias\s+Consensus",
                summary,
                flags=re.IGNORECASE,
            )
            if has_bias_inputs_section is None:
                additions.append(
                    "### Bias Inputs Transparency\n"
                    "| Component | Signal |\n"
                    "|---|---|\n"
                    "| Herman | state directional read and whether DOMINANT |\n"
                    "| ALN | state directional read |\n"
                    "| SMA stance | state macro/intraday alignment |\n"
                    "| Classification/Weekly context | state directional/regime read |\n"
                    "| GEX | state regime + directional implication |\n"
                    "| FTFC (optional) | include only when available |"
                )

            has_dominance = re.search(r"herman.*dominant|dominant.*herman", summary, flags=re.IGNORECASE)
            if has_dominance is None:
                additions.append(
                    "- Dominance Rule: if Herman is marked DOMINANT in the cheat sheet, treat it as the lead directional prior unless invalidated at named levels."
                )

        if "checkpoint table" not in summary.lower():
            additions.append(
                "### Checkpoint Table\n"
                "| Time | What Must Be True | If Not True |\n"
                "|---|---|---|\n"
                "| 08:35 ET | Initial post-news direction has a clear M5 close anchor | Treat as noise; wait for 09:50 macro window |\n"
                "| 09:50 ET | Primary trigger or clear invalidation is visible at named levels | Switch to alternate setup criteria; do not force entry |\n"
                "| 10:10 ET | One setup is validated with structure follow-through | Stand down and preserve attempts for later session |"
            )

    # Accept either explicit "no-trade / wait" wording or a native
    # no-trade-condition/stand-down clause.
    has_no_trade_clause = re.search(
        r"no\s*-?\s*trade\s*/\s*wait|no\s*-?\s*trade\s*condition|stand\s*-?\s*down\s*condition",
        summary,
        flags=re.IGNORECASE,
    )
    if has_no_trade_clause is None:
        additions.append(
            "- No-Trade Condition: no-trade / wait for confirmation if neither scenario validation trigger is met in the relevant window."
        )

    if not additions:
        return summary

    log.warning("Narrative contract guard applied for mode=%s", mode)
    return summary.rstrip() + "\n\n## Contract Compliance Addendum\n\n" + "\n\n".join(additions) + "\n"


def _append_contradiction_check(summary: str) -> str:
    """Flag obvious directional contradictions after generation.

    This is intentionally lightweight: it catches mixed bullish/bearish
    language when the narrative does not clearly frame the read as conditional.
    """
    lower = summary.lower()
    bullish_hits = len(re.findall(r"\bbullish\b", lower))
    bearish_hits = len(re.findall(r"\bbearish\b", lower))

    if bullish_hits and bearish_hits and not re.search(
        r"\b(conditional|mixed|conditionality|no-trade|wait for confirmation|alternate)\b",
        lower,
    ):
        log.warning("Narrative contradiction check flagged mixed directional language")
        return (
            summary.rstrip()
            + "\n\n## Consistency Check\n\n"
            + "Mixed directional language detected. Treat the read as conditional and wait for the validation trigger rather than forcing conviction.\n"
        )

    return summary


def _normalize_taxonomy_language(summary: str) -> str:
    """Normalize bias/regime wording to a consistent vocabulary."""
    normalized = summary

    # Bias vocabulary normalization.
    normalized = re.sub(r"\bneutral\s*[-/]\s*to\s*bullish\b", "NEUTRAL (bullish lean)", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bneutral\s*[-/]\s*to\s*bearish\b", "NEUTRAL (bearish lean)", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        r"(?<!NEUTRAL\s\()\bbullish\s+lean\b",
        "NEUTRAL (bullish lean)",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"(?<!NEUTRAL\s\()\bbearish\s+lean\b",
        "NEUTRAL (bearish lean)",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"NEUTRAL\s*\(\s*NEUTRAL\s*\(\s*bullish\s+lean\s*\)\s*\)",
        "NEUTRAL (bullish lean)",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"NEUTRAL\s*\(\s*NEUTRAL\s*\(\s*bearish\s+lean\s*\)\s*\)",
        "NEUTRAL (bearish lean)",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"NEUTRAL\s*/\s*NEUTRAL\s*\(\s*bullish\s+lean\s*\)",
        "NEUTRAL (bullish lean)",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"NEUTRAL\s*/\s*NEUTRAL\s*\(\s*bearish\s+lean\s*\)",
        "NEUTRAL (bearish lean)",
        normalized,
        flags=re.IGNORECASE,
    )

    # Regime tag normalization.
    normalized = re.sub(r"\[\s*SWEEP\s*[\-\u2192]\s*EXPANSION\s*\]", "[SWEEP->EXPANSION]", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\[\s*CHOP\s*[\-\u2192]\s*CAUTION\s*\]", "[CHOP]", normalized, flags=re.IGNORECASE)

    return normalized


def _dedupe_repetition(summary: str) -> str:
    """Conservatively remove obvious repeated lines and duplicate compliance headers."""
    lines = summary.splitlines()
    deduped: list[str] = []

    for line in lines:
        candidate = line.strip()
        if deduped:
            prev = deduped[-1].strip()
            if candidate and prev and candidate.lower() == prev.lower():
                continue
        deduped.append(line)

    text = "\n".join(deduped)

    # If model repeats the compliance heading, keep a single canonical one.
    text = re.sub(
        r"(?is)(\n##\s+Contract\s+Compliance\s+Addendum\s*\n)(?:.*?\n##\s+Contract\s+Compliance\s+Addendum\s*\n)",
        r"\1",
        text,
    )

    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text


def _limit_sentences(text: str, max_sentences: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(parts) <= max_sentences:
        return text.strip()
    return " ".join(parts[:max_sentences]).strip()


def _compress_watchlist_section(summary: str) -> str:
    """Trim repeated level narration in emphasized watch blocks."""

    def _compress_match(match: re.Match[str]) -> str:
        block = match.group(0).strip()
        return _limit_sentences(block, 2)

    compressed = re.sub(
        r"(?ms)^\*\*[123]\..*?(?=\n\s*\n(?:\*\*[123]\.|---|##|\*\*The 60-90 minute|\Z))",
        _compress_match,
        summary,
    )
    compressed = re.sub(
        r"(?ms)^\*\*The 60-90 minute if/then sequence:\*\*.*?(?=\n\s*\n(?:---|##|\Z))",
        _compress_match,
        compressed,
    )
    return compressed


def _sanitize_recommendation_language(summary: str) -> str:
    """Keep narratives analytical rather than imperative trade instructions."""
    sanitized = summary
    replacements = [
        (r"\bthe direction of that MSS is the trade\b", "that MSS determines the directional read"),
        (r"\blongs toward\b", "bullish continuation toward"),
        (r"\bshorts toward\b", "bearish continuation toward"),
        (r"\blook for longs toward\b", "watch for bullish continuation toward"),
        (r"\blook for shorts toward\b", "watch for bearish continuation toward"),
        (r"\bbuy the dip\b", "fade the pullback constructively"),
        (r"\bsell the rip\b", "fade strength at resistance"),
        (r"\bthe play is patience\b", "the read favors patience"),
        (r"\bthe play is to\b", "the read is to"),
        (r"\bi'm looking for bullish continuation toward\b", "the bullish continuation path points toward"),
        (r"\bi'm looking for bearish continuation toward\b", "the bearish continuation path points toward"),
        (r"\bi'm looking for\b", "the watch is for"),
        (r"\bi'm watching for\b", "the watch is for"),
        (r"\bi'll respect\b", "the conservative choice is to respect"),
        (r"\bhighest-probability play\b", "highest-probability read"),
        (r"\btrading the direction of that resolution\b", "reading the direction of that resolution"),
        (r"\bposition management matters:?\b", ""),
        (r"\bdon't fade longs\b", "don't fade the bullish read"),
        (r"\blong entry zone\b", "bullish response zone"),
        (r"\bshort entry zone\b", "bearish response zone"),
        (r"\bthe trade executes\b", "the move typically extends"),
        (r"\btake the money and don't give it back\b", "treat the delivery as mature and expect afternoon chop"),
        (r"\brespect that\b", "stand aside"),
        (r"\bstrong long setup\b", "strong bullish read"),
        (r"\bshort opportunity\b", "bearish continuation path"),
        (r"\bsize down\b", "stay conservative"),
        (r"\bavoid chasing\b", "avoid momentum-following"),
    ]
    for pattern, replacement in replacements:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(
        r"(?im)^\*\*Risk management context:\*\*[\s\S]*?(?=^\*\*Bottom line|^##|\Z)",
        "",
        sanitized,
    )
    sanitized = re.sub(
        r"(?im)^.*daily stop is \$\d+[\s\S]*?max \d+ trades\.?\n?",
        "",
        sanitized,
    )
    return sanitized


def _sanitize_open_mode_semantics(summary: str) -> str:
    """Fix recurring open-mode semantic drift the model introduces."""
    sanitized = summary
    sanitized = re.sub(
        r"The play is to",
        "The read is to",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"I'll respect",
        "The conservative choice is to respect",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"first 5m candle close before any consideration",
        "first 15m candle close before any consideration",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"immediate magnet/ceiling",
        "immediate overhead reference (price below dealer floor)",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"The Put Wall being overhead \(not below\) is unusual\s*[—-]\s*it's acting as resistance rather than support, which tells me the dealer positioning is constraining upside in the immediate term\.",
        "The Put Wall printing above current price is unusual — price is trading below the dealer floor reference, which signals unstable structure until that floor is reclaimed.",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


def _sanitize_intraday_mode_semantics(summary: str) -> str:
    """Fix recurring intraday spatial phrasing defects."""
    sanitized = summary
    sanitized = re.sub(
        r"The sell-side liquidity \(SSL\) is at \*\*([0-9,]+\.?[0-9]*)\*\* \(the prior day low\), which is (?:just )?([0-9.]+) points above current price\. That's a magnet — price often gets drawn to sweep resting sell stops below a prior low\.",
        r"The sell-side liquidity (SSL) is at **\1** (the prior day low), which is \2 points above current price. That makes it an overhead liquidity reference that price may reclaim, not a downside sweep target below current price.",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"which is just ([0-9.]+) points above current price\. That's a magnet — price often gets drawn to sweep resting sell stops below a prior low\.",
        r"which is \1 points above current price. That makes it an overhead liquidity reference rather than a downside sweep target below current price.",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"- \*\*Most Likely:\*\* Continued drift toward the SSL at \*\*([0-9,]+\.?[0-9]*)\*\* \([^)]+\) to sweep sell stops, then a bounce\.",
        r"- **Most Likely:** Continued drift lower inside the Asia range, with **\1** acting as the first overhead reclaim level if buyers stabilize the session.",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"Watch whether price sweeps the SSL at ([0-9,]+\.?[0-9]*) first \(bearish continuation setup\)",
        r"Watch whether price reclaims the overhead SSL at \1 first before London establishes direction",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


def _sanitize_close_mode_semantics(summary: str) -> str:
    """Remove remaining close-mode trade-plan phrasing and account-risk leakage."""
    sanitized = summary
    sanitized = re.sub(r"(?im)^\*\*Account Phase:\*\*.*(?:\n|$)", "", sanitized)
    sanitized = re.sub(r"(?im)^\*\*Date:\*\*.*(?:\n|$)", "", sanitized)
    sanitized = re.sub(r"(?im)^\*\*Close:\*\*.*(?:\n|$)", "", sanitized)
    sanitized = re.sub(r"\bbuy the morning\b", "expect a bounce risk into the morning", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bconditional, not a conviction, trade\b", "conditional, not a conviction, read", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bthen trade the first clean setup\b", "then read the first clean setup", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bany long position should be evaluated for exit before the afternoon session\b", "the afternoon session should be treated cautiously if the morning bounce fully matures", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bsize down or avoid entries\b", "treat that window cautiously", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bconditional long setup\b", "conditional bullish setup", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\btrade the first clean setup\b", "read the first clean setup", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bDo NOT trade the initial spike\b", "Do not trust the initial spike", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bWait for the first 5-minute candle to close and the market to establish a direction\b", "Wait for the first 5-minute candle to close so the market can establish direction", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bdo not hold overnight \(account rule\)\b", "do not rely on late-day follow-through after 15:00", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bthe watch is for a long toward\b", "the bullish path points toward", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bthe watch is for a short toward\b", "the bearish path points toward", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bif you trade, size down\b", "treat that window conservatively", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bwait for the NFP reaction to settle before committing\b", "wait for the NFP reaction to settle before assigning conviction", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bstrong long setup\b", "strong bullish read", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bshort opportunity\b", "bearish continuation path", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\blong setup\b", "bullish setup structure", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bshort setup\b", "bearish setup structure", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bscalp day\b", "range-bound day", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bthe disciplined play is to\b", "the disciplined read is to", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bonly take trades that respect\b", "only trust moves that respect", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bsize down and take profits at the range boundaries, not beyond them\b", "keep expectations conservative near the range boundaries", sanitized, flags=re.IGNORECASE)
    return sanitized


def _sanitize_trader_facing_output(summary: str) -> str:
    """Remove debug/provenance artifacts from trader-facing narratives.

    KB source metadata is useful for logs/tests but noisy in execution notes.
    """
    sanitized = summary

    # Remove explicit KB-availability disclaimers from user-facing notes.
    sanitized = re.sub(
        r"(?im)^\s*KB context unavailable;[^\n]*\n?",
        "",
        sanitized,
    )

    # Strip KB citation tokens like [KB:source_file|conf=0.85].
    sanitized = re.sub(r"\s*\[KB:[^\]]+\]", "", sanitized)

    # Remove citation-only bullets left after token stripping.
    sanitized = re.sub(r"(?im)^\s*[-*]\s*\*\*Citation:\*\*[^\n]*\n?", "", sanitized)

    # Rename KB-labeled section to a trader-usable neutral heading.
    sanitized = re.sub(
        r"(?im)^\s{0,3}(#{1,6})\s*KB-Evidenced Drivers\s*$",
        r"\1 Session Drivers",
        sanitized,
    )

    # Remove GitHub links that occasionally leak from mixed KB context.
    sanitized = re.sub(r"https?://github\.com/\S+", "", sanitized, flags=re.IGNORECASE)

    # Replace residual KB wording with neutral language.
    sanitized = re.sub(r"\bKB context\b", "historical context", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bKB tip\b", "historical note", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bKB\b", "", sanitized)

    # Normalize spacing after removals.
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip() + "\n"

    if sanitized != summary:
        log.warning("Trader-facing sanitizer removed KB/debug artifacts from narrative output")

    return sanitized


def _extract_week_modifiers_from_cheatsheet(cheat_sheet: str) -> set[str]:
    """Parse week modifiers from cheat sheet text for consistency guards."""
    m = re.search(r"(?im)^\s*Week Modifiers:\s*(.+)$", cheat_sheet)
    if not m:
        return set()
    parts = [p.strip().upper() for p in m.group(1).split("|") if p.strip()]
    return set(parts)


def _enforce_week_regime_consistency(summary: str, cheat_sheet: str) -> str:
    """Remove obvious cross-regime contamination based on active week modifiers."""
    active_mods = _extract_week_modifiers_from_cheatsheet(cheat_sheet)
    text = summary

    has_fomc = "FOMC WEEK" in active_mods
    has_nfp = "NFP WEEK" in active_mods
    has_opex = "OPEX" in active_mods or "TRIPLE WITCHING" in active_mods

    if not has_fomc:
        text = re.sub(r"(?im)\bFOMC week\b", "Fed-speaker week context", text)

    if not has_opex:
        # Remove direct OPEX analogies when OPEX modifier is not active.
        text = re.sub(
            r"(?im)^.*\bOPEX\b.*(?:similar|rhythm|pattern).*$\n?",
            "",
            text,
        )

    if has_nfp and not has_fomc:
        # Remove mixed phrase that can mislead sequence timing.
        text = re.sub(
            r"(?im)^.*\bFOMC/NFP\b.*$\n?",
            "",
            text,
        )

    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    if text != summary:
        log.warning("Week-regime consistency guard adjusted narrative wording")
    return text


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
        # Use the latest RTH trading day, not the current calendar date.
        # This handles running the narrative after midnight ET (e.g. the
        # EOD narrative at 00:30 ET on July 18 should analyze July 17's
        # session, not July 18's which hasn't started yet).
        try:
            from scripts.utils.fused_data_loader import load_fused_data
            from scripts.trader.briefing_core import get_latest_rth_date
            _df = load_fused_data(tickers[0] if tickers else "NQ1", timeframe="1m", require_historical=False)
            target_date = get_latest_rth_date(_df)
        except Exception:
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
            summary = _enforce_narrative_contract(summary, mode)
            summary = _append_contradiction_check(summary)
            summary = _enforce_week_regime_consistency(summary, cheat_sheet)
            summary = _normalize_taxonomy_language(summary)
            summary = _dedupe_repetition(summary)
            summary = _compress_watchlist_section(summary)
            summary = _sanitize_recommendation_language(summary)
            if mode == "open":
                summary = _sanitize_open_mode_semantics(summary)
            elif mode == "intraday":
                summary = _sanitize_intraday_mode_semantics(summary)
            elif mode == "close":
                summary = _sanitize_close_mode_semantics(summary)
            summary = _sanitize_trader_facing_output(summary)
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

    # Normalize short tickers (ES→ES1, NQ→NQ1, YM→YM1, RTY→RTY1)
    _short_map = {"ES": "ES1", "NQ": "NQ1", "YM": "YM1", "RTY": "RTY1"}
    args.tickers = [_short_map.get(t.upper(), t.upper()) for t in args.tickers]

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