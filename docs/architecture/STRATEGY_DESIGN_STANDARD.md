# Strategy Design Standard (Layer 4 & 5)

This document defines the mandatory structural requirements for all trading strategies in the `tvDownloadOHLC` repository.

## Design Philosophy: "Hunters vs. Execution"

A Strategy should be a **Pure Signal Hunter**. It's sole job is to identify "High-Probability Opportunities" and output their parameters. It should **not** manage trades, track P&L, or handle risk calculations.

---

## 1. The Canonical Interface: `hunt(data)`

### Decision Outcome: VERIFIED
The `hunt(data)` vectorized interface is now the MANDATORY standard for all new research strategies. This decision was formally verified on 2026-04-04 using the `IBPullbackStrategy` refactor, which demonstrated:
- **100x Speed Gain**: 5 years of 1m data processed in < 2 seconds.
- **Optuna Native**: Seamless parameter sweep compatibility.
- **SDS Compliance**: 100% adherence to the state-less design.
- **Output**: `pd.DataFrame` (The "Signal List") with exactly these columns:
    - `signal_time`: (DatetimeIndex) The bar where the signal was detected.
    - `direction`: ('long' or 'short')
    - `entry_price`: (float) The target price for entry.
    - `stop_price`: (float) The price to exit if the trade fails.
    - `target1_price`: (float) The price to exit if the trade succeeds.
- **No-Signal Output Rule (MANDATORY)**: If no setups are found, return an empty `pd.DataFrame` with the same canonical columns (`signal_time`, `direction`, `entry_price`, `stop_price`, `target1_price`). Do not return a column-less DataFrame.

---

## 2. Mandatory Rules of Vectorization

### 🚫 Forbidden: Row-by-Row Loops
Never use `for index, row in df.iterrows():` or `for i in range(len(df)):`. These are 100x slower than Pandas/NumPy and prevent scaling in Optuna.

### ✅ Required: Boolean Masking
Use Pandas boolean masks to find entries.
```python
# Example: Long entry on IB break
signals['is_long'] = data['high'] > data['ib_high']
signals['is_short'] = data['low'] < data['ib_low']
```

### ✅ Set-Based Indicators
Calculate all indicators (FVG, OB, IB) as columns in the main DataFrame before signal hunting.

---

## 3. Backtest Workflow

The only approved way to backtest a strategy is by passing the `Signal List` to the `VectorizedBacktester`.

### 2. Execution Layer (Engine)
The `VectorizedBacktester` is the standard engine for all SDS strategies. It handles high-performance point-value calculations and cost modeling.

**Engine Return Schema (MANDATORY)**:
All SDS-compliant hunters must output signals that the `VectorizedBacktester` can process into this standardized result dictionary:
- `total_return_%`: Final equity percentage gain/loss.
- `win_rate_%`: Percentage of trades with P&L > 0.
- `avg_mae_%`: Average Maximum Adverse Excursion (Risk measurement).
- `num_trades`: Total trade count.
- `equity_curve`: pd.Series of cumulative returns.
- `trades_detailed`: DataFrame with per-trade metrics.

#### Risk Parameter Synchronization
Signals MUST include the `'ticker'` parameter (e.g., `NQ1`, `ES1`) in the `risk_params` to ensure the engine applies the correct institutional point-value multipliers (e.g., $20/pt for NQ, $50/pt for ES).

By following this standard, all strategies automatically benefit from:
1. **Institutional-Grade MAE/MFE** reporting.
2. **200x Performance Boost** in Optuna sweeps.
3. **No "Shadowing" Bugs** (Single Engine).

---

## 4. Mandatory Verification Gate (Once Per Change)

For every new/ported hunter strategy and for any lifecycle schema change, you MUST run one full ADR-017 matrix smoke pass once before marking work complete.

PowerShell command (repo root):
`$strategies = @('ib_pullback','box_reversion','mean_reversion','ema_pullback','vwap_reclaim','failed_auction','six_am_reversal'); foreach ($s in $strategies) { & .\\.venv\\Scripts\\python.exe -m scripts.trading_framework.research.lifecycle_runner --ticker NQ1 --strategy $s --trials 1 --skip-persist; if ($LASTEXITCODE -ne 0) { throw "FAILED:$s" } }`
