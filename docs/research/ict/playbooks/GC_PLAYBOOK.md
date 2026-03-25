# GC Trading Playbook: Mean Reversion Focus

This playbook provides a deterministic decision tree for trading Gold (GC) based on historical probabilities (4,571 trading days).

---

## 🕒 1. NY AM Session (09:30 – 12:00 ET)
**Objective**: Target un-swept liquidity with higher volatility tolerance.

### IF London Action is: [ASIA_ENGULFS] (Asia Range Swept Both)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 65.6% Probability to hit **London High** first.
*   **AND** NY opens **BELOW** London Mid:
    *   **THEN**: 66.5% Probability to hit **London Low** first.

### IF London Action is: [LONDON_PARTIAL_UP] (Swept Asia High Only)
*   **AND** NY opens **BELOW** London Mid:
    *   **THEN**: 71.1% Probability to hit **London Low** first.

### IF London Action is: [LONDON_PARTIAL_DOWN] (Swept Asia Low Only)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 68.7% Probability to hit **London High** first.

---

## 🕒 2. NY Lunch Session (12:00 – 13:30 ET)
**Objective**: Scalp the Lunch Reversal or follow the AM Trend.

### IF AM Session was Trending:
*   **THEN**: Target **AM High** (21.1%) or **AM Low** (18.4%).
*   **ELSE**: Target **London Low** (13.3%) for a deeper retracement.

---

## 🕒 3. NY PM Session (13:30 – 16:00 ET)
**Objective**: Predict PM reversal or trend continuation.

### KEY MAGNETS (Highest across all tickers):
*   **Lunch High**: 26.6% Probability.
*   **Lunch Low**: 25.2% Probability.
*   **AM Low**: 11.7% (Trend Continuation).

---

## 🕒 4. Asia Session (19:30 – 02:30 ET)
**Objective**: Capture the "Deep History" magnets.

### PRIMARY MAGNET:
*   **PDC (Previous Day Close)**: 27.4% Hit Rate. Note: Gold drifts less reliably to PDC than Oil/Tech.

---

## 📉 Flowchart: GC Morning Analysis
1.  **London Sweep Check**: Wait for the 05:00 ET close.
2.  **NY Open Position**: Is price > or < London Midpoint?
3.  **Execute**:
    *   Gold has a lower "First Strike" probability than Oil (~65-70%). 
    *   **Priority Setup**: Sweep High + Open Below Mid -> **Target London Low**.
    *   If NY opens at the midline, Gold is statistically and structural "No Trade" until a side is taken.
