"""Universal Concept Runner CLI

Execute any concept independently or run the unified master brain synthesis.
"""
from __future__ import annotations

import sys
import json
import argparse
import logging
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure stdout handles unicode emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from scripts.concepts.registry import ConceptRegistry
import scripts.concepts.providers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    parser = argparse.ArgumentParser(description="Universal Trading Concept Runner")
    parser.add_argument("--concept", default=None, help="Concept name (candle_science, htf_macro, weekly_outlook, p12_scenarios, session_budget, signature_setups, aln_levels, herman_probabilities)")
    parser.add_argument("--all", action="store_true", help="Run all registered concepts")
    parser.add_argument("--list", action="store_true", help="List all available concepts")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--time", default="08:45", help="Cutoff time HH:MM (default: 08:45)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if args.list:
        print("")
        print("🏛️ Available Analytical Concept Providers in Trading Second Brain:")
        print("-" * 75)
        for c in ConceptRegistry.list_concepts():
            print(f"  • {c['name']:<22} : {c['description']}")
        print("-" * 75)
        print("")
        return

    if args.all:
        results = ConceptRegistry.execute_all(ticker=args.ticker, target_date=args.date, cutoff_time=args.time)
        if args.json:
            out = {k: v.data for k, v in results.items()}
            print(json.dumps(out, indent=2, default=str))
        else:
            print("")
            print("=" * 65)
            print(f"  🧠 MASTER SECOND BRAIN CONFLUENCE: {args.ticker} ({args.date or 'Today'})")
            print("=" * 65)
            print("")
            for k, payload in results.items():
                print(payload.markdown_report)
                print("")
                print("=" * 65)
                print("")
        return

    if args.concept:
        payload = ConceptRegistry.execute_concept(
            name=args.concept,
            ticker=args.ticker,
            target_date=args.date,
            cutoff_time=args.time
        )
        if args.json:
            print(json.dumps(payload.data, indent=2, default=str))
        else:
            print(payload.markdown_report)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
