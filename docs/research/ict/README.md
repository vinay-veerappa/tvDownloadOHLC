# ICT Session Model Research

This research environment is designed to statistically validate the "London Manipulation -> NY Reversal" model using historical 1-minute data.

## Structure

*   **`config.py`**: Settings for session times and detection thresholds.
*   **`data_loader.py`**: Loads and slices parquet data into trading days.
*   **`session_extractor.py`**: Extracts high/low stats for Asia, London, NY.
*   **`pattern_classifier.py`**: Determines Daily Bias based on Overnight action.
*   **`pda_detector.py`**: Detects OBs and FVGs during London.
*   **`outcome_measurer.py`**: Validates if NY reversed the manipulation.
*   **`run_research.py`**: Main pipeline script.
*   **`reporting.py`**: Generates the statistical report.

## How to Run

1.  **Run the Analysis Pipeline**:
    Process the historical data to generate statistics. By default, this uses **parallel processing** on all available CPU cores.
    ```bash
    python ict_research/run_research.py --ticker NQ
    ```
    *Use `--no-parallel` if you encounter memory issues on large datasets.*

2.  **Generate Report**:
    View the results of the analysis for a specific ticker.
    ```bash
    python ict_research/reporting.py --ticker NQ
    ```

## Outputs

*   `ict_research/data/trading_days_{TICKER}.csv`: One row per trading day with all classifications and outcomes.
*   `ict_research/data/pd_arrays_{TICKER}.csv`: All detected London PD arrays and their performance stats.
