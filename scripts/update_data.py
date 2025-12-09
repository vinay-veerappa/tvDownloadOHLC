import os
import shutil
import subprocess
import glob
from pathlib import Path
import re

# Configuration
BASE_DIR = Path(__file__).parent.parent
IMPORT_DIR = BASE_DIR / "data" / "imports"
DATA_DIR = BASE_DIR / "data"

def clean_ticker(raw_ticker):
    # Remove exchange prefixes like CME_MINI_, NYMEX_, etc.
    # Heuristic: Take the last part after underscores, or just preserve key tickers
    # Example: CME_MINI_ES1! -> ES1!
    
    # Common mappings or logic
    if "ES1!" in raw_ticker: return "ES1!"
    if "NQ1!" in raw_ticker: return "NQ1!"
    if "CL1!" in raw_ticker: return "CL1!"
    if "RTY1!" in raw_ticker: return "RTY1!"
    if "GC1!" in raw_ticker: return "GC1!"
    if "YM1!" in raw_ticker: return "YM1!"
    
    # Fallback: remove common prefixes if possible, or return as is
    # This might need adjustment based on all possible export formats
    return raw_ticker

def parse_filename(filename):
    """
    Parses TradingView export filenames.
    Format example: "CME_MINI_ES1!, 1_d8ffc.csv"
    """
    # Remove hash suffix and extension first
    # "CME_MINI_ES1!, 1_d8ffc.csv" -> "CME_MINI_ES1!, 1"
    name_part = filename.rsplit('_', 1)[0]
    
    if ", " in name_part:
        parts = name_part.split(", ")
        ticker_part = parts[0]
        timeframe_part = parts[1]
    else:
        # Unexpected format
        return None, None

    ticker = clean_ticker(ticker_part)
    
    # Normalize timeframe
    # "1" -> "1m", "5" -> "5m", "D" -> "1D"
    if timeframe_part.isdigit():
        timeframe = f"{timeframe_part}m"
    else:
        # e.g. "1D", "1W" - map to standard if needed
        timeframe = timeframe_part.replace("D", "1D").replace("W", "1W")
        if timeframe == "11D": timeframe = "1D" # Handle potential parsing weirdness if digit+letter

    return ticker, timeframe

def run_script(script_path, args=[]):
    cmd = ["python", str(script_path)] + args
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running {script_path}:")
        print(result.stderr)
        return False
    print(result.stdout)
    return True

def main():
    print("=== Starting Data Update Pipeline ===")
    
    # 1. Check Import Directory
    if not IMPORT_DIR.exists():
        IMPORT_DIR.mkdir(parents=True)
        print(f"Created import directory: {IMPORT_DIR}")
        print("Please place new CSV files here and run the script again.")
        return

    csv_files = list(IMPORT_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {IMPORT_DIR}")
        print("Skipping import step. Proceeding to regeneration check? (y/n)")
        # For now, just exit or ask? Let's just exit if no new data to assume manual run
        # Or maybe the user wants to regenerate existing?
        # Let's check matching args? 
        # For this version: process imports if present.
    
    processed_tickers = set()

    for csv_path in csv_files:
        print(f"Processing {csv_path.name}...")
        try:
            ticker, timeframe = parse_filename(csv_path.name)
            if not ticker or not timeframe:
                print(f"Skipping {csv_path.name}: Could not parse filename format.")
                continue
            
            # We mostly care about 1m data for the base conversion
            # If user drops 1D data, we might not want to overwrite the aggregated 1D from 1m?
            # Existing policy: scripts generate aggregations from 1m.
            # So if this is 1m data, we treat it as the golden source.
            
            dest_filename = f"{ticker.replace('!', '')}_{timeframe}_continuous.csv"
            dest_path = DATA_DIR / dest_filename
            
            print(f"  Mapped to: {dest_filename}")
            print(f"  Moving to {dest_path}...")
            
            shutil.move(str(csv_path), str(dest_path))
            
            if timeframe == "1m":
                processed_tickers.add(ticker)
                
        except Exception as e:
            print(f"Error processing {csv_path.name}: {e}")

    # 2. Run Conversions
    # If we imported new 1m data, or if we want to force update
    # Let's run conversion for any ticker we just updated
    
    if processed_tickers:
        print(f"\nrunning parquet conversion for: {', '.join(processed_tickers)}")
        for ticker in processed_tickers:
            # data_processing/convert_to_parquet.py
            script = BASE_DIR / "data_processing" / "convert_to_parquet.py"
            success = run_script(script, ["--ticker", ticker, "--timeframe", "1m"])
            if not success:
                print(f"Failed to convert {ticker}. Stopping.")
                return

        # 3. Update Web JSONs (Chunking)
        # This script processes ALL parquet files in data/
        print("\nUpdating Web JSON Chunks...")
        script = BASE_DIR / "scripts" / "convert_to_chunked_json.py"
        run_script(script)
        
        # 4. Update Sessions
        # This script regenerates session JSONs for files in data/
        print("\nUpdating Session Files...")
        script = BASE_DIR / "scripts" / "generate_sessions.py"
        run_script(script)
        
        # 5. Update Documentation
        print("\nUpdating Documentation...")
        script = BASE_DIR / "scripts" / "generate_coverage_report.py"
        run_script(script)
        
        print("\n=== Update Complete! ===")
    else:
        print("\nNo '1m' files were imported. Skipping regeneration.")
        print("To force regeneration, ensure 1m CSVs are imported or run scripts manually.")

if __name__ == "__main__":
    main()
