# Strategy Analysis & Grading Tool (The Edge System)
**Scripts**: `analyze_v3_comprehensive.py` (TradingView) | `analyze_ninjatrader.py` (NinjaTrader)
**Version**: 2.1 (Multi-Platform Edition)

## 1. Overview

Universal strategy grading tools that ingest backtest exports and generate standardized **System Reports** containing:
1. **The 10-Metric Card**: Every critical risk metric (EV, PF, RoR, Combined Edge, etc.)
2. **System Grade (A-F)**: Automated quality scoring based on "Edge System" rules
3. **Actionable Recommendations**: A "Fix Table" telling you exactly what to tune
4. **Granular Time Analysis**: Performance broken down by 5-min, 15-min, Hour, Day, Quarter, and Year

---

## 2. Quick Start

### Prerequisites
```bash
pip install pandas numpy openpyxl
```

### NinjaTrader Analysis
```bash
cd scripts
python analyze_ninjatrader.py trades.csv settings.csv
# Or auto-detect:
python analyze_ninjatrader.py
```

### TradingView Analysis
```bash
cd scripts
python analyze_v3_comprehensive.py
# Uses INPUT_PATTERN = "ORB_V3_*.xlsx"
```

**Output**: Generates `*_Analysis_*.md` report file.

---

## 3. Export Formats

### NinjaTrader Strategy Analyzer (3 CSV files)

**Trades CSV** (`*_trades.csv`):
| Column | Description |
|--------|-------------|
| Trade number | Sequential ID |
| Instrument | Contract (e.g., "MNQ 03-26") |
| Market pos. | "Long" or "Short" |
| Entry price / Exit price | Fill prices |
| Entry time / Exit time | Timestamps |
| Entry name / Exit name | Signal names |
| Profit | P&L as `$X.XX` or `($X.XX)` for losses |
| MAE / MFE / ETD | Excursion metrics |

**Settings CSV** (`*_settings.csv`):
Key-value pairs of strategy parameters.

**Summary CSV** (`*_summary.csv`):
Overall backtest statistics.

### TradingView Strategy Tester (Excel .xlsx)

**Sheet: "List of trades"**:
| Column | Description |
|--------|-------------|
| Trade # | Sequential ID |
| Type | "Entry long", "Exit long", etc. |
| Date and time | Timestamp |
| Price USD | Execution price |
| Net P&L USD | Trade P&L (exit rows only) |
| MFE USD / MAE USD | Excursion metrics |

**Sheet: "Properties"**: Strategy input parameters.

---

## 4. The 10 Metrics (Calculated)

| # | Metric | Formula |
|---|--------|---------|
| 1 | Risk ($) | `Abs(AvgLoss)` |
| 2 | EV ($) | `(Win% * AvgWin) - (Loss% * AvgLoss)` |
| 3 | Profit Factor | `GrossWin / GrossLoss` |
| 4 | MAE/MFE Ratio | `AvgMFE / AvgMAE` |
| 5 | SQN | `(MeanR / StdR) * sqrt(Trades)` |
| 6 | Max Streak | `ln(N) / ln(1/LossRate)` |
| 7 | DRR | `MaxDD / Risk` |
| 8 | Combined Edge | `(EV/Risk) * ProfitFactor` |
| 9 | RoR | `((1-Edge)/(1+Edge))^Units` |
| 10 | Max Drawdown | Peak-to-Valley ($) |

---

## 5. Grading Scale

| Grade | Combined Edge | Meaning |
|-------|---------------|---------|
| A+ | > 150 | Elite system |
| A | > 100 | Excellent |
| B | > 50 | Good |
| C | > 20 | Marginal |
| D | > 0 | Weak edge |
| F | ≤ 0 | No edge |

**Modifiers:**
- `(High DRR)` - Added if DRR > 10 (high drawdown risk)

---

## 6. Output Sections

1. **Executive Grading**: The 10-Metric Card + Final Grade
2. **Risk & Robustness**: Monte Carlo simulation (2500 iterations)
3. **Configuration Verification**: Strategy parameters table
4. **Time Analysis**:
   - Day x Hour performance matrix
   - Year x Quarter with market context
   - **Golden Minutes**: Best 5 entry times
   - **Toxic Minutes**: Worst 5 entry times
   - 5-Minute distribution matrices

---

## 7. Extending to Other Platforms

The scripts only need a DataFrame with these normalized columns:
- `Entry Time` (datetime)
- `Exit Time` (datetime)  
- `Net P&L USD` (float)
- `MAE USD` (optional)
- `MFE USD` (optional)

Create a loader function that transforms platform-specific format to this schema, then pass to `calc_stats_extended()`.
