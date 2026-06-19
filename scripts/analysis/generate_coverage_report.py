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
        if df.empty:
            return None
            
        count = len(df)
        start_date = "N/A"
        end_date = "N/A"

        # Get dates from index if it's a DatetimeIndex
        if isinstance(df.index, pd.DatetimeIndex):
            start_date = df.index.min().strftime('%Y-%m-%d')
            end_date = df.index.max().strftime('%Y-%m-%d')
        else:
            # Determine time column
            time_col = None
            if 'time' in df.columns: time_col = 'time'
            elif 'datetime' in df.columns: time_col = 'datetime'
            elif 'date' in df.columns: time_col = 'date'
            
            if time_col:
                first = df[time_col].iloc[0]
                last = df[time_col].iloc[-1]
                
                # If it's a number (int, float, numpy int), assume Unix timestamp
                if pd.api.types.is_number(first):
                    if first > 10**12: # Milliseconds
                        start_date = pd.to_datetime(first, unit='ms').strftime('%Y-%m-%d')
                        end_date = pd.to_datetime(last, unit='ms').strftime('%Y-%m-%d')
                    else: # Seconds
                        start_date = pd.to_datetime(first, unit='s').strftime('%Y-%m-%d')
                        end_date = pd.to_datetime(last, unit='s').strftime('%Y-%m-%d')
                else:
                    # Assume datetime object or string
                    try:
                        start_date = pd.to_datetime(first).strftime('%Y-%m-%d')
                        end_date = pd.to_datetime(last).strftime('%Y-%m-%d')
                    except:
                        pass
                
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
    lines.append("## Known Historical Gaps")
    lines.append("")
    lines.append("Historical daily and weekly data is contiguous up to the current date. The only gaps detected during audits perfectly align with known, multi-day **US Market Closures** and historical artifacts.")
    lines.append("")
    lines.append("- **September 2001 (144-168 hours)**: The week-long closure following the 9/11 attacks. (Impacts SPX, NQ1, QQQ, SPY, VIX).")
    lines.append("- **December 2006 / January 2007 (120 hours)**: The closure for the National Day of Mourning for President Gerald Ford combined with the New Year's Day holiday.")
    lines.append("- **October 2012 (120 hours)**: The closure due to Hurricane Sandy.")
    lines.append("- **Older SPX Gaps (1940s-1960s)**: Scattered 120-hour gaps corresponding to historical holiday schedules, wartime operations, and long weekend market closures before modern market schedules were standardized.")
    lines.append("- **VVIX (Volatility of Volatility)**: Contains missing data points/gaps clustered in its early inception years (2006) and a few in 2013-2014.")
    lines.append("")
    lines.append("### Live Storage (2026) Gaps")
    lines.append("")
    lines.append("The `live_storage` 1-minute data files contain a few recent gaps. These are NOT market closures; they represent periods where the quant system's live data collector was offline (e.g., server down, maintenance, or connection issues):")
    lines.append("")
    lines.append("- ~~**Mid-April System Outage (Apr 15 - Apr 24, 2026)**~~: *Resolved via TradingView CSV imports on June 18, 2026.*")
    lines.append("- ~~**Mid-May System Outage (May 8 - May 13, 2026)**~~: *Resolved via Schwab API patch script on June 18, 2026.*")
    lines.append("- ~~**Late-May System Outage (May 27 - June 1, 2026)**~~: *Resolved via Schwab API patch script on June 18, 2026.*")
    lines.append("- **Dormant Symbols (RIVN)**: These symbols have not been actively collected since December 2025 and are mostly empty in 2026.")
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
