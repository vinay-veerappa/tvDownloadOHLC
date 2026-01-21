---
name: ICT Trader
description: Provides key price levels (PDH, PDL, Midnight Open) and bias context based on Inner Circle Trader concepts.
---

# ICT Trader

This skill assists with "Inner Circle Trader" style analysis, focusing on Liquidity, Time, and Price.

## Workflow

1.  **Get Daily Context**
    Retrieve the critical levels for the current trading session.

    ```powershell
    python scripts/trader/retrieve_ict_context.py NQ1
    ```

    **Output**:
    -   **PDH / PDL**: Your primary Draw on Liquidity.
    -   **Midnight Open**: Your Bull/Bear dividing line for the day.
    -   **08:30 Open**: Key level for NY Session news injections.

2.  **Combine with Stats**
    Use this in conjunction with the **Stats Trader** skill.
    -   *Example*: If Stats Trader predicts a **DWP** (Deep Withdrawal/Pullback), you might look for a sweep of **PDH** (Liquidity) followed by a return to **Midnight Open**.

3.  **Key Concepts**
    -   **Power of 3 (AMD)**: Accumulation (Asia), Manipulation (London/NY Open), Distribution (Trend).
    -   **Judas Swing**: Look for a fake move *against* the bias at 9:30 or 02:00.
    -   **Silver Bullet**: Watch the 10:00-11:00 AM window for a Fair Value Gap setup.

## Usage
Run this skill every morning to mark your charts with the correct data-derived levels.
