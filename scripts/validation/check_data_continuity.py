import pandas as pd
from pathlib import Path
import argparse

def check_continuity(ticker: str, year: int = None, max_gap_hours: float = 48.0):
    """
    Checks for data gaps within a parquet file.
    If year is provided, checks only that year.
    max_gap_hours: Threshold to report a gap (default 48h for weekends).
    """
    path = Path(f"data/{ticker}_1m.parquet")
    if not path.exists():
        print(f"❌ {ticker} parquet not found: {path}")
        return

    print(f"Loading {path}...")
    df = pd.read_parquet(path)
    
    # Timezone Handling
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df.index = df.index.tz_convert('US/Eastern')
    
    # Filter by Year if requested
    if year:
        start_dt = pd.Timestamp(f"{year}-01-01", tz="US/Eastern")
        end_dt = pd.Timestamp(f"{year}-12-31", tz="US/Eastern")
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        print(f"--- {ticker} {year} Data Analysis ---")
    else:
        print(f"--- {ticker} Full History Analysis ---")

    if len(df) == 0:
        print(f"❌ No data found{' for ' + str(year) if year else ''}.")
        return

    print(f"Rows: {len(df):,}")
    print(f"Range: {df.index.min()} to {df.index.max()}")
    
    # Gap Check
    df = df.sort_index()
    diffs = df.index.to_series().diff()
    
    # Convert diffs to hours
    diffs_hours = diffs.dt.total_seconds() / 3600.0
    
    gaps = diffs[diffs_hours > max_gap_hours]
    
    if len(gaps) > 0:
        print(f"\n⚠️ Significant Gaps (> {max_gap_hours} hours):")
        for date, delta in gaps.items():
            print(f"  Gap ending {date}: {delta}")
    else:
        print(f"\n✅ No gaps > {max_gap_hours} hours found.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check data continuity and gaps.")
    parser.add_argument("ticker", help="Ticker symbol (e.g. NQ1)")
    parser.add_argument("--year", type=int, help="Specific year to check (optional)")
    parser.add_argument("--gap", type=float, default=48.0, help="Max gap in hours to ignore (default: 48.0)")
    
    args = parser.parse_args()
    
    check_continuity(args.ticker, args.year, args.gap)
