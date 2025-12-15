# Backtest Comparison: 9:30 1 Min Strategy vs Close Inside Range Variant

Compare the standard 9:30 1 Min breakout strategy against a variant that exits if a candle closes back inside the opening range.

## User Review Required
None.

## Proposed Changes

### Strategies
#### [NEW] [nq-1min-close-in-range-strategy.ts](file:///c:/Users/vinay/tvDownloadOHLC/web/lib/backtest/strategies/nq-1min-close-in-range-strategy.ts)
- Create a new strategy class `Nq1MinCloseInRangeStrategy` based on `Nq1MinStrategy`.
- Add a new exit condition in the trade management loop:
    - If `position` is active, check if `bar.close` is within `[rangeLow, rangeHigh]`.
    - If true, close the entire position at `bar.close` and record the trade.

### Scripts
#### [NEW] [compare-backtest.ts](file:///c:/Users/vinay/tvDownloadOHLC/scripts/compare-backtest.ts)
- Load data for 'NQ1!' 1m timeframe.
- Instantiate both `Nq1MinStrategy` and `Nq1MinCloseInRangeStrategy`.
- Run both strategies on the same data with the same parameters (`max_trades: 100`).
- Use `max_trades: 100` to limit the run to exactly 100 trades.
- Compare the results trade-by-trade (entries will be identical).
- Output a CSV file `backtest_comparison.csv` with columns:
    - `TradeNo`, `EntryDate`, `Direction`, `EntryPrice`
    - `Base_ExitPrice`, `Base_PnL`, `Base_Result`
    - `New_ExitPrice`, `New_PnL`, `New_Result`
    - `PnL_Diff`

## Verification Plan

### Automated Tests
Run the comparison script:
```powershell
npx tsx scripts/compare-backtest.ts
```
- Verify the script runs without errors.
- Verify 100 trades are executed.
- Verify `backtest_comparison.csv` is created and contains reasonable data.
