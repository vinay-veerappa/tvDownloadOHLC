import os
import sys
import argparse
import webbrowser
from datetime import date
from pathlib import Path
from typing import Optional, List
import pandas as pd

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from scripts.csp_ranking.tos_parser import parse_tos_scanner_csv, TOSOptionContract
from scripts.csp_ranking.finviz_client import FinvizClient, FinvizTickerProfile
from scripts.csp_ranking.technicals import TechnicalAnalyzer, TechnicalMetrics
from scripts.csp_ranking.scoring_engine import ScoredCandidate, rank_csp_candidates
from scripts.csp_ranking.trajectory_analyzer import run_autonomous_deep_review
from scripts.csp_ranking.dashboard import render_terminal_dashboard, generate_html_dashboard
from scripts.csp_ranking.llm_reviewer import generate_llm_csp_review_prompt
from scripts.csp_ranking.live_scanner import scan_live_market
from scripts.csp_ranking.schwab_scanner import scan_schwab_options

EXPORTS_DIR = Path("data/csp_ranking")


def find_latest_tos_export(search_dirs: Optional[List[Path]] = None) -> Optional[Path]:
    """
    Finds the most recently modified TOS Watchlist/Scanner CSV export in user Downloads or data folders.
    """
    if search_dirs is None:
        user_home = Path.home()
        search_dirs = [
            user_home / "Downloads",
            Path("data"),
            Path("data/live"),
            Path("."),
        ]

    candidate_files = []
    for d in search_dirs:
        if d.exists() and d.is_dir():
            for f in d.glob("*.csv"):
                fname = f.name.lower()
                if "scanner" in fname or "watchlist" in fname or "tos" in fname or "option" in fname:
                    candidate_files.append((f.stat().st_mtime, f))
                else:
                    candidate_files.append((f.stat().st_mtime - 86400, f))

    if not candidate_files:
        return None

    candidate_files.sort(key=lambda x: x[0], reverse=True)
    return candidate_files[0][1]


