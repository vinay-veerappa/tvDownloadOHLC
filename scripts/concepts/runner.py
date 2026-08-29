"""Universal Concept Runner CLI

Execute any concept independently or run the production master brain synthesis.
Strictly separates verified production engines from development scaffolds.
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
    parser.add_argument("--concept", default=None, help="Concept name to run independently")
    parser.add_argument("--all", action="store_true", help="Run all production concepts in master synthesis")
    parser.add_argument("--include-scaffolds", action="store_true", help="Include development scaffolds in --all run")
    parser.add_argument("--list", action="store_true", help="List all available concepts with lifecycle status")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--time", default="08:45", help="Cutoff time HH:MM (default: 08:45)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if args.list:
        print("")
        print("🏛️ Available Analytical Concept Providers in Trading Second Brain:")
        print("-" * 85)
        for c in ConceptRegistry.list_concepts(include_scaffolds=True):
            status_tag = f"[{c['status'].upper()}]" if c['is_production'] else f"[{c['status'].upper()} / NOT PROD]"
            print(f"  • {c['name']:<22} {status_tag:<20} (v{c['version']}) : {c['description']}")
        print("-" * 85)
        print("")
        return

    if args.all:
        results = ConceptRegistry.execute_all(
            ticker=args.ticker,
            target_date=args.date,
            cutoff_time=args.time,
            include_scaffolds=args.include_scaffolds,
        )
        if args.json:
            out = {k: v.data for k, v in results.items()}
            print(json.dumps(out, indent=2, default=str))
        else:
            print("")
            print("=" * 70)
            print(f"  🧠 MASTER SECOND BRAIN CONFLUENCE: {args.ticker} ({args.date or 'Today'})")
            print("=" * 70)
            print("")
            for k, payload in results.items():
                if not payload.is_success:
                    print(f"❌ FAILED PROVIDER [{payload.name}]: {payload.error_message}")
                else:
                    print(payload.markdown_report)
                print("")
                print("=" * 70)
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
            if not payload.is_success:
                print(f"❌ FAILED: {payload.error_message}")
            else:
                print(payload.markdown_report)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
