---
name: NQStats Analyzer
description: Automates the verification of NQStats metrics and generates daily bias briefings based on the Unified Bias Algorithm.
applyTo: "**/*.py"
---

# NQStats Analyzer Skill

This skill allows you to run specialized statistical analysis for NQ1, ES1, and other futures based on the NQStats methodology.

## When to use

Use when the user wants to verify NQStats metrics or generate daily bias briefings — automated statistical analysis.

## Key Metrics

1.  **ALN Sessions**: Asia-London-NY relationship (LPEU, LPED, LEA, AEL).
2.  **Noon Curve**: 75% probability of HOD/LOD occurring on opposite sides of noon.
3.  **Unified Bias**: Synthesis of ALN + Broken Status + Profiler into a high-conviction daily trade plan.

## Usage

### 1. Generate Daily NQStats Briefing
This is the primary command for your pre-market routine. It analyzes the current day's Asia and London sessions to predict NY bias.

```bash
python scripts/analysis/analyze_daily_nqstats.py --ticker NQ1
```

### 2. Verify Historical Stats
Run these to re-verify the NQStats claims against your own deep data (2015-2025).

```bash
# Noon Curve Verification
python scripts/nqstats/noon_curve/verify_noon_curve.py

# ALN Verification
python scripts/nqstats/aln_sessions/verify_aln.py
```

## Daily Integration
This skill is integrated into the `daily_analysis` workflow. It runs automatically during `scripts/trader/run_daily_prep.py` to provide a "Data Integrity" and "Statistical Bias" briefing.

## Documentation
- [Trading Playbook](docs/nqstats/TRADING_PLAYBOOK.md)
- [Unified Bias Algorithm](docs/nqstats/UNIFIED_BIAS_ALGORITHM.md)
