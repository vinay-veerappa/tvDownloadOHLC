# Trading Journal - Technical Architecture

Complete technical documentation for understanding, maintaining, and extending the Trading Journal system.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Directory Structure](#directory-structure)
4. [Database Schema](#database-schema)
5. [Server Actions](#server-actions)
6. [API Routes](#api-routes)
7. [Components](#components)
8. [Design Decisions](#design-decisions)
9. [Data Flows](#data-flows)
10. [Environment Configuration](#environment-configuration)
11. [Quick Reference](#quick-reference)

---

## System Overview

The Trading Journal is a Next.js 14+ application using the App Router pattern. It provides trade tracking, analytics, AI analysis, and integration with the chart application.

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ TradeList│ │Analytics│ │ AIChat  │ │ Dialogs │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
│       │           │           │           │                  │
│       ▼           ▼           ▼           ▼                  │
│  ┌──────────────────────────────────────────────┐           │
│  │           Server Actions (Next.js)            │           │
│  └──────────────────────────────────────────────┘           │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────┐           │
│  │              Prisma ORM                       │           │
│  └──────────────────────────────────────────────┘           │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────┐           │
│  │           SQLite Database                     │           │
│  └──────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Framework** | Next.js 14+ (App Router) | Full-stack React framework |
| **Language** | TypeScript | Type safety |
| **Database** | SQLite | Local file-based database |
| **ORM** | Prisma | Database access and migrations |
| **UI** | shadcn/ui + Radix | Component library |
| **Styling** | Tailwind CSS | Utility-first CSS |
| **Charts** | Recharts | Analytics visualizations |
| **AI** | Gemini API / Ollama | Trade analysis |
| **Icons** | Lucide React | Icon library |

---

## Directory Structure

```
web/
├── app/                          # Next.js App Router
│   ├── api/
│   │   └── ai/
│   │       └── chat/
│   │           └── route.ts      # AI chat endpoint
│   ├── journal/
│   │   ├── page.tsx              # Main journal page
│   │   ├── analytics/
│   │   │   └── page.tsx          # Analytics dashboard
│   │   ├── ai/
│   │   │   └── page.tsx          # AI assistant page
│   │   └── trade/
│   │       └── [id]/
│   │           └── page.tsx      # Trade detail page
│   └── layout.tsx
│
├── actions/                      # Server Actions
│   ├── trade-actions.ts          # CRUD for trades
│   ├── analytics-actions.ts      # Analytics queries
│   ├── market-context-actions.ts # VIX, session, events
│   ├── csv-actions.ts            # Import/export
│   └── backtest-exporter.ts      # Backtest import
│
├── components/
│   └── journal/                  # Journal-specific components
│       ├── trade-list.tsx        # Trade table with filters
│       ├── add-trade-dialog.tsx  # Add trade modal
│       ├── trade-review.tsx      # Post-trade questionnaire
│       ├── goal-tracker.tsx      # P&L goals
│       ├── playbook.tsx          # Trading setups
│       ├── ai-chat.tsx           # AI chat component
│       └── import-export-dialog.tsx
│
├── prisma/
│   ├── schema.prisma             # Database schema
│   ├── seed.ts                   # Default data seeding
│   └── seed-economic-events.ts   # Economic calendar import
│
└── lib/
    └── prisma.ts                 # Prisma client singleton
```

---

## Database Schema

### Core Models

#### Trade
```prisma
model Trade {
  id            String    @id @default(cuid())
  ticker        String                     # Symbol (NQ1, ES1, etc.)
  entryDate     DateTime                   # Entry timestamp
  exitDate      DateTime?                  # Exit timestamp (null if open)
  entryPrice    Float                      # Entry price
  exitPrice     Float?                     # Exit price
  quantity      Float                      # Position size
  direction     String                     # LONG | SHORT
  status        String                     # OPEN | CLOSED
  
  # Order Details
  orderType     String?                    # MARKET | LIMIT | STOP
  limitPrice    Float?
  stopPrice     Float?
  
  # Bracket Orders
  stopLoss      Float?
  takeProfit    Float?
  
  # P&L and Metrics
  pnl           Float?                     # Realized P&L
  fees          Float?
  risk          Float?
  mae           Float?                     # Max Adverse Excursion
  mfe           Float?                     # Max Favorable Excursion
  duration      Int?                       # Seconds
  
  # Metadata
  notes         String?
  chartSnapshot String?
  metadata      String?                    # JSON blob
  
  # Relations
  accountId     String?
  strategyId    String?
  account       Account?  @relation(...)
  strategy      Strategy? @relation(...)
  tags          Tag[]
  events        TradeEvent[]
  marketCondition MarketCondition?
}
```

#### MarketCondition
```prisma
model MarketCondition {
  id        String  @id @default(cuid())
  tradeId   String  @unique
  trade     Trade   @relation(...)
  vix       Float?                        # VIX value at trade time
  vvix      Float?                        # VVIX value
  atr       Float?                        # ATR value
  session   String?                       # US_REGULAR, ASIAN, etc.
  trend     String?                       # TRENDING_UP, RANGING, etc.
  volume    String?                       # HIGH, AVERAGE, LOW
}
```

#### EconomicEvent
```prisma
model EconomicEvent {
  id        String   @id @default(cuid())
  datetime  DateTime                      # Event timestamp
  name      String                        # NFP, CPI, FOMC, etc.
  impact    String                        # HIGH | MEDIUM | LOW
  actual    Float?
  forecast  Float?
  previous  Float?
  trades    TradeEvent[]                  # Many-to-many with Trade
}
```

### Support Models

```prisma
model Account {
  id             String  @id @default(cuid())
  name           String  @unique
  initialBalance Float
  currentBalance Float
  currency       String  @default("USD")
  isDefault      Boolean @default(false)
  trades         Trade[]
}

model Strategy {
  id     String  @id @default(cuid())
  name   String  @unique
  color  String  @default("#808080")
  trades Trade[]
}

model Tag {
  id      String  @id @default(cuid())
  name    String  @unique
  groupId String?
  group   TagGroup? @relation(...)
  trades  Trade[]
}
```

---

## Server Actions

### trade-actions.ts

| Function | Purpose | Parameters |
|----------|---------|------------|
| `getTrades()` | Fetch all trades | None |
| `getTrade(id)` | Fetch single trade | Trade ID |
| `createTrade(data)` | Create new trade | CreateTradeParams |
| `updateTrade(id, data)` | Update trade | ID, UpdateTradeParams |
| `deleteTrade(id)` | Delete trade | Trade ID |
| `closeTrade(id, exitPrice)` | Close open trade | ID, Exit price |
| `getStrategies()` | List all strategies | None |

### analytics-actions.ts

| Function | Purpose | Returns |
|----------|---------|---------|
| `getAnalyticsSummary()` | P&L summary stats | Total, win rate, etc. |
| `getEquityCurve()` | Cumulative P&L | Date/value pairs |
| `getStrategyPerformance()` | P&L by strategy | Strategy/P&L pairs |
| `getDayHourHeatmap()` | P&L by day/hour | 2D matrix |

### csv-actions.ts

| Function | Purpose | Parameters |
|----------|---------|------------|
| `exportTradesToCsv(filters)` | Export to CSV | Optional filters |
| `importTradesFromCsv(csv, accountId)` | Import from CSV | CSV content, account |
| `getBacktestResults()` | List backtests | None |
| `importBacktestToJournal(id)` | Import backtest | Backtest ID |

### market-context-actions.ts

| Function | Purpose | Returns |
|----------|---------|---------|
| `detectSession(date)` | Auto-detect session | Session name |
| `createMarketCondition(data)` | Save market context | MarketCondition |
| `getEconomicEvents(start, end)` | Get events in range | Event list |
| `linkTradeToEvent(tradeId, eventId)` | Link trade to event | TradeEvent |

---

## API Routes

### POST /api/ai/chat

AI chat endpoint supporting multiple providers.

**Request:**
```typescript
{
  messages: [{ role: "user" | "assistant", content: string }],
  provider: "gemini" | "ollama",
  model?: string,
  context?: {
    trades?: Trade[],
    summary?: AnalyticsSummary
  }
}
```

**Response:**
```typescript
{
  message: string,
  provider: string,
  model: string
}
```

**Providers:**
- **Gemini**: Uses `gemini-2.0-flash` model via Google API
- **Ollama**: Uses local LLM (default: `llama3.2`)

---

## Components

### trade-list.tsx
Main trade table with:
- **Filters**: Date range, ticker, status, direction
- **Sorting**: By any column
- **Pagination**: 10/25/50 per page
- **Click to navigate**: Opens trade detail

### add-trade-dialog.tsx
Modal form with:
- Required: Symbol, direction, entry date, price, quantity
- Optional: Strategy, stop loss, take profit, notes
- Validation before submit

### ai-chat.tsx
Chat interface with:
- Message history display
- Quick prompt buttons
- Provider selector (Gemini/Ollama)
- Context injection (trades + summary)
- Loading states and error handling

### trade-review.tsx
Post-trade questionnaire:
- Execution rating (1-5)
- Emotional state selection
- Mistake checkboxes
- Free-form reflection fields

### goal-tracker.tsx
P&L target tracking:
- Editable targets
- Progress bars
- Risk alerts
- Success notifications

---

## Design Decisions

### Why Server Actions over API Routes?

Server Actions simplify data fetching in Next.js App Router:
- Direct database access without HTTP overhead
- Automatic request deduplication
- Simpler error handling
- Type-safe end-to-end

### Why SQLite?

- Zero configuration for local development
- Single file, easy backup
- Fast for read-heavy workloads
- Prisma abstracts the differences

### Why Gemini + Ollama?

- **Gemini**: High-quality analysis, cloud-based
- **Ollama**: Privacy-focused, no API costs, offline capable
- Provider toggle gives user control

### Trade Context for AI

The AI receives:
1. Recent trades (last 50)
2. Performance summary (P&L, win rate, etc.)
3. Trading-specific system prompt

This enables contextual responses without sending entire history.

---

## Data Flows

### Trade Creation Flow
```
User clicks "Add Trade"
    ↓
AddTradeDialog opens
    ↓
User fills form + submits
    ↓
createTrade() server action
    ↓
Prisma creates Trade record
    ↓
revalidatePath('/journal')
    ↓
TradeList re-fetches and re-renders
```

### AI Chat Flow
```
User types message
    ↓
sendMessage() in ai-chat.tsx
    ↓
Fetch context (getAnalyticsSummary, getTrades)
    ↓
POST /api/ai/chat with messages + context
    ↓
Route handler formats for provider
    ↓
Gemini/Ollama API call
    ↓
Response parsed and returned
    ↓
Message added to chat history
```

### CSV Import Flow
```
User uploads CSV file
    ↓
File.text() reads content
    ↓
importTradesFromCsv() parses CSV
    ↓
Validate required columns
    ↓
Map rows to Trade objects
    ↓
Chunked createMany (50 per batch)
    ↓
revalidatePath('/journal')
```

---

## Environment Configuration

### Required for AI (Gemini)
```env
GEMINI_API_KEY=your_api_key_here
```

### Optional for AI (Ollama)
```env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

### Database
```env
DATABASE_URL="file:./dev.db"
```

---

## Quick Reference

### Adding a New Feature

1. **Database change**: Update `prisma/schema.prisma`, run `npx prisma migrate dev`
2. **Server action**: Add function to appropriate `actions/*.ts` file
3. **Component**: Create in `components/journal/`
4. **Page**: Add route in `app/journal/`
5. **Navigation**: Update journal page header buttons

### Key Files by Feature

| Feature | Files |
|---------|-------|
| Trade CRUD | `trade-actions.ts`, `trade-list.tsx`, `add-trade-dialog.tsx` |
| Analytics | `analytics-actions.ts`, `app/journal/analytics/page.tsx` |
| AI Chat | `app/api/ai/chat/route.ts`, `ai-chat.tsx` |
| Market Context | `market-context-actions.ts`, `trade/[id]/page.tsx` |
| Import/Export | `csv-actions.ts`, `import-export-dialog.tsx` |
| Trade Review | `trade-review.tsx` |
| Goals | `goal-tracker.tsx` |
| Playbook | `playbook.tsx` |

### Database Commands

```bash
# Generate Prisma client after schema changes
npx prisma generate

# Create and apply migration
npx prisma migrate dev --name description

# Reset database
npx prisma migrate reset

# Seed default data
npx prisma db seed

# Import economic calendar
npx tsx prisma/seed-economic-events.ts
```

### Data Scripts

```bash
# Fetch VIX/VVIX data
python scripts/fetch_vix_data.py --days 30
```
