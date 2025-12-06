"""
Generate DATA_COVERAGE_REPORT.md from parquet files
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

data_dir = Path("data")
output_file = Path("docs/DATA_COVERAGE_REPORT.md")

# Get all parquet files
parquet_files = sorted(data_dir.glob("*.parquet"))

# Build report data
report_data = []
for f in parquet_files:
    try:
        df = pd.read_parquet(f)
        parts = f.stem.split("_")
        ticker = parts[0]
        timeframe = parts[1] if len(parts) > 1 else "Unknown"
        
        start_date = df.index.min()
        end_date = df.index.max()
        bar_count = len(df)
        
        # Check volume
        has_volume = "volume" in df.columns and (df["volume"] > 0).any()
        vol_status = "✅" if has_volume else "❌"
        
        report_data.append({
            "ticker": ticker,
            "timeframe": timeframe,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "bars": bar_count,
            "volume": vol_status
        })
    except Exception as e:
        print(f"Error reading {f}: {e}")

# Sort by ticker then timeframe
tf_order = {"1m": 1, "5m": 2, "15m": 3, "1h": 4, "4h": 5, "1D": 6, "1W": 7}
report_data.sort(key=lambda x: (x["ticker"], tf_order.get(x["timeframe"], 99)))

# Generate markdown
lines = [
    "# 📊 Data Coverage Report",
    "",
    f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    "",
    "## Summary",
    "",
    "This report shows the available OHLC data for each ticker and timeframe.",
    "",
    "## Data Availability",
    "",
    "| Ticker | Timeframe | Start Date | End Date | Bars | Volume |",
    "|--------|-----------|------------|----------|------|--------|",
]

current_ticker = None
for row in report_data:
    ticker_cell = f"**{row['ticker']}**" if row["ticker"] != current_ticker else ""
    current_ticker = row["ticker"]
    lines.append(f"| {ticker_cell} | {row['timeframe']} | {row['start']} | {row['end']} | {row['bars']:,} | {row['volume']} |")

lines.extend([
    "",
    "## Legend",
    "",
    "- **Volume**: ✅ = Has volume data, ❌ = No volume data (historical OHLC only)",
    "",
    "## Notes",
    "",
    "- Data is stored in Parquet format in `data/` directory",
    "- Timestamps are in UTC",
    "- Weekend and holiday gaps are expected",
])

md = "\n".join(lines)

# Write to file
output_file.write_text(md, encoding="utf-8")
print(f"Report written to {output_file}")
print()
print(md)
