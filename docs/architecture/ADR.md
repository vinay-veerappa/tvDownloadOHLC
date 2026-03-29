# Architecture Decision Records (ADR)

This file serves as the single source of truth for architectural and behavioral decisions in the tvDownloadOHLC project.

---

## [ADR-001] Data Timezone Contract
**Status:** Approved
**Date:** 2025-12-09

### Context
To support both legacy logic and seamless timezone switching on the frontend.

### Decision
*   **Charts**: Expect Naive UTC inputs, displayed in `America/New_York` by default but offsettable.
*   **Derived JSONs**: Provide a **Hybrid Output**:
    *   `_time` fields (e.g. `hod_time`): **NY-based Strings** ("09:30").
    *   `_ts` fields (e.g. `hod_ts`): **Unix Timestamps** (UTC).
*   **Implementation**: Indicators prefer `_ts` fields for marker alignment.

---

## [ADR-002] Statistical Normalization Standard
**Status:** Approved
**Date:** 2026-03-29

### Context
Absolute price values (e.g., NQ at 10,000 vs 20,000) are context-dependent and prevent reliable historical or cross-ticker comparisons.

### Decision
All statistical reporting and internal calculations for performance metrics (MAE, MFE, Expected Moves, and Session Averages) MUST use **Price Percentage** as the primary basis.

### Implementation Rules
1.  **Basis**: Percentage of the reference price (e.g., Midnight Open or Session Start).
2.  **Reporting**: Values reported in % (e.g., "MFE: +0.42%") rather than points.
3.  **Calculation**: `(Target Price - Reference Price) / Reference Price * 100`
4.  **Exceptions**: Absolute points are reserved only for execution-level "tick" calculations (e.g., slippage), but normalized for aggregate analysis.

---

## [ADR-004] Institutional Session Windows (ALN)
**Status:** Approved
**Date:** 2026-03-26

### Context
Standardizing trading session boundaries for statistical analysis (Asia/London/NY).

### Decision
The following windows (ET) are the **Absolute Rule** for all ALN-based calculations:
| Session | Hours (ET) | Purpose |
| :--- | :--- | :--- |
| **Asia** | 20:00 - 02:00 | Range Establishment |
| **London** | 02:00 - 08:00 | Range Expansion |
| **New York** | 08:00 - 16:00 | Execution |

---

## [ADR-005] Profiler Quadrant Logic (LT/ST/LF/SF)
**Status:** Approved
**Date:** 2026-03-27

### Context
Classifying market behavior based on high/low break sequences within session "Boxes".

### Decision
| Status | Sentiment | Logic |
| :--- | :--- | :--- |
| **Long True (LT)** | Strong Bullish | Break High AND Hold Low. |
| **Short True (ST)** | Strong Bearish | Break Low AND Hold High. |
| **Long False (LF)** | Reversal (Short) | Break High THEN Break Low. |
| **Short False (SF)** | Reversal (Long) | Break Low THEN Break High. |

---

## [ADR-006] Data Fusion Layer Protocol
**Status:** Approved
**Date:** 2026-03-28

### Context
Separation of deep historical data (`data/`) and recent streaming data (`data/live/`).

## [ADR-007] Economic Event Data Fusion
**Status:** Approved
**Date:** 2026-03-29

### Context
Maintaining a comprehensive 26-year historical database of news events (EconomicEvent) while providing real-time scheduling.

### Decision
The **Prisma `EconomicEvent` Table** is officially designated as a **Secondary Source of Truth** for all news-based analytical services, alongside the live ForexFactory/Yahoo feeds.

### Implementation Rules
1.  **Passive Sync**: The Web UI `getDashboardContext` acts as the primary background sync trigger, upserting live feed data into the DB on load.
2.  **Historical Priority**: For backtesting, correlation studies, and "Day-at-a-Glance" history, services MUST query the `EconomicEvent` table to leverage the 9,800+ record archive.
3.  **Blackout Protocol**: The `news_calendar_fetcher.py` script bridges the DB and legacy bots by mirroring the current schedule to `news_blackout.csv`.
4.  **Timezone Integrity**: All dates in the `EconomicEvent` table MUST be stored in **UTC** (per ADR-001) for cross-platform compatibility.
