import pandas as pd
import numpy as np
import os

import glob

def analyze_trade_report():
    folder_path = r"C:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout"
    files = glob.glob(os.path.join(folder_path, "*.xlsx"))
    
    if not files:
        print("No Excel files found.")
        return

    print(f"Found {len(files)} trade reports.")
    
    for file_path in files:
        print("\n" + "="*60)
        print(f"REPORT: {os.path.basename(file_path)}")
        print("="*60)
        
        try:
            xl = pd.ExcelFile(file_path)
            
            # 1. GET SETTINGS (Properties)
            props_sheet = next((s for s in xl.sheet_names if 'Properties' in s or 'inputs' in s.lower()), None)
            if props_sheet:
                df_props = pd.read_excel(file_path, sheet_name=props_sheet)
                # Extract Key Settings
                print("--- SETTINGS ---")
                keys_to_check = ['Confirmation %', 'TP1 Level', 'TP1 Qty', 'Entry Mode', 'Stop trading after']
                # Filter rows where 'name' contains key (case insensitive) check
                # Assuming columns are 'name', 'value'
                if 'name' in df_props.columns and 'value' in df_props.columns:
                     for key in keys_to_check:
                         match = df_props[df_props['name'].astype(str).str.contains(key, case=False, na=False)]
                         if not match.empty:
                             for idx, row in match.iterrows():
                                 print(f"{row['name']}: {row['value']}")
            else:
                print("No Properties sheet found.")

            # 2. GET PERFORMANCE (Trades)
            list_sheet = next((s for s in xl.sheet_names if 'List of trades' in s), None)
            if not list_sheet:
                 list_sheet = next((s for s in xl.sheet_names if 'Trades' in s), None)
            
            if list_sheet:
                df = pd.read_excel(file_path, sheet_name=list_sheet)
                
                # Column Cleaning
                if 'Profit' not in df.columns:
                     df.columns = df.columns.astype(str).str.replace('\n', ' ').str.replace('  ', ' ').str.strip()
                     pnl_col = next((c for c in df.columns if 'Net P&L' in c and 'USD' in c), None)
                     if pnl_col: df.rename(columns={pnl_col: 'Profit'}, inplace=True)
                     
                if 'Profit' in df.columns:
                     if df['Profit'].dtype == object:
                          df['Profit'] = df['Profit'].astype(str).str.replace('$', '').str.replace(',', '').str.replace('−', '-').astype(float)
                     
                     # Find Date column
                     date_col = next((c for c in df.columns if 'Date' in c and 'time' in c), None)
                     if date_col: df.rename(columns={date_col: 'Date/Time'}, inplace=True)

                     # Deduplicate Partials
                     if 'Trade #' in df.columns:
                         # Force numeric if possible
                         df['Trade #'] = pd.to_numeric(df['Trade #'], errors='coerce')
                         # Determine if duplicate IDs exist
                         if df['Trade #'].duplicated().any():
                             print("(Partials detected - Aggregating trade results)")
                             agg_dict = {'Profit': 'sum'}
                             if 'Date/Time' in df.columns: agg_dict['Date/Time'] = 'first'
                             df = df.groupby('Trade #').agg(agg_dict).reset_index()
                     
                     # Date Range
                     if 'Date/Time' in df.columns:
                         start_date = df['Date/Time'].min()
                         end_date = df['Date/Time'].max()
                         print(f"Date Range: {start_date} to {end_date}")
                         
                     total_trades = len(df)
                     net_profit = df['Profit'].sum()
                     win_rate = (len(df[df['Profit'] > 0]) / total_trades * 100) if total_trades > 0 else 0
                     avg_trade = net_profit / total_trades if total_trades > 0 else 0
                     
                     print("--- PERFORMANCE ---")
                     print(f"Net Profit: ${net_profit:,.2f}")
                     print(f"Total Trades: {total_trades}")
                     print(f"Win Rate: {win_rate:.2f}%")
                     print(f"Avg Trade: ${avg_trade:.2f}")
                else:
                    print("Could not analyze Profit (Column missing).")
            else:
                print("No Trade List sheet found.")

        except Exception as e:
            print(f"Error processing {os.path.basename(file_path)}: {e}")

if __name__ == "__main__":
    analyze_trade_report()
