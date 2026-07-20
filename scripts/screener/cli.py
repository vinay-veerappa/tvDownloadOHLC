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
from scripts.screener.core.industry_rs import calculate_industry_rs
from scripts.screener.core.float_validator import validate_float
from scripts.market_data.sync_earnings_calendar import has_upcoming_earnings
from scripts.screener.tracker.setup_logger import log_setups_to_duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("screener_cli")

CONFIG_DIR = Path(__file__).resolve().parent / "config"


def run_screener(strategy_id: str = "qullamaggie_hft", limit: int = 50, log_duckdb: bool = True) -> pd.DataFrame:
    """
    Full pipeline runner:
    Regime Gatekeeper -> Finviz Funnel & Industry RS -> yfinance Vector Fetch -> Feature Matrix -> YAML Rules -> DuckDB
    """
    log.info(f"--- STARTING TRADE SCREENER [Strategy: {strategy_id}] ---")
    
    # 1. Global Market Regime Gatekeeper
    regime = get_market_regime()
    log.info(f"Market Regime: {regime.status} (SPY: ${regime.spy_close}, Macro High-Risk: {regime.is_macro_high_risk})")
    
    if regime.is_macro_high_risk:
        log.warning("MACRO HIGH RISK OVERLAY ACTIVE (FOMC/CPI/NFP today): Recommend halving position sizes and tightening stops.")
        if strategy_id in ["qullamaggie_hft", "stockbee_ep", "zanger_volume_surge"]:
            log.warning(f"Strategy {strategy_id} is highly sensitive to macro volatility. Consider skipping today.")
            
    if regime.status == "BEAR_PROTECTIVE" and "short" not in strategy_id:
        log.warning("Market Regime is BEAR_PROTECTIVE. Long breakouts stand down.")

    # 2. Stage 1 Universe Discovery & Industry RS
    candidates = fetch_finviz_candidates(limit=limit)
    if not candidates:
        log.info("No candidates returned from funnel.")
        return pd.DataFrame()

    industry_rs_map = calculate_industry_rs()
    cand_map = {c["ticker"]: c for c in candidates}
    tickers = list(cand_map.keys())
    log.info(f"Processing {len(tickers)} candidates...")

    # 3. Stage 2 Vectorized Market Data Fetch & Feature Matrix Construction
    all_matrices = []
    if yf is not None and len(tickers) > 0:
        try:
            data = yf.download(tickers, period="6mo", interval="1d", group_by="ticker", progress=False, threads=True)
            
            ticker_dfs = {}
            if len(tickers) == 1:
                t = tickers[0]
                if not data.empty:
                    ticker_dfs[t] = data.dropna()
            else:
                for t in tickers:
                    try:
                        if hasattr(data.columns, 'levels') and t in data.columns.levels[0]:
                            df_t = data[t].dropna()
                            if not df_t.empty and len(df_t) >= 20:
                                ticker_dfs[t] = df_t
                    except Exception:
                        continue

            for t, df in ticker_dfs.items():
                try:
                    cand = cand_map.get(t, {})
                    finviz_float = cand.get("float", 0.0)
                    float_info = validate_float(finviz_float, None)
                    
                    ind_name = cand.get("industry", "")
                    ind_rs = industry_rs_map.get(ind_name, 50.0)
                    has_earnings = has_upcoming_earnings(t, window_days=7)
                    
                    split_df, tr_df = prepare_price_series(df)
                    fm = build_feature_matrix(
                        split_df,
                        ticker=t,
                        tr_df=tr_df,
                        industry_rs_rank=ind_rs,
                        has_upcoming_earnings=has_earnings,
                        float_info=float_info
                    )
                    if not fm.empty:
                        all_matrices.append(fm)
                except Exception as e:
                    log.warning(f"Error processing feature matrix for {t}: {e}")
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
        close_price = row.get("close", row.get("Close", 0.0))
        log.info(f" -> {row['ticker']}: Close=${close_price:.2f} | ADR%={row['adr_20_pct']:.2f}% | Dist10EMA={row['dist_10ema_pct']:.2f}% | RVOL={row['rvol_20']:.2f}x | IndRS={row['industry_rs_rank']:.1f}")

    # 5. Stage 4 DuckDB Setup Logger
    if log_duckdb:
        log_setups_to_duckdb(matches)

    return matches



if __name__ == "__main__":
    from scripts.screener.generate_reports import generate_screener_reports

    parser = argparse.ArgumentParser(description="Run trade_screener engine.")
    parser.add_argument("--strategy", type=str, default="qullamaggie_hft", help="Strategy YAML config ID (or 'all' to run all strategies and generate reports).")
    parser.add_argument("--limit", type=int, default=50, help="Number of universe candidates to fetch.")
    parser.add_argument("--report", action="store_true", help="Generate strategy comparison matrix & export watchlists (TradingView & Thinkorswim).")
    args = parser.parse_args()

    if args.report or args.strategy.lower() == "all":
        log.info("--- GENERATING MULTI-STRATEGY COMPARISON MATRIX & WATCHLIST REPORTS ---")
        paths = generate_screener_reports(limit=args.limit)
        log.info("Report generation complete:")
        for name, path in paths.items():
            log.info(f" -> {name}: {path}")
    else:
        run_screener(strategy_id=args.strategy, limit=args.limit)

