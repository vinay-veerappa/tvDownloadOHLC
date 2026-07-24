"""Production KB context retriever for the narrative engine.

Extracted from ``test_narrative.py`` so that production code
(``briefing_core.build_premarket_context`` et al.) can import
``fetch_kb_context`` without depending on a test module.

The KB API (producer repo ``video2pdf/knowledge_ingest/serve.py``) must be
running on port 8900. If it is unreachable, all functions degrade gracefully
(return ``""`` / ``False``) so the narrative pipeline never hard-fails.

Concept triggers mirror ``kb_bridge.CONCEPT_TRIGGERS`` in the producer repo.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_KB_API_URL = "http://127.0.0.1:8900"

# Concept triggers (mirrors kb_bridge.py CONCEPT_TRIGGERS in producer repo).
# Keys are substrings scanned for (case-insensitive) in the cheat sheet;
# values are the semantic queries sent to the KB API /search endpoint.
CONCEPT_TRIGGERS: dict[str, str] = {
    "FVG": "fair value gap imbalance entry",
    "CSD": "change in state of delivery CSD entry",
    "MSS": "market structure shift MSS",
    "order block": "order block entry OB",
    "liquidity sweep": "liquidity sweep buy-side sell-side",
    "Judas": "Judas swing fake move London session",
    "Power of Three": "power of three accumulation manipulation distribution",
    "Po3": "power of three accumulation manipulation distribution",
    "MMXM": "market maker buy sell model MMXM",
    "Silver Bullet": "silver bullet entry window",
    "OTE": "optimal trade entry OTE",
    "killzone": "killzone trading session timing",
    "overnight session": "overnight session ONS profile trading",
    "premium": "premium discount dealing range",
    "discount": "premium discount dealing range",
    "PDH": "prior day high low reference level",
    "PDL": "prior day high low reference level",
    "midnight open": "midnight open reference level",
    "7 Rule": "Kish 7 Rules execution framework",
    "trendline": "trendline entry model",
    "breaker": "breaker block entry",
    "turtle soup": "turtle soup liquidity sweep",
    "CISD": "change in state of delivery CISD",
    "NWOG": "new week opening gap",
    "NDOG": "new day opening gap",
    "IPDA": "interbank price delivery algorithm",
    "draw on liquidity": "draw on liquidity DOL",
    "HOD": "high of day",
    "LOD": "low of day",
    "target": "target liquidity unfinished business",
    "stop": "stop placement invalidation",
    # Additional triggers for confluence-rich cheat sheets
    "Herman": "Herman liquidity sweep pre-NY session",
    "sweep": "liquidity sweep buy-side sell-side",
    "imbalance": "imbalance fair value gap delivery",
    "dealing range": "premium discount dealing range",
    "delivery triad": "ICT delivery triad order block FVG",
    "GEX": "gamma exposure options flow dealer positioning",
    "VWAP": "volume weighted average price anchor",
    "POC": "point of control volume profile",
    "ALN": "Asia London New York session liquidity",
    "RTH": "regular trading hours open break",
    # ── Conditional session knowledge triggers ──
    # These catch the cheat sheet's session-outcome language and retrieve
    # KB units about how one session's behavior predicts the next session.
    # The goal is to surface conditional rules (e.g. "large Asia range → NY
    # AM mean reversion", "PM liquidity run in the next morning session").
    "asia range": "Asia range size session conditional behavior continuation reversion NY AM",
    "asia": "Asia session range overnight conditional behavior NY AM prediction",
    "london range": "London range session conditional behavior breakout NY",
    "london": "London session range sweep conditional NY session behavior",
    "herman asia": "Herman Asia range size continuation mean reversion conditional",
    "pre-ny": "pre-NY sweep London low high conditional session behavior",
    "pre-london": "pre-London sweep Asia range conditional session behavior",
    "london low": "London low high sweep conditional NY session behavior",
    "london high": "London low high sweep conditional NY session behavior",
    "day type": "ICT day type conditional session behavior R1 R2 DWP DNP",
    "classification": "ICT day type conditional session behavior classification",
    "overnight range": "overnight session range profile predicts RTH behavior",
    "opening range": "opening range breakout OR conditional session behavior",
    "IB status": "initial balance IB break conditional day type behavior",
    "session bias": "session bias model conditional time of day probability",
    "noon curve": "noon curve AM session opposite side conditional probability",
    "lunch range": "lunch range breakout PM session conditional behavior",
    "macro": "ICT macro window timing probability setup conditional",
    "profile": "ICT session profile overnight daily conditional behavior prediction",
    # ── Weekly-level triggers ──
    # These catch weekly narrative language and retrieve KB units about
    # weekly profiles, opex behavior, NWOG, and Kish's weekly framework.
    "weekly profile": "ICT weekly profile bullish run bearish run inside outside balanced",
    "ICT Profile": "ICT weekly profile archetype Monday Tuesday development",
    "opex": "opex week trading behavior options expiration Monday Tuesday Wednesday sell-off",
    "OPEX": "opex week trading behavior options expiration Monday Tuesday Wednesday sell-off",
    "triple witching": "triple witching opex week dealer hedging expiration",
    "NWOG": "new week opening gap NWOG Monday open weekly gap",
    "new week": "new week opening gap NWOG Monday weekly development",
    "Monday": "Monday Tuesday range development weekly structure ICT profile",
    "Tuesday": "Monday Tuesday range development weekly structure ICT high low of week",
    "Wednesday": "Wednesday CSD reversal weekly profile expansion",
    # Abbreviated day names (used in weekly cheat sheet)
    "Mon ": "Monday Tuesday range development weekly structure ICT profile",
    "Tue ": "Monday Tuesday range development weekly structure ICT high low of week",
    "Wed ": "Wednesday CSD reversal weekly profile expansion",
    "Thu ": "Thursday Friday weekly profile continuation trend day",
    "Fri ": "Friday weekly profile NFP opex expiration close",
    "archetype": "ICT weekly archetype profile execution strategy conditional",
    "engineered origin": "engineered origin EO range weekly open Monday Tuesday",
    "weekly open": "weekly open engineered origin range Monday Tuesday development",
    "seek and destroy": "seek and destroy chop week NFP Friday conditional behavior",
    "High-Impact Cluster": "high impact cluster week multiple catalysts repricing conditional",
    "FOMC": "FOMC week consolidation expansion Wednesday Federal Reserve",
    "CPI": "CPI week early catalyst Tuesday repricing trend",
    "NFP": "NFP Friday non-farm payroll seek destroy chop week",
    "7 Rule": "Kish 7 Rules execution framework weekly timeframe planning",
    "Kish": "Kish weekly timeframe framework profile execution planning",
}


def check_kb_api(url: str = DEFAULT_KB_API_URL, timeout: float = 5.0) -> bool:
    """Return True if the KB API health endpoint responds OK."""
    try:
        req = urllib.request.Request(f"{url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok"
    except Exception:
        return False


def detect_concepts(text: str) -> dict[str, str]:
    """Scan ``text`` for concept triggers; return ``{trigger: query}``."""
    lower = text.lower()
    found: dict[str, str] = {}
    for trigger, query in CONCEPT_TRIGGERS.items():
        if trigger.lower() in lower:
            found[trigger] = query
    return found


def _search_kb(query: str, k: int, kb_api_url: str, timeout: float = 10.0) -> list[dict]:
    """POST /search to the KB API and return the raw units list."""
    body = json.dumps({"query": query, "k": k}).encode()
    req = urllib.request.Request(
        f"{kb_api_url}/search",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    if isinstance(data, list):
        return data
    return []


def fetch_kb_context(
    cheat_sheet: str,
    kb_api_url: str = DEFAULT_KB_API_URL,
    *,
    max_context_chars: int = 8000,
    k_per_concept: int = 3,
    timeout: float = 10.0,
) -> str:
    """Retrieve KB context for the cheat sheet via the KB API.

    Scans the cheat sheet for ICT concept triggers, queries the KB for each,
    dedupes by ``unit_id``, and returns a formatted context block
    (``# ICT KNOWLEDGE BASE CONTEXT ...``). Returns ``""`` if the API is
    unreachable, no concepts are detected, or no units match.

    Session-interplay triggers (asia, london, pre-ny, etc.) are processed
    FIRST so conditional session knowledge isn't crowded out by generic
    setup triggers (FVG, CSD, etc.) within the char budget.
    """
    if not check_kb_api(kb_api_url):
        log.debug("[kb_context] KB API unreachable at %s — returning empty", kb_api_url)
        return ""

    found = detect_concepts(cheat_sheet)
    if not found:
        log.debug("[kb_context] No concept triggers detected in cheat sheet")
        return ""

    # Prioritize session-interplay triggers so conditional knowledge
    # (Asia-London-NY interplay) is retrieved before generic setup triggers
    # (FVG, CSD) that would otherwise consume the char budget.
    _SESSION_PRIORITY = {
        "asia", "london", "pre-ny", "pre-london", "london low", "london high",
        "ALN", "Herman", "herman asia", "day type", "classification",
        "overnight range", "opening range", "IB status", "session bias",
        "noon curve", "lunch range", "macro", "profile", "RTH",
        "asia range", "london range",
        # Weekly-level priorities
        "weekly profile", "ICT Profile", "opex", "OPEX", "triple witching",
        "NWOG", "new week", "Monday", "Tuesday", "Wednesday",
        "archetype", "engineered origin", "weekly open", "seek and destroy",
        "High-Impact Cluster", "FOMC", "CPI", "NFP", "7 Rule", "Kish",
    }
    ordered = sorted(found.items(), key=lambda kv: (0 if kv[0] in _SESSION_PRIORITY else 1, kv[0]))

    all_units: list[dict] = []
    seen_ids: set[str] = set()

    for concept, query in ordered:
        try:
            units = _search_kb(query, k_per_concept, kb_api_url, timeout)
        except Exception as e:
            log.debug("[kb_context] search failed for %r: %s", concept, e)
            continue
        for u in units:
            uid = u.get("unit_id", str(id(u)))
            if uid not in seen_ids:
                all_units.append(u)
                seen_ids.add(uid)

    if not all_units:
        return ""

    # Format as context block
    lines: list[str] = []
    total = 0
    for u in all_units:
        ktype = u.get("knowledge_type", "?")
        summary = (u.get("summary") or "")[:200]
        concepts = u.get("concepts", "")
        confidence = u.get("confidence", 0.0)
        source_file = u.get("source_file", "?")
        verbatim = u.get("verbatim_anchor") or ""
        sessions = u.get("sessions", "")
        instruments = u.get("instruments", "")

        # Extract timeframe mentions from concepts (e.g. timeframe_m5, timeframe_m1)
        timeframes: list[str] = []
        if concepts:
            for token in concepts.split(","):
                token = token.strip()
                if token.startswith("timeframe_"):
                    tf = token.replace("timeframe_", "").upper()
                    if tf not in timeframes:
                        timeframes.append(tf)

        # Build block with session + timeframe context
        meta_parts: list[str] = []
        if timeframes:
            meta_parts.append(f"TFs: {', '.join(timeframes)}")
        if sessions and sessions != "any":
            meta_parts.append(f"Session: {sessions}")
        if instruments and instruments != "any":
            meta_parts.append(f"Instrument: {instruments}")
        meta_line = f"  Context: {' | '.join(meta_parts)}\n" if meta_parts else ""

        block = (
            f"[{ktype}] {source_file} (conf={confidence:.2f})\n"
            f"  Concepts: {concepts}\n"
            f"{meta_line}"
            f"  Summary: {summary}\n"
            f"  Anchor: {verbatim}\n"
        )
        if total + len(block) > max_context_chars:
            break
        lines.append(block)
        total += len(block)

    header = (
        f"# ICT KNOWLEDGE BASE CONTEXT (retrieved {len(lines)} units)\n"
        f"# Concepts detected: {', '.join(found.keys())}\n"
        f"# These are grounded source materials from ICT transcripts.\n"
        f"# Each unit includes Context (timeframes, session, instrument) where available.\n"
        f"# Use for terminology, methodology context, and setup definitions.\n"
    )
    return "\n".join([header] + lines)


__all__ = [
    "DEFAULT_KB_API_URL",
    "CONCEPT_TRIGGERS",
    "check_kb_api",
    "detect_concepts",
    "fetch_kb_context",
]