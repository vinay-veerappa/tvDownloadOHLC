---
name: Market Analysis Suite
description: Runs the full technical analysis pipeline (Day Types, Overnight Probabilities, Sequence Stats, Magnet Analysis) for a list of tickers.
applyTo: "**/*.py"
---

# Market Analysis Suite

This skill automates the generation of comprehensive market analysis reports for NQ1, ES1, YM1, RTY1, CL1, and GC1.

## When to use

Use when the user asks for the full technical analysis pipeline — Day Types, Overnight Probabilities, Session Boxes, and bias generation.

## Prerequisites

-   Python environment with `pandas`, `numpy`, `tqdm`.
-   Data available in `data/` (parquet files).

## Workflow Steps

1.  **Run Day Type Classification (Precompute)**
    This script categorizes every day into R1, R2, DWP, or DNP based on structure.
    > Note: This is optimized to run reasonably fast, but processing 6 tickers might take ~1-2 minutes.

    ```powershell
    python scripts/derived/precompute_daily_classification.py --tickers NQ1 ES1 YM1 RTY1 CL1 GC1
    ```

2.  **Generate Probability Reports (Overnight & Sequence)**
    This step generates the Markdown reports predicting day types from overnight action and streaks.

    ```powershell
    # Using the batched helper script
    ./scripts/analysis/run_batched_reports.ps1
    ```

3.  **Run Magnet Analysis (Reversal Drivers)**
    This identifies what specifically causes AM reversals (Round Numbers, Session Levels, etc.).

    ```powershell
    $tickers = @("NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1")
    foreach ($t in $tickers) {
        Write-Host "Running Magnet Analysis for $t..."
        python scripts/analysis/analyze_all_magnets.py $t "docs/DailyClassification/${t}_MARKET_PROBABILITIES.md"
    }
    ```

4.  **Verify Hub Document**
    Ensure `docs/DailyClassification/REVERSAL_MAGNETS_MASTER_HUB.md` exists and is up to date (manually check if new tickers were added).

## Output

-   **Data**: `.parquet` files in `data/derived/`
-   **Reports**: `_MARKET_PROBABILITIES.md`, `_OVERNIGHT_PROBABILITIES.md`, `_SEQUENCE_PROBABILITIES.md` in `docs/DailyClassification/`.
