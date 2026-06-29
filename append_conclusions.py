filepath = r'C:\Users\vinay\tvDownloadOHLC\scripts\indicators-pine\daily-ny-levels\DailyNYLevelsAnalytics_ANALYSIS.md'

content_to_append = """

### 6.8 Root Cause of Session Count Discrepancies ($N$ & Outcomes)
We ran cross-preset validation tests in Python to reconcile the breakout counts and wins/fails against the TradingView values. We identified the exact causes of the minor discrepancies:

#### 6.8.1 Missing Sunday Sessions (Parquet Data Gaps)
* **The Discovery**: For the **1800 Breakout** preset, TradingView loads `N = 74` sessions (excluding today), while Python only detected `N = 70`.
* **The Cause**: CME futures begin trading on **Sunday evenings at 18:00 ET**. TradingView's live feed has these Sunday bars, so it registers breakouts for the Sunday-to-Monday sessions. However, a scan of the local Parquet storage (`live_storage_-NQ.parquet`) revealed that **several Sundays are missing data** (e.g., March 22, May 10, May 31, June 7).
* **The Impact**: This 4-session gap in Sunday data explains why Python's $N$ count is exactly 4 sessions short for the 1800 Break preset.

#### 6.8.2 Timeframe Processing Alignment
* **The Discovery**: TradingView processes Opening Ranges using the 1-minute lower timeframe cache, but it gates breakout detection and signal logic **strictly on the main chart timeframe (5-minute bars)**.
* **The Cause**: Lines 603-610 of `DailyNYLevelsAnalytics.pine` show that `f_process_price_update` and `f_process_signal_logic` are called only when `in_data` is true on the main 5-minute bars, not inside the 1-minute LTF loop.
* **The Impact**: Setting Python to detect breakouts on the 5-minute close matches TradingView's breakout prices (e.g., today's `29,773.50` close instead of the 1-minute `29,739.50` close).

#### 6.8.3 Stop-Loss (Invalidation) Gating
* **The Discovery**: The 1-session win/fail mismatch on `2026-05-20` for the 1100 BO preset was traced to TradingView marking the day as a **Fail** despite closing above the opposite OR Low boundary at cutoff.
* **The Cause**: The live logs reveal that `2026-05-20` hit the **P80 MAE Invalidation Level (29,554.50) intraday at 12:15** before recovering to close above the boundary at 12:30. In TradingView, hitting the stop-loss (Invalidation) immediately locks the day as a Failure, whereas our basic Python test was only checking the cutoff close.
"""

with open(filepath, 'a', encoding='utf-8') as f:
    f.write(content_to_append)
print('Successfully appended final conclusions to ANALYSIS.md.')
