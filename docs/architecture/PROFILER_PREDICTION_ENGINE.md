# Profiler Prediction Engine Architecture

## 1. Overview

The Profiler Prediction Engine extends the session profiling system by introducing predictive probabilities for future trading sessions based on the specific "Signature" of previous sessions. It attempts to answer: _"Given NY1 broke High and NY2 broke Low yesterday, what does Asia usually do today?"_

## 2. Key Responsibilities

- **Data aggregation**: Merging Session Status (Trend) with Unadjusted Price Data (Volatility).
- **Context Mapping**: Linking `Previous Day` sessions to `Current Day` targets (e.g., Prev NY -> Current Asia).
  - _Note_: For sessions starting before a target level is formed (e.g. Asia analyzing NY1 Mid), the engine explicitly uses the **Previous Day's** version of that level to ensure valid hit probabilities.
- **Probability Generation**: Calculating frequency distributions for Session Status (Long True, Short False, etc.) and Price Extremes (HOD/LOD %).
- **Serving**: Providing these lookup tables to the Web UI for real-time analysis.

## 3. Data Flow

```mermaid
graph TD
    A[data/NQ1_profiler.json<br/>(Session Status)] --> C[generate_profiler_lookup.py]
    B[data/NQ1_daily_hod_lod_unadjusted.json<br/>(Unadjusted Prices)] --> C
    LT[data/NQ1_level_touches_columnar.json<br/>(Columnar Level Hits)] --> C

    C -->|Output| D[data/derived/NQ1_profiler_lookup.json<br/>4 tables: Asia, London, NY1, NY2]

    D --> F[FastAPI Service]
    D --> VAL[scripts/testing/<br/>Validation Framework]
    F --> G[Web UI Prediction Panel]
```

## 4. Key Components

- **`scripts/libs_py/profiler/generate_profiler_lookup.py`**: The offline ETL script.
  - _Role_: Calculates historical probabilities and generates the static JSON lookup tables.
  - _Logic_: Iterates through history in sorted date order, finding day `D-1` and day `D`, creating "Context Keys" (e.g., `LT|F|SF|T`) and tallying outcomes.
  - _Inputs_: `NQ1_profiler.json` (session status), `NQ1_daily_hod_lod_unadjusted.json` (unadjusted prices for distribution stats), `NQ1_level_touches_columnar.json` (per-outcome level hit rates).
  - _Outputs_: `data/derived/NQ1_profiler_lookup.json` containing 4 session tables.
- **`NQ1_profiler_lookup.json`**: The Lookup Database.
  - _Structure_: `{ "tables": { "NY1": { "LF|LF": { "samples": 154, "probabilities": {...}, "price_stats": {...}, ... } } }, "level_hits": {...}, "base_rates": {...} }`

## 5. Technology & Constraints

- **Data Integrity**: Price percentages MUST use **Unadjusted Data** to avoid contract roll gaps distorting the "Distance from Open" metric.
- **JSON Size**: The output JSONs are static lookup maps, expected to be small (< 1MB) and loadable into memory by FastAPI.
- **Tie-Breaking**: Mode bins are sorted numerically ascending on ties (deterministic across Python/JS).
- **Date Alignment**: Adjusted and unadjusted data files have different date ranges; the `useDailyHodLod` hook merges by date, not index.
- **Count Integrity**: Dates where the target session is entirely missing (no session record) are excluded from counts. "None" status dates are included (matching WebUI distribution behavior).

## 6. Lookup Table Generator

**Script:** `scripts/libs_py/profiler/generate_profiler_lookup.py`

Generates 4 compact JSON lookup tables (one per session: Asia, London, NY1, NY2) that map context signatures directly to prediction data.

### Context Signature Format

- Asia: `"prev_ny1_status|prev_ny1_broken|prev_ny2_status|prev_ny2_broken"`
- London: `"asia_status|asia_broken|prev_ny2_status|prev_ny2_broken"`
- NY1: `"asia_status|asia_broken|london_status|london_broken"`
- NY2: `"asia_status|asia_broken|london_status|london_broken|ny1_status|ny1_broken"`

Status-only keys (without broken bits) are also generated for aggregation.

### Each Entry Contains

- `samples`: Total matching days (including "None" status)
- `probabilities`: `{outcome: probability}` for LT/LF/ST/SF
- `price_stats`: Per-outcome `{h_mode, h_med, l_mode, l_med, h_avg, l_avg, h_span, l_span, sample_count}`
- `hod_lod_times`: Per-outcome `{hod_mode, lod_mode}` (15-min bucket ranges)
- `broken_rates`: Per-outcome broken rate
- `per_outcome_level_hits`: Per-outcome level hit rates for all 20 columnar level keys (computed from `NQ1_level_touches_columnar.json`)

## 7. Validation

The lookup tables are validated by `scripts/testing/` (see [PROFILER_DATA_DESIGN.md §8](./PROFILER_DATA_DESIGN.md#8-validation-framework-v130)).

**Current status (NQ1 NY1):** 76/76 filter combinations pass, 128/128 fields match on the LF|LF baseline.
