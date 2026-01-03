# Commodity Pivot Analysis (Modified Noon Curve)

**Concept**: Adapting the "Noon Curve" (Opposite Side Rule) to Commodities by shifting the pivot time to account for their earlier active sessions (Asia/London dominance).

## Key Findings

The standard 12:00 PM ET pivot fails for commodities. However, shifting the pivot to the **Morning** restores the statistical edge to **~75%** (matching Equities).

| Ticker | Optimal Pivot (ET) | "Opposite Side" Edge | Logic |
| :--- | :--- | :--- | :--- |
| **GC1 (Gold)** | **09:00 AM** | **74.5%** | Gold's "Day" is largely defined in London/Pre-market. By 9:00 AM, one extreme is usually set. |
| **CL1 (Oil)** | **10:00 AM** | **75.2%** | Oil trades slightly later than Gold but earlier than Equities. |

## Strategy Adaptation

### For Gold (GC)
*   **The "Noon" is 09:00 AM ET**.
*   **Rule**: If a High/Low is set between 00:00 AM and 09:00 AM, there is a **74.5% chance** the *opposite* extreme will form *after* 09:00 AM (09:00 - 17:00).
*   **Action**: At 09:00 AM, identify the session High/Low. Expect the *other* side to be broken or formed in the US Session.

### For Oil (CL)
*   **The "Noon" is 10:00 AM ET**.
*   **Rule**: Split the day at 10:00 AM.
*   **Edge**: **75.2%** probability of High/Low on opposite sides of 10:00 AM.

## Comparison Table (Pivot Time vs Success Rate)

| Pivot Time (ET) | Gold (GC) Edge | Oil (CL) Edge | note |
| :--- | :--- | :--- | :--- |
| 08:00 AM | 68.6% | 67.4% | Too early |
| **09:00 AM** | **74.5%** | 72.1% | **Gold Sweet Spot** |
| **10:00 AM** | 67.1% | **75.2%** | **Oil Sweet Spot** |
| 11:00 AM | 54.4% | 70.8% | Edge fading |
| 12:00 PM (Standard) | 42.9% | 59.0% | **Fails (Noon Curve)** |
