"""
weekly_briefing.py
==================
Stage 1: Weekly Macro Briefing Aggregation.

Reads existing pipeline outputs (macro_levels.json, unified_levels.json)
and price data (via DataLoader) to produce a single compact briefing.json
(the "TOON") optimized for LLM consumption.

Output: reports/weekly/{date}_briefing.json + latest_briefing.json

Usage:
    python -m scripts.trader.weekly_briefing [--tickers SPX QQQ ...]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.trader.briefing_core import (
    ET,
    REPO_ROOT,
    load_macro_levels,
    load_scored_levels,
    load_weekly_ems,
    get_friday_em,
    resolve_track,
    compute_invalidation,
    get_dataloader,
    load_weekly_price_context,
    fetch_week_events,
    get_week_label,
    get_prior_friday,
    save_weekly_briefing_to_db,
    parse_meta_fields,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Default tickers (full universe from config.py ACTIVE_TICKERS)
DEFAULT_TICKERS = [
    "SPX", "SPY", "QQQ", "IWM", "DIA",
    "AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AVGO",
]


def build_ticker_block(
    ticker: str,
    unified_entry: dict,
    loader,
) -> dict | None:
    """Build a single ticker's block for the briefing JSON.

    Reads from unified_levels.json structure (tokens + META_ fields),
    NOT from macro_levels.json (which had futures-translated values).
    """
    if not unified_entry:
        log.warning("  [SKIP] No unified data for %s", ticker)
        return None

    # ── Parse META_ fields from the line string ───────────────────
    meta = parse_meta_fields(unified_entry)

    # ── Extract regime from META_ fields ──────────────────────────
    regime_label = meta.get("REGIME", "NEUTRAL")
    gex_sign = "NEGATIVE" if meta.get("GEX_TOTAL", 0) < 0 else "POSITIVE"
    total_gex = meta.get("GEX_TOTAL", 0)
    concentration_score = meta.get("CONCENTRATION", 0)

    # ── Extract levels from tokens ────────────────────────────────
    tokens = unified_entry.get("tokens", [])

    def _find_token(label_match: str, filter_type: str = None) -> dict | None:
        """Find first token matching label substring and optional filter."""
        for t in tokens:
            if label_match in t.get("label", ""):
                if filter_type is None or t.get("filter") == filter_type:
                    return t
        return None

    cw_token = _find_token("CW", "W") or _find_token("0D CW")
    pw_token = _find_token("PW", "W") or _find_token("0D PW")
    magnet_token = _find_token("MAGNET")
    pin_token = _find_token("PIN")
    # GEX DA pivot: use ZERO GEX DA (delta-adjusted) as the primary zero gamma
    # level for daytrading. Falls back to ZERO GEX if DA is not available or
    # if the DA value is an outlier (more than 20% from spot — happens with
    # index products where delta adjustment can produce extreme values).
    zero_gex_da_token = _find_token("ZERO GEX DA")
    # Find ZERO GEX (raw) — must NOT match ZERO GEX DA, so use exact label match
    zero_gex_token = None
    for t in tokens:
        if t.get("label", "") == "ZERO GEX":
            zero_gex_token = t
            break

    call_wall = cw_token.get("strike", 0) if cw_token else 0
    put_wall = pw_token.get("strike", 0) if pw_token else 0
    gamma_magnet = magnet_token.get("strike", 0) if magnet_token else 0
    pin_strike = pin_token.get("strike", 0) if pin_token else 0

    # Determine spot for the sanity check (use magnet or wall midpoint)
    _ref_spot = gamma_magnet if gamma_magnet > 0 else (
        (call_wall + put_wall) / 2 if call_wall > 0 and put_wall > 0 else 0
    )

    # Primary: ZERO GEX DA (delta-adjusted) — more relevant for daytrading
    # Sanity check: DA value must be within ±20% of spot, otherwise it's an outlier
    zero_gamma = 0
    if zero_gex_da_token and _ref_spot > 0:
        da_value = zero_gex_da_token.get("strike", 0)
        if da_value > 0 and abs(da_value - _ref_spot) / _ref_spot < 0.20:
            zero_gamma = da_value
            log.info("  Using ZERO GEX DA: %s (within range of spot %s)", da_value, _ref_spot)
        else:
            log.warning("  ZERO GEX DA outlier: %s (spot ref: %s) — falling back", da_value, _ref_spot)

    # Fallback: ZERO GEX (raw)
    if zero_gamma == 0 and zero_gex_token:
        zero_gamma = zero_gex_token.get("strike", 0)

    # Final fallback: gamma magnet
    if zero_gamma == 0:
        zero_gamma = gamma_magnet

    # Wall separation
    wall_separation = round(call_wall - put_wall, 2) if call_wall > 0 and put_wall > 0 else 0

    # Pin odds from META_ (not available in tokens)
    pin_odds = meta.get("OI_PIN", 0) / meta.get("OI_CALLWALL", 1) if meta.get("OI_CALLWALL", 0) > 0 else 0

    # ── Volatility from META_ fields ──────────────────────────────
    atm_iv = meta.get("IV", 0)
    skew_premium = meta.get("SKEW", 0)
    skew_direction = "put-heavy" if skew_premium > 0.03 else "balanced"

    # ── Hedge flows from META_ fields ─────────────────────────────
    up_10 = meta.get("HFLOW_UP10", 0)
    up_25 = meta.get("HFLOW_UP25", 0)
    up_50 = meta.get("HFLOW_UP50", 0)
    dn_10 = meta.get("HFLOW_DN10", 0)
    dn_25 = meta.get("HFLOW_DN25", 0)
    dn_50 = meta.get("HFLOW_DN50", 0)

    total_up = abs(up_10) + abs(up_25) + abs(up_50)
    total_dn = abs(dn_10) + abs(dn_25) + abs(dn_50)
    if total_up > total_dn * 1.3:
        hf_bias = "asymmetric_upside"
    elif total_dn > total_up * 1.3:
        hf_bias = "asymmetric_downside"
    else:
        hf_bias = "balanced"

    # ── Resolve mandated execution track (Python, not LLM) ────────
    mandated_track = resolve_track(gex_sign, regime_label)

    # ── Price context via DataLoader (DRY) ────────────────────────
    price_ctx = load_weekly_price_context(loader, ticker)

    # Determine spot price — use prior week close if available, else fallback
    spot = price_ctx.get("prior_week", {}).get("close", 0)
    if spot == 0:
        spot = round((call_wall + put_wall) / 2, 2) if call_wall > 0 and put_wall > 0 else 0

    # ── Expected Moves (computed from weekly close EM in tokens) ──
    weekly_ems = load_weekly_ems(unified_entry, spot)
    friday_em_upper, friday_em_lower = get_friday_em(weekly_ems)

    # ── Scored levels (filtered by significance) ──────────────────
    scored = load_scored_levels(unified_entry, max_levels=6, min_significance="S")

    # ── Account invalidation threshold (Python, not LLM) ──────────
    invalidation = compute_invalidation(
        call_wall=call_wall,
        put_wall=put_wall,
        friday_em_upper=friday_em_upper,
        friday_em_lower=friday_em_lower,
        spot=spot,
        ticker=ticker,
    )

    # ── Build scenarios (pre-computed for LLM) ─────────────────────
    scenarios = build_scenarios(
        track=mandated_track,
        call_wall=call_wall,
        put_wall=put_wall,
        gamma_magnet=gamma_magnet,
        weekly_ems=weekly_ems,
        spot=spot,
    )

    # ── GEX regime interpretation ──────────────────────────────────
    if gex_sign == "NEGATIVE":
        gex_interp = "Dealers short gamma — amplifying moves. Trend-follow environment."
    elif gex_sign == "POSITIVE":
        gex_interp = "Dealers long gamma — dampening moves. Mean-revert environment."
    else:
        gex_interp = "GEX neutral — no strong dealer positioning signal."

    return {
        "ticker": ticker,
        "asset": ticker,  # unified_levels doesn't have a separate asset field
        "spot_price": spot,
        "prior_week": price_ctx.get("prior_week", {}),
        "recent_momentum": price_ctx.get("recent_momentum", {}),
        "gex_regime": {
            "label": regime_label,
            "gex_sign": gex_sign,
            "total_gex": round(total_gex, 2),
            "concentration_score": round(concentration_score, 4),
            "interpretation": gex_interp,
        },
        "mandated_execution_track": mandated_track,
        "key_levels": {
            "call_wall": round(call_wall, 2),
            "put_wall": round(put_wall, 2),
            "zero_gamma": round(zero_gamma, 2),
            "gamma_magnet": round(gamma_magnet, 2),
            "pin_strike": round(pin_strike, 2),
            "pin_odds": round(pin_odds, 4),
            "wall_separation": round(wall_separation, 2),
        },
        "expected_moves": weekly_ems,
        "volatility": {
            "atm_iv": round(atm_iv, 4),
            "skew_premium": round(skew_premium, 4),
            "skew_direction": skew_direction,
        },
        "hedge_flows": {
            "up_10": round(up_10, 2),
            "up_25": round(up_25, 2),
            "up_50": round(up_50, 2),
            "dn_10": round(dn_10, 2),
            "dn_25": round(dn_25, 2),
            "dn_50": round(dn_50, 2),
            "bias": hf_bias,
        },
        "scored_levels": scored,
        "account_invalidation": invalidation,
        "scenarios": scenarios,
    }


def build_scenarios(
    track: str,
    call_wall: float,
    put_wall: float,
    gamma_magnet: float,
    weekly_ems: dict,
    spot: float,
) -> dict:
    """Build pre-computed scenario strings for the LLM.

    The LLM receives these as guidance — it should expand them into
    the required output format, not invent new ones.
    """
    # Get Friday EM as the terminal boundary
    friday = weekly_ems.get("friday", weekly_ems.get("thursday", weekly_ems.get("wednesday", {})))
    em_upper = friday.get("upper", call_wall)
    em_lower = friday.get("lower", put_wall)

    if "TRACK A" in track:
        bullish = (
            f"Acceptance above {call_wall:.2f} (call wall) activates upside expansion. "
            f"Target terminal boundary at {em_upper:.2f} (Friday EM upper)."
        )
        bearish = (
            f"Acceptance below {put_wall:.2f} (put wall) activates short hedging velocity. "
            f"Target terminal liquidation boundary at {em_lower:.2f} (Friday EM lower)."
        )
    elif "TRACK B" in track:
        bullish = (
            f"Fade rallies toward {call_wall:.2f} (call wall). "
            f"Target retracement to Gamma Magnet at {gamma_magnet:.2f}."
        )
        bearish = (
            f"Fade selloffs toward {put_wall:.2f} (put wall). "
            f"Target retracement to Gamma Magnet at {gamma_magnet:.2f}."
        )
    else:
        bullish = "Observation only — no directional scenario until regime clarifies."
        bearish = "Observation only — no directional scenario until regime clarifies."

    neutral = (
        f"Price remains tethered between {put_wall:.2f} (support wall) and "
        f"{call_wall:.2f} (resistance wall), oscillating toward the Gamma Magnet at {gamma_magnet:.2f}."
    )

    return {
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
    }


def build_briefing(tickers: list[str]) -> dict:
    """Aggregate all pipeline outputs into a single briefing JSON."""
    now = datetime.now(ET)
    log.info("══════════════════════════════════════════════════")
    log.info("  WEEKLY MACRO BRIEFING — Aggregation")
    log.info("  Generated: %s ET", now.strftime("%Y-%m-%d %H:%M"))
    log.info("══════════════════════════════════════════════════\n")

    # ── Load pipeline outputs ─────────────────────────────────────
    log.info("Loading macro_levels.json...")
    all_macro = load_macro_levels()
    log.info("  Found %d tickers in macro_levels.json", len(all_macro))

    # ── Initialize DataLoader (DRY — reuses existing framework) ────
    log.info("Initializing DataLoader...")
    loader = get_dataloader(lookback_days=45)

    # ── Build per-ticker blocks ────────────────────────────────────
    ticker_blocks = []
    for ticker in tickers:
        log.info("\nProcessing %s...", ticker)
        macro_entry = all_macro.get(ticker)
        block = build_ticker_block(ticker, macro_entry, loader)
        if block:
            ticker_blocks.append(block)
            log.info("  ✓ Track: %s", block["mandated_execution_track"][:60])
            log.info("  ✓ Spot: %s", block["spot_price"])
            log.info("  ✓ Call Wall: %s | Put Wall: %s",
                     block["key_levels"]["call_wall"],
                     block["key_levels"]["put_wall"])
            log.info("  ✓ Invalidation: B=%s / S=%s",
                     block["account_invalidation"]["bullish_invalidation"],
                     block["account_invalidation"]["bearish_invalidation"])

    # ── Economic events for the upcoming week ─────────────────────
    prior_friday = get_prior_friday(now.date())
    next_friday = prior_friday + timedelta(days=7)
    log.info("\nFetching economic events for %s → %s...", prior_friday, next_friday)
    events = fetch_week_events(prior_friday, next_friday)
    log.info("  Found %d events", len(events))

    # ── Assemble briefing ────────────────────────────────────────
    week_label = get_week_label(now.date())

    briefing = {
        "meta": {
            "generated_at": now.isoformat(),
            "week_label": week_label,
            "prior_week_close": prior_friday.strftime("%Y-%m-%d"),
            "tickers_covered": len(ticker_blocks),
        },
        "economic_events": events,
        "tickers": ticker_blocks,
    }

    return briefing


def save_briefing(ticker_blocks: list[dict], week_start: date, week_end: date) -> str:
    """Save briefing to Prisma DB (DB-first — no JSON files).

    Creates a WeeklyBriefing parent + WeeklyBriefingTicker children.
    Returns the briefing ID.
    """
    return asyncio.run(save_weekly_briefing_to_db(week_start, week_end, ticker_blocks))


def main():
    parser = argparse.ArgumentParser(description="Weekly Macro Briefing Aggregation")
    parser.add_argument(
        "--tickers", nargs="+", default=DEFAULT_TICKERS,
        help="Tickers to include in the briefing",
    )
    args = parser.parse_args()

    # Build ticker blocks (in-memory only — not persisted as JSON)
    now = datetime.now(ET)
    all_macro = load_macro_levels()
    loader = get_dataloader(lookback_days=45)

    log.info("══════════════════════════════════════════════════")
    log.info("  WEEKLY MACRO BRIEFING — DB-First Aggregation")
    log.info("  Generated: %s ET", now.strftime("%Y-%m-%d %H:%M"))
    log.info("══════════════════════════════════════════════════\n")

    ticker_blocks = []
    for ticker in args.tickers:
        log.info("Processing %s...", ticker)
        macro_entry = all_macro.get(ticker)
        block = build_ticker_block(ticker, macro_entry, loader)
        if block:
            ticker_blocks.append(block)
            log.info("  ✓ Track: %s", block["mandated_execution_track"][:60])
            log.info("  ✓ Spot: %s | CW: %s | PW: %s",
                     block["spot_price"],
                     block["key_levels"]["call_wall"],
                     block["key_levels"]["put_wall"])
            log.info("  ✓ Invalidation: B=%s / S=%s",
                     block["account_invalidation"]["bullish_invalidation"],
                     block["account_invalidation"]["bearish_invalidation"])

    # Compute week dates
    prior_friday = get_prior_friday(now.date())
    week_start = prior_friday + timedelta(days=3)  # Monday
    week_end = prior_friday + timedelta(days=7)    # Next Friday

    # Save to DB
    briefing_id = save_briefing(ticker_blocks, week_start, week_end)

    # Summary
    log.info("\n══════════════════════════════════════════════════")
    log.info("  BRIEFING SAVED TO DB")
    log.info("  Briefing ID: %s", briefing_id)
    log.info("  Week: %s → %s", week_start, week_end)
    log.info("  Tickers: %d", len(ticker_blocks))
    log.info("══════════════════════════════════════════════════")

    return briefing_id


if __name__ == "__main__":
    main()