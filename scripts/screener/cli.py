"""
cli.py
======
Main CLI runner for trade_screener engine.
Usage:
  python -m scripts.screener.cli --strategy qullamaggie_hft --limit 50
  python -m scripts.screener.cli --strategy minervini_trend
"""
import os
import argparse
import logging
from pathlib import Path
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

from scripts.screener.core.funnel import fetch_finviz_candidates
from scripts.screener.core.data_policy import prepare_price_series
from scripts.screener.core.features import build_feature_matrix
from scripts.screener.core.regime import get_market_regime
from scripts.screener.core.yaml_evaluator import evaluate_strategy_file
from scripts.screener.tracker.setup_logger import log_setups_to_duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("screener_cli")

CONFIG_DIR = Path(__file__).resolve().parent / "config"


def run_screener(strategy_id: str = "qullamaggie_hft", limit: int = 50, log_duckdb: bool = True) -> pd.DataFrame:
    """
    Full pipeline runner:
    Regime Gatekeeper -> Finviz Funnel -> yfinance Vector Fetch -> Feature Matrix -> YAML Rules -> DuckDB
    """
    log.info(f"--- STARTING TRADE SCREENER [Strategy: {strategy_id}] ---")
    
    # 1. Global Market Regime Gatekeeper
    regime = get_market_regime()
    log.info(f"Market Regime: {regime.status} (SPY: ${regime.spy_close}, Macro High-Risk: {regime.is_macro_high_risk})")
    
    if regime.status == "BEAR_PROTECTIVE" and "short" not in strategy_id:
        log.warning("Market Regime is BEAR_PROTECTIVE. Long breakouts stand down.")

    # 2. Stage 1 Universe Discovery
    candidates = fetch_finviz_candidates(limit=limit)
    if not candidates:
        log.info("No candidates returned from funnel.")
        return pd.DataFrame()

    tickers = [c["ticker"] for c in candidates]
    log.info(f"Processing {len(tickers)} candidates...")

    # 3. Stage 2 Vectorized Market Data Fetch
    all_matrices = []
    if yf is not None and len(tickers) > 0:
        try:
            data = yf.download(tickers, period="6m", interval="1d", group_by="ticker", progress=False, threads=True)
            for t in tickers:
                try:
                    df = data[t].dropna() if len(tickers) > 1 else data.dropna()
                    if len(df) < 20:
                        continue
                    split_df, tr_df = prepare_price_series(df)
                    fm = build_feature_matrix(split_df, ticker=t)
                    if not fm.empty:
                        all_matrices.append(fm)
                except Exception as e:
                    continue
        except Exception as e:
            log.error(f"yfinance batch download failed: {e}")

    if not all_matrices:
        log.info("No valid feature matrices created.")
        return pd.DataFrame()

    full_matrix = pd.concat(all_matrices, ignore_index=True)

    # 4. Stage 3 YAML Strategy Rule Evaluator
    yaml_file = CONFIG_DIR / f"{strategy_id}.yaml"
    if not yaml_file.exists():
        yaml_file = CONFIG_DIR / "qullamaggie_hft.yaml"

    matches = evaluate_strategy_file(str(yaml_file), full_matrix)
    if matches.empty:
        log.info("No stocks matched the strategy rules.")
        return pd.DataFrame()

    matches["market_regime"] = regime.status
    log.info(f"MATCHED {len(matches)} CANDIDATES:")
    for _, row in matches.iterrows():
        log.info(f" -> {row['ticker']}: Close=${row['Close']:.2f} | ADR%={row['adr_20_pct']:.2f}% | Dist10EMA={row['dist_10ema_pct']:.2f}% | RVOL={row['rvol_20']:.2f}x")

    # 5. Stage 4 DuckDB Setup Logger
    if log_duckdb:
        log_setups_to_duckdb(matches)

    return matches


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run trade_screener engine.")
    parser.add_argument("--strategy", type=str, default="qullamaggie_hft", help="Strategy YAML config ID (e.g. qullamaggie_hft, minervini_trend, stockbee_momentum).")
    parser.add_argument("--limit", type=int, default=50, help="Number of universe candidates to fetch.")
    args = parser.parse_args()

    run_screener(strategy_id=args.strategy, limit=args.limit)
