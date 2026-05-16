# TCM-001: 08:15 AM 5m Anchor Candle Color vs Day Bias

## Concept Statement

The 08:15 AM 5-minute candle has an inverse relationship with the day bias:

- Bullish bias day -> 08:15 candle should close down (institutional support).
- Bearish bias day -> 08:15 candle should close up (immediate resistance).

## Testable Hypothesis

- H0 (null): 08:15 candle color and day bias are independent.
- H1 (alternative): the relationship is inverse and statistically significant.

## Current Status

- Status: Needs Review
- Last run: 2026-05-15
- Primary sample size: 4729 days
- Inverse rate: 51.53%
- p-value: 0.029855
- OOS inverse rate: 54.33%

## Session Fine-Tune (NY AM vs PM vs Full)

Session windows used:

- RTH full day: 09:30-16:00 ET
- NY AM: 09:30-12:00 ET
- NY PM: 12:05-16:00 ET
- NY full: 08:00-16:00 ET

Observed inverse rates:

- RTH full day: 51.53% (p=0.0299)
- NY AM: 51.34% (p=0.1063)
- NY PM: 51.38% (p=0.4063)
- NY full: 51.39% (p=0.9787)

Interpretation:

- No meaningful probability improvement in NY AM or NY PM versus the current full-day baseline.
- The strongest statistical signal remains the original RTH full-day definition, but effect size is still small.

## Operational Definitions (Version 1)

- Anchor candle: 5-minute bar from 08:15:00 to 08:19:59 ET.
- Anchor color:
  - Up candle: close > open
  - Down candle: close < open
  - Doji: close == open (excluded in primary test, included in sensitivity tests)
- Day bias (primary): RTH close minus RTH open (09:30 to 16:00 ET).
  - Bullish day: RTH close > RTH open
  - Bearish day: RTH close < RTH open

## Aspects We Will Test and Verify

1. [Data Universe and Sampling](01_data_universe_and_sampling.md)
2. [Feature Engineering and Labels](02_feature_engineering_and_labels.md)
3. [Core Statistical Test](03_core_statistical_test.md)
4. [Regime and Session Stratification](04_regime_and_session_stratification.md)
5. [Robustness and Out-of-Sample Validation](05_robustness_and_oos_validation.md)
6. [Acceptance Criteria and Decision Log](06_acceptance_criteria_and_decision_log.md)

## Execution Script

- Script path: `scripts/TCM/tcm_001_0815_anchor_inverse.py`

## Result Storage Convention

When run, this concept should write to:

- `results/TCM/TCM-001/summary.json`
- `results/TCM/TCM-001/by_year.csv`
- `results/TCM/TCM-001/by_month.csv`
- `results/TCM/TCM-001/by_year_month.csv`
- `results/TCM/TCM-001/by_quarter.csv`
- `results/TCM/TCM-001/by_regime.csv`
- `results/TCM/TCM-001/by_weekday.csv`
- `results/TCM/TCM-001/report.md`
- `results/TCM/TCM-001/session_comparison.csv`
- `results/TCM/TCM-001/session_comparison.json`

## Run Artifacts

- [Report](../../../../results/TCM/TCM-001/report.md)
- [Summary JSON](../../../../results/TCM/TCM-001/summary.json)
- [Yearly Breakdown](../../../../results/TCM/TCM-001/by_year.csv)
- [Month Breakdown](../../../../results/TCM/TCM-001/by_month.csv)
- [Year-Month Breakdown](../../../../results/TCM/TCM-001/by_year_month.csv)
- [Quarter Breakdown](../../../../results/TCM/TCM-001/by_quarter.csv)
- [Regime Breakdown](../../../../results/TCM/TCM-001/by_regime.csv)
- [Weekday Breakdown](../../../../results/TCM/TCM-001/by_weekday.csv)
- [Session Comparison CSV](../../../../results/TCM/TCM-001/session_comparison.csv)
- [Session Comparison JSON](../../../../results/TCM/TCM-001/session_comparison.json)
- [Sensitivity](../../../../results/TCM/TCM-001/sensitivity.csv)

## Changelog

- 2026-05-15: Initial concept spec created.
- 2026-05-15: Completed first full implementation and execution on NQ1 5m parquet. Outcome set to Needs Review.
- 2026-05-15: Added NY AM/PM/full session fine-tune comparison and persisted dedicated session outputs.
- 2026-05-15: Updated NY AM to 09:30-12:00 and added temporal breakdown outputs (weekday, month, year, year-month, quarter).
