# TCM-001 / Aspect 04: Regime and Session Stratification

## Objective

Check if the edge is stable across market regimes.

## Stratifications

- By year and quarter.
- By calendar month and year-month.
- By volatility regime (for example VIX buckets).
- By day type (trend day vs balanced day proxy).
- By weekday.

## Checklist

- [x] Yearly stability table generated.
- [x] Regime breakdown generated.
- [x] Weekday, month, and quarter tables generated.
- [ ] Worst-case bucket identified.
- [ ] Simpson's paradox risk reviewed.

## Deliverables

- Yearly table in `results/TCM/TCM-001/by_year.csv`.
- Month table in `results/TCM/TCM-001/by_month.csv`.
- Year-month table in `results/TCM/TCM-001/by_year_month.csv`.
- Quarter table in `results/TCM/TCM-001/by_quarter.csv`.
- Regime table in `results/TCM/TCM-001/by_regime.csv`.
- Weekday table in `results/TCM/TCM-001/by_weekday.csv`.
