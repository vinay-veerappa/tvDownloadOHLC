---
name: Stats Trader
description: Generates a statistical trade plan for the day based on previous day's classification and overnight context.
applyTo: "**/*.py"
---

# Stats Based Day Trader

This skill helps you build a data-driven "Morning Brief" by querying the probability matrices generated from historical analysis.

## When to use

Use when generating a statistical trade plan for the day — based on previous day's classification and session profiler data.

## Workflow

1.  **Identify Context**
    You need to know:
    -   **Ticker**: (e.g., NQ1, ES1)
    -   **Yesterday's Type**: (R1, R2, DWP, DNP) - Check the chart or your log.
    -   **Overnight Status**: (Bullish, Bearish, or specific "long true | short false" status) - Check the Overnight Session tool.

2.  **Generate Plan**
    Run the retrieval script to see what usually happens next.

    ```powershell
    # Example: Yesterday was DWP, Overnight is Bullish
    python scripts/trader/retrieve_daily_stats.py NQ1 --prev DWP --overnight Bullish
    ```

3.  **Interpret Output**
    The tool will output:
    -   **Sequence Edge**: "Yesterday was DWP -> 38% chance today is R2"
    -   **Overnight Edge**: "Overnight Bullish -> 60% chance of Trend Day"
    -   **Strategic Reminder**: Tips for trading the predicted day type.

## Tips
-   Use this during your **08:30 AM** prep routine.
-   If the Overnight and Sequence stats agree (e.g. both predict DWP), increase your risk size.
-   If they contradict, expect a choppy/R1 day.
