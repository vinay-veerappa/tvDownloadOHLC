# Options Strategy Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and deploy a complete Options Strategy Paper Trading Engine running 41 parameterized variants across 7 strategies with custom platform services, paper execution, real-time logging, and daily/weekly analytics rollups.

**Architecture:** A modular, stateless Python-based service layer wrapping Schwab option feeds, index tracking, volatility telemetry, and ICT/SMC concepts. Open positions are Mark-to-Market (MTM) on a schedule and closed on rules (profit targets, stops, time constraints). Daily and weekly analytics synthesize equity curves, feature importances, and near-miss logs to the SQLite Prisma schema.

**Tech Stack:** Python, Prisma CLI (with python-client generator), SQLite, Pytest, Pandas, ezoptionsschwab, yfinance.

---

### Task 1: Database Migration (Prisma)

**Files:**
- Modify: `c:/Users/vinay/tvDownloadOHLC/web/prisma/schema.prisma`
- Create: Migrations via Prisma CLI

**Step 1: Write schema.prisma edits**
Open [schema.prisma](file:///c:/Users/vinay/tvDownloadOHLC/web/prisma/schema.prisma) and:
1. Append these fields to the `Trade` model:
   ```prisma
     legs             TradeLeg[]
     snapshots        QuoteSnapshot[]
   ```
2. Append the 5 new models to the bottom of the file:
   ```prisma
   model TradeLeg {
     id          String   @id @default(cuid())
     tradeId     String
     trade       Trade    @relation(fields: [tradeId], references: [id], onDelete: Cascade)

     symbol      String                       // OCC option symbol or stock ticker
     legIndex    Int                          // 0, 1, 2, 3 for ordering within trade
     optionType  String                       // "CALL" | "PUT" | "STOCK"
     side        String                       // "LONG" | "SHORT"
     strike      Float?                       // null for STOCK
     expiry      DateTime?                    // null for STOCK
     quantity    Int                          // contracts or shares

     openPrice   Float
     openBid     Float?
     openAsk     Float?
     openIv      Float?
     openDelta   Float?
     openGamma   Float?
     openTheta   Float?
     openVega    Float?

     closePrice  Float?
     closeBid    Float?
     closeAsk    Float?
     closeIv     Float?
     closeDelta  Float?
     closeGamma  Float?
     closeTheta  Float?
     closeVega   Float?

     legPnl      Float?
     assigned    Boolean  @default(false)
     expiredOtm  Boolean  @default(false)

     createdAt   DateTime @default(now())
     updatedAt   DateTime @updatedAt

     @@index([tradeId])
     @@index([symbol])
   }

   model QuoteSnapshot {
     id              String   @id @default(cuid())
     tradeId         String
     trade           Trade    @relation(fields: [tradeId], references: [id], onDelete: Cascade)

     takenAt         DateTime @default(now())
     underlyingPx    Float
     netValue        Float                    // cost-to-close right now
     unrealizedPnl   Float

     legPrices       String                   // JSON: {symbol: {bid, ask, mid, iv, delta, ...}}

     vix             Float?
     gexRegime       String?
     zeroGamma       Float?

     @@index([tradeId, takenAt])
   }

   model SignalNearMiss {
     id                 String   @id @default(cuid())
     researchStrategyId String                // links to ResearchStrategy.id

     evaluatedAt        DateTime @default(now())
     ticker             String
     underlyingPx       Float

     failingFilter      String                // e.g. "iv_rank_below_threshold"
     filterValue        Float?
     filterThreshold    Float?

     context            String                // JSON of all filter values

     @@index([researchStrategyId, evaluatedAt])
     @@index([failingFilter])
   }

   model Holding {
     id          String   @id @default(cuid())
     ticker      String   @unique
     shares      Int
     costBasis   Float
     acquiredAt  DateTime
     notes       String?
     createdAt   DateTime @default(now())
     updatedAt   DateTime @updatedAt
   }

   model EarningsCalendar {
     id              String   @id @default(cuid())
     ticker          String
     earningsDate    DateTime
     beforeMarket    Boolean                  // BMO = true, AMC = false
     confirmed       Boolean  @default(false)
     source          String   @default("yfinance")
     fetchedAt       DateTime @default(now())

     @@unique([ticker, earningsDate])
     @@index([earningsDate])
   }
   ```

**Step 2: Generate prisma client & apply migrations**
Run the migration CLI command:
`cd c:/Users/vinay/tvDownloadOHLC/web && npx prisma migrate dev --name strategy_engine_v1`

**Step 3: Run code generation**
`npx prisma generate` (this will rebuild the python-client using `prisma-client-py` generator configured at top).

**Step 4: Commit**
`git add web/prisma/schema.prisma web/prisma/migrations/`
`git commit -m "db: add strategy engine migration"`

---

### Task 2: Strategy Engine Setup and Configuration

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/__init__.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/config.yaml`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/__init__.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/__init__.py`

**Step 1: Write config.yaml**
```yaml
# config.yaml
default_initial_balance: 25000.0
account_group_name: "Strategy Engine Silos"

approved_tickers:
  - SPY
  - SPX
  - QQQ
  - IWM
  - NVDA
  - TSLA
  - AAPL
  - GOOGL
  - MSFT
  - AMZN
  - RIVN

holdings:
  GOOGL: { shares: 300, cost_basis: 150.0, acquired_at: "2026-01-15T09:30:00Z" }
  TSLA: { shares: 200, cost_basis: 180.0, acquired_at: "2026-02-10T09:30:00Z" }
  RIVN: { shares: 1000, cost_basis: 10.0, acquired_at: "2026-03-01T09:30:00Z" } # staged

blackout_buffers:
  High: { pre_minutes: 120, post_minutes: 60 }
  Medium: { pre_minutes: 30, post_minutes: 30 }
  Low: { pre_minutes: 0, post_minutes: 0 }

strategies:
  WHEEL:
    tickers: [NVDA, TSLA, AAPL, GOOGL, MSFT, AMZN]
    variants:
      30D_45DTE: { short_delta: 0.30, dte: 45, min_iv_rank: 30 }
      20D_45DTE: { short_delta: 0.20, dte: 45, min_iv_rank: 30 }
      30D_7DTE:  { short_delta: 0.30, dte: 7,  min_iv_rank: 25 }

  ZERO_DTE_PCS:
    tickers: [SPY, SPX]
    variants:
      10D_5W: { short_delta: 0.10, width: 5.0, require_positive_gamma: true, require_ict: false }
      16D_5W: { short_delta: 0.16, width: 5.0, require_positive_gamma: true, require_ict: false }
      10D_5W_NOGEX: { short_delta: 0.10, width: 5.0, require_positive_gamma: false, require_ict: false }
      10D_5W_ICT: { short_delta: 0.10, width: 5.0, require_positive_gamma: true, require_ict: true }

  LONG_DTE_CREDIT:
    tickers: [SPY, NVDA, TSLA, IWM]
    variants:
      16D_45DTE: { short_delta: 0.16, width_pct: 0.02, dte: 45, min_iv_rank: 35 }

  MEAN_REVERSION_EM:
    tickers: [SPY, SPX]
    variants:
      1SD_TOUCH: { entry_window: ["10:30", "14:30"], max_vix: 20, require_positive_gamma: true }

  WALL_BREAK:
    tickers: [SPY, SPX]
    variants:
      BREAKOUT_DEBIT: { entry_window: ["10:00", "15:00"], max_vix: 22, wall_proximity_pct: 0.003 }

  INCOME_CC:
    tickers: [GOOGL, TSLA, RIVN]
    variants:
      TIER: {} # Parameterized dynamically inside the IncomeCcStrategy class tiers

  EARNINGS_STRANGLE:
    tickers: [NVDA, TSLA, AAPL, GOOGL]
    variants:
      30D_5D_BEFORE: { days_before: 5, target_delta: 0.30, max_debit: 5.0, max_iv_percentile: 50 }
```

**Step 2: Commit**
`git add scripts/libs_py/strategy_engine/`
`git commit -m "chore: scaffold engine workspace & configurations"`

---

### Task 3: Seed Script Implementation (`seed_data.py`)

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/seed_data.py`

**Step 1: Write seed_data.py**
Implement the bootstrapping logical flow:
1. Connects asynchronously using `prisma-client-py`.
2. Creates or fetches the `AccountGroup` named "Strategy Engine Silos".
3. Ensures all 7 basic `Strategy` rows exist.
4. Generates standard `Playbook` markdown rules and stores them.
5. Generates variant entries for the 41 combinations mapping exact config parameters:
   - For each variant: Create `ResearchStrategy` row.
   - For each variant: Create `Account` row linked to `AccountGroup` with $25k.
6. Seeds manual positions under `Holding`.

**Step 2: Run seed script**
`python c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/seed_data.py --config c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/config.yaml`
Expected: Database correctly initializes, listing 41 account ids and holdings in terminal output.

**Step 3: Commit**
`git add scripts/libs_py/strategy_engine/seed_data.py`
`git commit -m "feat: implement database seeding bootstrap"`

---

### Task 4: Platform Services - BrokerService

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/broker_service.py`

**Step 1: Implement BrokerService**
- Add async methods: `get_stock_quote`, `get_option_quote`, `get_chain`, `get_expiries`, `find_strike_by_delta`, `find_strike_nearest`.
- Ensure it wraps the existing python modules from `ezoptionsschwab` or `scripts/streaming/options/options_fetcher.py`.
- Add caching loops: Option chains (30s TTL), Stock quotes (5s TTL), Option quotes (10s TTL).

**Step 2: Write test assertions**
- Mock out `options_fetcher` and verify correct search mappings and cache resolutions.

**Step 3: Commit**
`git add scripts/libs_py/strategy_engine/services/broker_service.py`
`git commit -m "feat: build stateless broker service with quote caching"`

---

### Task 5: Platform Services - Volatility, Expected Move & GEX Regime Services

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/regime_service.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/em_service.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/iv_service.py`

**Step 1: Implement RegimeService**
- Reads from `GexSnapshot` and `MacroSnapshot` to fetch current spot, zg regime, zero gamma distance, and nearest dominant walls.
- Add staleness protection: staleness > 5 min for indices refuses entries.

**Step 2: Implement ExpectedMoveService**
- Aggregates daily bands from `ExpectedMove`, falling back to `RthExpectedMove` if missing.
- Computes standard deviations of price movement from session opens.

**Step 3: Implement IvService**
- Incorporates the `SPY` proxy mapping for index underlyings like `SPX`, `QQQ`, `IWM`.
- Resolves trailing EOD historical volatility data from Dolt and current ATM IV from Prisma GexSnapshots.

**Step 4: Commit**
`git add scripts/libs_py/strategy_engine/services/regime_service.py scripts/libs_py/strategy_engine/services/em_service.py scripts/libs_py/strategy_engine/services/iv_service.py`
`git commit -m "feat: complete volatility, EM, and dealer gamma regime services"`

---

### Task 6: Platform Services - Specialized Services (Holdings, Blackouts, Sizing, FVG/SMC)

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/ict_service.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/calendar_service.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/earnings_service.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/holdings_service.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/sizing_service.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/leg_quote_service.py`

**Step 1: Implement IctService**
- Connects to daily/intraday Parquet logs, running the vectorized indicator engine from `scripts/libs_py/ict_engine/core/pa.py` to identify Fair Value Gaps, Liquidity Sweeps, and session Open gaps (NWOG, NDOG).
- Includes 60s memory caching.

**Step 2: Implement Blackouts & Sizing**
- Build `CalendarService` to cross-check upcoming High-Impact macro dates (FOMC, CPI, NFP) and calculate buffer zones.
- Build `SizingService` mapping 1-contract boundaries matching balance silo capacities.
- Build `LegQuoteService` to Mark-to-Market (MTM) multiple open positions concurrently.

**Step 3: Commit**
`git commit -m "feat: implement specialized context services (Sizing, Economic Calendar, ICT, Leg MTM)"`

---

### Task 7: Strategy Framework (Base Abstract & Concrete Implementation Part 1)

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/base.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/wheel.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/zero_dte_pcs.py`

**Step 1: Write Strategy Base Class**
- Establish common lifecycle hooks: `scan` (candidate entries), `manage` (exits and rolling).
- Include default near-miss logger logic recording failed scan triggers.

**Step 2: Implement Strategy 1 (The Wheel)**
- Build the state transition engine: `CASH` -> `SHORT_PUT` -> `LONG_STOCK` -> `SHORT_CALL` -> `CASH`.
- Write the assignment checking, rolling logic, and stuck condition rule (strike >= breakeven).

**Step 3: Implement Strategy 2 (0DTE Put Credit Spread)**
- Focus on high-frequency index setups on SPY/SPX.
- Incorporate GEX regime boundaries, 1SD EM buffers, and immediate exit rules on Spot crossing Zero Gamma.

**Step 4: Commit**
`git add scripts/libs_py/strategy_engine/strategies/`
`git commit -m "feat: implement strategy core base, Wheel, and 0DTE PCS strategies"`

---

### Task 8: Strategy Framework (Concrete Implementation Part 2)

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/long_dte_credit.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/mean_reversion_em.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/wall_break.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/income_cc.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/strategies/earnings_strangle.py`

**Step 1: Implement remaining 5 strategies**
- **Strategy 3 (Long DTE):** Tastytrade 45 DTE setups with delta=0.16. Rollout rule at 21 DTE.
- **Strategy 4 (Mean Reversion):** 1SD daily EM boundary touches in positive-gamma regimes fading with a tight spread.
- **Strategy 5 (Wall Break):** Breakout debit spreads driven by major GEX walls, volume acceleration, and DEX momentum.
- **Strategy 6 (Income CC):** Tiered far-OTM covered calls against pre-owned holdings (GOOGL, TSLA, RIVN).
- **Strategy 7 (Earnings Strangle):** Trailing 60d IV expansion capture 5 days before announcement. High pre-earnings exit speed.

**Step 2: Commit**
`git add scripts/libs_py/strategy_engine/strategies/`
`git commit -m "feat: complete implementations of Long DTE, Mean Rev, Wall Break, Income CC, and Earnings Strangles"`

---

### Task 9: Paper Execution and Mark-To-Market Engine Loop

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/paper_exec.py`
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/engine.py`

**Step 1: Build paper_exec.py**
- Decouples execution orders.
- Writes new open trades, `TradeLeg` records, and updates capital balances.
- Assumes mid-fill on entry signals.

**Step 2: Build engine.py**
- Handles active ticks, calling `Strategy.scan()` and `Strategy.manage()` across all 41 variant instances.
- Periodically saves `QuoteSnapshot` details (aggregated MTM values).
- Handles EOD liquidations and daily expiration sweeps at 15:30 EST.

**Step 3: Commit**
`git add scripts/libs_py/strategy_engine/paper_exec.py scripts/libs_py/strategy_engine/engine.py`
`git commit -m "feat: build paper executor and MTM engine loop"`

---

### Task 10: Scheduling and Runner Orchestrator

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/runner.py`

**Step 1: Write runner.py**
- Main daemon executing timezone-aligned schedules (EST/EDT).
- Engine starts ticking at 9:30 ET and suspends at 16:00 ET.
- Triggers `daily_scan` cadences exactly at 10:00 ET.
- Runs `daily_rollup` at 16:30 ET.
- Runs pruning jobs at 3:00 ET (snapshots > 90d, near-misses > 30d).

**Step 2: Commit**
`git add scripts/libs_py/strategy_engine/runner.py`
`git commit -m "feat: deploy main runner loop with PM2 compatibility"`

---

### Task 11: Analytics Service & Sunday Review Report

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/analytics.py`

**Step 1: Implement AnalyticsService**
- Add async rollups calculating: Win rate, Profit Factor, ROC, Sharpe Ratio, Sortino Ratio, Drawdowns, and letter grades.
- Add feature breakdowns analyzing win rates across IV rank and GEX regime quartiles.
- Generates beautiful Sunday reviews in Markdown directly to `Rundown.content` database records.

**Step 2: Verify and Test**
- Run analytics test suit against mock closed trades to verify composite grading accuracy.

**Step 3: Commit**
`git add scripts/libs_py/strategy_engine/analytics.py`
`git commit -m "feat: implement analytics service with Sunday markdown rundown generator"`

---

### Task 12: End-To-End Verification Run

**Files:**
- Create: Mock dataset / paper simulation run

**Step 1: Run dry run check**
`python c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/runner.py --dry-run`
Expected: Daemon starts up, registers 41 variants, logs connection statuses, and verifies database handles cleanly.

**Step 2: Commit**
`git commit -m "test: verify engine boot and database connection integrity"`
