# Implementation Plan: Herman Playbook Verification & Extension

## Goal
1.  **Verify** the Herman London Playbook claims using our local `NQ1_1m.parquet` data (BacktestMarket or equivalent).
2.  **Extend** the analysis to create a "NY Playbook" (NY AM and PM sessions) using the same statistical framework.

## Data Requirements
*   **Source**: `data/NQ1_1m.parquet` (Local NQ Futures 1-minute data).
*   **Timezone**: Convert all data to **US/Eastern** (ET) before analysis.
*   **Sessions**:
    *   **Asia**: 20:00 (Prev) – 00:00 (Curr)
    *   **Pre-London**: 00:00 – 02:00
    *   **Opening Range (OR)**: 02:00 – 03:00
    *   **London**: 03:00 – 05:00
    *   *Extension - NY AM*: 07:00 – 10:00 (Base = London + OR?)
    *   *Extension - NY PM*: 13:00 – 16:00 (Base = NY AM?)

## Core Logic Engine: `PlaybookAnalyzer`

We will create a reusable Python class `PlaybookAnalyzer` that accepts:
*   `base_session_times`: (Start, End) e.g., Asia (20:00-00:00)
*   `setup_session_times`: (Start, End) e.g., Pre-London (00:00-02:00)
*   `trigger_session_times`: (Start, End) e.g., Opening Range (02:00-03:00)
*   `expansion_session_times`: (Start, End) e.g., London (03:00-05:00)

### 1. Verification Metrics (London Model)
For each trading day, calculate:

#### A. Base Context (Asia)
*   **Range Size**: High - Low.
*   **Classification**: Large (> 70.9 avg or > 0.45% relative) vs Small.

#### B. Setup Context (Pre-London vs Asia)
*   **Sweep Status**: Did PL sweep Asia High, Low, Both, or None?
*   **Close Status**: Did PL close outside Asia? (Trend implied).

#### C. Trigger Outcome (OR vs PL & Asia)
*   **First Sweep**: Which side of **Pre-London** (or Asia?) did OR break *first*?
    *   *Critical Note*: Herman's Playbook specifically asks "Did OR sweep PL High or Low?".
*   **Penetration**: Max distance beyond the swept level.
*   **Time to Sweep**: Minutes from 02:00 start to the break.

#### D. Expansion Outcome (London vs OR)
*   **Continuation**: Did London continue in the direction of the OR break?
*   **Reversal**: Did London fail and reverse the other way?
*   **Expansion %**: Frequency of breaking the OR High/Low.

### 2. Validation Script (`scripts/validation/verify_london_playbook.py`)
This script will:
1.  Load NQ1 data.
2.  Instantiate `PlaybookAnalyzer` for London.
3.  Generate the "Decision Tree" Stats:
    *   Group by Asia Size (Small/Large).
    *   Group by PL Action (Sweep H, L, None).
    *   Calculate OR First Sweep Probabilities (e.g., "PL Low -> High First 54%?").
    *   Calculate London Continuation Probabilities.
4.  **Compare** output against Herman's constants (hardcoded in script for reference).

### 3. Extension Script (`scripts/validation/generate_ny_playbook.py`)
We will reuse the logic for NY, comparing two potential "Opening Ranges" for the PM session.

#### A. NY AM Session Map (London-Driven)
*   **Base (The Context)**: London (02:00 – 06:00? or 02:00–07:00). *To be defined: likely 02:00-07:00 to capture full overnight magnitude.*
*   **Setup (Pre-OR)**: *Optional/Implicit in Base*.
*   **Trigger (OR)**: **07:00 – 08:00 ET** (07:00–07:59).
*   **Expansion Phase**: 08:00 – 11:00 ET.
*   **Goal**: Test if London Size (Large/Small) predicts NY AM continuity after the 07:00 OR break.

#### B. NY PM Session Map (AM-Driven)
*   **Base (The Context)**: NY AM (07:00 – 12:00).
*   **Setup (Pre-OR)**: Lunch (12:00 – 13:00).
*   **Trigger (OR) - Variant 1**: **Lunch Range** (High/Low of 12:00-13:00).
*   **Trigger (OR) - Variant 2**: **13:00 – 14:00 OR** (13:00-13:59).
*   **Expansion Phase**: 14:00 – 16:00 ET.
*   **Goal**: Compare Variant 1 vs 2 to see which "OR" offers better predictive power for the afternoon close.

## Execution Steps
1.  **Refine Logic**: Update `verify_herman_claims.py` to become `verify_london_playbook.py` with the granular "First Sweep" timestamp logic (argmax).
2.  **Run Validation**: Confirm if our data aligns with Herman's (expect slight deviations due to data provider, but directional alignment).
3.  **Run Extension**: Generate the "NY Playbook" stats.
4.  **Report**: Auto-generate a Markdown report `NY_PLAYBOOK_STATS.md` with the findings.
