# Options Strategy Engine — Master Specification

**Version:** 1.0
**Status:** Implementation-ready
**Date:** 2026-05-17
**Author context:** Built on top of the existing TCM Trading System infrastructure (GEX/DEX engine, ICT vectorized library, Prisma SQLite store, Dolt volatility history, Schwab API integration).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architectural Integration](#2-architectural-integration)
3. [Net-New Prisma Models](#3-net-new-prisma-models)
4. [Platform Services](#4-platform-services)
5. [Strategy Framework](#5-strategy-framework)
6. [Engine Orchestration](#6-engine-orchestration)
7. [Paper Execution & Mark-to-Market](#7-paper-execution--mark-to-market)
8. [The Seven Strategies](#8-the-seven-strategies)
9. [Analytics & Weekly Review](#9-analytics--weekly-review)
10. [Seed Data & Bootstrap](#10-seed-data--bootstrap)
11. [Operational Runbook](#11-operational-runbook)
12. [Open Questions & Future Work](#12-open-questions--future-work)

---

## 1. Overview

### 1.1 What this engine does

A fully automated paper-trading engine that runs continuously on the user's laptop during market hours. Every tick, it:

1. Pulls current market regime state from existing Prisma tables (`GexSnapshot`, `MacroSnapshot`, `ExpectedMove`).
2. For each enabled strategy variant, evaluates entry conditions. If conditions pass, opens a paper trade by writing a `Trade` row with attached `TradeLeg` rows.
3. For each open paper trade, marks-to-market using the Schwab option-chain API, writes a `QuoteSnapshot` row, and evaluates exit conditions.
4. Logs every "near-miss" (signal that almost fired but failed a specific filter) for post-hoc filter analysis.
5. Periodically (daily and weekly) rolls up performance into `ResearchRun` records with metrics, grades, and equity curves.

### 1.2 Design goals (in priority order)

1. **Learning > optimization.** The engine exists to teach the user options strategy mechanics through systematic comparison, not to maximize a single strategy's return.
2. **Honest data.** Every signal that fires logs every filter value at entry. Every near-miss logs why it failed. Weekly review surfaces feature-importance breakdowns from real trade history.
3. **Capital silos.** Each strategy variant runs against its own simulated capital account; they never compete for capital. Comparison is per-strategy, not portfolio-level.
4. **Existing infrastructure first.** Use the user's existing GEX engine, ICT library, Schwab adapter, Prisma schema, and Dolt history. Add only what is genuinely missing.
5. **Forward-only.** No historical backfill simulation. Engine begins generating trades from go-live; results accumulate from day one.

### 1.3 Non-goals (v1)

- Live trading. Engine is read-only against Schwab; it never submits orders.
- Multi-account capital allocation (Layer 2). Deferred until per-strategy performance data exists.
- Futures options. Architecture supports them; v1 does not include them.
- ICT persistence. Computed on-demand from parquet; not cached.
- Backtesting against historical data. Engine is forward-only.
- Pre-market and after-hours signal generation.

### 1.4 Strategy bucket (locked)

| # | Strategy | Underlyings (v1) |
|---|----------|------------------|
| 1 | Wheel (CSP → CC chain) | NVDA, TSLA, AAPL, GOOGL, MSFT, AMZN |
| 2 | 0DTE put credit spreads | SPY, SPX |
| 3 | 45 DTE credit spreads | SPY, NVDA, TSLA, IWM |
| 4 | Mean reversion to EM boundaries | SPY, SPX |
| 5 | GEX wall break debit spreads | SPY, SPX |
| 6 | Income covered calls | GOOGL, TSLA, RIVN (staged) |
| 7 | Earnings strangles | NVDA, TSLA, AAPL, GOOGL |

**Staged:** RIVN income CC strategy is defined but not active until ≥4 weeks of forward data collection on RIVN.

**Dropped:** AMD (config gap in GEX pipeline; revisit when fixed).

### 1.5 Tick cadence

| Underlying class | Cadence | Notes |
|------------------|---------|-------|
| Index/ETF (SPY, SPX, QQQ, IWM) | 60 seconds | Matches existing GEX scoring cadence |
| Stocks (NVDA, TSLA, AAPL, etc.) | 5 minutes | Lower-frequency strategies; GEX refresh is 10 min so 5 min is upper bound |
| Daily strategies (Wheel CSP scan, earnings scan) | Once per day, 10:00 ET | Premium-selling doesn't need intraday |

---

## 2. Architectural Integration

### 2.1 Where the strategy engine lives

```
scripts/libs_py/strategy_engine/         # NEW
├── __init__.py
├── services/
│   ├── __init__.py
│   ├── broker_service.py                # wraps ezoptionsschwab + options_fetcher
│   ├── regime_service.py                # reads GexSnapshot / MacroSnapshot
│   ├── em_service.py                    # reads ExpectedMove / ExpectedMoveHistory / RthExpectedMove
│   ├── iv_service.py                    # routes between Dolt (historical) and Prisma (current)
│   ├── ict_service.py                   # on-demand: loader.py + pa.py
│   ├── calendar_service.py              # wraps EconomicEvent
│   ├── earnings_service.py              # yfinance → EarningsCalendar
│   ├── holdings_service.py              # Holding table CRUD
│   ├── sizing_service.py                # respects Account.initialBalance + trade_policies
│   └── leg_quote_service.py             # current option mid via Schwab chain
├── strategies/
│   ├── __init__.py
│   ├── base.py                          # Strategy ABC + dataclasses
│   ├── wheel.py
│   ├── zero_dte_pcs.py
│   ├── long_dte_credit.py
│   ├── mean_reversion_em.py
│   ├── wall_break.py
│   ├── income_cc.py
│   └── earnings_strangle.py
├── engine.py                            # main tick loop
├── paper_exec.py                        # opens Trades, writes TradeLegs, MTM, closes
├── signal_log.py                        # SignalNearMiss + Trade.metadata tagging
├── analytics.py                         # weekly review, ResearchRun rollups
├── seed_data.py                         # one-time setup
├── config.yaml                          # strategy params, capital silos, cadences
└── runner.py                            # entry point; APScheduler config
```

### 2.2 Integration with existing modules

| Existing module | Used by strategy engine for | Modification needed |
|-----------------|------------------------------|---------------------|
| `streaming/options/ezoptionsschwab.py` | Quote fetching, chain fetching | None — consumed via broker_service |
| `streaming/options/options_fetcher.py` | Chain fetcher class | None — consumed via broker_service |
| `streaming/options/gex_calculator.py` | Already runs in live pipeline, writes to `GexSnapshot` | None |
| `streaming/options/level_scorer.py` | Already runs, writes to `MacroSnapshot` | None |
| `streaming/options/run_options_levels.py` | Already runs the pipeline | None |
| `streaming/api_expected_move.py` | Writes to `ExpectedMove` / `ExpectedMoveHistory` | None |
| `streaming/news_calendar_fetcher.py` | Already populates `EconomicEvent` | None |
| `libs_py/ict_engine/core/pa.py` | Called on-demand by ict_service | None |
| `libs_py/nqstats/sessions.py` | Session tagging in ict_service | None |
| `libs_py/data/loader.py` | Parquet reads for ICT context | None |
| `libs_py/risk/trade_policies.py` | Cap on position sizing | None — consumed |
| `web/prisma/schema.prisma` | Database schema | **5 new models added** |
| Dolt `volatility_history` | Historical IV rank/percentile | None — read-only via iv_service |

**Principle:** the engine is purely additive. No existing module is modified.

### 2.3 Process model

Two long-running Python processes on the user's laptop:

1. **Existing options pipeline** (`run_options_levels.py`) — continues running unchanged. Writes `GexSnapshot`, `MacroSnapshot`, `ExpectedMove` every 60 sec (Tier-1) / 10 min (Tier-2).
2. **NEW: Strategy engine** (`strategy_engine/runner.py`) — ticks every 60 sec for index strategies, every 5 min for stock strategies, once daily at 10:00 ET for daily strategies. Reads from Prisma + Dolt + parquet. Writes to Prisma.

Both run as separate processes. They communicate only through Prisma — no direct IPC.

### 2.4 Data flow

```
Schwab API ──► ezoptionsschwab ──► options_fetcher ──► gex_calculator ──► GexSnapshot
                                                    └─► level_scorer ──► MacroSnapshot
                                                    └─► api_expected_move ──► ExpectedMove

Dolt cron ──────────────────────────────────────────────► volatility_history (Dolt, weekly)

ForexFactory ──► news_calendar_fetcher ─────────────────► EconomicEvent (Prisma)

yfinance ──────► earnings_service (NEW) ────────────────► EarningsCalendar (NEW table)

                                                          │
                                                          ▼
                                              ┌──────────────────────┐
                                              │  Strategy Engine     │
                                              │                      │
Prisma ───► regime/em/iv/calendar services ──►│  Strategy.scan()     │
Dolt   ───► iv_service                       │       │              │
Parquet ──► ict_service                       │       ▼              │
                                              │   Signal             │
                                              │       │              │
                                              │       ▼              │
                                              │   paper_exec         │──► Trade + TradeLeg
                                              │       │              │
                                              │       ▼              │
                                              │  MTM every tick      │──► QuoteSnapshot
                                              │       │              │
                                              │       ▼              │
                                              │  Strategy.manage()   │──► Trade close + Account update
                                              └──────────────────────┘
                                                          │
                                                          ▼
                                                 analytics (daily/weekly)
                                                          │
                                                          ▼
                                                ResearchRun + Rundown
```

### 2.5 Configuration

A single YAML config file at `scripts/libs_py/strategy_engine/config.yaml` controls:

- Per-strategy enable/disable flags
- Per-strategy variant parameter overrides
- Tick cadences
- Capital silo sizes
- Logging level and destinations
- Schwab API rate-limit budgets

`seed_data.py` reads this file on first run to create Accounts, ResearchStrategies, and Playbooks. Subsequent edits to the YAML do not retroactively modify existing rows — users must re-run seed_data with explicit `--update` flag.

---

## 3. Net-New Prisma Models

Five models added to `web/prisma/schema.prisma`. All other tables unchanged.

### 3.1 TradeLeg

Per-leg detail for multi-leg paper trades. One Trade has many TradeLegs.

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
```

Stock legs (covered call underlying) are stored as TradeLeg with `optionType="STOCK"`, `strike=null`, `expiry=null`.

### 3.2 QuoteSnapshot

Mark-to-market history. Used to compute MAE, MFE, P&L curves.

```prisma
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
```

Aged: rows older than 90 days are deleted by maintenance job (§11).

### 3.3 SignalNearMiss

Strategies that almost fired. Critical for post-hoc filter analysis.

```prisma
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
```

Volume: ~10k rows/day across 25 variants. Pruned to last 30 days at full resolution by maintenance job.

### 3.4 Holding

The user's actual share positions (for income CC strategy). Seeded manually.

```prisma
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
```

### 3.5 EarningsCalendar

Upcoming earnings dates per ticker. Populated weekly from yfinance.

```prisma
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

### 3.6 Trade model extension

The existing `Trade` model gets two new relations. No field additions:

```prisma
model Trade {
  // ... existing fields unchanged ...
  legs          TradeLeg[]                 // NEW
  snapshots     QuoteSnapshot[]            // NEW

  // Documented usage of existing fields:
  // metadata: JSON containing {gex_regime, iv_rank, zero_gamma_distance,
  //           em_distance_sd, ict_context, research_strategy_id, vix_at_entry, ...}
  // notes: human-readable signal description
  // originalSource: always "strategy_engine"
}
```

### 3.7 Migration

```bash
cd web/
npx prisma migrate dev --name strategy_engine_v1
```

---

## 4. Platform Services

All services are stateless Python classes instantiated once at engine startup and passed to strategies. They wrap existing infrastructure with clean, testable interfaces.

**Convention:** All services use async Python where the underlying call is I/O-bound (Prisma queries, Schwab API), sync where it's pure computation (regime checks from cached snapshots).

### 4.1 BrokerService

Wraps `ezoptionsschwab` and `options_fetcher`. Centralizes all Schwab API calls. Caches aggressively to stay under rate limits.

```python
# scripts/libs_py/strategy_engine/services/broker_service.py

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class OptionQuote:
    """Single-leg option quote."""
    symbol: str           # OCC symbol
    bid: float
    ask: float
    mid: float            # (bid + ask) / 2
    last: float
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
    open_interest: int
    volume: int


@dataclass
class StockQuote:
    """Equity / ETF quote."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int


@dataclass
class ChainStrike:
    """One strike row in an option chain (combined call+put)."""
    strike: float
    call: Optional[OptionQuote]
    put: Optional[OptionQuote]


class BrokerService:
    """Read-only wrapper over Schwab API. NEVER submits orders.

    Caches:
        - Option chains: 30 sec TTL per (ticker, expiry)
        - Stock quotes: 5 sec TTL per ticker
        - Single option quotes: 10 sec TTL per OCC symbol
    """

    def __init__(self, options_fetcher, cache_ttl_chain_sec: int = 30):
        """
        Args:
            options_fetcher: existing OptionChainFetcher instance from
                             scripts/streaming/options/options_fetcher.py
            cache_ttl_chain_sec: TTL for chain cache. Default 30s.
        """
        ...

    async def get_stock_quote(self, ticker: str) -> StockQuote:
        """Current quote for an equity or ETF. Cached 5s."""
        ...

    async def get_option_quote(self, occ_symbol: str) -> OptionQuote:
        """Current quote for a specific option contract by OCC symbol. Cached 10s."""
        ...

    async def get_chain(
        self,
        ticker: str,
        expiry: date,
        strike_count: int = 50,
    ) -> list[ChainStrike]:
        """Full option chain for a ticker and expiry.

        Returns list of ChainStrike sorted ascending by strike. Cached 30s.
        Raises BrokerUnavailableError if Schwab API is unreachable.
        """
        ...

    async def get_expiries(self, ticker: str) -> list[date]:
        """All available expirations for a ticker, sorted ascending.

        Used by strategies to find the right DTE expiry. Cached 5 min.
        """
        ...

    async def find_strike_by_delta(
        self,
        ticker: str,
        expiry: date,
        target_delta: float,
        option_type: str,    # "CALL" or "PUT"
    ) -> Optional[OptionQuote]:
        """Convenience: returns the option whose absolute delta is closest to target.

        For PUTs, target_delta should be supplied positive (e.g. 0.30 means
        the strike whose put delta is closest to -0.30).
        Returns None if chain unavailable or all candidates too far from target.
        """
        ...

    async def find_strike_nearest(
        self,
        ticker: str,
        expiry: date,
        target_strike: float,
        option_type: str,
    ) -> Optional[OptionQuote]:
        """Convenience: returns the option closest to target_strike."""
        ...


class BrokerUnavailableError(Exception):
    """Raised when Schwab API cannot be reached after retries."""
    pass
```

### 4.2 RegimeService

Reads `GexSnapshot` and `MacroSnapshot` from Prisma. Provides the GEX regime context strategies need for filtering.

```python
# scripts/libs_py/strategy_engine/services/regime_service.py

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional


@dataclass
class GexRegime:
    """Current GEX regime state for a ticker."""
    ticker: str
    snapshot_at: datetime           # timestamp of the underlying GexSnapshot
    spot_price: float

    total_gex: float
    gex_regime: str                 # "POSITIVE" | "NEGATIVE" | "TRANSITION"
    regime_label: Optional[str]     # human-readable from GexSnapshot.regimeLabel
    zero_gamma: Optional[float]
    distance_to_zero_gamma_pct: Optional[float]  # (spot - zg) / zg * 100

    # Walls from MacroSnapshot
    macro_call_wall: Optional[float]
    macro_put_wall: Optional[float]

    # Second-order
    net_vanna_exposure: Optional[float]
    net_speed_exposure: Optional[float]
    volatility_skew_premium: Optional[float]
    put_25d_iv: Optional[float]
    call_25d_iv: Optional[float]

    # Centroids
    call_volume_centroid: Optional[float]
    put_volume_centroid: Optional[float]
    gamma_magnet: Optional[float]
    pin_strike: Optional[float]


@dataclass
class RegimeHistory:
    """Trajectory of regime over a time window. Used to confirm regime stability."""
    snapshots: list[GexRegime]      # chronological, oldest first
    minutes_in_current_regime: float
    spot_drift_pct: float


class RegimeService:
    """Reads GEX regime data from Prisma. Caches latest snapshot per ticker for 30s."""

    def __init__(self, prisma_client, cache_ttl_sec: int = 30):
        ...

    async def get_current_regime(self, ticker: str) -> Optional[GexRegime]:
        """Latest GEX regime snapshot for ticker.

        Returns None if no snapshot exists in the last 30 minutes (data staleness check).
        For index tickers (SPY/SPX/QQQ/IWM) snapshots are 60s; staleness > 5 min indicates
        the upstream pipeline has stopped — strategies should refuse to trade.
        """
        ...

    async def get_regime_history(
        self,
        ticker: str,
        lookback_minutes: int = 30,
    ) -> RegimeHistory:
        """Trajectory of regime snapshots over the lookback window.

        Used to answer: "has spot been above zero-gamma for the last 30 minutes?"
        """
        ...

    async def is_in_positive_gamma(self, ticker: str, stable_for_min: int = 30) -> bool:
        """Convenience: True if spot has been above zero-gamma for stable_for_min minutes.

        Returns False if data is stale or zero-gamma is unavailable.
        """
        ...

    async def get_nearest_walls(
        self,
        ticker: str,
        above_spot: bool = True,
        n: int = 3,
    ) -> list[float]:
        """Returns the n nearest call walls above spot (if above_spot=True) or put walls below.

        Reads from MacroSnapshot.dominantNodes (JSON-parsed) for the latest tradingDate.
        Returns empty list if no MacroSnapshot exists or nodes can't be parsed.
        """
        ...

    async def get_distance_to_em_boundary(
        self,
        ticker: str,
        side: str,                  # "UPPER" or "LOWER"
        spot: Optional[float] = None,
    ) -> Optional[float]:
        """Distance from spot to today's expected move boundary, in dollars.

        Negative if spot has already crossed the boundary on that side.
        Side="UPPER" returns spot - upper_em_boundary.
        """
        ...
```

### 4.3 ExpectedMoveService

Reads `ExpectedMove`, `ExpectedMoveHistory`, `RthExpectedMove` from Prisma. Provides EM context.

```python
# scripts/libs_py/strategy_engine/services/em_service.py

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class ExpectedMoveBands:
    """Expected move bands for a ticker on a date."""
    ticker: str
    calc_date: date
    expiry_date: date
    spot_at_calc: float
    straddle_price: float
    em_365: float                   # 365-day annualization
    em_252: float                   # 252-day annualization
    adj_em: float                   # 0.85 × straddle (the user's adjusted EM)

    upper_boundary_1sd: float       # spot + adj_em
    lower_boundary_1sd: float       # spot - adj_em
    upper_boundary_2sd: float       # spot + 2 * adj_em
    lower_boundary_2sd: float       # spot - 2 * adj_em


class ExpectedMoveService:
    """Wraps ExpectedMove and RthExpectedMove tables."""

    def __init__(self, prisma_client):
        ...

    async def get_today_em(self, ticker: str) -> Optional[ExpectedMoveBands]:
        """Today's expected move bands for ticker.

        Priority:
        1. Latest ExpectedMove row with calculationDate = today
        2. RthExpectedMove if ExpectedMove not present
        3. None if neither exists

        Used by intraday strategies (0DTE PCS, mean reversion, wall break).
        """
        ...

    async def get_historical_em_hit_rate(
        self,
        ticker: str,
        lookback_days: int = 60,
    ) -> Optional[dict]:
        """How often does spot stay within the EM boundary historically?

        Reads ExpectedMoveHistory joined against actual close prices.
        Returns {within_1sd_pct: float, beyond_upper_pct: float, beyond_lower_pct: float}
        or None if insufficient history.

        Used for analytics, not real-time decisions.
        """
        ...

    async def get_em_distance_in_sd(
        self,
        ticker: str,
        current_spot: float,
    ) -> Optional[float]:
        """How many SDs is current_spot from open price?

        Returns (current_spot - open) / adj_em. Positive = above open.
        Used by mean reversion strategy to detect 1SD touches.
        """
        ...
```

### 4.4 IvService

Routes IV queries between Dolt (historical) and Prisma (current/intraday).

```python
# scripts/libs_py/strategy_engine/services/iv_service.py

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class IvSnapshot:
    """IV state for a ticker on a date."""
    ticker: str
    on_date: date
    iv: float                       # current IV (EOD if historical, latest if today)
    hv: Optional[float]             # historical realized vol
    iv_rank: Optional[float]        # 0-100, vs 52w high/low
    iv_percentile: Optional[float]  # 0-100, % of last 252d below current
    iv_year_high: Optional[float]
    iv_year_low: Optional[float]
    iv_hv_ratio: Optional[float]    # iv / hv (vol risk premium indicator)
    source: str                     # "dolt" | "prisma_eod" | "prisma_rth"


class IvService:
    """Centralized IV access. Routes between Dolt and Prisma sources.

    Proxy mapping (handled below this layer in dolt.ts toDoltSymbols):
        SPX → SPY
        QQQ → SPY (when QQQ not in Dolt; logged as warning)
        IWM → SPY (when IWM not in Dolt; flagged with low confidence)
        RIVN → None (no IV filter available)
    """

    # Tickers known to be present in Dolt volatility_history (7-year history)
    DOLT_NATIVE = {"SPY", "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "AMD"}

    # Tickers that use SPY proxy in Dolt
    DOLT_PROXIED = {"SPX", "QQQ", "IWM"}

    # Tickers with no IV history anywhere
    DOLT_UNAVAILABLE = {"RIVN"}

    def __init__(self, prisma_client, dolt_adapter):
        """
        Args:
            prisma_client: Prisma async client
            dolt_adapter: existing dolt.ts wrapper or equivalent Python Dolt query layer
        """
        ...

    async def get_iv_snapshot(self, ticker: str, on_date: Optional[date] = None) -> Optional[IvSnapshot]:
        """Best available IV snapshot for ticker on date.

        Resolution order:
        1. If ticker in DOLT_NATIVE: query Dolt volatility_history → IvSnapshot.source="dolt"
        2. If ticker in DOLT_PROXIED: query Dolt for SPY → IvSnapshot.source="dolt" (note ticker still set to requested)
        3. If on_date is today and ticker is in Prisma: latest GexSnapshot for intraday IV
        4. Otherwise: None

        Returns None if ticker is in DOLT_UNAVAILABLE.
        """
        ...

    async def get_iv_rank(self, ticker: str, on_date: Optional[date] = None) -> Optional[float]:
        """IV rank 0-100. None if unavailable."""
        ...

    async def get_iv_percentile(self, ticker: str, on_date: Optional[date] = None) -> Optional[float]:
        """IV percentile 0-100 (% of last 252d below current). None if unavailable."""
        ...

    async def get_iv_hv_ratio(self, ticker: str, on_date: Optional[date] = None) -> Optional[float]:
        """Vol risk premium: IV / HV. >1 means IV is rich vs realized. None if HV unavailable."""
        ...

    async def get_current_intraday_iv(self, ticker: str) -> Optional[float]:
        """Latest ATM IV from GexSnapshot (intraday, fresh within last 60s).

        Used by strategies that want a real-time IV reading, not EOD.
        Falls back to None if no fresh snapshot.
        """
        ...

    async def get_current_skew(self, ticker: str) -> Optional[float]:
        """volatilitySkewPremium from latest GexSnapshot. None if unavailable.

        Higher = put-side IV richer than call-side (downside fear).
        """
        ...
```

### 4.5 IctService

On-demand ICT context. Calls existing `pa.py` against parquet windows. In-process cache with 60-sec TTL.

```python
# scripts/libs_py/strategy_engine/services/ict_service.py

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional


@dataclass
class FairValueGap:
    """A fair value gap detected in price action."""
    direction: str                  # "BULLISH" | "BEARISH"
    top: float
    bottom: float
    created_at: datetime
    is_mitigated: bool
    distance_from_spot_pct: float   # signed: + if above spot, - if below


@dataclass
class OrderBlock:
    """An order block."""
    direction: str
    top: float
    bottom: float
    created_at: datetime
    is_mitigated: bool


@dataclass
class LiquiditySweep:
    """A liquidity sweep event."""
    direction: str                  # "BUYSIDE" (swept highs) | "SELLSIDE" (swept lows)
    level: float                    # the swept level
    occurred_at: datetime
    minutes_ago: int


@dataclass
class SessionContext:
    """Current trading session tags."""
    asia: bool
    london: bool
    ny_am: bool
    ny_pm: bool
    rth: bool


@dataclass
class IctContext:
    """Snapshot of ICT-relevant state for a ticker at a timeframe."""
    ticker: str
    timeframe: str                  # "1m" | "5m" | "15m" | "1h"
    computed_at: datetime
    spot: float

    bullish_fvgs: list[FairValueGap] = field(default_factory=list)
    bearish_fvgs: list[FairValueGap] = field(default_factory=list)
    recent_bullish_obs: list[OrderBlock] = field(default_factory=list)
    recent_bearish_obs: list[OrderBlock] = field(default_factory=list)
    recent_sweeps: list[LiquiditySweep] = field(default_factory=list)
    session: SessionContext = field(default_factory=lambda: SessionContext(False, False, False, False, False))

    # Higher-timeframe references
    nwog_high: Optional[float] = None
    nwog_low: Optional[float] = None
    ndog_high: Optional[float] = None
    ndog_low: Optional[float] = None

    # Derived flags
    htf_bias: Optional[str] = None  # "BULLISH" | "BEARISH" | "NEUTRAL"

    def has_bullish_fvg_near(self, spot: float, tolerance_pct: float = 0.5) -> bool:
        """Convenience: any unmitigated bullish FVG within tolerance_pct of spot."""
        ...

    def has_bearish_fvg_near(self, spot: float, tolerance_pct: float = 0.5) -> bool:
        ...

    def to_dict(self) -> dict:
        """Serialize for storage in Trade.metadata JSON."""
        ...


class IctService:
    """On-demand ICT context. Computes from parquet via existing pa.py.

    Caches in-process for 60 sec per (ticker, timeframe).
    No persistent storage of ICT state.
    """

    def __init__(self, parquet_loader, pa_module, sessions_module, nwog_ndog_module):
        """
        Args:
            parquet_loader: existing loader.py module
            pa_module: existing libs_py/ict_engine/core/pa.py
            sessions_module: existing libs_py/nqstats/sessions.py
            nwog_ndog_module: existing trader/generate_ict_nwog_ndog.py
        """
        ...

    def get_context(
        self,
        ticker: str,
        timeframe: str = "5m",
        lookback_bars: int = 200,
    ) -> Optional[IctContext]:
        """Current ICT context for ticker at timeframe.

        Reads last `lookback_bars` from the corresponding parquet file,
        runs vectorized pa.py to detect FVGs/OBs/sweeps, attaches session tags
        and NWOG/NDOG references.

        Cached in-process for 60s per (ticker, timeframe).
        Returns None if parquet file is unavailable or too short.
        """
        ...

    def invalidate_cache(self, ticker: Optional[str] = None) -> None:
        """Force re-computation on next call. Used for testing."""
        ...
```

### 4.6 CalendarService

Wraps existing `EconomicEvent` with the "is right now a blackout window?" interface.

```python
# scripts/libs_py/strategy_engine/services/calendar_service.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class BlackoutWindow:
    """An economic event blackout."""
    event_name: str
    impact: str                     # "High" | "Medium" | "Low"
    event_time: datetime
    pre_minutes: int                # minutes before event the blackout starts
    post_minutes: int               # minutes after event the blackout ends


class CalendarService:
    """Read-only wrapper over EconomicEvent. Adds blackout-window semantics."""

    # Default pre/post buffers per impact level (configurable in config.yaml)
    DEFAULT_BUFFERS = {
        "High": (120, 60),     # 2h before, 1h after (FOMC, NFP, CPI)
        "Medium": (30, 30),    # 30 min on each side
        "Low": (0, 0),         # no buffer
    }

    def __init__(self, prisma_client, buffers: Optional[dict] = None):
        ...

    async def is_blackout_window(
        self,
        at: Optional[datetime] = None,
        min_impact: str = "High",
    ) -> bool:
        """True if `at` (default: now) falls within a High-or-above impact blackout."""
        ...

    async def get_active_blackouts(
        self,
        at: Optional[datetime] = None,
        within_hours: int = 24,
    ) -> list[BlackoutWindow]:
        """All blackouts that are active or upcoming within `within_hours` of `at`."""
        ...

    async def next_blackout_start(
        self,
        after: Optional[datetime] = None,
        min_impact: str = "High",
    ) -> Optional[datetime]:
        """When does the next High+ blackout begin? Used to plan exits before events."""
        ...
```

### 4.7 EarningsService

Populates `EarningsCalendar` from yfinance. Provides earnings lookups for strategies.

```python
# scripts/libs_py/strategy_engine/services/earnings_service.py

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass
class EarningsAnnouncement:
    """A scheduled earnings announcement."""
    ticker: str
    earnings_date: datetime
    before_market: bool
    confirmed: bool


class EarningsService:
    """Manages earnings calendar via yfinance + EarningsCalendar table.

    Populated by a weekly cron job (`fetch_upcoming_all`).
    """

    def __init__(self, prisma_client):
        ...

    async def get_next_earnings(self, ticker: str) -> Optional[EarningsAnnouncement]:
        """Next upcoming earnings announcement for ticker, or None if not scheduled."""
        ...

    async def is_earnings_within(self, ticker: str, days: int) -> bool:
        """True if ticker has earnings within `days` of now."""
        ...

    async def days_to_earnings(self, ticker: str) -> Optional[int]:
        """Calendar days from today to next earnings. None if not scheduled."""
        ...

    async def fetch_upcoming_all(self, tickers: list[str]) -> int:
        """Pull upcoming earnings from yfinance for each ticker, upsert into EarningsCalendar.

        Returns count of rows upserted. Called weekly by a cron job.
        Robust to yfinance flakiness — partial failures are logged but don't raise.
        """
        ...
```

### 4.8 HoldingsService

CRUD over `Holding` table. Used by income CC strategy.

```python
# scripts/libs_py/strategy_engine/services/holdings_service.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class HoldingInfo:
    ticker: str
    shares: int
    cost_basis: float
    acquired_at: datetime


class HoldingsService:
    """CRUD over Holding table.

    Seeded manually via seed_data.py from config.yaml `holdings` section.
    Not synced from Schwab (these are paper positions).
    """

    def __init__(self, prisma_client):
        ...

    async def get_holding(self, ticker: str) -> Optional[HoldingInfo]:
        """Returns the user's current paper position in ticker, or None."""
        ...

    async def get_all_holdings(self) -> list[HoldingInfo]:
        """All current holdings."""
        ...

    async def covered_call_capacity(self, ticker: str) -> int:
        """How many CC contracts can be sold against current holdings (shares // 100)."""
        ...

    async def adjust_for_assignment(self, ticker: str, shares_delta: int) -> None:
        """Update shares when a wheel CSP gets assigned or CC gets called away.

        Wheel strategy: increment shares by 100 when assigned.
        Wheel/Income CC: decrement by 100 when called away.

        Cost basis is updated to weighted average for additions; remains for removals.
        """
        ...
```

### 4.9 SizingService

Computes contract count for a signal given the strategy's risk parameters and the account's capital.

```python
# scripts/libs_py/strategy_engine/services/sizing_service.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class SizingDecision:
    """Result of a sizing computation."""
    contracts: int                  # 0 = signal rejected due to risk
    max_risk_dollars: float
    capital_committed: float
    rejection_reason: Optional[str] = None  # if contracts=0


class SizingService:
    """Computes position size, respecting:
       - The strategy's per-trade risk band ($100-$500 for this user)
       - The account's currentBalance (capital silo)
       - The trade_policies caps (volatility-adjusted)
    """

    def __init__(self, prisma_client, trade_policies_module):
        ...

    async def size_position(
        self,
        account_id: str,
        max_risk_per_contract: float,
        max_capital_per_contract: float,
        target_risk_dollars: float = 400.0,    # user's target: $100-$500/trade
        max_risk_dollars: float = 500.0,
    ) -> SizingDecision:
        """Compute number of contracts.

        Algorithm:
        1. Pull account.currentBalance for the silo.
        2. Apply trade_policies caps (drawdown, vol-adjusted).
        3. Compute n = min(target_risk_dollars / max_risk_per_contract, 1) for now.
           (Single-contract sizing for v1; multi-contract scaling deferred.)
        4. Verify n * max_capital_per_contract <= account.currentBalance.
        5. Return SizingDecision with n.

        Currently always returns 1 contract if risk fits, else 0.
        """
        ...
```

### 4.10 LegQuoteService

Re-quotes legs of an open trade for mark-to-market. Wraps BrokerService with leg-level convenience.

```python
# scripts/libs_py/strategy_engine/services/leg_quote_service.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class LegMtm:
    """Mark-to-market of a single leg right now."""
    leg_id: str
    symbol: str
    bid: float
    ask: float
    mid: float
    iv: Optional[float]
    delta: Optional[float]
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]


@dataclass
class TradeMtm:
    """Aggregate MTM for a trade."""
    trade_id: str
    underlying_px: float
    legs: list[LegMtm]
    net_value: float                # value to close (positive = costs to close, negative = receive credit)
    unrealized_pnl: float           # pnl since open
    legs_by_symbol: dict[str, LegMtm]


class LegQuoteService:
    """Re-quotes all legs of an open trade and computes current MTM.

    Used by paper_exec's MTM loop every tick.
    """

    def __init__(self, broker_service):
        ...

    async def mtm_trade(self, trade) -> TradeMtm:
        """Mark a trade to market right now.

        trade: a Trade row with eagerly-loaded legs (TradeLeg[]).
        Re-quotes every leg via BrokerService.
        Computes net_value as the dollar cost to close the combo right now.

        For credit trades (open at net credit): unrealized_pnl = open_credit - current_cost_to_close
        For debit trades (open at net debit): unrealized_pnl = current_close_value - debit_paid
        Stock legs are valued at current spot.
        """
        ...
```

### 4.11 Service dependency graph

```
BrokerService          (depends on existing ezoptionsschwab + options_fetcher)
RegimeService          (depends on Prisma)
ExpectedMoveService    (depends on Prisma)
IvService              (depends on Prisma + Dolt adapter)
IctService             (depends on parquet loader + pa + sessions + nwog_ndog)
CalendarService        (depends on Prisma)
EarningsService        (depends on Prisma + yfinance)
HoldingsService        (depends on Prisma)
SizingService          (depends on Prisma + trade_policies)
LegQuoteService        (depends on BrokerService)
```

All services are independently testable. Strategies depend on a subset; the engine wires them up at startup.

---

## 5. Strategy Framework

### 5.1 Strategy lifecycle

Each strategy implements a standard interface. The engine calls these methods on a schedule.

```
                 ┌─────────────────────────────────────┐
                 │  Engine tick (every 60s / 5m / 1d)  │
                 └─────────────────────────────────────┘
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐
        │  Strategy.scan() │    │  Strategy.manage() │
        │  (entries)       │    │  (exits)          │
        └──────────────────┘    └──────────────────┘
                  │                       │
                  ▼                       ▼
              [Signal]              [ManageAction]
                  │                       │
                  ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐
        │  paper_exec.open │    │  paper_exec.close│
        └──────────────────┘    └──────────────────┘
                  │                       │
                  ▼                       ▼
              Trade + TradeLegs     Trade updated
              SignalNearMiss for    Account.balance updated
              rejections logged
```

### 5.2 Core dataclasses

```python
# scripts/libs_py/strategy_engine/strategies/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


@dataclass
class LegSpec:
    """A single leg the strategy wants to open."""
    option_type: str                # "CALL" | "PUT" | "STOCK"
    side: str                       # "LONG" | "SHORT"
    strike: Optional[float]         # None for STOCK
    expiry: Optional[date]          # None for STOCK
    quantity: int

    # Populated by strategy from chain lookup
    symbol: Optional[str] = None
    mid: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None


@dataclass
class Signal:
    """A complete trade idea to be paper-executed."""
    research_strategy_id: str       # links to ResearchStrategy.id (the parameterized variant)
    strategy_category: str          # "WHEEL" | "ZERO_DTE_PCS" | etc. (links to Strategy.name)
    underlying: str
    legs: list[LegSpec]

    # Sizing inputs
    max_risk_per_contract: float
    max_capital_per_contract: float

    # Exit rule parameters (passed through to manage())
    profit_target_pct: float = 0.5
    stop_loss_mult: float = 2.0
    time_stop_minutes_before_close: Optional[int] = None
    time_stop_dte: Optional[int] = None
    roll_at_dte: Optional[int] = None

    # Context features at entry (logged into Trade.metadata)
    entry_features: dict = field(default_factory=dict)

    # Human-readable
    notes: str = ""


@dataclass
class NearMiss:
    """A signal that almost fired but failed a filter."""
    research_strategy_id: str
    ticker: str
    underlying_px: float
    failing_filter: str
    filter_value: Optional[float]
    filter_threshold: Optional[float]
    context: dict


@dataclass
class ManageAction:
    """Decision returned by Strategy.manage() for an open trade."""
    close: bool
    reason: Optional[str] = None    # "TARGET" | "STOP" | "EOD" | "REGIME_SHIFT" | "ASSIGNMENT" | "ROLL" | "SIGNAL"
    roll_to: Optional[dict] = None  # for rolls: new strike/expiry params


@dataclass
class StrategyParams:
    """Parameter set for one strategy variant.

    Each row in ResearchStrategy maps to one StrategyParams instance.
    Loaded from config.yaml at startup.
    """
    research_strategy_id: str
    name: str                       # e.g. "NVDA_WHEEL_30D_45DTE"
    category: str                   # e.g. "WHEEL"
    underlying: str
    account_id: str                 # the capital silo
    params: dict                    # strategy-specific knobs
    enabled: bool = True
```

### 5.3 Strategy abstract base

```python
class Strategy(ABC):
    """Abstract base for all strategies.

    Each concrete strategy:
    - Implements scan() and manage()
    - Declares which services it needs in __init__
    - Logs filter values to Signal.entry_features for every scan
    - Logs near-misses for every filter that fails

    Conventions:
    - scan() is called on the strategy's cadence (see config.yaml).
    - manage() is called every tick when at least one trade is open.
    - scan() should be idempotent: calling it twice in a tick should
      produce the same signals (or none on the second call if one was
      just opened).
    """

    def __init__(self, params: StrategyParams, services: dict):
        """
        Args:
            params: parameters for this variant (loaded from ResearchStrategy + config.yaml).
            services: dict of service instances:
                {
                    "broker": BrokerService,
                    "regime": RegimeService,
                    "em": ExpectedMoveService,
                    "iv": IvService,
                    "ict": IctService,
                    "calendar": CalendarService,
                    "earnings": EarningsService,
                    "holdings": HoldingsService,
                    "sizing": SizingService,
                    "leg_quote": LegQuoteService,
                    "prisma": PrismaClient,
                    "near_miss_log": NearMissLogger,
                }
        """
        self.params = params
        self.s = services
        self.name = params.name
        self.underlying = params.underlying
        self.p = params.params      # short alias for params dict

    @abstractmethod
    async def scan(self, now: datetime) -> list[Signal]:
        """Evaluate entry conditions; return zero or more signals.

        For every filter that fails, call self._log_near_miss().
        For every signal that fires, populate signal.entry_features with
        all observed values.
        """
        ...

    @abstractmethod
    async def manage(
        self,
        trade,                      # Trade row with eagerly-loaded legs and recent snapshots
        current_mtm,                # TradeMtm from leg_quote_service
        now: datetime,
    ) -> ManageAction:
        """Evaluate exit conditions for an open trade.

        Default implementations of common exits (profit target, stop loss, time stop)
        are provided as helper methods; concrete strategies override only what's
        strategy-specific.
        """
        ...

    # ─── Common helper methods ─────────────────────────────────────────

    async def _log_near_miss(
        self,
        ticker: str,
        underlying_px: float,
        failing_filter: str,
        filter_value: Optional[float],
        filter_threshold: Optional[float],
        context: dict,
    ) -> None:
        """Record a near-miss via the near_miss_log service."""
        ...

    async def _check_profit_target(
        self,
        trade,
        current_mtm,
        target_pct: float = 0.5,
    ) -> Optional[ManageAction]:
        """Standard 50% profit target for credit trades.

        Returns ManageAction(close=True, reason="TARGET") or None.
        """
        ...

    async def _check_stop_loss(
        self,
        trade,
        current_mtm,
        stop_mult: float = 2.0,
    ) -> Optional[ManageAction]:
        """Standard stop: 2x credit received."""
        ...

    async def _check_time_stop(
        self,
        trade,
        now: datetime,
        flat_by_minutes_before_close: int = 30,
    ) -> Optional[ManageAction]:
        """Force close N minutes before market close (for 0DTE strategies)."""
        ...

    async def _check_dte_time_stop(
        self,
        trade,
        now: datetime,
        close_at_dte: int = 21,
    ) -> Optional[ManageAction]:
        """For longer-dated trades: close at N DTE (the Tastytrade 21-DTE rule)."""
        ...

    async def _check_regime_invalidation(
        self,
        trade,
        now: datetime,
        require_positive_gamma: bool = True,
    ) -> Optional[ManageAction]:
        """If trade required positive gamma at entry and regime has shifted, close."""
        ...
```

### 5.4 The "log every filter" convention

Every strategy follows this pattern in `scan()`:

```python
async def scan(self, now):
    spot_quote = await self.s["broker"].get_stock_quote(self.underlying)
    spot = spot_quote.last
    signals = []

    # Filter 1: GEX regime
    regime = await self.s["regime"].get_current_regime(self.underlying)
    if not regime or regime.gex_regime != "POSITIVE":
        await self._log_near_miss(
            self.underlying, spot,
            "not_positive_gamma",
            filter_value=regime.total_gex if regime else None,
            filter_threshold=0.0,
            context={"regime_label": regime.regime_label if regime else None},
        )
        return signals

    # Filter 2: IV rank
    iv_rank = await self.s["iv"].get_iv_rank(self.underlying)
    if iv_rank is not None and iv_rank < self.p["min_iv_rank"]:
        await self._log_near_miss(
            self.underlying, spot,
            "iv_rank_below_threshold",
            filter_value=iv_rank,
            filter_threshold=self.p["min_iv_rank"],
            context={"iv_rank": iv_rank},
        )
        return signals

    # ... more filters ...

    # All filters passed: build the signal
    signal = Signal(
        research_strategy_id=self.params.research_strategy_id,
        strategy_category=self.params.category,
        underlying=self.underlying,
        legs=[...],
        # ... sizing/exit params ...
        entry_features={
            "iv_rank": iv_rank,
            "gex_regime": regime.gex_regime,
            "zero_gamma_distance_pct": regime.distance_to_zero_gamma_pct,
            "vix_skew_premium": regime.volatility_skew_premium,
            # ... every value observed during scan ...
        },
        notes=f"Entry: iv_rank={iv_rank:.1f}, gex={regime.gex_regime}",
    )
    return [signal]
```

**The entry_features dict is the per-trade feature ledger** used by analytics to compute "win rate when iv_rank > X" type breakdowns post-hoc. Every observed filter value goes in, even ones the strategy doesn't filter on.

---

## 6. Engine Orchestration

### 6.1 The main loop

```python
# scripts/libs_py/strategy_engine/engine.py

from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Optional

ET = ZoneInfo("America/New_York")


class StrategyEngine:
    """Main orchestration loop.

    Started by runner.py with APScheduler-managed cadences:
        - index_tick(): every 60s during RTH
        - stock_tick(): every 5min during RTH
        - daily_scan(): once at 10:00 ET on trading days
    """

    def __init__(
        self,
        strategies_index: list,     # Strategy instances for SPY/SPX/QQQ/IWM
        strategies_stock: list,     # Strategy instances for NVDA/TSLA/AAPL/etc.
        strategies_daily: list,     # Wheel CSP scans, earnings strangle scans
        paper_exec,                 # PaperExecutor instance
        prisma,
        logger,
    ):
        ...

    async def index_tick(self) -> None:
        """Called every 60s during RTH for index strategies.

        Steps:
        1. Check if market is open (skip otherwise).
        2. Mark-to-market all currently-open trades for index underlyings.
        3. For each strategies_index strategy, call scan() and process signals.
        4. For each open trade, call its strategy's manage() and process actions.
        """
        ...

    async def stock_tick(self) -> None:
        """Called every 5 min during RTH for stock strategies. Same logic as index_tick."""
        ...

    async def daily_scan(self) -> None:
        """Called once at 10:00 ET. Runs daily strategies (Wheel CSP scans, earnings scans).

        These don't need intraday MTM — wheel/CC positions are checked once per day.
        """
        ...

    async def _is_market_open(self, now: datetime) -> bool:
        """True iff now is within RTH 9:30-16:00 ET on a non-holiday weekday."""
        ...

    async def _process_signal(self, signal) -> None:
        """Pass a fired signal through sizing and paper execution."""
        ...

    async def _process_open_trades(
        self,
        strategy_class_filter: Optional[type] = None,
    ) -> None:
        """For every open trade matching the class filter (or all if None):
        1. Re-quote legs via LegQuoteService.
        2. Snapshot to QuoteSnapshot.
        3. Call the strategy's manage() and execute any close action.
        """
        ...
```

### 6.2 The runner

```python
# scripts/libs_py/strategy_engine/runner.py

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import yaml


async def main():
    """Entry point.

    1. Load config.yaml.
    2. Initialize Prisma client, Dolt adapter, parquet loader.
    3. Instantiate all services.
    4. Load ResearchStrategy rows from Prisma, instantiate corresponding
       Strategy classes with their params.
    5. Configure APScheduler:
         - index_tick every 60s during 9:30-16:00 ET
         - stock_tick every 5min during 9:30-16:00 ET
         - daily_scan at 10:00 ET
         - earnings calendar refresh weekly (Sunday 18:00 ET)
         - analytics rollup daily (16:30 ET)
         - weekly review (Sunday 17:00 ET)
         - maintenance/pruning daily (03:00 ET)
    6. Start scheduler, run until SIGINT.
    """
    ...


if __name__ == "__main__":
    asyncio.run(main())
```

### 6.3 config.yaml structure

```yaml
# scripts/libs_py/strategy_engine/config.yaml

engine:
  timezone: America/New_York
  tick_cadences:
    index_seconds: 60
    stock_seconds: 300
    daily_time: "10:00"
  log_level: INFO
  log_file: ~/strategy_engine.log

prisma:
  url: file:./web/prisma/dev.db

dolt:
  path: ./data/options/options/

accounts:
  # One Account per ResearchStrategy variant. Created by seed_data.py.
  default_initial_balance: 25000.0
  group_name: "Strategy Engine Silos"

holdings:
  # Manually declared paper holdings for income CC strategy.
  - ticker: TSLA
    shares: 200
    cost_basis: 240.00
    acquired_at: 2024-01-15
  - ticker: GOOGL
    shares: 100
    cost_basis: 165.00
    acquired_at: 2024-03-01
  - ticker: RIVN
    shares: 500
    cost_basis: 11.50
    acquired_at: 2024-06-10

strategies:
  wheel:
    enabled: true
    underlyings: [NVDA, TSLA, AAPL, GOOGL, MSFT, AMZN]
    variants:
      - name_suffix: "30D_45DTE"
        params:
          short_delta: 0.30
          dte: 45
          min_iv_rank: 30
          target_pct: 0.5
          roll_at_dte: 21
          min_premium_pct_of_strike: 0.01
      - name_suffix: "20D_45DTE"
        params:
          short_delta: 0.20
          dte: 45
          min_iv_rank: 30
          target_pct: 0.5
          roll_at_dte: 21
          min_premium_pct_of_strike: 0.01
      - name_suffix: "30D_7DTE"
        params:
          short_delta: 0.30
          dte: 7
          min_iv_rank: 25
          target_pct: 0.5
          roll_at_dte: 2
          min_premium_pct_of_strike: 0.005

  zero_dte_pcs:
    enabled: true
    underlyings: [SPY, SPX]
    variants:
      - name_suffix: "10D_5W"
        params:
          short_delta: 0.10
          width: 5.0
          min_credit: 0.10
          target_pct: 0.5
          stop_mult: 2.0
          require_positive_gamma: true
          min_minutes_in_regime: 30
          entry_time_start: "10:00"
          entry_time_end: "13:30"
          flat_by_minutes_before_close: 30
          max_vix: 25
          max_vix_pct_change: 10
          require_ict_confluence: false
      - name_suffix: "16D_5W"
        params:
          short_delta: 0.16
          width: 5.0
          min_credit: 0.15
          target_pct: 0.5
          stop_mult: 2.0
          require_positive_gamma: true
          min_minutes_in_regime: 30
          entry_time_start: "10:00"
          entry_time_end: "13:30"
          flat_by_minutes_before_close: 30
          max_vix: 25
          max_vix_pct_change: 10
          require_ict_confluence: false
      - name_suffix: "10D_5W_NOGEX"
        params:
          short_delta: 0.10
          width: 5.0
          min_credit: 0.10
          target_pct: 0.5
          stop_mult: 2.0
          require_positive_gamma: false   # CONTROL VARIANT — no GEX filter
          min_minutes_in_regime: 0
          entry_time_start: "10:00"
          entry_time_end: "13:30"
          flat_by_minutes_before_close: 30
          max_vix: 25
          max_vix_pct_change: 10
      - name_suffix: "10D_5W_ICT"
        params:
          short_delta: 0.10
          width: 5.0
          min_credit: 0.10
          target_pct: 0.5
          stop_mult: 2.0
          require_positive_gamma: true
          min_minutes_in_regime: 30
          entry_time_start: "10:00"
          entry_time_end: "13:30"
          flat_by_minutes_before_close: 30
          max_vix: 25
          max_vix_pct_change: 10
          require_ict_confluence: true    # ICT VARIANT
          ict_timeframe: "5m"

  long_dte_credit:
    enabled: true
    underlyings: [SPY, NVDA, TSLA, IWM]
    variants:
      - name_suffix: "16D_45DTE"
        params:
          short_delta: 0.16
          width_pct: 0.02         # 2% of spot
          dte: 45
          min_iv_rank: 35
          target_pct: 0.5
          stop_mult: 2.0
          roll_at_dte: 21

  mean_reversion_em:
    enabled: true
    underlyings: [SPY, SPX]
    variants:
      - name_suffix: "1SD_TOUCH"
        params:
          touch_sd_threshold: 1.0
          width: 5.0
          require_positive_gamma: true
          min_minutes_to_close: 90
          target_pct: 0.5
          stop_mult: 1.5
          max_vix: 20
          entry_time_start: "10:30"
          entry_time_end: "14:30"

  wall_break:
    enabled: true
    underlyings: [SPY, SPX]
    variants:
      - name_suffix: "BREAKOUT_DEBIT"
        params:
          wall_proximity_pct: 0.003       # within 0.3%
          require_dex_confirmation: true
          volume_multiple: 1.5
          width: 2.0
          dte: 0
          target_pct: 0.75
          stop_pct: 0.5
          time_stop_minutes: 45
          max_vix: 22
          entry_time_start: "10:00"
          entry_time_end: "15:00"

  income_cc:
    enabled: true
    underlyings: [GOOGL, TSLA, RIVN]
    variants:
      - name_suffix: "TIER_BY_TICKER"
        # Per-ticker rules baked in; see strategy implementation.
        params:
          target_pct: 0.7
          earnings_blackout_days: 2

  earnings_strangle:
    enabled: true
    underlyings: [NVDA, TSLA, AAPL, GOOGL]
    variants:
      - name_suffix: "30D_5D_BEFORE"
        params:
          days_before_earnings: 5
          close_days_before_earnings: 1
          target_call_delta: 0.30
          target_put_delta: 0.30
          max_iv_percentile: 50
          max_debit: 5.0
          target_pct: 0.5
          stop_pct: 0.3
```

This config is the **single source of truth for parameters**. Modifying a parameter requires editing the YAML and re-running `seed_data.py --update`.

---

## 7. Paper Execution & Mark-to-Market

### 7.1 PaperExecutor

```python
# scripts/libs_py/strategy_engine/paper_exec.py

from datetime import datetime
from typing import Optional


class PaperExecutor:
    """Opens, marks, and closes paper trades.

    All trades are stored as Trade rows with originalSource="strategy_engine".
    Capital silos are real Account rows; their currentBalance updates on each close.
    """

    def __init__(self, prisma, sizing_service, leg_quote_service, logger):
        ...

    async def open_signal(self, signal, account_id: str) -> Optional[str]:
        """Open a paper trade from a signal.

        Steps:
        1. Check capital silo via SizingService. If 0 contracts, abandon.
        2. Compute net credit/debit from signal.legs (already populated with mids).
        3. Verify no duplicate open position for this research_strategy_id (one-at-a-time policy).
        4. Create Trade row:
            - accountId = account_id (the silo)
            - strategyId = lookup from signal.strategy_category
            - playbookId = lookup matching playbook
            - ticker = signal.underlying
            - entryDate = now
            - entryPrice = net credit/debit per share
            - quantity = contracts * (multiplier 100 for options)
            - direction = "CREDIT" or "DEBIT" or "STOCK_LONG"
            - status = "OPEN"
            - orderType = "MARKET" (we use mid as fill)
            - risk = max_risk_per_contract * contracts
            - originalSource = "strategy_engine"
            - notes = signal.notes
            - metadata = JSON({
                research_strategy_id: signal.research_strategy_id,
                ...signal.entry_features,
                exit_rules: { target_pct, stop_mult, ... },
                fill_assumption: "mid",
              })
        5. For each leg in signal.legs, create TradeLeg row with open* fields.
        6. Create MarketCondition row (VIX, VVIX, ATR, trend, session, volume).
        7. Return trade.id.
        """
        ...

    async def mark_to_market(self, trade_id: str) -> None:
        """Re-quote all legs, write QuoteSnapshot, update Trade.mae/mfe."""
        ...

    async def close_trade(
        self,
        trade_id: str,
        reason: str,                # "TARGET" | "STOP" | "EOD" | "REGIME_SHIFT" | etc.
        current_mtm,
        now: datetime,
    ) -> None:
        """Close a trade.

        Steps:
        1. Update Trade row:
            - status = "CLOSED"
            - exitDate = now
            - exitPrice = current_mtm.net_value per share
            - pnl = current_mtm.unrealized_pnl
            - duration = (exitDate - entryDate).total_seconds()
            - notes += f" | closed: {reason}"
            - metadata.exit_reason = reason
        2. For each leg, update closePrice/closeBid/closeAsk/closeIv/closeDelta with current values.
        3. Compute per-leg pnl and write to TradeLeg.legPnl.
        4. Update Account.currentBalance by + trade.pnl.
        5. If reason in ("EXPIRY_ITM", "ASSIGNMENT"): mark TradeLeg.assigned=true for short legs.
        6. If reason in ("EXPIRY_OTM"): mark TradeLeg.expiredOtm=true.
        """
        ...

    async def handle_assignment(self, trade_id: str) -> None:
        """For wheel strategy: when a CSP expires ITM, update HoldingsService
        (or wheel-internal share state in Trade.metadata) and mark the trade closed
        with reason='ASSIGNMENT'.
        """
        ...

    async def handle_called_away(self, trade_id: str) -> None:
        """For CC: when ITM at expiry, called away. Update HoldingsService."""
        ...

    async def list_open_trades(
        self,
        research_strategy_id: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> list:
        """Open trades, optionally filtered."""
        ...
```

### 7.2 The MTM tick

Every engine tick, for every open trade:

```
1. paper_exec.mark_to_market(trade.id):
   - LegQuoteService.mtm_trade(trade) → TradeMtm
   - Write QuoteSnapshot row with:
     - underlyingPx, netValue, unrealizedPnl
     - legPrices = JSON of all leg quotes
     - vix, gexRegime, zeroGamma from latest snapshots
   - If unrealized_pnl < trade.mae: update Trade.mae
   - If unrealized_pnl > trade.mfe: update Trade.mfe

2. strategy.manage(trade, current_mtm, now) → ManageAction:
   - If close == True:
       paper_exec.close_trade(trade.id, action.reason, current_mtm, now)
```

### 7.3 The single-position-per-variant rule (v1)

In v1, each ResearchStrategy variant can have **at most one open trade at a time**. This simplifies sizing and analytics.

- If `scan()` returns a signal but a trade already exists for this variant, the signal is silently dropped (logged as `duplicate_open_position`).
- For wheels: the variant transitions through states (CSP open → assigned → CC open → called away → CSP open). At any moment exactly one position is "open" for the variant.

Future versions may allow stacking (e.g. multiple 0DTE PCS on the same day with different deltas). Out of scope for v1.

### 7.4 Fill assumption

All paper trades fill at the mid of bid/ask at the moment of signal. This is documented in `Trade.metadata.fill_assumption = "mid"`.

**Known limitation:** real fills are typically worse than mid (especially on wide-spread options). The user's plan to manually paper-trade ~20 signals in Schwab's paper account validates whether the mid-fill assumption needs adjustment. If empirical fills are systematically $0.02-0.05 worse than mid, we'll add a slippage adjustment in v1.1.

---

## 8. The Seven Strategies

Each strategy below is specified with: hypothesis, entry rules, exit rules, sizing, features logged, variants, and the corresponding Python class skeleton.

---

### 8.1 Strategy 1: The Wheel

**Category name in Strategy table:** `WHEEL`

**Hypothesis:** on quality names with positive long-term drift, systematically selling CSPs (and CCs after assignment) collects premium that compounds faster than buy-and-hold while assignment is acceptable because we'd own the stock anyway.

**State machine.** A wheel for a given (ticker, variant) cycles through:
```
CASH ──CSP sold──► SHORT_PUT ──expires OTM──► CASH
                       │
                       └──ITM at expiry──► LONG_STOCK ──CC sold──► SHORT_CALL
                                                                          │
                                                              ─called away┘
                                                              ─expires OTM─► LONG_STOCK
```

State is stored in `Trade.metadata.wheel_state` and the ticker's `Holding` row.

**Entry rules — CSP leg (CASH → SHORT_PUT):**

| # | Filter | Threshold (default variant) | Logged value | Skipped on |
|---|--------|------------------------------|--------------|------------|
| 1 | Underlying in approved list | `params.underlying` | — | Never |
| 2 | Current state == CASH | wheel_state | — | Never |
| 3 | Spot above 50-day SMA | computed from parquet 1d | spot, sma50 | Always |
| 4 | IV rank > min_iv_rank | 30 | iv_rank | When iv_rank unavailable |
| 5 | No earnings within `dte + 5` days | from EarningsCalendar | days_to_earnings | When no earnings scheduled |
| 6 | Find target-delta put at target DTE | `short_delta=0.30, dte=45` | strike, delta_achieved | — |
| 7 | Premium / strike ≥ min_premium_pct | 1.0% | premium_pct | — |

**Exit rules — CSP leg:**

| Condition | Action |
|-----------|--------|
| Buyback at 50% of credit | Close, reason="TARGET" |
| DTE ≤ `roll_at_dte` (default 21) AND not at target | Roll: close current, open new at DTE=45, strike=current-1 |
| Expires OTM (held to expiry) | Close, reason="EXPIRY_OTM"; state → CASH |
| Expires ITM | Close, reason="ASSIGNMENT"; state → LONG_STOCK; Holdings.shares += 100 |

**Entry rules — CC leg (LONG_STOCK → SHORT_CALL):**

| # | Filter | Threshold | Logged | Skipped on |
|---|--------|-----------|--------|------------|
| 1 | Current state == LONG_STOCK | wheel_state | — | Never |
| 2 | No CC currently open for this variant | — | — | Never |
| 3 | No earnings within DTE | — | — | When no earnings scheduled |
| 4 | Find target-delta call at target DTE | `0.30 / 45` | strike, delta | — |
| 5 | Strike ≥ assignment_price (or breakeven if accumulated premium) | tracked in metadata | strike, breakeven | When stuck condition |

**The "stuck" rule (decided in design phase):** if no call strike both above breakeven AND at ≥0.15 delta is available, the engine logs `STUCK_WAITING` near-miss and waits. No CC is sold. State remains LONG_STOCK until either spot recovers or premium can be sold below breakeven at delta ≤ 0.15.

**Exit rules — CC leg:**

| Condition | Action |
|-----------|--------|
| Buyback at 50% | Close, reason="TARGET" |
| DTE ≤ roll_at_dte AND ITM | Roll up and out for credit if possible |
| Expires OTM | Close, reason="EXPIRY_OTM"; state → LONG_STOCK |
| Expires ITM | Close, reason="CALLED_AWAY"; state → CASH; Holdings.shares -= 100 |

**Features logged at every state transition** (into `Trade.metadata`):

- `iv_rank`, `iv_at_entry`, `iv_at_exit`
- `delta_at_entry`, `delta_at_exit`
- `days_held`
- `premium_collected_this_cycle`
- `cumulative_premium_collected` (across the full wheel cycle)
- `buy_and_hold_benchmark`: value of 100 shares from first CSP date to today
- `wheel_state` (before and after)

**Variants (3 per ticker × 6 tickers = 18 variants):**

| Variant suffix | short_delta | dte | min_iv_rank |
|----------------|-------------|-----|-------------|
| `30D_45DTE` | 0.30 | 45 | 30 |
| `20D_45DTE` | 0.20 | 45 | 30 |
| `30D_7DTE` | 0.30 | 7 | 25 |

**Python class:**

```python
# scripts/libs_py/strategy_engine/strategies/wheel.py

from datetime import datetime, date, timedelta
from .base import Strategy, Signal, LegSpec, ManageAction


class WheelStrategy(Strategy):
    """The wheel: CSP → assigned → CC → called-away → CSP."""

    CATEGORY = "WHEEL"

    async def scan(self, now: datetime) -> list[Signal]:
        """Scan for next wheel action based on current state.

        State stored in: latest closed Trade.metadata.wheel_state for this variant,
        plus Holdings.shares for the ticker.

        Decision tree:
          state=CASH       → try to open CSP
          state=LONG_STOCK → try to open CC
          state=*_OPEN     → no scan (managed by manage())
        """
        ...

    async def manage(self, trade, current_mtm, now: datetime) -> ManageAction:
        """Manage open CSP or CC.

        Calls _check_profit_target with target_pct=0.5.
        Checks DTE roll trigger.
        Checks expiry: if today is expiry day and after 15:30 ET, evaluate ITM/OTM.
        """
        ...

    async def _scan_csp(self, now: datetime) -> list[Signal]:
        """Build a CSP signal if conditions met."""
        ...

    async def _scan_cc(self, now: datetime) -> list[Signal]:
        """Build a CC signal if conditions met (and not stuck)."""
        ...

    async def _get_wheel_state(self) -> str:
        """Read current state from latest Trade.metadata + Holdings."""
        ...

    async def _compute_breakeven(self) -> float:
        """Cost basis adjusted for cumulative premium collected this wheel cycle."""
        ...
```

**What you'll learn from this strategy:**
- Whether wheels beat buy-and-hold on each name over the test period.
- How often assignment happens at each delta.
- How long "stuck" periods last and what they cost.
- Whether 7-DTE or 45-DTE compounds better.
- The true dollar cost of being long during drawdowns (via buy_and_hold_benchmark comparison).

---

### 8.2 Strategy 2: 0DTE Put Credit Spread

**Category name in Strategy table:** `ZERO_DTE_PCS`

**Hypothesis:** premium decays fast in the last 6 hours of life on indices/large-caps when dealers are long gamma in the upper part of the range. Selling OTM puts at 0.10-0.20 delta during positive-gamma regimes, with appropriate exits, produces a high win-rate income stream.

**Cadence:** index_tick (60 sec).

**Entry rules:**

| # | Filter | Threshold (default variant) | Logged | Skip if |
|---|--------|------------------------------|--------|---------|
| 1 | Underlying in [SPY, SPX] | — | — | Never |
| 2 | 0DTE expiry exists today | — | — | Weekend / holiday |
| 3 | Time within entry window | 10:00 - 13:30 ET | time_of_day | — |
| 4 | VIX < max_vix | 25 | vix | Always |
| 5 | VIX % change today < max_vix_pct_change | 10% | vix_pct_change | Always |
| 6 | No High-impact blackout (FOMC/CPI/NFP) | from CalendarService | next_blackout_at | — |
| 7 | Spot > zero-gamma | from RegimeService | spot, zero_gamma | When zero_gamma unavailable |
| 8 | Spot stable above zero-gamma for ≥ min_minutes_in_regime | 30 min | minutes_in_regime | — |
| 9 | Find short put at target_delta | 0.10 | short_strike, short_delta | — |
| 10 | Short strike below today's -1SD EM boundary | from ExpectedMoveService | em_distance_sd | — |
| 11 | Short strike below nearest large positive GEX strike below spot | from RegimeService | wall_below_strike | — |
| 12 | Long put exists at strike = short - width | width=5 (SPY), 50 (SPX) | long_strike | — |
| 13 | Net credit ≥ min_credit | $0.10 | credit | — |
| 14 | (Optional) ICT confluence per variant | per variant | ict_context | When ICT variant disabled |

**Exit rules:**

| Condition | Action |
|-----------|--------|
| Buyback at 50% of credit | Close, reason="TARGET" |
| Cost-to-close ≥ stop_mult × credit | Close, reason="STOP" |
| Spot breaks below zero-gamma | Close, reason="REGIME_SHIFT" (immediate, regardless of P&L) |
| Time ≥ 15:30 ET | Close, reason="EOD" |
| Short strike touched (intraday) AND not yet stopped | Hold; continue monitoring |

**Features logged:**

- All filter values from above
- VIX intraday change
- Distance from short strike to spot (in $ and in SD)
- Distance from short strike to zero-gamma
- Distance from short strike to nearest positive GEX wall
- Minutes since regime stabilized
- ICT context (full IctContext serialized via `to_dict()`)
- volatility_skew_premium at entry
- Max underlying drift during life
- Whether short strike was touched intraday
- MAE, MFE
- Exit reason

**Variants (4 variants × 2 underlyings = 8 total):**

| Variant suffix | short_delta | width | require_positive_gamma | require_ict |
|----------------|-------------|-------|------------------------|-------------|
| `10D_5W` | 0.10 | 5 / 50 | yes | no |
| `16D_5W` | 0.16 | 5 / 50 | yes | no |
| `10D_5W_NOGEX` | 0.10 | 5 / 50 | **no** (CONTROL) | no |
| `10D_5W_ICT` | 0.10 | 5 / 50 | yes | **yes** |

**Python class:**

```python
# scripts/libs_py/strategy_engine/strategies/zero_dte_pcs.py

class ZeroDtePcsStrategy(Strategy):
    """0DTE put credit spread on SPY / SPX."""

    CATEGORY = "ZERO_DTE_PCS"

    async def scan(self, now: datetime) -> list[Signal]:
        """Evaluate entry filters and build signal if all pass."""
        ...

    async def manage(self, trade, current_mtm, now: datetime) -> ManageAction:
        """Exits: TARGET → STOP → REGIME_SHIFT → EOD."""
        ...
```

**What you'll learn:**
- Whether 60% win rate is achievable; at what delta.
- Whether GEX regime filter adds edge (compare `10D_5W` vs `10D_5W_NOGEX`).
- Whether ICT confluence adds edge (compare `10D_5W` vs `10D_5W_ICT`).
- Whether 0.10 or 0.16 delta is more capital-efficient.
- The cost of stops vs holding through.

---

### 8.3 Strategy 3: 45 DTE Credit Spreads

**Category name:** `LONG_DTE_CREDIT`

**Hypothesis:** baseline strategy — the classic Tastytrade premium-selling structure. Provides a comparison baseline to determine whether 0DTE actually beats it.

**Cadence:** daily_scan (10:00 ET).

**Entry rules:**

| # | Filter | Threshold | Logged |
|---|--------|-----------|--------|
| 1 | Underlying in [SPY, NVDA, TSLA, IWM] | — | — |
| 2 | No open position for this variant | — | — |
| 3 | IV rank ≥ min_iv_rank | 35 | iv_rank |
| 4 | No earnings within DTE + 5 days | — | days_to_earnings |
| 5 | Find expiry at target DTE ± 7 days | 45 DTE | expiry_used |
| 6 | Find short put at target_delta | 0.16 | short_strike, short_delta |
| 7 | Width = round(short_strike × width_pct) | 2% of spot | width |
| 8 | Net credit / max_risk ≥ 0.33 | rule of thumb | credit_to_risk_ratio |

**Exit rules:**

| Condition | Action |
|-----------|--------|
| Buyback at 50% | Close, reason="TARGET" |
| Cost-to-close ≥ stop_mult × credit | Close, reason="STOP" |
| DTE ≤ roll_at_dte (21) AND profitable | Close, reason="DTE_PROFITABLE" |
| DTE ≤ roll_at_dte AND not profitable | Roll out 30 days, adjust strike |
| Expires worthless | Close, reason="EXPIRY_OTM" |

**Variants (1 variant × 4 tickers = 4 total):**

| Variant suffix | short_delta | width_pct | dte | min_iv_rank |
|----------------|-------------|-----------|-----|-------------|
| `16D_45DTE` | 0.16 | 2.0% | 45 | 35 |

**IV rank caveat:** IWM has no Dolt IV data. For IWM the `min_iv_rank` filter is skipped and `iv_rank=None` is logged. The strategy fires without the IV filter for IWM — explicitly noted in metadata.

**Python class:**

```python
class LongDteCreditStrategy(Strategy):
    """45 DTE put credit spread, Tastytrade-style baseline."""
    CATEGORY = "LONG_DTE_CREDIT"

    async def scan(self, now): ...
    async def manage(self, trade, current_mtm, now): ...
    async def _roll(self, trade, now): ...
```

**What you'll learn:**
- Is 0DTE actually better than 45 DTE on the same underlyings (compare SPY here vs SPY in strategy 2)?
- Does IV rank filtering add edge?
- Do rolls work, or does taking the loss and re-entering produce better results?

---

### 8.4 Strategy 4: Mean Reversion to Expected Move

**Category name:** `MEAN_REVERSION_EM`

**Hypothesis:** when spot touches the 1SD daily expected move boundary intraday in a positive-gamma regime, dealer hedging creates mean-reversion pressure. Fading the touch with a tight credit spread produces a high win-rate setup.

**Cadence:** index_tick (60 sec).

**Entry rules:**

| # | Filter | Threshold | Logged |
|---|--------|-----------|--------|
| 1 | Underlying in [SPY, SPX] | — | — |
| 2 | No open position for this variant | — | — |
| 3 | Time within entry window | 10:30 - 14:30 ET | time_of_day |
| 4 | Minutes to market close ≥ min_minutes_to_close | 90 | min_to_close |
| 5 | VIX < max_vix | 20 | vix |
| 6 | Spot > zero-gamma (positive gamma) | required | gex_regime |
| 7 | Spot has touched ±1SD EM boundary in last 5 min | computed from snapshots | em_touch_side |
| 8 | Touch overshot by ≤ 0.5 × EM (not blown through) | em_overshoot_pct | — |
| 9 | Large positive GEX strike exists between spot and opposite EM boundary | from RegimeService | magnet_strike |
| 10 | Volatility skew premium not extreme | abs < 0.5 (configurable) | skew_premium |

**Strike selection:**
- If touched +1SD: sell call spread on upside. Short strike = 1 strike outside upper band.
- If touched -1SD: sell put spread on downside. Short strike = 1 strike outside lower band.
- Width: 5 (SPY) / 50 (SPX).

**Exit rules:**

| Condition | Action |
|-----------|--------|
| Buyback at 50% | Close, reason="TARGET" |
| Cost-to-close ≥ 1.5 × credit | Close, reason="STOP" (tighter than 0DTE PCS) |
| Spot crosses opposite EM boundary | Close, reason="OPPOSITE_BAND" |
| Spot breaks zero-gamma | Close, reason="REGIME_SHIFT" |
| Time ≥ 30 min before close | Close, reason="EOD" |

**Variants (1 × 2 = 2 total):** `1SD_TOUCH` × {SPY, SPX}.

```python
class MeanReversionEmStrategy(Strategy):
    CATEGORY = "MEAN_REVERSION_EM"

    async def scan(self, now): ...
    async def manage(self, trade, current_mtm, now): ...
    async def _detect_em_touch(self, ticker): ...
```

**What you'll learn:**
- Whether 1SD touches in positive gamma genuinely mean-revert.
- How much of the edge is timing (touch within last N minutes).
- Whether two-sided iron condors at the same time would work (future variant).

---

### 8.5 Strategy 5: GEX Wall Break Debit Spread

**Category name:** `WALL_BREAK`

**Hypothesis:** when spot breaks a major GEX strike with volume and DEX confirmation, dealer re-hedging accelerates a short-term continuation move. A tight debit spread in the breakout direction captures it.

**This is the only long-premium strategy in the lineup.** Lower win rate expected; needs occasional big winners.

**Cadence:** index_tick (60 sec).

**Entry rules:**

| # | Filter | Threshold | Logged |
|---|--------|-----------|--------|
| 1 | Underlying in [SPY, SPX] | — | — |
| 2 | No open position for this variant | — | — |
| 3 | Time within entry window | 10:00 - 15:00 ET | time_of_day |
| 4 | VIX < max_vix | 22 | vix |
| 5 | Spot within wall_proximity_pct of a major GEX strike (top 3) | 0.3% | wall_strike, distance_pct |
| 6 | DEX trending in breakout direction (last 30 min) | direction_match | dex_trend_dir |
| 7 | Volume in last 15 min ≥ volume_multiple × 15-min average | 1.5 | volume_ratio |
| 8 | No active blackout | — | — |

**Strike selection:**
- If breaking up: buy ATM/1-OTM call, sell 1-OTM/2-OTM call (debit call spread).
- If breaking down: mirror with puts.
- Width: 2 (SPY) / 20 (SPX). DTE: 0 (or 1 if 0 not available).

**Exit rules:**

| Condition | Action |
|-----------|--------|
| Position value ≥ target_pct × max profit | Close, reason="TARGET" (default 75%) |
| Position value ≤ stop_pct × debit | Close, reason="STOP" (default 50%) |
| Time elapsed ≥ time_stop_minutes from entry | Close, reason="TIME_STOP" (default 45 min) |
| Time ≥ 30 min before close | Close, reason="EOD" |

**Features logged:**
- Which wall was broken
- DEX trend strength
- Volume ratio
- Spot trajectory through wall
- Whether spot returned through wall (false breakout indicator)

**Variants (1 × 2 = 2 total):** `BREAKOUT_DEBIT` × {SPY, SPX}.

```python
class WallBreakStrategy(Strategy):
    CATEGORY = "WALL_BREAK"

    async def scan(self, now): ...
    async def manage(self, trade, current_mtm, now): ...
    async def _detect_wall_break(self, ticker): ...
    async def _get_dex_trend(self, ticker): ...
```

**What you'll learn:**
- Whether GEX walls actually produce tradeable breakouts (vs mean-reverting).
- The false-breakout rate.
- Whether long premium can be a winning strategy at this size.

---

### 8.6 Strategy 6: Income Covered Calls

**Category name:** `INCOME_CC`

**Hypothesis:** on positions you already own and intend to hold long-term, systematically selling far-OTM calls produces meaningful income without materially capping upside.

**Cadence:** daily_scan.

**Entry rules — per-ticker tier:**

For **GOOGL** (mega-cap, low realized vol):
- Sell call at delta 0.15-0.20
- DTE 30-45
- Strike ≥ 5% above current price
- IV rank > 25
- No CC currently open for this ticker
- No earnings within 14 days

For **TSLA** (high-beta growth):
- Sell call at delta 0.10-0.15
- DTE 21-30
- Strike ≥ 8% above current price
- IV rank > 30
- No CC currently open for this ticker
- No earnings within 14 days

For **RIVN** (high-vol small-cap, staged):
- Sell call at delta 0.20-0.25
- DTE 14-21
- Strike ≥ 10% above current price
- Minimum absolute premium $0.15
- (IV rank skipped — no IV data for RIVN)
- No earnings within 7 days

**Prerequisite:** `HoldingsService.covered_call_capacity(ticker) ≥ 1`. Otherwise no CC possible.

**Exit rules:**

| Condition | Action |
|-----------|--------|
| Buyback at 70% (more aggressive than wheel) | Close, reason="TARGET" |
| Delta of short call ≥ 0.50 AND DTE < 14 | Roll up and out for credit if possible |
| DTE ≤ 7 | Close, reason="DTE_FLAT" (don't let it expire ITM unintentionally) |
| Earnings 2 days away | Close, reason="PRE_EARNINGS" |
| Expires OTM | Close, reason="EXPIRY_OTM" |
| Expires ITM (called away) | Close, reason="CALLED_AWAY"; Holdings.shares -= 100 |

**Features logged:**

- All standard entry features
- premium_collected (per cycle)
- premium_annualized_yield: premium / strike × (365 / DTE)
- opportunity_cost: max(0, current_spot - strike) × 100 (the upside you capped)
- cumulative_premium_collected_on_this_ticker
- number_of_rolls
- whether_called_away

**Variants:** one per ticker (3 variants).

```python
class IncomeCcStrategy(Strategy):
    CATEGORY = "INCOME_CC"

    # Per-ticker tier configurations
    TIERS = {
        "GOOGL": {"short_delta": (0.15, 0.20), "dte": (30, 45),
                  "min_strike_pct_above": 0.05, "min_iv_rank": 25,
                  "earnings_blackout_days": 14},
        "TSLA": {"short_delta": (0.10, 0.15), "dte": (21, 30),
                 "min_strike_pct_above": 0.08, "min_iv_rank": 30,
                 "earnings_blackout_days": 14},
        "RIVN": {"short_delta": (0.20, 0.25), "dte": (14, 21),
                 "min_strike_pct_above": 0.10, "min_premium_abs": 0.15,
                 "min_iv_rank": None,           # skip
                 "earnings_blackout_days": 7},
    }

    async def scan(self, now): ...
    async def manage(self, trade, current_mtm, now): ...
```

**What you'll learn:**
- Real annualized yield per ticker.
- Opportunity cost from capped upside (likely the hidden killer).
- Whether TSLA CCs are even viable given its vol.
- How rolls affect the income vs holding pattern.

---

### 8.7 Strategy 7: Earnings Strangles

**Category name:** `EARNINGS_STRANGLE`

**Hypothesis:** IV expands into earnings and crushes after. Buying strangles 5 days before announcement and closing the day before captures the IV ramp without taking event risk.

**Cadence:** daily_scan.

**Entry rules:**

| # | Filter | Threshold | Logged |
|---|--------|-----------|--------|
| 1 | Underlying in [NVDA, TSLA, AAPL, GOOGL] | — | — |
| 2 | No open position for this variant on this ticker | — | — |
| 3 | Earnings announcement is exactly `days_before_earnings` trading days away | 5 | earnings_date |
| 4 | IV percentile (trailing 60d) ≤ max_iv_percentile | 50 | iv_percentile |
| 5 | Find expiry that lands after earnings | — | expiry_used |
| 6 | Find call at +0.30 delta and put at -0.30 delta | — | call_strike, put_strike |
| 7 | Total debit ≤ max_debit | $5.00 | debit |
| 8 | Total debit ≤ 2% of underlying price | — | debit_pct_of_spot |

**Exit rules (priority order):**

| Condition | Action |
|-----------|--------|
| 30 min before close on day before earnings | Close, reason="PRE_EARNINGS" (HARD RULE — never hold through) |
| Position value ≥ 1.5 × debit | Close, reason="TARGET" (up 50%) |
| Position value ≤ 0.7 × debit | Close, reason="STOP" (down 30%) |

**Features logged:**

- IV percentile at entry, per leg IV at entry
- IV at exit per leg
- Days held
- Underlying drift during hold
- The "missed move" (what underlying did from your exit through next day's open) — logged retroactively after earnings
- Total debit paid, total credit received

**Variants:** 1 variant × 4 tickers = 4 total: `30D_5D_BEFORE`.

```python
class EarningsStrangleStrategy(Strategy):
    CATEGORY = "EARNINGS_STRANGLE"

    async def scan(self, now): ...
    async def manage(self, trade, current_mtm, now): ...
    async def _is_entry_window(self, ticker, now): ...
```

**What you'll learn:**
- Per-ticker IV ramp magnitude (varies dramatically).
- Whether 30-delta strangles or ATM straddles work better (add variant later).
- The cost of timing — closing too early vs too late.
- Vega in your bones.

---

### 8.8 Strategy summary table

| # | Strategy | Category | Cadence | Variants | Underlyings | Notes |
|---|----------|----------|---------|----------|-------------|-------|
| 1 | Wheel | WHEEL | daily | 3 | 6 stocks | 18 instances |
| 2 | 0DTE PCS | ZERO_DTE_PCS | 60s | 4 | 2 indices | 8 instances; one variant is control |
| 3 | Long DTE Credit | LONG_DTE_CREDIT | daily | 1 | 4 (SPY, NVDA, TSLA, IWM) | 4 instances |
| 4 | Mean Rev EM | MEAN_REVERSION_EM | 60s | 1 | 2 (SPY, SPX) | 2 instances |
| 5 | Wall Break | WALL_BREAK | 60s | 1 | 2 (SPY, SPX) | 2 instances |
| 6 | Income CC | INCOME_CC | daily | 1 (per-ticker) | 3 (GOOGL, TSLA, RIVN-staged) | 3 instances; RIVN staged |
| 7 | Earnings Strangle | EARNINGS_STRANGLE | daily | 1 | 4 stocks | 4 instances |

**Total: 41 ResearchStrategy variants running in parallel.**

---

## 9. Analytics & Weekly Review

### 9.1 What the analytics layer produces

Three artifacts, written on schedule to Prisma:

1. **Daily strategy rollup** (16:30 ET, after market close) — for each ResearchStrategy with activity today, write a row to `BacktestResult` and update `ResearchRun` (or create a new one if none exists for this period).
2. **Weekly review report** (Sunday 17:00 ET) — written to `Rundown.content` as markdown, viewable in the Next.js dashboard.
3. **Feature-importance breakdown** (Sunday, on-demand via CLI) — computes per-feature win rate splits and writes to a `Note` row tagged "feature_analysis".

### 9.2 The AnalyticsService

```python
# scripts/libs_py/strategy_engine/analytics.py

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass
class StrategyStats:
    """Summary stats for one ResearchStrategy over a period."""
    research_strategy_id: str
    name: str
    period_start: date
    period_end: date

    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float                         # wins / total

    gross_pnl: float
    avg_winner: float
    avg_loser: float
    profit_factor: float                    # gross_wins / gross_losses

    avg_days_held: float
    avg_capital_committed: float
    return_on_capital: float                # gross_pnl / avg_capital_committed
    annualized_roc: float

    max_drawdown: float                     # peak-to-trough on cumulative equity
    sharpe_daily: Optional[float]
    sortino_daily: Optional[float]

    grade: str                              # "A+" through "F"

    # Breakdown buckets
    win_rate_by_regime: dict                # {"POSITIVE": 0.72, "NEGATIVE": 0.41, ...}
    win_rate_by_iv_rank_bucket: dict        # {"0-25": ..., "25-50": ..., ...}
    win_rate_by_time_of_day: dict


@dataclass
class CrossStrategyReport:
    """Comparative metrics across strategies."""
    period_start: date
    period_end: date

    strategy_stats: list[StrategyStats]

    # Daily P&L curves per strategy (date → cumulative pnl)
    equity_curves: dict[str, list[tuple[date, float]]]

    # Correlation matrix of daily P&Ls
    correlations: dict[tuple[str, str], float]

    # Ranking
    ranked_by_sharpe: list[str]              # research_strategy_ids
    ranked_by_roc: list[str]
    ranked_by_win_rate: list[str]


class AnalyticsService:
    """Computes performance metrics, writes rollups, generates reports."""

    def __init__(self, prisma):
        ...

    async def compute_strategy_stats(
        self,
        research_strategy_id: str,
        period_start: date,
        period_end: date,
    ) -> Optional[StrategyStats]:
        """All metrics for one ResearchStrategy over a date range.

        Returns None if no trades in the period.

        Queries:
        - SELECT * FROM Trade WHERE
            json_extract(metadata, '$.research_strategy_id') = ?
            AND status = 'CLOSED'
            AND exitDate BETWEEN ? AND ?
        - Computes win/loss splits, drawdown from cumulative equity series.
        - Reads MarketCondition for regime context per trade.
        - Reads Trade.metadata for feature values per trade.
        """
        ...

    async def daily_rollup(self, target_date: Optional[date] = None) -> None:
        """For each active ResearchStrategy with trades closed today:
        1. Compute StrategyStats for the full strategy life-to-date.
        2. Upsert a BacktestResult row with the current summary.
        3. Update or create a ResearchRun row with metricsJson, configJson, grade.

        Called daily at 16:30 ET.
        """
        ...

    async def weekly_review(self, week_ending: date) -> str:
        """Generate the weekly review report as markdown.

        Sections:
        - This week's summary (trades opened, closed, P&L per strategy)
        - Cross-strategy ranking by win rate and ROC
        - Top performers and worst performers
        - Anomalies (strategies that fired dramatically more or less than usual)
        - Feature breakdowns: for each strategy with ≥20 trades, the most
          predictive features identified from win-rate splits
        - Near-miss summary: which filters caused the most rejections per strategy
        - Open positions snapshot

        Writes to Rundown.content with date=week_ending.
        Returns the markdown string for stdout/email.
        """
        ...

    async def feature_breakdown(
        self,
        research_strategy_id: str,
        feature_name: str,
        bucket_strategy: str = "quartile",   # or "median_split" or "custom"
    ) -> dict:
        """For a specific feature, compute win rate within each bucket.

        Example: feature_breakdown("SPY_0DTE_PCS_10D_5W", "iv_rank")
        returns {
            "Q1 (0-25)": {"n": 12, "win_rate": 0.83, "avg_pnl": 18.4},
            "Q2 (25-50)": {"n": 14, "win_rate": 0.71, "avg_pnl": 12.1},
            ...
        }
        """
        ...

    async def cross_strategy_report(
        self,
        period_start: date,
        period_end: date,
    ) -> CrossStrategyReport:
        """All-strategy comparative report. Used in the weekly review."""
        ...

    async def correlation_matrix(
        self,
        research_strategy_ids: list[str],
        period_start: date,
        period_end: date,
    ) -> dict:
        """Pairwise correlation of daily P&L between strategies.

        Useful for diversification analysis: high correlation = same edge,
        no actual diversification.
        """
        ...

    async def grade_strategy(self, stats: StrategyStats) -> str:
        """Assign letter grade based on a composite of win rate, profit factor,
        Sharpe, and drawdown. Stored in ResearchRun.grade.

        Grading rubric:
            A+: win_rate > 65%, PF > 2.0, Sharpe > 1.5, dd < 10%
            A : win_rate > 60%, PF > 1.7, Sharpe > 1.2
            B : win_rate > 55%, PF > 1.4
            C : win_rate > 50%, PF > 1.2
            D : profitable but doesn't meet C
            F : losing money
        """
        ...
```

### 9.3 The weekly review report structure

The Sunday rundown markdown looks roughly like:

```markdown
# Weekly Review — Week ending 2026-06-07

## Summary
- Trades opened: 47
- Trades closed: 51
- Net P&L (all strategies): +$842.31
- Best strategy: SPY_0DTE_PCS_16D_5W (+$312)
- Worst strategy: SPY_WALL_BREAK_BREAKOUT_DEBIT (-$87)

## Cross-Strategy Ranking
| Rank | Strategy | Win Rate | PF | Sharpe | Grade |
|------|----------|----------|-----|--------|-------|
| 1 | SPY_0DTE_PCS_16D_5W | 72% | 2.1 | 1.8 | A |
| 2 | NVDA_WHEEL_30D_45DTE | 100% | ∞ | — | (too few trades) |
| ... | ... | ... | ... | ... | ... |

## Feature Breakdowns
### SPY_0DTE_PCS_10D_5W (n=18)
- Win rate when IV rank > 30: 82% (n=11)
- Win rate when IV rank ≤ 30: 43% (n=7)
- → IV rank appears predictive; consider raising min_iv_rank.

### NVDA_WHEEL_30D_45DTE (n=4)
- Insufficient data for breakdowns (need ≥20 trades).

## Near-Miss Analysis
- SPY_0DTE_PCS_10D_5W: top rejection = "not_positive_gamma" (43%)
  - Many missed opportunities? Or correctly filtered out bad trades?
  - Need 4 more weeks to evaluate.

## Open Positions
- NVDA_WHEEL_30D_45DTE — SHORT_PUT, opened 2026-05-29, DTE 18, unrealized +$45
- TSLA_INCOME_CC_TIER — SHORT_CALL, opened 2026-06-02, DTE 22, unrealized +$30
- ...

## Action Items for User Review
- Validate fill assumptions: pick 3 trades from this week, paper-trade them in Schwab,
  compare actual fills to mid.
- Review SPY_0DTE_PCS_10D_5W IV rank breakdown — likely a parameter tightening opportunity.
```

### 9.4 SQL examples

For the user's reference, the analytics relies on these query patterns:

**Trades for a specific research strategy:**
```sql
SELECT *, json_extract(metadata, '$.research_strategy_id') AS rsid
FROM Trade
WHERE rsid = ?
  AND status = 'CLOSED'
  AND exitDate BETWEEN ? AND ?;
```

**Win rate by IV rank bucket:**
```sql
SELECT
  CASE
    WHEN CAST(json_extract(metadata, '$.iv_rank') AS REAL) < 25 THEN 'Q1'
    WHEN CAST(json_extract(metadata, '$.iv_rank') AS REAL) < 50 THEN 'Q2'
    WHEN CAST(json_extract(metadata, '$.iv_rank') AS REAL) < 75 THEN 'Q3'
    ELSE 'Q4'
  END AS iv_bucket,
  COUNT(*) AS n,
  SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS win_rate,
  AVG(pnl) AS avg_pnl
FROM Trade
WHERE json_extract(metadata, '$.research_strategy_id') = ?
  AND status = 'CLOSED'
GROUP BY iv_bucket;
```

**Correlation between two strategies' daily P&Ls:**
```sql
WITH daily_pnl AS (
  SELECT
    date(exitDate) AS d,
    json_extract(metadata, '$.research_strategy_id') AS rsid,
    SUM(pnl) AS daily_pnl
  FROM Trade
  WHERE status = 'CLOSED'
  GROUP BY d, rsid
)
SELECT a.d, a.daily_pnl AS pnl_a, b.daily_pnl AS pnl_b
FROM daily_pnl a
JOIN daily_pnl b ON a.d = b.d
WHERE a.rsid = ? AND b.rsid = ?
ORDER BY a.d;
-- Then compute Pearson correlation in Python.
```

---

## 10. Seed Data & Bootstrap

### 10.1 First-run setup

`seed_data.py` is the one-time bootstrap script. It:

1. **Reads `config.yaml`**.
2. **Creates `AccountGroup`** named "Strategy Engine Silos" if not present.
3. **Creates `Strategy` rows** (the seven categories) if not present.
4. **Creates `Playbook` rows** with markdown rule text (the spec content from §8 for each strategy).
5. **For each strategy variant in config.yaml**:
   - Create a `ResearchStrategy` row with the variant name.
   - Create an `Account` row with `initialBalance=config.default_initial_balance`, linked to the AccountGroup.
6. **Creates `Holding` rows** from config.yaml `holdings` section.
7. **Logs all created entities** to stdout for verification.

```python
# scripts/libs_py/strategy_engine/seed_data.py

import asyncio
import yaml
from pathlib import Path


async def seed(config_path: Path = "config.yaml", update: bool = False):
    """One-time setup.

    Args:
        config_path: path to config.yaml
        update: if True, update existing rows with new params. Default False
                (refuse to overwrite to prevent accidental data loss).
    """
    ...


def _seed_strategy_categories(prisma) -> dict:
    """Create the 7 Strategy rows. Returns {category_name: strategy_id}."""
    ...


def _seed_playbooks(prisma) -> dict:
    """Create Playbook rows with rules text. Returns {category_name: playbook_id}."""
    ...


def _seed_research_strategies(prisma, config, strategy_ids, playbook_ids) -> list:
    """Create ResearchStrategy + Account per variant. Returns list of created ids."""
    ...


def _seed_holdings(prisma, holdings_config):
    """Create Holding rows."""
    ...


def _generate_variant_name(category: str, underlying: str, suffix: str) -> str:
    """e.g. ("WHEEL", "NVDA", "30D_45DTE") → "NVDA_WHEEL_30D_45DTE"."""
    return f"{underlying}_{category}_{suffix}"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed(Path(args.config), update=args.update))
```

### 10.2 Example: variant naming

The config's wheel section with 3 variants × 6 tickers produces 18 ResearchStrategy rows:

```
NVDA_WHEEL_30D_45DTE     account_id: acc_001    initial_balance: 25000
NVDA_WHEEL_20D_45DTE     account_id: acc_002    initial_balance: 25000
NVDA_WHEEL_30D_7DTE      account_id: acc_003    initial_balance: 25000
TSLA_WHEEL_30D_45DTE     account_id: acc_004    initial_balance: 25000
... (15 more) ...
```

Each variant has its own dedicated Account with $25K. They never share capital.

### 10.3 Playbook content

Each Playbook row's `rules` field contains the markdown spec for that strategy. Example for the wheel:

```markdown
# Wheel Strategy Playbook

## State Machine
[copied from §8.1 of this document]

## Entry Rules — CSP
[copied]

## Exit Rules
[copied]

## What This Tests
[copied]
```

This means the engine's behavior is fully traceable back to the documented rules. If the spec changes, the Playbook is updated, and existing trades retain their historical Playbook reference.

---

## 11. Operational Runbook

### 11.1 Starting the engine

```bash
# One-time bootstrap (only on first install)
cd scripts/libs_py/strategy_engine/
python seed_data.py --config config.yaml

# Run the engine
python runner.py
```

Recommended: use `pm2` or `systemd` to keep it running on the user's laptop:

```bash
pm2 start runner.py --name strategy_engine --interpreter python3
pm2 save
```

### 11.2 Daily operations

The engine self-manages. No daily user intervention needed.

**What happens automatically:**
- 9:30 ET: engine starts ticking (it's already running; this is when it begins firing scans).
- 10:00 ET: daily_scan runs (wheel CSPs, earnings strangles).
- 10:00-16:00 ET: index strategies tick every 60s, stock strategies every 5m.
- 16:00 ET: trading halts; engine stops scanning but holds open positions for next-day decisions.
- 16:30 ET: analytics daily_rollup runs.
- 03:00 ET: maintenance/pruning runs (delete QuoteSnapshots > 90 days, SignalNearMiss > 30 days).
- Weekly on Sunday 17:00 ET: weekly_review runs and writes the Rundown.
- Weekly on Sunday 18:00 ET: earnings calendar refresh.

### 11.3 What the user does

**Daily (5 min):**
- Spot-check the engine is alive (logs show recent activity).

**Weekly (30-60 min):**
- Read the auto-generated Rundown.
- Review feature breakdowns; consider parameter tweaks.
- If pondering changes, edit `config.yaml`, then run `seed_data.py --update`.

**Monthly (one-off task):**
- Pick 5-10 recent paper trades and replicate them in Schwab's paper account.
- Compare actual fills to engine-assumed mid fills.
- If systematic slippage detected, file as v1.1 issue.

### 11.4 Failure modes and recovery

| Failure | Symptom | Recovery |
|---------|---------|----------|
| Schwab API unreachable | BrokerUnavailableError in logs | Engine logs and skips this tick; auto-retries next tick. If sustained > 15 min, alert user. |
| GexSnapshot stale > 5 min | RegimeService returns None | Strategies that require regime data refuse to trade. Logged. Engine continues. |
| Prisma connection lost | Crashes write attempts | pm2 restarts the runner; engine re-initializes. Resume from last completed tick. |
| Dolt query fails | iv_rank=None | Strategies that have iv filter skip it; logged in metadata. |
| Parquet file missing | IctService returns None | Strategies that require ICT skip; logged. |
| Holdings out of sync (CC fires but no shares) | Logged error | Engine refuses to open. User manually reconciles `Holding` rows. |

### 11.5 Logging

All logs go to `~/strategy_engine.log` with rotation:
- INFO: every tick, every signal, every open/close.
- WARNING: filter failures that look suspicious (e.g. all strategies failing same filter for hours), data staleness.
- ERROR: API failures, DB errors, unexpected exceptions.

A separate `~/strategy_engine_trades.csv` is appended on every close for quick eyeballing.

### 11.6 Maintenance schedule

| Task | Cadence | Owner |
|------|---------|-------|
| Engine process alive | Continuous | pm2 |
| QuoteSnapshot pruning (>90d) | Daily 03:00 ET | Engine |
| SignalNearMiss pruning (>30d) | Daily 03:00 ET | Engine |
| Earnings calendar refresh | Weekly Sun 18:00 ET | Engine |
| Dolt volatility_history update | Weekly | User's existing cron |
| GEX pipeline (run_options_levels.py) | Continuous | User's existing process |
| Manual config review | Quarterly | User |
| Schwab paper-fill validation | Monthly | User |

---

## 12. Open Questions & Future Work

### 12.1 Known issues to revisit

1. **Slippage assumption.** v1 assumes mid-fill. User's monthly paper-fill validation may reveal systematic slippage. **Action:** if validated, add a per-strategy `fill_slippage_dollars` config knob in v1.1.

2. **AMD pipeline gap.** AMD has no GEX snapshots in Prisma. Add AMD to the pipeline config; once collecting, add an AMD wheel variant in v1.2.

3. **QQQ and IWM `ExpectedMoveHistory` gap.** Not blocking but useful for historical hit-rate analytics. **Action:** extend `api_expected_move.py` to populate these.

4. **RIVN data collection.** Add RIVN to GEX pipeline. After ~4 weeks of collection, the RIVN income CC strategy can go live.

5. **IV rank for IWM.** Currently skipped for IWM long-DTE strategy. Once we have ≥6 months of forward IWM IV data (collected from `RthExpectedMove.ivAtOpen`), build a percentile-rank substitute.

### 12.2 Deferred features (v2 candidates)

1. **Layer 2 capital allocator.** After 3+ months of strategy data, build an allocator that proposes capital allocation across strategies given their performance, correlation, and drawdown profiles. Currently strategies have independent silos.

2. **Multi-contract sizing.** v1 fires 1 contract per signal. v2 could scale based on conviction (e.g. higher contract count when multiple ICT/GEX/IV filters all align strongly).

3. **Stacking positions.** v1 enforces one-open-per-variant. v2 could allow stacking 0DTE PCS entries at different deltas in the same session.

4. **Iron condors and iron flies.** Currently both wings traded separately. Combining as IC/IF reduces capital and rerwrites the variant matrix.

5. **Futures options.** The architecture supports them. Once ES/NQ options are added to BrokerService, strategies extend naturally.

6. **ICT persistence (the parquet cache).** If on-demand computation proves too slow, add the daily-batch ICT parquet from §4.5's alternative design.

7. **Earnings strangle variants.** Test straddle vs strangle, 3-day vs 5-day entries, hold-through-earnings as a separate variant.

8. **Real-time notifications.** Currently no notifications. v2 could push to Discord/Slack on each signal fired, on regime changes, on stop-outs.

9. **Web dashboard.** The Next.js app shown in your inventory could grow a Strategy Engine tab with real-time positions, equity curves, near-miss summaries.

10. **Multi-account / multi-broker.** Eventually support Tradier or IBKR as alternative broker adapters. The BrokerService interface is intentionally generic.

### 12.3 Things that could break the design

1. **Schwab API changes.** If Schwab significantly changes their options API, `ezoptionsschwab` needs updating. The BrokerService interface insulates strategies; only the adapter changes.

2. **Volume changes upstream.** If GEX snapshots stop being written every 60s for index tickers (e.g. their pipeline fails), strategies will refuse to fire. Acceptable: better to skip than trade on stale data.

3. **Prisma schema changes.** The existing schema is owned by the broader app. If a future change removes/renames fields the engine uses, the engine breaks. **Mitigation:** keep `strategy_engine` as a separate dependency-aware module, run pre-flight schema validation at startup.

4. **Volatility regime shifts.** Strategies tuned to current vol may underperform in radically different regimes (e.g. sustained VIX > 40). The forward-test discovers this naturally over time.

### 12.4 Success criteria

The engine has succeeded if, after 3-6 months of operation:

1. The user has clear data answering: which of these 7 strategies actually work? At what parameter settings?
2. The user can articulate, with data backing, why each strategy works (or doesn't): which features predict wins, which regimes favor each strategy.
3. The user has internalized the mechanics of all 7 strategies — wheels, CCs, credit spreads at multiple DTEs, mean reversion, wall breaks, and earnings strangles — well enough to design and propose their own variants.
4. The user has a defensible answer to the original question: "given my $25K, how should I allocate it across these strategies in real money?"

If any of these isn't true at the 6-month mark, the engine has failed at its primary purpose (learning) regardless of whether the paper P&L is positive.

---

## Appendix A: Implementation Order

Recommended build sequence to get value fastest:

1. **Week 1:** Prisma migration (the 5 new models), seed_data.py with config.yaml structure, BrokerService wrapping existing modules.
2. **Week 2:** RegimeService, ExpectedMoveService, IvService, CalendarService, HoldingsService — all the read-only services.
3. **Week 3:** Strategy base class, PaperExecutor, signal_log, LegQuoteService, the engine loop with mock strategies for end-to-end test.
4. **Week 4:** Strategy 1 (Wheel) full implementation. End-to-end on paper.
5. **Week 5:** Strategy 2 (0DTE PCS) — your home court — full implementation.
6. **Week 6:** Strategies 3 (Long DTE Credit) and 6 (Income CC).
7. **Week 7:** IctService, Strategy 4 (Mean Reversion EM), Strategy 5 (Wall Break).
8. **Week 8:** Strategy 7 (Earnings Strangle), AnalyticsService, weekly review.
9. **Week 9+:** Run, observe, tune.

Each phase produces a working subset. Don't try to ship all 7 strategies at once — the value comes from running and learning.

## Appendix B: Files to create

```
scripts/libs_py/strategy_engine/
├── __init__.py
├── config.yaml
├── seed_data.py
├── engine.py
├── runner.py
├── paper_exec.py
├── signal_log.py
├── analytics.py
├── services/
│   ├── __init__.py
│   ├── broker_service.py
│   ├── regime_service.py
│   ├── em_service.py
│   ├── iv_service.py
│   ├── ict_service.py
│   ├── calendar_service.py
│   ├── earnings_service.py
│   ├── holdings_service.py
│   ├── sizing_service.py
│   └── leg_quote_service.py
└── strategies/
    ├── __init__.py
    ├── base.py
    ├── wheel.py
    ├── zero_dte_pcs.py
    ├── long_dte_credit.py
    ├── mean_reversion_em.py
    ├── wall_break.py
    ├── income_cc.py
    └── earnings_strangle.py

web/prisma/schema.prisma                    # ADD 5 models (TradeLeg, QuoteSnapshot,
                                            #               SignalNearMiss, Holding,
                                            #               EarningsCalendar)
```

## Appendix C: Glossary

- **Variant.** A specific parameterization of a strategy (e.g. "NVDA_WHEEL_30D_45DTE"). One row in `ResearchStrategy`.
- **Capital silo.** A dedicated `Account` row for one variant. They never share capital in v1.
- **Near-miss.** A scan that almost fired but failed a filter. Logged for post-hoc analysis.
- **Entry features.** The dict of all filter values observed during a scan, stored in `Trade.metadata` for analytics.
- **Stuck.** Wheel state where no acceptable CC strike exists (would be below breakeven).
- **GEX regime.** Whether dealers are net long gamma (POSITIVE) or short gamma (NEGATIVE) at current spot.
- **Mid-fill.** The fill price assumption: the midpoint of bid/ask at signal time.
- **Tick.** One iteration of the engine's main loop.

---

**End of specification. Implementation begins in your IDE.**
