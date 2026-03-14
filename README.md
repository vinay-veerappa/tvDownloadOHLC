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
- Automated options dealer-level pipeline (SPX/NDX → ES/NQ) with advanced GEX structure levels

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

### Quick Start Scripts (Windows)

For convenience, use these batch files:

| Script | Purpose |
|:---|:---|
| `start_web.bat` | Start Next.js frontend |
| `start_api.bat` | Start FastAPI backend |
| `start_llm.bat` | Start Ollama LLM server |

## 📖 Documentation

See [`docs/README.md`](docs/README.md) for the full documentation index including:
- **[Developer Standards - Indicators & Tools](docs/architecture/INDICATOR_DEVELOPMENT_STANDARDS.md)** 🆕 (Performance & Interaction Patterns)
- **[Lightweight Charts Performance Guide](docs/ui/Lightweight_Charts_Performance_Guide.md)** (General optimization tips)
- [User Guide](docs/setup/USER_GUIDE.md)
- Plugin System
- Indicators Guide
- [Data Processing Instructions](docs/data/pipeline/INSTRUCTIONS.md)
- **[Data Integrity & Streaming Guide](docs/data/pipeline/INTEGRITY.md)** 🆕 (Corruption Prevention)
- **[Data Inventory](DATA_INVENTORY.md)** (Available Tickers & Timeframes)

## 🐍 Data Scripts (Python)

### Dealer Levels (Options GEX → ES/NQ)
Generates robust dealer-positioning levels from Schwab chains with ETF fallback logic, futures translation, richer narrative plans, and copy-ready outputs for both TradingView and Discord.

```powershell
# Run once
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels

# Run scheduler (08:30 ET and 11:00 ET weekdays)
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --schedule

# Enable Discord for this run (default is disabled)
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --discord
```

Outputs:
- `data/daily_levels.txt` (copy-ready strings + interpretation/pre-open plan + detailed summary)
- `data/daily_levels.json` (Pine-ready level records for ES/NQ)

Discord behavior:
- Posts to the `option-levels` webhook target configured in `discord_webhooks.json`
- Sends one top copy block formatted for direct paste into `scripts/indicators/options/DealerLevels.pine`
- Sends per-ticker embeds for interpretation and key levels

See full docs: `docs/indicators/Options/README.md`

### Update Data (CSV Import)
To automatically import and sync new TradingView exports:
1. Place your `.csv` files in `data/imports/`
2. Run:
```bash
python scripts/market_data/update_data.py
```
This script handles remaining processing, format conversion, and updates documentation automatically.

### Update Data (Schwab API)
**New!** Automatically fetch recent data and bridge gaps using the Schwab API.
```bash
# Update everything
python scripts/market_data/update_via_schwab.py --all

# Update specific ticker and timeframe
python scripts/market_data/update_via_schwab.py NQ --tf 1m
```
This script updates standard Parquet files and regenerates Web JSON chunks for the chart.

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
