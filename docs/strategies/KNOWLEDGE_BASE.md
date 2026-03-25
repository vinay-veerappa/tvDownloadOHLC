# Strategy & Data Knowledge Base

## 1. Data Inventory Map

| Data Set | Location | Content | Key Uses |
| :--- | :--- | :--- | :--- |
| **NQ1 Min/Hourly** | `data/NQ1_1m.parquet` | Raw OHLC (1m, 1h) | Backtesting, Simulation |
| **NQ Stats** | `scripts/nqstats/results/*.csv` | Hourly Personalities, Breaks | Volatility Filters, Probabilities |
| **Profiler** | `data/{ticker}_profiler.json` | Session HOD/LOD, ranges | Context, Daily Bias |
| **Opening Range** | `data/{ticker}_opening_range.json` | 9:30 Range Metrics | Breakout Strategies |
| **Sessions** | `data/sessions/` | Session definitions | Session-based Logic |

## 2. Strategy Registry

### A. NY Session Statistical Strategy (Magic Hour)
*   **Path:** `docs/strategies/magic_hour_analysis/`
*   **Status:** ⏸️ Paused (Debugging "No Trades")
*   **Core Data:** `NQ1_1m.parquet`, `nqstats` (Median Distribution)
*   **Concept:** Breakout of 9:30-9:40 range using 20-day median distribution as a filter.

### B. Initial Balance Break
*   **Path:** `scripts/strategies/initial_balance/data/`
*   **Status:** ✅ Proven (See results folder)
*   **Core Data:** `initial_balance` stats
*   **Concept:** Breakout of first hour range.

### C. 9:30 Breakout
*   **Path:** `docs/strategies/9_30_breakout/`
*   **Status:** 🚧 In Progress/Legacy?
*   **Core Data:** `opening_range.json`
*   **Concept:** Simple range breakout strategies.

### D. Generic Periodic ORB
*   **Path:** `docs/strategies/generic_periodic_orb/`
*   **Status:** 🛠️ Refinement
*   **Concept:** Generalized ORB logic.

## 3. Analysis Tools
*   `scripts/nqstats/`: Source of "Proven" statistical edges.
*   `scripts/derived/`: Generators for JSON data.

## 4. Derived Data Reference
*   **HOD/LOD:** Probability of High/Low being set in specific hours.
*   **Level Touches:** Interaction with previous day levels.
