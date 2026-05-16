# TCM-001 / Aspect 01: Data Universe and Sampling

## Objective

Define and freeze the dataset used to test the concept.

## Checklist

- [ ] Ticker(s) selected (initially NQ1).
- [ ] Time window defined (start/end dates).
- [ ] Trading days only (exclude holidays/partial sessions if needed).
- [ ] 5-minute bars aligned to ET.
- [ ] Missing anchor bars logged and excluded with counts.

## Deliverables

- Dataset manifest in `results/TCM/TCM-001/dataset_manifest.json`.
- Day-level sample table in `results/TCM/TCM-001/day_sample.parquet`.
