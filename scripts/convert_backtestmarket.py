#!/usr/bin/env python3
"""
Convert BacktestMarket CSV files to standard format with Unix timestamps.

Source: https://www.backtestmarket.com/

BacktestMarket CSV Format:
==========================
- Delimiter: Semicolon (;)
- Date Format: DD/MM/YYYY (European format, NOT MM/DD/YYYY!)
- Time Format: HH:MM (24-hour)
- Timezone: Chicago (America/Chicago)
  - CST (Nov-Mar): UTC-6
  - CDT (Mar-Nov): UTC-5
- Columns: date;time;open;high;low;close;volume (no header row)

Example Input:
  09/11/2025;18:40;25319.25;25323.75;25315.50;25323.00;150

Conversion Steps:
=================
1. Parse date as DD/MM/YYYY
2. Combine date + time into datetime
3. Localize to Chicago timezone (handles DST automatically)
4. Convert to UTC
5. Convert to Unix timestamp

Verification:
=============
Always verify conversion by matching OHLC values against a known-good
source (e.g., TradingView Unix timestamp export) for overlapping periods.

Usage:
======
  python scripts/convert_backtestmarket.py <input_csv> <output_csv> [--ticker TICKER]

  Example:
    python scripts/convert_backtestmarket.py data/TV_OHLC/nq-1m_bk.csv data/TV_OHLC/nq-1m_converted.csv --ticker NQ1
"""

import argparse
import pandas as pd
from pathlib import Path
import pytz
import sys


def convert_backtestmarket_csv(input_path: Path, output_path: Path, ticker: str = ""):
    """
    Convert BacktestMarket CSV to standard format with Unix timestamps.
    
    Args:
        input_path: Path to input CSV (semicolon-delimited, Chicago timezone)
        output_path: Path to output CSV (comma-delimited, Unix timestamps)
        ticker: Optional ticker name for logging
    
    Returns:
        DataFrame with converted data
    """
    print(f"Converting: {input_path}")
    print(f"Ticker: {ticker or 'Unknown'}")
    print()
    
    # Load the CSV (semicolon-delimited, no header)
    print("Loading CSV...")
    df = pd.read_csv(input_path, sep=";", header=None,
                     names=["date", "time", "open", "high", "low", "close", "volume"])
    print(f"  Loaded {len(df):,} rows")
    
    # Parse date with DD/MM/YYYY format (European format!)
    print("Parsing dates (DD/MM/YYYY format)...")
    df["datetime_str"] = df["date"] + " " + df["time"]
    df["datetime"] = pd.to_datetime(df["datetime_str"], format="%d/%m/%Y %H:%M", errors="coerce")
    
    parse_errors = df["datetime"].isna().sum()
    if parse_errors > 0:
        print(f"  WARNING: {parse_errors} rows failed to parse")
        df = df.dropna(subset=["datetime"])
    else:
        print("  No parse errors")
    
    # Convert Chicago timezone to UTC
    print("Converting Chicago timezone to UTC...")
    chicago_tz = pytz.timezone("America/Chicago")
    
    # Localize to Chicago (handle DST transitions)
    df["datetime"] = df["datetime"].dt.tz_localize(chicago_tz, ambiguous="NaT", nonexistent="NaT")
    
    # Count and drop ambiguous times (DST transitions)
    ambiguous = df["datetime"].isna().sum()
    if ambiguous > 0:
        print(f"  Dropped {ambiguous} rows with ambiguous DST times")
        df = df.dropna(subset=["datetime"])
    
    # Convert to UTC
    df["datetime"] = df["datetime"].dt.tz_convert("UTC")
    
    # Convert to Unix timestamp
    df["unix_time"] = df["datetime"].apply(lambda x: int(x.timestamp()))
    
    # Remove timezone info
    df["datetime"] = df["datetime"].dt.tz_localize(None)
    
    print(f"  Conversion complete: {len(df):,} rows")
    print(f"  Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    print()
    
    # Save output
    output_df = df[["unix_time", "open", "high", "low", "close", "volume"]].copy()
    output_df.columns = ["time", "open", "high", "low", "close", "volume"]
    output_df.to_csv(output_path, index=False)
    print(f"Saved to: {output_path}")
    
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Convert BacktestMarket CSV to standard format with Unix timestamps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("input", type=Path, help="Input CSV file (BacktestMarket format)")
    parser.add_argument("output", type=Path, help="Output CSV file (Unix timestamps)")
    parser.add_argument("--ticker", type=str, default="", help="Ticker name for logging")
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    convert_backtestmarket_csv(args.input, args.output, args.ticker)
    print("\nDone!")


if __name__ == "__main__":
    main()
