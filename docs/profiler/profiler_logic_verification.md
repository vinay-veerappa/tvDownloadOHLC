# Profiler Logic & Verification

**Date:** 2025-01-24
**Status:** Verified
**Scope:** Pine Script Table Statistics & Data Architecture

## 1. System Architecture

The Profiler system uses a split-data architecture to optimize for Pine Script limit:

*   **Status & Filtering (`NQ1_profiler.json`)**: Contains the *Session Status* (Long True, Short False, etc.) used to filter historical days.
*   **Table Metrics (`NQ1_daily_hod_lod.json`)**: Contains the *Daily* High/Low prices and times used to calculate the displayed statistics (HOD/LOD Dist, HOD/LOD Time).

> **Critical Learning:** The "Stats" table in Pine Script displays **Daily** metrics (e.g., Daily HOD relative to Daily Open), but filters them based on **Session** outcomes.

## 2. Calculation Logic (Verified)

### A. Distribution Ranges (HOD/LOD Dist)
The displayed percentage range (e.g., `0.3 to 0.6%`) is calculated as the **Union** of two statistical ranges:

1.  **Mode Range**: The 10% bucket with the highest frequency (e.g., `0.3 to 0.4%`).
2.  **Median Range**: The 10% bucket containing the median value (e.g., `0.5 to 0.6%`).
3.  **Display**: `Max(ModeHigh, MedianHigh) to Min(ModeLow, MedianLow)`.

*   **Formula**: `(DailyHigh - DailyOpen) / DailyOpen * 100`
*   **Source**: `NQ1_daily_hod_lod.json` -> `hod_price` / `daily_open`.

### B. Time Buckets (HOD/LOD Time)
The displayed time bucket (e.g., `16:00-16:15`) is a **Mode-only** calculation.

*   **Logic**: It finds the single 15-minute bucket with the highest frequency of occurrences.
*   **Median**: Median is NOT used for Time.

### C. "Asia None" Baseline
The "Asia None" result represents the **Global Baseline** (all days in history), simulated in verification by ignoring the session status filter.

## 3. Verified Results (Global Baseline)

Validation against `NQ1` historical data (approx. 4,850 days):

| Outcome | Matches | HOD Dist (Daily) | HOD Time | Logic Check |
| :--- | :--- | :--- | :--- | :--- |
| **Long True** | **33.9% (1646)** | **0.6 to 0.3%** | 16:00-16:15 | **MATCH** |
| **Long False** | **18.8% (912)** | 0.4 to 0.1% | 16:00-16:15 | MATCH |
| **Short True** | **28.6% (1388)** | 0.3 to 0.0% | 18:00-18:15 | MATCH |
| **Short False** | **18.7% (905)** | 0.5 to 0.1% | 16:00-16:15 | MATCH |

*   **Counts**: Exact match to User Screenshot.
*   **HOD Dist**: Matches User's observed "0.3-0.6%" range (Mode=0.3-0.4, Median=0.5-0.6).

## 4. Implementation Requirements
Any future implementation (Multi-Ticker) must adhere to:
1.  **Load both JSONs**: Join `_profiler.json` and `_daily_hod_lod.json` on Date.
2.  **Deduplicate**: Access keys must handle unique dates only.
3.  **Bit-Packing**: Pine libraries require 50-bit integer packing for efficiency.
