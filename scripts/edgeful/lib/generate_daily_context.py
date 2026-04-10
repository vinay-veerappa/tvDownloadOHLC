#!/usr/bin/env python3
"""
Generate Daily Context for All Phase 1 Symbols — Shared Infrastructure

Phase 1 scope: Futures only (NQ1, ES1, YM1, RTY1, CL1, GC1) with 18:00 ET institutional rollover.

This script generates `data/derived/daily_context_{symbol}.parquet` files for all Phase 1 symbols.

Each file contains one row per trading_date with comprehensive context:
  - VIX regime, ATR, gap classification
  - Prior day levels (PDH, PDL, PD range)
  - Session outcome (direction, PD breaks, range)
  - Economic events and OPEX week flags
  - Streak tracking

Output location: data/derived/daily_context_{symbol}.parquet

These parquet files are then joined by all downstream modules (macro, ranges, etc.)
via (symbol, trading_date) to provide universal filter dimensions.

Usage:
    python scripts/edgeful/lib/generate_daily_context.py                      # All Phase 1 symbols
    python scripts/edgeful/lib/generate_daily_context.py --symbol NQ1         # Single symbol
    python scripts/edgeful/lib/generate_daily_context.py --symbol NQ1 ES1     # Multiple
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import date

import pandas as pd

# Add repo root to path
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

from scripts.edgeful.lib.data_loader import DataLoader
from scripts.edgeful.lib.context import DailyContextBuilder, DailyContext

logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("generate_daily_context")

# Phase 1: Futures only (18:00 ET institutional rollover)
# Non-futures symbols (equities, ETFs, indices) deferred to Phase 3+
ALL_SYMBOLS = [
    "NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1",
]

DERIVED_DIR = repo_root / "data" / "derived"
DERIVED_DIR.mkdir(parents=True, exist_ok=True)


def generate_for_symbol(symbol: str, loader: DataLoader, verify: int = 0) -> bool:
    """
    Generate daily_context.parquet for a single symbol.
    
    Args:
        symbol: Ticker
        loader: DataLoader instance
        verify: If > 0, spot-check N random days against TradingView (future work)
    
    Returns:
        True if successful, False otherwise
    """
    output_path = DERIVED_DIR / f"daily_context_{symbol}.parquet"
    logger.info(f"Generating {symbol}...")
    
    try:
        builder = DailyContextBuilder(loader)
        ctx_df = builder.compute_for_symbol(symbol)
        
        if ctx_df.empty:
            logger.warning(f"  No data generated for {symbol}")
            return False
        
        # Convert dataclass dict columns to proper types
        # (pandas from_dict doesn't handle some complex types well)
        ctx_df.to_parquet(output_path, index=False)
        logger.info(f"  ✓ {symbol}: {len(ctx_df)} trading days → {output_path.name}")
        
        # Summary stats
        if "vix_regime" in ctx_df.columns:
            vix_dist = ctx_df["vix_regime"].value_counts()
            logger.debug(f"    VIX regimes: {dict(vix_dist)}")
        
        if "event_type" in ctx_df.columns:
            event_days = ctx_df["is_event_day"].sum()
            logger.debug(f"    Event days: {event_days} / {len(ctx_df)}")
        
        return True
    
    except Exception as e:
        logger.error(f"  Failed to generate {symbol}: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate Daily Context for all symbols (Phase 1)"
    )
    parser.add_argument(
        "--symbol", nargs="+", default=None,
        help="Symbols to generate (default: all)"
    )
    parser.add_argument(
        "--verify", type=int, default=0,
        help="Spot-check N random days per symbol (future work)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate even if output exists"
    )
    args = parser.parse_args()
    
    symbols = args.symbol or ALL_SYMBOLS
    loader = DataLoader()
    
    logger.info(f"Generating Daily Context for {len(symbols)} Phase 1 symbols...")
    logger.debug(f"Output directory: {DERIVED_DIR}")
    logger.debug("Phase 1 scope: Futures only (18:00 ET institutional rollover)")
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for symbol in sorted(symbols):
        output_path = DERIVED_DIR / f"daily_context_{symbol}.parquet"
        
        # Skip if already exists (unless --force)
        if output_path.exists() and not args.force:
            logger.info(f"  {symbol}: already exists (use --force to regenerate)")
            skip_count += 1
            continue
        
        # Skip non-existing data
        try:
            test_df = loader.load_1m(symbol)
            if test_df.empty:
                logger.info(f"  {symbol}: no data available")
                skip_count += 1
                continue
        except Exception as e:
            logger.info(f"  {symbol}: no data available ({e})")
            skip_count += 1
            continue
        
        if generate_for_symbol(symbol, loader, args.verify):
            success_count += 1
        else:
            fail_count += 1
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Summary: {success_count} success, {fail_count} failed, {skip_count} skipped")
    logger.info(f"Generated files saved to: {DERIVED_DIR}")
    logger.info(f"\nNext steps:")
    logger.info(f"  1. Verify output: ls -lh {DERIVED_DIR}/daily_context_*.parquet")
    logger.info(f"  2. Spot-check a few files in DuckDB")
    logger.info(f"  3. Join to macro_records for Phase 2")
    
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
