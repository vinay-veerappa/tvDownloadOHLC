"""
Merge NinjaTrader ES data - Wrapper for standard importer
Ensures consistency with system-wide data ingestion logic.
"""

import sys
import os
from pathlib import Path

# Add scripts directory to path to import data_processing module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from data_processing.import_ninjatrader import import_ninjatrader_data

# Configuration
NEW_CSV = Path("data/NinjaTrader/24Dec2025/ES Thursday 857.csv")
TICKER = "ES1"
INTERVAL = "1m"

print("=" * 60)
print(f"ES 1m Data Merge (via Standard Importer)")
print("=" * 60)

if not NEW_CSV.exists():
    print(f"Error: Source file {NEW_CSV} not found!")
    exit(1)

# Use the standard importer function
# Default params from import_ninjatrader: 
#   shift_to_open=True (NinjaTrader exports Close time, we want Open time)
#   timezone="America/Los_Angeles" (User's local time)
#   align=False (We can enable this if we suspect price gaps/rollover issues, let's keep it safe off or consistent?)
#   Main script uses align=False usually unless specified.
#   User mentioned 'filling in missing data', so align=False is safer to avoid modifying history unless needed.

try:
    import_ninjatrader_data(
        str(NEW_CSV), 
        TICKER, 
        INTERVAL, 
        align=False,   # Don't auto-shift prices unless requested
        shift_to_open=True, # NinjaTrader uses Close time, system uses Open time
        timezone="America/Los_Angeles" # User is in PST
    )
    print("\nMerge process completed successfully using standard logic.")
    
except Exception as e:
    print(f"\n❌ Merge Failed: {e}")
    exit(1)
