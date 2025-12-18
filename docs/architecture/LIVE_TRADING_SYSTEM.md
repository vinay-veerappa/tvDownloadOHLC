# Live Trading System: Architecture & Design

This document outlines the current implementation, requirements, and future roadmap for the Live Trading System integrated with the Schwab Trader API.

## 1. System Overview
The system provides a real-time bridge between the Schwab Streaming API and a local web interface, with persistent storage for session bars.

### Current Components:
- **`stream_chart.py`**: The "Engine". Handles WebSocket authentication, Level 1 price streaming, and 1-minute OHLC bar calculation.
- **Hot Buffer (`live_chart.json`)**: A high-frequency JSON file used for rapid polling by the web frontend.
- **Persistent Storage (`live_storage.parquet`)**: A session-based Parquet file where completed 1-minute bars are archived for future backtesting and analysis.
- **Frontend (`/tools/live-chart`)**: A React/Next.js interface providing real-time visualization via Lightweight Charts.

## 2. Technical Requirements
- **Authentication**: Requires `secrets.json` (App Key/Secret) and `token.json` (OAuth2 Access/Refresh tokens).
- **API Rate Limits**: 
    - **Streaming**: Schwab allows persistent connections for Level 1 and Chart data.
    - **Polling**: Frontend is limited to **2000ms (30 req/min)** to stay well under the 100 req/min limit.
- **Dependencies**: 
    - Python: `schwab-py`, `pandas`, `websockets`.
    - Frontend: `lightweight-charts`, `lucide-react`, `radix-ui`.

## 3. Current Design
### Data Flow:
1. **WebSocket Connect**: StreamClient initiates a connection to Schwab.
2. **Subscriptions**: Subscribes to `CHART_FUTURES` (1-min bars) and `LEVEL_ONE_FUTURES` (Last Price).
3. **Price Oscillation**: Level 1 ticks update the `live_price` field in `live_chart.json` instantly.
4. **Bar Completion**: When a new minute timestamp arrives, the previous bar is flushed to `live_storage.parquet`.
5. **Frontend Sync**: The web UI polls the server action every 2 seconds to refresh the chart series and price label.

## 4. Safety & Security
- **Credential Protection**: `secrets.json` and `token.json` are globally ignored via `.gitignore`.
- **Backup**: Triple-redundant backups are performed via `scripts/utils/backup_credentials.py`.
- **Fault Tolerance**: The frontend shows a "Data Stream Offline" state instead of hanging if the script stops.

## 5. Future Scope & Roadmap
### Phase 1: Real-time Signal Engine
- Integrate the **9:30 NQ Breakout** logic into the stream handler.
- Trigger desktop/mobile notifications when a breakout occurs live.

### Phase 2: System Consolidation
- Build a unified "Master Parquet" merge utility to combine `live_storage.parquet` with historical `NQ1_1m.parquet` daily.
- Implement an equity curve visualizer for the live session.

### Phase 3: Automated Execution
- Add order submission (Buy/Sell) capabilities via the Schwab Trader API.
- Implement a real-time Stop Loss / Take Profit manager (Trailing Stops).

### Phase 4: Unified Charting Interface (Planned)
The goal is to create a single, high-performance charting application that consolidates all existing tools.

#### 🎯 Objectives:
1. **Dynamic Context Switching**: Dropdown or command-palette to switch tickers (/NQ, /ES, etc.) and timeframes (1m, 5m, 15m) without page reloads.
2. **Indicator Library**: A plugin architecture to toggle existing indicators (Standard Deviations, ICT FVGs, Price Models) over live data.
3. **Data Fusion**: Seamlessly blending historical Parquet data (multiple years) with the live "hot buffer" for a continuous scrolling experience.

#### 🛠️ Technical Hurdles:
- **State Management**: Handling large datasets (>100k points) across timeframe switches without memory leaks.
- **API Multiplexing**: If switching tickers, the Python streamer must dynamically (un)subscribe to avoid Schwab rate limits and bandwidth waste.
- **Worker Threads**: Offloading indicator calculations (e.g., SD bands) to Web Workers to keep the UI at 60fps.
- **Syncing Tools**: Ensuring drawings and annotations persist across ticker/timeframe switches.

---
*Created: December 2025*
