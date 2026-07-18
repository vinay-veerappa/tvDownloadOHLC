"""
run.py — Main CLI runner for the WebUI validation framework.

Validates WebUI feature computations against local reference data.
Supports any feature that implements the FeatureValidator protocol.

Usage:
    # Validate a single filter combination
    python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --filter "LT|F|ST|F"

    # Validate all filter combinations for a session
    python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --all-filters

    # Validate all sessions and all filters
    python -m scripts.testing.run --feature profiler --ticker NQ1 --all-sessions --all-filters

    # List available features
    python -m scripts.testing.run --list-features

    # Output as JSON
    python -m scripts.testing.run --feature profiler --ticker NQ1 --session NY1 --all-filters --format json
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from .core.base import ValidationResult, ComparisonStatus
from .core.reporter import (
    format_validation_result,
    format_side_by_side,
    format_summary_table,
    MarkdownReporter,
    JsonReporter,
)
from .core.api_client import WebUIClient
from .features import get_validator, list_features, FEATURE_REGISTRY


def main():
    parser = argparse.ArgumentParser(
        description="WebUI Validation Framework — Compare local computation against WebUI backend",
    )
    parser.add_argument("--feature", default="profiler",
                        help=f"Feature to validate. Available: {list_features()}")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol")
    parser.add_argument("--session", default=None,
                        help="Target session (depends on feature)")
    parser.add_argument("--filter", default=None,
                        help="Single filter key to test (e.g. LT|F|ST|F)")
    parser.add_argument("--all-filters", action="store_true",
                        help="Test all filter combinations")
    parser.add_argument("--all-sessions", action="store_true",
                        help="Test all target sessions")
    parser.add_argument("--min-samples", type=int, default=5,
                        help="Minimum samples to include a filter combo")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="Output format")
    parser.add_argument("--detail", action="store_true",
                        help="Show side-by-side comparison for a single filter combination")
    parser.add_argument("--list-features", action="store_true",
                        help="List available features and exit")
    parser.add_argument("--check-backend", action="store_true",
                        help="Check if WebUI backend is running")

    args = parser.parse_args()

    # ── List features ──
    if args.list_features:
        print("Available features:")
        for name in list_features():
            v = get_validator(name)
            print(f"  {name}: {v.description}")
            print(f"    Tickers: {v.get_tickers()}")
            print(f"    Sessions: {v.get_target_sessions()}")
        return

    # ── Check backend ──
    if args.check_backend:
        client = WebUIClient()
        if client.health_check():
            print("✅ WebUI backend is running")
        else:
            print("❌ WebUI backend is NOT running (start with start_api.bat)")
        return

    # ── Get validator ──
    try:
        validator = get_validator(args.feature)
    except KeyError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # ── Check backend health ──
    client = WebUIClient()
    if not client.health_check():
        print("❌ WebUI backend is not running. Start it with start_api.bat first.")
        sys.exit(1)

    # ── Determine sessions and filters ──
    if args.session:
        target_sessions = [args.session]
    elif args.all_sessions:
        target_sessions = validator.get_target_sessions()
    else:
        target_sessions = [validator.get_target_sessions()[2]]  # Default: NY1

    if args.filter:
        filter_keys = [args.filter]
    elif args.all_filters:
        filter_keys = None  # Will get all from validator
    else:
        filter_keys = ["LT|F|ST|F"]  # Default demo filter

    # ── Run validation ──
    if args.format != "json":
        print(f"Validating feature '{args.feature}' for {args.ticker}...")
        print(f"Target sessions: {target_sessions}")
        print(f"Filters: {'ALL' if filter_keys is None else filter_keys}")
        print(f"Min samples: {args.min_samples}")
        print("=" * 60)
        print()

    all_results: List[ValidationResult] = []

    for target_session in target_sessions:
        if filter_keys is None:
            keys = validator.get_filter_keys(args.ticker, target_session, args.min_samples)
        else:
            keys = filter_keys

        for fk in keys:
            result = validator.validate(args.ticker, target_session, fk)
            all_results.append(result)

    # ── Output ──
    if args.format == "json":
        reporter = JsonReporter()
        print(reporter.generate(all_results))
    elif args.detail and len(all_results) == 1:
        # Side-by-side comparison for a single filter
        print(format_side_by_side(all_results[0]))
    else:
        # Detailed results
        for r in all_results:
            print(format_validation_result(r))
            print()

        # Summary
        print(format_summary_table(all_results))


if __name__ == "__main__":
    main()
