# 🗄️ Prisma Database Schema Reference Manual

This document serves as a permanent, comprehensive structural reference of the SQLite database schema defined in [schema.prisma](file:///c:/Users/vinay/tvDownloadOHLC/web/prisma/schema.prisma). It maps all models, their fields, types, default values, and relational bindings. This reference ensures consistency across automated services, Python streaming processors, and web user interfaces.

---

## 🗺️ Conceptual Schema Map

The database is structured around five core functional zones:
1. **Capital Allocation & Execution Core:** Accounts, Groups, Strategies, Playbooks, and Trades.
2. **Operational Metadata & Context:** Trade Plans, Market Conditions, Economic Calendars, Custom Tags, Notes, and Chart Snapshots.
3. **Quantitative Backtesting & Research:** Research Strategies, optimized Research Runs, and Backtest Results.
4. **Options Analytical Snapshots:** Net/Delta GEX Snapshots, Macro Wall coordinates, Expected Moves, and Volatility states.
5. **Session Workflow & Journals:** Pre-Market Daily Analyses, Wargames, Post-Market Checklist Routines, and Qualitative Diaries.

---

## 🗂️ Detailed Model Catalog

### 1. Capital Allocation & Execution Core

#### 💳 `Account`
Tracks balances, seed capital, and liquidation history.
```prisma
model Account {
  id             String        @id @default(cuid())
  name           String
  currency       String        @default("USD")
  initialBalance Float
  currentBalance Float
  isDefault      Boolean       @default(false)
  createdAt      DateTime      @default(now())
  updatedAt      DateTime      @updatedAt
  groupId        String?
  group          AccountGroup? @relation(fields: [groupId], references: [id])
  trades         Trade[]
}
```

#### 📁 `AccountGroup`
Categorizes multiple accounts (e.g. personal, prop, simulation).
```prisma
model AccountGroup {
  id          String    @id @default(cuid())
  name        String    @unique
  description String?
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt
  accounts    Account[]
}
```

#### 🎯 `Strategy`
Categorical trading strategies (e.g. "Judas Swing", "FVG Retest") with UI colors.
```prisma
model Strategy {
  id          String   @id @default(cuid())
  name        String
  description String?
  color       String   @default("#2962FF")
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
  trades      Trade[]
}
```

#### 📘 `Playbook`
Set rules and definitions backing strategy logic.
```prisma
model Playbook {
  id          String   @id @default(cuid())
  name        String   @unique
  description String?
  rules       String?
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
  trades      Trade[]
}
```

#### 📈 `Trade`
The core ledger model logging entry/exit dates, price details, and key execution metrics.
```prisma
model Trade {
  id               String           @id @default(cuid())
  ticker           String
  entryDate        DateTime
  exitDate         DateTime?
  entryPrice       Float?
  exitPrice        Float?
  quantity         Float
  direction        String
  status           String
  accountId        String
  strategyId       String?
  orderType        String           @default("MARKET")
  limitPrice       Float?
  stopPrice        Float?
  stopLoss         Float?
  takeProfit       Float?
  pnl              Float?
  fees             Float?
  risk             Float?
  mae              Float?           // Maximum Adverse Excursion
  mfe              Float?           // Maximum Favorable Excursion
  duration         Int?             // Duration in seconds
  chartSnapshot    String?
  notes            String?
  metadata         String?          // JSON field for extra broker metrics
  originalSource   String?          // "Schwab", "NinjaTrader", "Manual"
  playbookId       String?
  disciplineRating Int?             // Rating 1-10
  emotions         String?
  mistakes         String?
  createdAt        DateTime         @default(now())
  updatedAt        DateTime         @updatedAt
  chartLinks       Chart[]
  marketCondition  MarketCondition?
  tradeNotes       Note[]
  playbook         Playbook?        @relation(fields: [playbookId], references: [id])
  strategy         Strategy?        @relation(fields: [strategyId], references: [id])
  account          Account          @relation(fields: [accountId], references: [id])
  tradeEvents      TradeEvent[]
  tradePlan        TradePlan?
  tags             Tag[]            @relation("TagToTrade")
}
```

---

### 2. Operational Metadata & Context

#### 🌦️ `MarketCondition`
Captures macro indicators, volatility context, and intraday trend at execution.
```prisma
model MarketCondition {
  id      String  @id @default(cuid())
  tradeId String  @unique
  vix     Float?
  vvix    Float?
  atr     Float?
  trend   String?
  session String?
  volume  String?
  trade   Trade   @relation(fields: [tradeId], references: [id], onDelete: Cascade)
}
```

#### 🛡️ `TradePlan`
Pre-planned structural rules established before the trade was executed.
```prisma
model TradePlan {
  id            String   @id @default(cuid())
  date          DateTime
  instrument    String
  setup         String?
  entryPlan     String?
  exitPlan      String?
  riskPlan      String?
  linkedTradeId String?  @unique
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
  linkedTrade   Trade?   @relation(fields: [linkedTradeId], references: [id])
}

#### 📅 `EarningsCalendar`
Tracks upcoming US stock earnings announcements synced via dual-provider (Nasdaq API + yfinance) engine.
```prisma
model EarningsCalendar {
  id           String   @id @default(cuid())
  ticker       String
  earningsDate DateTime
  beforeMarket Boolean  // BMO = true, AMC = false
  confirmed    Boolean  @default(false)
  source       String   @default("yfinance") // "nasdaq_api" | "yfinance"
  fetchedAt    DateTime @default(now())
  company      String?
  marketCap    Float?

  @@unique([ticker, earningsDate])
  @@index([earningsDate])
}
```

```

#### 🏷️ `Tag` & `TagGroup`
Flexible tagging system for classifying trades.
```prisma
model Tag {
  id      String    @id @default(cuid())
  name    String    @unique
  groupId String?
  group   TagGroup? @relation(fields: [groupId], references: [id])
  trades  Trade[]   @relation("TagToTrade")
}

model TagGroup {
  id    String @id @default(cuid())
  name  String @unique
  color String @default("#6b7280")
  tags  Tag[]
}
```

#### 🎙️ `Note`
Tracks qualitative details and AI reviews generated for executions.
```prisma
model Note {
  id          String    @id @default(cuid())
  tradeId     String?
  date        DateTime?
  type        String    @default("trade")
  content     String
  aiGenerated Boolean   @default(false)
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt
  mood        String?
  tags        String?
  trade       Trade?    @relation(fields: [tradeId], references: [id], onDelete: Cascade)
}
```

---

### 3. Quantitative Backtesting & Research

#### 🧪 `ResearchStrategy` & `ResearchRun`
Manages experimental backtesting data, parameter combinations, equity curve outputs, and reproducibility hashes.
```prisma
model ResearchStrategy {
  id          String        @id @default(cuid())
  name        String        @unique
  description String?
  color       String        @default("#2962FF")
  createdAt   DateTime      @default(now())
  updatedAt   DateTime      @updatedAt
  runs        ResearchRun[]
}

model ResearchRun {
  id              String           @id @default(cuid())
  runId           String           @unique
  ticker          String
  environment     String           @default("Backtest")
  strategyId      String
  metricsJson     String?          // JSON dictionary containing final statistics
  configJson      String?          // JSON parameters passed to the engine
  thumbnailJson   String?
  equityCurvePath String?          // Path to local plot files
  grade           String?          // Grade rating (e.g. "A+", "B")
  filePath        String?
  gitHash         String?          // Tracks exact source code commit
  createdAt       DateTime         @default(now())
  updatedAt       DateTime         @updatedAt
  strategy        ResearchStrategy @relation(fields: [strategyId], references: [id], onDelete: Cascade)

  @@index([strategyId])
  @@index([ticker])
}
```

#### 📊 `BacktestResult`
Legacy or simplified backtest metrics output container.
```prisma
model BacktestResult {
  id           String   @id @default(cuid())
  strategy     String
  ticker       String
  timeframe    String
  startDate    DateTime
  endDate      DateTime
  totalTrades  Int
  winRate      Float
  profitFactor Float
  totalPnl     Float
  config       String   // Stringified input configs
  trades       String   // Stringified trades
  createdAt    DateTime @default(now())
}
```

---

### 4. Options Analytical Snapshots

#### ⚡ `GexSnapshot`
Tracks real-time dealer positioning metrics (GEX, Speed, Vanna, skews, volume centroids) executed every 60 seconds.
```prisma
model GexSnapshot {
  id                    Int      @id @default(autoincrement())
  ticker                String
  timestamp             DateTime
  tradingDate           DateTime
  totalGex              Float
  totalGexDeltaAdj      Float?
  callGammaTotal        Float?
  putGammaTotal         Float?
  gexRegime             String
  regimeLabel           String?
  spotPrice             Float
  gammaMagnet           Float?
  pinStrike             Float?
  callVolumeCentroid    Float?
  putVolumeCentroid     Float?
  netSpeedExposure      Float?
  netVannaExposure      Float?
  put25dIv              Float?
  call25dIv             Float?
  volatilitySkewPremium Float?
  futuresSymbol         String?
  futuresTranslationMode String?
  futuresBasisSpread    Float?
  futuresBasisRatio     Float?
  createdAt             DateTime @default(now())

  @@index([ticker, tradingDate])
  @@index([ticker, timestamp])
}
```

#### 🛡️ `MacroSnapshot`
Maintains daily high-significance wall coordinates (Call Wall, Put Wall, Zero Gamma boundary) evaluated across wide thresholds.
```prisma
model MacroSnapshot {
  id                    String   @id @default(cuid())
  ticker                String
  timestamp             DateTime
  tradingDate           DateTime
  spotPrice             Float
  macroCallWall         Float?
  macroPutWall          Float?
  zeroGamma             Float?
  put25dIv              Float?
  call25dIv             Float?
  volatilitySkewPremium Float?
  anomalies             String?
  dominantNodes         String?

  @@unique([ticker, tradingDate])
  @@index([ticker])
}
```

#### 📦 Expected Move & Volatility Metrics
Models used to persist historical and RTH calculations for volatility (HV/IV) and expected deviations.
```prisma
model ExpectedMove {
  id              Int      @id @default(autoincrement())
  ticker          String
  calculationDate DateTime
  expiryDate      DateTime
  price           Float
  straddle        Float
  em365           Float
  em252           Float
  adjEm           Float
  manualEm        Float?
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt
  basis           String?
  note            String?

  @@unique([ticker, calculationDate, expiryDate])
}

model ExpectedMoveHistory {
  id            Int      @id @default(autoincrement())
  ticker        String
  date          DateTime
  closePrice    Float
  straddlePrice Float?
  emStraddle    Float?
  iv365         Float?
  em365         Float?
  iv252         Float?
  em252         Float?
  source        String?
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt

  @@unique([ticker, date])
  @@index([ticker])
}

model RthExpectedMove {
  id            Int      @id @default(autoincrement())
  ticker        String
  date          DateTime
  openPrice     Float?
  vixValue      Float?
  straddlePrice Float?
  emStraddle    Float?
  ivAtOpen      Float?
  emIv          Float?
  emVix         Float?
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt

  @@unique([ticker, date])
  @@index([ticker])
}

model HistoricalVolatility {
  id         Int      @id @default(autoincrement())
  ticker     String
  date       DateTime
  iv         Float
  hv         Float?
  closePrice Float?
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  @@unique([ticker, date])
  @@index([ticker])
}
```

---

### 5. Session Workflow, Wargaming, and Diaries

#### 📔 `Journal` & `Rundown`
Standard qualitative session logs capturing thoughts and scoring subjective metrics.
```prisma
model Journal {
  id        String   @id @default(cuid())
  date      DateTime @unique
  content   String
  mood      String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

model Rundown {
  id        String   @id @default(cuid())
  date      DateTime @unique
  content   String?
  mood      String?
  score     Int?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

model Routine {
  id        String   @id @default(cuid())
  date      DateTime @unique
  checklist String?
  rating    Int?
  notes     String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}
```

#### 🛡️ `Analysis` & `Wargame`
Calculates pre-market technical setups, daily invalidate targets, and scenario planning trees.
```prisma
model Analysis {
  id                    String    @id @default(cuid())
  date                  DateTime  @unique
  sentiment             String?
  bias                  String?
  notes                 String?
  keyLevels             String?
  invalidationLevel     String?
  profilerSnapshot      String?
  candleScienceSnapshot String?
  createdAt             DateTime  @default(now())
  updatedAt             DateTime  @updatedAt
  charts                Chart[]
  wargames              Wargame[]
}

model Wargame {
  id          String   @id @default(cuid())
  analysisId  String
  scenario    String
  plan        String
  probability String?
  outcome     String?
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
  charts      Chart[]
  analysis    Analysis @relation(fields: [analysisId], references: [id], onDelete: Cascade)
}
```

---

### 6. Supporting Utilities

#### 📸 `Chart`
Dynamic URLs attached to Trade execution logs or Daily Analysis structures.
```prisma
model Chart {
  id         String    @id @default(cuid())
  url        String
  type       String?
  tags       String?
  tradeId    String?
  analysisId String?
  wargameId  String?
  createdAt  DateTime  @default(now())
  updatedAt  DateTime  @updatedAt
  wargame    Wargame?  @relation(fields: [wargameId], references: [id])
  analysis   Analysis? @relation(fields: [analysisId], references: [id])
  trade      Trade?    @relation(fields: [tradeId], references: [id])
}
```

#### 📡 `SchwabToken`
Maintains primary access credentials, tokens, and expirations for options chain requests.
```prisma
model SchwabToken {
  id           String   @id @default("schwab-primary")
  accessToken  String
  refreshToken String
  expiresAt    Int
  idToken      String?
  tokenType    String
  scope        String?
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
}
```

#### 📅 `EconomicEvent` & `TradeEvent`
Economic calendar and event impact records linked to custom executions.
```prisma
model EconomicEvent {
  id        String       @id @default(cuid())
  datetime  DateTime
  name      String
  impact    String
  actual    Float?
  forecast  Float?
  previous  Float?
  createdAt DateTime     @default(now())
  trades    TradeEvent[]
}

model TradeEvent {
  tradeId String
  eventId String
  event   EconomicEvent @relation(fields: [eventId], references: [id], onDelete: Cascade)
  trade   Trade         @relation(fields: [tradeId], references: [id], onDelete: Cascade)

  @@id([tradeId, eventId])
}
```

#### 🏷️ `WatchlistGroup` & `WatchlistItem`
Custom portfolio watchlists containing dynamic tickers.
```prisma
model WatchlistGroup {
  id        String          @id @default(cuid())
  name      String          @unique
  isDefault Boolean         @default(false)
  createdAt DateTime        @default(now())
  updatedAt DateTime        @updatedAt
  items     WatchlistItem[]
}

model WatchlistItem {
  id        String         @id @default(cuid())
  symbol    String
  name      String?
  groupId   String
  createdAt DateTime       @default(now())
  group     WatchlistGroup @relation(fields: [groupId], references: [id], onDelete: Cascade)

  @@unique([groupId, symbol])
}
```

#### 📰 `MarketNews`
General publisher logs stored locally.
```prisma
model MarketNews {
  id                  String   @id @default(cuid())
  uuid                String   @unique
  title               String
  publisher           String
  link                String
  providerPublishTime DateTime
  type                String?
  relatedTickers      String?
  createdAt           DateTime @default(now())
}
```
