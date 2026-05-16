# TCM-001 / Aspect 06: Acceptance Criteria and Decision Log

## Objective

Define pass/fail criteria before seeing outcomes and record final decision.

## Proposed Acceptance Criteria (V1)

- Inverse agreement rate >= 55% overall.
- p-value < 0.05 on independence test.
- Out-of-sample inverse agreement rate >= 53%.
- No major regime bucket below 50% for more than two consecutive years.

## Decision Log

- Status: Needs Review
- Last updated: 2026-05-15
- Notes: First full run completed on NQ1 5m history. Signal is statistically significant but practical edge is weak.

## Final Outcome (Run 1)

- Outcome: Needs Review
- Effective date: 2026-05-15
- In-sample metrics:
	- Primary days: 4729
	- Inverse agreement: 51.53% (95% CI: 50.11% to 52.96%)
	- p-value: 0.029855
	- Cramer's V: 0.0316
- Out-of-sample metrics:
	- Test window: 2020-06-29 to 2026-01-23
	- OOS inverse agreement: 54.33%
- Acceptance criteria check:
	- Inverse agreement >= 55%: FAIL
	- p-value < 0.05: PASS
	- OOS >= 53%: PASS
	- Min regime bucket >= 50%: FAIL (49.90%)
- Caveats:
	- Effect size is very small despite statistical significance.
	- Regime stability is borderline and dips below threshold.
	- NY AM/PM split did not improve edge versus full-day baseline.
- Next action:
	- Tighten definition by conditioning on pre-existing bias stack (for example ALN or overnight range context) and rerun as TCM-001A.

## Session Comparison Addendum (2026-05-15)

- RTH full day (09:30-16:00): inverse_rate=51.53%, p-value=0.0299, n=4729
- NY AM (09:30-12:00): inverse_rate=51.34%, p-value=0.1063, n=4723
- NY PM (12:05-16:00): inverse_rate=51.38%, p-value=0.4063, n=4722
- NY full (08:00-16:00): inverse_rate=51.39%, p-value=0.9787, n=4725

Conclusion:

- Session fine-tuning (AM/PM) does not show higher probability than the current full-day RTH setup for this concept.

## Temporal Breakdown Addendum (2026-05-15)

Generated breakdown artifacts:

- Weekday: [by_weekday.csv](../../../../results/TCM/TCM-001/by_weekday.csv)
- Month: [by_month.csv](../../../../results/TCM/TCM-001/by_month.csv)
- Year: [by_year.csv](../../../../results/TCM/TCM-001/by_year.csv)
- Year-Month: [by_year_month.csv](../../../../results/TCM/TCM-001/by_year_month.csv)
- Quarter: [by_quarter.csv](../../../../results/TCM/TCM-001/by_quarter.csv)

Quick read:

- Best weekday in current run: Thursday (54.51%)
- Weakest weekday in current run: Friday (49.57%)
- Best calendar month aggregate: May (55.75%)
- Weakest calendar month aggregate: September (49.23%)

Artifacts:

- [Report](../../../../results/TCM/TCM-001/report.md)
- [Summary](../../../../results/TCM/TCM-001/summary.json)
- [Session Comparison CSV](../../../../results/TCM/TCM-001/session_comparison.csv)
