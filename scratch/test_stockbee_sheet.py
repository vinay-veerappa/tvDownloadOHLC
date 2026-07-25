import sys
sys.path.insert(0, '.')
import pandas as pd
import yfinance as yf
from pathlib import Path
from io import StringIO
from scripts.screener.core.data_policy import prepare_price_series
from scripts.screener.core.features import build_feature_matrix
from scripts.screener.core.yaml_evaluator import evaluate_strategy_file

CONFIG_DIR = Path('scripts/screener/config')

sheet_path = Path(r'C:\Users\vinay\.gemini\antigravity\brain\eba9e5d1-13a8-4bda-9a19-8ef40ca47d28\.system_generated\steps\388\content.md')
with open(sheet_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

csv_lines = [l.strip() for l in lines if l.startswith('"')]
df_sheet = pd.read_csv(StringIO('\n'.join(csv_lines)), header=0)

today_col = df_sheet.columns[0]
print(f'Evaluating Stockbee Official Google Sheet Date: {today_col}')

today_tickers = df_sheet[today_col].dropna().astype(str).tolist()
today_tickers = [t.strip().upper() for t in today_tickers if len(t.strip()) > 0 and t.strip() != today_col]

print(f'Total Stockbee Tickers for Today ({today_col}): {len(today_tickers)}')
print(f'Sample Tickers: {today_tickers[:15]}\n')

data = yf.download(today_tickers, period='3mo', interval='1d', group_by='ticker', progress=False)

matrices = []
for t in today_tickers:
    try:
        df = data[t].dropna() if len(today_tickers) > 1 else data.dropna()
        if len(df) < 5: continue
        split_df, tr_df = prepare_price_series(df)
        fm = build_feature_matrix(split_df, ticker=t, tr_df=tr_df)
        if not fm.empty:
            matrices.append(fm)
    except Exception as e:
        pass

if matrices:
    full_fm = pd.concat(matrices, ignore_index=True)
    print(f'Successfully constructed feature matrices for {len(matrices)} tickers.\n')
    
    match_summary = {}
    matched_set = set()
    
    for yaml_file in sorted(CONFIG_DIR.glob('*.yaml')):
        matches = evaluate_strategy_file(str(yaml_file), full_fm)
        matched_list = matches['ticker'].tolist() if not matches.empty else []
        match_summary[yaml_file.stem] = matched_list
        matched_set.update(matched_list)
        print(f'Strategy {yaml_file.stem:22s}: {len(matched_list):2d} matches -> {matched_list}')
        
    pct = round(len(matched_set) / len(matrices) * 100, 1)
    print(f'\n=== OVERALL MATCH SUMMARY ===')
    print(f'Unique Stockbee tickers matching at least 1 strategy: {len(matched_set)} / {len(matrices)} ({pct}%)')
