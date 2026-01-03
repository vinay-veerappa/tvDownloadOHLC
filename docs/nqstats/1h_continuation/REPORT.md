# 1H Continuation Verification Report

**Source**: [NQStats - Hour Stats](https://nqstats.com/hour-stats) (Credit to NQStats)
**Date Verified**: January 3, 2026
**Tickers Analyzed**: NQ, ES, YM, RTY, GC, CL (10 Years: 2014-2025)
**Source Logic**: 9AM-10AM Candle Color Predicting NY Session Direction.

## Executive Summary

The **1H Continuation** metric is **STRONGLY VERIFIED** for Equity Futures (NQ, ES, RTY, YM).
*   **The Edge**: If the **09:00-10:00 AM ET Candle** closes **GREEN**, there is a **~70% Probability** that the entire NY Session (09:30 Open vs 16:00 Close) will be **GREEN**.
*   **NQ Performance**: NQ shows the strongest correlation at **71.6%** (beating the claim of 70%).

## 1. Bullish Continuation (9AM Green -> NY Green)
Probability that a Green 9AM Hour leads to a Green NY Session.

| Ticker | Win Rate (Validation) | Claim | Status |
| :--- | :--- | :--- | :--- |
| **NQ1** | **71.6%** | 70% | ✅ **STRONGER** |
| **RTY1** | **69.7%** | - | ✅ **STRONG** |
| **ES1** | 68.1% | - | ✅ VALID |
| **YM1** | 67.8% | - | ✅ VALID |
| **GC1** | 61.4% | - | WEAK |
| **CL1** | 59.9% | - | WEAK |

## 2. Bearish Continuation (9AM Red -> NY Red)
Probability that a Red 9AM Hour leads to a Red NY Session.

| Ticker | Win Rate (Validation) | Claim | Status |
| :--- | :--- | :--- | :--- |
| **RTY1** | **66.8%** | - | ✅ **STRONG** |
| **NQ1** | **62.7%** | 60% | ✅ **VALID** |
| **YM1** | **61.6%** | - | ✅ VALID |
| **GC1** | **60.6%** | - | ✅ VALID |
| **ES1** | 60.4% | - | ✅ VALID |
| **CL1** | 58.2% | - | WEAK |

## 3. Operational Strategy
*   **Wait for 10:00 AM ET**.
*   **Check Candle**: Is the 1H Candle (09:00-10:00) Green or Red?
*   **Set Bias**:
    *   **If Green**: Expect "Buy Dips" behavior for the rest of the day. Target a 16:00 Close above the 09:30 Open.
    *   **If Red**: Expect "Sell Rallies" behavior (though the edge is slightly weaker than the Bullish side).

## 4. Source Code & Data
*   **Verification Script**: [verify_1h_continuation.py](file:///scripts/nqstats/1h_continuation/verify_1h_continuation.py)
*   **Raw Results (CSV)**: [1h_continuation_verification.csv](file:///scripts/nqstats/results/1h_continuation_verification.csv)