# TCM-001 / Aspect 03: Core Statistical Test

## Objective

Measure whether inverse pairing occurs above chance.

## Primary Metrics

- Inverse hit rate: P(anchor down | bullish day) and P(anchor up | bearish day).
- Overall inverse agreement rate.
- Chi-square test of independence.
- Effect size (Cramer's V).

## Checklist

- [ ] Confusion matrix computed.
- [ ] Confidence intervals computed (bootstrap or binomial).
- [ ] Statistical significance recorded.
- [ ] Effect size interpreted (small/medium/large).

## Deliverables

- Stats summary in `results/TCM/TCM-001/stats_summary.json`.
- Confusion matrix in `results/TCM/TCM-001/confusion_matrix.csv`.
