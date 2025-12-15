# Trading Journal

A comprehensive trade tracking and analysis system integrated with the chart application.

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](JOURNAL_USER_GUIDE.md) | How to use the journal, workflows, best practices |
| [Technical Architecture](JOURNAL_TECHNICAL.md) | Schema, actions, components, design decisions |

## Quick Start

1. Navigate to `/journal`
2. Click **"+ Add Trade"** to record a trade
3. View **Analytics** for performance insights
4. Use **AI Assistant** for pattern analysis

## Features

- ✅ **Trade Logging** - Entry/exit, P&L tracking
- ✅ **Analytics Dashboard** - Summary cards, equity curve
- ✅ **AI Assistant** - Gemini + Ollama support
- ✅ **Goal Tracking** - Daily/weekly/monthly targets
- ✅ **Trade Review** - Post-trade questionnaire
- ✅ **Playbook** - Trading setup library
- ✅ **Chart Integration** - Bidirectional navigation
- ✅ **CSV Import/Export** - Data portability
- ✅ **Economic Calendar** - 8,843 events (2000-2025)
- ✅ **Market Context** - VIX, VVIX, session detection

## Environment Setup

```env
# Required for AI (Gemini)
GEMINI_API_KEY=your_api_key

# Optional for AI (Ollama)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

## Data Scripts

```bash
# Fetch VIX/VVIX data
python scripts/fetch_vix_data.py

# Import economic calendar
cd web && npx tsx prisma/seed-economic-events.ts
```

### Economic Calendar

8,843 events from 2000-2025 including:
- NFP, CPI, PPI (High Impact)
- FOMC decisions
- ISM PMI data
- Jobless claims
- Housing data

### VIX/VVIX Data

Daily OHLC data for VIX and VVIX from 2006-present.

## CSV Import Format

Required columns:
- `ticker` - Symbol (e.g., NQ1)
- `direction` - LONG or SHORT
- `entryDate` - ISO date string
- `entryPrice` - Entry price

Optional columns:
- `exitDate`, `exitPrice`, `quantity`, `pnl`, `stopLoss`, `takeProfit`, `notes`, `strategy`

Example:
```csv
ticker,direction,entryDate,entryPrice,exitDate,exitPrice,pnl
NQ1,LONG,2024-01-15T09:35:00,17500,2024-01-15T10:15:00,17550,1000
```

## Scripts

### Fetch VIX/VVIX Data
```powershell
python scripts/fetch_vix_data.py --days 30
```

### Import Economic Calendar
```powershell
cd web
npx tsx prisma/seed-economic-events.ts
```

## API Endpoints

### Trade Actions (`actions/trade-actions.ts`)
- `getTrades(filters)` - Fetch trades with filters
- `getTrade(id)` - Fetch single trade
- `createTrade(data)` - Create new trade
- `updateTrade(id, data)` - Update trade
- `deleteTrade(id)` - Delete trade
- `closeTrade(id, exitPrice)` - Close open trade

### Analytics Actions (`actions/analytics-actions.ts`)
- `getAnalyticsSummary()` - Summary statistics
- `getEquityCurve()` - Cumulative P&L data
- `getStrategyPerformance()` - P&L by strategy

### CSV Actions (`actions/csv-actions.ts`)
- `exportTradesToCsv(filters)` - Export to CSV
- `importTradesFromCsv(content, accountId)` - Import from CSV
- `getBacktestResults()` - List backtest results
- `importBacktestToJournal(id)` - Import backtest trades

## Components

### Journal Components
- `TradeList` - Main trade table with filters
- `AddTradeDialog` - Modal for adding trades
- `TradeReview` - Post-trade questionnaire
- `GoalTracker` - P&L goal tracking
- `Playbook` - Trading setup library
- `ImportExportDialog` - CSV and backtest import

## Navigation

| Route | Description |
|-------|-------------|
| `/journal` | Main trade list |
| `/journal/trade/[id]` | Trade detail page |
| `/journal/analytics` | Analytics dashboard |
