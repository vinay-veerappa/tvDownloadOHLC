"""
run_options_levels.py
=====================
Main entry point for the automated Dealer Levels pipeline.

This script orchestrates:
  1. Authenticated Schwab API data fetch (options chains + futures quotes)
  2. GEX / Expected-Move / Wall calculations for SPX and NDX
  3. Cash-to-futures basis translation (SPX→ES, NDX→NQ)
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
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import (
    DTE_TARGETS,
    ENABLE_DISCORD_UPDATES,
    ETF_FALLBACK,
    INDEX_TO_FUTURES,
    LOG_FILE,
    MIN_NONZERO_OI_CONTRACTS,
    PRIMARY_INDEX_TICKERS,
    REPO_ROOT,
    SCHEDULE_TIMES,
    SCHEDULE_TIMEZONE,
    SECRETS_PATH,
    TEST_OUTPUT_TICKERS,
    TOKEN_PATH,
)
from .discord_notifier import send_discord_update, send_regime_change_alert
from .file_writer import write_levels
from .futures_translator import translate_to_futures
from .gex_calculator import (
    DealerLevels,
    calculate_dealer_levels,
    calculate_price_metrics,
    rescale_levels_to_target_spot,
)
from .options_fetcher import create_client, fetch_futures_quote, fetch_option_chain_data
from .state_tracker import (
    build_current_state,
    detect_changes,
    format_change_alert,
    load_previous_state,
    save_current_state,
)

log = logging.getLogger(__name__)


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
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(run_label: str = "", enable_discord: bool = ENABLE_DISCORD_UPDATES) -> None:
    """
    Execute one complete fetch → calculate → output cycle.

    Parameters
    ----------
    run_label : Short human-readable label embedded in all outputs.
                Auto-generated from current Eastern time when empty.
    """
    _setup_logging()

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
    cash_levels_by_ticker: dict[str, DealerLevels] = {}

    # --- Process each index / futures pair ----------------------------------
    for ticker in PRIMARY_INDEX_TICKERS:
        futures_sym = INDEX_TO_FUTURES.get(ticker)
        if futures_sym is None:
            log.warning("No futures mapping for %s — skipping.", ticker)
            continue

        log.info("─── Processing: %s → %s ───", ticker, futures_sym)

        try:
            # 1. Fetch primary index chain (0DTE + 1DTE)
            primary_chain = fetch_option_chain_data(client, ticker, DTE_TARGETS)
            chain = primary_chain
            target_cash_spot = primary_chain.spot_price
            source_ticker = ticker
            direct_price_metrics = None

            # 1b. ETF fallback if index chain is empty or has unusable OI profile
            if (not chain.calls and not chain.puts) or (not _chain_has_actionable_oi(chain)):
                if primary_chain.calls and primary_chain.puts:
                    direct_price_metrics = calculate_price_metrics(primary_chain)
                fallback = ETF_FALLBACK.get(ticker)
                if fallback:
                    log.warning(
                        "%s chain lacks actionable OI/contracts — falling back to %s.",
                        ticker,
                        fallback,
                    )
                    chain = fetch_option_chain_data(client, fallback, DTE_TARGETS)
                    source_ticker = fallback
                else:
                    log.error("No fallback available for %s — skipping.", ticker)
                    continue

            # 2. Fetch front-month futures quote.
            #    NOTE: fetch_futures_quote reads the token file directly for
            #    REST calls, then falls back to yfinance.  It does not use the
            #    schwab client object because the client library doesn't
            #    reliably return futures data.
            fut = fetch_futures_quote(futures_sym)

            # 3. Calculate GEX / walls / EM from the selected source chain
            levels = calculate_dealer_levels(chain, source_ticker)

            # 3b. If fallback source differs from target ticker, rescale levels
            # back into target cash index space before futures translation.
            if source_ticker != ticker and target_cash_spot > 0:
                levels = rescale_levels_to_target_spot(
                    levels,
                    target_ticker=ticker,
                    target_spot=target_cash_spot,
                )
                if direct_price_metrics is not None:
                    levels = replace(
                        levels,
                        **direct_price_metrics,
                    )
                    log.info(
                        "Overlayed direct %s EM/vol metrics onto %s-derived structure.",
                        ticker,
                        source_ticker,
                    )
                log.info(
                    "Rescaled %s-derived levels into %s space (target spot=%.2f).",
                    source_ticker,
                    ticker,
                    target_cash_spot,
                )

            cash_levels_by_ticker[ticker] = levels

            # 4. Translate levels into futures price space
            if fut is None:
                log.warning(
                    "No futures price for %s — skipping futures translation for %s. "
                    "Cash levels will still be written.",
                    futures_sym,
                    ticker,
                )
                # Do NOT append an untranslated DealerLevels to
                # translated_levels — it would crash downstream consumers
                # that expect TranslatedLevels attributes.
                continue
            else:
                tl = translate_to_futures(levels, fut)
                translated_levels.append(tl)

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

    if not translated_levels and not cash_levels_by_ticker:
        log.error("No levels were computed — all outputs skipped.")
        return

    # --- Additional cash-space outputs for Pine testing ---------------------
    for ticker in TEST_OUTPUT_TICKERS:
        if ticker in cash_levels_by_ticker:
            continue
        log.info("─── Processing cash-space test ticker: %s ───", ticker)
        try:
            chain = fetch_option_chain_data(client, ticker, DTE_TARGETS)
            levels = calculate_dealer_levels(chain, ticker)
            cash_levels_by_ticker[ticker] = levels
        except Exception as exc:
            log.error("Cash-space test ticker failed for %s: %s", ticker, exc)

    if "RUT" in cash_levels_by_ticker and "RTY" not in cash_levels_by_ticker:
        cash_levels_by_ticker["RTY"] = replace(cash_levels_by_ticker["RUT"], ticker="RTY")
    if "DJX" in cash_levels_by_ticker and "YM" not in cash_levels_by_ticker:
        djx_levels = cash_levels_by_ticker["DJX"]
        cash_levels_by_ticker["YM"] = rescale_levels_to_target_spot(
            djx_levels,
            target_ticker="YM",
            target_spot=djx_levels.spot * 100.0,
        )

    # --- Persist to disk ----------------------------------------------------
    try:
        write_levels(
            translated_levels,
            run_label,
            cash_levels=list(cash_levels_by_ticker.values()),
        )
    except Exception as exc:
        log.error("File write failed: %s", exc)

    # --- State tracking & regime change detection ---------------------------
    try:
        previous_state = load_previous_state()
        current_state = build_current_state(
            run_label, translated_levels, cash_levels_by_ticker,
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

    # --- Send Discord notification (optional) -------------------------------
    if enable_discord:
        try:
            send_discord_update(
                translated_levels,
                run_label,
                cash_levels=list(cash_levels_by_ticker.values()),
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
        log.info("Discord updates are disabled for this run.")

    log.info("Pipeline complete  |  %s", run_label)


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

        def _job(lbl: str = label) -> None:
            if _is_trading_day():
                run_pipeline(lbl, enable_discord=enable_discord)
            else:
                log.info("Non-trading day — skipping %s run.", lbl)

        scheduler.add_job(
            _job,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            id=f"dealer_levels_{time_str.replace(':', '')}",
            replace_existing=True,
            misfire_grace_time=300,   # allow up to 5-minute delay before skipping
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
    parser.add_argument(
        "--label",
        metavar="LABEL",
        default="",
        help="Override the run label embedded in outputs (default: current time).",
    )
    parser.add_argument(
        "--discord",
        action="store_true",
        help="Enable Discord webhook updates for this run (disabled by default).",
    )
    parser.add_argument(
        "--no-discord",
        action="store_true",
        help="Force-disable Discord webhook updates for this run.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.discord and args.no_discord:
        log.critical("Choose either --discord or --no-discord, not both.")
        sys.exit(2)

    if args.discord:
        enable_discord = True
    elif args.no_discord:
        enable_discord = False
    else:
        enable_discord = ENABLE_DISCORD_UPDATES

    if args.schedule:
        run_scheduled(enable_discord=enable_discord)
    else:
        run_pipeline(run_label=args.label, enable_discord=enable_discord)


if __name__ == "__main__":
    main()