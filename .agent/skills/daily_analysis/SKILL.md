---
name: Daily Analysis
description: Runs a comprehensive daily market analysis including data sync, classification updates, ICT context, and wargame scenario generation.
applyTo: "**/*.py"
---

# Daily Market Analysis (Master Skill)

This is your primary "Start of Day" routine. It automates the data pipeline and generates a strategic briefing.

## When to use

Use when the user asks for daily market analysis — runs data sync, classification, and bias generation for the current trading day.

## Workflow

1.  **Data Acquisition (Bridge)**
    -   Connects to Schwab (via `fetch_schwab_data.py`) to download any missing 1-minute and 1-hour candles for NQ, ES, etc.
    -   Updates local Parquet files.

2.  **Classification Update**
    -   Runs `precompute_daily_classification.py` to classify recent days (R1, R2, DWP, DNP).

3.  **Context Generation**
    -   **ICT Levels**: pdh/pdl/midnight_open from `retrieve_ict_context.py`.
    -   **Statistical Probability**: Accesses the Probability Matrix (Overnight/Sequence).
    -   **Profiles & Calendar**: (Skeleton) Checks for key weekly profiles and news events.

4.  **Wargame Synthesis**
    -   Combines all inputs into a "If This / Then That" plan.

## Usage

Run this command once per day (e.g. at 08:00 AM EST):

```powershell
# Analyze NQ and ES
python scripts/trader/run_daily_prep.py --tickers NQ1 ES1
```

## Configuration
-   **Tickers**: Defaults to NQ1, ES1. Can add others via command line.
-   **Data**: Requires `token.json` for Schwab access (auto-refreshes if valid).
