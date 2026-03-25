# Parallelization & Optimization Strategy

This document details the techniques used to optimize the ICT research pipeline (`run_research.py`), transforming it from a slow, sequential process into a high-performance parallelized system.

## 1. The 3-Phase Architecture

To balance speed with data dependencies (historical context), the pipeline is split into three distinct phases:

### Phase 1: Sequential Extraction (Fast O(N))
*   **Purpose**: Extract raw session stats (Open/High/Low/Close) for every day while maintaining historical context (e.g., today's gap depends on yesterday's close).
*   **Technique**: Sequential processing is required here because Day T depends on Day T-1.
*   **Optimization**: 
    *   **Vectorized Lookup**: Replaced the original `df[df['date'] == d]` filter (which was O(N²) effectively) with a `df.groupby('trading_date')` hash map (O(1) lookup inside the loop).
    *   **Result**: Reduced extraction time from minutes to seconds.

### Phase 2: Parallel Analysis (Heavy O(N/Cores))
*   **Purpose**: Perform computationally expensive tasks: classifying valid patterns, detecting PD arrays, and measuring tick-by-tick level hits.
*   **Technique**: `multiprocessing.Pool`
*   **Implementation**:
    *   The expensive `process_day_worker` function is mapped across all available CPU cores.
    *   **Data Locality**: Each worker receives a standalone packet of data `(date, day_1m_df, day_stats)`, ensuring no shared strict locks are needed.
    *   **Spawnsafe**: The code is wrapped in `if __name__ == "__main__":` to support Windows' spawn process model.

### Phase 3: Cross-Day Dependencies (Sequential)
*   **Purpose**: Measure outcomes that require future data (e.g., Asia session of "Tomorrow" testing "Today's" PM levels).
*   **Technique**: A final sequential pass over the *results* of Phase 2.
*   **Why**: Parallel workers process days in isolation. Worker T cannot see Worker T+1's data. This phase bridges that gap by iterating largely pre-computed results, which is very fast.

## 2. Key Optimization Techniques

| Technique | Implementation | Benefit |
| :--- | :--- | :--- |
| **Groupby caching** | `day_groups = df_1m.groupby('trading_date')` | Eliminates 5000+ full-table scans. O(N²) → O(N). |
| **Multiprocessing** | `Pool().map(worker, tasks)` | Utilizes 100% of CPU cores for heavy math. |
| **Data Slicing** | `day_1m` slicing before worker dispatch | Reduces memory overhead passed to subprocesses. |
| **Naive Date Filter** | `unique_dates[pd.notna(unique_dates)]` | Prevents `NaT` errors during sorting. |

## 3. Worker Function Design

The `process_day_worker` function is designed to be purely functional (stateless):
1.  **Input**: Date, Daily DataFrame, Daily Stats Object.
2.  **Process**: 
    *   Classifies Overnight Patterns.
    *   Detects PD Arrays.
    *   Measures NY Session Outcomes.
    *   Classifies PM Session Patterns.
3.  **Output**: A dictionary of results + The updated Stats object (for Phase 3).

## 4. How to Run

No special flags are needed. The script auto-detects CPU count.

```bash
# Standard Run (Parallel)
python ict_research/run_research.py --ticker NQ

# Debug Mode (Sequential)
python ict_research/run_research.py --ticker NQ --no-parallel
```
