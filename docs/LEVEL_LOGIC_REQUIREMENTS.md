
# Level Logic & Time Range Requirements

**Last Updated:** Dec 2025
**Philosophy:** "08-12 Philosophy" / Strict Post-Establishment Validity

This document defines the strict logic, time windows, and trading day definitions used in the Profiler and Level Statistics calculation.

## 1. Trading Day Definition
*   **Start**: 18:00 ET (Previous Calendar Day)
*   **End**: 17:00 ET (Current Calendar Day)
*   **Anchor**: All statistical calculations (histograms, hit rates) are anchored to **18:00 ET**. Timestamps are minutes from 18:00.

## 2. Touch Validity Logic ("08-12 Philosophy")
A level is strictly considered "touched" **only after** its establishment time has passed. Any price action *during* the establishment period (or before it) is ignored for statistical touch counting.

## 3. Specific Level Definitions & Valid Time Windows

All times are in **US/Eastern (ET)**.

### Time-Based Opens
| Level Name | Establishment Time | Valid Touch Window | Notes |
| :--- | :--- | :--- | :--- |
| **Daily Open** | 18:00 | **18:00 - 17:00** | Full Trading Day |
| **Midnight Open** | 00:00 | **00:00 - 17:00** | Strict 00:00 Start |
| **07:30 Open** | 07:30 | **07:30 - 17:00** | Strict 07:30 Start |

### Session Mids
Mid levels are established at the **end** of their respective session establishment window. They can only be "touched/retested" *after* that window closes.

| Level Name | Establishment Time | Valid Touch Window | Notes |
| :--- | :--- | :--- | :--- |
| **Asia Mid** | 02:00 | **02:00 - 17:00** | Asia Session Ends 02:00 |
| **London Mid** | 07:00 | **07:00 - 17:00** | London Session Ends 07:00 |
| **NY1 Mid** | 12:00 | **12:00 - 17:00** | NY1 Session Ends 12:00 |
| **NY2 Mid** | 16:00 | **16:00 - 17:00** | (Currently Removed from UI) |

### Overnight Levels (P12)
| Level Name | Definition | Valid Touch Window | Notes |
| :--- | :--- | :--- | :--- |
| **P12** | 18:00 - 06:00 | **06:00 - 17:00** | Touches valid only after 06:00 |

## 4. UI Chart Bounding
All Charts in the Profiler UI must strictly adhere to the **Valid Touch Window** defined above.
*   **Do not** show "Daily" (18-17) range for levels that only exist after 07:00.
*   **Do not** include touches/hits from before the Valid Window in Hit Rate % calculations.

## 5. Backend Calculation Reference
*   **Script**: `api/scripts/precompute_level_stats.py`
*   **Logic**:
    1.  Load 1m Data.
    2.  Define **Trading Day** (18:00 D-1 to 17:00 D).
    3.  For each level, define `valid_start_time`.
    4.  Filter price data: `valid_slice = day_slice[valid_start_time:]`.
    5.  Check for touches only within `valid_slice`.
