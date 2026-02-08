# CL Trading Playbook: Liquidity Sniper

This playbook provides a deterministic decision tree for trading CL based on historical probabilities (4,490 trading days).

---

## 🕒 1. NY AM Session (09:30 – 12:00 ET)
**Objective**: Target un-swept liquidity with high precision.

### IF London Action is: [ASIA_ENGULFS] (Asia Range Swept Both)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 73.3% Probability to hit **London High** first.
*   **AND** NY opens **BELOW** London Mid:
    *   **THEN**: 74.7% Probability to hit **London Low** first.

### IF London Action is: [LONDON_PARTIAL_UP] (Swept Asia High Only)
*   **AND** NY opens **BELOW** London Mid:
    *   **THEN**: 70.0% Probability to hit **London Low** first.

### IF London Action is: [LONDON_PARTIAL_DOWN] (Swept Asia Low Only)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 73.2% Probability to hit **London High** first.

---

## 🕒 2. NY Lunch Session (12:00 – 13:30 ET)
**Objective**: Scalp the Lunch Reversal.

### IF Morning Trend was Bullish (Set High near end of AM):
*   **THEN**: Target **AM High** (21.2%) for final expansion.
*   **ELSE**: Target **AM Low** (19.4%) for reversal.

---

## 🕒 3. NY PM Session (13:30 – 16:00 ET)
**Objective**: Predict PM reversal or trend continuation.

### KEY MAGNETS:
*   **Lunch High**: 25.4% Probability.
*   **Lunch Low**: 23.0% Probability.
*   **AM High**: 13.8% (Trend Continuation).

### JUDAS FACTOR (PM):
*   **CL has a 17.7% Judas Day rate**. If PM sweeps AM High/Low and fails, Expect **~60% reversal rate**.

---

## 🕒 4. Asia Session (19:30 – 02:30 ET)
**Objective**: Capture the "Deep History" magnets.

### PRIMARY MAGNET:
*   **PDC (Previous Day Close)**: 31.9% Hit Rate. This is the most reliable target for the overnight transition in oil.

---

## 📉 Flowchart: CL Morning Tactical
1.  **London Filter**: Wait for 05:00 ET. Identify if Asia High or Low was breached.
2.  **Open Alignment**: Check 09:30 price relative to London Midpoint.
3.  **Execute**:
    *   One side swept? Target the **Other side**.
    *   Both sides swept? Target the side **aligned with the NY Open** (Above Mid = Target High).
    *   No sweep? Probability is low (~12%). Wait for a liquidity sweep first.
