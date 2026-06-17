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

import argparse
import logging
import sys
import json
import time
from dataclasses import replace
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

from .config import (
    ACTIVE_TICKERS,
    DTE_TARGETS,
    ENABLE_DISCORD_UPDATES,
    ETF_FALLBACK,
    INDEX_TO_FUTURES,
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
    rescale_levels_to_target_spot,
)
from .level_scorer import score_levels, ScoredLevels
from .options_fetcher import create_client, fetch_futures_quote, fetch_option_chain_data
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
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )
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


def _load_weekly_scope_cache(path: Path = WEEKLY_SCOPE_CACHE_JSON) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        log.warning("Failed to load weekly scope cache %s: %s", path.name, exc)
        return {}


def _save_weekly_scope_cache(cache: dict[str, dict[str, Any]], path: Path = WEEKLY_SCOPE_CACHE_JSON) -> None:
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
    enable_discord: bool = ENABLE_DISCORD_UPDATES,
    full_discord: bool = False,
    discord_target_key: str | None = None,
    versioned: bool = False,
    reset_anchors: bool = False,
    snapshot_suffix: str | None = None,
    intraday_only: bool = False,
) -> None:
    """
    Execute one complete fetch -> calculate -> output cycle.

    Parameters
    ----------
    run_label : Short human-readable label embedded in all outputs.
                Auto-generated from current Eastern time when empty.
    """
    _setup_logging()
    
    dte_targets = DTE_TARGETS if intraday_only else PIPELINE_DTE_TARGETS

    if not run_label:
        tz = ZoneInfo(SCHEDULE_TIMEZONE)
        run_label = datetime.now(tz).strftime("%Y-%m-%d %H:%M ET")

    log.info("=" * 60)
    log.info("Dealer Levels pipeline starting  |  %s", run_label)
    log.info("=" * 60)

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

    # --- Load existing anchors ----------------------------------------------
    all_anchors = load_basis_anchors()
    new_anchors_captured = False
    weekly_scope_cache = _load_weekly_scope_cache()
    weekly_scope_cache_updated = False
    now_ny = datetime.now(ZoneInfo(SCHEDULE_TIMEZONE))
    today_ny = now_ny.date()
    is_eod_run = _is_eod_snapshot(run_label, now_ny)


    # --- Process each ticker --------------------------------------------------
    target_tickers = tickers if tickers is not None else ACTIVE_TICKERS
    for ticker in target_tickers:
        futures_sym = INDEX_TO_FUTURES.get(ticker)
        mapping_str = f"-> {futures_sym}" if futures_sym else "(Cash only)"
        log.info("--- Processing: %s %s ---", ticker, mapping_str)

        try:
            # 1. Fetch macro-scale option chain (covers near-term density + macro targets)
            full_chain = fetch_option_chain_data(client, ticker, dte_targets)
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
                    chain = fetch_option_chain_data(client, fallback, dte_targets)
                    source_ticker = fallback
                else:
                    log.error("No fallback available for %s — skipping.", ticker)
                    continue

            # 2. Fetch front-month futures quote
            fut = fetch_futures_quote(futures_sym)

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
                    log.info("Using Persistent Basis for %s: %.2f (Ratio: %.4f)", 
                             ticker, anchor_basis, anchor_ratio)
                else:
                    # Attempt to capture new anchor
                    # Prefer open prices (Open Price Hack)
                    spot_open = full_chain.spot_open
                    fut_open = fut.open_price
                    
                    if spot_open and fut_open:
                        anchor_basis = fut_open - spot_open
                        anchor_ratio = fut_open / spot_open if spot_open else 1.0
                        log.info("Captured NEW Opening Basis for %s: %.2f (Ratio: %.4f) [Source: Open Prices]", 
                                 ticker, anchor_basis, anchor_ratio)
                        all_anchors[ticker] = {"basis": anchor_basis, "ratio": anchor_ratio}
                        new_anchors_captured = True
                    elif ticker_anchor:
                        # Fallback to existing if open prices missing
                        anchor_basis = ticker_anchor.get("basis")
                        anchor_ratio = ticker_anchor.get("ratio")
                        log.warning("Could not capture new open prices for %s. Retaining existing anchor.", ticker)
                    else:
                        # Final fallback: use current prices as the anchor if no open price yet
                        anchor_basis = fut.price - full_chain.spot_price
                        anchor_ratio = fut.price / full_chain.spot_price if full_chain.spot_price else 1.0
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
            log.info("Calculating [%s] and [MACRO] levels structure...", ticker)
            levels_intraday = calculate_dealer_levels(
                intraday_chain,
                source_ticker,
                min_oi_floor=profile.min_oi_floor,
                wall_scope="FRONT_WEEK_WEIGHTED",
                wall_dte_range=INTRADAY_VIEW.dte_range,
            )
            levels_macro = calculate_dealer_levels(
                chain,
                source_ticker,
                min_oi_floor=profile.min_oi_floor,
                wall_scope="ALL_EXPIRIES_WEIGHTED",
                wall_dte_range=MACRO_VIEW.dte_range,
            )

            # 3b. If fallback source differs from target ticker, rescale levels
            # back into target cash index space before futures translation.
            if source_ticker != ticker and target_cash_spot > 0:
                levels_intraday = rescale_levels_to_target_spot(
                    levels_intraday,
                    target_ticker=ticker,
                    target_spot=target_cash_spot,
                )
                levels_macro = rescale_levels_to_target_spot(
                    levels_macro,
                    target_ticker=ticker,
                    target_spot=target_cash_spot,
                )
                if direct_price_metrics is not None:
                    levels_intraday = replace(levels_intraday, **direct_price_metrics)
                    levels_macro = replace(levels_macro, **direct_price_metrics)

                log.info("Rescaled %s-derived levels into %s space.", source_ticker, ticker)

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
                        log.info(
                            "Captured Friday weekly scope for %s -> %s [%.2f, %.2f]",
                            ticker,
                            weekly_scope_record["expiry"],
                            weekly_scope_record["em_lower"],
                            weekly_scope_record["em_upper"],
                        )

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
                
                translated_levels.append(tl_intraday)
                translated_macro_levels.append(tl_macro)

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
                write_scored_levels_txt(
                    ticker,
                    scored_intraday,
                    metadata_levels=levels_intraday,
                    versioned=versioned,
                    snapshot_suffix=snapshot_suffix,
                )
                write_scored_levels_txt(
                    ticker,
                    scored_macro,
                    metadata_levels=levels_macro,
                    path=SCORED_MACRO_LEVELS_TXT,
                    versioned=versioned,
                    snapshot_suffix=snapshot_suffix,
                )

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

    if not translated_levels and not cash_levels_by_ticker:
        log.error("No levels were computed — all outputs skipped.")
        return

    # --- Persist to disk ----------------------------------------------------
    try:
        from .config import DATA_DIR, DAILY_LEVELS_JSON, DAILY_LEVELS_TXT, INTRADAY_LEVELS_JSON, MACRO_LEVELS_JSON
        
        # 1. Intraday View (Legacy paths + Intraday JSON)
        write_levels(
            translated_levels,
            run_label,
            cash_levels=list(cash_levels_by_ticker.values()),
            scored_levels=list(scored_intraday_by_ticker.values()),
            json_path=DAILY_LEVELS_JSON, # Legacy
            versioned=versioned,
            snapshot_suffix=snapshot_suffix,
        )
        write_levels(
            translated_levels,
            run_label,
            cash_levels=list(cash_levels_by_ticker.values()),
            scored_levels=list(scored_intraday_by_ticker.values()),
            json_path=INTRADAY_LEVELS_JSON, # Explicit
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
            txt_path=DATA_DIR / "macro_levels.txt",
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
    else:
        if not enable_discord:
            log.info("Discord updates are disabled for this run.")
        else:
            log.info("Discord updates skipped (outside allowed windows: 09:30, 16:15 ET).")

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

    # --- Pulse Scheduling ---
    # We want to force a FULL versioned run at exactly these times.
    # We now pull these from config.SCHEDULE_TIMES
    snapshot_targets = SCHEDULE_TIMES # ["08:30", "09:30", "10:00", ...]
    last_pulse_date: dict[str, str] = {} # "08:30" -> "2026-05-06"

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
                    intraday_only=is_intraday_only
                )
                # Successful run! Update timestamps
                if due_tier1 or is_pulse_cycle:
                    tier1_last_run = now
            except Exception as exc:
                log.error("Pipeline cycle failed: %s", exc)
            finally:
                _cfg.ACTIVE_TICKERS = original

        # Sleep for a short beat to check for manual triggers frequently
        time.sleep(LOOP_BEAT_SECONDS)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def _is_trading_day(tz_name: str = SCHEDULE_TIMEZONE) -> bool:
    """
    Return True when today is a Monday–Friday trading day.
    Market holidays are not accounted for; add a trading-calendar library
    (e.g. pandas-market-calendars) for full holiday awareness.
    """
    return datetime.now(ZoneInfo(tz_name)).weekday() < 5


def run_scheduled(enable_discord: bool = ENABLE_DISCORD_UPDATES) -> None:
    """
    Block and run the pipeline at the configured schedule times (APScheduler).
    The process runs on weekdays only; weekends are silently skipped.

    Raises SystemExit when APScheduler is not installed.
    """
    _setup_logging()

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
    scheduler = BlockingScheduler(timezone=tz)  # type: ignore[call-arg]

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
                run_pipeline(lbl, enable_discord=enable_discord, versioned=is_pulse, reset_anchors=do_reset, snapshot_suffix=suffix)
            else:
                log.info("Non-trading day — skipping %s run.", lbl)

        scheduler.add_job(
            _job,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            id=f"dealer_levels_{time_str.replace(':', '')}",
            replace_existing=True,
            misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME,   # allow for delayed execution before skipping
        )
        log.info("Scheduled: %s ET", time_str)

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
        "--versioned",
        action="store_true",
        help="Write timestamped versioned file snapshots.",
    )
    return parser


def main() -> None:
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
        run_scheduled(enable_discord=enable_discord)
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