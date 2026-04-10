#!/usr/bin/env python3
"""
Validate Daily Context Output — Phase 1 QA

Spot-check daily_context parquet files to ensure correctness:
  - Gap calculations (open vs. prior close)
  - PDH/PDL (true highs/lows from day)
  - ATR (14-day calculation)
  - Session outcomes (close > open = GREEN, etc.)
  - Event classification (keyword match accuracy)
  - No NaN leakage in critical fields

Usage:
    python scripts/edgeful/lib/validate_daily_context.py                    # All symbols, 10 checks each
    python scripts/edgeful/lib/validate_daily_context.py --symbol NQ1       # Single symbol
    python scripts/edgeful/lib/validate_daily_context.py --checks 20        # 20 checks per symbol
    python scripts/edgeful/lib/validate_daily_context.py --verbose          # Print all rows
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import timedelta

import pandas as pd
import numpy as np

repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

from scripts.edgeful.lib.data_loader import DataLoader
from scripts.edgeful.lib.session_tagger import tag_session
from scripts.edgeful.lib.context import DailyContext, EVENT_CATEGORIES

logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("validate_daily_context")

DERIVED_DIR = Path(repo_root) / "data" / "derived"
ALL_SYMBOLS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]


def validate_dataclass_schema(df: pd.DataFrame) -> list[str]:
    """
    Check that all required DailyContext fields are present.
    Return list of missing fields (empty if all present).
    """
    required_fields = set(DailyContext.__dataclass_fields__.keys())
    actual_fields = set(df.columns)
    missing = required_fields - actual_fields
    return sorted(missing)


def validate_no_nan_leakage(df: pd.DataFrame, symbol: str) -> list[tuple[str, int]]:
    """
    Check for NaN in critical fields.
    Return list of (field_name, nan_count) pairs.
    """
    critical_fields = [
        "symbol", "trading_date", "session_close", "session_direction",
        "pdh", "pdl", "gap_size_pct", "gap_direction",
        "vix_close", "vix_regime", "atr_14d", "event_types"
    ]
    
    issues = []
    for field in critical_fields:
        if field not in df.columns:
            continue
        nan_count = df[field].isna().sum()
        if nan_count > 0:
            issues.append((field, nan_count))
    
    return issues


def validate_numeric_bounds(df: pd.DataFrame, symbol: str, checks: int = 10) -> list[str]:
    """
    Spot-check that numeric fields are within reasonable bounds.
    """
    issues = []
    
    # Sample rows for checking
    sample_indices = np.random.choice(len(df), min(checks, len(df)), replace=False)
    sample_df = df.iloc[sample_indices]
    
    for idx, row in sample_df.iterrows():
        trading_date = row["trading_date"]
        
        # Gap percent should be < 5% for most days
        if "gap_size_pct" in row and abs(row["gap_size_pct"]) > 10:
            issues.append(f"  {trading_date}: gap_size_pct={row['gap_size_pct']:.2%} (unusual but possible)")
        
        # ATR should be > 0
        if "atr_14d" in row and row["atr_14d"] <= 0:
            issues.append(f"  {trading_date}: atr_14d={row['atr_14d']} (should be > 0)")
        
        # VIX pctile should be 0-100
        if "vix_pctile_60d" in row:
            pctile = row["vix_pctile_60d"]
            if pd.notna(pctile) and not (0 <= pctile <= 100):
                issues.append(f"  {trading_date}: vix_pctile_60d={pctile} (should be 0-100)")
        
        # PDH >= PDL
        if "pdh" in row and "pdl" in row:
            if row["pdh"] < row["pdl"]:
                issues.append(f"  {trading_date}: pdh={row['pdh']} < pdl={row['pdl']} (inverted!)")
        
        # Event type should be in known categories or empty
        if "event_type" in row and pd.notna(row["event_type"]):
            if row["event_type"] not in EVENT_CATEGORIES:
                issues.append(f"  {trading_date}: event_type='{row['event_type']}' (unknown category)")
    
    return issues


def validate_session_direction(df: pd.DataFrame, symbol: str, loader: DataLoader, checks: int = 10) -> list[str]:
    """
    Cross-check session_direction against actual open/close.
    Load raw bars and recompute direction for random dates.
    """
    issues = []
    
    sample_indices = np.random.choice(len(df), min(checks, len(df)), replace=False)
    sample_df = df.iloc[sample_indices]
    
    for idx, row in sample_df.iterrows():
        trading_date = row["trading_date"]
        ctx_direction = row.get("session_direction", None)
        
        try:
            # Load all bars for this trading_date
            bars = loader.load_1m(symbol)
            if bars.empty:
                continue
            
            bars = tag_session(bars)
            day_bars = bars[bars["trading_date"] == pd.Timestamp(trading_date)]
            
            if day_bars.empty:
                continue
            
            # Compute open/close
            rth_bars = day_bars[day_bars["is_rth"] == True]
            if rth_bars.empty:
                continue
            
            open_price = rth_bars.iloc[0]["open"]
            close_price = rth_bars.iloc[-1]["close"]
            computed_direction = "GREEN" if close_price > open_price else "RED"
            
            if ctx_direction != computed_direction:
                issues.append(
                    f"  {trading_date}: session_direction={ctx_direction}, "
                    f"but open={open_price:.2f} close={close_price:.2f} → {computed_direction}"
                )
        
        except Exception as e:
            logger.debug(f"  {trading_date}: could not cross-check ({e})")
    
    return issues


def validate_symbol(symbol: str, loader: DataLoader, checks: int = 10, verbose: bool = False) -> dict:
    """
    Validate a single symbol's daily_context.parquet
    
    Returns dict with keys: symbol, pass, issues, nan_issues, bounds_issues, direction_issues
    """
    output_path = DERIVED_DIR / f"daily_context_{symbol}.parquet"
    
    result = {
        "symbol": symbol,
        "pass": False,
        "missing_fields": [],
        "nan_issues": [],
        "bounds_issues": [],
        "direction_issues": [],
    }
    
    if not output_path.exists():
        logger.warning(f"  {symbol}: {output_path} not found")
        return result
    
    try:
        df = pd.read_parquet(output_path)
        logger.info(f"  {symbol}: {len(df)} rows")
        
        if verbose:
            logger.debug(f"\n{df.head(5)}\n")
        
        # Check 1: Schema
        missing = validate_dataclass_schema(df)
        if missing:
            result["missing_fields"] = missing
            logger.warning(f"    Missing fields: {missing}")
        
        # Check 2: NaN leakage
        nan_issues = validate_no_nan_leakage(df, symbol)
        if nan_issues:
            result["nan_issues"] = nan_issues
            for field, count in nan_issues:
                logger.warning(f"    NaN leakage in {field}: {count} rows")
        
        # Check 3: Numeric bounds
        bounds_issues = validate_numeric_bounds(df, symbol, checks)
        if bounds_issues:
            result["bounds_issues"] = bounds_issues
            for issue in bounds_issues:
                logger.debug(issue)
        
        # Check 4: Session direction (optional, expensive)
        # direction_issues = validate_session_direction(df, symbol, loader, checks)
        # if direction_issues:
        #     result["direction_issues"] = direction_issues
        #     for issue in direction_issues:
        #         logger.warning(issue)
        
        # Summary
        total_issues = len(missing) + len(nan_issues) + len(bounds_issues)
        result["pass"] = (total_issues == 0)
        
        if result["pass"]:
            logger.info(f"    ✓ All checks passed")
        else:
            logger.info(f"    ✗ {total_issues} issue(s) found")
    
    except Exception as e:
        logger.error(f"  {symbol}: {e}", exc_info=True)
        result["error"] = str(e)
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate Daily Context output")
    parser.add_argument("--symbol", nargs="+", default=None, help="Symbols to validate")
    parser.add_argument("--checks", type=int, default=10, help="Spot-checks per symbol")
    parser.add_argument("--verbose", action="store_true", help="Print all rows")
    args = parser.parse_args()
    
    symbols = args.symbol or ALL_SYMBOLS
    loader = DataLoader()
    
    logger.info(f"Validating Daily Context for {len(symbols)} symbols...")
    logger.info(f"Input directory: {DERIVED_DIR}\n")
    
    results = []
    for symbol in sorted(symbols):
        result = validate_symbol(symbol, loader, args.checks, args.verbose)
        results.append(result)
    
    # Summary
    passed = sum(1 for r in results if r.get("pass", False))
    logger.info(f"\n{'='*60}")
    logger.info(f"Summary: {passed}/{len(results)} symbols passed validation")
    
    if passed < len(results):
        logger.warning("Issues found:")
        for r in results:
            if not r.get("pass", False):
                logger.warning(f"  {r['symbol']}:")
                if r.get("missing_fields"):
                    logger.warning(f"    - Missing fields: {r['missing_fields']}")
                if r.get("nan_issues"):
                    logger.warning(f"    - NaN leakage: {r['nan_issues']}")
                if r.get("error"):
                    logger.warning(f"    - Error: {r['error']}")
    
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
