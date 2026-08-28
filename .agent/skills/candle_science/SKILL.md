---
name: Candle Science
description: Analyzes 3-candle sequence patterns (C1 -> C2 -> C3) and derives empirical MFE and MAE percentiles (P30, P50, P70) for daily target boxes and statistical reversal limits.
applyTo: "scripts/candle_science/**,api/features/candle_science/**"
---

# 🕯️ Candle Science Skill

## Overview
Candle Science models historical 3-candle sequences over 4,300+ trading days to compute statistical excursion envelopes (MFE and MAE) across percentiles.

## Execution
Run the standalone engine:
```bash
python scripts/candle_science/run_candle_science.py --ticker NQ1 --mode open
```

## Key Rules
1. **P30 (30th Percentile)**: Conservative cash-flow target ("Cover The Queen").
2. **P50 (Median)**: Standard session baseline target for HOD/LOD.
3. **P70 (70th Percentile Reversal Limit)**: 70% of the time, price reverses before exceeding the P70 box; only 30% of days expand cleanly through (DNP/DWP trend days).
