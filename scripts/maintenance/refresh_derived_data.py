"""refresh_derived_data.py — daily derived data refresh + gap detection.

Runs the ICT features computation pipeline to keep derived parquets fresh.
Designed to be called by the scheduler daily (17:10 ET after market close)
or on-demand to bridge data gaps.

What it does:
  1. Checks data freshness (last bar timestamp in live storage)
  2. If stale (>2 hours during trading hours), alerts + attempts backfill
  3. Runs compute_ict_features for all symbols (incremental)
  4. Logs results + alerts on failures

Usage:
    # Daily refresh (all symbols, incremental)
    python -m scripts.maintenance.refresh_derived_data

    # Specific symbols
    python -m scripts.maintenance.refresh_derived_data --symbols ES1,NQ1

    # Full rebuild (from scratch)
    python -m scripts.maintenance.refresh_derived_data --full-regen

    # Check freshness only (no refresh)
    python -m scripts.maintenance.refresh_derived_data --check-only
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO))

from zoneinfo import ZoneInfo
ET_TZ = ZoneInfo("America/New_York")

# Symbols to refresh by default
DEFAULT_SYMBOLS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

# Staleness thresholds
STALE_HOURS_TRADING = 2  # during trading hours, data should be <2h old
STALE_HOURS_WEEKEND = 72  # weekends are fine

# Live storage paths
LIVE_DIR = _REPO / "data" / "live"
DERIVED_DIR = _REPO / "data" / "derived" / "ICT"

# Symbol -> live storage file mapping
SYMBOL_MAP = {
    "ES1": "live_storage_-ES.parquet",
    "NQ1": "live_storage_-NQ.parquet",
    "YM1": "live_storage_-YM.parquet",
    "RTY1": "live_storage_-RTY.parquet",
    "CL1": "live_storage_-CL.parquet",
    "GC1": "live_storage_-GC.parquet",
}


def check_data_freshness(symbol: str) -> dict:
    """Check if the live storage data for a symbol is fresh.

    Returns dict with:
        symbol, last_bar, age_hours, is_stale, reason
    """
    filename = SYMBOL_MAP.get(symbol, f"live_storage_-{symbol.replace('1','')}.parquet")
    path = LIVE_DIR / filename

    if not path.exists():
        return {"symbol": symbol, "last_bar": None, "age_hours": None,
                "is_stale": True, "reason": "live storage file not found"}

    try:
        df = pd.read_parquet(path)
        if df.empty:
            return {"symbol": symbol, "last_bar": None, "age_hours": None,
                    "is_stale": True, "reason": "empty parquet"}

        # Get last timestamp
        if "timestamp" in df.columns:
            ts_series = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            last_ts = ts_series.max()
        elif df.index.name and "time" in str(df.index.name).lower():
            last_ts = df.index.max()
        else:
            last_ts = pd.to_datetime(df.index[-1], utc=True, errors="coerce")

        if last_ts.tz is None:
            last_ts = last_ts.tz_localize("UTC")

        now_utc = pd.Timestamp.now(tz="UTC")
        age = now_utc - last_ts
        age_hours = age.total_seconds() / 3600

        now_et = datetime.now(ET_TZ)
        is_weekend = now_et.weekday() >= 5
        is_after_hours = now_et.hour >= 16 or now_et.hour < 18

        if is_weekend:
            threshold = STALE_HOURS_WEEKEND
        elif is_after_hours:
            threshold = STALE_HOURS_WEEKEND  # after close, data won't update until 18:00
        else:
            threshold = STALE_HOURS_TRADING

        is_stale = age_hours > threshold

        return {
            "symbol": symbol,
            "last_bar": str(last_ts),
            "age_hours": round(age_hours, 1),
            "is_stale": is_stale,
            "reason": f"stale ({age_hours:.1f}h > {threshold}h)" if is_stale else "fresh",
        }
    except Exception as e:
        return {"symbol": symbol, "last_bar": None, "age_hours": None,
                "is_stale": True, "reason": f"error: {e}"}


def run_compute_features(symbols: list[str], full_regen: bool = False) -> dict:
    """Run the ICT features computation pipeline.

    Returns dict with results per symbol.
    """
    python_exe = str(_REPO / ".venv" / "Scripts" / "python.exe")
    cmd = [
        python_exe, "-m", "scripts.context.compute_ict_features",
        "--symbols", ",".join(symbols),
    ]
    if full_regen:
        cmd.append("--full-regen")
    else:
        cmd.append("--incremental")

    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd, cwd=str(_REPO), capture_output=True, text=True, timeout=600
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-1000:] if result.stdout else "",
        "stderr": result.stderr[-500:] if result.stderr else "",
    }


def refresh_all(symbols: list[str] | None = None, full_regen: bool = False,
                check_only: bool = False) -> dict:
    """Refresh derived data for all symbols.

    Args:
        symbols: list of symbols (defaults to DEFAULT_SYMBOLS)
        full_regen: if True, rebuild from scratch
        check_only: if True, only check freshness without refreshing

    Returns:
        dict with freshness checks and refresh results
    """
    if symbols is None:
        symbols = DEFAULT_SYMBOLS

    log.info("="*60)
    log.info("DERIVED DATA REFRESH")
    log.info("Symbols: %s", ", ".join(symbols))
    log.info("Mode: %s", "check-only" if check_only else ("full-regen" if full_regen else "incremental"))
    log.info("="*60)

    # Step 1: Check freshness
    freshness = {}
    stale_symbols = []
    for sym in symbols:
        check = check_data_freshness(sym)
        freshness[sym] = check
        status = "STALE" if check["is_stale"] else "FRESH"
        log.info("  %s: %s (%s, age=%sh)", sym, status, check["reason"],
                 check.get("age_hours", "N/A"))
        if check["is_stale"]:
            stale_symbols.append(sym)

    if check_only:
        return {"freshness": freshness, "refresh": None, "stale_symbols": stale_symbols}

    # Step 2: Alert on stale symbols
    if stale_symbols:
        log.warning("STALE SYMBOLS: %s", ", ".join(stale_symbols))
        log.warning("  These symbols have stale live data. Derived data refresh may not help.")
        log.warning("  Consider backfilling from streaming/TV/NT8 first.")

    # Step 3: Run compute pipeline
    log.info("Running compute_ict_features...")
    refresh_result = run_compute_features(symbols, full_regen=full_regen)

    if refresh_result["returncode"] == 0:
        log.info("Compute pipeline: SUCCESS")
    else:
        log.error("Compute pipeline: FAILED (exit %d)", refresh_result["returncode"])
        if refresh_result["stderr"]:
            log.error("  stderr: %s", refresh_result["stderr"][:300])

    # Step 4: Verify derived parquets exist
    derived_files = list(DERIVED_DIR.glob("*.parquet")) if DERIVED_DIR.exists() else []
    log.info("Derived parquets: %d files in %s", len(derived_files), DERIVED_DIR)

    return {
        "freshness": freshness,
        "refresh": refresh_result,
        "stale_symbols": stale_symbols,
        "derived_files": len(derived_files),
        "timestamp": datetime.now(ET_TZ).isoformat(),
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Refresh derived ICT data + gap detection")
    ap.add_argument("--symbols", default=None, help="Comma-separated symbols (default: all)")
    ap.add_argument("--full-regen", action="store_true", help="Rebuild from scratch")
    ap.add_argument("--check-only", action="store_true", help="Check freshness only, no refresh")
    args = ap.parse_args()

    symbols = args.symbols.split(",") if args.symbols else None
    result = refresh_all(symbols=symbols, full_regen=args.full_regen, check_only=args.check_only)

    # Print summary
    print("\n" + "=" * 60)
    print("  DERIVED DATA REFRESH SUMMARY")
    print("=" * 60)
    for sym, check in result["freshness"].items():
        status = "STALE" if check["is_stale"] else "FRESH"
        print(f"  {sym}: {status} (age={check.get('age_hours', 'N/A')}h, {check['reason']})")

    if result.get("refresh"):
        rc = result["refresh"]["returncode"]
        print(f"\n  Compute pipeline: {'SUCCESS' if rc == 0 else 'FAILED'}")

    if result["stale_symbols"]:
        print(f"\n  Stale symbols: {', '.join(result['stale_symbols'])}")
        print("  Consider backfilling live data first.")

    print("=" * 60)


if __name__ == "__main__":
    main()