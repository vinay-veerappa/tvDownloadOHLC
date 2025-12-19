# Expected Move (EM) Methodology

Expected Move (EM) represents the market's anticipated range for an underlying asset by a specific expiration date, typically derived from option pricing.

## Calculation Methods

The system uses three primary methods to calculate Expected Moves:

### 1. ATM Straddle Method
The most direct measure of the market's expected range for a specific expiry.
- **Formula**: `EM = Straddle Price * 0.85`
- **Source**: Directly from the At-The-Money (ATM) straddle price of the closest expiration.
- **Accuracy**: Highly accurate for short-term expiries (0-7 DTE).

### 2. 365-Day IV Method (VIX-Style)
Calculates the expected daily or periodic move based on annual implied volatility.
- **Formula**: `EM = Price * IV * sqrt(T/365)`
- **IV Source**: Uses the `iv365` (VIX-style) 30-day standardized IV.
- **Usage**: Used for multi-day OR multi-week projections when straddle data is unavailable.

### 3. 252-Day IV Method (Trading Day Style)
Calculates the expected move based on the number of trading days in a year.
- **Formula**: `EM = Price * IV * sqrt(T/252)`
- **Usage**: Alternative to the 365-day method, often preferred by traders focusing on market-open sessions.

### 4. Full Straddle Method (1.0x)
Uses the full ATM straddle price without the 0.85 haircut.
- **Formula**: `EM = Straddle Price * 1.0`
- **Usage**: Conservative boundary for high-volatility events.

### 5. Open-Based EM
Calculates the expected move using the Daily Open price as the anchor instead of the Previous Close.
- **Formula**: `EM_Open = Open * (EM_Percentage)`
- **Usage**: Intraday recalibration of risk after the market open.

## Current Data Coverage (as of Dec 2025)

| Ticker | Price Range | EM Coverage | Status |
|--------|-------------|-------------|--------|
| **SPX** | 1939 - 2025 | Minimal | Needs proxy from SPY or direct 0DTE/1DTE calculation. |
| **SPY** | 1993 - 2025 | 2019 - 2025 | High-quality Straddle and IV coverage back to 2019. |
| **QQO** | 1999 - 2025 | Minimal | Needs proxy or dedicated source. |
| **AAPL** | 1980 - 2025 | 2019 - 2025 | Excellent historical EM coverage from Feb 2019. |
| **DIA** | 1998 - 2025 | 2019 - 2025 | Strong coverage back to 2019. |
| **AMD** | 1980 - 2025 | 2019 - 2025 | Strong coverage back to 2019. |

## Data Sources

The historical Expected Move data is derived from the following source files:

| File | Type | Description |
|------|------|-------------|
| [option_chain.csv](file:///c:/Users/vinay/tvDownloadOHLC/data/options/options/doltdump/option_chain.csv) | Options Chain | Full historical option chain (8.8 GB). Contains bid/ask for straddle calculation. |
| [volatility_history.csv](file:///c:/Users/vinay/tvDownloadOHLC/data/options/options/doltdump/volatility_history.csv) | IV History | Standardized Implied Volatility (IV) for various timeframes (30d, 60d, etc.). |

### Source File Structures

**`volatility_history.csv`**:
- `date`, `act_symbol`, `iv_30`, `iv_60`, `iv_90`, etc.

**`option_chain.csv`**:
- `date`, `act_symbol`, `expiration`, `strike`, `call_put`, `bid`, `ask`, `vol`, `delta`, `gamma`, `theta`, `vega`, `rho`

## Data Pipeline

1. **Option Chain Ingestion**: Scripts stream `option_chain.csv` from `doltdump`.
2. **Unified History Building**: `scripts/data_processing/build_unified_em_history.py` merges prices, IV, and straddle data into the `ExpectedMoveHistory` table.
3. **Live Updates**: Live streaming APIs (Schwab/TradingView) update the `ExpectedMove` table for active expiries.
