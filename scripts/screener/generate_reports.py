"""
generate_reports.py
===================
Generates multi-strategy screener comparison matrix CSV and export watchlists
formatted for TradingView and Thinkorswim (TOS).

Outputs:
1. reports/screener/strategy_comparison_matrix.csv
2. reports/screener/tradingview_watchlist.csv
3. reports/screener/thinkorswim_watchlist.csv
"""
import os
import logging
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any

from scripts.screener.core.funnel import fetch_finviz_candidates
from scripts.screener.core.data_policy import prepare_price_series
from scripts.screener.core.features import build_feature_matrix
from scripts.screener.core.regime import get_market_regime
from scripts.screener.core.yaml_evaluator import evaluate_strategy_file, load_yaml_strategy
from scripts.screener.core.industry_rs import calculate_industry_rs
from scripts.screener.core.float_validator import validate_float
from scripts.market_data.sync_earnings_calendar import has_upcoming_earnings

try:
    import yfinance as yf
except ImportError:
    yf = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("screener_reports")

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(__file__).resolve().parent / "config"
OUTPUT_DIR = REPO_ROOT / "reports" / "screener"


from scripts.screener.core.provider import fetch_equity_daily_batch

def generate_screener_reports(
    limit: int = 100,
    provider: str = "yfinance",
    fallback: str = "schwab"
) -> Dict[str, str]:
    """
    Runs all available YAML strategies against the universe, creates comparison matrix
    and exports TradingView / TOS watchlists.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Discover all YAML strategies
    strategy_files = sorted(list(CONFIG_DIR.glob("*.yaml")))
    strategy_ids = [p.stem for p in strategy_files]
    log.info(f"Discovered {len(strategy_ids)} strategies: {strategy_ids}")

    # 1. Fetch Universe Candidates & Industry RS
    candidates = fetch_finviz_candidates(limit=limit)
    if not candidates:
        log.error("No candidates found.")
        return {}

    industry_rs_map = calculate_industry_rs()
    cand_map = {c["ticker"]: c for c in candidates}
    tickers = list(cand_map.keys())
    log.info(f"Building feature matrices for {len(tickers)} universe candidates...")

    # 2. Vectorized Feature Matrix Construction (via Provider & Local Parquet Cache)
    all_matrices = []
    if len(tickers) > 0:
        ticker_dfs = fetch_equity_daily_batch(tickers, provider=provider, fallback=fallback)
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
                continue

    if not all_matrices:
        log.error("No feature matrices could be constructed.")
        return {}

    full_matrix = pd.concat(all_matrices, ignore_index=True)

    # 3. Evaluate each strategy and build match table
    matches_by_strategy = {}
    matched_ticker_set = set()

    for s_id in strategy_ids:
        yaml_file = CONFIG_DIR / f"{s_id}.yaml"
        matches = evaluate_strategy_file(str(yaml_file), full_matrix)
        if not matches.empty:
            matched_tickers = set(matches["ticker"].tolist())
            matches_by_strategy[s_id] = matched_tickers
            matched_ticker_set.update(matched_tickers)
        else:
            matches_by_strategy[s_id] = set()

    log.info(f"Total unique tickers matching at least 1 strategy: {len(matched_ticker_set)}")

    # 4. Construct Strategy Comparison Matrix DataFrame
    rows = []
    # If no ticker matched any strict rule, report all candidates evaluated for visibility
    target_tickers = sorted(list(matched_ticker_set)) if matched_ticker_set else tickers

    for t in target_tickers:
        cand = cand_map.get(t, {})
        # Find latest close from full_matrix
        t_rows = full_matrix[full_matrix["ticker"] == t]
        close_price = t_rows["close"].iloc[-1] if not t_rows.empty else cand.get("price", 0.0)
        
        matched_strats = []
        row_dict = {
            "ticker": t,
            "company": cand.get("company", ""),
            "sector": cand.get("sector", ""),
            "industry": cand.get("industry", ""),
            "close": round(close_price, 2),
        }
        
        for s_id in strategy_ids:
            is_match = 1 if t in matches_by_strategy[s_id] else 0
            row_dict[s_id] = is_match
            if is_match:
                matched_strats.append(s_id)

        row_dict["matched_strategies_count"] = len(matched_strats)
        row_dict["matched_strategies_list"] = ", ".join(matched_strats) if matched_strats else "None"
        rows.append(row_dict)

    matrix_df = pd.DataFrame(rows)
    
    # Reorder columns: ticker info, matched count/list, then each strategy 1/0 column
    base_cols = ["ticker", "company", "sector", "industry", "close", "matched_strategies_count", "matched_strategies_list"]
    col_order = base_cols + [c for c in matrix_df.columns if c not in base_cols]
    matrix_df = matrix_df[col_order]

    # SORT BY MATCHED STRATEGIES COUNT DESCENDING (Common subset at top!)
    matrix_df.sort_values(by=["matched_strategies_count", "ticker"], ascending=[False, True], inplace=True)

    # 5. Export Strategy Comparison Matrix CSV
    matrix_csv_path = OUTPUT_DIR / "strategy_comparison_matrix.csv"
    matrix_df.to_csv(matrix_csv_path, index=False)
    log.info(f"Saved strategy comparison matrix CSV to {matrix_csv_path}")

    # 6. Export TradingView Watchlist CSV
    tv_csv_path = OUTPUT_DIR / "tradingview_watchlist.csv"
    with open(tv_csv_path, "w", encoding="utf-8") as f:
        for t in matrix_df["ticker"].tolist():
            f.write(f"{t}\n")
    log.info(f"Saved TradingView watchlist CSV to {tv_csv_path}")

    # 7. Export Thinkorswim (TOS) Watchlist CSV
    tos_csv_path = OUTPUT_DIR / "thinkorswim_watchlist.csv"
    with open(tos_csv_path, "w", encoding="utf-8") as f:
        f.write("Symbol\n")
        for t in matrix_df["ticker"].tolist():
            f.write(f"{t}\n")
    log.info(f"Saved Thinkorswim (TOS) watchlist CSV to {tos_csv_path}")

    return {
        "comparison_matrix": str(matrix_csv_path),
        "tradingview_watchlist": str(tv_csv_path),
        "thinkorswim_watchlist": str(tos_csv_path),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate stock screener reports & watchlists.")
    parser.add_argument("--limit", type=int, default=100, help="Candidate limit.")
    args = parser.parse_args()

    paths = generate_screener_reports(limit=args.limit)
    print("Report generation complete:")
    for k, v in paths.items():
        print(f" - {k}: {v}")
