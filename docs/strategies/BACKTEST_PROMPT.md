# Backtest Development Prompt

Use this prompt when creating or running backtest scripts to ensure compliance with project standards.

---

## 📋 Pre-Execution Checklist

Before running any backtest or creating a new backtest script, the agent MUST review these documents:

### 1. Data Standards
- **[BACKTEST_STANDARDS.md](BACKTEST_STANDARDS.md)**: Required CSV columns, metric definitions (% based), and market regime periods.
- **[../data/DATA_SOURCES.md](../data/DATA_SOURCES.md)**: Timezone conventions (UTC in parquet, conversion to US/Eastern for logic).
- **[../data/DERIVED_DATA.md](../data/DERIVED_DATA.md)**: Pre-computed data files (`*_opening_range.json`, `*_profiler.json`, etc.) and their schemas.

### 2. Strategy-Specific Docs (if applicable)
- **Strategy Master Spec**: E.g., `9_30_breakout/ORB_STRATEGY_MASTER_SPEC.md` for filter logic, entry modes, and exit rules.
- **Analysis Summary**: Prior research findings and expected performance benchmarks.

---

## 🔧 Script Requirements

Every backtest script MUST:

1. **Use Parquet as Primary Source**: `data/{TICKER}_1m.parquet` for OHLC data.
2. **Convert Timezones**: Raw data is UTC; convert to `US/Eastern` for RTH logic.
3. **Output Compliant CSV** with these columns:
   - **Context**: `Date`, `DayOfWeek`, `Range_Pct`, `Regime_Bull`, `VVIX_Open`
   - **Execution**: `Variant`, `Direction`, `Entry_Price`, `Entry_Time`, `Entry_Type`, `Entry_Delay`, `Is_Outside_Range`
   - **Outcome**: `Result`, `PnL_Pct`, `MAE_Pct`, `MFE_Pct`, `Exit_Time`, `Exit_Reason`
4. **Use Percentage-Based Metrics**: PnL, MAE, MFE, Range Size all as `%` of Entry/Open price.
5. **Validate Data Ranges**: Ensure the parquet covers the intended backtest period.

---

## ⏰ Trading Day Definition

| Session | Time (EST) | Purpose |
|---------|------------|---------|
| Pre-Market | 04:00 - 09:29 | Context only (no entries) |
| **RTH Open** | 09:30 | Opening Range capture |
| **Entry Window** | 09:31 - 10:00 | Trade execution |
| RTH Close | 16:00 | EOD Exit deadline |

---

## 🧪 Regime Testing Requirement

All backtests must be validated across these benchmark periods (per BACKTEST_STANDARDS.md):

| Regime | Period |
|--------|--------|
| Strong Bull | 2020-04 to 2021-12 |
| Strong Bear | 2022-01 to 2022-10 |
| Consolidation | 2023-01 to 2023-06 |
| Standard Bull | 2023-11 to Present |

---

## 📊 Data Field Semantics

| Field | Unit | Example | Notes |
|-------|------|---------|-------|
| `range_pct` (in JSON) | % | `0.10` = 0.10% | Already a percentage, NOT a decimal |
| `PnL_Pct` | % | `0.25` = 0.25% | Relative to Entry Price |
| `MAE_Pct` | % | `0.15` = 0.15% | Maximum Adverse Excursion |
| `MFE_Pct` | % | `0.50` = 0.50% | Maximum Favorable Excursion |

---

## 🚀 Quick Start Command

```bash
python scripts/backtest/9_30_breakout/run_930_v6_strategy.py
```

Output saved to: `scripts/backtest/9_30_breakout/results/v6_backtest_details.csv`
