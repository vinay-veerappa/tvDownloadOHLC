# ES Trading Playbook: Structural Precision

This playbook provides a deterministic decision tree for trading ES based on historical probabilities (5,166 trading days).

---

## 🕒 1. NY AM Session (09:30 – 12:00 ET)
**Objective**: Target structural magnets with lower volatility than NQ.

### IF London Action is: [ASIA_ENGULFS] (Asia Range Swept Both)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 74.3% Probability to hit **London High** first.
*   **AND** NY opens **BELOW** London Mid:
    *   **THEN**: 80.2% Probability to hit **London Low** first.

### IF London Action is: [LONDON_PARTIAL_UP] (Swept Asia High Only)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 78.6% Probability to hit **London High** first.
*   **AND** NY opens **BELOW** London Mid:
    *   **THEN**: 76.7% Probability to hit **London Low** first.

### IF London Action is: [LONDON_PARTIAL_DOWN] (Swept Asia Low Only)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 77.9% Probability to hit **London High** first.
*   **AND** NY opens **BELOW** London Mid:
    *   **THEN**: 74.9% Probability to hit **London Low** first.

---

## 🕒 2. NY Lunch Session (12:00 – 13:30 ET)
**Objective**: Identify the "Lunch Magnet" for structural reversion.

### IF Morning Trend was clearly Bearish:
*   **THEN**: Target **London Low** (13.7%) or **AM Low** (17.1%).
*   **ELSE**: Target **London High** (13.7%).

---

## 🕒 3. NY PM Session (13:30 – 16:00 ET)
**Objective**: Predict PM reversal or trend continuation.

### KEY MAGNETS:
*   **Lunch High**: 26.6% Probability (Primary Reversal Target).
*   **Lunch Low**: 20.2% Probability.
*   **AM High**: 14.7% (Trend Continuation).

---

## 🕒 4. Asia Session (19:30 – 02:30 ET)
**Objective**: Capture the "Deep History" magnets.

### IF Current Day was Bullish Manipulation:
*   **THEN**: 64.7% Expectation of reversal (if Gap Up).
*   **PRIMARY MAGNET**: **PDC** (32.1% Hit Rate).

---

## 📉 Flowchart: ES Morning Decision Tree
1.  **London Evaluation**: Did London sweep Asia High/Low?
2.  **NY Open Check**: Midpoint of London Session (02:30-05:00).
3.  **Execute Based on Open Alignment**:
    *   Open > Lon Mid + Sweep Low = **Target Lon High**
    *   Open < Lon Mid + Sweep High = **Target Lon Low**
    *   "No Sweep" Day? Probability of hitting Lon High drops to **~60%**. Avoid high conviction.
