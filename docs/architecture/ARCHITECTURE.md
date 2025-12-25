# System Architecture

**Version:** 0.4.0
**Last Updated:** December 09, 2025

## 1. High-Level Overview

**tvDownloadOHLC** is a hybrid trading platform combining a high-performance Next.js frontend with a Python/FastAPI backend and a Selenium-based data pipeline.

### Core Components
1.  **Web Client (`web/`)**: Next.js 16 application serving the UI, Charting Engine (Lightweight Charts), and Trading Interface.
2.  **API Server (`api/`)**: Python FastAPI server handling data serving, session analysis, and file operations.
3.  **Data Pipeline (`scripts/`)**: Automations for downloading data from TradingView (Selenium) and processing it into Parquet/CSV formats.
4.  **Database**: SQLite (managed via Prisma on the frontend for user data like journals, and direct file access for OHLC data).

---

## 2. Frontend Architecture (`web/`)

**Tech Stack:**
- **Framework**: Next.js 16.0.7 (App Router), React 19.
- **Language**: TypeScript 5.
- **UI**: TailwindCSS 4, Shadcn/UI (Radix Primitives), Lucide React.
- **Charts**: Lightweight Charts v5.0.9.
- **State**: React Context, Sonner (Toast).
- **Database ORM**: Prisma 5.22.0.

### Key Directories
-   `app/`: Next.js App Router pages (`/chart`, `/journal`, `/backtest`).
-   `components/`: Reusable UI components (Shadcn).
-   `components/chart/`: Chart-specific UI (Legend, Toolbars).
-   `lib/charts/`: Core charting logic.
    -   `StandardChart.tsx`: The main wrapper component integrating the library.
    -   `indicators/`: Custom indicator implementations (e.g., `HourlyProfiler`).
    -   `plugins/`: Custom drawing tools and interactions.

### State Management
-   **React Context**: `TradingContext` manages global state (Positions, Account Balance, Active Ticker).
-   **Hooks**: Specialized hooks for data and logic:
    -   `useDataLoading`: Fetches/paginates OHLC data.
    -   `useResampling`: Aggregates 1m data into higher timeframes (5m, 15m, 1h) client-side.
    -   `useReplay`: Manages bar-by-bar playback state.

### Charting Engine
We use **Lightweight Charts v5** extended with custom "Primitives" and "Pane Views" for advanced features:
-   **Hourly Profiler**: A custom renderer implementing `ISeriesPrimitive` to draw complex box/line profiles directly on the canvas.
-   **Session Highlighting**: Custom canvas rendering for background session colors.

### 2.5 Data Timezone Contract (Hybrid)
To support both legacy logic and seamless timezone switching:
*   **Charts**: Expect Naive UTC inputs, which are displayed in `America/New_York` by default but can be offset.
*   **Derived JSONs**: Provide a **Hybrid Output**:
    *   `_time` fields (e.g. `hod_time`): **NY-based Strings** ("09:30") for legacy compatibility.
    *   `_ts` fields (e.g. `hod_ts`): **Unix Timestamps** (UTC) for frontend flexibility.
*   **Indicators**: Should prefer `_ts` fields when drawing markers to ensure they align with the chart's time scale regardless of display settings.

---

## 3. Backend Architecture (`api/`)

**Tech Stack:**
- **Server**: Python 3.11+, FastAPI, Uvicorn.
- **Data Processing**: Pandas, NumPy, PyArrow (Parquet).
- **WebScraping**: Selenium, WebDriver Manager.

### Core Responsibilities
-   **Data Serving**: Reads from `data/parquet/` and serves OHLC chunks to the frontend.
-   **Session Analysis**: Calculates session stats (RTH/Globex High/Low) on demand.
-   **File Management**: Lists available tickers and timeframes.

### API Endpoints
-   `GET /api/data/{ticker}`: Returns OHLC data (JSON).
-   `GET /api/sessions/{ticker}`: Returns pre-calculated session/hourly profile data.
-   `GET /api/files`: Lists available data files.

---

## 4. Data Pipeline (`scripts/`)

### Flow
1.  **Download**: `selenium_downloader/` launches a headless Chrome instance to scrape data from TradingView.
2.  **Processing**: `process_data.py` cleans CSVs, handles timezones, and converts to optimized Parquet files.
3.  **Storage**:
    -   `data/imports`: Raw CSV landing zone.
    -   `data/parquet`: Optimized storage for the API.

---

## 5. Key Workflows

### Data Loading (Client-Side)
1.  User selects Ticker/Timeframe.
2.  `useDataLoading` hook calls `GET /api/data/{ticker}`.
3.  If Timeframe > 1m, `useResampling` aggregates the 1m base data on the fly (for performance and consistency).
4.  Data is fed to `StandardChart`.

### Trading Engine (Simulation)
1.  User clicks "Buy".
2.  `TradingContext` creates a `Position` object.
3.  Every price update (tick), the context checks current price vs Entry/SL/TP.
4.  P&L is calculated in real-time.
5.  On Close, the trade is moved to `TradeHistory` and saved to Prisma/SQLite.

---

## 6. Directory Structure
```
/
├── api/                 # FastAPI Backend
├── data/                # Data Storage (Parquet/CSV)
├── docs/                # Documentation
├── scripts/             # Python Data Scripts
├── web/                 # Next.js Frontend
│   ├── app/             # Pages
│   ├── components/      # UI Components
│   ├── lib/             # Logic & Utils
│   │   ├── charts/      # Formatting/Indicators
│   │   ├── db/          # Prisma Client
│   │   └── hooks/       # React Hooks
│   └── prisma/          # Database Schema
└── ...
```
