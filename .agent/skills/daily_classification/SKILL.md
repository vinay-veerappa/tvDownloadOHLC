---
name: Daily Classification
description: Automates the generation of daily bias reports based on R1, R2, DWP, and DNP classifications, combining sequential and overnight probabilities.
---

# Daily Classification Skill

This skill allows you to analyze and predict the "Day Type" (R1, R2, DWP, DNP) based on historical sequence patterns and current overnight session action.

## Classifications

1.  **R1 (Range 1)**: Rotational/Time-Spent day. Price stays mostly within the opening range.
2.  **R2 (Range 2)**: Reversal day. Price expands out of the range but returns later.
3.  **DWP (Directional With Pullback)**: Structural trend day with entry opportunities.
4.  **DNP (Directional No Pullback)**: Aggressive power trend day.

## Usage

### 1. Generate Daily Classification Briefing
Predicts today's most likely day type using the last 3 days of price action and the current overnight session.

```bash
python scripts/analysis/analyze_daily_classification_bias.py --ticker NQ1
```

### 2. Update Historical Probabilities
Run these to re-calculate the probability matrices if more data has been added.

```bash
# Overnight Probabilities
python scripts/analysis/analyze_overnight_probabilities.py NQ1

# Sequential Probabilities
python scripts/analysis/analyze_sequence_probabilities.py NQ1
```

## Daily Integration
Integrated as Step 6 in `run_daily_prep.py`. It provides a "Structural Bias" briefing to Discord, complementing the NQStats briefing.

## Documentation
- [Classification Guide](docs/DailyClassification/DAILY_CLASSIFICATION.md)
- [Overnight Probabilities](docs/DailyClassification/NQ1_OVERNIGHT_PROBABILITIES.md)
- [Sequential Probabilities](docs/DailyClassification/NQ1_SEQUENCE_PROBABILITIES.md)
