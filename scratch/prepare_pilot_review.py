"""Prepare Pilot Wargame Code & Logic Review Prompt

Prepares review prompt for pilot_single_day.py and queries Kimi K2.7 and DeepSeek V4.
"""
from pathlib import Path

REPO = Path(__file__).parent.parent
code_file = REPO / "scripts" / "wargaming" / "pilot_single_day.py"

prompt_file = REPO / "scratch" / "pilot_review_prompt.txt"
prompt_file.write_text(f"""You are an expert quantitative python developer and trading system auditor.
Review the following Python module (`scripts/wargaming/pilot_single_day.py`), which implements an end-to-end Single-Day Pilot Wargame (08:30 AM pre-market scenario generation) and EOD Reengineering Post-Mortem (16:00 PM EST intraday replay).

Focus your code review on:
1. **Strict Prevention of Look-Ahead Bias**: Verify that `premarket_0830` ingests ONLY pre-market inputs prior to 09:30 AM EST.
2. **Robustness & Error Handling**: Are there edge cases where missing 1m bars, timezone mismatches, or holiday sessions will break execution?
3. **Type Safety & Code Quality**: Check for clean typing, efficient pandas operations, and modularity.
4. **Actionable Code Enhancements**: Recommend any refactoring or performance improvements.

--- SOURCE CODE ---
{code_file.read_text(encoding='utf-8')}
""", encoding="utf-8")

print(f"Wrote pilot review prompt to {prompt_file}")
