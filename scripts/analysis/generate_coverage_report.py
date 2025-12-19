import pandas as pd
from pathlib import Path
from datetime import datetime
import os

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
REPORT_FILE = DOCS_DIR / "data" / "DATA_COVERAGE_REPORT.md"

def get_parquet_stats(filepath):
    try:
        # Read only necessary columns/metadata to be faster? 
        # parquet metadata might suffice for some, but we need volume check and exact date range
        df = pd.read_parquet(filepath)
        df.reset_index(inplace=True)
        
        if df.empty:
            return None
            
        count = len(df)
        
        # Determine time column
        time_col = None
        if 'time' in df.columns: time_col = 'time'
        elif 'datetime' in df.columns: time_col = 'datetime'
        elif 'date' in df.columns: time_col = 'date'
        elif 'index' in df.columns: time_col = 'index'
        
        start_date = "N/A"
        end_date = "N/A"
        
        if time_col:
            # Check if unix timestamp
            first = df[time_col].iloc[0]
            last = df[time_col].iloc[-1]
            
            if isinstance(first, (int, float)):
                start_date = datetime.fromtimestamp(first).strftime('%Y-%m-%d')
                end_date = datetime.fromtimestamp(last).strftime('%Y-%m-%d')
            else:
                # Assume datetime object or string
                start_date = pd.to_datetime(first).strftime('%Y-%m-%d')
                end_date = pd.to_datetime(last).strftime('%Y-%m-%d')
                
        has_volume = 'volume' in df.columns or 'Volume' in df.columns
        
        return {
            "count": count,
            "start": start_date,
            "end": end_date,
            "volume": has_volume
        }
    except Exception as e:
        print(f"Error reading {filepath.name}: {e}")
        return None

def main():
    print("Generating Data Coverage Report...")
    
    if not DATA_DIR.exists():
        print("Data directory not found!")
        return

    # Collect stats
    data = []
    
    files = sorted(list(DATA_DIR.glob("*.parquet")))
    
    for p_file in files:
        # Parse ticker and timeframe
        # Format: TICKER_TF.parquet
        parts = p_file.stem.split('_')
        if len(parts) >= 2:
            ticker = parts[0]
            timeframe = "_".join(parts[1:]) 
        else:
            continue
            
        print(f"  Scanning {p_file.name}...")
        stats = get_parquet_stats(p_file)
        
        if stats:
            data.append({
                "ticker": ticker,
                "timeframe": timeframe,
                "start": stats['start'],
                "end": stats['end'],
                "bars": stats['count'],
                "volume": stats['volume']
            })

    # Group by Ticker
    data_by_ticker = {}
    for item in data:
        t = item['ticker']
        if t not in data_by_ticker:
            data_by_ticker[t] = []
        data_by_ticker[t].append(item)
        
    # Sort timeframes ordering
    tf_order = {"1m": 0, "5m": 1, "15m": 2, "1h": 3, "4h": 4, "1D": 5, "1W": 6}
    
    # Generate Markdown
    lines = []
    lines.append("# 📊 Data Coverage Report")
    lines.append("")
    lines.append(f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("This report shows the available OHLC data for each ticker and timeframe.")
    lines.append("")
    lines.append("## Data Availability")
    lines.append("")
    lines.append("| Ticker | Timeframe | Start Date | End Date | Bars | Volume |")
    lines.append("|--------|-----------|------------|----------|------|--------|")
    
    for ticker in sorted(data_by_ticker.keys()):
        items = data_by_ticker[ticker]
        # Sort items
        items.sort(key=lambda x: tf_order.get(x['timeframe'], 99))
        
        first = True
        for item in items:
            t_cell = f"**{ticker}**" if first else ""
            vol_icon = "✅" if item['volume'] else "❌"
            
            lines.append(f"| {t_cell} | {item['timeframe']} | {item['start']} | {item['end']} | {item['bars']:,} | {vol_icon} |")
            first = False

    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append("- **Volume**: ✅ = Has volume data, ❌ = No volume data (historical OHLC only)")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Data is stored in Parquet format in `data/` directory")
    lines.append("- Timestamps are in UTC")
    lines.append("- Weekend and holiday gaps are expected")
    
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
        
    print(f"Report updated: {REPORT_FILE}")

if __name__ == "__main__":
    main()
