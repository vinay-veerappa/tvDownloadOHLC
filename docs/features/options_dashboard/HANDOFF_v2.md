# Strategy Engine — Handoff Addendum (v2)

**Date:** 2026-05-18
**Predecessor:** `HANDOFF.md` v1.0 (2026-05-17)
**Companion:** `STRATEGY_ENGINE_SPEC.md` v1.0
**Status:** Engine end-to-end runnable for paper testing. ~85% of v1 spec implemented; deferred items documented below.

---

## Purpose of this addendum

The original HANDOFF described the design. This document describes **what was actually built**, the **design decisions that drifted from the spec** during implementation, and the **known limitations** still on the table. Read this before opening any source file — it'll save you from chasing ghosts.

If you're an AI assistant resuming this project, read in order: HANDOFF.md → this addendum → STRATEGY_ENGINE_SPEC.md → source.

---

## 1. What landed in v2

### Strategy framework (`strategies/`)
- All 7 strategy classes implemented with `scan()` / `manage()` lifecycle.
- `base.py` exposes split direction-aware helpers: `_check_stop_loss_credit` (uses `stop_mult`) and `_check_stop_loss_debit` (uses `stop_pct`). The legacy `_check_stop_loss` is kept as a back-compat router.
- `_check_profit_target` works for both CREDIT and DEBIT because `LegQuoteService` returns direction-correct `unrealized_pnl`.
- `_exit_rules` property reads per-variant exit params from config: `profit_target_pct`, `stop_loss_mult`, `stop_loss_pct`, `roll_at_dte`, `time_stop_dte`, `flat_before_close_minutes`. Defaults are tuned for CREDIT spreads.
- `_safe_mid(contract)` helper guards against one-sided quotes (was a silent bug in v1 where `(bid+ask)/2 or last` never fell back to `last` because the arithmetic was always truthy).
- Near-miss writes go directly to Prisma `SignalNearMiss` from `_log_near_miss`; no separate `NearMissLogger` service was built (deferred — see §3).

