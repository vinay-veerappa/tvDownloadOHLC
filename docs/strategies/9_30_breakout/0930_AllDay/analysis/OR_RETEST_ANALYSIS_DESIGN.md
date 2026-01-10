# Design Document: Opening Range (OR) Re-test Analysis
**Date**: January 8, 2026 (Refined V2)
**Target Ticker**: MNQ (and others)
**Timezone**: US/Eastern (EST)

## 1. Objective
To quantify the frequency, timing, and profitability of price returning to the **09:30 Opening Range (OR)** after an initial breakout.
**Key Focus**: "How deep does price retrace inside the box before continuing?" (e.g., Does it touch the 50% midline?)

## 2. Algorithm & Definitions

### A. The Opening Range (OR)
*   **Time Window**: 09:30:00 to 09:30:59 EST.
*   **Attributes**: `OR_High`, `OR_Low`, `OR_Height` (High - Low).

### B. The "Breakout" & "Retest"
*   **Breakout**: First 1-m Close outside OR. Set `Direction` (Bull/Bear).
*   **Re-test Condition**: Price touches the **Breakout Edge** (e.g., if Bullish, Low <= OR_High).

### C. Depth Analysis (Inside the Range)
Once a re-test starts (price re-enters the box), we track how deep it goes.
*   **0% Depth**: Touches the edge (Breakout Level).
*   **50% Depth**: Touches the Midline.
*   **100% Depth**: Touches the opposite edge (Full Reversal).

**Tiers to Track:**
1.  **Touch (0%)**: Did it kiss the line?
2.  **Tier 1 (25%)**: Did it penetrate 25% of the range?
3.  **Tier 2 (50%)**: Did it test the midline?
4.  **Tier 3 (75%)**: Did it go deep?

## 3. Data Structure & Storage
**File Path**: `data/derived/or_retests_{TICKER}.jsonl`
**Format**: All price values in **Percentages** (either % of Underlying Price or % of Range Height) to be time/ticker agnostic.

**Schema (Single Line Record):**
```json
{
  "date": "2026-01-08",
  "ticker": "MNQ1!",
  "or_height_pts": 10.25,
  "or_height_pct_price": 0.06,  // % of asset price (e.g., 10 pts on 15000 = 0.06%)
  "breakout_dir": "Bull",
  "breakout_time": "09:32",
  "retests": [
    {
      "start_time": "09:35",
      "max_depth_pct_range": 55.0, // Retraced 55% into the box (past midline)
      "time_of_max_depth": "09:36",
      "exit_time": "09:38",        // SECONDARY BREAKOUT: Time it left the box again
      "duration_mins": 3,
      "tiers_reached": {
        "25pct": "09:35", 
        "50pct": "09:36",
        "75pct": null
      },
      "excursion_mae_pct_price": -0.05, // Max adverse move (depth) relative to Breakout Edge
      "excursion_mfe_pct_price": 0.45   // Max favorable move (expansion) *after* this re-test sequence
    }
  ]
}
```

## 4. Derived Metrics (For Reporting)
*   **"The Deep Retrace Probability"**: % of re-tests that hit 50% depth but NOT 100% (Valid Midline Test).
*   **"The Kiss & Go"**: % of re-tests that stay < 25% depth.
*   **"Secondary Breakout quality"**: Time from Re-entry -> Secondary Breakout.
*   **"Average MFE by Depth"**: Does a deeper retrace (50%) lead to a bigger move (Springboard effect)?

## 5. Modular Script Architecture

To ensure maintainability, the solution will be split into classes:

### `extract_or_retests.py`
1.  **`class DataLoader`**: Handles CSV parsing, Timezone conversion (UTC -> EST), and Initial validation.
2.  **`class ORDetector`**: Encapsulates logic for finding the 09:30 range (High/Low) and Session filtering.
3.  **`class RetestEngine`**: The core state machine.
    *   *Input*: Stream of OHLC candles.
    *   *State*: `WAIT_FOR_BREAKOUT` -> `MONITOR_RETEST` -> `IN_RETEST` -> `SECONDARY_BREAKOUT`.
    *   *Output*: List of `RetestEvent` objects.

### `analyze_retest_stats.py`
1.  **`class ForensicsReport`**: Loads the JSONL derived data and generates the Markdown report.
    *   Separates *Data Aggregation* (Pandas) from *Visual Presentation* (Markdown generation).

## 6. MAE/MFE Capture Details
*   **Reference Point**: All MAE/MFE are measured relative to the **Breakout Edge** (The "Line in the Sand").
*   **MAE Capture**: Tracks the *Deepest Point* reached inside the box (or out the other side) during the re-test.
*   **MFE Capture**: Tracks the *Highest/Lowest Point* reached in the breakout direction *after* the re-test completes (Secondary Breakout) until EOD.
