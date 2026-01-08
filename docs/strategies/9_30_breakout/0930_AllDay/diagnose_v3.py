import pandas as pd
import os
import glob
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# Directory
DIR = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\old"
files = glob.glob(os.path.join(DIR, "*.xlsx"))

results = {}

for path in files:
    name = os.path.basename(path)
    # Skip temporary files
    if name.startswith("~$"): continue
    
    print(f"Loading {name}...")
    try:
         xls = pd.ExcelFile(path)
         
         # 1. READ PROPERTIES (Inputs)
         props = {}
         if "Properties" in xls.sheet_names:
             df_props = pd.read_excel(path, sheet_name="Properties")
             # Print columns to debug
             if name == os.path.basename(files[0]):
                 print(f"DEBUG: {name} Columns: {df_props.columns.tolist()}")
                 print(df_props.head(3))

             # Try detecting Key/Value cols
             # Usually Key is first string col, Value is next.
             # Convert entire DF to string to be safe
             df_props = df_props.astype(str)
             
             for index, row in df_props.iterrows():
                 # Iterate all cols to find Key/Value pair?
                 # Assume Col 0 = Key, Col 1 = Value
                 if len(row) >= 2:
                    key = str(row.iloc[0]).strip()
                    val = str(row.iloc[1]).strip()
                    props[key] = val
         
         # Extract Key Inputs
         mode = props.get("Runner Mode After TP1", "Unknown")
         trail_act = props.get("Trail Activation % (if Trailing)", props.get("Trail Activation %", "N/A"))
         trail_off = props.get("Trail Offset % (if Trailing)", props.get("Trail Offset % (Wide)", "N/A"))
         min_con = props.get("Min Contracts (Force Size)", "N/A")
         max_att = props.get("Max Attempts per Day", "N/A")
         vvix = props.get("Enable VVIX Filter", "N/A")
         range_flt = props.get("Max Range % (Skip if larger)", "N/A")

         # 2. READ TRADES via List of trades
         sheet = next((s for s in xls.sheet_names if s.lower() == "list of trades"), None)
         if sheet:
             df = pd.read_excel(path, sheet_name=sheet)
             
             # DEBUG: Check Head for Duplication
             if name == os.path.basename(files[0]):
                 print(f"DEBUG: {name} Head:\n{df[['Trade #', 'Type', 'Net P&L USD']].head(10).to_string()}")
             
             profit = 0
             if 'Net P&L USD' in df.columns and 'Type' in df.columns:
                 # Filter to only keep EXIT rows to avoid duplication
                 # Check if Type contains 'Exit'
                 df_exits = df[df['Type'].astype(str).str.contains("Exit", case=False, na=False)]
                 profit = df_exits['Net P&L USD'].sum()
             
             trades = len(df) // 2 # Approx trades is half of rows if Entry+Exit
             
             # Calculate Trades Per Day
             days = 0
             if 'Date and time' in df.columns:
                 df['Date and time'] = pd.to_datetime(df['Date and time'])
                 if not df.empty:
                     start = df['Date and time'].min()
                     end = df['Date and time'].max()
                     days = (end - start).days
             
             avg_daily = round(trades / days, 1) if days > 0 else 0
             
             results[name] = {
                 "Mode": mode,
                 "Profit": round(profit, 2),
                 "Trades": trades,
                 "Avg/Day": avg_daily,
                 "TrailAct": trail_act,
                 "TrailOff": trail_off,
                 "MinCon": min_con,
                 "VVIX": vvix,
                 "RangeFlt": range_flt,
                 "Att": max_att
             }
         else:
             results[name] = "No Trade Sheet"

    except Exception as e:
         print(f"  Error {name}: {e}")
         results[name] = "Error"

print("\n--- COMPARISON ---")
for name, res in results.items():
    if isinstance(res, dict):
        print(f"\nFILE: {name}")
        print(f"  Mode    : {res['Mode']}")
        print(f"  Profit  : ${res['Profit']}")
        print(f"  Trades  : {res['Trades']}")
        print(f"  Avg/Day : {res['Avg/Day']}")
        print(f"  TrailAct: {res['TrailAct']}")
        print(f"  TrailOff: {res['TrailOff']}")
        print(f"  MinCon  : {res['MinCon']}")
        print(f"  VVIX    : {res['VVIX']}")
        print(f"  MaxRange: {res['RangeFlt']}") # Added RangeFlt to dict below
        print(f"  MaxAtt  : {res['Att']}")
    else:
         print(f"{name}: {res}")
