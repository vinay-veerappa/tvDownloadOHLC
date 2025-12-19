import os
import json
import datetime
import glob

DATA_ROOT = "web/public/data"
OUTPUT_FILE = "DATA_INVENTORY.md"

def get_human_date(ts):
    if not ts: return "N/A"
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

def main():
    print(f"Scanning {DATA_ROOT}...")
    
    inventory = []
    
    # scan for meta.json files
    meta_files = glob.glob(os.path.join(DATA_ROOT, "*", "meta.json"))
    
    for meta_path in meta_files:
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
                
            folder_name = os.path.basename(os.path.dirname(meta_path))
            
            # Extract ticker/timeframe from folder name or meta
            # Folder format: TICKER_TIMEFRAME (usually)
            
            item = {
                'ticker': meta.get('ticker', 'Unknown'),
                'timeframe': meta.get('timeframe', 'Unknown'),
                'start': get_human_date(meta.get('startTime')),
                'end': get_human_date(meta.get('endTime')),
                'bars': meta.get('totalBars', 0),
                'folder': folder_name
            }
            inventory.append(item)
        except Exception as e:
            print(f"Error reading {meta_path}: {e}")

    # Sort by Ticker, then Timeframe
    inventory.sort(key=lambda x: (x['ticker'], x['timeframe']))
    
    # Generate Markdown
    md_lines = []
    md_lines.append("# Data Inventory")
    md_lines.append(f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append("")
    md_lines.append("| Ticker | Timeframe | Start Date | End Date | Bars | Source Folder |")
    md_lines.append("|---|---|---|---|---|---|")
    
    for item in inventory:
        md_lines.append(f"| {item['ticker']} | {item['timeframe']} | {item['start']} | {item['end']} | {item['bars']} | `{item['folder']}` |")
        
    md_lines.append("")
    md_lines.append("## Notes")
    md_lines.append("- Data is stored in chunked JSON format in `web/public/data/`.")
    md_lines.append("- Dates are derived from `meta.json`.")

    with open(OUTPUT_FILE, 'w') as f:
        f.write('\n'.join(md_lines))
        
    print(f"Generated {OUTPUT_FILE} with {len(inventory)} entries.")

if __name__ == "__main__":
    main()
