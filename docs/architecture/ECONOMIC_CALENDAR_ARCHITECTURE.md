# Economic Calendar & Earnings Data Architecture

**Last updated:** 2026-07-23

## Overview

The narrative engine depends on economic calendar data for:
- Day type classification (CLEAN, CPI, NFP, FOMC, JACKSON_HOLE, SPECIAL)
- Weekly event timeline patterns (FOMC week, CPI week, NFP week, etc.)
- Calendar context blocks in premarket/open/intraday/close cheat sheets
- Earnings catalysts (index-moving mega-cap earnings)

## Single-Fetcher Policy

**Investing.com** (`scripts/market_data/fetch_economic_calendar.py`) is the **primary fetcher** for live/future economic calendar data.

| Fetcher | Role | Source | Future data? | Country stored? |
|---|---|---|---|---|
| `fetch_economic_calendar.py` | **PRIMARY** | Investing.com API (country_id=5) | ✅ 14 days ahead | ✅ `country='USD'` |
| `news_calendar_fetcher.py` | Fallback (NinjaTrader) | ForexFactory XML | ❌ Current week only | ✅ via Prisma |
| `web/lib/economic-calendar.ts` | Web app display | ForexFactory JSON | ❌ Current week only | ✅ USD-only |
| `seed-economic-events.ts` | Historical seed (one-time) | CSV + TradingEconomics API | N/A | ✅ `country='USD'` |

### Why Investing.com is primary

- Fetches **14 days ahead** (solves the Friday/Saturday ForexFactory limitation where next week's data isn't available until Sunday)
- Filters to **US only** (country_id=5)
- Has **impact levels** (HIGH/MEDIUM/LOW)
- Has **detailed event names** (CPI m/m, Median CPI, Trimmed CPI, etc.)

### Run command

```bash
.\.venv\Scripts\python.exe -m scripts.market_data.fetch_economic_calendar
```

Fetches today + 14 days of US economic events and upserts into the Prisma SQLite DB.

## Historical Data

- `docs/JournalRequirements/us_complete_economic_calendar_2000_2025.csv` — 9,063 rows (2000-2025, US only)
- `docs/JournalRequirements/economic_backfill/us_economic_calendar_2026_q1.csv` — ~1,000 rows (Q1 2026, US only)
- Seed script: `web/prisma/seed-economic-events.ts` — reads CSVs, backfills gaps via TradingEconomics API

## DB Schema

```prisma
model EconomicEvent {
  id        String       @id @default(cuid())
  datetime  DateTime
  name      String
  impact    String       // HIGH, MEDIUM, LOW
  country   String?      // USD (all events are US-only)
  actual    Float?
  forecast  Float?
  previous  Float?
  createdAt DateTime     @default(now())
  trades    TradeEvent[]
}
```

## Narrative Engine Integration

### `get_econ_releases()` — `scripts/trader/signals/econ_calendar.py`

Queries the DB for today's events, filtered by:
- `country = 'USD'` (DB-level filter)
- `datetime` within today's ET range

Returns events with `time_et`, `impact`, `datetime` (epoch ms), `forecast`, `previous`, `actual`.

### `classify_day_type()` — `scripts/trader/signals/day_type.py`

Classifies the trading day based on HIGH impact events:
- `cpi` — CPI m/m, CPI y/y, Core CPI m/m, Core CPI y/y
- `nfp` — Non-Farm Payroll, NFP
- `fomc` — FOMC, Federal Open Market
- `jackson_hole` — Jackson Hole, JacksonHole
- `special` — other HIGH impact events (Jobless Claims, Treasury auctions, etc.)
- `clean` — no HIGH impact events

### `get_weekly_modifiers()` — `scripts/trader/briefing_core.py`

Detects week-level context:
- `is_opex_week` — third Friday of the month
- `is_triple_witching_week` — third Friday in Mar/Jun/Sep/Dec
- `is_fomc_week` — any FOMC event this week
- `is_cpi_week` — US CPI event this week (filtered to US-only patterns)
- `is_nfp_week` — NFP event this week
- `is_jackson_hole_week` — Jackson Hole event this week
- `has_treasury_auction` — Treasury/Bond auction this week

## Earnings Calendar

Earnings data is fetched separately via the Schwab API / yfinance in `scripts/trader/signals/earnings.py`:
- `fetch_earnings_events()` — fetches earnings for the target date
- Filters to index-moving tickers (AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA)
- Resolves overnight price moves via Schwab/yfinance

### Earnings in narratives
- **Premarket**: shows BMO_TODAY and AMC_YESTERDAY earnings with pre-market % moves
- **Close**: flags BMO today or AMC/AMC_YESTERDAY that could move the index at tomorrow's open
- **Weekly**: lists index-moving earnings for the week

## Data Quality Audit (2026-07-23)

### Issues found and fixed

| Issue | Root cause | Fix |
|---|---|---|
| All 11,662 events had `country=null` | 3 fetchers not writing `country` to DB | Fixed all fetchers; DB backfilled to `country='USD'` |
| International events in US narratives | Web app fetched 8 currencies | Restricted to USD-only |
| CPI week triggered by UK CPI | Over-broad `"CPI"` matching | Filtered to US CPI patterns only |
| No DB-level country filter | Unreliable name-based filtering | Added `WHERE country='USD'` to query |

### Alternatives considered

- **yfinance** (`Calendars.get_economic_events_calendar()`) — tested, works, fetches future data with `Region` filter. But lacks impact levels (HIGH/MEDIUM/LOW) and has abbreviated event names. Kept as potential fallback.
- **finviz** (`Calendar.calendar()`) — tested, returned empty. Not viable.