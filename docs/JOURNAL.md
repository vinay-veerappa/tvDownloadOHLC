# Trading Journal Documentation

## Overview

The Trading Journal is a comprehensive trade tracking and analysis system integrated with the chart application. It provides features for logging trades, reviewing performance, setting goals, and managing trading playbooks.

## Features

### Core Journal Features

| Feature | Description |
|---------|-------------|
| **Trade Logging** | Log trades with entry/exit prices, direction, quantity, strategy |
| **Trade List** | Filterable, sortable list of all trades with pagination |
| **Trade Detail** | Full trade view with all fields, notes, and market context |
| **Analytics Dashboard** | Summary cards, equity curve, strategy comparison |

### Advanced Features

| Feature | Description |
|---------|-------------|
| **Trade Review** | Post-trade questionnaire with execution rating, emotional state, lessons learned |
| **Goal Tracker** | Daily/weekly/monthly P&L targets with progress visualization |
| **Playbook** | Setup library with entry/exit/risk rules |
| **Market Context** | VIX, VVIX, ATR, session detection for each trade |

### Integration Features

| Feature | Description |
|---------|-------------|
| **Chart → Journal** | Log Trade button in chart toolbar opens Add Trade dialog |
| **Journal → Chart** | View on Chart button navigates to chart at trade time |
| **Backtest Import** | Import backtest results as simulated trades |
| **CSV Import/Export** | Import/export trades in CSV format |

## Data Structure

### Trade Fields

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | String | Trading instrument (e.g., NQ1, ES1) |
| `direction` | LONG/SHORT | Trade direction |
| `entryDate` | DateTime | Entry timestamp |
| `exitDate` | DateTime? | Exit timestamp |
| `entryPrice` | Float | Entry price |
| `exitPrice` | Float? | Exit price |
| `quantity` | Float | Position size |
| `status` | OPEN/CLOSED | Trade status |
| `pnl` | Float? | Realized profit/loss |
| `stopLoss` | Float? | Stop loss price |
| `takeProfit` | Float? | Take profit price |
| `strategyId` | String? | Linked strategy |
| `accountId` | String? | Trading account |
| `notes` | Text? | Trade notes |

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
