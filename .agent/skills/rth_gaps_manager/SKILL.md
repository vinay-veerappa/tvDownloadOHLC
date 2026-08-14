---
name: RTH Gaps Manager
description: Manages the generation, maintenance, and statistical analysis of RTH (Regular Trading Hours) gaps and their subsequent fills.
applyTo: "**/*.py"
---

# RTH Gaps Manager

This skill handles the lifecycle of "RTH Gap" data—specifically the price difference between the previous session's RTH Close (e.g., 16:15 ET) and the current session's RTH Open (09:30 ET).

## When to use

Use when managing RTH (Regular Trading Hours) gap data — generation, maintenance, and statistical analysis of gap events.

## Capabilities
1.  **Generate Data**: scanning intraday data to identify historical gaps.
2.  **Analyze Fills**: Verifying if/when gaps were filled intraraday.
3.  **Correlations**: Assessing relationships between gap size, defense (holding the gap), and trend days.

## Key Scripts

### 1. Data Generation
*   **Script**: `scripts/derived/generate_rth_gaps.py`
*   **Usage**: `python scripts/derived/generate_rth_gaps.py --tickers NQ1 ES1`
*   **Output**: `data/derived/rth_gaps.json`
*   **Logic**:
    *   Finds RTH gaps based on ticker-specific hours (e.g., Indices 09:30-16:15).
    *   Vectorized for high performance over 20+ years of 1-minute data.

### 2. Gap Analysis (Fills & Defense)
*   **Script**: `scripts/analysis/analyze_gap_history.py`
*   **Usage**: `python scripts/analysis/analyze_gap_history.py --ticker NQ1`
*   **Output**: Prints statistical summary to console.
*   **Metrics**:
    *   **Fill Rate**: % of gaps that close completely.
    *   **Time to Fill**: Median minutes from Open.
    *   **Defense Rate**: % of times the "Far Side" (Yesterday's Low for Gap Up) is never broken.
    *   **Gap & Go**: Probability of session trending in gap direction.

## Workflow Integration
*   **Daily Prep**: This generation runs automatically in `scripts/trader/run_daily_prep.py`
*   **Reports**: See `docs/nqstats/rth_breaks/GAP_ANALYSIS.md` for the latest comprehensive study.
