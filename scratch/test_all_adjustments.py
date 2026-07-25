import sys
sys.path.insert(0, '.')
import pandas as pd
import yfinance as yf
from pathlib import Path
from scripts.screener.core.data_policy import prepare_price_series
from scripts.screener.core.features import build_feature_matrix
from scripts.screener.core.yaml_evaluator import evaluate_strategy_file

CONFIG_DIR = Path('scripts/screener/config')

sample_universe = [
    'NVDA', 'AAPL', 'MSFT', 'AMD', 'META', 'TSLA', 'AMZN', 'GOOGL', 'AVGO', 'SMCI',
    'ARM', 'PLTR', 'PANW', 'NET', 'CRWD', 'SNOW', 'DDOG', 'ZS', 'MDB', 'CELH',
    'AGEN', 'AMWL', 'ATAI', 'CDNA', 'CHRN', 'COAG', 'LCID', 'MAN', 'NXTC', 'PESI',
    'PYPL', 'QBTZ', 'RCEL', 'RHI', 'VEEE', 'XNCR', 'GORO', 'FBRX', 'SKYQ', 'IONZ',
    'JNJ', 'PG', 'KO', 'PEP', 'JPM', 'BAC', 'WFC', 'XOM', 'CVX', 'CAT',
    'DE', 'UNH', 'LLY', 'ABBV', 'MRK', 'PFE', 'HD', 'LOW', 'COST', 'WMT'
]

data = yf.download(sample_universe, period='6mo', interval='1d', group_by='ticker', progress=False)

matrices = []
for t in sample_universe:
    try:
        df = data[t].dropna() if len(sample_universe) > 1 else data.dropna()
        if len(df) < 20: continue
        split_df, tr_df = prepare_price_series(df)
        fm = build_feature_matrix(split_df, ticker=t, tr_df=tr_df, industry_rs_rank=85.0)
        if not fm.empty:
            matrices.append(fm)
    except Exception:
        pass

full_fm = pd.concat(matrices, ignore_index=True)

print("=== SCREENER STRATEGY AUDIT RESULTS ===")
for yaml_file in sorted(CONFIG_DIR.glob('*.yaml')):
    matches = evaluate_strategy_file(str(yaml_file), full_fm)
    matched_tickers = matches['ticker'].tolist() if not matches.empty else []
    print(f"Strategy {yaml_file.stem:22s}: {len(matched_tickers):2d} matches -> {matched_tickers[:8]}")
