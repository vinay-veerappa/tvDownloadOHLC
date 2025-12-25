# Data Anomaly Report

**Generated:** December 25, 2025
**Purpose:** Document remaining price anomalies after fresh NinjaTrader imports for user verification.

---

## Summary

| Ticker | Total Rows | Anomaly Threshold | Anomalies | Status |
|--------|------------|-------------------|-----------|--------|
| **ES1** | 6,214,524 | >80pt | 11 | ✅ Imported |
| **NQ1** | 5,895,490 | >200pt | 25 | ✅ Imported |
| **YM1** | 5,886,390 | >80pt | 2,477 | ⚠️ Normal volatility |
| **RTY1** | 2,768,519 | >80pt | 1 | ✅ Clean |
| **GC1** | 6,153,069 | >80pt | 1 | ✅ Clean |
| **CL1** | 6,004,895 | >80pt | 0 | ✅ Clean |

---

## ES1 Anomalies (11 occurrences, >80pt moves)

These dates may contain data issues or represent legitimate high-volatility events:

| Date/Time | Price Move | Notes |
|-----------|------------|-------|
| 2025-02-02 18:00:00 | 112.75pt | Session start |
| 2025-04-02 16:42:00 | 131.75pt | |
| 2025-04-02 16:43:00 | 137.00pt | |
| 2025-04-02 17:00:00 | 138.75pt | Session end |
| 2025-04-02 18:00:00 | 186.25pt | Session start |
| 2025-04-04 09:59:00 | 96.75pt | |
| 2025-04-04 10:00:00 | 109.00pt | |
| 2025-04-04 17:00:00 | 81.00pt | |
| 2025-04-06 18:00:00 | 163.75pt | Weekend gap |
| 2025-04-06 18:02:00 | 101.75pt | |
| 2025-04-08 17:00:00 | 105.75pt | |

---

## NQ1 Anomalies (25 occurrences, >200pt moves)

| Date/Time | Price Move | Notes |
|-----------|------------|-------|
| 2025-01-26 23:00:00 | 213.25pt | |
| 2025-02-02 23:00:00 | 584.50pt | Large gap |
| 2025-02-12 13:30:00 | 233.75pt | |
| 2025-04-02 20:13:00 | 203.75pt | |
| 2025-04-06 22:00:00 | 776.75pt | Weekend gap |
| 2025-04-06 22:03:00 | 211.75pt | |
| 2025-04-07 00:04:00 | 209.25pt | |
| 2025-04-07 14:10:00 | 292.25pt | High volatility period |
| 2025-04-07 14:13:00 | 244.50pt | |
| 2025-04-07 14:18:00 | 319.25pt | |
| 2025-04-07 14:20:00 | 210.25pt | |
| 2025-04-07 14:34:00 | 215.00pt | |
| 2025-04-07 15:14:00 | 296.00pt | |
| 2025-04-07 17:00:00 | 208.25pt | |
| 2025-04-09 07:02:00 | 334.25pt | |
| *(additional entries truncated)* | | |

---

## Observations

1. **April 2025** shows concentrated volatility across ES and NQ - this aligns with known market events.
2. **Session boundaries** (17:00, 18:00, 23:00) often show large gaps due to overnight/weekend gaps.
3. **YM1** has 2,477 "anomalies" which is normal for DJIA (smaller point moves have larger % impact).

---

## Verification Steps

For each date above, the user should:
1. Open the chart at that date/time
2. Verify if the price move appears correct (e.g., legitimate gap vs. data error)
3. If corrupt data is found, notify for manual correction

