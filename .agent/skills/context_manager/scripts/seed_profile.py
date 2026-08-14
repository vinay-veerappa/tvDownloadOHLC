"""
seed_profile.py — curated user_prefs seeder (P1).

Hand-curation, not automation (design §4.1). The seeds below are derived from
already-user-ratified sources (ADR.md, SecondBrain_Trading.md, claude_memory
rows, copilot-instructions.md). Each row is user-approved via --apply.

Usage:
    python .agent/skills/context_manager/scripts/seed_profile.py           # dry-run
    python .agent/skills/context_manager/scripts/seed_profile.py --apply   # write
    python .agent/skills/context_manager/scripts/seed_profile.py --apply --render  # write + render USER.md
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from store_schema import (
    DB_PATH,
    USER_MD_PATH,
    get_db_connection,
    ensure_schema,
    upsert_pref,
    render_profile_md,
)

# ---------------------------------------------------------------------------
# Curated seed list (design §4.1 — each item user-ratified)
# ---------------------------------------------------------------------------

SEEDS = [
    # trading_* from SecondBrain_Trading.md
    ("trading_sessions", "Asia 20:00-02:00, London 02:00-08:00, NY 08:00-16:00 ET", 1.0, "SecondBrain_Trading.md"),
    ("trading_instruments", "NQ1 (primary), ES1 (secondary)", 1.0, "SecondBrain_Trading.md"),
    ("trading_execution", "Buy in Discount (<50% of dealing range), Sell in Premium (>50%)", 1.0, "SecondBrain_Trading.md"),
    ("trading_lea_pattern", "London Engulfs Asia: 71.5% break London High, 70.4% break Low", 1.0, "SecondBrain_Trading.md"),
    ("trading_ael_pattern", "Asia Engulfs London: 81.1% break London High (high-conviction bullish)", 1.0, "SecondBrain_Trading.md"),
    ("trading_rth_inside", "Open inside pRTH: 74% break at least one side; only 8.3% outside day", 1.0, "SecondBrain_Trading.md"),

    # conventions_* from ADR.md
    ("conventions_timezone", "UTC naive inputs; ET session windows; UTC epoch storage (ADR-001)", 1.0, "ADR.md"),
    ("conventions_stats_pct", "Metrics as price-percentage, not absolute points (ADR-002)", 1.0, "ADR.md"),
    ("conventions_vectorized", "No for-loops in calculation paths — vectorized NumPy/Pandas (ADR-017)", 1.0, "ADR.md"),
    ("conventions_visual", "Indicators bind to VISUAL_SYSTEM.md templates, zero direct draw calls (ADR-018)", 1.0, "ADR.md"),
    ("conventions_prop_rth_close", "Max intraday exit at 16:00 ET close of 15:59 bar (ADR-020)", 1.0, "ADR.md"),
    ("conventions_prop_sim", "Only PropFirmSimulator for prop firm evaluation; never per-trade % as daily P&L (ADR-021)", 1.0, "ADR.md"),
    ("conventions_parallel", ">=32-arm parameter sweeps use joblib; Numba @njit for bounded loops; CuPy GPU for >1M-element cumulative (ADR-022)", 1.0, "ADR.md"),

    # lessons_* from claude_memory rows (inferred, confidence 0.7)
    ("lessons_account_change", "NT8 Account.Change() modifies the position in place — validate after call", 0.7, "claude_memory/nt8-order-change-semantics"),
    ("lessons_mutation_testing", "Mutation testing is the evidence standard, not green-suite review", 0.7, "claude_memory/mutation-testing-beats-review"),
    ("lessons_test_doubles", "A green suite is evidence about the fiction we authored, not the system", 0.7, "claude_memory/test-doubles-are-not-evidence"),
    ("lessons_fix_class_not_instance", "When a defect is found, ask what structure generates it before patching the instance", 0.7, "claude_memory/fix-the-class-not-the-instance"),
    ("lessons_git_push_blockers", "data/ and audio files purge from git; run git lfs or .gitignore before push", 0.7, "claude_memory/git-push-blockers"),

    # api_* / workflow_* from copilot-instructions.md
    ("api_mcp_first", "Use codebase-memory MCP first for code search; grep only as fallback", 1.0, "copilot-instructions.md"),
    ("api_compile_via_mcp", "NT8 compile via nt_compile MCP only; never manual HTTP to localhost:7890", 1.0, "copilot-instructions.md"),
    ("workflow_sync_keyword", "'sync' keyword triggers mandatory startup sequence (AGENTS.md + memory.db + skills)", 1.0, "copilot-instructions.md"),
]


def main():
    parser = argparse.ArgumentParser(description="Seed user_prefs from curated, user-ratified sources.")
    parser.add_argument("--apply", action="store_true", help="Write seeds to DB (default: dry-run)")
    parser.add_argument("--render", action="store_true", help="Also render .agent/USER.md")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        ensure_schema(conn)
        print(f"Database: {DB_PATH}")
        print(f"Seeds: {len(SEEDS)} rows")
        print()
        for key, value, conf, source in SEEDS:
            print(f"  {key:<40} conf={conf:.1f}  src={source}")
            print(f"    {value}")
            if args.apply:
                upsert_pref(conn, key, value, conf, source)
        print()
        if args.apply:
            print(f"Applied {len(SEEDS)} rows to user_prefs.")
        else:
            print(f"Dry-run only. Use --apply to write.")
        if args.render:
            md = render_profile_md(conn)
            with open(USER_MD_PATH, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"Rendered USER.md -> {USER_MD_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()