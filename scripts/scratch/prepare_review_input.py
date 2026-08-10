"""Prepare Review Input for Ollama Critical Review

Concatenates the Implementation Plan and Domain Blueprints and queries Ollama model.
"""
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).parent.parent
BRAIN_DIR = Path(r"C:\Users\vinay\.gemini\antigravity\brain\30eda112-25a1-420f-a08a-b544e235c6fd")

plan_file = BRAIN_DIR / "implementation_plan.md"
inventory_file = REPO / "docs" / "profiler" / "mickey_austin_tool_inventory.md"
cs_blueprint = REPO / "docs" / "features" / "CandleScience" / "BLUEPRINT.md"
htf_blueprint = REPO / "docs" / "features" / "htf_ema_analysis" / "BLUEPRINT.md"
line_apex_blueprint = REPO / "docs" / "profiler" / "line_vs_apex_blueprint.md"
handover_file = REPO / "docs" / "handover" / "WARGAMING_SYSTEM_ROADMAP_HANDOVER.md"

content = []

for name, p in [
    ("MASTER IMPLEMENTATION PLAN", plan_file),
    ("TOOL INVENTORY", inventory_file),
    ("CANDLE SCIENCE BLUEPRINT", cs_blueprint),
    ("HTF EMA BLUEPRINT", htf_blueprint),
    ("LINE VS APEX BLUEPRINT", line_apex_blueprint),
    ("LIVING HANDOVER & ROADMAP", handover_file),
]:
    if p.exists():
        content.append(f"\n=========================================\n=== {name} ===\n=========================================\n")
        content.append(p.read_text(encoding="utf-8"))

full_text = "\n".join(content)
prompt_file = REPO / "scratch" / "review_prompt.txt"
prompt_file.write_text(f"""You are an elite quantitative trading system architect and statistical analyst conducting a rigorous, highly critical review of our trading system roadmap and domain blueprints.

Below is our current Master Implementation Plan, Tool Inventory, living Handover, and Domain Blueprints for Candle Science, HTF EMA Analysis, and Line vs Apex 3-Hour Block Sequencing.

Perform a deep, unsparing critical audit addressing:
1. **Gaps & Blind Spots**: What critical price action rules, statistical assumptions, or invalidation edge-cases are missing or over-simplified?
2. **Backtesting & Verification Integrity**: Does our Phase 0 validation-first framework (comparing intraday 1m OHLCV price action against transcript rules) adequately prove edge before scaling to batch backtesting?
3. **Multi-Ticker Scalability**: Are there ticker-specific nuances (tick sizes, point values, 10 bps threshold scaling, session hours) between NQ, ES, CL, GC that might break?
4. **Execution Playbook & Risk Alignment**: Are Mickey's 3-tier TP scaling (Cover the Queen 10 bps, P30/P50 MFE, 09:44 AM exit) and position sizing rules accurately represented and testable?
5. **Concrete Actionable Recommendations**: What specific enhancements should we add to Phase 0.4 (Line vs Apex) and Phase 0.5 (Profiler Feature Extractor) before proceeding?

--- SYSTEM DOCUMENTS ---
{full_text}
""", encoding="utf-8")

print(f"Wrote review prompt ({len(full_text)} chars) to {prompt_file}")
