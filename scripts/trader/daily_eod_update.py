"""
daily_eod_update.py
===================
Stage 1: Daily Progress Check Aggregation (Open & EOD).

Compares current price action against the latest weekly briefing anchor
(stored in Prisma DB). Computes level interactions, track alignment,
and invalidation proximity.

Output: DailyEodUpdate + DailyEodTickerSnapshot rows in Prisma DB.

Usage:
    python -m scripts.trader.daily_eod_update [--session open|eod] [--tickers SPX QQQ ...]
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.trader.briefing_core import (
    ET,
    REPO_ROOT,
    load_macro_levels,
    parse_meta_fields,
    resolve_track,
    compute_invalidation,
    compute_level_interactions,
    assess_track_alignment,
    get_dataloader,
    load_daily_price_context,
    save_daily_eod_to_db,
    load_weekly_briefing_from_db,
    translate_level_to_futures,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

DEFAULT_TICKERS = [
    "SPX", "SPY", "QQQ", "IWM", "DIA",
    "AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AVGO",
]


def build_daily_snapshot(
    ticker: str,
    unified_entry: dict,
    weekly_anchor: dict,
    loader,
    today_date: date,
    days_elapsed: int,
    days_remaining: int,
) -> dict | None:
    """Build a single ticker's daily EOD snapshot."""
    if not unified_entry:
        log.warning("  [SKIP] No unified data for %s", ticker)
        return None

    # ── Parse current META_ fields (today's regime) ────────────────
    meta = parse_meta_fields(unified_entry)
    current_regime = meta.get("REGIME", "NEUTRAL")

    # ── Extract current levels from tokens ─────────────────────────
    tokens = unified_entry.get("tokens", [])

    def _find_token(label_match: str, filter_type: str = None) -> dict | None:
        for t in tokens:
            if label_match in t.get("label", ""):
                if filter_type is None or t.get("filter") == filter_type:
                    return t
        return None

    cw_token = _find_token("CW", "W") or _find_token("0D CW")
    pw_token = _find_token("PW", "W") or _find_token("0D PW")
    em_hi_token = next((t for t in tokens if "EM HI" in t.get("label", "") and "EM85" not in t.get("label", "")), None)
    em_lo_token = next((t for t in tokens if "EM LO" in t.get("label", "") and "EM85" not in t.get("label", "")), None)

    call_wall_raw = cw_token.get("strike", 0) if cw_token else 0
    put_wall_raw = pw_token.get("strike", 0) if pw_token else 0
    em_upper_raw = em_hi_token.get("strike", 0) if em_hi_token else 0
    em_lower_raw = em_lo_token.get("strike", 0) if em_lo_token else 0

    call_wall = translate_level_to_futures(ticker, call_wall_raw, meta)
    put_wall = translate_level_to_futures(ticker, put_wall_raw, meta)
    em_upper = translate_level_to_futures(ticker, em_upper_raw, meta)
    em_lower = translate_level_to_futures(ticker, em_lower_raw, meta)

    # ── Today's price action via DataLoader ────────────────────────
    today_price = load_daily_price_context(loader, ticker)
    if not today_price:
        log.warning("  [SKIP] No price data for %s", ticker)
        return None

    # Keep SPY/QQQ daily price action in futures scale to match translated
    # structural levels used by narratives and risk logic.
    if ticker in {"SPY", "QQQ"}:
        for key in ("open", "high", "low", "close"):
            today_price[key] = translate_level_to_futures(ticker, today_price.get(key, 0), meta)

    # ── Weekly anchor levels ───────────────────────────────────────
    mandated_track = weekly_anchor.get("mandated_track", "")
    weekly_call_wall = weekly_anchor.get("call_wall", call_wall)
    weekly_put_wall = weekly_anchor.get("put_wall", put_wall)
    weekly_bull_inv = weekly_anchor.get("bullish_invalidation", 0)
    weekly_bear_inv = weekly_anchor.get("bearish_invalidation", 0)
    weekly_regime = weekly_anchor.get("regime_label", "NEUTRAL")

    # ── Level interactions ─────────────────────────────────────────
    interactions = compute_level_interactions(
        today=today_price,
        call_wall=call_wall,
        put_wall=put_wall,
        em_upper=em_upper,
        em_lower=em_lower,
        zero_gamma=0,  # not needed for daily
        gamma_magnet=0,
    )

    # ── Track alignment assessment ──────────────────────────────────
    on_track, track_assessment = assess_track_alignment(
        track=mandated_track,
        today=today_price,
        interactions=interactions,
    )

    # ── Invalidation proximity ────────────────────────────────────
    close = today_price.get("close", 0)
    dist_bullish = round(abs(close - weekly_bull_inv) / close * 100, 2) if close > 0 and weekly_bull_inv > 0 else 999
    dist_bearish = round(abs(weekly_bear_inv - close) / close * 100, 2) if close > 0 and weekly_bear_inv > 0 else 999

    nearest_inv = "bullish" if dist_bullish < dist_bearish else "bearish"
    nearest_dist = min(dist_bullish, dist_bearish)

    # ── Position in EM envelope ────────────────────────────────────
    if em_upper > 0 and em_lower > 0 and em_upper > em_lower:
        position_in_em = round((close - em_lower) / (em_upper - em_lower), 4)
        position_in_em = max(0.0, min(1.0, position_in_em))
    else:
        position_in_em = None

    # ── Regime change check ────────────────────────────────────────
    regime_changed = current_regime.upper() != weekly_regime.upper()

    return {
        "ticker": ticker,
        # Today's price action
        "open_price": today_price.get("open", 0),
        "high_price": today_price.get("high", 0),
        "low_price": today_price.get("low", 0),
        "close_price": today_price.get("close", 0),
        "change_pct": today_price.get("change_pct", 0),
        "range_pct": today_price.get("range_pct", 0),
        "body": today_price.get("body", ""),
        # Weekly anchor reference
        "mandated_track": mandated_track,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "today_em_upper": em_upper,
        "today_em_lower": em_lower,
        # Level interactions
        "call_wall_tested": interactions["call_wall_tested"],
        "call_wall_broken": interactions["call_wall_broken"],
        "put_wall_tested": interactions["put_wall_tested"],
        "put_wall_broken": interactions["put_wall_broken"],
        "em_upper_tested": interactions["em_upper_tested"],
        "em_upper_broken": interactions["em_upper_broken"],
        "em_lower_tested": interactions["em_lower_tested"],
        "em_lower_broken": interactions["em_lower_broken"],
        # Invalidation proximity
        "bullish_invalidation": weekly_bull_inv,
        "bearish_invalidation": weekly_bear_inv,
        "dist_to_bullish_inv_pct": dist_bullish,
        "dist_to_bearish_inv_pct": dist_bearish,
        # Track alignment
        "on_track": on_track,
        "track_assessment": track_assessment,
        # Regime check
        "weekly_regime": weekly_regime,
        "current_regime": current_regime,
        "regime_changed": regime_changed,
        # Weekly progress
        "position_in_em_envelope": position_in_em,
        "days_elapsed_in_week": days_elapsed,
        "days_remaining_in_week": days_remaining,
    }


