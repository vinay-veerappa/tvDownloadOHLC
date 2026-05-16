# TCM-001 / Aspect 02: Feature Engineering and Labels

## Objective

Create deterministic labels for anchor color and day bias.

## Checklist

- [ ] Anchor candle extracted at 08:15 ET.
- [ ] Anchor color labeled (up/down/doji).
- [ ] Day bias labeled from RTH open/close.
- [ ] Doji handling policy documented.
- [ ] Label leakage checks completed.

## Deliverables

- Labeled dataset in `results/TCM/TCM-001/labeled_days.parquet`.
- Feature dictionary in `results/TCM/TCM-001/feature_dictionary.json`.
