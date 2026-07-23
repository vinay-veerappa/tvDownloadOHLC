"""Integration test: Knowledge Bridge → Narrative Engine.

Tests whether KB-retrieved context improves the narrative cheat sheet.
Runs in two modes:
  1. test: Builds cheat sheet, retrieves KB context, prints both — no LLM call
  2. compare: Builds two narratives (with/without KB), prints side-by-side

Usage:
    # test mode (no LLM tokens, just shows cheat sheet + KB context)
    python -m scripts.knowledge_bridge.test_narrative --mode premarket --ticker ES1

    # compare mode (calls LLM twice — with and without KB context)
    python -m scripts.knowledge_bridge.test_narrative --mode premarket --ticker ES1 --compare
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Ensure project root on sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def check_kb_api(url: str = "http://127.0.0.1:8900") -> bool:
    """Check if the KB API is reachable."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok"
    except Exception:
        return False


def fetch_kb_context(cheat_sheet: str, kb_api_url: str = "http://127.0.0.1:8900") -> str:
    """Retrieve KB context for the cheat sheet via the KB API.

    Uses the same concept-trigger logic as kb_bridge.py but calls
    the KB API directly from the consumer repo.
    """
    import urllib.request

    # Concept triggers (mirrors kb_bridge.py CONCEPT_TRIGGERS)
    triggers = {
        "FVG": "fair value gap imbalance entry",
        "CSD": "change in state of delivery CSD entry",
        "MSS": "market structure shift MSS",
        "order block": "order block entry OB",
        "liquidity sweep": "liquidity sweep buy-side sell-side",
        "Judas": "Judas swing fake move London session",
        "Power of Three": "power of three accumulation manipulation distribution",
        "Po3": "power of three accumulation manipulation distribution",
        "MMXM": "market maker buy sell model MMXM",
        "Silver Bullet": "silver bullet entry window",
        "OTE": "optimal trade entry OTE",
        "killzone": "killzone trading session timing",
        "overnight session": "overnight session ONS profile trading",
        "premium": "premium discount dealing range",
        "discount": "premium discount dealing range",
        "PDH": "prior day high low reference level",
        "PDL": "prior day high low reference level",
        "midnight open": "midnight open reference level",
        "7 Rule": "Kish 7 Rules execution framework",
        "trendline": "trendline entry model",
        "breaker": "breaker block entry",
        "turtle soup": "turtle soup liquidity sweep",
        "CISD": "change in state of delivery CISD",
        "NWOG": "new week opening gap",
        "NDOG": "new day opening gap",
        "IPDA": "interbank price delivery algorithm",
        "draw on liquidity": "draw on liquidity DOL",
        "HOD": "high of day",
        "LOD": "low of day",
        "target": "target liquidity unfinished business",
        "stop": "stop placement invalidation",
    }

    # Detect concepts in cheat sheet
    cheat_lower = cheat_sheet.lower()
    found = {}
    for trigger, query in triggers.items():
        if trigger.lower() in cheat_lower:
            found[trigger] = query

    if not found:
        return ""

    # Search KB for each concept
    all_units = []
    seen_ids = set()
    max_context_chars = 2000

    for concept, query in found.items():
        try:
            body = json.dumps({
                "query": query,
                "k": 3,
            }).encode()
            req = urllib.request.Request(
                f"{kb_api_url}/search",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                # API returns {"results": [...]} or raw list
                if isinstance(data, dict) and "results" in data:
                    units = data["results"]
                elif isinstance(data, list):
                    units = data
                else:
                    units = []
                for u in units:
                    uid = u.get("unit_id", str(id(u)))
                    if uid not in seen_ids:
                        all_units.append(u)
                        seen_ids.add(uid)
        except Exception:
            continue

    if not all_units:
        return ""

    # Format as context block
    lines = []
    total = 0
    for u in all_units:
        ktype = u.get("knowledge_type", "?")
        summary = (u.get("summary") or "")[:200]
        concepts = u.get("concepts", "")
        confidence = u.get("confidence", 0.0)
        source_file = u.get("source_file", "?")
        verbatim = u.get("verbatim_anchor") or ""

        block = f"[{ktype}] {source_file} (conf={confidence:.2f})\n  Concepts: {concepts}\n  Summary: {summary}\n  Anchor: {verbatim}\n"
        if total + len(block) > max_context_chars:
            break
        lines.append(block)
        total += len(block)

    header = (
        f"# ICT KNOWLEDGE BASE CONTEXT (retrieved {len(lines)} units)\n"
        f"# Concepts detected: {', '.join(found.keys())}\n"
        f"# These are grounded source materials from ICT transcripts.\n"
        f"# Use for terminology, methodology context, and setup definitions.\n"
    )
    return "\n".join([header] + lines)


def main():
    parser = argparse.ArgumentParser(
        description="Test Knowledge Bridge integration with the narrative engine."
    )
    parser.add_argument(
        "--mode", default="premarket",
        choices=["premarket", "open", "intraday", "close"],
        help="Narrative mode to test (default: premarket).",
    )
    parser.add_argument(
        "--ticker", default="ES1",
        help="Ticker to use (default: ES1).",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="Compare narratives with and without KB context (uses LLM tokens).",
    )
    parser.add_argument(
        "--model", default="gpt-4o",
        help="LLM model for compare mode (default: gpt-4o).",
    )
    parser.add_argument(
        "--kb-url", default="http://127.0.0.1:8900",
        help="KB API URL (default: http://127.0.0.1:8900).",
    )
    parser.add_argument(
        "--sim-time", default=None,
        help="Simulate at this ET time 'YYYY-MM-DD HH:MM'.",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Directory to write test outputs (default: logs/kb_test/).",
    )

    args = parser.parse_args()

    # ── 1. Check KB API ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("KNOWLEDGE BRIDGE -> NARRATIVE ENGINE INTEGRATION TEST")
    print("=" * 70)

    kb_ok = check_kb_api(args.kb_url)
    if kb_ok:
        print(f"✓ KB API reachable at {args.kb_url}")
    else:
        print(f"✗ KB API not reachable at {args.kb_url}")
        print("  Start it: cd C:\\Users\\vinay\\video2pdf; .\\.venv\\Scripts\\Activate.ps1")
        print("  $env:PYTHONPATH='.'; $env:KB_DATA_DIR='C:\\Users\\vinay\\tvDownloadOHLC\\data\\knowledge'")
        print("  python -m knowledge_ingest.serve --port 8900")
        print("\n  Continuing without KB context (will show cheat sheet only)...")
    print()

    # ── 2. Build cheat sheet ──────────────────────────────────────────────────
    from scripts.trader.briefing_core import (
        build_premarket_context,
        build_ticker_cheat_sheet,
        build_intraday_context,
        build_eod_context,
        get_dataloader,
    )
    from datetime import datetime
    import pytz

    ET = pytz.timezone("America/New_York")
    sim_dt = None
    if args.sim_time:
        sim_dt = ET.localize(datetime.strptime(args.sim_time, "%Y-%m-%d %H:%M"))

    loader = get_dataloader(lookback_days=5)

    print(f"Building cheat sheet (mode={args.mode}, ticker={args.ticker})...")
    try:
        if args.mode == "premarket":
            cheat_sheet = build_premarket_context(
                loader=loader, nq_ticker=args.ticker, target_date=sim_dt.date() if sim_dt else None
            )
        elif args.mode == "intraday":
            cheat_sheet = build_intraday_context(
                loader=loader, ticker=args.ticker, now_et=sim_dt
            )
        elif args.mode == "close":
            cheat_sheet = build_eod_context(
                loader=loader, ticker=args.ticker, target_date=sim_dt.date() if sim_dt else None
            )
        else:
            cheat_sheet = build_ticker_cheat_sheet(
                ticker=args.ticker, mode=args.mode, loader=loader,
                now_et=sim_dt,
            )
    except Exception as e:
        print(f"✗ Failed to build cheat sheet: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"✓ Cheat sheet assembled ({len(cheat_sheet):,} chars)")
    print()

    # ── 3. Retrieve KB context ───────────────────────────────────────────────
    kb_context = ""
    if kb_ok:
        print("Retrieving KB context for cheat sheet concepts...")
        kb_context = fetch_kb_context(cheat_sheet, kb_api_url=args.kb_url)
        if kb_context:
            print(f"✓ KB context retrieved ({len(kb_context):,} chars)")
        else:
            print("✗ No KB units matched cheat sheet concepts")
    else:
        print("⊘ Skipping KB context (API not reachable)")
    print()

    # ── 4. Output ─────────────────────────────────────────────────────────────
    output_dir = Path(args.output_dir) if args.output_dir else _ROOT / "logs" / "kb_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save cheat sheet
    cs_path = output_dir / f"cheatsheet_{args.mode}_{args.ticker}.txt"
    cs_path.write_text(cheat_sheet, encoding="utf-8")
    print(f"Cheat sheet saved: {cs_path}")

    # Save KB context
    if kb_context:
        kb_path = output_dir / f"kb_context_{args.mode}_{args.ticker}.txt"
        kb_path.write_text(kb_context, encoding="utf-8")
        print(f"KB context saved:   {kb_path}")

    # Save augmented cheat sheet (cheat sheet + KB context)
    if kb_context:
        augmented = cheat_sheet + "\n\n" + kb_context
        aug_path = output_dir / f"augmented_{args.mode}_{args.ticker}.txt"
        aug_path.write_text(augmented, encoding="utf-8")
        print(f"Augmented saved:    {aug_path} ({len(augmented):,} chars)")

    print()

    # ── 5. Print summary ─────────────────────────────────────────────────────
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Mode:           {args.mode}")
    print(f"  Ticker:         {args.ticker}")
    print(f"  KB API:         {'✓ reachable' if kb_ok else '✗ not reachable'}")
    print(f"  Cheat sheet:    {len(cheat_sheet):,} chars")
    print(f"  KB context:     {len(kb_context):,} chars" if kb_context else "  KB context:     0 chars")
    print(f"  Augmented total: {len(cheat_sheet) + len(kb_context):,} chars")
    print()

    # Print first 500 chars of each for quick inspection
    print("-- CHEAT SHEET (first 500 chars) --")
    print(cheat_sheet[:500])
    print("...")
    print()
    if kb_context:
        print("-- KB CONTEXT (first 500 chars) --")
        print(kb_context[:500])
        print("...")

    # ── 6. Compare mode (optional, uses LLM tokens) ───────────────────────────
    if args.compare and kb_context:
        print()
        print("=" * 70)
        print("COMPARE MODE: Generating two narratives (with/without KB)")
        print("=" * 70)

        from scripts.trader.trader_narrative import load_prompt_template, call_ollama

        prompt_template = load_prompt_template(args.mode)

        # Without KB
        prompt_no_kb = prompt_template.replace("{{INSERT_CHEAT_SHEET}}", cheat_sheet)
        print("\nGenerating narrative WITHOUT KB context...")
        narrative_no_kb = call_ollama(prompt_no_kb, args.model)
        print(f"✓ Narrative (no KB): {len(narrative_no_kb):,} chars")

        # With KB
        augmented_cs = cheat_sheet + "\n\n" + kb_context
        prompt_with_kb = prompt_template.replace("{{INSERT_CHEAT_SHEET}}", augmented_cs)
        print("Generating narrative WITH KB context...")
        narrative_with_kb = call_ollama(prompt_with_kb, args.model)
        print(f"✓ Narrative (with KB): {len(narrative_with_kb):,} chars")

        # Save both
        no_kb_path = output_dir / f"narrative_no_kb_{args.mode}_{args.ticker}.md"
        with_kb_path = output_dir / f"narrative_with_kb_{args.mode}_{args.ticker}.md"
        no_kb_path.write_text(narrative_no_kb, encoding="utf-8")
        with_kb_path.write_text(narrative_with_kb, encoding="utf-8")
        print(f"\nSaved: {no_kb_path}")
        print(f"Saved: {with_kb_path}")

        print()
        print("-- NARRATIVE WITHOUT KB (first 800 chars) --")
        print(narrative_no_kb[:800])
        print("...")
        print()
        print("-- NARRATIVE WITH KB (first 800 chars) --")
        print(narrative_with_kb[:800])
        print("...")

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()