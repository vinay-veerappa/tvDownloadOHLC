"""
run_options_levels.py
=====================
Main entry point for the automated Dealer Levels pipeline.

This script orchestrates:
  1. Authenticated Schwab API data fetch (options chains + futures quotes)
  2. GEX / Expected-Move / Wall calculations for SPX and NDX
  3. Cash-to-futures basis translation (SPX->ES, NDX->NQ)
  4. Discord webhook notification
  5. JSON + TXT file output for Pine Script ingestion

Usage
-----
Run once immediately::

    python -m scripts.streaming.options.run_options_levels

Run on a schedule (blocks, press Ctrl-C to stop)::

    python -m scripts.streaming.options.run_options_levels --schedule

Override the run label::

    python -m scripts.streaming.options.run_options_levels --label "08:30 Pre-Market"

Add a new index pair by editing ``ASSET_PAIRS`` in this file or by
extending ``config.PRIMARY_INDEX_TICKERS`` / ``config.INDEX_TO_FUTURES``.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# MULTIPROCESSING GUARD
# On Windows, multiprocessing.spawn re-imports this module as __main__ in the
# child process.  We want the child to skip all heavy imports (Prisma, Schwab,
# GEX calculator …) and just run the RTD worker.  The child sets this env var
# before importing so we can detect that case and bail out early.
# ---------------------------------------------------------------------------
import os as _os
import logging
import sys
import time

_IS_RTD_CHILD = _os.environ.get("_RTD_WORKER_CHILD") == "1"

if not _IS_RTD_CHILD:
    import argparse
    import json
    from dataclasses import replace
    from datetime import datetime, date, timedelta
    from pathlib import Path
    from zoneinfo import ZoneInfo
    from typing import Any

if not _IS_RTD_CHILD:
    from .config import (
        ACTIVE_TICKERS,
        DTE_TARGETS,
        ENABLE_DISCORD_UPDATES,
        ETF_FALLBACK,
        INDEX_TO_FUTURES,
        EOD_FUTURES_CLOSE_TIME,
        EOD_SPX_CLOSE_TIME,
        LOG_FILE,
        MIN_NONZERO_OI_CONTRACTS,
        PRIORITY_TICKERS,
        REPO_ROOT,
        SCHEDULE_TIMES,
        SCHEDULE_TIMEZONE,
        SECRETS_PATH,
        TIER2_INTERVAL_SECONDS,
        TOKEN_PATH,
        USE_OPENING_BASIS,
        RTH_T1_INTERVAL,
        RTH_T2_INTERVAL,
        OFF_HOURS_T1_INTERVAL,
        OFF_HOURS_T2_INTERVAL,
        WEEKEND_T1_INTERVAL,
        WEEKEND_T2_INTERVAL,
        EQUITY_RTH_START_TIME,
        EQUITY_RTH_END_TIME,
        OPTIONS_RTH_START_TIME,
        OPTIONS_RTH_END_TIME,
        FUTURES_CLOSE_FRIDAY_TIME,
        FUTURES_OPEN_SUNDAY_TIME,
        MANUAL_TRIGGER_FILENAME,
        TIER1_TICKERS_DEFAULT,
        LOOP_BEAT_SECONDS,
        SCHEDULER_MISFIRE_GRACE_TIME,
        MACRO_DTE_TARGETS,
        PIPELINE_DTE_TARGETS,
        MACRO_VIEW,
        INTRADAY_VIEW,
        get_ticker_profile,
        SCORED_LEVELS_TXT,
        SCORED_MACRO_LEVELS_TXT,
        BASIS_ANCHORS_JSON,
        UNIFIED_LEVELS_TXT,
        UNIFIED_LEVELS_JSON,
        ENABLE_UNIFIED_CONTRACT_OUTPUTS,
        ENABLE_SCORED_CONTRACT_OUTPUTS,
        PIPELINE_DEBUG_TICKER,
        PIPELINE_DEBUG_RTD,
    )
    from .discord_notifier import send_discord_update, send_regime_change_alert
    from .file_writer import (
        write_levels,
        _is_rth,
        write_scored_levels_txt,
        write_unified_levels_txt,
        write_unified_levels_json,
        unified_payload_fingerprint,
    )
    from .futures_translator import translate_to_futures
    from .gex_calculator import (
        DealerLevels,
        calculate_dealer_levels,
        calculate_price_metrics,
    )
    from .level_scorer import score_levels, ScoredLevels
    from .options_fetcher import create_client, fetch_futures_quote, fetch_batched_futures_quotes, fetch_option_chain_data, merge_option_chains, get_eod_close_price, FuturesQuote
    from .state_tracker import (
        build_current_state,
        detect_changes,
        format_change_alert,
        load_previous_state,
        save_current_state,
    )
    from .macro_pipeline import run_macro_pipeline
    from .formatting import (
        build_plan,
        copy_ready_line,
        fmt,
        HasLevels,
    )

    # TOS RTD hybrid coordinator (optional, Windows-only, opt-in)
    from .tos_rtd.hybrid_coordinator import HybridCoordinator

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persistent storage map (run-to-run state)
# ---------------------------------------------------------------------------
# 1) BASIS_ANCHORS_JSON (config): daily translation anchors captured near open
#    and reused for futures translation consistency.
# 2) WEEKLY_SCOPE_CACHE_JSON: Friday EOD weekly expected-move scope snapshot
#    (including EM85 bounds), reused Mon-Fri until expiry rollover.
# 3) pipeline_state.json (via state_tracker): previous vs current regime state
#    for change detection and alerting.
# ---------------------------------------------------------------------------
if not _IS_RTD_CHILD:
    WEEKLY_SCOPE_CACHE_JSON = REPO_ROOT / "data" / "options" / "weekly_em_scope.json"
    DISCORD_ALLOWED_SNAPSHOT_SUFFIXES = {"0930", "1615"}


# ---------------------------------------------------------------------------
# Logging setup — deferred to _setup_logging() so it only runs when the
# module is executed as an entry point, not on every import.
# ---------------------------------------------------------------------------

_logging_configured = False


def _setup_logging() -> None:
    global _logging_configured
    if _logging_configured:
        return
    from .config import PIPELINE_DEBUG
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if PIPELINE_DEBUG else logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s" if not PIPELINE_DEBUG else "%(asctime)s  %(levelname)-5s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )
    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _logging_configured = True


def _chain_has_actionable_oi(chain) -> bool:
    contracts = chain.calls + chain.puts
    nonzero_oi = sum(1 for contract in contracts if contract.open_interest > 0)
    return nonzero_oi >= MIN_NONZERO_OI_CONTRACTS


# ---------------------------------------------------------------------------
# Basis Anchors Persistence
# ---------------------------------------------------------------------------

def load_basis_anchors() -> dict[str, dict]:
    """Load daily basis anchors from disk."""
    if not BASIS_ANCHORS_JSON.exists():
        return {}
    try:
        with open(BASIS_ANCHORS_JSON, "r") as f:
            data = json.load(f)
            # Validate it's for today
            today = datetime.now(ZoneInfo(SCHEDULE_TIMEZONE)).strftime("%Y-%m-%d")
            if data.get("date") != today:
                log.info("Basis anchor file is from a previous day (%s). Resetting.", data.get("date"))
                return {}
            return data.get("anchors", {})
    except Exception as e:
        log.error("Failed to load basis anchors: %s", e)
        return {}


def save_basis_anchors(anchors: dict[str, dict]) -> None:
    """Save daily basis anchors to disk."""
    try:
        today = datetime.now(ZoneInfo(SCHEDULE_TIMEZONE)).strftime("%Y-%m-%d")
        data = {
            "date": today,
            "anchors": anchors
        }
        with open(BASIS_ANCHORS_JSON, "w") as f:
            json.dump(data, f, indent=4)
        log.info("Saved %d basis anchors to %s", len(anchors), BASIS_ANCHORS_JSON.name)
    except Exception as e:
        log.error("Failed to save basis anchors: %s", e)


def _load_weekly_scope_cache(path: "Path | None" = None) -> "dict[str, dict[str, Any]]":
    if path is None:
        path = WEEKLY_SCOPE_CACHE_JSON
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        log.warning("Failed to load weekly scope cache %s: %s", path.name, exc)
        return {}


def _save_weekly_scope_cache(cache: "dict[str, dict[str, Any]]", path: "Path | None" = None) -> None:
    if path is None:
        path = WEEKLY_SCOPE_CACHE_JSON
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as exc:
        log.warning("Failed to save weekly scope cache %s: %s", path.name, exc)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_eod_snapshot(run_label: str, now_ny: datetime) -> bool:
    label = (run_label or "").upper()
    if "EOD" in label or "16:00" in run_label or "16:15" in run_label:
        return True
    return now_ny.hour >= 16


def _select_weekly_scope_candidate(levels: DealerLevels, today_ny: date):
    candidates = []
    for em in getattr(levels, "expected_moves", []):
        expiry = _parse_iso_date(getattr(em, "expiry", None))
        if expiry is None or expiry <= today_ny or expiry.weekday() != 4:
            continue
        dte = (expiry - today_ny).days
        if 4 <= dte <= 10:
            candidates.append((abs(dte - 7), dte, em, expiry))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, em, expiry = candidates[0]
    return em, expiry


def _next_friday(today_ny: date) -> date:
    """Return the next Friday strictly after today (DTE >= 1)."""
    days_ahead = 4 - today_ny.weekday()  # 4 = Friday
    if days_ahead <= 0:
        days_ahead += 7
    return today_ny + timedelta(days=days_ahead)


def _compute_tos_em_fallback(
    levels: DealerLevels,
    today_ny: date,
    is_futures: bool = False,
) -> tuple[float, float, str] | None:
    """Compute weekly EM via the TOS formula when the weekly expiry is missing from the chain.

    This handles the case where the RTD chain for NQ/ES only has 0DTE + monthly
    expiries, but the weekly Friday expiry (DTE 4-10) that TOS displays is not in
    the chain. We compute EM directly using the calibrated TOS time-scaling model
    with the chain's spot and ATM IV.

    Returns (em_upper, em_lower, expiry_str) or None if inputs are invalid.
    """
    spot = getattr(levels, "spot", 0) or getattr(levels, "spot_price", 0)
    if not spot or spot <= 0:
        # Try cash_spot fallback
        spot = getattr(levels, "cash_spot", 0) or 0
    if not spot or spot <= 0:
        return None

    atm_iv = getattr(levels, "atm_iv", 0) or 0
    if atm_iv <= 0:
        # Try blending call/put 25d IV
        c25 = getattr(levels, "call_25d_iv", 0) or 0
        p25 = getattr(levels, "put_25d_iv", 0) or 0
        if c25 > 0 and p25 > 0:
            atm_iv = (c25 + p25) / 2
    if atm_iv <= 0:
        return None

    next_fri = _next_friday(today_ny)
    # Only use this if the next Friday is DTE 4-10 (the weekly window)
    dte = (next_fri - today_ny).days
    if dte < 3:
        # Too close to expiry, skip
        return None

    try:
        from .gex_calculator import calculate_tos_expected_move
        em_value = calculate_tos_expected_move(
            spot, next_fri.isoformat(), atm_iv * 100, is_futures=is_futures
        )
        if em_value <= 0:
            return None
        em_upper = round(spot + em_value, 2)
        em_lower = round(spot - em_value, 2)
        return em_upper, em_lower, next_fri.strftime("%Y-%m-%d")
    except Exception as exc:
        log.warning("[weekly_scope] TOS EM fallback failed for %s: %s",
                    getattr(levels, "ticker", "?"), exc)
        return None


def _attach_weekly_scope(levels: Any, record: dict[str, Any] | None) -> None:
    attrs = (
        "weekly_scope_upper",
        "weekly_scope_lower",
        "weekly_scope_85_upper",
        "weekly_scope_85_lower",
        "weekly_scope_expiry",
        "weekly_scope_source",
        "weekly_scope_captured_on",
    )
    if not record:
        for attr in attrs:
            setattr(levels, attr, None)
        return

    setattr(levels, "weekly_scope_upper", record.get("em_upper"))
    setattr(levels, "weekly_scope_lower", record.get("em_lower"))
    setattr(levels, "weekly_scope_85_upper", record.get("straddle_85_upper"))
    setattr(levels, "weekly_scope_85_lower", record.get("straddle_85_lower"))
    setattr(levels, "weekly_scope_expiry", record.get("expiry"))
    setattr(levels, "weekly_scope_source", record.get("source"))
    setattr(levels, "weekly_scope_captured_on", record.get("captured_on"))


def _translate_weekly_scope_record(record: dict[str, Any], translated_levels: Any) -> dict[str, Any]:
    ratio = getattr(translated_levels, "translation_ratio", None)
    spread = getattr(translated_levels, "translation_spread", None)
    mode = getattr(translated_levels, "translation_mode", "")

    def _shift(value: float | None) -> float | None:
        if value is None:
            return None
        if mode == "multiplicative" and ratio:
            return round(value * ratio, 2)
        if spread is not None:
            return round(value + spread, 2)
        return round(value, 2)

    translated = dict(record)
    translated["em_upper"] = _shift(record.get("em_upper"))
    translated["em_lower"] = _shift(record.get("em_lower"))
    translated["straddle_85_upper"] = _shift(record.get("straddle_85_upper"))
    translated["straddle_85_lower"] = _shift(record.get("straddle_85_lower"))
    return translated


def _discord_window_allowed(
    run_label: str,
    snapshot_suffix: str | None,
    now_ny: datetime | None = None,
) -> bool:
    if snapshot_suffix and snapshot_suffix in DISCORD_ALLOWED_SNAPSHOT_SUFFIXES:
        return True

    label = (run_label or "")
    return ("09:30" in label) or ("16:15" in label)


def _build_snapshot_suffix(now_ny: datetime, time_str: str) -> str:
    """Build a date-qualified snapshot suffix (YYYYMMDD_HHMM)."""
    return f"{now_ny.strftime('%Y%m%d')}_{time_str.replace(':', '')}"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    tickers: list[str] | None = None,
    run_label: str = "",
    enable_discord: "bool | None" = None,
    full_discord: bool = False,
    discord_target_key: str | None = None,
    versioned: bool = False,
    reset_anchors: bool = False,
    snapshot_suffix: str | None = None,
    intraday_only: bool = False,
    rtd_coord: "HybridCoordinator | None" = None,
) -> None:
    """
    Execute one complete fetch -> calculate -> output cycle.

    Parameters
    ----------
    run_label : Short human-readable label embedded in all outputs.
                Auto-generated from current Eastern time when empty.
    rtd_coord : Optional pre-started HybridCoordinator. When supplied, the
                pipeline will reuse it and will not stop it on exit. This
                avoids repeated COM spawn/teardown in loop mode.
    """
    _setup_logging()
    if enable_discord is None:
        enable_discord = ENABLE_DISCORD_UPDATES
    
    dte_targets = DTE_TARGETS if intraday_only else PIPELINE_DTE_TARGETS

    if not run_label:
        tz = ZoneInfo(SCHEDULE_TIMEZONE)
        run_label = datetime.now(tz).strftime("%Y-%m-%d %H:%M ET")

    log.info("=" * 60)
    log.info("Dealer Levels pipeline starting  |  %s", run_label)
    log.info("=" * 60)

    _tic_total = time.time()
    timings: dict[str, float] = {}

    def _t(name: str) -> None:
        timings[name] = time.time()

    def _dt(a: str, b: str) -> float:
        return timings.get(b, time.time()) - timings.get(a, 0.0)

    # --- Create Schwab client -----------------------------------------------
    try:
        client = create_client(SECRETS_PATH, TOKEN_PATH)
    except Exception as exc:
        log.critical("Cannot create Schwab client: %s", exc)
        return

    translated_levels = []
    translated_macro_levels = []
    cash_levels_by_ticker: dict[str, DealerLevels] = {}
    macro_levels_by_ticker: dict[str, DealerLevels] = {}
    scored_intraday_by_ticker: dict[str, ScoredLevels] = {}
    scored_macro_by_ticker: dict[str, ScoredLevels] = {}
    futures_quotes = {}
    eod_close_prices = {}
    rtd_gex_results = {}

    # --- Load existing anchors ----------------------------------------------
    all_anchors = load_basis_anchors()
    new_anchors_captured = False
    weekly_scope_cache = _load_weekly_scope_cache()
    weekly_scope_cache_updated = False
    now_ny = datetime.now(ZoneInfo(SCHEDULE_TIMEZONE))
    today_ny = now_ny.date()
    is_eod_run = _is_eod_snapshot(run_label, now_ny)

    # --- Start / reuse TOS RTD hybrid coordinator (if enabled) -----------------
    rtd_started_here = rtd_coord is None
    if rtd_coord is None:
        rtd_coord = HybridCoordinator()
        rtd_coord.start()
    if rtd_coord.is_rtd_active:
        log.info("TOS RTD active — using real-time futures prices")
    elif rtd_coord._enabled:
        log.warning("TOS RTD enabled but not active — check TOS desktop is running")

    # --- Process each ticker --------------------------------------------------
    target_tickers = tickers if tickers is not None else ACTIVE_TICKERS

    # Tickers that are pure futures — no Schwab cash options chain; sourced entirely from RTD.
    RTD_NATIVE_TICKERS: set[str] = {"NQ", "ES"}

    # Pre-fetch all options chains concurrently to minimize network latency
    etf_tickers = [t for t in target_tickers if t not in RTD_NATIVE_TICKERS]
    rtd_only_tickers = [t for t in target_tickers if t in RTD_NATIVE_TICKERS]
    
    # Priority classification: Tier 1 Priority vs Tier 2 Secondary
    from .config import PRIORITY_TICKERS
    tier1_set = set(PRIORITY_TICKERS) | {"SPX", "SPY", "NDX", "QQQ"}
    tier1_tickers = [t for t in etf_tickers if t in tier1_set]
    tier2_tickers = [t for t in etf_tickers if t not in tier1_set]
    
    log.info(
        "Pre-fetching options chains (Tier 1 Priority: %s, Tier 2 Secondary: %s, RTD-native: %s)...",
        tier1_tickers, tier2_tickers, rtd_only_tickers or "none",
    )
    chains_by_ticker = {}
    from concurrent.futures import ThreadPoolExecutor

    # Helper function to fetch intraday DTE 0-14 and stitch with cached daily macro DTE 15-365
    def fetch_and_stitch(t: str, req_priority: int):
        try:
            # 1. Fetch live intraday chain (DTE 0-14) in 1 single API call
            intraday_chain = fetch_option_chain_data(client, t, DTE_TARGETS, priority=req_priority)
            
            # 2. Try loading cached daily macro chain (DTE 15-365)
            macro_chain = None
            try:
                today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
                cache_file = DATA_DIR / f"macro_cache_{t.upper().replace('/', '')}_{today_str}.json"
                if cache_file.exists():
                    from .macro_pipeline import _deserialize_chain
                    macro_chain = _deserialize_chain(json.loads(cache_file.read_text()))
            except Exception as cache_err:
                log.debug("Macro cache load for %s skipped: %s", t, cache_err)

            # 3. Stitch intraday + macro chains together
            if macro_chain:
                log.debug("Stitching live intraday DTE 0-14 with cached macro DTE 15-365 for %s...", t)
                return t, merge_option_chains(intraday_chain, macro_chain)
            return t, intraday_chain
        except Exception as e:
            log.error("Failed to fetch/stitch option chain for %s: %s", t, e)
            return t, None

    # Step A: Fetch Tier 1 Priority Tickers FIRST (high priority = 2 during RTH)
    if tier1_tickers:
        with ThreadPoolExecutor(max_workers=min(len(tier1_tickers), 2) or 1) as executor:
            results = executor.map(lambda t: fetch_and_stitch(t, req_priority=2), tier1_tickers)
            for t, chain_data in results:
                if chain_data:
                    chains_by_ticker[t] = chain_data

    # Step B: Fetch Tier 2 Secondary Tickers SECOND (lower priority = 4)
    if tier2_tickers:
        with ThreadPoolExecutor(max_workers=min(len(tier2_tickers), 3) or 1) as executor:
            results = executor.map(lambda t: fetch_and_stitch(t, req_priority=4), tier2_tickers)
            for t, chain_data in results:
                if chain_data:
                    chains_by_ticker[t] = chain_data

    # Pre-fetch all futures quotes in a single batched REST call (8 HTTP requests -> 1 batched call)
    all_futures_syms = [INDEX_TO_FUTURES.get(t) for t in target_tickers if INDEX_TO_FUTURES.get(t)]
    futures_quotes = fetch_batched_futures_quotes(all_futures_syms) if all_futures_syms else {}

    for ticker in target_tickers:
        futures_sym = INDEX_TO_FUTURES.get(ticker)
        mapping_str = f"-> {futures_sym}" if futures_sym else "(Cash only)"
        if PIPELINE_DEBUG_TICKER:
            log.info("--- Processing: %s %s ---", ticker, mapping_str)

        # ── RTD-native tickers (NQ, ES) — scored entirely from RTD, no Schwab chain ──
        if ticker in RTD_NATIVE_TICKERS:
            if not rtd_coord.is_rtd_active:
                log.warning("RTD-native ticker %s requested but RTD is not active — skipping.", ticker)
                continue
            try:
                rtd_gex_result = rtd_gex_results.get(futures_sym)
                if rtd_gex_result is None:
                    _t(f"rtd_gex_start_{ticker}")
                    # Retry with configurable settle time — RTD chain data may not have streamed in yet
                    from scripts.streaming.options.config import RTD_SETTLE_SECONDS, RTD_SETTLE_MAX_RETRIES
                    for attempt in range(RTD_SETTLE_MAX_RETRIES):
                        rtd_gex_result = rtd_coord.calculate_rtd_gex(futures_sym)
                        if rtd_gex_result and rtd_gex_result.chain_data and rtd_gex_result.contract_count > 0:
                            break
                        if attempt < RTD_SETTLE_MAX_RETRIES - 1:
                            log.info("RTD chain for %s empty on attempt %d/%d — waiting %ds before retry...",
                                     futures_sym, attempt + 1, RTD_SETTLE_MAX_RETRIES, RTD_SETTLE_SECONDS)
                            time.sleep(RTD_SETTLE_SECONDS)
                    _t(f"rtd_gex_done_{ticker}")
                    rtd_gex_results[futures_sym] = rtd_gex_result
                if rtd_gex_result is None or rtd_gex_result.chain_data is None or rtd_gex_result.contract_count == 0:
                    log.warning("RTD GEX result unavailable or empty for %s — skipping.", ticker)
                    continue
                ticker_profile = get_ticker_profile(ticker)

                # Compute separate intraday and macro dealer levels from the same
                # RTD chain.  Intraday uses FRONT_WEEK_WEIGHTED (0-14 DTE) for
                # tactical walls; macro uses ALL_EXPIRIES_WEIGHTED for structural
                # levels.  RTD only has 2 expiries so macro coverage is thinner
                # than the Schwab path (which has 0-365 DTE), but it's still
                # better to compute what we can than to skip it.
                from .gex_calculator import calculate_dealer_levels as _calc_dl
                from .config import MACRO_VIEW as _MACRO_VIEW

                rtd_dl_intraday = rtd_gex_result.dealer_levels  # already computed with (0, 14)
                rtd_dl_macro = _calc_dl(
                    rtd_gex_result.chain_data,
                    ticker,
                    min_oi_floor=ticker_profile.min_oi_floor,
                    wall_scope="ALL_EXPIRIES_WEIGHTED",
                    wall_dte_range=_MACRO_VIEW.dte_range,
                )

                # Weekly scope capture/attachment (same as Schwab path)
                weekly_scope_record = None
                if is_eod_run and today_ny.weekday() == 4:
                    weekly_candidate = _select_weekly_scope_candidate(rtd_dl_macro, today_ny)
                    if weekly_candidate is None:
                        weekly_candidate = _select_weekly_scope_candidate(rtd_dl_intraday, today_ny)
                    if weekly_candidate is not None:
                        weekly_em, weekly_expiry = weekly_candidate
                        weekly_scope_record = {
                            "expiry": weekly_expiry.strftime("%Y-%m-%d"),
                            "captured_on": today_ny.strftime("%Y-%m-%d"),
                            "source": "FRIDAY_EOD_CAPTURE",
                            "em_upper": round(float(weekly_em.em_upper), 2),
                            "em_lower": round(float(weekly_em.em_lower), 2),
                            "straddle_85_upper": round(float(getattr(weekly_em, "straddle_85_upper", 0.0) or 0.0), 2),
                            "straddle_85_lower": round(float(getattr(weekly_em, "straddle_85_lower", 0.0) or 0.0), 2),
                        }
                        if weekly_scope_cache.get(ticker) != weekly_scope_record:
                            weekly_scope_cache[ticker] = weekly_scope_record
                            weekly_scope_cache_updated = True
                    else:
                        # Fallback: the weekly expiry (DTE 4-10) is missing from the
                        # RTD chain (NQ/ES only have 0DTE + monthly). Compute EM via
                        # the TOS formula using the chain's spot + ATM IV.
                        _is_fut = ticker in ("NQ", "ES", "YM", "RTY")
                        tos_fb = _compute_tos_em_fallback(rtd_dl_macro, today_ny, is_futures=_is_fut)
                        if tos_fb is None:
                            tos_fb = _compute_tos_em_fallback(rtd_dl_intraday, today_ny, is_futures=_is_fut)
                        if tos_fb is not None:
                            em_up, em_lo, exp_str = tos_fb
                            weekly_scope_record = {
                                "expiry": exp_str,
                                "captured_on": today_ny.strftime("%Y-%m-%d"),
                                "source": "FRIDAY_EOD_TOS_FORMULA_FALLBACK",
                                "em_upper": em_up,
                                "em_lower": em_lo,
                                "straddle_85_upper": 0.0,
                                "straddle_85_lower": 0.0,
                            }
                            log.info("[weekly_scope] %s: TOS formula fallback EM ±%.2f for %s expiry",
                                     ticker, (em_up - em_lo) / 2, exp_str)
                            if weekly_scope_cache.get(ticker) != weekly_scope_record:
                                weekly_scope_cache[ticker] = weekly_scope_record
                                weekly_scope_cache_updated = True

                if weekly_scope_record is None:
                    candidate_record = weekly_scope_cache.get(ticker)
                    expiry = _parse_iso_date(candidate_record.get("expiry") if candidate_record else None)
                    if candidate_record and expiry and expiry >= today_ny:
                        weekly_scope_record = candidate_record
                    elif ticker in weekly_scope_cache:
                        del weekly_scope_cache[ticker]
                        weekly_scope_cache_updated = True

                _attach_weekly_scope(rtd_dl_intraday, weekly_scope_record)
                _attach_weekly_scope(rtd_dl_macro, weekly_scope_record)

                rtd_scored_intraday = score_levels(
                    rtd_dl_intraday, rtd_gex_result.chain_data, ticker, ticker_profile, INTRADAY_VIEW
                )
                rtd_scored_macro = score_levels(
                    rtd_dl_macro, rtd_gex_result.chain_data, ticker, ticker_profile, MACRO_VIEW
                )

                # ── Integrity gate (self-healing last line of defence) ──
                # Upstream monitors can fail together; this inspects the
                # computed levels and refuses to silently publish garbage.
                try:
                    from .file_writer import assess_levels_integrity
                    integrity = assess_levels_integrity(
                        ticker, rtd_dl_intraday.strike_gex, rtd_gex_result.futures_price
                    )
                    if not integrity["ok"]:
                        log.warning(
                            "INTEGRITY GATE: %s levels failed checks %s (metrics=%s) — "
                            "tagging output DEGRADED",
                            ticker, integrity["reasons"], integrity["metrics"],
                        )
                        rtd_dl_intraday.regime_label = (
                            (rtd_dl_intraday.regime_label or "DEGRADED") + " [DEGRADED-DATA]"
                        )
                        rtd_scored_intraday.bias = "DEGRADED"
                except Exception as gate_exc:
                    log.debug("Integrity gate error for %s: %s", ticker, gate_exc)

                scored_intraday_by_ticker[ticker] = rtd_scored_intraday
                scored_macro_by_ticker[ticker] = rtd_scored_macro

                # Populate the metadata dicts so the unified output writer can
                # generate structural tokens and META_ tokens for NQ/ES —
                # same as the Schwab path does for SPY/QQQ/etc.
                # Also tag the DealerLevels with futures metadata so that
                # interval_writer.write_snapshot persists futures_symbol etc.
                rtd_dl_intraday.futures_symbol = futures_sym
                rtd_dl_intraday.translation_mode = "rtd_direct"
                rtd_dl_intraday.basis_spread = 0.0
                rtd_dl_intraday.basis_ratio = 1.0
                rtd_dl_macro.futures_symbol = futures_sym
                rtd_dl_macro.translation_mode = "rtd_direct"
                rtd_dl_macro.basis_spread = 0.0
                rtd_dl_macro.basis_ratio = 1.0

                cash_levels_by_ticker[ticker] = rtd_dl_intraday
                macro_levels_by_ticker[ticker] = rtd_dl_macro

                # Append to translated_levels so NQ/ES appear in JSON outputs,
                # pipeline_state change detection, and Discord embeds.
                from .futures_translator import TranslatedLevels
                from dataclasses import replace as _replace

                def _build_rtd_translated(dl, scope_label):
                    """Build a full TranslatedLevels from a DealerLevels for RTD-native path."""
                    return TranslatedLevels(
                        futures_symbol=futures_sym,
                        cash_ticker=ticker,
                        futures_price=rtd_gex_result.futures_price,
                        cash_spot=rtd_gex_result.futures_price,
                        basis_spread=0.0,
                        basis_ratio=1.0,
                        translation_mode="rtd_direct",
                        min_tick=0.25,
                        total_gex=dl.total_gex,
                        gex_regime=dl.gex_regime,
                        zero_gamma=dl.zero_gamma,
                        zero_gamma_delta_adj=dl.zero_gamma_delta_adj,
                        gamma_flip_lower=dl.gamma_flip_lower,
                        gamma_flip_upper=dl.gamma_flip_upper,
                        call_wall=dl.call_wall,
                        put_wall=dl.put_wall,
                        secondary_call_wall=dl.secondary_call_wall,
                        secondary_put_wall=dl.secondary_put_wall,
                        local_call_node=dl.local_call_node,
                        local_put_node=dl.local_put_node,
                        call_wall_0dte=dl.call_wall_0dte,
                        put_wall_0dte=dl.put_wall_0dte,
                        hedge_wall=dl.hedge_wall,
                        max_pain=dl.max_pain,
                        em_upper=dl.em_upper,
                        em_lower=dl.em_lower,
                        em_value=dl.em_value,
                        atm_straddle=dl.atm_straddle,
                        gamma_magnet=dl.gamma_magnet,
                        pin_strike=dl.pin_strike,
                        pin_odds=dl.pin_odds,
                        wall_separation=dl.wall_separation,
                        regime_label=dl.regime_label,
                        directional_bias=dl.directional_bias,
                        call_gamma_total=dl.call_gamma_total,
                        put_gamma_total=dl.put_gamma_total,
                        net_vanna_exposure=dl.net_vanna_exposure,
                        wall_scope=scope_label,
                        wall_dte_min=dl.wall_dte_min,
                        wall_dte_max=dl.wall_dte_max,
                        concentration_score=dl.concentration_score,
                        call_wall_oi=dl.call_wall_oi,
                        put_wall_oi=dl.put_wall_oi,
                        pin_strike_oi=dl.pin_strike_oi,
                        net_speed_exposure=dl.net_speed_exposure,
                        total_gex_delta_adj=dl.total_gex_delta_adj,
                        call_volume_centroid=dl.call_volume_centroid,
                        put_volume_centroid=dl.put_volume_centroid,
                        atm_iv=dl.atm_iv,
                        put_25d_iv=dl.put_25d_iv,
                        call_25d_iv=dl.call_25d_iv,
                        volatility_skew_premium=dl.volatility_skew_premium,
                        vol_trigger_upper_05=getattr(dl, 'vol_trigger_upper_05', None),
                        vol_trigger_lower_05=getattr(dl, 'vol_trigger_lower_05', None),
                        vol_trigger_upper_10=getattr(dl, 'vol_trigger_upper_10', None),
                        vol_trigger_lower_10=getattr(dl, 'vol_trigger_lower_10', None),
                        vol_trigger_upper_15=getattr(dl, 'vol_trigger_upper_15', None),
                        vol_trigger_lower_15=getattr(dl, 'vol_trigger_lower_15', None),
                        gamma_cliff_up=getattr(dl, 'gamma_cliff_up', None),
                        gamma_cliff_down=getattr(dl, 'gamma_cliff_down', None),
                        vanna_call_node=getattr(dl, 'vanna_call_node', None),
                        vanna_put_node=getattr(dl, 'vanna_put_node', None),
                        charm_call_node=getattr(dl, 'charm_call_node', None),
                        charm_put_node=getattr(dl, 'charm_put_node', None),
                        volume_imbalance_call_node=getattr(dl, 'volume_imbalance_call_node', None),
                        volume_imbalance_put_node=getattr(dl, 'volume_imbalance_put_node', None),
                        dex_call_node=getattr(dl, 'dex_call_node', None),
                        dex_put_node=getattr(dl, 'dex_put_node', None),
                        liquidity_vacuum_lower=getattr(dl, 'liquidity_vacuum_lower', None),
                        liquidity_vacuum_upper=getattr(dl, 'liquidity_vacuum_upper', None),
                        skew_pivot_put_25d=getattr(dl, 'skew_pivot_put_25d', None),
                        skew_pivot_call_25d=getattr(dl, 'skew_pivot_call_25d', None),
                        hedge_flow_up_10=getattr(dl, 'hedge_flow_up_10', 0.0),
                        hedge_flow_up_25=getattr(dl, 'hedge_flow_up_25', 0.0),
                        hedge_flow_up_50=getattr(dl, 'hedge_flow_up_50', 0.0),
                        hedge_flow_dn_10=getattr(dl, 'hedge_flow_dn_10', 0.0),
                        hedge_flow_dn_25=getattr(dl, 'hedge_flow_dn_25', 0.0),
                        hedge_flow_dn_50=getattr(dl, 'hedge_flow_dn_50', 0.0),
                        hourly_flow_curve=getattr(dl, 'hourly_flow_curve', []),
                        iv_change=getattr(dl, 'iv_change', 0.0),
                        expected_moves=dl.expected_moves,
                    )

                rtd_tl_intraday = _build_rtd_translated(rtd_dl_intraday, "FRONT_WEEK_WEIGHTED")
                rtd_tl_macro = _build_rtd_translated(rtd_dl_macro, "ALL_EXPIRIES_WEIGHTED")
                translated_levels.append(rtd_tl_intraday)
                translated_macro_levels.append(rtd_tl_macro)

                log.info("RTD-native scored levels saved for %s (spot=%.2f)", ticker, rtd_gex_result.futures_price)

                # ── EOD parquet close-price pinning for RTD-native futures ──
                # At the 16:15 ET snapshot, pin the futures price to the 16:14 ET
                # close from our local parquet — same logic as the Schwab path below.
                # This keeps RTD-native /ES and /NQ in sync with SPX/NDX closes.
                is_eod_snapshot = (snapshot_suffix == "1615")
                if is_eod_snapshot and futures_sym:
                    tz_ny = ZoneInfo("America/New_York")
                    tz_utc = ZoneInfo("UTC")
                    now_ny_local = datetime.now(tz_ny)
                    eod_close_et = datetime.combine(
                        now_ny_local.date(), EOD_FUTURES_CLOSE_TIME
                    ).replace(tzinfo=tz_ny)
                    eod_close_utc = eod_close_et.astimezone(tz_utc).replace(tzinfo=None)

                    cache_key = (futures_sym, eod_close_utc)
                    if cache_key in eod_close_prices:
                        parquet_close = eod_close_prices[cache_key]
                    else:
                        parquet_close = get_eod_close_price(futures_sym, eod_close_utc)
                        eod_close_prices[cache_key] = parquet_close

                    if parquet_close is not None:
                        log.info(
                            "EOD parquet override %s (RTD): 16:14 close=%.2f  (RTD price was %.2f)",
                            futures_sym, parquet_close, rtd_gex_result.futures_price,
                        )
                        rtd_gex_result.futures_price = parquet_close
                        # Re-compute dealer levels with the pinned spot
                        from dataclasses import replace as _replace
                        from .gex_calculator import calculate_dealer_levels as _calc_dl
                        from .config import MACRO_VIEW as _MACRO_VIEW
                        rtd_dl_intraday = _replace(rtd_gex_result.dealer_levels, spot=parquet_close)
                        # Re-apply translation metadata (lost by _replace)
                        rtd_dl_intraday.futures_symbol = futures_sym
                        rtd_dl_intraday.translation_mode = "rtd_direct"
                        rtd_dl_intraday.basis_spread = 0.0
                        rtd_dl_intraday.basis_ratio = 1.0
                        rtd_dl_macro = _calc_dl(
                            rtd_gex_result.chain_data, ticker,
                            min_oi_floor=ticker_profile.min_oi_floor,
                            wall_scope="ALL_EXPIRIES_WEIGHTED",
                            wall_dte_range=_MACRO_VIEW.dte_range,
                        )
                        rtd_dl_macro = _replace(rtd_dl_macro, spot=parquet_close)
                        rtd_dl_macro.futures_symbol = futures_sym
                        rtd_dl_macro.translation_mode = "rtd_direct"
                        rtd_dl_macro.basis_spread = 0.0
                        rtd_dl_macro.basis_ratio = 1.0
                        # Re-score with the pinned spot
                        scored_intraday_by_ticker[ticker] = score_levels(
                            rtd_dl_intraday, rtd_gex_result.chain_data, ticker, ticker_profile, INTRADAY_VIEW
                        )
                        scored_macro_by_ticker[ticker] = score_levels(
                            rtd_dl_macro, rtd_gex_result.chain_data, ticker, ticker_profile, MACRO_VIEW
                        )
                        # Update metadata dicts with pinned dealer_levels
                        cash_levels_by_ticker[ticker] = rtd_dl_intraday
                        macro_levels_by_ticker[ticker] = rtd_dl_macro
                    else:
                        log.warning(
                            "EOD parquet override: no 16:14 bar for %s — keeping RTD price %.2f",
                            futures_sym, rtd_gex_result.futures_price,
                        )

                # Write per-ticker snapshot to DB (RTH only)
                if _is_rth():
                    from .interval_writer import write_snapshot
                    write_snapshot(rtd_dl_intraday, ticker_override=futures_sym)

            except Exception as e:
                log.error("RTD-native processing failed for %s: %s", ticker, e)
            continue  # Skip the Schwab/ETF path entirely

        try:
            _t(f"chain_start_{ticker}")
            # Retrieve pre-fetched option chain
            full_chain = chains_by_ticker.get(ticker)
            if not full_chain:
                # Fallback: fetch sequentially if concurrent fetch failed
                try:
                    full_chain = fetch_option_chain_data(client, ticker, dte_targets)
                except Exception as e:
                    log.error("Failed to fetch option chain fallback for %s: %s — skipping.", ticker, e)
                    continue

            _t(f"chain_fetch_{ticker}")
            chain = full_chain
            target_cash_spot = full_chain.spot_price
            source_ticker = ticker
            direct_price_metrics = None
            
            # Reset translation anchors for each ticker to avoid variable leakage
            anchor_basis = None
            anchor_ratio = None

            # 1b. ETF fallback if index chain is empty or has unusable OI profile
            if (not chain.calls and not chain.puts) or (not _chain_has_actionable_oi(chain)):
                if full_chain.calls and full_chain.puts:
                    direct_price_metrics = calculate_price_metrics(full_chain)
                fallback = ETF_FALLBACK.get(ticker)
                if fallback:
                    log.warning(
                        "%s chain lacks actionable OI/contracts — falling back to %s.",
                        ticker,
                        fallback,
                    )
                    # Check pre-fetched cache first
                    chain = chains_by_ticker.get(fallback)
                    if not chain:
                        chain = fetch_option_chain_data(client, fallback, dte_targets)
                    source_ticker = fallback
                else:
                    log.error("No fallback available for %s — skipping.", ticker)
                    continue

            # 2. Fetch front-month futures quote (RTD first, Schwab fallback cached)
            _t(f"quote_start_{ticker}")
            if futures_sym in futures_quotes:
                schwab_fut = futures_quotes[futures_sym]
            else:
                schwab_fut = fetch_futures_quote(futures_sym) if futures_sym else None
                if futures_sym:
                    futures_quotes[futures_sym] = schwab_fut
            _t(f"quote_schwab_{ticker}")
            hybrid_quote = rtd_coord.get_futures_price(futures_sym, schwab_price=schwab_fut.price if schwab_fut else None)
            _t(f"quote_rtd_{ticker}")
            if hybrid_quote and hybrid_quote.source == "tos_rtd":
                if PIPELINE_DEBUG_RTD:
                    log.info("Using RTD futures price for %s: %.2f", futures_sym, hybrid_quote.price)
                fut = FuturesQuote(
                    symbol=futures_sym,
                    price=hybrid_quote.price,
                    open_price=schwab_fut.open_price if schwab_fut else None,
                )
            else:
                fut = schwab_fut

            # 2c. EOD close-price override (16:15 ET snapshot only)
            # At EOD, ES/NQ/RTY/YM keep trading after 4 PM so the live Schwab
            # mark drifts away from the official RTH close.  Pin the futures
            # price to the 16:14 ET candle close from our local parquet —
            # the same timestamp as the official SPX close publication (16:14 ET).
            # This synchronises futures and index price references so the basis
            # spread is zero at EOD, keeping translated levels in sync.
            is_eod_snapshot = (snapshot_suffix == "1615")
            if is_eod_snapshot and futures_sym and fut and fut.price is not None:
                tz_ny = ZoneInfo("America/New_York")
                tz_utc = ZoneInfo("UTC")
                now_ny = datetime.now(tz_ny)
                # Build UTC-naive timestamp for the 16:14 ET candle
                eod_close_et = datetime.combine(
                    now_ny.date(), EOD_FUTURES_CLOSE_TIME
                ).replace(tzinfo=tz_ny)
                eod_close_utc = eod_close_et.astimezone(tz_utc).replace(tzinfo=None)
                
                cache_key = (futures_sym, eod_close_utc)
                if cache_key in eod_close_prices:
                    parquet_close = eod_close_prices[cache_key]
                else:
                    parquet_close = get_eod_close_price(futures_sym, eod_close_utc)
                    eod_close_prices[cache_key] = parquet_close

                if parquet_close is not None:
                    log.info(
                        "EOD parquet override %s: 16:14 close=%.2f  (live mark was %.2f)",
                        futures_sym, parquet_close, fut.price,
                    )
                    fut = FuturesQuote(
                        symbol=fut.symbol,
                        price=parquet_close,
                        open_price=fut.open_price,
                    )
                else:
                    log.warning(
                        "EOD parquet override: no 16:14 bar for %s — keeping live mark %.2f",
                        futures_sym, fut.price,
                    )

                # SPX cash spot: pin to 16:14 ET close (official SPX close time)
                if ticker == "SPX":
                    spx_close_et = datetime.combine(
                        now_ny.date(), EOD_SPX_CLOSE_TIME
                    ).replace(tzinfo=tz_ny)
                    spx_close_utc = spx_close_et.astimezone(tz_utc).replace(tzinfo=None)
                    
                    spx_cache_key = ("SPX", spx_close_utc)
                    if spx_cache_key in eod_close_prices:
                        spx_parquet_close = eod_close_prices[spx_cache_key]
                    else:
                        spx_parquet_close = get_eod_close_price("SPX", spx_close_utc)
                        eod_close_prices[spx_cache_key] = spx_parquet_close

                    if spx_parquet_close is not None:
                        log.info(
                            "EOD SPX spot override: 16:14 close=%.2f  (chain mark was %.2f)",
                            spx_parquet_close, full_chain.spot_price,
                        )
                        target_cash_spot = spx_parquet_close
                        full_chain = replace(full_chain, spot=spx_parquet_close)
                    else:
                        log.warning(
                            "EOD SPX spot override: no 16:14 bar — keeping chain mark %.2f",
                            full_chain.spot_price,
                        )

            # 2b. Establish or load basis anchor
            # Logic: 
            # 1. Use existing anchor if available and not resetting
            # 2. Capture new anchor if resetting (09:30 pulse) or missing
            # 3. Use 'Open Price Hack' as fail-safe capture source
            ticker_anchor = all_anchors.get(ticker)
            
            if USE_OPENING_BASIS and futures_sym and fut and fut.price is not None:
                if not reset_anchors and ticker_anchor:
                    anchor_basis = ticker_anchor.get("basis")
                    anchor_ratio = ticker_anchor.get("ratio")
                    if PIPELINE_DEBUG_TICKER:
                        log.info("Using Persistent Basis for %s: %.2f (Ratio: %.4f)", 
                                 ticker, anchor_basis, anchor_ratio)
                else:
                    spot_open = full_chain.spot_open
                    fut_open = fut.open_price
                    
                    if spot_open and fut_open:
                        anchor_basis = fut_open - spot_open
                        anchor_ratio = fut_open / spot_open if spot_open else 1.0
                        if PIPELINE_DEBUG_TICKER:
                            log.info("Captured NEW Opening Basis for %s: %.2f (Ratio: %.4f) [Source: Open Prices]", 
                                     ticker, anchor_basis, anchor_ratio)
                        all_anchors[ticker] = {"basis": anchor_basis, "ratio": anchor_ratio}
                        new_anchors_captured = True
                    elif ticker_anchor:
                        anchor_basis = ticker_anchor.get("basis")
                        anchor_ratio = ticker_anchor.get("ratio")
                        log.warning("Could not capture new open prices for %s. Retaining existing anchor.", ticker)
                    else:
                        anchor_basis = fut.price - full_chain.spot_price
                        anchor_ratio = fut.price / full_chain.spot_price if full_chain.spot_price else 1.0
                        if PIPELINE_DEBUG_TICKER:
                            log.info("Captured NEW Basis for %s: %.2f (Ratio: %.4f) [Source: Current Prices]", 
                                     ticker, anchor_basis, anchor_ratio)
                        all_anchors[ticker] = {"basis": anchor_basis, "ratio": anchor_ratio}
                        new_anchors_captured = True

            # 3. Create Intraday Subset for tactical wall detection
            # Filter the full chain to just the near-term (<= 14 DTE) window
            tz_ny = ZoneInfo("America/New_York")
            today = datetime.now(tz_ny).date()
            
            # Helper to filter contracts
            def _filter_dte(contracts, max_dte):
                return [c for c in contracts if (c.expiry - today).days <= max_dte]

            intraday_calls = _filter_dte(chain.calls, 14)
            intraday_puts = _filter_dte(chain.puts, 14)
            
            # Construct a virtual intraday chain
            intraday_chain = replace(chain, contracts=intraday_calls + intraday_puts)

            profile = get_ticker_profile(ticker)

            # 4. Calculate Dealer Levels for both timeframes
            if PIPELINE_DEBUG_TICKER:
                log.info("Calculating [%s] and [MACRO] levels structure...", ticker)
            levels_intraday = calculate_dealer_levels(
                intraday_chain,
                source_ticker,
                min_oi_floor=profile.min_oi_floor,
                wall_scope="FRONT_WEEK_WEIGHTED",
                wall_dte_range=INTRADAY_VIEW.dte_range,
            )
            _t(f"calc_intraday_{ticker}")
            levels_macro = calculate_dealer_levels(
                chain,
                source_ticker,
                min_oi_floor=profile.min_oi_floor,
                wall_scope="ALL_EXPIRIES_WEIGHTED",
                wall_dte_range=MACRO_VIEW.dte_range,
            )
            _t(f"calc_macro_{ticker}")

            # NOTE: ETF→index rescaling (rescale_levels_to_target_spot) has been
            # removed.  Scaling ETF option levels into index space by a ratio is
            # mathematically invalid — the option books, OI, and Greeks are
            # fundamentally different.  If an index chain is thin, we use whatever
            # source_ticker produced and label it as that source (not the target).

            weekly_scope_record = None
            if is_eod_run and today_ny.weekday() == 4:
                weekly_candidate = _select_weekly_scope_candidate(levels_macro, today_ny)
                if weekly_candidate is None:
                    weekly_candidate = _select_weekly_scope_candidate(levels_intraday, today_ny)
                if weekly_candidate is not None:
                    weekly_em, weekly_expiry = weekly_candidate
                    weekly_scope_record = {
                        "expiry": weekly_expiry.strftime("%Y-%m-%d"),
                        "captured_on": today_ny.strftime("%Y-%m-%d"),
                        "source": "FRIDAY_EOD_CAPTURE",
                        "em_upper": round(float(weekly_em.em_upper), 2),
                        "em_lower": round(float(weekly_em.em_lower), 2),
                        "straddle_85_upper": round(float(getattr(weekly_em, "straddle_85_upper", 0.0) or 0.0), 2),
                        "straddle_85_lower": round(float(getattr(weekly_em, "straddle_85_lower", 0.0) or 0.0), 2),
                    }
                    if weekly_scope_cache.get(ticker) != weekly_scope_record:
                        weekly_scope_cache[ticker] = weekly_scope_record
                        weekly_scope_cache_updated = True
                        log.debug(
                            "Captured Friday weekly scope for %s -> %s [%.2f, %.2f]",
                            ticker,
                            weekly_scope_record["expiry"],
                            weekly_scope_record["em_lower"],
                            weekly_scope_record["em_upper"],
                        )
                else:
                    # Fallback: weekly expiry (DTE 4-10) missing from chain.
                    # Compute EM via TOS formula using chain spot + ATM IV.
                    _is_fut = futures_sym is not None and futures_sym.startswith("/")
                    tos_fb = _compute_tos_em_fallback(levels_macro, today_ny, is_futures=_is_fut)
                    if tos_fb is None:
                        tos_fb = _compute_tos_em_fallback(levels_intraday, today_ny, is_futures=_is_fut)
                    if tos_fb is not None:
                        em_up, em_lo, exp_str = tos_fb
                        weekly_scope_record = {
                            "expiry": exp_str,
                            "captured_on": today_ny.strftime("%Y-%m-%d"),
                            "source": "FRIDAY_EOD_TOS_FORMULA_FALLBACK",
                            "em_upper": em_up,
                            "em_lower": em_lo,
                            "straddle_85_upper": 0.0,
                            "straddle_85_lower": 0.0,
                        }
                        log.info("[weekly_scope] %s: TOS formula fallback EM +-%.2f for %s expiry",
                                 ticker, (em_up - em_lo) / 2, exp_str)
                        if weekly_scope_cache.get(ticker) != weekly_scope_record:
                            weekly_scope_cache[ticker] = weekly_scope_record
                            weekly_scope_cache_updated = True

            if weekly_scope_record is None:
                candidate_record = weekly_scope_cache.get(ticker)
                expiry = _parse_iso_date(candidate_record.get("expiry") if candidate_record else None)
                if candidate_record and expiry and expiry >= today_ny:
                    weekly_scope_record = candidate_record
                elif ticker in weekly_scope_cache:
                    del weekly_scope_cache[ticker]
                    weekly_scope_cache_updated = True

            _attach_weekly_scope(levels_intraday, weekly_scope_record)
            _attach_weekly_scope(levels_macro, weekly_scope_record)

            cash_levels_by_ticker[ticker] = levels_intraday 
            macro_levels_by_ticker[ticker] = levels_macro

            # 5. Compute ScoredLevels for both views
            
            # Intraday Scoring (filters to ±6% spot, Primary/Secondary/Context)
            scored_intraday = score_levels(levels_intraday, intraday_chain, ticker, profile, INTRADAY_VIEW)
            
            # Macro Scoring (filters to ±15% spot, Primary only)
            scored_macro = score_levels(levels_macro, chain, ticker, profile, MACRO_VIEW)

            # 6. Translate levels into futures price space
            if futures_sym is None or fut is None:
                log.debug("No futures translation for %s (mapping missing or quote failed).", ticker)
                # We skip appending to translated_levels, but proceed to next steps
                # so cash_levels_by_ticker is already populated and can be used.
            else:
                # 6. Translate levels into futures price space
                tl_intraday = translate_to_futures(levels_intraday, fut, anchor_basis=anchor_basis, anchor_ratio=anchor_ratio)
                tl_macro = translate_to_futures(levels_macro, fut, anchor_basis=anchor_basis, anchor_ratio=anchor_ratio)

                if weekly_scope_record is not None:
                    _attach_weekly_scope(tl_intraday, _translate_weekly_scope_record(weekly_scope_record, tl_intraday))
                    _attach_weekly_scope(tl_macro, _translate_weekly_scope_record(weekly_scope_record, tl_macro))
                
                # 6b. RTD GEX — compute dealer levels directly from futures options if RTD active
                rtd_tl = None
                rtd_dl_primary = None
                if rtd_coord.is_rtd_active and futures_sym in rtd_coord._symbols:
                    from .config import TOS_RTD_GEX_AS_PRIMARY
                    if futures_sym in rtd_gex_results:
                        rtd_gex_result = rtd_gex_results[futures_sym]
                        if rtd_gex_result and PIPELINE_DEBUG_RTD:
                            log.info("Reusing cached RTD GEX result for %s", futures_sym)
                    else:
                        _t(f"rtd_gex_start_{ticker}")
                        rtd_gex_result = rtd_coord.calculate_rtd_gex(futures_sym)
                        _t(f"rtd_gex_done_{ticker}")
                        rtd_gex_results[futures_sym] = rtd_gex_result

                    if rtd_gex_result is not None:
                        rtd_dl = rtd_gex_result.dealer_levels
                        rtd_dl_primary = rtd_dl
                        
                        # Score and save direct RTD levels under futures ticker (e.g. 'NQ' or 'ES')
                        # Only inject when the user explicitly requested this futures ticker.
                        if rtd_gex_result.chain_data is not None:
                            clean_fut_sym = futures_sym.lstrip('/')
                            if clean_fut_sym in target_tickers:
                                # Don't overwrite if the RTD-native path already
                                # scored this ticker with its own profile (line 551).
                                # The RTD-native path uses get_ticker_profile("ES")
                                # while the Schwab-ETF loop here uses the ETF's
                                # profile (e.g. SPY), which has different min_oi
                                # thresholds and would produce different walls.
                                if clean_fut_sym in RTD_NATIVE_TICKERS and clean_fut_sym in scored_intraday_by_ticker:
                                    log.info("RTD-native scored levels already exist for %s — not overwriting from %s loop",
                                             clean_fut_sym, ticker)
                                else:
                                    try:
                                        rtd_scored_intraday = score_levels(
                                            rtd_dl, rtd_gex_result.chain_data, clean_fut_sym, profile, INTRADAY_VIEW
                                        )
                                        rtd_scored_macro = score_levels(
                                            rtd_dl, rtd_gex_result.chain_data, clean_fut_sym, profile, MACRO_VIEW
                                        )
                                        scored_intraday_by_ticker[clean_fut_sym] = rtd_scored_intraday
                                        scored_macro_by_ticker[clean_fut_sym] = rtd_scored_macro
                                        log.info("Direct RTD scored levels saved for ticker: %s", clean_fut_sym)
                                    except Exception as e:
                                        log.error("Failed to score direct RTD levels for %s: %s", clean_fut_sym, e)
                            else:
                                log.debug(
                                    "RTD levels computed for %s (used for GEX/price context) but not saved "
                                    "— add '%s' to --tickers to include it in output.",
                                    clean_fut_sym, clean_fut_sym,
                                )

                        if PIPELINE_DEBUG_RTD:
                            log.info(
                                "RTD GEX for %s: total_gex=%.2f regime=%s call_wall=%s put_wall=%s zero_gamma=%s (%d contracts)",
                                futures_sym, rtd_dl.total_gex, rtd_dl.gex_regime,
                                rtd_dl.call_wall, rtd_dl.put_wall, rtd_dl.zero_gamma,
                                rtd_gex_result.contract_count,
                            )



                        if TOS_RTD_GEX_AS_PRIMARY:
                            if PIPELINE_DEBUG_RTD:
                                log.info("Using RTD GEX as PRIMARY for %s (TOS_RTD_GEX_AS_PRIMARY=True)", futures_sym)
                            # Tag the RTD dealer levels with futures metadata
                            rtd_dl.futures_symbol = futures_sym
                            rtd_dl.translation_mode = "rtd_direct"
                            rtd_dl.basis_spread = 0.0
                            rtd_dl.basis_ratio = 1.0
                            # Replace the translated levels with RTD-sourced ones
                            # We need to construct a TranslatedLevels from the RTD DealerLevels
                            from .futures_translator import TranslatedLevels
                            rtd_tl = TranslatedLevels(
                                futures_symbol=futures_sym,
                                cash_ticker=futures_sym,  # RTD is direct, no cash proxy
                                futures_price=rtd_gex_result.futures_price,
                                cash_spot=rtd_gex_result.futures_price,
                                basis_spread=0.0,
                                basis_ratio=1.0,
                                translation_mode="rtd_direct",
                                min_tick=0.25,
                                total_gex=rtd_dl.total_gex,
                                gex_regime=rtd_dl.gex_regime,
                                zero_gamma=rtd_dl.zero_gamma,
                                zero_gamma_delta_adj=rtd_dl.zero_gamma_delta_adj,
                                gamma_flip_lower=rtd_dl.gamma_flip_lower,
                                gamma_flip_upper=rtd_dl.gamma_flip_upper,
                                call_wall=rtd_dl.call_wall,
                                put_wall=rtd_dl.put_wall,
                                secondary_call_wall=rtd_dl.secondary_call_wall,
                                secondary_put_wall=rtd_dl.secondary_put_wall,
                                local_call_node=rtd_dl.local_call_node,
                                local_put_node=rtd_dl.local_put_node,
                                call_wall_0dte=rtd_dl.call_wall_0dte,
                                put_wall_0dte=rtd_dl.put_wall_0dte,
                                hedge_wall=rtd_dl.hedge_wall,
                                max_pain=rtd_dl.max_pain,
                                em_upper=rtd_dl.em_upper,
                                em_lower=rtd_dl.em_lower,
                                em_value=rtd_dl.em_value,
                                atm_straddle=rtd_dl.atm_straddle,
                                gamma_magnet=rtd_dl.gamma_magnet,
                                pin_strike=rtd_dl.pin_strike,
                                pin_odds=rtd_dl.pin_odds,
                                wall_separation=rtd_dl.wall_separation,
                                regime_label=rtd_dl.regime_label,
                                directional_bias=rtd_dl.directional_bias,
                                call_gamma_total=rtd_dl.call_gamma_total,
                                put_gamma_total=rtd_dl.put_gamma_total,
                                net_vanna_exposure=rtd_dl.net_vanna_exposure,
                                wall_scope=rtd_dl.wall_scope,
                                wall_dte_min=rtd_dl.wall_dte_min,
                                wall_dte_max=rtd_dl.wall_dte_max,
                                concentration_score=rtd_dl.concentration_score,
                                call_wall_oi=rtd_dl.call_wall_oi,
                                put_wall_oi=rtd_dl.put_wall_oi,
                                pin_strike_oi=rtd_dl.pin_strike_oi,
                                net_speed_exposure=rtd_dl.net_speed_exposure,
                                total_gex_delta_adj=rtd_dl.total_gex_delta_adj,
                                call_volume_centroid=rtd_dl.call_volume_centroid,
                                put_volume_centroid=rtd_dl.put_volume_centroid,
                                atm_iv=rtd_dl.atm_iv,
                                put_25d_iv=rtd_dl.put_25d_iv,
                                call_25d_iv=rtd_dl.call_25d_iv,
                                volatility_skew_premium=rtd_dl.volatility_skew_premium,
                                vol_trigger_upper_05=getattr(rtd_dl, 'vol_trigger_upper_05', None),
                                vol_trigger_lower_05=getattr(rtd_dl, 'vol_trigger_lower_05', None),
                                vol_trigger_upper_10=getattr(rtd_dl, 'vol_trigger_upper_10', None),
                                vol_trigger_lower_10=getattr(rtd_dl, 'vol_trigger_lower_10', None),
                                vol_trigger_upper_15=getattr(rtd_dl, 'vol_trigger_upper_15', None),
                                vol_trigger_lower_15=getattr(rtd_dl, 'vol_trigger_lower_15', None),
                                gamma_cliff_up=getattr(rtd_dl, 'gamma_cliff_up', None),
                                gamma_cliff_down=getattr(rtd_dl, 'gamma_cliff_down', None),
                                vanna_call_node=getattr(rtd_dl, 'vanna_call_node', None),
                                vanna_put_node=getattr(rtd_dl, 'vanna_put_node', None),
                                charm_call_node=getattr(rtd_dl, 'charm_call_node', None),
                                charm_put_node=getattr(rtd_dl, 'charm_put_node', None),
                                volume_imbalance_call_node=getattr(rtd_dl, 'volume_imbalance_call_node', None),
                                volume_imbalance_put_node=getattr(rtd_dl, 'volume_imbalance_put_node', None),
                                dex_call_node=getattr(rtd_dl, 'dex_call_node', None),
                                dex_put_node=getattr(rtd_dl, 'dex_put_node', None),
                                liquidity_vacuum_lower=getattr(rtd_dl, 'liquidity_vacuum_lower', None),
                                liquidity_vacuum_upper=getattr(rtd_dl, 'liquidity_vacuum_upper', None),
                                skew_pivot_put_25d=getattr(rtd_dl, 'skew_pivot_put_25d', None),
                                skew_pivot_call_25d=getattr(rtd_dl, 'skew_pivot_call_25d', None),
                                hedge_flow_up_10=getattr(rtd_dl, 'hedge_flow_up_10', 0.0),
                                hedge_flow_up_25=getattr(rtd_dl, 'hedge_flow_up_25', 0.0),
                                hedge_flow_up_50=getattr(rtd_dl, 'hedge_flow_up_50', 0.0),
                                hedge_flow_dn_10=getattr(rtd_dl, 'hedge_flow_dn_10', 0.0),
                                hedge_flow_dn_25=getattr(rtd_dl, 'hedge_flow_dn_25', 0.0),
                                hedge_flow_dn_50=getattr(rtd_dl, 'hedge_flow_dn_50', 0.0),
                                hourly_flow_curve=getattr(rtd_dl, 'hourly_flow_curve', []),
                                iv_change=getattr(rtd_dl, 'iv_change', 0.0),
                                expected_moves=rtd_dl.expected_moves,
                            )

                # Don't append a duplicate futures entry if the RTD-native
                # path already added one (line 664).  The RTD-native path
                # produces the authoritative /ES and /NQ entries; the Schwab
                # ETF loop's translated entry would be overwritten in
                # build_current_state anyway, and having two entries for the
                # same futures_symbol causes the SPY-translated values to
                # silently replace the RTD-direct ones in pipeline_state.
                _fut_already_added = any(
                    getattr(tl, 'futures_symbol', None) == futures_sym
                    and getattr(tl, 'translation_mode', None) == 'rtd_direct'
                    for tl in translated_levels
                )
                if _fut_already_added:
                    log.info("RTD-direct entry already exists for %s — skipping Schwab-translated append",
                             futures_sym)
                else:
                    translated_levels.append(tl_intraday)
                    translated_macro_levels.append(tl_macro)

                    # 6c. If RTD GEX is primary, replace the just-appended Schwab levels
                    if rtd_tl is not None and TOS_RTD_GEX_AS_PRIMARY:
                        translated_levels[-1] = rtd_tl
                        translated_macro_levels[-1] = replace(rtd_tl, wall_scope="ALL_EXPIRIES_WEIGHTED")
                        # Write RTD GEX snapshot to DB
                        if _is_rth() and rtd_dl_primary is not None:
                            from .interval_writer import write_snapshot
                            write_snapshot(rtd_dl_primary, ticker_override=futures_sym)

            # 7. Write per-ticker snapshot to DB (now includes futures translation fields)
            if _is_rth():
                from .interval_writer import write_snapshot
                write_snapshot(levels_intraday, ticker_override=ticker)

                # (Removed translate_scored_levels call: TradingView Pinescript performs live dynamic translation 
                # against native cash/ETF data. Unified outputs must remain in native space to prevent double-conversion).

            # Save the final (translated if futures quote was available) scored levels to dicts
            scored_intraday_by_ticker[ticker] = scored_intraday
            scored_macro_by_ticker[ticker] = scored_macro

            if ENABLE_SCORED_CONTRACT_OUTPUTS:
                # DEPRECATED: write_scored_levels_txt generation stopped.
                # Files moved to archive. Left here commented for reference.
                # write_scored_levels_txt(
                #     ticker,
                #     scored_intraday,
                #     metadata_levels=levels_intraday,
                #     versioned=versioned,
                #     snapshot_suffix=snapshot_suffix,
                # )
                # write_scored_levels_txt(
                #     ticker,
                #     scored_macro,
                #     metadata_levels=levels_macro,
                #     path=SCORED_MACRO_LEVELS_TXT,
                #     versioned=versioned,
                #     snapshot_suffix=snapshot_suffix,
                # )
                pass

            # 8. Support basis anchors for next loop
            # (Keeping base_open logic for opening basis detection)
            base_open = full_chain.spot_open

        except RuntimeError as exc:
            # API errors (HTTP failures, rate limits, bad responses)
            log.error("API error for %s: %s", ticker, exc)
            continue
        except ValueError as exc:
            # Calculation errors (zero spot, etc.)
            log.error("Calculation error for %s: %s", ticker, exc)
            continue
        except Exception as exc:
            log.error(
                "Unexpected error for %s: %s", ticker, exc, exc_info=True
            )
            continue

    # --- Save anchors if updated --------------------------------------------
    if new_anchors_captured:
        save_basis_anchors(all_anchors)
    if weekly_scope_cache_updated:
        _save_weekly_scope_cache(weekly_scope_cache)

    if not translated_levels and not cash_levels_by_ticker and not scored_intraday_by_ticker:
        log.error("No levels were computed — all outputs skipped.")
        return

    # --- Persist to disk ----------------------------------------------------
    try:
        from .config import (
            DATA_DIR, DAILY_LEVELS_TXT, INTRADAY_LEVELS_JSON, MACRO_LEVELS_JSON,
        )

        # 1. Intraday View — canonical write to intraday_levels.json.
        #    daily_levels.json is no longer written (it was an identical duplicate).
        #    Web consumers read intraday_levels.json directly.
        write_levels(
            translated_levels,
            run_label,
            cash_levels=list(cash_levels_by_ticker.values()),
            scored_levels=list(scored_intraday_by_ticker.values()),
            json_path=INTRADAY_LEVELS_JSON,
            txt_path=None,  # Legacy TXT deprecated — unified_levels.txt is the canonical text output
            versioned=versioned,
            snapshot_suffix=snapshot_suffix,
        )
        
        # 2. Macro View (Macro paths)
        write_levels(
            translated_macro_levels,
            run_label,
            cash_levels=list(macro_levels_by_ticker.values()),
            scored_levels=list(scored_macro_by_ticker.values()),
            json_path=MACRO_LEVELS_JSON,
            txt_path=None, # Macro TXT deprecated
            txt_mode="macro",
            versioned=versioned,
            snapshot_suffix=snapshot_suffix,
        )

        if ENABLE_UNIFIED_CONTRACT_OUTPUTS:
            write_unified_levels_txt(
                list(scored_intraday_by_ticker.values()),
                path=UNIFIED_LEVELS_TXT,
                versioned=versioned,
                snapshot_suffix=snapshot_suffix,
                macro_scored_levels=list(scored_macro_by_ticker.values()),
                metadata_levels_by_ticker=cash_levels_by_ticker,
                macro_spot_by_ticker={k: v.spot for k, v in macro_levels_by_ticker.items()},
            )
            write_unified_levels_json(
                list(scored_intraday_by_ticker.values()),
                path=UNIFIED_LEVELS_JSON,
                versioned=versioned,
                snapshot_suffix=snapshot_suffix,
                macro_scored_levels=list(scored_macro_by_ticker.values()),
                metadata_levels_by_ticker=cash_levels_by_ticker,
                macro_spot_by_ticker={k: v.spot for k, v in macro_levels_by_ticker.items()},
            )

            txt_fp = unified_payload_fingerprint(UNIFIED_LEVELS_TXT)
            json_fp = unified_payload_fingerprint(UNIFIED_LEVELS_JSON)
            log.info(
                "Unified TXT fingerprint | exists=%s bytes=%d lines=%d sha256=%s",
                txt_fp["exists"],
                txt_fp["bytes"],
                txt_fp["lines"],
                txt_fp["sha256"],
            )
            log.info(
                "Unified JSON fingerprint | exists=%s bytes=%d lines=%d sha256=%s",
                json_fp["exists"],
                json_fp["bytes"],
                json_fp["lines"],
                json_fp["sha256"],
            )
        else:
            log.info("Unified contract outputs disabled by config flag.")

        if not ENABLE_SCORED_CONTRACT_OUTPUTS:
            log.info("Scored contract outputs disabled by config flag; unified feed is default.")
    except Exception as exc:
        log.error("File write failed: %s", exc)

    # --- State tracking & regime change detection ---------------------------
    try:
        previous_state = load_previous_state()
        current_state = build_current_state(
            run_label, translated_levels, cash_levels_by_ticker,
            previous_state=previous_state,
        )
        changes = detect_changes(previous_state, current_state)
        save_current_state(current_state)

        if changes:
            log.info(
                "Detected %d state change(s): %s",
                len(changes),
                ", ".join(f"{c.ticker}:{c.change_type}" for c in changes),
            )
        else:
            log.info("No regime changes detected since last run.")
    except Exception as exc:
        log.error("State tracking failed: %s", exc)
        changes = []

    # --- Send Discord notification (optional + time-gated) ------------------
    should_send_discord = enable_discord and _discord_window_allowed(
        run_label=run_label,
        snapshot_suffix=snapshot_suffix,
        now_ny=now_ny,
    )

    if should_send_discord:
        try:
            send_discord_update(
                translated_levels,
                run_label,
                cash_levels=list(cash_levels_by_ticker.values()),
                scored_levels=list(scored_intraday_by_ticker.values()),
                unified_copy_path=UNIFIED_LEVELS_TXT if ENABLE_UNIFIED_CONTRACT_OUTPUTS else None,
                webhook_key=discord_target_key,
                include_cash_embeds=full_discord,
            )
        except Exception as exc:
            log.error("Discord notification failed: %s", exc)

        # Send regime change alert if any changes detected
        if changes:
            try:
                alert_text = format_change_alert(changes, run_label)
                if alert_text:
                    send_regime_change_alert(alert_text)
            except Exception as exc:
                log.error("Regime change alert failed: %s", exc)

        # Send RTD health status if RTD is enabled
        if rtd_coord._enabled:
            try:
                from .discord_notifier import send_rtd_health_alert
                send_rtd_health_alert(rtd_coord.get_status())
            except Exception as exc:
                log.error("RTD health alert failed: %s", exc)
    else:
        if not enable_discord:
            log.info("Discord updates are disabled for this run.")
        else:
            log.info("Discord updates skipped (outside allowed windows: 09:30, 16:15 ET).")

    # --- Greeks drift validation (legacy diagnostic, off by default) ---------
    from .config import TOS_RTD_ENABLE_DRIFT_VALIDATION
    if rtd_coord.is_rtd_active and TOS_RTD_ENABLE_DRIFT_VALIDATION:
        validated_syms = set()
        for ticker, levels in cash_levels_by_ticker.items():
            futures_sym = INDEX_TO_FUTURES.get(ticker)
            if not futures_sym or futures_sym in validated_syms:
                continue
            drift_results = rtd_coord.validate_greeks(levels, futures_sym)
            validated_syms.add(futures_sym)
            if drift_results:
                drifts = [r.gamma_drift_pct for r in drift_results if r.gamma_drift_pct is not None]
                avg_drift = sum(drifts) / len(drifts) if drifts else 0.0
                max_drift = max(drifts) if drifts else 0.0
                high_drift_count = sum(1 for d in drifts if d > 5.0)
                log.info(
                    "Greeks drift validation for %s: %d contracts, avg drift=%.4f%%, max=%.4f%%",
                    futures_sym,
                    len(drift_results),
                    avg_drift,
                    max_drift,
                )
                if high_drift_count > 0:
                    log.warning(
                        "Greeks drift > 5%% on %d contracts for %s — BSM model may need recalibration",
                        high_drift_count,
                        futures_sym,
                    )

    # --- Stop RTD coordinator only if we started it --------------------------
    if rtd_started_here:
        rtd_coord.stop()

    log.info("Pipeline complete  |  %s", run_label)


# ---------------------------------------------------------------------------
# Continuous Priority Loop  (--loop mode)
# ---------------------------------------------------------------------------

def run_loop(enable_discord: bool = False) -> None:
    """
    Continuously run the pipeline in a two-tier priority loop.

    Tier 1 (PRIORITY_TICKERS: SPX, SPY, QQQ) — processed every iteration.
    Tier 2 (remaining ACTIVE_TICKERS)         — processed only when their
        last-processed timestamp exceeds TIER2_INTERVAL_SECONDS.

    The base tick is 60 seconds (matching the Schwab API rate limit comfort
    zone). Tier-2 tickers refresh approximately every 10 minutes.
    """
    import time
    _setup_logging()

    tick_interval = 60          # seconds between Tier-1 passes
    tier2_due: dict[str, float] = {}   # tracks when each Tier-2 ticker is next eligible

    tier1 = [t for t in ACTIVE_TICKERS if t in PRIORITY_TICKERS]
    tier2 = [t for t in ACTIVE_TICKERS if t not in PRIORITY_TICKERS]

    log.info("=" * 60)
    log.info("Continuous Priority Loop starting")
    log.info("  Standard Tier-1: 60s (RTH) | 30m (Off-hours) | 4h (Weekends)")
    log.info("  Standard Tier-2: 10m (RTH) | 1h  (Off-hours) | 4h (Weekends)")
    log.info("=" * 60)

    tier1_last_run = 0.0
    tier2_last_run: dict[str, float] = {}

    try:
        client = create_client(SECRETS_PATH, TOKEN_PATH)
    except Exception as exc:
        log.critical("Cannot create Schwab client: %s", exc)
        return

    # --- TOS RTD coordinator: start once and reuse across all loop cycles ---
    loop_rtd_coord: HybridCoordinator | None = None
    try:
        loop_rtd_coord = HybridCoordinator()
        loop_rtd_coord.start()
        if loop_rtd_coord.is_rtd_active:
            log.info("Loop RTD coordinator active — real-time futures prices enabled")
        elif loop_rtd_coord._enabled:
            log.warning("Loop RTD coordinator enabled but not active — check TOS desktop")
    except Exception as exc:
        log.warning("Failed to start loop RTD coordinator: %s", exc)

    # --- RTD health-check / restart state ----------------------------------
    # RTD can drop mid-session (worker process crash, TOS desktop restart,
    # COM topic failure). Without recovery, NQ/ES silently skip for the rest
    # of the session. We periodically probe is_rtd_active and attempt a
    # restart when it goes False, with exponential backoff so we don't
    # hammer a broken TOS instance.
    import time as _time_module
    rtd_health_last_check = 0.0          # epoch seconds of last probe
    rtd_health_last_restart = 0.0        # epoch seconds of last restart attempt
    rtd_restart_failures = 0             # consecutive failed restart attempts
    RTD_HEALTH_CHECK_INTERVAL = 60.0    # probe every 60s (cheap — just reads a flag)
    RTD_RESTART_MIN_BACKOFF = 30.0       # initial backoff between restart attempts
    RTD_RESTART_MAX_BACKOFF = 1800.0     # cap at 30 min
    RTD_RESTART_MAX_FAILURES = 10        # after this, stop trying until process restart

    # --- Pulse Scheduling ---
    # We want to force a FULL versioned run at exactly these times.
    # We now pull these from config.SCHEDULE_TIMES
    snapshot_targets = SCHEDULE_TIMES # ["08:30", "09:30", "10:00", ...]
    last_pulse_date: dict[str, str] = {} # "08:30" -> "2026-05-06"

    # Initialize past targets on startup to prevent backlog replay storm
    init_ny_now = datetime.now(ZoneInfo(SCHEDULE_TIMEZONE))
    init_time_str = init_ny_now.strftime("%H:%M")
    init_today_str = init_ny_now.strftime("%Y-%m-%d")
    for s_time in snapshot_targets:
        if s_time <= init_time_str:
            last_pulse_date[s_time] = init_today_str
            log.info("Loop startup: marked past scheduled pulse %s as completed for today.", s_time)

    try:
        while True:
            ny_now = datetime.now(ZoneInfo(SCHEDULE_TIMEZONE))
            now = time.time() # Current timestamp for interval checks
            today_str = ny_now.strftime("%Y-%m-%d")

            # Futures Market Weekend Timing: Friday 17:00 ET to Sunday 18:00 ET
            is_weekend_closed = (
                (ny_now.weekday() == 4 and ny_now.time() >= FUTURES_CLOSE_FRIDAY_TIME) or  # Friday after 5pm
                (ny_now.weekday() == 5) or                                                # Saturday
                (ny_now.weekday() == 6 and ny_now.time() < FUTURES_OPEN_SUNDAY_TIME)      # Sunday before 6pm
            )

            # Regular Trading Hours (Equity RTH)
            is_equity_rth = (EQUITY_RTH_START_TIME <= ny_now.time() <= EQUITY_RTH_END_TIME) and not is_weekend_closed

            # Options RTH: 09:30–16:00 ET — the window when Schwab actually
            # returns fresh intraday data for cash equity/ETF option chains.
            # Outside this window, ETF/INDEX chains are stale; only futures
            # (/ES, /NQ) stream continuously via RTD.
            is_options_rth = (OPTIONS_RTH_START_TIME <= ny_now.time() <= OPTIONS_RTH_END_TIME) and not is_weekend_closed

            # --- Adaptive Intervals ---
            if is_equity_rth:
                t1_interval = RTH_T1_INTERVAL
                t2_interval = RTH_T2_INTERVAL
            elif is_weekend_closed:
                t1_interval = WEEKEND_T1_INTERVAL
                t2_interval = WEEKEND_T2_INTERVAL
            else:
                # Active futures but not equity RTH (e.g. overnight/pre-market)
                t1_interval = OFF_HOURS_T1_INTERVAL
                t2_interval = OFF_HOURS_T2_INTERVAL

            # Reload priority tickers dynamically
            from .config import get_priority_tickers
            dynamic_priority = get_priority_tickers()

            # Merge hardcoded indices with user-specified priority
            tier1_tickers = list(set(TIER1_TICKERS_DEFAULT + dynamic_priority))
            tier2_tickers = [t for t in ACTIVE_TICKERS if t not in tier1_tickers]

            is_pulse_cycle = False
            pulse_suffix = None
            pulse_time_str = None
            current_time_str = ny_now.strftime("%H:%M") # "08:30"
            for s_time in snapshot_targets:
                # If we are AT or PAST a snapshot time today, and haven't run it yet
                if current_time_str >= s_time and last_pulse_date.get(s_time) != today_str:
                    # On weekdays, trigger the pulse
                    if ny_now.weekday() < 5:
                        is_pulse_cycle = True
                        pulse_time_str = s_time
                        pulse_suffix = _build_snapshot_suffix(ny_now, s_time)
                        last_pulse_date[s_time] = today_str
                        log.info("SCHEDULED PULSE DETECTED: %s snapshot triggered.", s_time)
                        break

            # Check for manual trigger file (e.g., from UI 'Refresh' button)
            manual_trigger_file = REPO_ROOT / MANUAL_TRIGGER_FILENAME
            manual_tickers = []
            if manual_trigger_file.exists():
                try:
                    with open(manual_trigger_file, "r") as f:
                        manual_tickers = json.load(f)
                    manual_trigger_file.unlink() # consume the trigger
                    log.info("Manual trigger detected for: %s", ", ".join(manual_tickers))
                except Exception as e:
                    log.error("Failed to read/delete manual trigger file: %s", e)

            # Decide what is due
            due_tier1 = tier1_tickers if (now - tier1_last_run) >= t1_interval else []

            # Off-hours ticker restriction (uses OPTIONS RTH, not equity RTH):
            # Outside options RTH (09:30–16:00 ET), cash equity/ETF option
            # chains from Schwab are stale or empty. Only futures (/ES, /NQ)
            # stream continuously via RTD, so restrict regular (non-pulse)
            # cycles to RTD-native tickers. Pulse cycles and manual triggers
            # still run the full ticker set — pulses are the daily anchor
            # snapshots and must capture ETF OI even if intraday data is thin.
            is_off_hours = not is_options_rth and not is_weekend_closed
            if is_off_hours and not is_pulse_cycle and not manual_tickers:
                # Futures-only subset during pre/post-market hours.
                # NQ/ES are RTD-native; if RTD is down we still emit them so the
                # pipeline's RTD-native skip + fallback path handles it.
                rtd_native_loop_tickers = [t for t in ACTIVE_TICKERS if t in {"NQ", "ES"}]
                if rtd_native_loop_tickers and (now - tier1_last_run) >= t1_interval:
                    active_this_cycle = rtd_native_loop_tickers
                    is_versioned = False
                    is_intraday_only = True
                    log.info(
                        "Off-hours (outside options RTH %s–%s ET): restricting cycle to RTD-native futures %s — "
                        "Schwab ETF chains skipped until %s ET",
                        OPTIONS_RTH_START_TIME.strftime("%H:%M"),
                        OPTIONS_RTH_END_TIME.strftime("%H:%M"),
                        rtd_native_loop_tickers,
                        OPTIONS_RTH_START_TIME.strftime("%H:%M"),
                    )
                else:
                    active_this_cycle = []
                    is_versioned = False
                    is_intraday_only = False
            else:
                # Restriction logic:
                # 1. Pulse Cycle -> ALL TICKERS (Full snapshot)
                # 2. Manual Trigger -> TIER 1 + Manual Tickers
                # 3. Normal Loop -> TIER 1 Only (if due)
                is_intraday_only = False
                if is_pulse_cycle:
                    active_this_cycle = ACTIVE_TICKERS
                    is_versioned = True
                elif manual_tickers:
                    active_this_cycle = list(set(due_tier1 + manual_tickers))
                    is_versioned = False
                else:
                    active_this_cycle = due_tier1
                    is_versioned = False
                    is_intraday_only = True

            # --- RTD health check / restart (data-flow aware, throttled) ---
            # Old check only probed is_rtd_active (child process alive), so a
            # zombie worker with a dead COM feed passed every check while the
            # LAST price silently froze for hours. Now we probe the adapter's
            # get_health(): drain-thread aliveness, data staleness, heartbeat
            # errors. Any of those triggers a full restart with backoff.
            if loop_rtd_coord is not None and (now - rtd_health_last_check) >= RTD_HEALTH_CHECK_INTERVAL:
                rtd_health_last_check = now
                rtd_needs_restart = False
                rtd_health_reason = ""
                if not loop_rtd_coord.is_rtd_active:
                    rtd_needs_restart = True
                    rtd_health_reason = "inactive"
                elif loop_rtd_coord._adapter is not None:
                    try:
                        health = loop_rtd_coord._adapter.get_health()
                        if health.get("drain_dead"):
                            rtd_needs_restart = True
                            rtd_health_reason = "drain thread dead"
                        elif health.get("last_data_age_seconds") is not None \
                                and health["last_data_age_seconds"] > 300 \
                                and not is_weekend_closed:
                            # RTH-aware: when the futures market is closed
                            # (weekend/holiday), zero data flow is normal —
                            # no restarts, no alarms. Only silence DURING
                            # tradable hours means the feed is dead.
                            rtd_needs_restart = True
                            rtd_health_reason = f"no data for {health['last_data_age_seconds']:.0f}s"
                        elif health.get("worker_errors", 0) >= 3:
                            rtd_needs_restart = True
                            rtd_health_reason = f"{health['worker_errors']} worker errors"
                    except Exception as h_exc:
                        log.debug("RTD health probe failed: %s", h_exc)

                if rtd_needs_restart:
                    # Determine backoff for this attempt
                    backoff = min(
                        RTD_RESTART_MIN_BACKOFF * (2 ** rtd_restart_failures),
                        RTD_RESTART_MAX_BACKOFF,
                    )
                    if rtd_restart_failures >= RTD_RESTART_MAX_FAILURES:
                        # Silent after max failures — only log once per backoff window
                        pass
                    elif (now - rtd_health_last_restart) >= backoff:
                        log.warning(
                            "RTD unhealthy (%s, failures=%d) — attempting restart (backoff=%.0fs)...",
                            rtd_health_reason, rtd_restart_failures, backoff,
                        )
                        rtd_health_last_restart = now
                        try:
                            # If a previous error path cleared _enabled, restore it
                            # so start() actually tries. Also stop any zombie adapter.
                            if not loop_rtd_coord._enabled:
                                loop_rtd_coord._enabled = True
                            if loop_rtd_coord._adapter is not None:
                                try:
                                    loop_rtd_coord.stop()
                                except Exception:
                                    pass
                            loop_rtd_coord.start()
                            if loop_rtd_coord.is_rtd_active:
                                log.info("RTD restart succeeded — real-time futures prices resumed")
                                rtd_restart_failures = 0
                            else:
                                rtd_restart_failures += 1
                                log.warning(
                                    "RTD restart attempt %d did not activate — will retry in %.0fs",
                                    rtd_restart_failures,
                                    min(RTD_RESTART_MIN_BACKOFF * (2 ** rtd_restart_failures), RTD_RESTART_MAX_BACKOFF),
                                )
                        except Exception as exc:
                            rtd_restart_failures += 1
                            log.error("RTD restart attempt %d failed: %s", rtd_restart_failures, exc)

            if active_this_cycle:
                run_label = ny_now.strftime("%Y-%m-%d %H:%M ET")
                log.info("Cycle start — processing %d tickers: %s (Pulse=%s, Versioned=%s, IntradayOnly=%s)", 
                         len(active_this_cycle), ", ".join(active_this_cycle), is_pulse_cycle, is_versioned, is_intraday_only)

                # Temporarily restrict ACTIVE_TICKERS to our cycle subset
                import scripts.streaming.options.config as _cfg
                original = _cfg.ACTIVE_TICKERS
                _cfg.ACTIVE_TICKERS = active_this_cycle

                try:
                    # During the 09:30 pulse, we force an anchor reset
                    should_reset_anchors = (is_pulse_cycle and pulse_time_str == "09:30")

                    run_pipeline(
                        run_label=run_label, 
                        enable_discord=enable_discord, 
                        versioned=is_versioned,
                        reset_anchors=should_reset_anchors,
                        snapshot_suffix=pulse_suffix,
                        intraday_only=is_intraday_only,
                        rtd_coord=loop_rtd_coord,
                    )
                    # Successful run! Update timestamps
                    if due_tier1 or is_pulse_cycle:
                        tier1_last_run = now
                except Exception as exc:
                    log.error("Pipeline cycle failed: %s", exc)
                finally:
                    _cfg.ACTIVE_TICKERS = original
                    import gc
                    gc.collect()

            # Sleep for a short beat to check for manual triggers frequently
            time.sleep(LOOP_BEAT_SECONDS)
    finally:
        if loop_rtd_coord is not None:
            loop_rtd_coord.stop()


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def _is_trading_day(tz_name: "str | None" = None) -> bool:
    """Return True when today is a Monday–Friday trading day.

    Market holidays are not accounted for; add a trading-calendar library
    (e.g. pandas-market-calendars) for full holiday awareness.
    """
    if tz_name is None:
        tz_name = SCHEDULE_TIMEZONE
    return datetime.now(ZoneInfo(tz_name)).weekday() < 5


def run_scheduled(enable_discord: "bool | None" = None, narratives_only: bool = False) -> None:
    """
    Block and run the pipeline at the configured schedule times (APScheduler).
    The process runs on weekdays only; weekends are silently skipped.

    Raises SystemExit when APScheduler is not installed.
    """
    _setup_logging()
    if enable_discord is None:
        enable_discord = ENABLE_DISCORD_UPDATES

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.critical(
            "APScheduler is not installed. "
            "Run: pip install 'apscheduler>=3.10,<4'"
        )
        sys.exit(1)

    tz = ZoneInfo(SCHEDULE_TIMEZONE)
    job_defaults = {
        "misfire_grace_time": SCHEDULER_MISFIRE_GRACE_TIME,
        "coalesce": True,
        "max_instances": 1,
    }
    scheduler = BlockingScheduler(timezone=tz, job_defaults=job_defaults)

    if not narratives_only:
        # Deduplicate schedule times to prevent double-firing (e.g. duplicate
        # "11:00" entries in config).
        seen_times: set[str] = set()
        for time_str in SCHEDULE_TIMES:
            if time_str in seen_times:
                log.warning(
                    "Duplicate schedule time '%s' in SCHEDULE_TIMES — skipping.",
                    time_str,
                )
                continue
            seen_times.add(time_str)

            hour, minute = map(int, time_str.split(":"))
            label = f"{time_str} ET"

            def _job(lbl: str = label, t_str: str = time_str) -> None:
                if _is_trading_day():
                    is_pulse = t_str in ("09:30", "16:00")
                    # Reset anchors only at 09:30 open
                    do_reset = (t_str == "09:30")
                    suffix = _build_snapshot_suffix(datetime.now(tz), t_str)
                    run_pipeline(run_label=lbl, enable_discord=enable_discord, versioned=is_pulse, reset_anchors=do_reset, snapshot_suffix=suffix)
                else:
                    log.info("Non-trading day — skipping %s run.", lbl)

            scheduler.add_job(
                _job,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
                id=f"dealer_levels_{time_str.replace(':', '')}",
                replace_existing=True,
                misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,
                coalesce=True,
            )
            log.info("Scheduled Options Run: %s ET", time_str)
    else:
        log.info("Running in --narratives-only mode: Options pipeline cron jobs skipped (handled by --loop).")

    # -----------------------------------------------------------------
    # NARRATIVE JOBS (Trader Briefing System)
    # -----------------------------------------------------------------
    import os
    import subprocess

    from scripts.streaming.options.config import (
        NARRATIVE_SCHEDULE,
        NARRATIVE_TICKERS,
        WEEKLY_NARRATIVE_TIME,
    )

    ticker_args = ["--tickers", *NARRATIVE_TICKERS]

    def _parse_time(time_str: str) -> tuple[int, int]:
        hour, minute = map(int, time_str.split(":"))
        return hour, minute

    def _run_subprocess(args: list[str], label: str, timeout: int = 600) -> None:
        if not _is_trading_day():
            log.info("Non-trading day — skipping %s.", label)
            return
        log.info("Running %s...", label)
        try:
            # We use subprocess so the LLM generation (which can take a minute)
            # does not block the apscheduler thread pool or crash the main pipeline.
            # NOTE: always use sys.executable (the interpreter that launched this
            # pipeline, i.e. the project venv) instead of the bare "python" on PATH.
            from scripts.streaming.options.config import REPO_ROOT
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT)
            resolved_args = [sys.executable, *args[1:]] if args and args[0] == "python" else args
            subprocess.run(
                resolved_args,
                env=env,
                cwd=str(REPO_ROOT),
                check=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
            log.info("✓ %s completed", label)
        except subprocess.TimeoutExpired:
            log.error("Timed out running %s after %ds", label, timeout)
        except Exception as e:
            log.error("Failed to run %s: %s", label, e)

    def _run_narrative_chain(jobs: list[tuple[list[str], str]]) -> None:
        """Run a sequence of narrative subprocesses (no short-circuiting)."""
        if not _is_trading_day():
            log.info("Non-trading day — skipping narrative chain.")
            return
        for args, label in jobs:
            _run_subprocess(args, label)

    # 0. Premarket Narrative
    premarket_hour, premarket_minute = _parse_time(NARRATIVE_SCHEDULE["premarket"])
    scheduler.add_job(
        lambda: _run_narrative_chain([
            (["python", "-m", "scripts.trader.trader_narrative", "--mode", "premarket", "--no-discord", *ticker_args], "Trader Narrative Premarket"),
        ]),
        trigger=CronTrigger(day_of_week='mon-fri', hour=premarket_hour, minute=premarket_minute, timezone=tz),
        id="narrative_premarket",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,
        coalesce=True,
    )
    log.info("Scheduled Narrative: %s ET (Premarket)", NARRATIVE_SCHEDULE["premarket"])

    # 1. Daily Open Narrative
    open_hour, open_minute = _parse_time(NARRATIVE_SCHEDULE["open"])
    scheduler.add_job(
        lambda: _run_narrative_chain([
            (["python", "-m", "scripts.trader.daily_eod_update", "--session", "open", *ticker_args], "Open Update"),
            (["python", "-m", "scripts.trader.daily_narrative", "--session", "open", *ticker_args], "Open Narrative"),
            (["python", "-m", "scripts.trader.trader_narrative", "--mode", "open", "--no-discord", *ticker_args], "Trader Narrative Open"),
        ]),
        trigger=CronTrigger(day_of_week='mon-fri', hour=open_hour, minute=open_minute, timezone=tz),
        id="narrative_open",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,
        coalesce=True,
    )
    log.info("Scheduled Narrative: %s ET (Open)", NARRATIVE_SCHEDULE["open"])

    # 2. Intraday Narrative
    intraday_hour, intraday_minute = _parse_time(NARRATIVE_SCHEDULE["intraday"])
    scheduler.add_job(
        lambda: _run_narrative_chain([
            (["python", "-m", "scripts.trader.trader_narrative", "--mode", "intraday", "--no-discord", *ticker_args], "Trader Narrative Intraday"),
        ]),
        trigger=CronTrigger(day_of_week='mon-fri', hour=intraday_hour, minute=intraday_minute, timezone=tz),
        id="narrative_intraday",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,
        coalesce=True,
    )
    log.info("Scheduled Narrative: %s ET (Intraday)", NARRATIVE_SCHEDULE["intraday"])

    # 3. Daily EOD Narrative
    close_hour, close_minute = _parse_time(NARRATIVE_SCHEDULE["close"])
    scheduler.add_job(
        lambda: _run_narrative_chain([
            (["python", "-m", "scripts.trader.daily_eod_update", "--session", "eod", *ticker_args], "EOD Update"),
            (["python", "-m", "scripts.trader.daily_narrative", "--session", "eod", *ticker_args], "EOD Narrative"),
            (["python", "-m", "scripts.trader.trader_narrative", "--mode", "close", "--no-discord", *ticker_args], "Trader Narrative Close"),
        ]),
        trigger=CronTrigger(day_of_week='mon-fri', hour=close_hour, minute=close_minute, timezone=tz),
        id="narrative_eod",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,
        coalesce=True,
    )
    log.info("Scheduled Narrative: %s ET (EOD)", NARRATIVE_SCHEDULE["close"])

    # 4. Weekly Briefing
    weekly_hour, weekly_minute = _parse_time(WEEKLY_NARRATIVE_TIME)
    scheduler.add_job(
        lambda: _run_narrative_chain([
            (["python", "-m", "scripts.trader.weekly_briefing", *ticker_args], "Weekly Update"),
            (["python", "-m", "scripts.trader.weekly_narrative"], "Weekly Narrative"),
        ]),
        trigger=CronTrigger(day_of_week='fri', hour=weekly_hour, minute=weekly_minute, timezone=tz),
        id="narrative_weekly",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,
        coalesce=True,
    )
    log.info("Scheduled Narrative: %s ET (Weekly, Friday)", WEEKLY_NARRATIVE_TIME)

    # 5. Daily Derived Data Refresh (17:10 ET, after market close)
    scheduler.add_job(
        lambda: _run_subprocess(
            ["python", "-m", "scripts.maintenance.refresh_derived_data"],
            "Derived Data Refresh"
        ) if _is_trading_day() else None,
        trigger=CronTrigger(day_of_week='mon-fri', hour=17, minute=10, timezone=tz),
        id="derived_data_refresh",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,
        coalesce=True,
    )
    log.info("Scheduled Derived Data Refresh: 17:10 ET (Mon-Fri, after close)")

    # 6. Multi-Expiry TOS Expected Moves Extraction (16:14 ET Daily Mon-Fri)
    scheduler.add_job(
        lambda: _run_subprocess(
            ["python", "-m", "scripts.market_data.extract_all_expiries_em"],
            "Multi-Expiry TOS Expected Moves"
        ) if _is_trading_day() else None,
        trigger=CronTrigger(day_of_week='mon-fri', hour=16, minute=14, timezone=tz),
        id="daily_multi_expiry_tos_em",
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,
        coalesce=True,
    )
    log.info("Scheduled Multi-Expiry TOS EM: 16:14 ET (Mon-Fri)")


    log.info("APScheduler started (timezone=%s). Press Ctrl-C to stop.", SCHEDULE_TIMEZONE)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dealer Levels Pipeline — pulls Schwab options data, calculates "
            "institutional GEX levels, and pushes results to Discord and disk."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--schedule",
        action="store_true",
        help=(
            "Run on the configured schedule (08:30 and 11:00 ET on trading "
            "days). Blocks until Ctrl-C."
        ),
    )
    mode.add_argument(
        "--loop",
        action="store_true",
        help=(
            "Run continuously with a 2-tier priority scanner: "
            "Tier-1 (SPX, SPY, QQQ) every 60s; Tier-2 every 10 min. "
            "Blocks until Ctrl-C."
        ),
    )
    parser.add_argument(
        "--label",
        metavar="LABEL",
        default="",
        help="Override the run label (default: current time).",
    )
    parser.add_argument(
        "--full-discord",
        action="store_true",
        help="Send Coach's Briefing and embeds for ALL active tickers.",
    )
    parser.add_argument(
        "--discord",
        action="store_true",
        help="Enable Discord webhook updates for this run (disabled by default).",
    )
    parser.add_argument(
        "--discord-key",
        metavar="KEY",
        default="",
        help="Override discord_webhooks.json key for dealer-level updates (for example: test_channel).",
    )
    parser.add_argument(
        "--no-discord",
        action="store_true",
        help="Force-disable Discord webhook updates for this run.",
    )
    parser.add_argument(
        "--tickers",
        metavar="TICKER,TICKER",
        help="Comma-separated list of tickers to process (overrides ACTIVE_TICKERS).",
    )
    parser.add_argument(
        "--macro",
        action="store_true",
        help="Run the Weekly Macro HTF pipeline instead of the intraday GEX pipeline.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refresh data (ignore cache) in macro mode.",
    )
    parser.add_argument(
        "--narratives-only",
        action="store_true",
        help="Run only the scheduled Trader Narrative & Briefing tasks without scheduling options pipeline runs.",
    )
    parser.add_argument(
        "--versioned",
        action="store_true",
        help="Write timestamped versioned file snapshots.",
    )
    return parser


def main() -> None:
    import multiprocessing
    multiprocessing.freeze_support()
    _setup_logging()
    args = _build_parser().parse_args()
    if args.discord and args.no_discord:
        log.critical("Choose either --discord or --no-discord, not both.")
        sys.exit(2)

    if args.discord or args.full_discord:
        enable_discord = True
    elif args.no_discord:
        enable_discord = False
    else:
        enable_discord = ENABLE_DISCORD_UPDATES

    # Parse tickers if provided
    tickers = None
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]

    if args.macro:
        from .macro_pipeline import run_macro_pipeline
        # If no tickers provided for macro, use ACTIVE_TICKERS or a subset?
        # Usually macro is run on index family. Let's use provided tickers or ACTIVE_TICKERS.
        macro_tickers = tickers if tickers else ACTIVE_TICKERS
        run_macro_pipeline(macro_tickers, force_refresh=args.force, versioned=args.versioned)
    elif args.schedule:
        run_scheduled(enable_discord=enable_discord, narratives_only=args.narratives_only)
    elif args.loop:
        run_loop(enable_discord=enable_discord)
    else:
        run_pipeline(
            tickers=tickers,
            run_label=args.label,
            enable_discord=enable_discord,
            full_discord=args.full_discord,
            discord_target_key=(args.discord_key or None),
            versioned=args.versioned,
        )


if __name__ == "__main__":
    main()