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
today_tickers = df_sheet[today_col].dropna().astype(str).tolist()
today_tickers = [t.strip().upper() for t in today_tickers if len(t.strip()) > 0 and t.strip() != today_col]

sss_matches = ['AGEN', 'AMWL', 'APLZ', 'ASTN', 'ATAI', 'BEZ', 'CDNA', 'CHRN', 'CLRO', 'COAG', 'CORD', 'DMRA', 'FBRX', 'FIGG', 'GDXD', 'GORO', 'GRPN', 'IONZ', 'LCID', 'MAN', 'NBIZ', 'NXTC', 'OKLS', 'PESI', 'PYPG', 'PYPL', 'QBTZ', 'RGTZ', 'RHI', 'RKLZ', 'RPD', 'SKYQ', 'SMCZ', 'SNAL', 'SNDQ', 'SOXS', 'VEEE', 'XNCR']

missing_tickers = [t for t in today_tickers if t not in sss_matches]

print(f'Missing Tickers count: {len(missing_tickers)} out of {len(today_tickers)}')
print(f'Missing Tickers: {missing_tickers}\n')

data = yf.download(missing_tickers, period='1mo', interval='1d', group_by='ticker', progress=False)

diag_list = []
for t in missing_tickers:
    try:
        df = data[t].dropna() if len(missing_tickers) > 1 else data.dropna()
        if len(df) < 5:
            diag_list.append({'ticker': t, 'status': 'insufficient_data/delisted', 'close': 0, 'max_5d_gain_pct': 0, 'avg_vol': 0, 'reason': 'Delisted/No YFinance Data'})
            continue
        close = df['Close']
        high = df['High']
        low = df['Low']
        vol = df['Volume']
        
        max_5d_gain = ((high.iloc[-5:].max() - low.iloc[-5:].min()) / low.iloc[-5:].min()) * 100.0
        avg_vol = vol.iloc[-20:].mean() if len(vol) >= 20 else vol.mean()

        reason = []
        if close.iloc[-1] < 1.0:
            reason.append(f"Price < $1.0 (${close.iloc[-1]:.2f})")
        if avg_vol < 100000:
            reason.append(f"Avg Vol < 100k ({int(avg_vol)})")
        if max_5d_gain < 20.0:
            reason.append(f"5d Move < 20% ({max_5d_gain:.1f}%)")
        if not reason:
            reason.append("Passed metrics (check yaml rule binding)")

        diag_list.append({
            'ticker': t,
            'close': round(close.iloc[-1], 2),
            'max_5d_gain_pct': round(max_5d_gain, 1),
            'avg_vol': int(avg_vol),
            'exclusion_reason': ', '.join(reason)
        })
    except Exception as e:
        diag_list.append({'ticker': t, 'close': 0, 'max_5d_gain_pct': 0, 'avg_vol': 0, 'exclusion_reason': f'Error: {e}'})

df_diag = pd.DataFrame(diag_list)
print(df_diag.to_string(index=False))
