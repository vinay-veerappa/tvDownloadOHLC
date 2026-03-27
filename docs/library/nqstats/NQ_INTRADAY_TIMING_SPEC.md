# NQ Intraday Timing & Macros (Second Brain)

## 1. Overview
This module defines the critical intraday timing windows for NQ futures, integrating "Judas" swings and statistical reversion points.

## 2. The "Judas" Open (09:30 - 10:00 AM ET)
*   **The Check**: 5m Open Range Breakout (ORB).
*   **Expansion Probability**: If 09:30-09:35 is GREEN, Expect a Late High. 
*   **Rule**: Do NOT fade the initial drive in the first 30 minutes. 76% of early drives hold.

## 3. The "Money Trade" (10:00 AM ET Reversion)
*   **Probability**: >82% win rate when specific criteria are met.
*   **Logic**: High/Low of the 10:00 hour forms in the first 15 minutes (Minute 00-15) 37% of the time.
*   **The Setup**: 
    1.  Price sweeps the 09:00-10:00 range High or Low.
    2.  Must occur between 10:00 and 10:15 AM ET.
    3.  **Action**: Fade back to the 10:00 AM Open.

## 4. The Noon Curve (12:00 PM ET)
*   **Baseline Probability**: 75% chance HOD and LOD occur on opposite sides of Noon.
*   **The Filter**:
    *   If price is *inside* the AM range at 12:00 PM, expect a breakout/expansion in the PM session.
    *   Direction usually follows the confirmed 10:00 AM bias.

## 5. The "Power Hour" (15:00 - 16:00 PM ET)
*   **Trend Persistence**: High/Low forms in the last 15 minutes (Q4) 41% of the time.
*   **Rule**: Trend continuation is the highest probability. Do NOT fade the 3:00 PM move.

## 6. Implementation Reference
- No current automated logic for 10:00 AM Reversion (Pending implementation).
- Noon Curve: `scripts/libs/nqstats/classifiers.py`
