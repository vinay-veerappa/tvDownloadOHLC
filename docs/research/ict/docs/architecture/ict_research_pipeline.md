# ICT Research Pipeline Architecture

## 1. Overview
The ICT Research Pipeline is a high-performance system designed to extract deep session statistics, classify market manipulations, and measure probabilistic outcomes for trading strategies (specifically the "Herman" London Playbook and its extensions).

It processes historical 1-minute OHLC data to generate a rich dataset of `TradingDay` objects, each containing over 60 granular metrics. These metrics feed into a suite of analysis modules that compute conditional probabilities for various market setups.

## 2. Key Responsibilities
-   **Session Extraction**: Identify key price levels (High/Low/Open/Close/Mid/Range) for custom trading sessions (Asia, London, NY AM/PM, Lunch, CBDR, FLOUT).
-   **Pattern Classification**: Classify overnight and intraday price action (e.g., `PARTIAL_UP`, `ENGULFS`, `INSIDE`).
-   **Manipulation Detection**: Identify "Judas Swings" and false moves relative to key reference points.
-   **Outcome Measurement**: Determine if specific price levels were hit, in what order, and if manipulations were reversed.
-   **Normalization**: Convert absolute price ranges into percentages relative to price for multi-year/cross-instrument analysis.
-   **Probabilistic Analysis**: Compute conditional probabilities using decision trees and other statistical methods.

## 3. Data Flow

```mermaid
graph TD;
    RawData[Raw 1m OHLC Parquet/CSV] --> Loader[data_loader.py];
    Loader --> Extractor[session_extractor.py: Phase 1];
    Extractor -- "List[TradingDay]" --> ParallelEngine[run_research.py: Phase 2];
    
    subgraph "Parallel Analysis Core"
        ParallelEngine --> Classifier[pattern_classifier.py];
        ParallelEngine --> Detector[pda_detector.py];
        ParallelEngine --> Measurer[outcome_measurer.py];
        Classifier --> ResultDict;
        Detector --> ResultDict;
        Measurer --> ResultDict;
    end
    
    ResultDict --> CrossDay[Phase 3: Cross-Day Logic];
    CrossDay --> EnhancedCSV[trading_days_enhanced_{TICKER}.csv];
    
    EnhancedCSV --> Reporter[reporting.py];
    
    subgraph "Analysis Modules"
        Reporter --> Mod1[decision_tree.py];
        Reporter --> Mod2[gap_confluence.py];
        Reporter --> Mod3[pm_manipulation.py];
        Reporter --> Mod4[... others ...];
    end
    
    Mod1 --> FinalReport[Console Report / Markdown];
```

## 4. Key Components

### Core Pipeline
-   **`run_research.py`**: The orchestrator using a 3-Phase Parallel Architecture (see `parallelization_strategy.md`).
-   **`session_extractor.py`**: Defines the `TradingDay` dataclass and extracts 60+ raw stats. Now handles **percentage normalization** and new sessions (**FLOUT**).
-   **`outcome_measurer.py`**: Checks if levels were hit, gap fills, and reversal timings.
-   **`config.py`**: Central definition of session times (e.g., `FLOUT` = 20:00-00:00).

### Analysis Modules (`ict_research/analysis/`)
-   **`decision_tree.py`**: computes probabilities for 72 unique scenarios based on Asia Range, London Open, Sweep Type, and NY Position.
-   **`gap_confluence.py`**: Analyzes RTH Gap alignment with manipulation type.
-   **`pm_manipulation.py`**: Analyzes NY PM session behavior relative to AM range.
-   **`cbdr_sigma_analysis.py`**: Standard deviation reach based on CBDR range.
-   **`asia_prediction.py`**: Validates the "Asia Prediction Model".
-   (Plus `timing_analysis`, `sweep_order_analysis`, `dow_analysis`, `range_effects`, `pm_bias`).

## 5. Technology & Constraints
-   **Parallelization**: Uses `multiprocessing.Pool` (Phase 2) to handle heavy computation.
-   **Data Dependency**: Phase 1 must be sequential (history preservation). Phase 3 must be sequential (future dependency).
-   **Memory**: Uses `groupby` caching in memory for O(1) access to 1-minute data chunks.
-   **Metric Normalization**: All ranges are stored as `% of Price` (e.g., `asia_range_pct`) to allow comparison across decades (NQ 2000 vs NQ 20000).

## 6. Comprehensive Data Dictionary (Enhanced)

### Session Definitions
| Session | Time (ET) | Purpose |
| :--- | :--- | :--- |
| **Asia** | 19:30 - 02:30 | Initial range definition. |
| **London** | 02:30 - 08:00 | The "Judas" manipulation session. |
| **NY AM** | 09:30 - 12:00 | Primary expansion leg. |
| **Lunch** | 12:00 - 13:30 | Retracement/Consolidation. |
| **NY PM** | 13:30 - 16:00 | Secondary leg or Reversal. |
| **CBDR** | 14:00 - 20:00 | Central Bank Dealers Range (Classic). |
| **FLOUT** | 20:00 - 00:00 | Fish Lure / Turtle Soup reference range. |

### New Normalized Metrics
*   `asia_range_pct`: Asia Range / Globex Open * 100
*   `london_sweep_up_pct`: (London High - Asia High) / Asia Mid * 100
*   `london_high_from_ny_open_pct`: Distance normalized to NY Open.
*   `cbdr_range_pct_of_price`: Relative volatility of CBDR.

### Position Classifications
*   `london_open_vs_asia_mid`: **ABOVE_ASIA_MID** / **BELOW_ASIA_MID** (Determines London bias).
*   `ny_position`: **ABOVE_LONDON_MID** / **BELOW_LONDON_MID**.
*   `manipulation_type`: **BULLISH_MANIPULATION** / **BEARISH_MANIPULATION** (Did London sweep one side and close inside/reversing?).

## 7. Methodology: Decision Tree Analysis
The system computes conditional probabilities (`decision_tree.py`) based on 5 branching factors:
1.  **Asia Range Size**: Above/Below 50-day median.
2.  **London Open Position**: Above/Below Asia Mid.
3.  **London Sweep Type**: High First, Low First, Both, None.
4.  **NY Open Position**: Above/Below London Mid.
5.  **NY Outcome**: Sweep London High/Low/Reversal.

This creates a **72-Branch Decision Matrix** to predict the most likely NY Session outcome.

## 8. Recent Fixes & Enhancements (Feb 2026)
### Critical Bug Fixes
-   **CBDR Sigma Hits**: Fixed a field name mismatch where `setattr` was generating strings like `_2_0` instead of `_2`, causing all sigma hit flags to report as `False`. Logic now uses explicit assignments.
-   **Missing Data Export**: Overhauled `run_research.py` to use `dataclasses.asdict()`, ensuring 60+ calculated fields (Percentage Ranges, Time-based Opens, detailed Hit Flags) are correctly written to the CSV.
-   **Logic Deduplication**: Cleaned up `session_extractor.py` to remove redundant calculation blocks and duplicate field definitions.

### Added Metrics
-   **Full CBDR Sigma Analysis**: 0.5 to 4.0 standard deviations (Up/Down) with both Price Levels and Boolean Hit Flags.
-   **Time-Based Opens**: Midnight, 07:30, 08:30, 13:30 (PM Open) explicitly tracked.
-   **Relative Percentages**: Ranges and distances normalized to opening prices (Globex/Asia/NY) for cross-era analysis.
-   **Detailed Outcomes**: Specific flags for hitting London High/Low, Overnight High/Low, and P12 Extremes.
