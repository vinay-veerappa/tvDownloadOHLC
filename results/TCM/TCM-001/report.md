# TCM-001 Verification Report

- Ticker: NQ1
- Date range: full history to latest
- Primary sample size: 4729

## Key Metrics
- Inverse rate: 0.5153
- 95% CI: [0.5011, 0.5296]
- p-value: 0.029855
- Cramer's V: 0.0316
- OOS inverse rate: 0.5433

## Session Split Comparison
- NY AM window: 09:30-12:00
- NY PM window: 12:05-16:00
- NY Full window: 08:00-16:00

## Temporal Breakdown Outputs
- by_weekday.csv
- by_month.csv
- by_year.csv
- by_year_month.csv
- by_quarter.csv
- rth_full_day: inverse_rate=0.5153, p_value=0.029855, n=4729
- ny_am_0930_1200: inverse_rate=0.5134, p_value=0.106346, n=4723
- ny_pm_1205_1600: inverse_rate=0.5138, p_value=0.406256, n=4722
- ny_full_0800_1600: inverse_rate=0.5139, p_value=0.978723, n=4725

## Decision
- Outcome: Needs Review
- Criteria passed: 2/4
- overall_ge_55pct: False
- pvalue_lt_0p05: True
- oos_ge_53pct: True
- min_regime_ge_50pct: False
