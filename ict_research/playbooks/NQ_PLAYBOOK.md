# NQ Trading Playbook: Momentum & Structure

This playbook provides a deterministic decision tree for trading NQ based on historical probabilities (5,165 trading days).

---

## 🕒 1. NY AM Session (09:30 – 12:00 ET)
**Objective**: Target the high-probability "First Strike" of the London Range.

### IF London Action is: [LONDON_PARTIAL_UP] (Swept Asia High Only)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 77.2% Probability to hit **London High** first.
    *   **ELSE** (Opens Below Mid): 76.2% Probability to hit **London Low** first.

### IF London Action is: [LONDON_PARTIAL_DOWN] (Swept Asia Low Only)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 77.9% Probability to hit **London High** first.
    *   **ELSE** (Opens Below Mid): 73.8% Probability to hit **London Low** first.

### IF London Action is: [ASIA_ENGULFS] (Asia Range Swept Both)
*   **AND** NY opens **ABOVE** London Mid:
    *   **THEN**: 80.4% Probability to hit **London High** first.
    *   **ELSE** (Opens Below Mid): 71.4% Probability to hit **London Low** first.

---

## 🕒 2. NY Lunch Session (12:00 – 13:30 ET)
**Objective**: Scalp the Lunch Reversal or follow the AM Trend.

### IF AM Session trended UP (Set High near end of AM):
*   **THEN**: Target **AM High** (23.7%) for continuation.
*   **ELSE**: Target **AM Low** (17.1%) for mean reversion.

### IF AM Session was choppy/range-bound:
*   **THEN**: Target **London High** (14.2%) or **London Low** (13.4%).

---

## 🕒 3. NY PM Session (13:30 – 16:00 ET)
**Objective**: Predict the final session direction.

### IF PM Opens ABOVE AM Mid:
*   **THEN**: 52.3% Probability to hit **AM High**.
*   **ELSE**: 20.4% Probability to hit **AM Low**.

### IF PM Opens BELOW AM Mid:
*   **THEN**: 43.5% Probability to hit **AM Low**.
*   **ELSE**: 22.7% Probability to hit **AM High**.

---

## 🕒 4. Asia Session (19:30 – 02:30 ET)
**Objective**: Capture the "Deep History" magnets.

### IF Current Day was Bearish Manipulation:
*   **THEN**: 21.9% Probability Asia reverses (hits PM High).
*   **ELSE**: Target **PDC** (31.8% Magnet).

---

## 📉 Flowchart: NY Morning Strike
1.  **Identify London Sweep**: Did it sweep Asia High, Low, or Both?
2.  **Determine NY Open**: Is the 09:30 price above or below the 02:30-05:00 Midpoint?
3.  **Execute**:
    *   Sweep High + Open Above Mid -> **Long to London High**
    *   Sweep Low + Open Below Mid -> **Short to London Low**
    *   Sweep Both + Open Above Mid -> **Long to London High (High Conviction)**