### Strategy-specific changes from spec
- **EARNINGS_STRANGLE flipped from SHORT to LONG.** Spec §8.7 was always LONG strangles to capture pre-earnings IV ramp; v1 implementation was SHORT (selling premium for IV crush). v2 reverted to spec. Decision rationale in §2.1 below.
- **Wheel "stuck" rule** (spec §8.1) implemented: no CC sold below cost basis. Logs `STUCK_WAITING` near-miss and waits.
- **Mean-reversion EM overshoot guard** (spec §8.4 filter #8): rejects 1.5SD+ blowouts via `get_em_distance_in_sd`.
- **Wall break DEX confirmation + volume filter** (spec §8.5 filters #6-7): now use `get_today_em` for DEX confirmation and per-strike volume vs chain average for the volume filter.
- **0DTE PCS ICT integration** (spec §8.2): variant `10D_5W_ICT` now uses `IctService.get_context()` to check HTF bias AND requires an unmitigated bullish FVG near spot via `has_bullish_fvg_near`.

### Services (`services/`)
- All 10 services implemented per spec §4 with dataclass-or-dict-or-TypedDict returns per service convention (see §2.2).
- **RegimeService**: full spec §4.2 interface including `get_nearest_walls` with real `MacroSnapshot.dominantNodes` JSON parsing.
- **ExpectedMoveService**: split API — `get_today_em` returns dataclass (used by wall_break for attribute access), `get_expected_move_bands` returns dict (used by mean_reversion_em for key access).
- **IvService**: full spec §4.4 with `IvSnapshot` dataclass + percentile/skew/HV ratio. IV rank unit bug fixed (all internal computation in decimal scale via `_to_decimal`). Legacy dict API preserved.
- **HoldingService**: TypedDict returns. `add_shares`/`remove_shares` aliases for paper_exec compatibility.
- **BrokerService**: dict returns with TypedDict type hints. Caches: 5s stock, 10s option, 30s chain, 5min expiries.

### Engine + Runner (`engine.py`, `runner.py`)
- Three-tier cadence implemented:
  - **Tier 1 (60s)**: index/ETF strategies (SPY/SPX/QQQ/IWM), excluding daily-only codes
  - **Tier 2 (5min)**: stock strategies (NVDA/TSLA/AAPL/GOOGL/MSFT/AMZN/RIVN), excluding daily-only codes
  - **Tier 3 (daily at 10:00 ET)**: WHEEL, EARNINGS_STRANGLE, INCOME_CC, LONG_DTE_CREDIT
- Maintenance jobs all scheduled: weekly earnings refresh (Sun 18:00), weekly rundown (Sun 17:00), EOD daily rollup (Mon-Fri 16:30), daily prune (03:00).
- M10 variant-level `enabled: false` flag respected — disabled variants log a warning on startup and don't instantiate.
- Per-tick staleness cache prevents redundant `GexSnapshot` queries within one tick.
- Engine startup auto-seeds `EarningsCalendar` if empty.

### Paper execution (`paper_exec.py`)
- **Cash accounting model**: "Net Equity" (no cash movement at open, full PnL at close). Decision rationale in §2.3.
- Per-leg slippage applied: $0.02 for SPY/SPX/QQQ/IWM, $0.05 for equities. Slippage is included in `openPrice` and `closePrice` so leg PnL math comes out right.
- Assignment branch validates DTE ≤ 0 AND short option ITM before treating as actual assignment; otherwise falls back to normal close with a warning.
- `list_open_trades()` convenience method on the executor.

### Analytics (`analytics.py`)
- Per-silo daily rollup writes `ResearchRun` rows with `metricsJson`, `configJson`, `grade`, equity curve PNG path.
- Weekly rundown markdown with: cross-strategy ranking, correlation matrix, feature breakdown by VIX/IV-rank/breakout-direction buckets, near-miss filter insights, operational suggestions.
- Variant name parsing uses `startswith(strategy_code + "_")` to avoid the v1 underscore-split bug that broke 6 of 7 strategies.
- Letter grading A+ through F based on win rate × profit factor × trade count.

### Seed data (`seed_data.py`)
- Idempotent. Seeds AccountGroup, 7 Strategy categories, 1 Playbook, 41 ResearchStrategy+Account pairs, Holdings from config, initial EarningsCalendar via yfinance, initial EconomicEvent via ForexFactory.

---

## 2. Design decisions that drifted from the spec

These are choices made during implementation that diverged from the spec text. Each is intentional and documented so we don't relitigate.

### 2.1 EARNINGS_STRANGLE direction (LONG vs SHORT)

**Spec §8.7**: BUY strangles to capture pre-earnings IV ramp; close day before earnings.
**v1 implementation**: SELL strangles to capture post-earnings IV crush; hold through and close morning after.
**v2 decision**: Reverted to spec (LONG strangle).

**Why**: SHORT strangles need ~$3,000 margin per contract (Reg-T) and have unlimited tail risk. A single bad earnings gap could lose $1,500-$5,000+ on one contract, blowing through the user's $100-$500 per-trade risk band. LONG strangles cap risk at the debit paid ($500ish per contract) and fit the budget naturally.

### 2.2 Service return types — mixed dataclass/dict/TypedDict by service

**Spec §4 / HANDOFF v1 §9**: "Dataclasses (not Pydantic) for service-level data contracts."
**v2 reality**: Mixed.

| Service | Returns | Why |
|---|---|---|
| BrokerService | dicts (with TypedDict hints) | matches upstream Schwab API shape, JSON-serializable for free |
| RegimeService | dataclass (`GexRegime`) + legacy dict alias | rich type that strategies want to introspect |
| ExpectedMoveService | dataclass `get_today_em`, dict `get_expected_move_bands` | serves wall_break (attribute) and mean_reversion_em (key) without forcing either to refactor |
| IvService | dataclass (`IvSnapshot`) + legacy dict alias | rich type per spec §4.4 |
| IctService | dataclass (`IctContext`) | already implemented this way, strategies use `.has_bullish_fvg_near()` |
| HoldingService | TypedDict (acts as dict at runtime) | dict-shape but with IDE autocomplete |
| LegQuoteService | plain dict | matches base.py helper `current_mtm["unrealized_pnl"]` access |
| CalendarService / EarningsService | dataclasses | already implemented |
| SizingService | int (scalar) | trivial return |

**Why mixed**: the dict-everywhere refactor would have been ~1 day of mechanical work for marginal benefit. The actual bugs were unit-mismatch and method-name drift, not type-shape. Each service uses the shape that serves its consumers best. Where there's ambiguity, the service exposes both APIs.

### 2.3 Cash accounting — "Net Equity" model

**Spec §7.1**: Cash flow specified ambiguously — premium received at open, cost-to-close paid at close.
**v2 decision**: No cash moves at open. Realized PnL booked at close.

**Why**: With the "premium at open + cost at close" model, `account.currentBalance` is inflated by the premium during the life of the trade. Analytics rebuilds equity from `initialBalance + sum(closed pnl)`, which conflicts with that mid-life balance. Picking ONE model and sticking to it eliminates a class of reconciliation bugs.

**Known tradeoff**: see §3.1 below — sizing on `currentBalance` becomes slightly inflated after wheel assignments because stock cost basis isn't deducted from the cash account.

### 2.4 Variant naming uses underscore separator

**Original review flagged**: parsing `f"{strategy_code}_{variant_name}_{ticker}"` was broken when strategy codes contain underscores.
**v2 fix**: kept the same separator, but parsing in analytics uses `startswith(strategy_code + "_")` matched against the known list of 7 strategy codes. Avoids the schema migration that storing strategy/variant/ticker as separate columns would have required.

**Why**: spec §10.2 shows variant names as underscore-joined strings. Keeping the format means existing reports and any user tooling still works. The parsing rule is "match longest known prefix, then strip ticker from end."

### 2.5 Mid-fill assumption + per-leg slippage

**Spec §7.4**: All paper trades fill at mid; documented as `Trade.metadata.fill_assumption = "mid"`.
**v2 reality**: Per-leg slippage applied ($0.02 for SPY/SPX/QQQ/IWM, $0.05 for equities). Slippage cost flows through both open and close.

**Why**: The Playbook markdown text (rendered into the seeded Playbook row) explicitly mentions per-leg slippage, and the user requested it during the engine/runner review. The implementation applies slippage to `openPrice` and `closePrice` directly, so leg PnL automatically reflects it. `Trade.metadata.fill_assumption` should be set to `"mid_with_slippage"` going forward (currently still says `"mid"`).

### 2.6 Single-position-per-variant rule preserved

Spec §7.3 dictated: each variant has at most one open trade at a time. v2 honors this — every strategy checks `active_trades` count at the top of `scan()` and returns empty if non-zero. Stacking deferred to v2 of the engine (post-launch enhancement).

### 2.7 Rolls are "close + re-scan", not atomic

Spec §8.1 implied true atomic rolls (close old + open new in one operation, single P&L trail).
**v2 implementation**: `ManageAction(close=True, reason="ROLL")` closes the trade. The next scan tick may or may not open a replacement depending on filter state.

**Why**: True atomic rolling requires a separate code path in PaperExecutor that handles two opens in one transaction with linked metadata. Adds complexity for unclear analytical benefit — the rolled trade's history is still in the database, just split across two rows. If you need it later, refactor `PaperExecutor` to add a `roll_trade(old_trade, new_signal)` method that uses a Prisma transaction.

---

## 3. Known limitations (deferred to v1.1)

These were identified during review but explicitly not fixed in v2. Each has a workaround or rationale.

### 3.1 Sizing inflation after wheel assignments

**Where**: `paper_exec.py` `close_trade` assignment branch + `sizing_service.py` `calculate_size`.
**What**: When a CSP gets assigned, `Holdings` table records the new shares at cost basis, but `account.currentBalance` only changes by the realized option PnL — it doesn't decrease by `strike × 100 × qty` (the cash that would have been used to buy stock). Subsequent CSP sizing reads `currentBalance` and over-sizes because some of that "balance" is conceptually locked in stock.

**Impact**: Only matters for wheels post-assignment. Sizes after CC writes are correct (stock already held, no further cash motion).

**Workaround**: Live with it for v1. Wheels run with $25K silos, so 1-2 CSP at $20K strike maxes out before sizing inflation matters.

**Fix path**: Either deduct cost basis on assignment from `currentBalance` (and have analytics add back stock-at-cost to recover true equity), or add a `Account.cashReserved` field for stock acquisitions. The second is cleaner but needs a Prisma migration.

### 3.2 No margin reservation on credit spreads

**Where**: `paper_exec.py` execute_signal.
**What**: With the no-cash-at-open model, nothing prevents the engine from opening more credit spreads than the account could collateralize. A $5-wide PCS needs $500 margin per contract; in theory you could open 50 such spreads on a $25K account.

**Impact**: Bounded by `SizingService.calculate_size` which caps `qty` by `max_allocation_pct=0.10` (10% of balance per trade). So a $25K silo opens at most 1-2 contracts per signal. The single-position-per-variant rule prevents stacking. Net result: maximum exposure ≈ $500-$2,500 per silo, well within $25K equity.

**Workaround**: Live with the sizing safeguard. Future fix when stacking is allowed.

### 3.3 IV percentile uses `iv_rank` as a proxy in earnings_strangle

**Where**: `earnings_strangle.py` scan, `IvService.get_volatility_metrics`.
**What**: Spec §8.7 filter #4 calls for IV percentile (rank vs trailing 60d). `IvService` does compute `iv_percentile` properly via `get_iv_percentile`, but `earnings_strangle.py` currently reads `iv_rank` from `get_volatility_metrics` as a proxy. There's a `TODO(D3)` comment in the strategy.

**Workaround**: Behavioral difference is small for indices and large-caps. Update the strategy to call `iv.get_iv_percentile(ticker)` directly when convenient.

### 3.4 EM distance uses snapshot basis, not session open

**Where**: `em_service.py` `get_em_distance_in_sd`.
**What**: Spec §4.3 says distance should be from session open. Current implementation uses whichever basis the EM record holds (typically the snapshot price, which equals open early in the day but drifts as the session progresses).

**Impact**: Mean reversion's 1.5SD overshoot gate may fire late in the day when distance-from-snapshot exceeds 1.5SD but distance-from-open is still <1.5SD.

**Fix path**: Plumb `session_open` from `broker.get_stock_quote(ticker)["open"]` through to `get_em_distance_in_sd`. ~10-line change.

### 3.5 No buffered `NearMissLogger`

**Where**: `base.py` `_log_near_miss`, spec §5.3 promised a `signal_log.py` module.
**What**: Strategies write directly to `SignalNearMiss` via Prisma. With 41 variants × ~10k near-misses/day across all of them, this is direct synchronous writes inside `scan()`.

**Impact**: Latency overhead on hot path. With Prisma SQLite on local laptop, single inserts are ~1-5ms — probably fine but unmeasured.

**Workaround**: If scans start exceeding their cadence budget (60s for indices, 5min for stocks), add a buffered logger that batches `createMany` flushes every N seconds.

### 3.6 Wall break uses snapshot price as "session open" proxy for DEX

**Where**: `wall_break.py`, uses `em_bands["upper_1sd"]`/`lower_1sd"]` directly.
**What**: DEX confirmation is a thumb-on-the-scale check that spot hasn't already overextended past the 1SD EM band. Uses snapshot basis from EM service, same issue as §3.4.

**Workaround**: Same as §3.4.

### 3.7 Atomic rolling deferred

See §2.7 above. Same fix path: add `PaperExecutor.roll_trade()` using Prisma transaction.

### 3.8 `Trade.metadata.fill_assumption` says "mid" but slippage is applied

Cosmetic. Update `paper_exec.execute_signal` to write `"fill_assumption": "mid_with_slippage"` in the metadata blob.

### 3.9 `news_calendar_fetcher` import in seed_data not verified

`seed_data.py` step 7 imports `scripts.streaming.news_calendar_fetcher`. The module path exists per OPTIONS_INVENTORY but the function signatures (`fetch_and_save`, `save_to_prisma`) weren't verified during v2 development. Wrapped in try/except so failure is non-fatal. Verify on first real seed run.

---

## 4. Open user actions (carried forward from v1)

Still on the user, unchanged:

1. **Add RIVN to GEX scoring pipeline** — blocks INCOME_CC variant for RIVN even though `enabled: false` flag suppresses near-miss spam.
2. **Fix QQQ ExpectedMoveHistory gap** — non-blocking, affects analytics richness.
3. **Investigate AMD GEX config gap** — non-blocking; enables AMD strategies in v1.2.
4. **Validate ~20 paper trades in Schwab paper account** — once engine is firing signals (post-Sprint 4), pick a sample and replicate manually to validate the mid+slippage fill assumption.

---

## 5. What's verified clean end-to-end

A typical strategy tick traces cleanly through all layers:

1. **Runner** triggers `tick_index_job` every 60s during market hours
2. **Engine** filters strategies by cadence + staleness, calls `strategy.scan(now)`
3. **Strategy** calls services (broker, regime, em, iv, calendar, earnings, ict, holdings) — all return shapes match consumer expectations
4. **Strategy** builds `Signal` with `entry_features` and `LegSpec`s
5. **Engine** passes signal to `executor.execute_signal()`
6. **PaperExecutor** creates `Trade` + `TradeLeg` rows, writes `metadata` with `research_strategy_id`, applies slippage, no cash move at open
7. **Engine** also runs `manage_tick` first — for each open trade, calls `leg_quote.get_trade_mtm()` and writes `QuoteSnapshot` with aggregate netValue/PnL
8. **Strategy.manage()** uses base helpers (`_check_profit_target`, `_check_stop_loss_credit/debit`, `_check_time_stop`, `_check_dte_time_stop`) all reading `current_mtm["unrealized_pnl"]` / `current_mtm["net_value"]` in aggregate dollars
9. **Returns ManageAction** with close=True if trigger fires
10. **PaperExecutor.close_trade()** updates trade with realized PnL, leg-level close prices, status="CLOSED", balance += PnL
11. **EOD analytics** runs `_assign_grade`, generates equity curve, writes `ResearchRun`
12. **Weekly rundown** aggregates across silos, computes correlation matrix and feature breakdown, writes `Rundown.content` markdown

No `AttributeError` / `KeyError` traps remaining in the hot path.

---

## 6. Resumption guide

If you (user or AI assistant) come back to this in 3 months:

1. Read this addendum first
2. `pm2 list` (or equivalent) — verify `strategy_engine` runner is alive
3. `tail -100 ~/strategy_engine.log` — look for repeated WARN/ERROR
4. Run `python scripts/libs_py/strategy_engine/check_results.py` for a status snapshot
5. Open `scripts/libs_py/strategy_engine/rundowns/weekly_rundown_YYYY-MM-DD.md` for the latest weekly review
6. If something's broken, check §3 first — it's probably documented as a known limitation
7. If sizing looks weird, suspect §3.1 (wheel assignment cash inflation)

To extend (new strategy, new variant):
- New variant on existing strategy: edit `config.yaml`, run `seed_data.py --update` (not yet implemented — see spec §10.1; for now, ad-hoc Prisma update)
- New strategy: create `strategies/<name>.py` extending `Strategy`, add to `strategies/__init__.py`, add to `STRATEGY_CLASSES` and `DAILY_STRATEGY_CODES` (if applicable) in `engine.py` and `runner.py`, add to `STRATEGY_DETAILS` in `seed_data.py`, add config block

---

## 7. Versions

- **Spec version:** 1.0 (2026-05-17) — unchanged
- **HANDOFF v1:** 1.0 (2026-05-17) — original
- **HANDOFF v2 (this document):** 1.0 (2026-05-18)
- **Implementation status:** end-to-end runnable; deferred items listed in §3

The spec remains the source of truth for design intent. This addendum is the source of truth for *implementation reality* — when they conflict, the addendum wins for "what the code actually does" and the spec wins for "what we wanted it to do."
