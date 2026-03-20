# Options Tactical Dashboard & Indicators

## Overview
This suite provides real-time visibility into dealer positioning, gamma exposure (GEX), and institutional flow for SPX, NDX, and major ETFs.

## 1. Options Tactical Command (Web Dashboard)
The primary interface for active day trading. Accessible at `/options-live`.

### Core Features
- **Neon Tactical UI**: High-density monitoring with glassmorphism and real-time pulse alerts.
- **Dynamic Charting**: Toggle between Net GEX, Call/Put Walls, Volume Profiles, and OI Profiles.
- **Vertical Price Ladder**: DOM-style vertical mapping of reaction zones aligned with live price.
- **Coach's Briefing**: AI-generated narrative translation of the current market structure.
- **Advanced Telemetry**: Includes Call/Put Centroids, Vanna/Charm nodes, and Pin Concentration.

---

## 2. TradingView Indicators
For users who prefer to trade directly off TradingView charts.

### `scripts/indicators/options/DealerLevels.pine`
Paste one or more formatted lines into a single text box and it auto-selects the line matching the current chart symbol.

**Key Features:**
- Exact ticker matching and family-based routing (SPX/SPY/ES).
- Overnight futures session-aware reset logic.
- Customizable line styles, EM fills, and label overlap management.
- Compact mode for clean high-density charts.

---

## 3. Data Pipeline (`run_options_levels.py`)
The engine that powers both the Dashboard and the Pine indicators.

### Modes of Operation
- **Scheduled**: Runs at key intervals (e.g., 08:30, 11:00 ET).
- **Loop**: Continuous priority scanner (60s tick for Tier 1 tickers).
- **Manual**: Trigger on-demand via the Web UI "Refresh" button.

### Calculation Logic
Calculations are performed in `gex_calculator.py` using Black-Scholes Greeks and proprietary centroid algorithms. Results are normalized to cash-index space even when using ETF or futures sources.

---

## 4. Output Archetypes
- **`daily_levels.json`**: Unified state for the Web Dashboard.
- **`daily_levels.txt`**: Human-readable summary and copy-ready Pine strings.
- **`gex_profiles.json`**: High-resolution strike-level data (Gamma, Volume, OI).
- **`live_trend.json`**: Historical intraday trace for trend analysis.

---

## 5. Setup & Configuration
All settings are managed in `scripts/streaming/options/config.py`. Key constants include:
- `PRIMARY_INDEX_TICKERS`: Tickers monitored by the priority scanner.
- `ETF_FALLBACK`: Mapping for index-to-etf data sourcing.
- `INDEX_TO_FUTURES`: Mapping for basis-translation (e.g., SPX -> ES).
