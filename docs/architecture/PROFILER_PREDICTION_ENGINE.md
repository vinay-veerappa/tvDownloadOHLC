# Profiler Prediction Engine Architecture

## 1. Overview

The Profiler Prediction Engine extends the session profiling system by introducing predictive probabilities for future trading sessions based on the specific "Signature" of previous sessions. It attempts to answer: _"Given NY1 broke High and NY2 broke Low yesterday, what does Asia usually do today?"_

## 2. Key Responsibilities

- **Data aggregation**: Merging Session Status (Trend) with Unadjusted Price Data (Volatility).
- **Context Mapping**: Linking `Previous Day` sessions to `Current Day` targets (e.g., Prev NY -> Current Asia).
- **Probability Generation**: Calculating frequency distributions for Session Status (Long True, Short False, etc.) and Price Extremes (HOD/LOD %).
- **Serving**: Providing these lookup tables to the Web UI for real-time analysis.

## 3. Data Flow

```mermaid
graph TD
    A[data/NQ1_profiler.json<br/>(Session Status)] --> C[scripts/profiler/generate_prediction_datasets.py]
    B[data/NQ1_daily_hod_lod_unadjusted.json<br/>(Unadjusted Price Extremes)] --> C

    C -->|Output 1| D[data/NQ1_asia_predictions.json<br/>map: Prev NY1+NY2 -> Asia]
    C -->|Output 2| E[data/NQ1_london_predictions.json<br/>map: Prev NY2+Asia -> London]

    D --> F[FastAPI Service]
    E --> F
    F --> G[Web UI Prediction Panel]
```

## 4. Key Components

- **`scripts/profiler/generate_prediction_datasets.py`**: The offline ETL script.
  - _Role_: Calculates the historical probabilities and generates the static JSON datasets.
  - _Logic_: Iterates through history, finding day `D-1` and day `D`, creating "Context Keys" (e.g., `NY1:LT|NY2:SF`) and tallying outcomes.
- **`NQ1_asia_predictions.json`**: The Lookup Database.
  - _Structure_: `{ "CONTEXT_KEY": { "outcomes": { "Long True": 0.45, ... }, "samples": 150 } }`

## 5. Technology & Constraints

- **Data Integrity**: Price percentages MUST use **Unadjusted Data** to avoid contract roll gaps distorting the "Distance from Open" metric.
- **JSON Size**: The output JSONs are static lookup maps, expected to be small (< 1MB) and loadable into memory by FastAPI.
