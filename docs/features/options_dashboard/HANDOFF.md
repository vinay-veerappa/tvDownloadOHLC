# Strategy Engine — Handoff Document

**Date:** 2026-05-17
**Status:** Design complete. Ready for implementation.
**Companion document:** `STRATEGY_ENGINE_SPEC.md` (the master specification)

---

## Purpose of this document

This is the **context bridge** between design and implementation. Read this before opening the spec. It tells you:

1. What the project is and why it exists
2. The user's situation and goals
3. Every significant decision we made and why
4. What's been ruled out (and why, so we don't relitigate)
5. The state of the user's existing infrastructure
6. Open items requiring user action
7. How to resume in a fresh context

If you are a future Claude/AI assistant picking this up: read sections 1-6 in order, then the spec. If you are the user returning to this after a break, jump to section 8 (Where you left off) first.

---

## 1. What we're building

An automated **paper-trading research engine** for options strategies. It runs continuously on the user's laptop during market hours, evaluates seven distinct options strategies in parallel against live Schwab market data, logs paper trades to a Prisma database, marks them to market, closes them on defined rules, and produces a weekly review showing which strategies actually work.

**The user is NOT** building this to:
- Run live trades (read-only against Schwab)
- Find the One True Optimal Strategy
- Build a backtesting framework against historical data (it's forward-test only)

**The user IS** building this to:
- Learn options strategy mechanics deeply by running them all in parallel
- Generate data-backed answers about which strategies fit their style
- Eventually allocate real capital across the winners with confidence

The framework treats "learning" as the primary deliverable. Paper P&L is secondary.

---

## 2. User context (important — shapes every decision)

**Background:**
- Trades futures actively. Comfortable with leverage, margin, intraday risk management, sitting through drawdowns.
- Has done credit spreads before. Has not done wheels, covered calls, strangles, calendar spreads, etc.
- Wants to learn the broader options landscape through systematic comparison.
- Full-time availability for this project.

**Capital plan:**
- Targeting ~$25K real-money deployment eventually.
- Per-strategy in the engine uses $25K simulated silos (so each strategy is evaluated as if it had the full account — comparison is per-strategy).
- Real money allocation across strategies is a Phase 2 question.

**Risk profile:**
- Conservative: $100-$500 risk per trade.
- Target win rate: 60%+.

**Holdings (real positions the user has, used by income CC strategy):**
- TSLA: 200 shares
- GOOGL: 100 shares
- RIVN: 500 shares

**Tickers the user wants to potentially own long-term (wheel candidates):**
- NVDA, TSLA, AAPL, GOOGL, MSFT, AMZN (the "magnificent 7 minus META")

**ICT methodology:**
- User practices ICT (Inner Circle Trader) price action methodology — FVGs, order blocks, liquidity sweeps, killzones.
- Has it computed in code (vectorized via `pa.py`).
- Wants ICT confluence to enhance strategy filtering, but it's optional, not mandatory.

**Existing infrastructure (this is critical — the engine builds on top, not from scratch):**
- Schwab API access working with OAuth (existing `ezoptionsschwab.py` + `options_fetcher.py`).
- GEX/DEX engine running, 60-sec snapshots for SPY/SPX/QQQ/IWM, 10-min for stocks. Writes to `GexSnapshot` and `MacroSnapshot` Prisma tables.
- Zero-gamma already computed and stored.
- Expected Move engine writes to `ExpectedMove` / `ExpectedMoveHistory` / `RthExpectedMove`.
- ICT engine (`pa.py`) computes FVGs, order blocks, sweeps, BPRs, IFVGs vectorized from parquet.
- Economic calendar populated from ForexFactory into `EconomicEvent`.
- Trade journal Prisma schema already includes `Trade`, `Account`, `Strategy`, `Playbook`, `ResearchStrategy`, `ResearchRun`, `MarketCondition`, `Tag` — substantial existing infrastructure.
- Dolt database has 7 years of daily IV/HV history for SPY, AAPL, NVDA, TSLA, MSFT, AMZN, GOOGL, AMD. Updated weekly via cron.

**Two reference documents the user provided that informed the design:**
- `OPTIONS_INVENTORY.md` — the user's existing options/market-data infrastructure inventory
- `PRISMA_DATABASE_SCHEMA.md` — the existing Prisma schema reference

These are not duplicated here but should be reviewed if doing infrastructure work.

---

## 3. The seven strategies (locked)

This was the most-discussed scope decision. The final lineup:

| # | Strategy | Why it's in | Underlyings |
|---|----------|-------------|-------------|
| 1 | **Wheel** (CSP→CC chain) | Foundational. Teaches assignment, put-call parity, share ownership psychology. | NVDA, TSLA, AAPL, GOOGL, MSFT, AMZN |
| 2 | **0DTE Put Credit Spreads** | User's home court. Tests whether existing skill is real edge or familiarity. | SPY, SPX |
| 3 | **45 DTE Credit Spreads** | Tastytrade baseline. Comparison to 0DTE. | SPY, NVDA, TSLA, IWM |
| 4 | **Mean Reversion to EM** | Uses user's GEX/EM specialty. Tests the dealer hedging hypothesis. | SPY, SPX |
| 5 | **GEX Wall Break Debit Spreads** | Only long-premium directional strategy. Tests whether walls produce tradeable breakouts. | SPY, SPX |
| 6 | **Income Covered Calls** | Real income on existing holdings. Practical outcome user wants. | GOOGL, TSLA, RIVN (staged) |
| 7 | **Earnings Strangles** | Teaches vega — biggest gap in user's options knowledge. | NVDA, TSLA, AAPL, GOOGL |

**Total: 41 parameterized variants across these 7 strategies.**

**Things explicitly NOT included (and why):**
- **AMD wheel/strategies:** AMD has a config gap in user's GEX pipeline (no GEX snapshots). User decided to drop AMD from v1 rather than fix it now.
- **Futures options (ES/NQ):** Defer to Phase 2. The architecture supports them but v1 is equity options only.
- **Iron condors / iron flies / ratios:** Defer. The credit spread strategies build the foundation.
- **Short strangles / straddles:** Too risky at user's stage. Acknowledged as Tastytrade staple but inappropriate.
- **"Qullamaggie-style" momentum with calls:** Not a different strategy, it's a sizing vehicle. Out of scope.
- **Calendar/diagonal spreads:** Defer to Phase 2.

---

## 4. Architecture decisions (locked)

These are the decisions you should NOT relitigate. The reasoning is preserved here so anyone picking this up understands.

### 4.1 Build alongside, not replace

The new `strategy_engine` module is **purely additive**. No existing module is modified. The engine reads from existing Prisma tables (GexSnapshot, MacroSnapshot, ExpectedMove, EconomicEvent) and consumes existing services (Schwab API wrappers, `pa.py`, parquet loaders) but doesn't change any of them.

**Why:** the user's existing pipeline works and produces good data. Touching it risks breaking it. Pure addition is safer and respects work already done.

### 4.2 Two long-running processes

1. Existing `run_options_levels.py` keeps writing GexSnapshot/MacroSnapshot every 60s — unchanged.
2. New `strategy_engine/runner.py` reads from Prisma and writes new Trade rows.

They communicate only through the database. No IPC, no shared memory, no callbacks.

**Why:** decoupling means each process can fail and restart independently. Engine downtime doesn't lose market data; pipeline downtime doesn't corrupt engine state.

### 4.3 Independent capital silos per variant

Each ResearchStrategy variant has its own Account row with `initialBalance=$25K`. Variants never share capital.

**Why:** the engine's purpose is to *compare* strategies. If they share capital, strategy A's poor performance starves strategy B and we can't tell which is actually better. Layer 2 (capital allocation across strategies) is a separate, later problem.

### 4.4 Forward-test only, no backfill

Engine starts firing trades from day one of operation. We never simulate "what would this strategy have done last quarter."

**Why:** the user doesn't have option chain history with the granularity needed. Building a backtester to half-fake historical data would consume weeks of effort to produce results we couldn't trust. Forward-testing is honest; it takes longer but the data is real.

### 4.5 ICT computed on-demand, not cached

Strategy engine calls existing `pa.py` against parquet windows when ICT context is needed. Results cached in-process for 60 seconds. **No persistent ICT storage.**

**Why:** user pushed back on a per-tick parquet cache because (a) it duplicates data already in OHLCV parquet, (b) doesn't match existing storage idiom, (c) creates cache-invalidation problems, (d) bloats storage. ICT state is **derived data** — fundamentally a function of OHLCV. Recomputing the relevant window (e.g. 200 bars of 5m) is millisecond-fast, and the per-trade ICT context gets snapshotted into `Trade.metadata` JSON when a trade fires — preserving the analyzable information without per-minute storage.

If recomputation later proves too slow, Option 3 (daily batch parquet) is a clean retrofit. The service interface (`IctService.get_context()`) doesn't change.

### 4.6 IV history via Dolt + Prisma routing, no new tables

Dolt has 7 years of daily IV/HV for 8 tickers. Existing Prisma tables (`ExpectedMoveHistory`, `RthExpectedMove`, `GexSnapshot`) have recent intraday IV. The `IvService` routes queries to the right source.

**Proxy mapping handled in existing `dolt.ts`:** SPX → SPY, QQQ → SPY, IWM → SPY. Engine doesn't reimplement.

RIVN has no IV anywhere. The income CC strategy for RIVN skips the IV filter entirely.

**Why:** the user already has the data. Building a parallel IV history table would duplicate it and create sync problems. Routing through existing tables means there's one source of truth per data type.

### 4.7 Strategy hierarchy uses existing Prisma models

This was a critical reconciliation. The user's schema already has:
- `Strategy` — category model (color, name, description)
- `ResearchStrategy` — parameterized variant
- `ResearchRun` — periodic rollup with metricsJson and grade
- `Playbook` — rule text
- `Trade` — individual trade with `metadata` JSON field
- `MarketCondition` — VIX/VVIX/ATR per trade

The engine uses these as:
- 7 rows in `Strategy` (categories like WHEEL, ZERO_DTE_PCS)
- 41 rows in `ResearchStrategy` (parameterized variants)
- 7 rows in `Playbook` (rule text for each category)
- Many rows in `Trade` linked to all three above

Only **5 new tables** are needed: `TradeLeg`, `QuoteSnapshot`, `SignalNearMiss`, `Holding`, `EarningsCalendar`.

**Why:** the user's schema authors had already thought about this structure correctly. Using existing models means the strategy engine integrates with the existing journal/dashboard infrastructure naturally.

### 4.8 Single-position-per-variant rule (v1)

Each ResearchStrategy variant can have at most one open trade at a time. If `scan()` produces a signal but one is already open for that variant, the signal is silently dropped.

**Why:** simplifies sizing, analytics, and debugging in v1. Stacking positions is a v2 feature.

### 4.9 Mid-fill assumption

All paper trades fill at the midpoint of bid/ask at signal time. Documented in `Trade.metadata.fill_assumption = "mid"`.

**Why:** simplest defensible assumption. The user committed to manually paper-trading ~20 signals in Schwab's paper account to validate this assumption against reality. If systematic slippage shows up, we add a per-strategy slippage adjustment in v1.1.

### 4.10 Wheel "stuck" rule

When wheel state is LONG_STOCK and no acceptable CC strike exists above breakeven, the engine logs `STUCK_WAITING` and waits. It does NOT sell a CC below cost basis (locking in a loss). It does NOT sell at delta > 0.15 below breakeven.

**Why:** the user wanted to learn the true cost of being stuck holding underwater shares. Selling premium below breakeven hides that cost. Waiting shows it honestly.

### 4.11 No notifications (v1)

The engine runs silently. User reviews via the weekly Rundown report.

**Why:** user explicitly didn't want notifications. Reduces noise and prevents emotional engagement with intraday signals. Real-time alerts is a v2 feature.

### 4.12 Tradier API not adopted

User evaluated Tradier as a supplementary data source. Decided to stay with Schwab only.

**Why:** Schwab already provides everything needed. Adding a second broker integration would add complexity for marginal benefit. Schwab's options data + the Dolt IV history + the existing GEX pipeline cover all required signals.

---

## 5. The state of the user's data (data audit summary)

This came from programmatic audits the user ran during design. Important context for what works and what doesn't.

| Ticker | GEX (Prisma) | Daily EM (Prisma) | IV Rank (Dolt) | Notes |
|--------|--------------|-------------------|----------------|-------|
| SPY | ✅ Full | ✅ Full | ✅ Full (7y) | All strategies ready |
| SPX | ✅ Full | ✅ Full | Proxied to SPY | Dolt adapter handles automatically |
| QQQ | ✅ Full | ⚠️ Missing | Proxied to SPY | User wants gap fixed but not blocking |
| IWM | ✅ Full | ⚠️ Missing | ⚠️ None | Use SPY-or-skip for IV; less precise |
| NVDA | ✅ Full | ✅ Full | ✅ Full (7y) | All strategies ready |
| TSLA | ✅ Full | ✅ Full | ✅ Full (7y) | All strategies ready |
| AAPL | ✅ Full | ✅ Full | ✅ Full (7y) | All strategies ready |
| GOOGL | ✅ Full | ✅ Full | ✅ Full (7y) | All strategies ready |
| MSFT | ✅ Full | ✅ Full | ✅ Full (7y) | All strategies ready |
| AMZN | ✅ Full | ✅ Full | ✅ Full (7y) | All strategies ready |
| AMD | ❌ Missing | ✅ Full | ✅ Full (7y) | Dropped from v1 (GEX gap) |
| RIVN | ❌ None | ❌ None | ❌ None | STAGED until user adds to pipeline |

**Dolt update cadence:** weekly cron (existing).
**Prisma intraday cadence:** 60s for SPY/SPX/QQQ/IWM, 10 min for stocks (existing).

**Key implication:** strategies on SPY/SPX/NVDA/TSLA/AAPL/GOOGL/MSFT/AMZN are unblocked and can fire signals from day one with full filtering. Strategies on IWM, QQQ work but with less precise IV filtering. RIVN strategy stages until user adds RIVN to the pipeline.

---

## 6. The deliverable artifact

**`STRATEGY_ENGINE_SPEC.md`** — single comprehensive markdown file, ~3,200 lines, ~113KB.

Organized in 12 sections + 3 appendices:

1. Overview — goals, scope, ticker bucket, tick cadences
2. Architectural Integration — directory layout, existing-module-table, process model, data flow, config approach
3. Net-new Prisma Models — full DSL for 5 new tables + Trade extension
4. Platform Services — 10 services with full Python dataclasses and method signatures with docstrings
5. Strategy Framework — abstract base class, lifecycle, "log every filter" convention
6. Engine Orchestration — main loop, runner, full config.yaml with every variant parameterized
7. Paper Execution & Mark-to-Market — PaperExecutor with method signatures, MTM tick sequence
8. The Seven Strategies — each fully spec'd with entry rules, exit rules, features logged, variants, class skeleton
9. Analytics & Weekly Review — AnalyticsService signatures, weekly review template, SQL query patterns
10. Seed Data & Bootstrap — first-run setup, variant naming, playbook content
11. Operational Runbook — start/stop, daily/weekly user tasks, failure modes, maintenance
12. Open Questions & Future Work — known issues, v2 candidates, success criteria

Appendices: implementation order (8-week plan), files to create (tree), glossary.

The spec is **implementation-ready** — every service has Python signatures with docstrings; every strategy has its rule table; every Prisma model is fully defined. A developer (or AI assistant) can open this in an IDE and start writing code immediately.

---

## 7. Open items requiring user action

These are pre-implementation tasks the user owns. None block starting implementation; some unblock specific strategies.

| # | Item | Blocking? | Owner |
|---|------|-----------|-------|
| 1 | Add RIVN to GEX scoring pipeline (`run_options_levels.py` config) | Blocks RIVN income CC strategy. ~4 week data accumulation. | User |
| 2 | Fix QQQ `ExpectedMoveHistory` gap (extend `api_expected_move.py`) | Non-blocking. Affects analytics richness for QQQ. | User |
| 3 | Investigate AMD GEX config gap | Non-blocking. Enables future AMD strategies in v1.2. | User |
| 4 | Validate ~20 paper trades in Schwab paper account once engine fires signals | Non-blocking. Validates mid-fill assumption. | User (after Week 4-5 of implementation) |
| 5 | Verify Dolt cron continues running (existing weekly job) | Non-blocking. Just a check. | User |

---

## 8. Where you left off (resumption guide)

**Last status:** Volume 1 (master spec) complete and delivered as `STRATEGY_ENGINE_SPEC.md`. Implementation has NOT started. User intends to implement in their IDE.

**The recommended next concrete action:**

1. Open `STRATEGY_ENGINE_SPEC.md` in your IDE.
2. Read Section 1 (Overview) and Section 2 (Architecture) for orientation.
3. Run the Prisma migration to add the 5 new tables (`npx prisma migrate dev --name strategy_engine_v1`). The exact Prisma DSL is in Section 3.
4. Create the `scripts/libs_py/strategy_engine/` directory tree per Appendix B.
5. Build `seed_data.py` first (Section 10). This validates the schema and creates the Strategy/Playbook/ResearchStrategy/Account rows.
6. Build `BrokerService` (Section 4.1) — wraps existing `ezoptionsschwab` + `options_fetcher`. Smallest service, validates the integration pattern.
7. Follow the 8-week order in Appendix A for everything else.

The first end-to-end milestone is the Wheel strategy (Appendix A, Week 4). That gives you a working strategy firing real signals against real data.

---

## 9. If you're an AI assistant joining mid-stream

Read these documents in order:

1. **This handoff document** (you're reading it). Tells you the why.
2. **`STRATEGY_ENGINE_SPEC.md`** — the what.
3. **`OPTIONS_INVENTORY.md`** (in user's repo) — what infrastructure already exists.
4. **`PRISMA_DATABASE_SCHEMA.md`** (in user's repo) — existing schema reference.

**Conventions the user established and you should respect:**
- Async Python for all I/O-bound code.
- Dataclasses (not Pydantic) for service-level data contracts.
- Existing module names are sacred — don't rename or refactor existing code.
- Prisma models use cuid IDs for new tables (matches existing convention).
- Timestamps stored as DateTime in Prisma; timezone is America/New_York for all engine logic.
- Logging via standard Python logging, output to `~/strategy_engine.log`.
- New code lives only under `scripts/libs_py/strategy_engine/` — additive, not invasive.

**Things to verify before suggesting changes:**
- Does the existing infrastructure already handle this? (Check OPTIONS_INVENTORY.md.)
- Is there an existing Prisma model for this? (Check PRISMA_DATABASE_SCHEMA.md.)
- Does the design decision in section 4 of this handoff already address this? (Don't relitigate locked decisions without strong cause.)

**The user's preference:** they push back well, ask probing questions, and don't want unnecessary complexity. When in doubt, propose the simpler path. If you're tempted to add a new abstraction layer, first check if existing infrastructure handles it.

---

## 10. Versions, references, and contact

- **Spec version:** 1.0 (2026-05-17)
- **This handoff:** 1.0 (2026-05-17)
- **Spec file:** `STRATEGY_ENGINE_SPEC.md`
- **User's repo:** `tvDownloadOHLC` (paths reference this root)
- **Database:** SQLite via Prisma at `web/prisma/dev.db`
- **Dolt database:** `data/options/options/`
- **Parquet data:** `data/*.parquet`

If revisiting in 3+ months, expect:
- Dolt to have more data (weekly cron continues)
- Prisma intraday tables to be much larger (60s cadence)
- RIVN data to be available (if user added it to pipeline)
- Some strategies may be partially implemented; check `scripts/libs_py/strategy_engine/` for what exists

---

**End of handoff document. The spec is the source of truth for implementation details; this document is the source of truth for context and decisions.**
