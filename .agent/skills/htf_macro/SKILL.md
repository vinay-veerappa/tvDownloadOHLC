---
name: HTF Macro Analysis
description: Analyzes Higher Timeframe (HTF) Macro anchors including Prior Monthly Midpoint, NFP Benchmark Midpoint, Weekly EMA(5) 52-week excursion percentiles, and multi-timeframe daily/hourly moving average regimes.
applyTo: "scripts/wargaming/htf_macro_levels.py,scripts/wargaming/**"
---

# 🏛️ HTF Macro Analysis Skill

## Overview
Computes macroeconomic anchor levels and higher timeframe mean-reversion gravity wells:
1. **Monthly Midpoint (50%)**: 50% equilibrium of the prior completed calendar month.
2. **NFP Midpoint (50%)**: 50% equilibrium of the most recent First-Friday Non-Farm Payrolls session.
3. **Weekly EMA(5) Excursions**: 52-week statistical distribution of Upper (Dup) and Lower (Ddn) excursions, tracking the 2%-3% high-probability mean-reversion zone.
4. **Daily 21 / 50 EMAs**: Higher timeframe baseline trend filters.

## Execution
Run the standalone engine:
```bash
python scripts/wargaming/htf_macro_levels.py --ticker NQ1
```
