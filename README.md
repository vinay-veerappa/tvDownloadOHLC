# tvDownloadOHLC - Trading Platform

**Version 0.4.0** - Timeframe Standardization & Performance Refactor
 
 ## 📂 Project Structure
 
 *   **`web/`**: The main Next.js Trading Platform (Chart, Journal, Backtest).
     *   Stack: Next.js 16, TypeScript, Shadcn/UI, Prisma, Lightweight Charts v5.
     *   Run: `cd web && npm run dev`
 *   **`data/`**: Historical OHLC data (Parquet/CSV).
 *   **`scripts/`**: Python scripts for data downloading and processing.
 *   **`docs/`**: Technical documentation and guides.
 *   **`legacy_chart_ui/`**: **[DEPRECATED]** The original Vanilla JS Chart Viewer. Kept for reference.
 
 ## ✨ Features (v0.4.0)
 
 ### Architecture Improvements
 - **Resolution Standardization**: Unified timeframe handling (minutes-based, e.g., "60" vs "1h") using `resolution.ts`.
 - **Hook Splitting**: `useChartData` decomposed into:
     - `useDataLoading`: Optimized data fetching, pagination, and memory management.
     - `useReplay`: Focused replay state logic.
     - `useResampling`: Client-side data aggregation (e.g., 3m from 1m).
 - **Performance**: Fixed NQ1 (high-frequency) data crashes by optimizing initial load sizes.
 
 ### Trading Engine
 - LONG/SHORT position management with real-time P&L
 - Stop Loss / Take Profit bracket orders
 - Trade reversal support (LONG → SHORT or vice versa)
 - Draggable SL/TP price lines on chart
 - Session-based P&L tracking
 
 ### Advanced Journaling
- MAE (Max Adverse Excursion) / MFE (Max Favorable Excursion) tracking
- Trade duration in seconds
- Risk-per-trade configurable
- Trade history with advanced filtering

### Chart Features
- Multiple chart styles: Candles, Bars, Line, Area, Heiken-Ashi
- Drawing tools: Trend Lines, Rays, Fibonacci, Text annotations
- Indicators: SMA, EMA, Session Highlighting, Watermark
- Replay Mode with step-forward/back and timeframe sync
- Magnet mode for precision drawing (weak/strong)
- Light/Dark theme support

### Data Pipeline
- Parquet-based OHLC data storage
- Multi-ticker, multi-timeframe support
- TV Selenium downloader for historical data

## 🚀 Getting Started

1.  Navigate to the web app:
    ```bash
    cd web
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Initialize the database:
    ```bash
    npx prisma db push
    ```
4.  Start the development server:
    ```bash
    npm run dev
    ```
5.  Open [http://localhost:3000](http://localhost:3000)

## 📖 Documentation

See [`docs/README.md`](docs/README.md) for the full documentation index including:
- **[Developer Standards - Indicators & Tools](docs/architecture/INDICATOR_DEVELOPMENT_STANDARDS.md)** 🆕 (Performance & Interaction Patterns)
- **[Lightweight Charts Performance Guide](docs/ui/Lightweight_Charts_Performance_Guide.md)** (General optimization tips)
- [User Guide](docs/setup/USER_GUIDE.md)
- Plugin System
- Indicators Guide
- [Data Processing Instructions](docs/data/DATA_PROCESSING_INSTRUCTIONS.md)
- **[Data Inventory](DATA_INVENTORY.md)** (Available Tickers & Timeframes)

## 🐍 Data Scripts (Python)

### Update Data (New)
To automatically import and sync new TradingView exports:
1. Place your `.csv` files in `data/imports/`
2. Run:
```bash
python scripts/update_data.py
```
This script handles remaining processing, format conversion, and updates documentation automatically.

### Historical Download (Selenium)
**New!** Automated download of full contract history using TradingView Replay mode.

**Prerequisites:**
1.  Open Chrome with remote debugging enabled:
    ```bash
    chrome.exe --remote-debugging-port=9222 --user-data-dir="c:\selenium\profile"
    ```
2.  Log in to TradingView in this Chrome instance.

**Usage:**
Run the replay downloader with a list of contracts:
```bash
python selenium_downloader/download_contracts_replay.py --contracts "ESZ2023,ESH2024"
```

**Features:**
- Automatic **Replay Mode** navigation.
- **Rollover Awareness**: Automatically stops downloading when it reaches the previous contract's rollover date (uses `es_rollover_calendar.csv` or `cl_rollover_calendar.csv`).
- **Resilient**: Handles "Continue Replay" dialogs and connection interruptions.
- Saves data chunks to `data/downloads_contracts_replay/`.

### Legacy Processing
To run manual data processing scripts:
```bash
python scripts/process_data.py
```

## 📜 License

MIT License
