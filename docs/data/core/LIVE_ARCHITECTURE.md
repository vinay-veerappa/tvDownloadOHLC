# Live Data Architecture

## Overview
The application serves chart data in two distinct modes: **Historical** and **Live**.

### 1. Historical Mode (Default)
*   **Reading Pattern**: On-Demand via API.
*   **Source**: Fused Parquet Files.
    *   Base: `data/{ticker}_1m.parquet` (Deep History, e.g., 2006–2024).
    *   Live Storage: `data/live/live_storage_-{ticker}.parquet` (Recent, e.g., 2025–Present).
*   **Mechanism**:
    1.  Frontend calls `POST /api/indicators/calculate-from-file`.
    2.  Backend `api.services.data_loader.load_parquet` reads both files.
    3.  Pandas concatenates them, de-duplicates, and returns a single DataFrame.
*   **Pros**: Full history, indicator calculations possible.
*   **Cons**: Slower (reading large files), per-request overhead.

### 2. Live Mode (`?mode=live`)
*   **Reading Pattern**: Polling via Server Action with Delta Updates.
*   **Source**: JSON Cache File.
    *   Path: `data/live/live_chart_-{ticker}.json`.
    *   Format: Lightweight JSON optimized for the frontend.
    *   Content: Rolling 500k candles (approx 1 year).
*   **Mechanism**:
    1.  **Writer**: `scripts/market_data/stream_chart.py` writes to this JSON file continuously. It maintains a buffer of 500k candles to prevent data loss.
    2.  **Reader**: Frontend (`useLiveDataLoading.ts`) polls `getLiveChartData` server action every 500ms.
    3.  **Delta Optimization**: The frontend sends a `since` timestamp. The backend returns only candles *newer* than this timestamp.
*   **Pros**: Extremely fast, low bandwidth (<1KB per poll), full history available on first load (60MB).
*   **Cons**: No indicators (raw candles only).

## Data Flow Diagram

```mermaid
graph TD
    subgraph "Data Sources"
        H[Historical Parquet]
        L[Live Storage Parquet]
        J[Live JSON Cache]
    end

    subgraph "Update Process"
        S[stream_chart.py] -->|Writes (Buffer: 500k)| J
        S -->|Appends| L
    end

    subgraph "Serving - Historical"
        API[FastAPI Backend] -->|Reads| H
        API -->|Reads| L
        API -->|Fuses| Unified[DataFrame]
        FE_H[Frontend (Historical)] -->|POST| API
    end

    subgraph "Serving - Live"
        SA[Next.js Server Action] -->|Reads| J
        SA -->|Filters New Candles| Delta[Delta JSON]
        FE_L[Frontend (Live)] -->|Polls (since=t)| SA
        SA -->|Returns| Delta
        FE_L -->|Merges| FE_State[Frontend Store]
    end
```

## Troubleshooting

### Missing Data / Truncated History
*   **Cause**: `stream_chart.py` buffer limit was too small (e.g., 5k candles).
*   **Fix**: Update `stream_chart.py` to allow 500k candles and restart it.
*   **Verify**: Check `data/live/live_chart_-NQ.json` size. 5k rows ~ 1MB. 500k rows ~ 60MB.

### Chart Crashes ("Assertion Failed: unordered")
*   **Cause**: Frontend merged old data + new data out of order.
*   **Fix**: `use-live-data-loading.ts` now enforces sorting and deduplication on every merge.

### High Latency / Network Lag
*   **Cause**: Downloading 60MB JSON every 500ms.
*   **Fix**: Frontend must use `since` parameter to request delta updates.

## Key Files
*   `scripts/market_data/stream_chart.py`: Python streamer & JSON writer.
*   `web/actions/get-live-chart.ts`: Next.js Server Action (Reader + Filter).
*   `web/hooks/chart/use-live-data-loading.ts`: React Hook (Poller + Merger).
