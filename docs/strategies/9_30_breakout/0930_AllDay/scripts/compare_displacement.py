"""
Compare Displacement Filter Backtest Results
=============================================
Analyze Excel files from displacement subfolder
"""

import pandas as pd
from pathlib import Path

DISP_DIR = Path(r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\displacement")

def analyze_excel(excel_path):
    """Extract key metrics from backtest Excel"""
    print(f"\n{'='*60}")
    print(f"File: {excel_path.name}")
    print(f"{'='*60}")
    
    try:
        # Get performance summary
        perf = pd.read_excel(excel_path, sheet_name='Performance')
        print("\nPERFORMANCE SUMMARY:")
        
        # Find key rows
        for _, row in perf.iterrows():
            label = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            value = row.iloc[1] if len(row) > 1 and pd.notna(row.iloc[1]) else None
            
            if any(k in label.lower() for k in ['net profit', 'total trades', 'win', 'loss', 'factor', 'drawdown']):
                print(f"  {label}: {value}")
        
        # Get trade analysis
        trades = pd.read_excel(excel_path, sheet_name='Trades analysis')
        print("\nTRADES ANALYSIS:")
        for _, row in trades.iterrows():
            label = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            value = row.iloc[1] if len(row) > 1 and pd.notna(row.iloc[1]) else None
            
            if any(k in label.lower() for k in ['total', 'winning', 'losing', 'percent', 'ratio']):
                print(f"  {label}: {value}")
        
        # Get input settings from Properties
        try:
            props = pd.read_excel(excel_path, sheet_name='Properties')
            print("\nKEY SETTINGS:")
            for _, row in props.iterrows():
                label = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                value = row.iloc[1] if len(row) > 1 else None
                
                if 'displacement' in label.lower() or 'min disp' in label.lower():
                    print(f"  >>> {label}: {value}")
                elif any(k in label.lower() for k in ['entry mode', 'tp mode', 'attempts']):
                    print(f"  {label}: {value}")
        except:
            pass
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    excel_files = sorted(DISP_DIR.glob("*.xlsx"))
    print(f"Found {len(excel_files)} Excel files")
    
    for f in excel_files:
        analyze_excel(f)
