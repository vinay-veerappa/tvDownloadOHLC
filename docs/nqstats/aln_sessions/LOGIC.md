# ALN Sessions Logic (Asia, London, New York)

**Source**: NQStats "ALN Sessions" Video Transcript
![ALN Stats Info](ALN_INFO.png)
**Concept**: Analyzing how the interaction between Asia and London sessions predicts New York session behavior.

## 1. Session Definitions (Eastern Time)

| Session | Start (ET) | End (ET) | Notes |
| :--- | :--- | :--- | :--- |
| **Asia** | 20:00 (Prior Day) | 02:00 | |
| **London** | 02:00 | 08:00 | Use 08:00 as cutoff (NY Pre-market starts, London continues but stats use 08:00) |
| **New York** | 08:00 | 16:00 | Includes pre-market from 08:00 |

## 2. Session Classifications

We classify the **London** session based on its relationship to the **Asia** session range.

1.  **London Engulfs Asia (LEA)**
    *   London High > Asia High AND London Low < Asia Low.
    *   London trades WIDER than Asia.

2.  **Asia Engulfs London (AEL)**
    *   London High <= Asia High AND London Low >= Asia Low.
    *   London stays INSIDE Asia. (Rare: ~7% frequency).

3.  **London Partially Engulfs Up (LPEU)**
    *   London High > Asia High AND London Low >= Asia Low.
    *   London breaks UP but holds the low.

4.  **London Partially Engulfs Down (LPED)**
    *   London Low < Asia Low AND London High <= Asia High.
    *   London breaks DOWN but holds the high.

## 3. Statistical Claims (Probabilities for NY Session)

The "Claims" are what we expect the **New York Session (08:00 - 16:00)** to do.

### If London Engulfs Asia (LEA)
*   **Claim 1**: NY breaks London High OR London Low: **~80%**
*   **Claim 2**: NY breaks BOTH London High AND Low: **~64%**

### If Asia Engulfs London (AEL)
*   **Claim 1**: NY breaks Asia High: **~74%**
*   **Claim 2**: NY breaks Asia Low: **~63%**
*   **Claim 3**: NY breaks BOTH Asia High AND Low: **~42%**

### If London Partially Engulfs Up (LPEU)
*   **Claim 1**: NY breaks London High (Continuation): **~78%**
*   **Claim 2**: NY breaks London Low (Reversal): **~63%**
*   **Claim 3**: NY breaks Asia Low (Full Reversal): **~54%**
*   **Claim 4**: NY breaks BOTH (Full Engulf): **~36%**

### If London Partially Engulfs Down (LPED)
*   **Claim 1**: NY breaks London Low (Continuation): **~82%**
*   **Claim 2**: NY breaks London High (Reversal): **~58%**
