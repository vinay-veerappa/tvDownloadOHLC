import sys
from pathlib import Path
sys.path.append(str(Path("scripts").resolve())) # Add scripts dir to path
from import_ninjatrader import import_ninjatrader_data
from regenerate_derived import regenerate_all

def run_import():
    csv_path = Path("data/NinjaTrader/NQ Monday 1755.csv")
    ticker = "NQ1" 
    interval = "1m"
    timezone = "America/Los_Angeles" # NinjaTrader Export Default
    
    print(f"=== Fixing {ticker} Data from {csv_path} ===")
    
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        return

    # Import and Merge
    # align=True tries to align price levels with existing data if possible, 
    # but the main fix is the timezone/shift.
    # shift_to_open=True (-1 min) is crucial for NinjaTrader 1m data.
    import_ninjatrader_data(
        csv_path=csv_path, 
        ticker=ticker, 
        interval=interval, 
        align=False, 
        shift_to_open=True, 
        timezone=timezone
    )
    
    # Regenerate Derived Data
    print("\n=== Regenerating Derived Data ===")
    regenerate_all(ticker)

if __name__ == "__main__":
    run_import()
