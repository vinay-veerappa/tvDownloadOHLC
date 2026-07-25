import sys
sys.path.insert(0, '.')
import pandas as pd
import yfinance as yf
from pathlib import Path
from scripts.screener.core.data_policy import prepare_price_series
from scripts.screener.core.features import build_feature_matrix
from scripts.screener.core.yaml_evaluator import evaluate_strategy_file

CONFIG_DIR = Path('scripts/screener/config')

# Sample universe of 60 liquid benchmark & momentum stocks across market caps & sectors
sample_universe = [
    # Tech & Momentum Leaders
    'NVDA', 'AAPL', 'MSFT', 'AMD', 'META', 'TSLA', 'AMZN', 'GOOGL', 'AVGO', 'SMCI',
    'ARM', 'PLTR', 'PANW', 'NET', 'CRWD', 'SNOW', 'DDOG', 'ZS', 'MDB', 'CELH',
    # High Beta Growth & Short-Term Swing Movers
    'AGEN', 'AMWL', 'ATAI', 'CDNA', 'CHRN', 'COAG', 'LCID', 'MAN', 'NXTC', 'PESI',
    'PYPL', 'QBTZ', 'RCEL', 'RHI', 'VEEE', 'XNCR', 'GORO', 'FBRX', 'SKYQ', 'IONZ',
    # Large Cap Defensive / Value / Income Setup Universe
    'JNJ', 'PG', 'KO', 'PEP', 'JPM', 'BAC', 'WFC', 'XOM', 'CVX', 'CAT',
    'DE', 'UNH', 'LLY', 'ABBV', 'MRK', 'PFE', 'HD', 'LOW', 'COST', 'WMT'
]

print(f"Fetching 2-year data for {len(sample_universe)} universe benchmark tickers...")
data = yf.download(sample_universe, period='2y', interval='1d', group_by='ticker', progress=False)


matrices = []
for t in sample_universe:
    try:
        df = data[t].dropna() if len(sample_universe) > 1 else data.dropna()
        if len(df) < 20: continue
        split_df, tr_df = prepare_price_series(df)
        fm = build_feature_matrix(split_df, ticker=t, tr_df=tr_df, industry_rs_rank=88.0)
        if not fm.empty:
            matrices.append(fm)
    except Exception as e:
        pass

if not matrices:
    print("Error: No feature matrices built.")
    sys.exit(1)

full_fm = pd.concat(matrices, ignore_index=True)
print(f"Successfully constructed feature matrices for {len(matrices)} tickers.\n")

audit_results = []
for yaml_file in sorted(CONFIG_DIR.glob('*.yaml')):
    matches = evaluate_strategy_file(str(yaml_file), full_fm)
    matched_tickers = matches['ticker'].tolist() if not matches.empty else []
    
    # Read rules from YAML
    with open(yaml_file, 'r', encoding='utf-8') as f:
        yaml_content = f.read()
    
    audit_results.append({
        'strategy_id': yaml_file.stem,
        'matches_count': len(matched_tickers),
        'matched_tickers': ', '.join(matched_tickers[:8]) + ('...' if len(matched_tickers) > 8 else ''),
        'rules_count': yaml_content.count('- name:')
    })

df_audit = pd.DataFrame(audit_results)
print("=== ALL 12 SCREENERS AUDIT BREAKDOWN ===")
print(df_audit.to_string(index=False))
