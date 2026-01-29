# NQ NY Session Playbook Stats (Verification & Extension)

**Generated**: Jan 2026
**Data Source**: `NQ1_1m.parquet` (5,000+ Days)

## 1. London Playbook Verification
We verified Herman's "London Playbook" logic against our local dataset.

### Large Asia (> 70.9 pts)
*   **First Sweep Bias**: **58.3% High** / 41.1% Low.
    *   *Herman Ref*: Fits the "Continuation" narrative (Large Asia + Setup Sweep -> Strong Continuation).
*   **Median Penetration**:
    *   High Breaks: **29.75 pts** (Herman: 25-38 pts).
    *   Low Breaks: **32.25 pts**.
*   **Verdict**: **Verified**. Large Asia days produce larger clean moves (~30 pts) and strong directional outcomes.

### Small Asia (<= 70.9 pts)
*   **First Sweep Bias**: **51.3% High** / 48.0% Low (Balanced).
*   **Median Penetration**:
    *   High Breaks: **17.50 pts** (Herman: 17-24 pts).
    *   Low Breaks: **19.25 pts**.
*   **Verdict**: **Verified**. Small Asia days are choppy/balanced with significantly smaller extensions (~18 pts).

---

## 2. NY AM Session Extension
*   **Base**: London Session (02:00 – 07:00 implied context).
*   **Setup**: Pre-Market (05:00 – 07:00).
*   **Trigger (OR)**: **07:00 – 08:00 ET**.
*   **Expansion**: 08:00 – 11:00 ET.

### Stats (All Days)
*   **First Sweep Bias**:
    *   High First: **51.4%**
    *   Low First: **48.0%**
    *   (Almost perfectly balanced).
*   **Context Correlation**:
    *   If Pre-Market (05-07) Sweeps High -> NY AM Sweeps High: **49.0%**.
    *   **Insight**: NY AM does **NOT** blindly follow the Pre-Market sweep direction. It is a true "Decision Node".
*   **Median Penetration**:
    *   High Breaks: **15.25 pts**.
    *   Low Breaks: **17.12 pts**.
    *   *Note*: These are smaller than London penetrations? Likely due to 07:00-08:00 being a "Waiting for Open" period. The real expansion happens after 09:30.

---

## 3. NY PM Session Extension (The Duel)
We tested two definitions for the "Afternoon Opening Range".

### Variant A: Lunch Range Trigger (12:00 – 13:00)
*   **Trigger**: High/Low of the 12:00-13:00 hour.
*   **Expansion**: 13:00 – 16:00.
*   **First Sweep Bias**: **53.5% High** (Bullish Tilt).
*   **Median Penetration**: **11.50 / 13.75 pts**.

### Variant B: 13:00 OR Trigger (13:00 – 14:00)
*   **Trigger**: High/Low of the 13:00-14:00 hour.
*   **First Sweep Bias**: **51.7% High**.
*   **Median Penetration**: **9.50 / 11.00 pts**.

### Comparison & Selection
*   **Directional Signal**: Variant A (Lunch Range) has a stronger signal (53.5%) than Variant B (51.7%).
*   **Magnitude**: Variant A captures larger moves (11-13 pts) vs Variant B (9-11 pts).
*   **Conclusion**: **Use the Lunch Range (12:00-13:00)** as the "PM Opening Range". The breakout of Lunch sets the tone for the afternoon.

---

## Final Recommendation: The Full Day Map

| Session | Time (ET) | Trigger Logic | Median Target |
| :--- | :--- | :--- | :--- |
| **London** | 03:00 – 05:00 | **02:00 – 03:00 OR** | ~30 pts (Lg Asia) / 18 pts (Sm Asia) |
| **NY AM** | 08:00 – 11:00 | **07:00 – 08:00 OR** | ~16 pts (Scalp Focus) |
| **NY PM** | 13:00 – 16:00 | **12:00 – 13:00 OR** | ~12-14 pts (Grind Focus) |

**Note**: NY AM Penetration might improve if we shift the "Trigger" to **09:30 – 10:00 (The Open)** instead of 07:00. The 07:00 OR is often a pre-market range that gets whipped at 09:30.
