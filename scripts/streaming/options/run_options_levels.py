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
import json
import time
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

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
    MACRO_VIEW,
    INTRADAY_VIEW,
    get_ticker_profile,
)
from .discord_notifier import send_discord_update, send_regime_change_alert
from .file_writer import write_levels
from .futures_translator import translate_to_futures
from .gex_calculator import (
    DealerLevels,
    calculate_dealer_levels,
    calculate_price_metrics,
    rescale_levels_to_target_spot,
    ScoredLevels,
)
from .options_fetcher import create_client, fetch_futures_quote, fetch_option_chain_data
from .level_scorer import score_levels
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

def run_pipeline(
    tickers: list[str] | None = None,
    run_label: str = "",
    enable_discord: bool = ENABLE_DISCORD_UPDATES,
    full_discord: bool = False,
) -> None:
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
    translated_macro_levels = []
    cash_levels_by_ticker: dict[str, DealerLevels] = {}
    macro_levels_by_ticker: dict[str, DealerLevels] = {}
    scored_intraday_by_ticker: dict[str, ScoredLevels] = {}
    scored_macro_by_ticker: dict[str, ScoredLevels] = {}

    # --- Process each ticker --------------------------------------------------
    target_tickers = tickers if tickers is not None else ACTIVE_TICKERS
    for ticker in target_tickers:
        futures_sym = INDEX_TO_FUTURES.get(ticker)
        mapping_str = f"-> {futures_sym}" if futures_sym else "(Cash only)"
        log.info("--- Processing: %s %s ---", ticker, mapping_str)

        try:
            # 1. Fetch macro-scale option chain (covers 0DTE to 365DTE targets)
            full_chain = fetch_option_chain_data(client, ticker, MACRO_DTE_TARGETS)
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
                    chain = fetch_option_chain_data(client, fallback, MACRO_DTE_TARGETS)
                    source_ticker = fallback
                else:
                    log.error("No fallback available for %s — skipping.", ticker)
                    continue

            # 2. Fetch front-month futures quote
            fut = fetch_futures_quote(futures_sym)

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
            intraday_chain = replace(chain, calls=intraday_calls, puts=intraday_puts)

            # 4. Calculate Dealer Levels for both timeframes
            log.info("Calculating [%s] and [MACRO] levels structure...", ticker)
            levels_intraday = calculate_dealer_levels(intraday_chain, source_ticker)
            levels_macro = calculate_dealer_levels(chain, source_ticker)

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

            cash_levels_by_ticker[ticker] = levels_intraday 
            macro_levels_by_ticker[ticker] = levels_macro

            # 5. Compute ScoredLevels for both views
            profile = get_ticker_profile(ticker)
            
            # Intraday Scoring (filters to ±6% spot, Primary/Secondary/Context)
            scored_intraday = score_levels(levels_intraday, intraday_chain, ticker, profile, INTRADAY_VIEW)
            scored_intraday_by_ticker[ticker] = scored_intraday
            
            # Macro Scoring (filters to ±15% spot, Primary only)
            scored_macro = score_levels(levels_macro, chain, ticker, profile, MACRO_VIEW)
            scored_macro_by_ticker[ticker] = scored_macro

            # 7. Write per-ticker snapshot to DB
            if _is_rth():
                from .interval_writer import write_snapshot
                write_snapshot(levels_intraday, ticker_override=ticker)

            # 6. Translate levels into futures price space
            if futures_sym is None or fut is None:
                log.debug("No futures translation for %s (mapping missing or quote failed).", ticker)
                # We skip appending to translated_levels, but proceed to next steps
                # so cash_levels_by_ticker is already populated and can be used.
            else:
                # Use primary_chain's opening spot (original index) for basis anchors.
                # If we fell back to an ETF (source_ticker != ticker), we should NOT
                # use the ETF's opening price here as that would cause a 10x/40x 
                # scale error in the anchor_ratio.
                translated_levels.append(tl_intraday)
                translated_macro_levels.append(tl_macro)

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
        )
        write_levels(
            translated_levels,
            run_label,
            cash_levels=list(cash_levels_by_ticker.values()),
            scored_levels=list(scored_intraday_by_ticker.values()),
            json_path=INTRADAY_LEVELS_JSON, # Explicit
        )
        
        # 2. Macro View (Macro paths)
        write_levels(
            translated_macro_levels,
            run_label,
            cash_levels=list(macro_levels_by_ticker.values()),
            scored_levels=list(scored_macro_by_ticker.values()),
            json_path=MACRO_LEVELS_JSON,
            txt_path=DATA_DIR / "macro_levels.txt",
        )
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

    # --- Send Discord notification (optional) -------------------------------
    if enable_discord:
        try:
            send_discord_update(
                translated_levels,
                run_label,
                cash_levels=list(cash_levels_by_ticker.values()),
                scored_levels=list(scored_levels_by_ticker.values()),
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
        log.info("Discord updates are disabled for this run.")

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

    while True:
        ny_now = datetime.now(ZoneInfo(SCHEDULE_TIMEZONE))
        now = time.time() # Current timestamp for interval checks
        
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
        due_tier2 = [t for t in tier2_tickers if (now - tier2_last_run.get(t, 0)) >= t2_interval]

        # Tickers to process this cycle: Tier 1 (if due) + Due Tier 2 + Manual Tickers
        active_this_cycle = list(set(due_tier1 + due_tier2 + manual_tickers))

        if active_this_cycle:
            run_label = ny_now.strftime("%Y-%m-%d %H:%M ET")
            log.info("Cycle start — processing %d tickers: %s", len(active_this_cycle), ", ".join(active_this_cycle))

            # Temporarily restrict ACTIVE_TICKERS to our cycle subset
            import scripts.streaming.options.config as _cfg
            original = _cfg.ACTIVE_TICKERS
            _cfg.ACTIVE_TICKERS = active_this_cycle
            try:
                run_pipeline(run_label=run_label, enable_discord=enable_discord)
                # Successful run! Update timestamps
                if due_tier1:
                    tier1_last_run = now
                for t in due_tier2:
                    tier2_last_run[t] = now
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
        run_macro_pipeline(macro_tickers, force_refresh=args.force)
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
        )


if __name__ == "__main__":
    main()