async def run_daily_update(tickers: list[str], session: str = "eod") -> str:
    """Main daily aggregation flow.

    1. Load latest weekly briefing from DB (the anchor)
    2. Load current unified levels based on session (live/open/close)
    3. Load today's price via DataLoader
    4. Compute interactions, track alignment, invalidation proximity
    5. Save to DB
    """
    now = datetime.now(ET)
    today = now.date()

    log.info("══════════════════════════════════════════════════")
    log.info("  DAILY %s PROGRESS CHECK — %s ET", session.upper(), now.strftime("%Y-%m-%d %H:%M"))
    log.info("══════════════════════════════════════════════════\n")

    # 1. Load weekly briefing from DB
    log.info("Loading weekly briefing from DB...")
    weekly_data = await load_weekly_briefing_from_db()
    if not weekly_data:
        raise RuntimeError("No weekly briefing found in DB. Run weekly_briefing.py first.")

    briefing_id = weekly_data["meta"]["id"]
    log.info("  Weekly briefing: %s (%d tickers)", briefing_id, len(weekly_data["tickers"]))

    # Build a lookup of weekly anchor data per ticker
    weekly_lookup = {}
    for t in weekly_data["tickers"]:
        weekly_lookup[t["ticker"]] = {
            "mandated_track": t.get("mandated_execution_track", ""),
            "call_wall": t.get("key_levels", {}).get("call_wall", 0),
            "put_wall": t.get("key_levels", {}).get("put_wall", 0),
            "bullish_invalidation": t.get("account_invalidation", {}).get("bullish_invalidation", 0),
            "bearish_invalidation": t.get("account_invalidation", {}).get("bearish_invalidation", 0),
            "regime_label": t.get("gex_regime", {}).get("label", "NEUTRAL"),
        }

    # 2. Load current unified levels based on session
    log.info("Loading unified levels for session: %s...", session)
    # Map 'open' -> 'open', 'eod' -> 'close', 'live' -> 'live'
    session_map = {"open": "open", "eod": "close", "live": "live"}
    all_unified = load_macro_levels(session=session_map.get(session, "live"))

    # 3. Initialize DataLoader
    log.info("Initializing DataLoader...")
    loader = get_dataloader(lookback_days=10)

    # 4. Compute days elapsed/remaining in week
    # Week starts Monday. If today is Saturday/Sunday, we're between weeks.
    day_of_week = today.weekday()  # 0=Monday, 6=Sunday
    if day_of_week < 5:  # Mon-Fri
        days_elapsed = day_of_week + 1
        days_remaining = 5 - days_elapsed
    else:  # Weekend
        days_elapsed = 5
        days_remaining = 0

    log.info("  Days elapsed: %d/5, remaining: %d", days_elapsed, days_remaining)

    # 5. Build per-ticker snapshots
    snapshots = []
    for ticker in tickers:
        log.info("\nProcessing %s...", ticker)
        unified_entry = all_unified.get(ticker)
        weekly_anchor = weekly_lookup.get(ticker, {})

        if not weekly_anchor:
            log.warning("  [SKIP] No weekly anchor for %s", ticker)
            continue

        snap = build_daily_snapshot(
            ticker=ticker,
            unified_entry=unified_entry,
            weekly_anchor=weekly_anchor,
            loader=loader,
            today_date=today,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
        )
        if snap:
            snapshots.append(snap)
            track_status = "ON TRACK" if snap["on_track"] else "⚠️ OFF TRACK"
            log.info("  ✓ Close: %s (%s%%) | %s", snap["close_price"], snap["change_pct"], track_status)
            log.info("  ✓ CW tested: %s | PW tested: %s", snap["call_wall_tested"], snap["put_wall_tested"])
            log.info("  ✓ Inv proximity: B=%s%% / S=%s%%", snap["dist_to_bullish_inv_pct"], snap["dist_to_bearish_inv_pct"])

    # 6. Save to DB
    # Note: save_daily_eod_to_db is the DB helper. We use it for both Open and EOD.
    eod_id = await save_daily_eod_to_db(today, briefing_id, snapshots)

    log.info("\n══════════════════════════════════════════════════")
    log.info("  DAILY %s SAVED TO DB", session.upper())
    log.info("  EOD ID: %s", eod_id)
    log.info("  Date: %s", today)
    log.info("  Tickers: %d", len(snapshots))
    log.info("══════════════════════════════════════════════════")

    return eod_id


def main():
    parser = argparse.ArgumentParser(description="Daily Progress Check (Open/EOD)")
    parser.add_argument(
        "--session", choices=["open", "eod", "live"], default="eod",
        help="Session to process (default: eod)",
    )
    parser.add_argument(
        "--tickers", nargs="+", default=DEFAULT_TICKERS,
        help="Tickers to include",
    )
    args = parser.parse_args()

    eod_id = asyncio.run(run_daily_update(args.tickers, session=args.session))
    return eod_id


if __name__ == "__main__":
    main()