def run_pipeline(
    csv_path: Optional[str | Path] = None,
    live_scan: bool = False,
    schwab_scan: bool = False,
    min_volume: int = 10,
    max_spread_pct: float = 50.0,
    force_refresh: bool = False,
    open_browser: bool = False,
):
    """
    Executes the end-to-end CSP ranking pipeline with full multi-quarter deep analysis.
    """
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    scan_source_name = ""

    # 1. Resolve Contracts (Schwab API vs Autonomous Live vs CSV File)
    if schwab_scan:
        try:
            contracts = scan_schwab_options()
            scan_source_name = "Schwab Trader API Live Scan"
        except Exception as e:
            print(f"⚠️ Schwab API error ({e}). Falling back to autonomous live scanner...")
            contracts = scan_live_market()
            scan_source_name = "Live Autonomous Market Scan"
    elif live_scan:
        contracts = scan_live_market()
        scan_source_name = "Live Autonomous Market Scan"
    else:
        if csv_path:
            target_csv = Path(csv_path)
        else:
            target_csv = find_latest_tos_export()

        if not target_csv or not target_csv.exists():
            print(f"❌ Error: No ThinkorSwim CSV export found. Please provide a path or run with --live or --schwab.")
            sys.exit(1)

        print(f"\n📂 Loading ThinkorSwim scan from: {target_csv.resolve()}")
        scan_source_name = str(target_csv.name)
        try:
            contracts = parse_tos_scanner_csv(target_csv, scan_date=today)
        except Exception as e:
            print(f"❌ Error parsing CSV: {e}")
            sys.exit(1)

    if not contracts:
        print(f"⚠️ Warning: No valid option contracts found in {target_csv}")
        sys.exit(0)

    unique_tickers = sorted(list(set(c.ticker for c in contracts)))
    print(f"✅ Ingested {len(contracts)} option contracts across {len(unique_tickers)} unique tickers.")

    # 3. Data Enrichment (Finviz & Technicals)
    finviz_client = FinvizClient()
    tech_analyzer = TechnicalAnalyzer(benchmark_symbol="SPY")

    print(f"🔍 Enriching market data & fundamentals for {len(unique_tickers)} tickers...")
    profiles: dict[str, Optional[FinvizTickerProfile]] = {}
    technicals: dict[str, TechnicalMetrics] = {}

    for ticker in unique_tickers:
        prof = finviz_client.get_ticker_profile(ticker, force_refresh=force_refresh)
        profiles[ticker] = prof

        fallback_p = prof.price if prof else 0.0
        tech = tech_analyzer.analyze_ticker(ticker, fallback_price=fallback_p)
        technicals[ticker] = tech

    print(f"✅ Data enrichment complete for all {len(unique_tickers)} tickers.")

    # 4. Score Base Candidates
    scored_all_raw: List[ScoredCandidate] = []
    for c in contracts:
        cand = ScoredCandidate(
            contract=c,
            profile=profiles.get(c.ticker),
            technicals=technicals.get(c.ticker),
            scan_date=today,
            min_volume=min_volume,
            max_spread_pct=max_spread_pct,
        )
        scored_all_raw.append(cand)

    ranked_per_ticker = rank_csp_candidates(scored_all_raw, one_contract_per_ticker=True)
    passed_finalists = [c for c in ranked_per_ticker if c.is_passed_hard_filters]

    # 5. Autonomous Deep Multi-Quarter Trajectory Review
    print(f"🧠 Running Autonomous Multi-Quarter Trajectory & Qualitative Review...")
    deep_analyses = run_autonomous_deep_review(passed_finalists)
    print(f"✅ Deep review complete across all {len(deep_analyses)} qualified finalists.")

    # 6. Export to CSV
    export_csv_path = EXPORTS_DIR / f"csp_ranked_{today.strftime('%Y-%m-%d')}.csv"
    records = [a.to_dict() for a in deep_analyses]
    df_export = pd.DataFrame(records)
    df_export.to_csv(export_csv_path, index=False)
    print(f"💾 Saved full CSV results to: {export_csv_path}")

    # 7. Generate Standalone LLM Review Prompt Payload
    prompt_content = generate_llm_csp_review_prompt(passed_finalists, scan_date=today)
    prompt_file_path = EXPORTS_DIR / f"llm_review_prompt_{today.strftime('%Y-%m-%d')}.md"
    with open(prompt_file_path, "w", encoding="utf-8") as f:
        f.write(prompt_content)

    # 8. Render Terminal & HTML Dashboards
    render_terminal_dashboard(
        all_candidates=scored_all_raw,
        deep_analyses=deep_analyses,
        scan_source=scan_source_name,
    )
    
    html_path = generate_html_dashboard(
        all_candidates=scored_all_raw,
        deep_analyses=deep_analyses,
        scan_source=scan_source_name,
    )
    print(f"🌐 Full Interactive Analysis Dashboard created at: {html_path.resolve()}")

    if open_browser:
        try:
            webbrowser.open(html_path.resolve().as_uri())
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Cash-Secured Put (CSP) Ranking & Scoring Engine")
    parser.add_argument("--csv", type=str, default=None, help="Path to ThinkorSwim Watchlist/Scanner CSV export (auto-detected if omitted)")
    parser.add_argument("--live", action="store_true", help="Run autonomous live market options scan without needing ThinkorSwim")
    parser.add_argument("--schwab", action="store_true", help="Run live scan directly via Charles Schwab Developer API")
    parser.add_argument("--min-volume", type=int, default=10, help="Minimum volume threshold for hard filter (default: 10)")
    parser.add_argument("--max-spread", type=float, default=50.0, help="Maximum spread percentage for hard filter (default: 50.0%)")
    parser.add_argument("--refresh", action="store_true", help="Force fresh download of fundamental and technical data")
    parser.add_argument("--open-browser", action="store_true", help="Automatically open HTML report in default browser")
    
    args = parser.parse_args()

    run_pipeline(
        csv_path=args.csv,
        live_scan=args.live,
        schwab_scan=args.schwab,
        min_volume=args.min_volume,
        max_spread_pct=args.max_spread,
        force_refresh=args.refresh,
        open_browser=args.open_browser,
    )


if __name__ == "__main__":
    main()
