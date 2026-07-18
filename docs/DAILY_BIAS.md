# Daily Bias Analysis Framework

This document outlines the systematic process for determining daily market bias, combining technical context, statistical patterns, and sequential probabilities.

## 1. Core Objectives
- **Predict Daily Market Type**: R1, R2, DWP, or DNP.
- **Identify Key Liquidity Levels**: HTF S/R, Opening Range, and Session Extrema.
- **Quantify Probabilities**: Use historical data (NQStats) and sequential trends to assign confidence to the bias.

## 2. Methodology & Components

The daily bias is derived from four primary analysis engines integrated into `run_daily_prep.py`:

### A. ICT Context & Liquidity
- **Purpose**: Identify the "State of the Week" and key price levels.
- **Key Levels**: PWH/PWL, PMH/PML, WTD High/Low, PDC.
- **Visuals**: Generates the ICT Context chart with FVG detection and session boxes.
- **Script**: `retrieve_ict_context.py` & `generate_ict_chart.py`.

### B. NQStats Unified Bias (Pattern-Based)
- **Purpose**: Apply statistical edges based on Overnight (Asia/London) price action patterns.
- **Patterns**: ALN (Asia/London/NY) classifications like LPEU (London Protrusion Expansion Up).
- **Conviction**: Based on "Broken Status" (whether Asia/London highs/lows held or were breached).
- **Script**: `analyze_daily_nqstats.py`.

### C. Daily Classification Bias (Sequential)
- **Purpose**: Predict today's outcome based on yesterday's classification and current overnight sentiment.
- **Probabilities**: 
  - **Sequential**: Probability of Today (e.g., R2) given Yesterday (e.g., R1).
  - **Overnight Sentiment**: Probability given Asia/London status (Bullish/Bearish/Neutral).
- **Script**: `analyze_daily_classification_bias.py`.

### D. Data Integrity Verification
- **Purpose**: Ensure the analysis is based on accurate, non-corrupted data.
- **Checks**: Cross-references Schwab live data with historical parquet files to detect "bootstrap conflicts."
- **Script**: `generate_conflict_report.py`.

## 3. Report Formats (Discord)

All reports are consolidated into the `test_channel` Discord channel.

### Statistical Bias (NQStats)
```markdown
### 📊 NQSTATS: NQ1 | 2026-01-22
---
**Final Bias**: BULLISH | **Conviction**: HIGH
**Action**: Favor Longs. Targets: PDC / PWH.

**Classification**:
- ALN: LPEU
- Broken: Held/Broken
- Status: B/S
```

### Classification Bias (Sequential)
```markdown
### 🏷️ CLASSIFICATION BIAS: NQ1
---
**Sequential Probability** (After R2):
> R1: 21.5% | R2: 32.8% | DWP: 30.2% | DNP: 15.5%

**Overnight Probability** (Key: long false | short false | LdnBreak:False):
> R1: 15.7% | R2: 38.2% | DWP: 27.5% | DNP: 18.6%

**Most Likely Outcome**: R2
```

## 4. Execution Workflow

To run the full Daily Bias analysis for a ticker:

```powershell
python scripts/trader/run_daily_prep.py --tickers NQ1
```

### Maintenance Tasks
- **Update Classifications**: `python scripts/derived/precompute_daily_classification.py` (Manual).
- **Refresh Profiler Lookup Table**: `python -m scripts.libs_py.profiler.generate_profiler_lookup --ticker NQ1` (regenerates `data/derived/{ticker}_profiler_lookup.json` from the raw profiler JSON + daily HOD/LOD + level touches). The raw `{ticker}_profiler.json` itself is refreshed by `python scripts/derived/precompute_profiler.py --days 5` (Incremental).
- **Bridge Gaps**: Run `stream_chart.py` to ensure local storage matches Schwab historical data.
