import sys
sys.path.insert(0, '.')
import pandas as pd
import yfinance as yf
from pathlib import Path
from io import StringIO

sheet_path = Path(r'C:\Users\vinay\.gemini\antigravity\brain\eba9e5d1-13a8-4bda-9a19-8ef40ca47d28\.system_generated\steps\388\content.md')
with open(sheet_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

csv_lines = [l.strip() for l in lines if l.startswith('"')]
df_sheet = pd.read_csv(StringIO('\n'.join(csv_lines)), header=0)

today_col = df_sheet.columns[0]
today_tickers = [t.strip().upper() for t in df_sheet[today_col].dropna().astype(str) if len(t.strip()) > 0 and t.strip() != today_col]

data = yf.download(today_tickers, period='1mo', interval='1d', group_by='ticker', progress=False)

diag_list = []
for t in today_tickers:
    try:
        df = data[t].dropna()
        if len(df) < 10: continue
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        move_5d = ((high.iloc[-5:].max() - low.iloc[-5:].min()) / low.iloc[-5:].min()) * 100.0
        move_10d = ((high.iloc[-10:].max() - low.iloc[-10:].min()) / low.iloc[-10:].min()) * 100.0
        
        diag_list.append({
            'ticker': t,
            'move_5d': round(move_5d, 1),
            'move_10d': round(move_10d, 1),
            'pass_12pct_5d': move_5d >= 12.0,
            'pass_20pct_10d': move_10d >= 20.0
        })
    except Exception:
        pass

df_diag = pd.DataFrame(diag_list)
print('--- THRESHOLD ADJUSTMENT RESULTS ---')
print('Strict 20% 5-day move pass:', (df_diag['move_5d'] >= 20.0).sum(), '/ 50')
print('Adjusted 12% 5-day move pass:', (df_diag['move_5d'] >= 12.0).sum(), '/ 50')
print('Adjusted 20% 10-day move pass:', (df_diag['move_10d'] >= 20.0).sum(), '/ 50')
combined_count = ((df_diag['move_5d'] >= 12.0) | (df_diag['move_10d'] >= 20.0)).sum()
print('Combined (12% 5-day OR 20% 10-day) pass:', combined_count, '/ 50')
