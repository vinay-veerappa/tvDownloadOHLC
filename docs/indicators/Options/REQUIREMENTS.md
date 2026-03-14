# Dealer Levels — Requirements Specification

**Feature**: Automated Institutional Dealer Positioning Levels via Options GEX  
**Status**: v1.0  
**Last Updated**: 2026-03-14

---

## 1. Goals

Provide automated, quantitative, actionable price levels derived from the
institutional options dealer-hedging flow (Gamma Exposure), delivered to
traders before market open and refreshed mid-morning, so they can frame their
intraday bias and identify high-probability reaction zones on ES and NQ futures.

---

## 2. Non-Goals

- Real-time tick-by-tick GEX streaming (run schedule is 08:30 and 11:00 ET only).
- Intraday options flow monitoring (order-flow / dark-pool prints).
- Signal generation or automated order routing.
- Backtesting GEX-based strategies.

---

## 3. User Stories

| ID   | As a…         | I want to…                                              | So that…                                                   |
|------|---------------|---------------------------------------------------------|------------------------------------------------------------|
| US-1 | Day trader    | See ES and NQ Call Wall / Put Wall levels each morning  | I know where dealers are likely to defend / offer supply   |
| US-2 | Day trader    | See the Zero Gamma level                                | I know whether we are in a trending or reverting regime    |
| US-3 | Day trader    | Receive an 08:30 ET Discord notification                | I am informed before RTH open without running code myself  |
| US-4 | Day trader    | Get a mid-morning 11:00 ET refresh                      | I can re-evaluate after 0DTE open interest shifts          |
| US-5 | Day trader    | See all levels expressed in futures prices (ES / NQ)    | I can trade directly without manual basis adjustment       |
| US-6 | Pine coder    | Load levels into a TradingView indicator                | I can visualise them alongside price action                |
| US-7 | Developer     | Add a new underlying (e.g. IWM/RTY) with minimal effort | The system scales without invasive code changes            |

---

## 4. Functional Requirements

### FR-1: Data Ingestion

| ID      | Requirement                                                                 |
|---------|-----------------------------------------------------------------------------|
| FR-1.1  | Authenticate to the Charles Schwab Individual Developer API using stored OAuth tokens |
| FR-1.2  | Pull the full options chain for SPX (via `$SPX`) covering 0DTE and 1DTE expirations |
| FR-1.3  | Pull the full options chain for NDX (via `$NDX`) covering 0DTE and 1DTE expirations |
| FR-1.4  | Fall back to SPY (SPX) or QQQ (NDX) if the index chain returns no contracts |
| FR-1.5  | Pull a current quote for `/ES` (E-mini S&P 500) and `/NQ` (E-mini Nasdaq-100) futures |
| FR-1.6  | Each contract record must include: strike, expiry, OI, bid, ask, mark, IV, delta, gamma, theta, vega, rho, DTE |

### FR-2: GEX Calculations

| ID      | Requirement                                                                 |
|---------|-----------------------------------------------------------------------------|
| FR-2.1  | Compute per-strike Net GEX: `(call_gamma × call_OI − put_gamma × put_OI) × spot × 100` |
| FR-2.2  | Build a cumulative GEX profile from the lowest to highest strike            |
| FR-2.3  | Determine GEX Regime: POSITIVE when total GEX ≥ 0, NEGATIVE otherwise     |
| FR-2.4  | Identify the Zero Gamma level via linear interpolation at the sign-change strike |
| FR-2.5  | Identify the Call Wall: strike with maximum `call_OI × |call_gamma|`        |
| FR-2.6  | Identify the Put Wall: strike with maximum `put_OI × |put_gamma|`           |
| FR-2.7  | Only consider strikes with OI ≥ MIN_OI_THRESHOLD for wall detection         |

### FR-3: Expected Move

| ID      | Requirement                                                                 |
|---------|-----------------------------------------------------------------------------|
| FR-3.1  | Locate the ATM strike (closest to current spot price)                       |
| FR-3.2  | Default: EM = (ATM call ask + ATM put ask) × EM_STRADDLE_SCALAR             |
| FR-3.3  | Alternative (configurable): EM = spot × ATM_IV × √(max(DTE,1) / 365)       |
| FR-3.4  | Output EM Upper = spot + EM and EM Lower = spot − EM                        |

### FR-4: Futures Translation

| ID      | Requirement                                                                 |
|---------|-----------------------------------------------------------------------------|
| FR-4.1  | Compute basis spread = futures_price − cash_spot                            |
| FR-4.2  | Add the basis spread to every SPX level to produce ES-translated equivalents |
| FR-4.3  | Add the basis spread to every NDX level to produce NQ-translated equivalents |

### FR-5: Discord Output

| ID      | Requirement                                                                 |
|---------|-----------------------------------------------------------------------------|
| FR-5.1  | Post one Discord embed per asset pair (ES, NQ) via the configured webhook   |
| FR-5.2  | Embed must include: regime, cash spot, futures price, basis spread, Call Wall, Put Wall, Zero Gamma, EM Upper, EM Lower, ATM straddle, total GEX |
| FR-5.3  | Embed colour: green for POSITIVE regime, red for NEGATIVE regime            |
| FR-5.4  | Webhook URL is read from `discord_webhooks.json` (key: `alerts`)            |

### FR-6: File Output

| ID      | Requirement                                                                 |
|---------|-----------------------------------------------------------------------------|
| FR-6.1  | Write `data/daily_levels.json` with an array of level objects per the Pine Script schema |
| FR-6.2  | Write `data/daily_levels.txt` with a human-readable summary                 |
| FR-6.3  | JSON schema per entry: `{ level, type, asset, regime, cash_ticker, basis_spread }` |
| FR-6.4  | Both files must be overwritten (not appended) on each run                   |

### FR-7: Scheduling

| ID      | Requirement                                                                 |
|---------|-----------------------------------------------------------------------------|
| FR-7.1  | The pipeline must be runnable once on-demand (default CLI mode)             |
| FR-7.2  | The pipeline must be runnable on an APScheduler schedule via `--schedule`   |
| FR-7.3  | Scheduled runs fire at 08:30 ET and 11:00 ET on weekdays only               |
| FR-7.4  | Non-trading weekends must be silently skipped (no error)                    |

---

## 5. Non-Functional Requirements

| ID     | Category      | Requirement                                                     |
|--------|---------------|-----------------------------------------------------------------|
| NFR-1  | Reliability   | A failure for one asset pair must not prevent output for others |
| NFR-2  | Observability | All runs must produce structured log output to `data/dealer_levels.log` |
| NFR-3  | Extensibility | Adding a new underlying requires changes only in `config.py` and optionally the Pine Script |
| NFR-4  | Security      | API credentials (app_key, app_secret) must never be logged or embedded in source code |
| NFR-5  | Performance   | The full pipeline for two asset pairs must complete in < 30 seconds under normal conditions |
| NFR-6  | Correctness   | Zero Gamma reported with ≤ 2 decimal places resolution          |

---

## 6. Constraints

- Schwab API rate limits: use a single authenticated client per run; do not
  parallelize chain fetches without rate-limit guards.
- Schwab API requires `$SPX` (with dollar prefix) for CBOE cash index symbols.
- Pine Script v6 indicator receives data via manual input fields only (no
  file I/O from TradingView).
- `apscheduler` v3.x is required (`<4`); v4 has breaking API changes.
