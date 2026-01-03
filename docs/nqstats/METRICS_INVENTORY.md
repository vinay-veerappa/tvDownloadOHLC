# NQStats Metrics Inventory

Based on research from [nqstats.com](https://nqstats.com), the following statistical scenarios are available for verification against our local ticker data.

## 1. Initial Balance (IB) Breaks
**Definition**: The range formed during the first hour of RTH (9:30 AM - 10:30 AM ET).
*   **Metric 1.1**: Probability that IB High or Low is broken before 4:00 PM ET. (Claim: ~96%)
*   **Metric 1.2**: Probability that IB High or Low is broken before 12:00 PM ET. (Claim: ~83%)
*   **Metric 1.3**: If IB closes in the upper half, probability that IB High is broken. (Claim: ~81%)

## 2. RTH Breaks (Relative to Prior Day)
**Definition**: Relationship between today's opening RTH price and yesterday's RTH range (pRTH).
*   **Metric 2.1 (Outside Open)**: If Open is OUTSIDE pRTH, probability of NOT breaking the far side of pRTH. (Claim: ~83%)
*   **Metric 2.2 (Inside Open)**: If Open is INSIDE pRTH, probability of breaking at least one side of pRTH. (Claim: ~72%)

## 3. The Morning Judas
**Definition**: Initial moves and reversals/continuations at 9:40 AM and 10:00 AM.
*   **Metric 3.1 (Up Judas)**: If 9:30-9:40 is UP, probability of continuation (10:00 > 9:40). (Claim: ~64%)
*   **Metric 3.2 (Down Judas)**: If 9:30-9:40 is DOWN, probability of continuation (10:00 < 9:40). (Claim: ~70%)

## 4. ALN Sessions (Asia/London/NY)
**Definition**: Interaction between overnight session ranges and the NY session.
*   **Metric 4.1**: Probability that NY Session breaks at least one side of London Session High/Low. (Claim: ~98%)
*   **Metric 4.2**: Probability that NY Session "engulfs" London (breaks BOTH High and Low). (Claim: ~43%)

## 5. Hour Stats / Sweeps
**Definition**: Probability of retracing to Open after sweeping High/Low of previous hour.
