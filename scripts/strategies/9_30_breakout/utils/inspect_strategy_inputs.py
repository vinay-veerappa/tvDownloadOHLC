import pandas as pd
import os

FILE_PATH = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx"

def inspect():
    print(f"Inspecting {FILE_PATH}...")
    try:
        # TradingView exports often have inputs in a separate sheet or at the top of 'Summary' 
        # But usually 'List of trades' is just trades.
        # Let's check sheet names first.
        xl = pd.ExcelFile(FILE_PATH)
        print(f"Sheets: {xl.sheet_names}")
        
        # Check 'Settings' or 'Inputs' if it exists (Generic TV export might not have it, but Strategy Tester export does 'List of trades', 'Performance Summary')
        # If no specific sheet, sometimes data is in the header of 'List of trades'
        


        # Check 'Properties' sheet (Found in sheet list)
        if "Properties" in xl.sheet_names:
            print("\nReading 'Properties' sheet (Rows 30-60)...")
            df_props = pd.read_excel(xl, sheet_name="Properties")
            print(df_props.iloc[30:60])
        else:
            print("'Properties' sheet not found.")
            
        # Often settings aren't in the export unless manual copy-paste.
        # If not found, I will have to ask the user or infer from trade behavior.
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
