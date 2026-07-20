# Product Requirements Document (PRD): Stock & Options Screener Engine (`trade_screener`)

**Document Version**: 1.1.0  
**Status**: Implemented & Active  
**Author**: Antigravity AI & Trading Team  
**Date**: 2026-07-20  

---

## 1. Overview & Objectives

The **`trade_screener` engine** is a high-performance, 100% free Python stock and options screening framework built directly into the local trading environment (`tvDownloadOHLC`). It empowers systematic traders to identify high-probability momentum swing breakouts and income-generating option setups across proven institutional frameworks.

### Primary Goals
1. **Proven Framework Coverage**: Support Minervini (Trend Template & VCP), O'Neil (CANSLIM Cup-with-Handle), Stockbee (Momentum Bursts, EPs, Industry RS), Qullamaggie (High Tight Flags, Parabolic Shorts), Oliver Kell (EMA Reversals), Dan Zanger (Volume Surges), Stan Weinstein (Stage 2 Uptrends), and Covered Calls/PMCC options strategies.
2. **Global Market Regime Gatekeeper**: Provide a single master macro gatekeeper (SPY/QQQ trends + S&P 500 breadth + high-impact economic event risk) that dynamically sizes or stands down strategies.
3. **Data Integrity & Policy Enforcement**: Enforce explicit split vs. dividend adjustment policies, float cross-validation, and survivorship bias flags on all setup evaluations.
4. **Single Source of Truth Earnings Calendar**: Integrate direct Nasdaq Earnings API fetching into `sync_earnings_calendar.py` to keep the Web UI, Discord Notifier, and Screener perfectly synchronized via `web/prisma/dev.db`.
5. **Declarative Strategy Rule Engine**: Allow strategies to be defined via versioned YAML files over a 100% vectorized Pandas feature table.

---

## 2. Core Functional Requirements

### FR-1: Universe Funneling & Data Pipeline (Stage 1 & 2)
- **Top-of-Funnel Filtering**: Query Finviz (`finvizfinance`) to reduce ~8,000 US equities to ~100–200 high-potential candidates based on liquidity (Price $> \$5$, Volume $> 500\text{K}$), performance, and sector filters.
- **Vectorized Data Fetching**: Fetch 6-month daily OHLCV bars for candidate tickers in a single multi-threaded vectorized `yfinance` network call.
- **Data Adjustment Standard**:
  - Technical price levels, Moving Averages (10/20 EMA, 50/150/200 SMA), ADR%, and Gap % calculations MUST use **Split-Adjusted ONLY** data.
  - Performance and Relative Strength (RS) calculations MUST use **Split- and Dividend-Adjusted Total Return** data.

### FR-2: Float Cross-Validation Engine
- Cross-reference Finviz reported Float with `yfinance` `sharesOutstanding` and `floatShares`.
- Flag any ticker with float discrepancy $>15\%$ to prevent false low-float triggers on outdated share counts.

### FR-3: Industry Group Relative Strength Engine
- Track 140+ Finviz / ETF industry groups.
- Calculate 1-month and 3-month Industry Group RS rank.
- Gate Stockbee and Minervini strategies so candidate stocks must belong to an Industry Group in the **Top 15%–25% RS rank**.

### FR-4: Dual-Provider Earnings Calendar Sync
- Upgrade `scripts/market_data/sync_earnings_calendar.py` with **Nasdaq Earnings API** (`api.nasdaq.com/api/calendar/earnings`) as primary provider and `yfinance` as fallback.
- Persist structured events to `web/prisma/dev.db` (`EarningsEvent` table).
- Provide calendar bridge functions:
  - `is_episodic_pivot_catalyst(ticker, date)`: Validates earnings gap-ups for Stockbee EPs.
  - `has_upcoming_earnings(ticker, window_days=5)`: Excludes options setups expiring across earnings.

### FR-5: Global Market Regime Filter (Master Gatekeeper)
Every strategy evaluation inherits a global market regime state derived from SPY/QQQ and high-impact macro calendar events in `dev.db`:
- **`BULL_EXPLOSIVE`**: SPY & QQQ $> 21\text{ EMA} > 50\text{ SMA}$; $>60\%$ S&P 500 stocks $> 50\text{ SMA}$. $\rightarrow$ **Full position sizing**.
- **`BULL_CHOPIER`**: SPY $> 50\text{ SMA}$ but $< 21\text{ EMA}$. $\rightarrow$ **Half position sizing / tighter trailing stops**.
- **`BEAR_PROTECTIVE`**: SPY $< 50\text{ SMA}$ & $200\text{ SMA}$; $<40\%$ stocks $> 50\text{ SMA}$. $\rightarrow$ **Long breakouts disabled; Parabolic Shorts / Cash active**.
- **`MACRO_HIGH_RISK`**: Today has major FOMC / CPI / NFP event release. $\rightarrow$ **Tightened risk parameters**.

### FR-6: Declarative YAML Strategy Evaluator
- Evaluates strategy rules defined in YAML files (`strategies/*.yaml`).
- Each YAML strategy defines: `strategy_id`, `version`, `author`, `global_regime_required`, `filters`, and `rules` expressions.
- Executes 100% vectorized expression evaluation over the Pandas feature matrix without python `for` loops (ADR-017 compliance).

### FR-7: Setup Logging, Forward Return Tracking & Survivorship Bias
- Log every flagged candidate into local DuckDB (`data/screener_setups.duckdb`) with schema:
  `[setup_id, timestamp_utc, ticker, strategy_id, strategy_version, config_hash, market_regime, entry_close, adr_20_pct, tightness_pct, industry_rs_rank, float_shares, survivorship_bias_flag]`
- Automatically evaluate 5-day, 10-day, and 20-day forward performance (MFE/MAE/Returns %) for tracked setups.
- Append a **Survivorship Bias Warning Flag** on all historical backtest outputs.

---

## 3. Non-Functional Requirements (NFRs)

1. **Performance**: Total end-to-end execution of a full market scan across 100 candidates must complete in $< 15$ seconds.
2. **Zero-Loop Architecture**: All calculation paths in `features.py` must use vectorized Pandas/NumPy operations (ADR-017).
3. **Reproducibility**: Every logged setup MUST store a SHA256 `config_hash` of the YAML rule file evaluated.
4. **Timezone Standard**: UTC for database storage; ET (`America/New_York`) for market session calculations (ADR-001).

---

## 4. Architectural Boundaries

- **In Scope (Phases 1–3)**: Data Pipeline, Adjustment Handlers, Nasdaq Earnings API Sync, Feature Matrix Engine, YAML Strategy Evaluator, DuckDB Setup Logger, Forward Return Backtester.
- **Out of Scope (Deferred to Phase 4)**: Discord Webhook Bot UI commands, TradingView Watchlist CSV exporter, Next.js Web UI page (`/screener`).
