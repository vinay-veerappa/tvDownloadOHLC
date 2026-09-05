"""Autonomous Multi-Source Strategy Harvester CLI.

Crawls YouTube, TradingView, Quantpedia, and GitHub for trading strategies,
scores each candidate against the 100-point triage rubric, and exports
backlog-ready candidate cards.

Usage:
    python -m scripts.mining.harvest_all --channels all --archetypes mean_reversion,opening_range
    python -m scripts.mining.harvest_all --channels tradingview --archetypes all --max 10
"""
from __future__ import annotations

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.mining.config import DATA_DIR, ARCHETYPE_QUERIES
from scripts.mining.youtube_miner import harvest_youtube
from scripts.mining.tradingview_miner import harvest_tradingview
from scripts.mining.quantpedia_miner import harvest_quantpedia
from scripts.mining.github_miner import harvest_github
from scripts.mining.futures_io_miner import harvest_futures_io
from scripts.mining.babypips_miner import harvest_babypips
from scripts.mining.reddit_miner import harvest_reddit
from scripts.mining.triage import StrategyTriage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("Harvester")


def run_harvest(
    channels: List[str],
    archetypes: List[str],
    max_per_source: int = 10,
) -> Dict[str, Any]:
    """Execute harvesting across requested channels and archetypes."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_harvested: List[Dict[str, Any]] = []

    for arch in archetypes:
        log.info(f"=== Starting Harvesting for Archetype: '{arch}' ===")

        if "youtube" in channels:
            try:
                yt_items = harvest_youtube(arch, max_videos=max_per_source)
                all_harvested.extend(yt_items)
            except Exception as e:
                log.error(f"YouTube miner failed for {arch}: {e}")

        if "tradingview" in channels:
            try:
                tv_items = harvest_tradingview(arch, max_strategies=max_per_source)
                all_harvested.extend(tv_items)
            except Exception as e:
                log.error(f"TradingView miner failed for {arch}: {e}")

        if "quantpedia" in channels:
            try:
                qp_items = harvest_quantpedia(arch, max_strategies=max_per_source)
                all_harvested.extend(qp_items)
            except Exception as e:
                log.error(f"Quantpedia miner failed for {arch}: {e}")

        if "github" in channels:
            try:
                gh_items = harvest_github(arch, max_repos=max_per_source)
                all_harvested.extend(gh_items)
            except Exception as e:
                log.error(f"GitHub miner failed for {arch}: {e}")

        if "babypips" in channels:
            try:
                bp_items = harvest_babypips(arch)
                all_harvested.extend(bp_items)
            except Exception as e:
                log.error(f"BabyPips miner failed for {arch}: {e}")

        if "reddit" in channels:
            try:
                rd_items = harvest_reddit(arch)
                all_harvested.extend(rd_items)
            except Exception as e:
                log.error(f"Reddit miner failed for {arch}: {e}")

    if "futures_io" in channels:
        try:
            fio_items = harvest_futures_io(max_items=max_per_source)
            all_harvested.extend(fio_items)
        except Exception as e:
            log.error(f"Futures.io miner failed: {e}")

    # Triage and score all harvested items
    log.info(f"=== Triaging {len(all_harvested)} Total Harvested Candidates ===")
    admitted = []
    rejected = []
    summary_records = []

    cards_md = ["# Automated Strategy Harvest — Candidate Triage\n"]

    for item in all_harvested:
        score, score_breakdown, is_pass = StrategyTriage.evaluate(item)
        rec = {
            "title": item.get("title"),
            "source": item.get("source"),
            "archetype": item.get("archetype"),
            "url": item.get("url"),
            "total_score": score,
            "breakdown": score_breakdown,
            "admitted": is_pass,
        }
        summary_records.append(rec)

        if is_pass:
            admitted.append(rec)
            card = StrategyTriage.format_backlog_card(item, score)
            cards_md.append(card + "\n---\n")
        else:
            rejected.append(rec)

    # Export summaries
    summary_path = DATA_DIR / "triage_summary.json"
    summary_path.write_text(json.dumps(summary_records, indent=2), encoding="utf-8")

    cards_path = DATA_DIR / "backlog_candidates.md"
    cards_path.write_text("\n".join(cards_md), encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"HARVEST COMPLETE:")
    print(f"  Total Candidates Scraped: {len(all_harvested)}")
    print(f"  Admitted to Backlog (>=70): {len(admitted)}")
    print(f"  Rejected: {len(rejected)}")
    print(f"  Summary JSON: {summary_path}")
    print(f"  Markdown Cards: {cards_path}")
    print("=" * 70 + "\n")

    return {
        "total": len(all_harvested),
        "admitted": len(admitted),
        "rejected": len(rejected),
        "summary_file": str(summary_path),
        "cards_file": str(cards_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Autonomous Multi-Source Strategy Harvester")
    parser.add_argument(
        "--channels",
        default="all",
        help="Comma-separated channels: youtube,tradingview,quantpedia,github,all (default: all)",
    )
    parser.add_argument(
        "--archetypes",
        default="all",
        help="Comma-separated archetypes: mean_reversion,opening_range,ema_pullback,squeeze_breakout,ict_smc,all",
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=5,
        help="Max items per channel per archetype (default: 5)",
    )
    args = parser.parse_args()

    all_chans = ["youtube", "tradingview", "quantpedia", "github", "babypips", "reddit", "futures_io"]
    selected_chans = all_chans if args.channels == "all" else [c.strip().lower() for c in args.channels.split(",")]

    all_archs = list(ARCHETYPE_QUERIES.keys())
    selected_archs = all_archs if args.archetypes == "all" else [a.strip().lower() for a in args.archetypes.split(",")]

    run_harvest(
        channels=selected_chans,
        archetypes=selected_archs,
        max_per_source=args.max_per_source,
    )


if __name__ == "__main__":
    main()
