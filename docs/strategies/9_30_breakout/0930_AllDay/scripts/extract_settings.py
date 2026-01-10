"""
Extract settings from all Excel backtests to see what's actually used
"""
import pandas as pd
from pathlib import Path

STRATEGY_DIR = Path(r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay")

# Find recent V3 Excel files
excel_files = list(STRATEGY_DIR.glob("ORB_V3*MNQ*.xlsx")) + list(STRATEGY_DIR.glob("ORB_V3*MNQ*.xlsx"))
excel_files = [f for f in excel_files if 'old' not in str(f).lower()]

print(f"Found {len(excel_files)} recent Excel files")

all_settings = []

for f in excel_files[:5]:  # Check up to 5 files
    try:
        props = pd.read_excel(f, sheet_name='Properties')
        print(f"\n=== {f.name} ===")
        
        settings = {}
        for _, row in props.iterrows():
            label = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            value = row.iloc[1] if len(row) > 1 and pd.notna(row.iloc[1]) else None
            
            if label and value is not None:
                settings[label] = value
                print(f"  {label}: {value}")
        
        all_settings.append(settings)
    except Exception as e:
        print(f"Error reading {f.name}: {e}")

# Find common settings across all files
print("\n" + "="*70)
print("SETTINGS COMPARISON")
print("="*70)
