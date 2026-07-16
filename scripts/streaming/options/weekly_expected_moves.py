"""
weekly_expected_moves.py
========================
Reads pre-calculated Expected Move levels from ``unified_levels.json``
(produced by the pipeline using ``gex_calculator.py``'s TOS time-scaling
model) and formats them for Pine Script consumption and console display.

All EM values come from the single TOS-calibrated source of truth
(``calculate_tos_expected_move``). This script does NOT compute EM
independently — it reads the ``EM HI`` / ``EM LO`` / ``EM85 HI`` /
``EM85 LO`` tokens that the pipeline already wrote into
``unified_levels.json``.

For the weekly (Friday expiry) scope, it also reads
``weekly_em_scope.json`` which captures the Friday EOD EM snapshot.

Usage::

    python -m scripts.streaming.options.weekly_expected_moves
    python -m scripts.streaming.options.weekly_expected_moves --ticker SPY
    python -m scripts.streaming.options.weekly_expected_moves --pinefile
"""
import logging
import argparse
import json
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.streaming.options.config import (
    ACTIVE_TICKERS,
    INDEX_TO_FUTURES,
    EXPECTED_MOVE_TXT,
    UNIFIED_LEVELS_JSON,
    NY_SESSION_ROLLOVER_TIME,
    REPO_ROOT,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

WEEKLY_SCOPE_JSON: Path = REPO_ROOT / "data" / "options" / "weekly_em_scope.json"


def _today_ny() -> date:
    """Logical 'today' in NY timezone (rolls at 16:15 ET)."""
    tz = ZoneInfo("America/New_York")
    now_dt = datetime.now(tz)
    if now_dt.time() >= NY_SESSION_ROLLOVER_TIME:
        return now_dt.date() + timedelta(days=1)
    return now_dt.date()


def _load_unified_levels() -> dict:
    """Load unified_levels.json and return the raw dict."""
    if not UNIFIED_LEVELS_JSON.exists():
        log.warning(f"unified_levels.json not found at {UNIFIED_LEVELS_JSON}")
        return {}
    try:
        return json.loads(UNIFIED_LEVELS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"Failed to read unified_levels.json: {e}")
        return {}


def _load_weekly_scope() -> dict:
    """Load weekly_em_scope.json (Friday EOD captures)."""
    if not WEEKLY_SCOPE_JSON.exists():
        return {}
    try:
        return json.loads(WEEKLY_SCOPE_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_em_tokens(ticker_entry: dict) -> list[dict]:
    """Extract EM HI / EM LO / EM85 HI / EM85 LO tokens from a unified_levels ticker entry.

    Returns list of dicts: {strike, label, dte, raw}
    """
    tokens = ticker_entry.get("tokens", [])
    em_tokens = []
    for tok in tokens:
        label = tok.get("label", "")
        if label.startswith("EM ") or label.startswith("EM85 "):
            dte_match = re.search(r"(\d+)d", label)
            dte = int(dte_match.group(1)) if dte_match else 0
            em_tokens.append({
                "strike": tok.get("strike", 0.0),
                "label": label,
                "dte": dte,
                "raw": tok.get("raw", ""),
            })
    return em_tokens


def _extract_meta_price(ticker_entry: dict) -> float | None:
    """Extract the OGT (opening gap target) or spot from META tokens."""
    tokens = ticker_entry.get("tokens", [])
    for tok in tokens:
        label = tok.get("label", "")
        if label.startswith("META_OGT_"):
            try:
                return float(tok.get("strike", 0.0))
            except Exception:
                pass
    return None


def read_em_from_unified_levels(ticker: str) -> list[dict]:
    """Read EM tokens from unified_levels.json for the given ticker.

    Returns a list of dicts with keys: strike, label, dte, raw.
    """
    data = _load_unified_levels()
    tickers = data.get("tickers", [])

    entry = None
    for t in tickers:
        if t.get("ticker") == ticker:
            entry = t
            break

    if entry is None:
        log.warning(f"No entry found for {ticker} in unified_levels.json")
        return []

    return _extract_em_tokens(entry)


def read_weekly_scope_em(ticker: str) -> dict | None:
    """Read Friday EOD weekly scope EM from weekly_em_scope.json.

    Returns dict with keys: expiry, em_upper, em_lower, straddle_85_upper,
    straddle_85_lower, captured_on, source.
    """
    scope = _load_weekly_scope()
    return scope.get(ticker)


def fetch_weekly_expected_moves():
    """Main entry point — reads unified_levels.json + weekly_em_scope.json."""
    logical_today = _today_ny()
    days_to_friday = (4 - logical_today.weekday()) % 7
    target_friday = logical_today + timedelta(days=days_to_friday)

    log.info("=" * 60)
    log.info("WEEKLY EXPECTED MOVES (from unified_levels.json — TOS time-scaling model)")
    log.info(f"Logical Today:   {logical_today.strftime('%A, %b %d')}")
    log.info(f"Target Friday:   {target_friday.strftime('%A, %b %d')}")
    log.info("=" * 60 + "\n")

    parser = argparse.ArgumentParser(description="Weekly Expected Moves (read from unified levels)")
    parser.add_argument("--ticker", type=str, help="Specify a single ticker to process")
    parser.add_argument("--pinefile", action="store_true", help="Write Pine Script EM summary to expected_moves.txt")
    args, unknown = parser.parse_known_args()

    tickers = [args.ticker] if args.ticker else ACTIVE_TICKERS
    pine_lines = []
    unified = _load_unified_levels()
    weekly_scope = _load_weekly_scope()

    for cash_sym in tickers:
        # Skip raw futures tickers — EM is on the cash/index side
        if cash_sym.startswith("/"):
            continue

        # --- Read from unified_levels.json ---
        entry = None
        for t in unified.get("tickers", []):
            if t.get("ticker") == cash_sym:
                entry = t
                break

        if entry is None:
            # SPX/NDX are not always in unified_levels.json (only their ETF
            # proxies are). But they may have a weekly scope entry — check that
            # before skipping entirely.
            scope = weekly_scope.get(cash_sym)
            if scope:
                log.info(f"[{cash_sym}] Not in unified_levels.json — using weekly_em_scope.json only")
                entry = {"tokens": []}
                em_tokens = []
                spot = None
            else:
                log.warning(f"[{cash_sym}] No entry in unified_levels.json or weekly_em_scope.json — skipping")
                continue
        else:
            em_tokens = _extract_em_tokens(entry)
            spot = _extract_meta_price(entry)
            scope = weekly_scope.get(cash_sym)

        # --- Print intraday EM tokens (from unified_levels.json) ---
        if em_tokens:
            log.info(f"[{cash_sym}] Intraday EM tokens (from unified_levels.json):")
            for em in em_tokens:
                log.info(f"  \u21b3 {em['raw']}")
        else:
            log.info(f"[{cash_sym}] No intraday EM tokens in unified_levels.json")

        # --- Print weekly scope EM (from weekly_em_scope.json) ---
        if scope:
            em_upper = scope.get("em_upper", 0.0)
            em_lower = scope.get("em_lower", 0.0)
            em_val = (em_upper - em_lower) / 2.0
            straddle_85_upper = scope.get("straddle_85_upper", 0.0)
            straddle_85_lower = scope.get("straddle_85_lower", 0.0)
            expiry = scope.get("expiry", "N/A")
            captured = scope.get("captured_on", "N/A")
            center = (em_upper + em_lower) / 2.0

            log.info(f"\n  Weekly Scope (Friday EOD capture, expiry {expiry}, captured {captured}):")
            log.info(f"    EM \u00b1{em_val:.2f} | Range: {em_lower:.2f} \u2194 {em_upper:.2f} (center: {center:.2f})")
            log.info(f"    EM85 Range: {straddle_85_lower:.2f} \u2194 {straddle_85_upper:.2f}")

            # Futures translation
            fut_sym = INDEX_TO_FUTURES.get(cash_sym)
            fut_price = None
            if fut_sym:
                fut_clean = fut_sym.replace("/", "")
                for t in unified.get("tickers", []):
                    if t.get("ticker") == fut_clean:
                        fut_price = _extract_meta_price(t)
                        break

            if fut_sym and fut_price and spot and spot > 0:
                ratio = fut_price / spot
                fut_em = em_val * ratio
                fut_upper = fut_price + fut_em
                fut_lower = fut_price - fut_em
                trans_mode = "Multiplicative" if abs(ratio - 1.0) > 0.02 else "Additive"
                log.info(f"\n  [{fut_sym}] Translated Futures | Spot: {fut_price:,.2f} ({trans_mode} from {cash_sym})")
                log.info(f"    EM \u00b1{fut_em:.2f} | Range: {fut_lower:.2f} \u2194 {fut_upper:.2f}")

                try:
                    exp_date = date.fromisoformat(expiry)
                    day_name = exp_date.strftime("%a")
                except Exception:
                    day_name = "Fri"
                clean_fut = fut_sym.replace("/", "")
                pine_lines.append(f"{clean_fut}_EM={fut_em:.2f}:{day_name}")

            # Pine Script for cash/ETF
            try:
                exp_date = date.fromisoformat(expiry)
                day_name = exp_date.strftime("%a")
            except Exception:
                day_name = "Fri"
            clean_ticker = cash_sym.replace("$", "").replace("/", "")
            pine_lines.append(f"{clean_ticker}_EM={em_val:.2f}:{day_name}")

        log.info("-" * 60 + "\n")

    # Write Pine Script EM summary to file if requested
    if args.pinefile and pine_lines:
        with open(EXPECTED_MOVE_TXT, "w", encoding="utf-8") as f:
            for line in pine_lines:
                f.write(line + "\n")
        log.info(f"\nPine Script EM summary written to: {EXPECTED_MOVE_TXT}\n")


if __name__ == "__main__":
    fetch_weekly_expected_moves()