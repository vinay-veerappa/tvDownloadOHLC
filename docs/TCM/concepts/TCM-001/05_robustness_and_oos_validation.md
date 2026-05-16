# TCM-001 / Aspect 05: Robustness and Out-of-Sample Validation

## Objective

Verify the concept persists outside in-sample periods and under alternate definitions.

## Robustness Tests

- Alternate day-bias definitions.
- Include vs exclude doji days.
- Rolling walk-forward windows.
- Out-of-sample split (time-based).

## Checklist

- [ ] Train/test split documented.
- [ ] OOS hit rate computed.
- [ ] Sensitivity table generated.
- [ ] Drift detection noted.

## Deliverables

- OOS summary in `results/TCM/TCM-001/oos_summary.json`.
- Sensitivity report in `results/TCM/TCM-001/sensitivity.csv`.
