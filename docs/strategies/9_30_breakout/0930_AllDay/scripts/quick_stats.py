
import pandas as pd
import glob
import os

# Target the Superstar File
FILE_PATTERN = r"ORB_V3_Doji*8f5bf.xlsx"
files = glob.glob(FILE_PATTERN)

if not files:
    print("File not found.")
else:
    path = files[0]
    print(f"Analyzing: {os.path.basename(path)}")
    
    df = pd.read_excel(path, sheet_name="List of trades")
    df.columns = df.columns.str.strip()
    
    # Filter for Exits to get P&L
    # Actually 'Net P&L USD' is usually on the Exit row, but let's just use the column if it's filled.
    # TradingView 'List of trades' usually has P&L on the *closing* trade row.
    exits = df[df['Type'].str.contains('Exit', na=False)]
    
    wins = exits[exits['Net P&L USD'] > 0]['Net P&L USD']
    losses = exits[exits['Net P&L USD'] <= 0]['Net P&L USD']
    
    avg_win = wins.mean()
    avg_loss = losses.mean()
    
    print(f"Average Win:  ${avg_win:,.2f}")
    print(f"Average Loss: ${avg_loss:,.2f}")
    print(f"Risk Unit (R): ${abs(avg_loss):,.2f}")
