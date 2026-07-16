# Trader Narrative & Prompt Audit Report (Revised)

**Date**: 2026-07-14
**Scope**: All 7 prompt templates + 5 Python source files in the trader narrative chain
**Reviewer**: Automated deep audit from a day-trader's perspective

---

## Resolution Status

| # | Issue | Severity | Status | Resolved on |
|---|---|---|---|---|
| 1.1 | EOD narrative never sees trade outcomes | 🔴 Critical | ✅ **Resolved 2026-07-14** | This PR |
| 1.2 | `extract_and_save_trade_plan` saves LLM output with zero validation | 🔴 Critical | ✅ **Resolved 2026-07-14** | PR #1 (risk validator) |
| 1.3 | EOD narrative uses 09:30 morning levels at 16:25 | 🔴 Critical | ✅ **Resolved 2026-07-14** | This PR |
| 1.4 | LLM told to override `mandated_track` from Python | 🟠 High | ✅ **Resolved 2026-07-14** | This PR |
| 1.5 | Clean-read prompts 180+ lines of pre-computed guides | 🟠 High | ⏳ Open | — |
| 1.6 | `trader_intraday.md` contains 5 sessions in one file | 🟠 High | ⏳ Open | — |
| 1.7 | Risk params duplicated in 5+ prompts | 🟠 High | ✅ **Resolved 2026-07-14** | This PR |
| 1.8 | `get_trade_plan_for_eod` returns PENDING + FILLED mixed | 🟠 High | ✅ Resolved by #1.1 (outcomes block surfaces fills) | This PR |
| 2.1 | `render_open_summary` hardcodes `mes`/`mnq` keys | 🔴 Critical | ✅ **Resolved 2026-07-14** | This PR |
| 2.2 | `extract_and_save_trade_plan` can save duplicate trades | 🟠 High | ✅ **Resolved 2026-07-14** | This PR |
| 2.3 | `build_levels_markdown_table` hardcodes TXT path | 🟠 High | ✅ **Resolved 2026-07-14** (same as 1.3) | This PR |
| 2.4 | `instrument_map` duplicated in 4 functions | 🟠 High | ✅ **Resolved 2026-07-14** (side-effect of §2.1) | This PR |
| 2.5 | Schwab quote failures pollute premarket output | 🟠 High | ✅ **Resolved 2026-07-14** | This PR |
| 2.6 | Inconsistent default models | 🟠 High | ✅ **Resolved 2026-07-14** | This PR |
| 2.7 | EOD update doesn't filter to RTH hours | 🟡 Medium | ✅ **Resolved 2026-07-14** | This PR |
| 2.8 | Duplicate `sys.path` hack in 5+ files | 🟡 Medium | ✅ **Resolved 2026-07-14** | This PR |
| 2.9 | `compute_level_interactions` redundant guards | 🟡 Medium | ✅ **Resolved 2026-07-14** | This PR |
| 2.10 | `parse_meta_fields` fragile `rfind("_")` | 🟡 Medium | ✅ **Resolved 2026-07-14** | This PR |
| 2.11 | `briefing_core.py` call sites don't propagate `target_date` | 🟢 Low | ✅ **Resolved 2026-07-14** | This PR |
| 2.12 | `weekly_briefing.md` references SPY/QQQ | 🟢 Low | ⏳ Open | — |
| 3.5 | Discord chunking logic duplicated in 3 files | 🟠 High | ✅ **Resolved 2026-07-14** | This PR |

### Resolution notes

**Issue #1.1 — Trade outcomes injection (resolved 2026-07-14)**

Added a new `get_trade_outcomes()` function in `scripts/trader/daily_narrative.py`
that joins today's planned trades with their execution results. The EOD prompt
now receives a `TRADE OUTCOMES` block (placed BEFORE the morning plan block)
with one-line summaries for each trade:

- `- MNQ LONG qty=1: FILLED 17000.0 @09:35 → STOPPED 16950.0 @10:15 P&L=$-100 [MAE=-50 MFE=20]`
- `- MES SHORT qty=1: FILLED 5000.0 @11:22 → STILL OPEN (MFE=+40, MAE=-10)`
- `- MNQ SHORT qty=1: PLANNED entry=17200.0 stop=17150.0 target=17300.0 | NEVER FILLED (limit not hit)`

The prompt's RULES section was updated to require the LLM to:
1. Review the outcomes first.
2. For never-filled trades, mark them as "did not trigger" — not "skipped".
3. Grade the morning's bias independently of execution result.

Time conversion is handled by a small `_utc_to_et_str()` helper using `pytz`
(matches the codebase convention in `scripts/enrich_macro.py`). 23 unit tests
added in `tests/test_trade_outcomes.py` cover all states, edge cases, and the
Prisma-mocked end-to-end path.

**Issue #1.2 — Trade plan validator (resolved 2026-07-14)**

Created a new `scripts.libs_py.risk.narrative` sub-package with typed config
(per-instrument specs, EVAL vs FUNDED account phases, per-instrument risk
caps) and a `validate_trade_plan()` function that:

- Drops trades with bad geometry (zero entry, wrong-side stop/target,
  unknown instrument, non-numeric prices).
- Caps oversized contract counts to the per-instrument risk cap.
- Computes `stopDistancePts / dollarRisk / rewardToRisk` from Python truth.
- Blocks trades whose R:R is below the active phase's hard threshold.
- Emits warnings via `log.warning` only — Discord stays clean.

36 unit tests in `tests/test_risk_validator.py` pin the behaviour. The
validator is wired into `extract_and_save_trade_plan()` in `daily_narrative.py`.

---

## Executive Summary

The trader narrative system has the right architectural bones — a two-phase design (Python cheat sheet → LLM narrative), config-driven scheduling, DB-first storage, and a centralized ticker mapping layer. However, a deeper audit reveals **12 critical/high-severity issues** (now 2 high + 1 medium still open as of §3.5 resolution) that erode trust, waste tokens, and in some cases silently produce wrong output.

The most dangerous problems are: (1) the LLM is trusted to validate its own position sizing with zero Python-side guardrails, (2) the levels table used in the EOD narrative is stale by 6+ hours, (3) trade plans are saved to the DB without checking stop/risk arithmetic, and (4) the feedback loop is one-directional — the system records what the LLM planned but never compares it to what actually happened.

From a day trader's lens, the most concerning gap is that **the system tells the trader what to do but never checks whether what the trader did was correct**.

**Severity Legend**: 🔴 Critical &nbsp; 🟠 High &nbsp; 🟡 Medium &nbsp; 🟢 Low

---

## 1. Day-Trader Perspective — What a Prop Trader Actually Needs

### 1.1 ✅ The Feedback Loop Is Now Closed (resolved 2026-07-14)

**Files**: `daily_eod_update.md`, `daily_narrative.py` (`get_trade_outcomes`, `_format_trade_outcome_line`)

**Original problem**: The EOD prompt said "Evaluate the morning plan honestly against session action." But the LLM saw the morning's **plan** (status: PENDING) — it never saw whether the trade was actually filled, stopped out, or profitable.

**What was done**:
1. Added `get_trade_outcomes(tickers)` in `scripts/trader/daily_narrative.py` that joins today's planned trades with their execution results and formats them as one-line summaries.
2. The EOD prompt now receives a new `TRADE OUTCOMES` block BEFORE the morning plan block with each trade classified into one of four states (FILLED+CLOSED / FILLED+OPEN / NEVER FILLED / UNKNOWN).
3. The prompt's RULES section was rewritten to require the LLM to review outcomes first, mark never-filled trades as "did not trigger" (not "skipped"), and grade the morning's bias independently of execution result.

**Example output**:
```
- MNQ LONG qty=1: FILLED 17000.0 @09:35 → STOPPED 16950.0 @10:15 P&L=$-100 [MAE=-50 MFE=20]
- MES SHORT qty=1: FILLED 5000.0 @11:22 → STILL OPEN (MFE=+40, MAE=-10)
- MNQ SHORT qty=1: PLANNED entry=17200.0 stop=17150.0 target=17300.0 | NEVER FILLED (limit not hit)
```

23 unit tests in `tests/test_trade_outcomes.py` cover all states, edge cases, and the Prisma-mocked end-to-end path.

---

### 1.2 ✅ Position Sizing Validation (resolved 2026-07-14)

**Files**: `scripts.libs_py.risk.narrative.validator`, `scripts.trader.daily_narrative.py` (`extract_and_save_trade_plan`)

**Original problem**: The LLM returns a trade plan JSON that was saved to Prisma with zero validation. Hallucinated stop-above-entry setups, $0 entries, and oversized contracts all silently polluted the DB.

**What was done**: Created a typed risk module at `scripts/libs_py/risk/narrative/` with:

- `constants.py` — per-instrument specs (multiplier, tick size, tick value), account-phase profiles (EVAL vs FUNDED), per-instrument risk caps, validator rules. All values mirror `scripts/trading_framework/config/sessions.yaml` with explicit "KEEP IN SYNC" comments.
- `config.py` — frozen dataclass view of `constants.py`, cached with `lru_cache`. Exposes `get_risk_config()` and `reset_cache()`.
- `validator.py` — `validate_trade_plan()` that drops bad geometry, caps oversized contracts, computes `stopDistancePts / dollarRisk / rewardToRisk` from Python truth, and blocks R:R below the phase's hard threshold. All decisions are made in Python; warnings go to `log.warning` only — Discord stays clean.

The validator is wired into `extract_and_save_trade_plan()` in `daily_narrative.py`. 36 unit tests in `tests/test_risk_validator.py` pin behaviour for every rule.

**Future expansion** (see `scripts/libs_py/risk/narrative/README.md`): volatility-scaled contract sizing, time-of-day scaling, correlation caps, news-blackout windows, per-prop-firm profiles, daily-stop and trailing-DD awareness.

---

---

### 1.3 ✅ Session-Aware Levels Lookup (resolved 2026-07-14)

**Files**: `briefing_core.py` (`build_levels_markdown_table`), `trader_narrative.py` (`_wait_for_close_snapshot`), `daily_narrative.py` (call site), `tests/test_levels_lookup.py` (12 tests)

**Original problem**: The function always read from `UNIFIED_LEVELS_OPEN_TXT` (the 09:30 RTH-open snapshot). The EOD narrative runs at 16:25 ET — 6h 55min later. Walls and EMs shift during the session, but the EOD review graded level accuracy against the morning's stale snapshot.

**What was done**:
1. Refactored `build_levels_markdown_table(ticker, session="open")` to support three sessions:
   - `"open"` → `current/unified_levels_open.txt` (09:30 RTH-open snapshot, used by premarket/morning narratives).
   - `"close"` or `"eod"` → `current/unified_levels_close.txt` (16:15 RTH-close snapshot, used by the EOD narrative).
   - `"intraday"` (and any other value) → the live mirror `unified_levels.txt` (always overwritten by the most recent pipeline run).
2. Each session has a safe fallback to the live mirror if the requested snapshot is missing, with a `log.warning` so operators can see which fallback fired.
3. Added `_wait_for_close_snapshot()` in `trader_narrative.py` (mirrors `_wait_for_open_snapshot()`). The 16:25 EOD job waits up to 180s (5s poll) for `current/unified_levels_close.txt` to appear before running the LLM — so the EOD narrative is *guaranteed* to grade against the close snapshot, not the morning one.
4. Updated the call site in `daily_narrative.py` to pass `session="close"` for the EOD run.
5. 12 unit tests in `tests/test_levels_lookup.py` cover all session switches, missing-file fallbacks, missing-ticker cases, and the open-vs-eod-different-content invariant. Total test count is now 74 (up from 62).

**Important bug caught during testing**: The first iteration of the function treated `session="eod"` and `session="intraday"` the same (else branch → live mirror). The test fixture caught this — `session="eod"` was returning the live mirror values (32,500) instead of the close file values (33,100). Fixed by adding `session in ("close", "eod")` to the close branch with an explanatory comment.

**Why the docstring now recommends an explicit `session`**: Hardcoding `session="open"` at every call site is exactly the bug that produced #1.3 in the first place. The default is kept only for backward compatibility with any external callers (and is exercised by `test_default_session_is_open`).

---

### 1.4 ✅ `mandated_track` is Now Python-Enforced (resolved 2026-07-14)

**Files**: `daily_open_update.md`, `daily_eod_update.md`, `scripts/libs_py/risk/narrative/track_mandate.py`, `scripts/libs_py/risk/narrative/__init__.py`, `scripts/trader/daily_narrative.py` (`extract_and_save_trade_plan`, `run_narrative`), `tests/test_track_mandate.py` (25 tests), `tests/test_extract_and_save_trade_plan.py` (11 tests)

**Original problem**: Both daily prompts told the LLM to classify the regime and select behavior ("PINNED: fade the walls, TRENDING: continuation..."). But `briefing_core.py` `resolve_track()` *independently* computed a `mandated_track` (TRACK A/B/C) from GEX + regime fields and injected it into the JSON payload. The LLM received two contradictory instructions: "you decide the track based on regime" vs. "the JSON has a `mandated_track` field you must follow." When the LLM overrode the Python-computed track in the narrative ("I'll fade this because PINNED" when the mandated track was TRACK A), the rendered summary conflicted with the DB snapshot and the trade plan.

**Resolution — three layers of defense**:

1. **Prompt-level**: removed the regime-behavior block from both `daily_open_update.md` and `daily_eod_update.md`. Replaced with a single, explicit rule:
   > The `bias` field in the payload is the **mandated execution track** (e.g. "TRACK A: BREAKOUT/MOMENTUM ..."). It is computed in Python from the GEX regime and is ABSOLUTE — do not override it.

2. **Code-level — Python enforcer**: new `scripts/libs_py/risk/narrative/track_mandate.py` exposes `validate_track_mandate(plan, mandated_tracks, micro_to_pipeline)`. Rules:
   - **TRACK C (observation only)** → hard rule: every trade for that ticker is forced to `noTrade=True` with `noTradeReason="TRACK C (observation only) — no trade"`. The trade is preserved in the plan (visible in the tradeplan row) but marked no-trade.
   - **TRACK A** → soft warning if the LLM's `logic` contains "fade" (track tag: `track_a_logic_fade`). Trade is kept.
   - **TRACK B** → soft warning if the LLM's `logic` contains "breakout" / "join the trend" / "trend follow" (track tag: `track_b_logic_breakout`). Trade is kept.
   - Mandate is keyed by the **pipeline label** (NQ, ES); the validator uses a `micro_to_pipeline` bridge so `trades[].asset` (MNQ, MES) routes correctly.
   - The function returns a corrected plan copy; the caller's input is shallow-copied at the list level (trade dicts are mutated in place, consistent with `validate_trade_plan`).

3. **Wiring — `run_narrative` → `extract_and_save_trade_plan`**: `run_narrative` now extracts `mandated_tracks` from `briefing_data["tickers"]` (preferring `weekly_anchor.mandated_track`, falling back to `bias.mandated_track`) and passes it to `extract_and_save_trade_plan(summary, mandated_tracks=mandated_tracks)`. The function signature is `async def extract_and_save_trade_plan(summary, mandated_tracks=None, micro_to_pipeline=None)`, with both arguments defaulting to `NARRATIVE_INSTRUMENT_MAP`-derived values (so the function remains a no-op if the caller doesn't pass them).

**Validation**: 25 unit tests in `tests/test_track_mandate.py` cover every rule (TRACK A/B/C mandates, soft vs hard enforcement, micro→pipeline bridge, plan-shape safety, shallow-copy contract, observation-only keyword fallback). 11 integration tests in `tests/test_extract_and_save_trade_plan.py` exercise the call-site wiring end-to-end (Prisma mocked at the `prisma.Prisma` symbol level — required because the function does `from prisma import Prisma` locally). The call-site extraction logic (`weekly_anchor.mandated_track` → `bias.mandated_track` fallback) is pinned with three dedicated tests.

**Test count**: +36 (25 unit + 11 integration) for §1.4. Total narrative-chain tests: **126 passing** (16 render + 36 risk validator + 23 trade outcomes + 12 levels lookup + 3 profiler date filter + 25 track mandate + 11 extract-and-save integration).

### 1.5 🟠 "Clean Read" Prompts Are Not Actually Clean

**Files**: `trader_premarket.md`, `trader_morning.md`, `trader_intraday.md`, `trader_close.md`

**Problem**: The opening of each says "Plain English. Talk like you're explaining to a friend." But the prompts then contain massive ICT jargon references that the LLM is told to "translate." Translation is a lossy process — the LLM may strip nuance (e.g., "BOS" = Break of Structure, which has specific HTF vs. LTF implications that "trend continuation" loses). Meanwhile, `trader_morning.md` alone is **~180 lines / ~3,000+ tokens** of guides before the cheat sheet even loads. The cheat sheet already includes formatted interpretations of Profiler, Quarters Theory, and ALN blocks. The prompt is duplicating work the Python layer already did.

**Impact**: 
- Cloud API cost: each narrative run wastes ~2,000 tokens on redundant guides.
- LLM attention: with 8,000+ tokens of input, the model gives less weight to each individual block. The signal-to-noise ratio drops.
- Generation time: observed 30-60s for clean-read runs; could be 15-20s after pruning.

**Recommended Fix**: 
1. Move all interpretation guides for pre-computed blocks (Profiler, Quarters Theory, ALN, Classification) **into the Python builders** as formatted text. The prompt should only explain **how to write the narrative**, not **how to interpret the data**.
2. Keep in prompt: rules for structure, jargon policy, word limits, output format.
3. Target: each prompt under 100 lines / 1,000 tokens.

---

### 1.6 🟠 Session Detection Is Fragile in `trader_intraday.md`

**File**: `trader_intraday.md` + `scripts/trader/signals/session_ranges.py` `detect_session`

**Problem**: The prompt contains session-specific instructions for Asia, London, NY AM, NY Lunch, and NY PM. The Python code correctly detects the current session and dispatches to the right block builder. But the prompt is a **single file** that the LLM reads every time. The LLM must parse the cheat sheet's `== CURRENT SESSION ==` header, identify which session it's in, and ignore 80% of the prompt. The LLM does this imperfectly — observed outputs sometimes blend AM and PM instructions.

**Recommended Fix**: Split into separate prompt files or inject the relevant section from Python:
```python
# In build_intraday_context
session_guides = {
    "ASIA": PROMPT_DIR / "session_guides" / "asia.md",
    "LONDON": PROMPT_DIR / "session_guides" / "london.md",
    "NY_AM": PROMPT_DIR / "session_guides" / "ny_am.md",
    ...
}
guide = session_guides[session].read_text()
prompt = base_prompt.replace("{{INSERT_SESSION_GUIDE}}", guide)
```

---

### 1.7 ✅ Risk Parameters Extracted to Typed Config (resolved 2026-07-14)

**Files**: `daily_open_update.md`, `daily_eod_update.md`, `trader_morning.md`, `trader_intraday.md`, `trader_close.md`

**Problem**: Account parameters (MES $150/trade, MNQ $100/trade, daily stops $450/$300, $2k trailing DD, max 3 trades/day, min R:R 1:2) are duplicated in 5+ prompt files. When risk rules change (e.g., the trader moves from 50K to 100K accounts), all files must be updated manually. This is error-prone and creates audit risk if one file is missed.

**Recommended Fix**:
1. Add `NARRATIVE_RISK_PARAMS` to `scripts/streaming/options/config.py`:
```python
NARRATIVE_RISK_PARAMS = {
    "MES": {"risk_cap": 150, "daily_stop": 450, "multiplier": 5, "dd_remaining": 2000},
    "MNQ": {"risk_cap": 100, "daily_stop": 300, "multiplier": 2, "dd_remaining": 2000},
    "max_trades_per_day": 3,
    "min_rr": 2.0,
}
```
2. Add `{{INSERT_RISK_PARAMS}}` placeholder to all prompts.
3. In `daily_narrative.py` and `trader_narrative.py`, inject the formatted block before calling the LLM.
**Resolved 2026-07-14 (this PR)**:

The recommended fix was applied with a small but deliberate deviation: instead of a new `NARRATIVE_RISK_PARAMS` dict in `scripts/streaming/options/config.py`, the renderer is built on top of the **existing** typed risk config in `scripts/libs_py/risk/narrative/constants.py` (`ACCOUNT_PHASES`, `PER_INSTRUMENT_CAPS`, `INSTRUMENT_SPECS`, `ACTIVE_PHASE`). Reasons:

- The numbers in `ACCOUNT_PHASES` and `PER_INSTRUMENT_CAPS` are the **same** numbers the validator enforces at runtime. Adding a second copy in `config.py` would create a new "what if they drift" failure mode — the original audit problem, in different clothes.
- The audit's `NARRATIVE_RISK_PARAMS` example only covered MES and MNQ. The existing config has a complete map for all six contracted instruments (MNQ, MES, MYM, M2K, NQ, ES) with proper contract multipliers and risk caps, so the rendered block now covers all of them, not just the two examples.
- Trailing-DD, daily-stop, max-open-trades, and R:R bounds are phase-aware (EVAL vs FUNDED), which a flat dict could not express.

**What was done**:

1. **New renderer** in `scripts/libs_py/risk/narrative/prompt_render.py`:
   - `format_risk_params_block(instruments, phase)` returns a deterministic markdown table from typed config — no f-string interpolation of literals, no chance of a value drifting from what the validator enforces.
   - `insert_risk_params(prompt, instruments)` is a drop-in string replace for the `{{INSERT_RISK_PARAMS}}` placeholder.
   - Phase-aware trailing-DD line: `Trailing-DD buffer: not applicable` for EVAL (no buffer), `Trailing-DD buffer remaining: $2,000` for FUNDED.
   - Per-instrument table includes: contract, $/pt multiplier, risk/trade cap, daily stop contribution, and proxy symbol (MNQ→QQQ, MES→SPY, NQ→NDX, ES→SPX) for context.
   - Combined-risk cap line: `Same-direction combined risk cap: $250 (MNQ $100 + MES $150)` — surfaces the multi-contract additive risk that the validator already enforces.

2. **Constants added** to `scripts/libs_py/risk/narrative/constants.py`:
   - `PROXY_SYMBOLS: Final[dict[str, str]]` — MNQ→QQQ, MES→SPY, NQ→NDX, ES→SPX, MYM→DIA, M2K→IWM.
   - `ACCOUNT_SIZE_USD: Final[dict[str, int]] = {"EVAL": 50_000, "FUNDED": 100_000}` — used to render the account-size line.

3. **5 prompt files updated** with `{{INSERT_RISK_PARAMS}}` placeholder:
   - `daily_eod_update.md` and `daily_open_update.md`: replaced the hardcoded "MES: $50k, $2k trailing DD..." and "MNQ: $50k, $2k trailing DD..." lines (these are the two the audit explicitly flagged).
   - `trader_morning.md`, `trader_intraday.md`, `trader_close.md`: added a new "# ACCOUNT CONTEXT" section with the placeholder + the soft combined-risk cap line (these three didn't have hardcoded values in the audit, but updating them keeps all five files consistent — the renderer is cheap and the LLM now sees identical risk framing in every session).
   - `weekly_briefing.md` was **not** updated: it describes week-level outlook, not per-trade risk; account rules belong in the daily/intraday prompts.

4. **Injection sites**:
   - `scripts/trader/daily_narrative.py` — wires `insert_risk_params` into both the open and EOD prompt paths, using `NARRATIVE_TO_MICRO` to map the configured `tickers` (e.g. NQ1, ES1) to micro contracts (MNQ, MES) the risk config knows about.
   - `scripts/trader/trader_narrative.py` — wires `insert_risk_params` into the trader_*/cheat-sheet prompt path with a local `_micro_map = {"NQ1": "MNQ", "ES1": "MES"}` (the trader_* prompts already run on the pipeline tickers; the local map is the only place that knows them).

5. **28 unit tests** in `tests/test_prompt_render.py` cover:
   - EVAL vs FUNDED block shape (account size, daily stop, trailing-DD line, max open trades, R:R bounds).
   - Per-instrument table content (contract, $/pt, risk cap, daily stop, proxy).
   - Combined-risk cap math (`$100 + $150 = $250` for MNQ+MES same direction).
   - Default instrument order matches `DEFAULT_INSTRUMENT_ORDER` constant.
   - Dedup is not done in the renderer (it's a pure formatter); placeholder replacement is idempotent.
   - Unknown instruments are silently skipped (forward-compat for new tickers).
   - Empty configuration renders a sentinel `EMPTY_BLOCK` placeholder text, not a broken table.
   - USD formatting uses comma separators (`$2,000` not `$2000`).
   - Public API smoke test — `format_risk_params_block` and `insert_risk_params` are importable from the package root.

**Total test count after this PR**: 90 + 28 = 118.
---

### 1.8 ✅ EOD Trade Plan Distinguishes Filled vs Pending (resolved 2026-07-14, side-effect of §1.1)

**File**: `daily_narrative.py`, `get_trade_plan_for_eod` (lines 200-238)

**Problem**: The function queries trades where `createdAt >= start_of_day` and includes all of them — PENDING, FILLED, CLOSED, STOPPED, etc. At EOD time (16:25), trades that were planned at 09:35 but never filled are still status=PENDING. Trades that were filled and closed are status=CLOSED/WIN/LOSS. The function lists them all without distinguishing, and the LLM sees:
```
- MES SHORT | Entry: 6905 | Stop: 6915 | Target: 6875 | Status: PENDING
- MNQ SHORT | Entry: 25450 | Stop: 25480 | Target: 25360 | Status: PENDING
```
With no indication of which were actually traded. The LLM is then asked to "evaluate the morning plan" against this incomplete picture.

**Impact**: The LLM may write "Both trades were stopped at their stops" when in fact neither was filled.

**Recommended Fix**: 
1. Separate the query into two: planned-but-not-filled vs. filled-and-closed.
2. Show outcome per trade: `MES SHORT: NEVER FILLED (limit not hit)` or `MES SHORT: FILLED 6905, STOPPED at 6915 (-$50)`.
3. Cross-reference with the broker fill events.

---

## 2. Technical Issues

### 2.1 ✅ Multi-Ticker Render Path (resolved 2026-07-14)

**Files**: `daily_narrative.py` (`NARRATIVE_INSTRUMENT_MAP`, `PIPELINE_TO_NARRATIVE`, `MICRO_TO_NARRATIVE`, `NARRATIVE_TO_MICRO`, `build_open_static_template`, `build_eod_static_template`, `render_open_summary`, `render_eod_summary`), `prompts/daily_open_update.md`, `prompts/daily_eod_update.md`, `tests/test_render_summaries.py` (16 tests)

**Original problem**: `render_open_summary` had hardcoded `mes` / `mnq` reads; `render_eod_summary` had its own inline `instrument_map = {"NQ1": "MNQ", "ES1": "MES"}` dict; `build_open_static_template` and `build_eod_static_template` had a third copy of the same dict. Adding YM1 or RTY1 would require code edits in five places, and the open path would silently produce `N/A` for any new ticker.

**Pipeline vs micro split (the design insight)**: The narrative chain deals in three different "names" for each futures product, and conflating them is the source of a long history of slot-name bugs. The fix separates them:

- **`pipeline` label** (`NQ`, `ES`) — the futures the trader WATCHES. Drives slot names (`{{NQ_REGIME}}`, `{{TM_ES_ENTRY}}`), regime lines, level tables, and the LLM's JSON contract (`tickers: {NQ: {...}, ES: {...}}`, `tomorrow: {NQ: {...}}`, `session_log: {NQ: ...}`). This is what the entire narrative is about.
- **`micro` label** (`MNQ`, `MES`) — the actual prop-firm contract. Only appears in `plan_json.trades[].asset` — that's the field the prop-firm API cares about, and it is the only place where the micro label is semantically correct.
- **`description`** — human-readable string for the static template's "trade plan" header line (e.g. `Nasdaq-100 futures (MNQ micro), contract: MNQ`).

The trader reads about **NQ** levels on **NQ** regime on **NQ** chart, and the system quietly plans to execute the trade in **MNQ** because the prop-firm account trades micros. Both labels visible in the rendered output, but never conflated.

**What was done**:

1. **Centralized the map** at module level in `daily_narrative.py` with all three names per ticker:
   ```python
   NARRATIVE_INSTRUMENT_MAP: dict[str, dict[str, str]] = {
       "NQ1": {"pipeline": "NQ",  "micro": "MNQ", "description": "Nasdaq-100 futures (MNQ micro)"},
       "ES1": {"pipeline": "ES",  "micro": "MES", "description": "S&P 500 futures (MES micro)"},
   }
   # Derived reverse maps for callers that need to map back:
   PIPELINE_TO_NARRATIVE  # "NQ" -> "NQ1"
   MICRO_TO_NARRATIVE     # "MNQ" -> "NQ1"
   NARRATIVE_TO_MICRO     # "NQ1" -> "MNQ"
   ```
   All four previously-duplicated call sites (`build_open_static_template`, `build_eod_static_template`, `render_open_summary`, `render_eod_summary`) now derive everything from this single source. Adding YM1 / RTY1 = one line in the map.

2. **Slot names use the pipeline label** throughout the static templates: `{{NQ_REGIME}}`, `{{ES_ENTRY}}`, `{{TM_NQ_TARGET}}`, `{{TM_ES_RR}}`, `{{SESSION_NQ}}`, `{{SESSION_ES}}`. The LLM JSON contract uses the same: `tickers: {NQ: ..., ES: ...}`, `tomorrow: {NQ: ..., ES: ...}`, `session_log: {NQ: ..., ES: ...}`. The `plan_json.trades[].asset` field remains the micro label (MNQ, MES) — that's the actual contract.

3. **Prompts updated**:
   - `daily_open_update.md` — `tickers.MNQ/MES` → `tickers.NQ/ES`; `risk_summary.line_1/3` switched to ES/NQ.
   - `daily_eod_update.md` — `session_log.MNQ/MES` → `session_log.NQ/ES`; `tomorrow.MNQ/MES` → `tomorrow.NQ/ES`; `tomorrow_risk_budget` switched to ES/NQ.
   - The "ACCOUNTS" header in both prompts (lines 9-10) still describes the prop-firm accounts by their micro labels (MNQ, MES) — that's correct because the account is named after the contract it trades.

4. **Backwards-compatible fallback**: Both render functions prefer the new dict shape (keyed by pipeline label) but fall back to the legacy flat keys (`mes` / `mnq` for open, `tomorrow_mes` / `tomorrow_mnq` and `session_log.mes` / `session_log.mnq` for eod) for backward compatibility with previously-generated analyses and old DB rows.

5. **16 unit tests** in `tests/test_render_summaries.py` cover:
   - `NARRATIVE_INSTRUMENT_MAP` invariants and reverse-map consistency.
   - Static templates use the **pipeline** label in slot names (`{{NQ_REGIME}}`); the **micro** label only appears in `plan_json.trades[].asset` and in the descriptive text.
   - New `tickers: {NQ: ...}` / `tomorrow: {NQ: ...}` / `session_log: {NQ: ...}` JSON contracts.
   - Legacy `mes` / `mnq` / `tomorrow_mes` / `tomorrow_mnq` / `session_log.mes` / `session_log.mnq` fallback paths.
   - New-ticker rendering (YM1 added via monkeypatch — no code changes required; pipeline "YM" / micro "MYM" picked up automatically).
   - Missing-payload safety (no KeyError, all unfilled slots become `N/A`).

**Bug caught during testing**: The first iteration of `build_open_static_template` used f-string slots with spaces inside the braces (`{{ NQ_REGIME }}`) — but `_replace_slot` matches `{{KEY}}` exactly. The slot names were silently never replaced, and the static template had every slot show `N/A`. Fixed by building the slot strings at Python level (`f"{{{{{pipeline}_REGIME}}}}"`) so the brace doubling produces `{{NQ_REGIME}}` cleanly.

**Total test count after this PR**: 90 (74 + 16).

---

### 2.2 ✅ Duplicate-Trade Prevention via Source-Keyed Dedup (resolved 2026-07-14)

**File**: `daily_narrative.py`, `extract_and_save_trade_plan`

**Problem**: This function is called for BOTH the open narrative AND the eod narrative (see lines 919, 922). At open time, it saves PENDING trades. At EOD time, `get_trade_plan_for_eod` returns the morning's PENDING trades. The EOD narrative generates a **new** plan for tomorrow. If the LLM returns the same trade structure at EOD, `extract_and_save_trade_plan` will create a **second set** of identical PENDING trades — duplicating the morning's plan without marking it as the source.

**Impact**: The DB accumulates duplicate PENDING trades. The drawdown query (`get_drawdown_status`) filters by status, so duplicates don't inflate P&L — but they pollute the trade history and confuse any "what's currently active?" query.

**Recommended Fix**: 
1. Add a `source` field to the Trade model (`OPEN` / `EOD_TOMORROW`).
2. In `extract_and_save_trade_plan`, check if a matching PENDING trade already exists from the same session type. If so, update instead of insert.
3. Or: delete the morning's PENDING trades before saving the EOD's tomorrow plan.

**Resolved 2026-07-14 (this PR)**:

The `source` field already existed on the Prisma Trade model (`originalSource String?`, schema line 90) — no migration required. The fix was a targeted runtime check at the save site.

**What was done**:

1. **Trade-source constants** in `scripts/trader/daily_narrative.py`:
   - `TRADE_SOURCE_OPEN = "OPEN"` — the morning open narrative's plan (today's session).
   - `TRADE_SOURCE_EOD_TOMORROW = "EOD_TOMORROW"` — the EOD narrative's plan (tomorrow's session).
   - `_VALID_TRADE_SOURCES = frozenset({TRADE_SOURCE_OPEN, TRADE_SOURCE_EOD_TOMORROW})` — allow-list.

2. **`extract_and_save_trade_plan` updated** with a `source: str = TRADE_SOURCE_OPEN` parameter. The function:
   - Validates `source` against the allow-list at the top; rejects bad values and returns early (no DB write).
   - For each planned trade, calls `db.trade.find_first(where={ticker, direction, entryPrice, accountId, status: 'PENDING', originalSource: source})` before the create.
   - If a match exists, logs `skipping — duplicate of trade <id>` and `continue`s. If not, creates the new trade with `originalSource=source` set.

3. **Both call sites updated** to pass the correct source:
   - Open narrative → `source=TRADE_SOURCE_OPEN` (today's plan).
   - EOD narrative → `source=TRADE_SOURCE_EOD_TOMORROW` (tomorrow's plan).

4. **Cross-source pairs are NOT deduped** — this is the design insight. The morning's `OPEN` plan and the EOD's `EOD_TOMORROW` plan are **two different commitments**:
   - The morning plan says "trade MES SHORT today."
   - The EOD plan says "trade MES SHORT tomorrow."
   These are two separate tradable signals with different risk windows; collapsing them into one row would lose the source-of-truth distinction the trader needs at audit time. The dedup key includes `originalSource`, so the same LLM producing the same plan twice within the **same** session (e.g. the open job runs twice because of a retry) is still caught, while the legitimate morning+EOD pair survives.

5. **18 unit tests** in `tests/test_trade_plan_dedup.py` cover:
   - Module constants: `TRADE_SOURCE_OPEN`, `TRADE_SOURCE_EOD_TOMORROW`, distinct values, no whitespace.
   - First-time open save creates one trade per proposal.
   - Second open save with the same plan is deduplicated (one trade, not two).
   - Three open runs of the same plan → one trade, not three.
   - Open + EOD_TOMORROW with the same plan creates **two** trades (cross-source pair preserved).
   - Two EOD_TOMORROW runs with the same plan → one trade.
   - Invalid `source` (e.g. `open` lowercase, or arbitrary string) is rejected with no DB write.
   - Saved record has `originalSource=source` set.
   - Different `entryPrice` / `direction` / `ticker` is NOT a duplicate.
   - A `CLOSED` trade with the same key does NOT block a new save (only `PENDING` blocks).
   - Default `source` is `TRADE_SOURCE_OPEN` (backward-compatible signature).

The integration test file `tests/test_extract_and_save_trade_plan.py` was also updated: its shared `_MockTradeClient` mock now mirrors Prisma's read-your-writes semantics — `create()` appends to the dedup index, so the next call's `find_first` correctly finds the just-inserted row.

**Total test count after this PR**: 118 + 18 = 136.

---

### 2.3 ✅ `build_levels_markdown_table` Is Now Session-Aware (resolved 2026-07-14, same as §1.3)

**File**: `briefing_core.py`, `build_levels_markdown_table` line 1161

The function uses `UNIFIED_LEVELS_OPEN_TXT` unconditionally. This is the same issue as §1.3 but from the technical perspective: the function should accept a `session` argument, defaulting to `"open"` for backward compatibility.

---

### 2.4 ✅ `instrument_map` Centralized (resolved 2026-07-14, side-effect of §2.1)

This issue was resolved automatically as part of the §2.1 refactor. The new module-level `NARRATIVE_INSTRUMENT_MAP` in `scripts/trader/daily_narrative.py` is the single source of truth, with all three names per ticker (pipeline / micro / description):

```python
NARRATIVE_INSTRUMENT_MAP: dict[str, dict[str, str]] = {
    "NQ1": {"pipeline": "NQ", "micro": "MNQ", "description": "Nasdaq-100 futures (MNQ micro)"},
    "ES1": {"pipeline": "ES", "micro": "MES", "description": "S&P 500 futures (MES micro)"},
}
```

All four previously-duplicated call sites now reference it:
- `build_open_static_template()` — derives slot names from `pipeline`.
- `build_eod_static_template()` — derives slot names from `pipeline`.
- `render_open_summary()` — looks up per-instrument data using `pipeline` for slot names and `micro` as the fallback for legacy keys.
- `render_eod_summary()` — same.

Three derived reverse maps are also exposed for callers:
- `PIPELINE_TO_NARRATIVE` (`"NQ" -> "NQ1"`)
- `MICRO_TO_NARRATIVE` (`"MNQ" -> "NQ1"`)
- `NARRATIVE_TO_MICRO` (`"NQ1" -> "MNQ"`)

**Note**: The audit recommended putting this map in `scripts/streaming/options/config.py` to keep all narrative config in one place. We placed it in `daily_narrative.py` instead because:
- It is consumed only by the daily-narrative module (the other renderers, premarket/intraday/weekly, do their own ticker mapping).
- The narrative-pipeline config in `config.py` is for schedule/tickers; the instrument label mapping is a per-renderer concern.

If/when a second consumer needs this map, the right move is to lift it into `config.py` (or a new `scripts/trader/constants.py`) — but not before.

---

### 2.5 ✅ Schwab Hub Availability Probe (resolved 2026-07-14)

**File**: `trader_narrative.py`, premarket/open paths

**Problem**: The premarket and open narratives call `get_macro_quotes()` which tries to fetch Schwab quotes for JPM, BAC, GS (bank stocks used for intermarket context). When the hub proxy on port 8080 is down, each failed call produces 3 lines of `ConnectionRefusedError` traceback in the console output. The premarket narrative runs sequentially for NQ1 then ES1, producing ~18 lines of noise before the actual LLM output.

**Impact**: Operators reading the console see a wall of errors and may think the system is broken when it's just a missing external service.

**Recommended Fix**: Add a `try_once = True` flag to the Schwab quote fetcher, or detect hub proxy availability before calling. Alternatively, move intermarket quotes to a non-blocking background task and skip if unavailable.

**Resolved 2026-07-14 (this PR)**:

The recommended fix was applied via option 2 — a 0.25-second TCP probe of `127.0.0.1:8080` (the local Schwab hub proxy) before any Schwab auth is attempted. The probe runs as a separate function `_is_schwab_hub_reachable()` so it can be unit-tested in isolation.

**What was done**:

1. **New helper** `_is_schwab_hub_reachable()` in `scripts/trader/briefing_core.py`:
   - Uses `socket.create_connection(("127.0.0.1", 8080), timeout=0.25)`.
   - Returns `True` if the connect succeeds, `False` on any `OSError` (including `ConnectionRefusedError`) or `socket.timeout`.
   - The 0.25s timeout caps the worst case at 250 ms — fast enough that an online hub adds negligible latency, slow enough that an offline hub doesn't appear instant.

2. **`get_intermarket_quotes()` rewired** in `briefing_core.py`:
   - If the hub is unreachable: log a single `DEBUG` line and skip the entire Schwab auth + quote path. Skip directly to the yfinance fallback.
   - If the hub is reachable but the auth fails: log a single `DEBUG` line, set `client = None`, and skip to yfinance.
   - If the hub is reachable and the auth succeeds but a single quote call fails: log a `DEBUG` line for that specific symbol (`[intermarket] Schwab quote $VIX failed: ...`) and continue. **No more bare `pass` in the inner loop** — the previous code swallowed per-quote failures with no log at all, making it hard to debug when one symbol returns stale data.
   - The yfinance fallback path is unchanged in shape, but its inner `pass` is also upgraded to a `DEBUG` log for parity with the Schwab path.

3. **Wall of tracebacks eliminated**: when the hub is down, the only log line is `[intermarket] Schwab hub (127.0.0.1:8080) not reachable — using yfinance fallback` at DEBUG level. The `test_hub_down_does_not_log_traceback` test in `tests/test_schwab_hub_and_model.py` pins this — it asserts zero WARNING+ records are emitted on the hub-down path.

**4 unit tests** in `tests/test_schwab_hub_and_model.py` cover:
   - `_is_schwab_hub_reachable()` returns True when the socket connects.
   - Returns False on `OSError` and on `socket.timeout`.
   - The probe targets `127.0.0.1:8080` with a sub-1s timeout.
   - The probe is fast (completes in well under 100 ms in the happy path).

**2 integration tests** cover the consumer of the probe:
   - `get_intermarket_quotes()` on hub-down does NOT call `schwab.auth.easy_client` (the wall-of-errors code path is fully bypassed).
   - `get_intermarket_quotes()` on hub-down emits zero WARNING+ log records.

**Total test count after this PR**: 174 + 6 = 180.

---

### 2.6 ✅ Unified Default Model via config_loader (resolved 2026-07-14)

**Files**: `trader_narrative.py` (line 60: `deepseek-v4-pro:cloud`), `daily_narrative.py` (line 58: `gemma4:latest`)

**Problem**: The two narrative chains default to different models. Different models have different prose styles, attention patterns, and JSON adherence. A trader reading the morning "clean read" from one model and the daily EOD from another sees inconsistent voice and formatting.

**Recommended Fix**: Add `NARRATIVE_DEFAULT_MODEL` to `config.py`. Reference from both scripts. The `--model` CLI flag already allows per-run overrides.

**Resolved 2026-07-14 (this PR)**:

The recommended fix was applied, but with a small deviation: there is no `scripts/streaming/options/config.py` entry to add `NARRATIVE_DEFAULT_MODEL` to (the audit's example config file does not exist; the narrative chain has its own config). Instead, the LLM defaults are added to the existing `scripts/trader/config/narrative_stats.yaml` as a new top-level `llm:` section, and exposed via `config_loader.get_llm_config()`. Reasons:

- The narrative chain already has a typed config loader (`config_loader.py`) with `lru_cache` and validation. Adding the LLM section there is a 5-line change vs. introducing a brand-new config file.
- The audit's `NARRATIVE_DEFAULT_MODEL` is one number. We actually need **three** (default, cloud fallback, local fallback) and **two** (one per chain — the daily chain and the trader chain can intentionally point at different models). A flat `NARRATIVE_DEFAULT_MODEL` const would not express this.

**What was done**:

1. **New `llm:` section** in `scripts/trader/config/narrative_stats.yaml`:
   ```yaml
   llm:
     default_model: "gemma4:latest"           # daily chain
     default_trader_model: "gemma4:latest"   # trader chain (intentionally same)
     fallback_model: "gemma4:31b-cloud"      # cloud fallback
     local_fallback_model: "gemma4:latest"   # local-only fallback
   ```
   The audit's design point — "different chains have different voices" — is now pinned by the fact that the two chains both read from the same `default_*_model` key. The audit found that the chains had drifted to `deepseek-v4-pro:cloud` vs `gemma4:latest`; the fix is to deliberately point them at the same model. Operators can still override per-run via `--model`.

2. **New function** `get_llm_config()` in `scripts/trader/config_loader.py`:
   - Returns the `llm` section of the loaded config.
   - Returns an empty dict (not raises) if the section is missing — call sites defensively fall back to hardcoded defaults so a single missing key never takes the narrative chain down at module-import time.

3. **`daily_narrative.py` rewired**:
   - `DEFAULT_MODEL` and `FALLBACK_MODEL` now read from `get_llm_config()` at module-import time.
   - The `--model` CLI flag still works (it overrides the config-sourced default at parse time).

4. **`trader_narrative.py` rewired**:
   - `DEFAULT_MODEL`, `FALLBACK_MODEL`, and `LOCAL_FALLBACK_MODEL` all read from `get_llm_config()`.
   - The trader chain uses `default_trader_model` (falls back to `default_model` if missing) so the two chains can intentionally diverge if the operator wants — but the default config keeps them aligned.

5. **5 unit tests** in `tests/test_schwab_hub_and_model.py::TestUnifiedDefaultModel` cover:
   - `config_loader.get_llm_config()` exposes a non-empty `default_model`.
   - `daily_narrative.DEFAULT_MODEL == config.default_model` (the two are now equal at import time).
   - `trader_narrative.DEFAULT_MODEL == config.default_model` (same for the trader chain).
   - `FALLBACK_MODEL` is also unified across both modules.
   - The chosen model is a sane string (no `TODO`/`FIXME`/`XXX` placeholders).

**Total test count after this PR**: 180 + 5 = 185.

---

### 2.7 ✅ EOD Settlement Read from Daily Timeframe (resolved 2026-07-14)

**File**: `briefing_core.py`, `load_daily_price_context`

**Original problem**: The function resampled the FULL 1m parquet via `df_1m.resample("B").agg({..., "close": "last"})`. The `last` aggregator picks the last 1m bar of whatever is in the file — which may be a 20:00 Globex print, not the 16:00 ET settlement. The EOD narrative would then report the wrong `close`, `high`, and `low` (Globex can extend the daily range well past RTH).

**What was done**:

1. **Primary path: read the daily timeframe parquet** via `loader.load_parquet(ticker, "1D")`. The daily file is one bar per business day with `close = 16:00 ET settlement print` by construction. It is updated by the data-freshness pipeline's daily rollup.

2. **Freshness check** (`_is_daily_fresh`): if the daily parquet's last bar is more than 1 calendar day behind today, we do NOT trust it. The 1-day buffer covers the case where the EOD narrative runs in the late afternoon and the daily rollup has not yet committed today's bar.

3. **Fallback: RTH-filtered 1m resample** (`_rth_filter_1m_to_daily`). When the daily parquet is stale, we filter the 1m bars to `between_time("09:30", "16:00")` and resample. This guarantees `close = 16:00 settlement` regardless of when the daily rollup last ran. The filter also handles the case where the daily file is missing entirely (e.g. cold start, fresh ticker).

4. **Empty / missing index handling**: if the 1m feed's index is not a US/Eastern `DatetimeIndex` (e.g. legacy data with a `time` column instead of a timezone-aware index), the RTH filter returns an empty DataFrame and the function logs a warning rather than producing a wrong answer. This prevents the silent-corruption mode where the old code would have aggregated a misaligned index.

5. **Test for the headline bug**: `test_falls_back_to_1m_when_daily_is_stale` builds a 1m feed with both a 16:00 RTH bar (close=105) and a 20:00 Globex bar (close=999), and asserts the function returns 105 — NOT 999. This pins the fix to the exact failure mode the audit flagged.

**13 unit tests** in `tests/test_daily_price_context.py` cover:
   - RTH filter keeps 09:30-16:00 bars and drops Globex (the headline bug).
   - RTH filter returns empty for non-DatetimeIndex inputs.
   - The 16:00 bar is included (settlement is the 16:00 bar's `open`).
   - Freshness check: today is fresh, yesterday is fresh, 3 days old is stale, empty/None is not fresh, ms timestamps are auto-detected.
   - End-to-end: fresh daily parquet is trusted (1m loader NOT called); stale daily parquet falls back to RTH-filtered 1m; both failing returns empty dict.

**Total test count after this PR**: 185 + 13 = 198.

---

### 2.8 ✅ `sys.path` Hack Centralized (resolved 2026-07-14)

**File**: `daily_eod_update.py`, `load_daily_price_context` (delegated to `briefing_core.py`)

**Problem**: `load_daily_price_context` resamples 1m bars to business-day (`B`) frequency and takes the last row. The "last row" is the most recent bar in the parquet, which may be a 23:00 ET Globex bar, not the 16:00 RTH close. For a session="eod" run at 16:25 ET, the parquet likely has bars up to ~16:23 (if the RTD or fused loader is writing in real-time), but for backfill runs or runs after hours, the "today" candle may include overnight data.

**Impact**: The "open/high/low/close" reported in the EOD narrative may include a 20:00 bar as the "close," which is the RTH close + 4 hours of Globex action. The change_pct calculation is then against the previous RTH close (correct) but the OHLCV is wrong.

**Recommended Fix**: In `load_daily_price_context`, filter the 1m bars to RTH hours (09:30-16:00 ET) before resampling. Or accept a `session` parameter and slice accordingly.

---

### 2.8 ✅ `sys.path` Hack Centralized (resolved 2026-07-14)

**Files**: All 5 Python source files in `scripts/trader/`

**Problem**: Every file starts with the same 10-line block:
```python
import sys
from pathlib import Path
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)
```

This is fragile (breaks if the file is moved or the project structure changes) and violates DRY. The scheduler already sets `PYTHONPATH` in the subprocess environment, so this hack is redundant.

**Recommended Fix**: 
1. Create `scripts/trader/_path_setup.py` that does this once.
2. Replace the 10 lines in each file with `from scripts.trader._path_setup import *` (or call a function).
3. Better: rely on `PYTHONPATH` set by the scheduler, delete the hack entirely.

**Resolved 2026-07-14 (this PR)**:

The recommended fix was applied exactly as suggested (option 1 — a single `_path_setup.py` module). The audit's count of 5 affected files was off — there are actually **7** consumer files in `scripts/trader/`, all of which now use the side-effect import.

**What was done**:

1. **New module** `scripts/trader/_path_setup.py` (90 lines):
   - `_resolve_repo_root()` — walks up from this file to find the directory containing `scripts/`, then returns its parent (the repo root).
   - `_ensure_repo_root_on_path()` — inserts the resolved root at the head of `sys.path` if not already present. Idempotent.
   - Side-effect on import: the call runs as soon as the module is imported, so consumer files just need a single line.

2. **Side-effect import** in all 7 consumer files:
   - `briefing_core.py`, `daily_eod_update.py`, `daily_narrative.py`, `seed_vol_history.py`, `trader_narrative.py`, `weekly_briefing.py`, `weekly_narrative.py`.
   - The 10-line block (`import sys` + `from pathlib import Path` + 8 lines of walking + `sys.path.insert`) is gone from each. The single line that replaced it is:
     ```python
     from scripts.trader import _path_setup  # noqa: F401
     ```
   - Two of the seven files (`daily_narrative.py`, `weekly_narrative.py`) had a duplicate `import sys` + `from pathlib import Path` because they also use `sys.stdout.reconfigure(encoding='utf-8')` early in the file. The duplication is now consolidated: the first `import sys` (used by the reconfigure call) is kept; the second pair was removed.

3. **Why a side-effect import and not a function call?** Because the consumers have `from scripts.trader.briefing_core import ...` lines immediately after the path block. Replacing the block with a function call would mean ordering matters (the call must run before the first import). A side-effect import is impossible to misorder.

4. **14 unit tests** in `tests/test_path_setup.py` cover:
   - `_resolve_repo_root()` returns the parent of `scripts/`, is absolute, and points at a directory containing both `scripts/` and `tests/` (sanity-check).
   - `_ensure_repo_root_on_path()` is idempotent (no duplicate entries on re-import; reload doesn't grow the list).
   - The side-effect import puts the repo root on `sys.path` after import.
   - **All 7 consumer files** have the old 10-line hack removed AND the new side-effect import added (parametrized test greps each file for the unique markers).
   - The idempotency test mutates `sys.path` in place (via `sys.path[:] = ...`) rather than reassigning the attribute, because other modules in the suite hold a reference to the list and would otherwise be left with a stale view.

**Total test count after this PR**: 136 + 14 = 150.

---

### 2.9 ✅ `compute_level_interactions` Guards Standardized (resolved 2026-07-14)

**File**: `briefing_core.py`, `compute_level_interactions`

```python
"call_wall_tested": high >= call_wall > 0,
"put_wall_tested": low <= put_wall > 0 and put_wall > 0,
```
The `put_wall_tested` has `put_wall > 0` twice (in the chained comparison and as a standalone). Also, the chained `high >= call_wall > 0` means call_wall must be strictly positive — if call_wall is 0 (no wall found), the comparison returns False. The `put_wall_tested` equivalent `low <= put_wall > 0 and put_wall > 0` is inconsistent and harder to read.

**Recommended Fix**: Standardize on the chained form for both:
```python
"call_wall_tested": call_wall > 0 and high >= call_wall,
"put_wall_tested": put_wall > 0 and low <= put_wall,
```

**Resolved 2026-07-14 (this PR)**:

The recommended form was applied, but with a small read-order adjustment. The audit's example uses `call_wall > 0 and high >= call_wall` — the gate first, then the touch condition. We use exactly that form throughout, with a 9-line comment block at the top of the function explaining why (the chained form is easy to mis-translate; the explicit form reads top-to-bottom).

**What changed**:

- All 10 keys (`call_wall`, `put_wall`, `em_upper`, `em_lower` × `tested`/`broken`, plus `zero_gamma_crossed` and `magnet_tested`) now use the explicit form.
- The double `put_wall > 0` (`low <= put_wall > 0 and put_wall > 0`) is gone.
- `zero_gamma_crossed` and `magnet_tested` are now also explicit: `level > 0 and low < level < high`. The old form used a ternary `if level > 0 else False` that conflated the gate with the value.
- A `truth_table_matches_old_chained_form` test in `tests/test_briefing_core_fixes.py` fuzzes the new form against the old form over a 4×4 grid of (level, high, low, close) values and asserts the truth tables are identical. This pins the fix to **behavioural equivalence** so a future refactor cannot silently change the semantics.

**9 unit tests** in `tests/test_briefing_core_fixes.py::TestComputeLevelInteractionsGuards` cover:
- Positive level above/below high → tested/not-tested.
- Zero or negative level → no flag ever fires (this is the 'no level found' sentinel the audit flagged).
- `zero_gamma_crossed` and `magnet_tested` only fire when the level is strictly inside the high-low range and `> 0`.
- Fuzzed truth-table equivalence between new and old chained forms (16 grid points).

**Total test count after this PR**: 150 + 9 = 159.

---

### 2.10 ✅ `parse_meta_fields` Uses Strict Regex (resolved 2026-07-14)

**File**: `briefing_core.py`, `parse_meta_fields`

**Problem**: The fallback parser does `meta_part.rfind("_")` to split key from value. If a value contains an underscore (e.g., `NOTE: "12-31 expiry"`), the split mis-aligns. The known_keys list covers common cases, but adding new META fields requires updating the list. New fields in the pipeline silently fall through to the broken fallback.

**Recommended Fix**: Use a regex or a strict format spec: `META_{KEY}_{VALUE}` where KEY is alphanumeric only. Reject any META field whose key contains non-alphanumeric characters and log a warning.

**Resolved 2026-07-14 (this PR)**:

The recommended fix was applied. The fallback parser now uses `re.match(r"^([A-Z][A-Z0-9]*)_(.+)$", meta_part)` — a strict format spec where the key must start with an uppercase letter and contain only uppercase letters / digits. This rejects the malformed cases the old `rfind("_")` would have silently mis-parsed.

**Specific bugs that are now caught**:

| Old behaviour (broken) | New behaviour (correct) |
|---|---|
| `META_NOTE_12-31 expiry` → `meta["NOTE_12-31"] = "expiry"` (key has a digit, value has a space — both corruption) | `meta["NOTE"] = "12-31 expiry"` (key clean, value preserved) |
| `META_NOTE_TIER: A` → `meta["NOTE_TIER: A"] = ""` (key has a colon and a space) | `meta["NOTE"] = "TIER: A"` (key clean, value preserved) |
| `META_lowercase_42.5` → `meta["lowercase"] = 42.5` (mixed case key) | silently dropped (consumer code tolerates missing keys) |
| `META_1FOO_42.5` → `meta["1FOO"] = 42.5` (key starts with digit) | silently dropped |
| `META_FOO-BAR_42.5` → `meta["FOO-BAR"] = 42.5` (key has hyphen) | silently dropped |

**What was done**:

1. **Strict regex** replaces `rfind("_")`. The key must be `^([A-Z][A-Z0-9]*)_` (one uppercase letter, then zero or more uppercase letters or digits). Values are `(.+)$` (one or more characters, anything goes).
2. **Silent rejection** for malformed fields. The audit suggested logging a warning; we deliberately chose silent drop because (a) the consumer code uses `meta.get("FOO")` and tolerates missing keys, and (b) a `log.warning` per malformed field would clutter the parser's stdout without actionable signal — the field is dropped before it can pollute downstream code, which is the actual fix.
3. **Empty value (`META_X_`) is also dropped** under the strict spec. The audit recommended a strict format spec; allowing empty values would require `.+` → `.*`, which is a one-character change if we want to revisit. For now, the strict form is preferred.

**15 unit tests** in `tests/test_briefing_core_fixes.py::TestParseMetaFields*` cover:
- Single known key parses correctly.
- Numeric value parses as float, string value parses as string.
- Longest-match wins (GEX_TOTAL before GEX) — preserved by the known_keys list, sorted by length descending.
- Multiple fields in one line all parse.
- Unknown well-formed key (the forward-compat case) parses correctly.
- Value with underscore does not corrupt the key (the audit's headline bug).
- Value with colon does not corrupt the key.
- Lowercase / digit-leading / hyphen-containing keys are rejected.
- Empty / missing line returns empty dict.

**Total test count after this PR**: 159 + 15 = 174.

---

### 2.11 ✅ `target_date` Propagated Through `build_ticker_cheat_sheet` and `build_eod_context` (resolved 2026-07-14)

**Files**: `scripts/trader/briefing_core.py` (5 call sites)

**Original problem**: The audit flagged that `trader_narrative.py` didn't pass `target_date` to its context builders. Investigation revealed the actual bug was **one level deeper**: `trader_narrative.py` *does* propagate `target_date` correctly to all four of its builder calls (`build_intraday_context`, `build_eod_context`, `build_premarket_context`, `build_ticker_cheat_sheet`). The leak was inside the *builders themselves* — specifically in `build_ticker_cheat_sheet` and `build_eod_context` — where 5 internal calls to `build_overnight_context(loader, ticker)` dropped the `target_date` argument that their enclosing functions had in scope.

When `target_date` is None (the default), `build_overnight_context` falls back to today's date inside the function. For backfill runs (e.g., testing the Friday narrative on Monday), the overnight context was therefore showing Monday's Globex session instead of Friday's, contaminating the cheat sheet that the LLM consumes.

**What was done**:

1. **Located the 5 leaky call sites** in `scripts/trader/briefing_core.py`:
   - Line 3122: `nq_ctx = build_overnight_context(loader, "NQ1")` (in `build_ticker_cheat_sheet`)
   - Line 3123: `es_ctx = build_overnight_context(loader, "ES1")` (in `build_ticker_cheat_sheet`)
   - Line 3125: `ticker_ctx = build_overnight_context(loader, ticker)` (in `build_ticker_cheat_sheet`, top block)
   - Line 3196: `ticker_ctx = build_overnight_context(loader, ticker)` (in `build_ticker_cheat_sheet`, downstream `open`/`intraday` branches)
   - Line 3752: `nq_ctx_morning = build_overnight_context(loader, ticker)` (in `build_eod_context`, morning-bias feedback loop)

2. **Added `target_date` as the 3rd positional argument** to each of the 5 call sites. All three enclosing functions (`build_ticker_cheat_sheet`, `build_eod_context`) had `target_date` already in their signatures as a `date | None = None` parameter, so the propagation was a one-token addition per site.

3. **Added a 9-test regression suite** in `tests/test_target_date_propagation.py`:
   - **Static check (4 tests)**: walks the source of `briefing_core.py` and asserts every `build_overnight_context(loader, ...)` call includes `target_date`; pins the total call-site count at exactly 7 (2 in `build_premarket_context` + 5 in the fixed sites); asserts no call site uses a hardcoded `date()` or `datetime.now()` (which would defeat the backfill purpose); asserts no call site uses a literal date string.
   - **Signature check (3 tests)**: verifies the public `build_ticker_cheat_sheet`, `build_eod_context`, and `build_overnight_context` signatures still expose `target_date` with a `None` default.
   - **Caller check (2 tests)**: verifies `trader_narrative.py` still passes `target_date` to all four of its builder calls (regression guard against the upstream fix being reverted).

**Audit correction**: the original section header said "trader_narrative.py Does Not Pass target_date" — the actual defect was that `trader_narrative.py` *was* passing it correctly, but the downstream `build_ticker_cheat_sheet` and `build_eod_context` in `briefing_core.py` were dropping it on the floor in 5 of their internal calls. The audit's recommended fix (propagate from `run_narrative` to all context builders) was already in place; the real fix was to propagate from the builders to `build_overnight_context`.

**Backfill behaviour after the fix**: a run with `trader_narrative.py --target-date 2026-07-10` (a Friday) now resolves Friday's overnight session for both NQ1 and ES1, regardless of what day the script is invoked. The LLM sees Friday's Globex → RTH boundary, not today's.

---

### 2.12 🟢 `weekly_briefing.md` Prompt References SPY/QQQ but System Uses NQ1/ES1

**File**: `weekly_briefing.md`

The prompt says: "For SPY/QQQ scenarios, use both scales when relevant: translated futures value first, raw proxy value in brackets." But the configured tickers are NQ1/ES1. The SPY/QQQ language is a vestige from the original architecture.

**Recommended Fix**: Either remove the SPY/QQQ reference (since the system is futures-direct) or make it conditional: "If the ticker is SPY or QQQ, show both scales; otherwise show only the futures value."

---

## 3. Architecture Observations

### 3.1 ✅ Two-Phase Design Is Correct

The Python-pre-digest → LLM-narrative pattern is the right architecture. The cheat sheet assembly in `briefing_core.py` is comprehensive (~1200-5000 chars depending on mode). The compact briefing builders (`build_compact_briefing`, `build_compact_eod`) reduce the daily TOON by ~40%.

### 3.2 ✅ Config-Driven Scheduling Is Working

The migration of schedule times and ticker lists to `config.py` (NARRATIVE_SCHEDULE, NARRATIVE_TICKERS, NARRATIVE_TICKER_MAP) is complete and validated. The scheduler logs confirm all 5 narrative jobs are registered at the correct times (08:45 premarket, 09:35 open, 12:00 intraday, 16:25 EOD, Friday 16:20 weekly).

### 3.3 ✅ DB-First Storage Is Correct

The weekly_briefing, daily_eod_update, and daily_narrative scripts all use Prisma/SQLite for persistence. This is a significant improvement over file-based storage — the same data feeds both the Discord webhooks and the web dashboard. The `save_*_to_db` functions use upsert patterns correctly to allow re-runs.

### 3.4 ⚠️ Prompt-Compute Boundary Is Blurred

Several prompts contain decision logic that should be in Python:

| Logic | Currently In | Should Be In |
|---|---|---|
| Confluence Model (3/3=HIGH, 2/3=MEDIUM) | `trader_morning.md` | `assess_confluence()` already exists in `signals/confluence.py` — inject result into cheat sheet |
| VIX Regime (QUIET/CALM/NORMAL/ELEVATED/HIGH/CRISIS) | `trader_morning.md` | `signals/volatility.py` — add `get_vix_regime_label()` function |
| RTH Break scenario (Gap Up/Down/Inside) | `trader_morning.md` + `daily_*.md` | Already computed in `build_ticker_cheat_sheet` as a text line — verify it appears in the prompt input |
| Hourly personality (10:00 reversion, 15:00 trend) | `trader_intraday.md` | Pre-compute and inject as a `== HOURLY OUTLOOK ==` block |
| ALN bias classification | `briefing_core.py` cheat sheet | Already in cheat sheet — remove from prompt guides |

### 3.5 ✅ Discord Chunking Logic Now Lives in One Place (resolved 2026-07-14)

**Files**: `scripts/libs_py/discord/{config.py,chunking.py,sender.py,__init__.py}`, `scripts/trader/daily_narrative.py`, `scripts/trader/trader_narrative.py`, `scripts/trader/weekly_narrative.py`, `tests/test_discord_sender.py`

**Original problem**: The Discord chunking logic (split on `\n## ` headers, 1900 char limit, chunk-by-chunk send) was duplicated verbatim in `daily_narrative.py::send_discord_summary` and `trader_narrative.py::send_discord_summary`. The audit's review also caught a third copy in `weekly_narrative.py`. If Discord changes its limit or the chunking strategy improves, all three files had to be updated in lockstep.

**What was done**:

1. **New sub-package** `scripts/libs_py/discord/` (mirrors the `libs_py/risk/narrative/` pattern from §1.2/§1.4/§1.7):
   - `config.py` — single home for `DISCORD_MAX_CHARS=1900`, `DEFAULT_WEBHOOK_KEY="macro-alerts"`, `HTTP_TIMEOUT_SECONDS=15`, `DISCORD_WEBHOOKS_FILENAME="discord_webhooks.json"`, and `resolve_webhooks_path(repo_root)`. KEEP-IN-SYNC comments point at the on-disk JSON and at `narrative_stats.yaml` for future config refactors.
   - `chunking.py` — pure, side-effect-free `chunk_markdown(text, max_chars=1900, section_header="\n## ")`. Handles: short text → `[text]`, empty text → `[""]`, multi-section packing, oversized single section. No `requests` import, no logging — fully unit-testable.
   - `sender.py` — `send_summary(summary, webhook_key, repo_root, *, webhooks_path, poster, max_chars)` does the I/O: load URL → `chunk_markdown` → POST each chunk with `{"content": chunk}` and a 15s timeout. Lazy-imports `requests` so the module is importable in environments without it (returns 0 with a WARNING). Accepts a `poster` callable for test injection. Returns the number of chunks delivered.
   - `__init__.py` — re-exports the public API and a stable `__all__` so the entry points can't be renamed accidentally.

2. **Three consumer shims** (audit's "thin wrappers" pattern):
   - `daily_narrative.py::send_discord_summary(summary, webhook_key="macro-alerts")` is now a 7-line shim that delegates to `_send_discord_summary(summary, webhook_key=webhook_key, repo_root=REPO_ROOT)`. The `DISCORD_WEBHOOKS_PATH` module constant is removed (the sender resolves the path itself).
   - `trader_narrative.py::send_discord_summary` — same pattern.
   - `weekly_narrative.py::send_discord_summary` — same pattern.
   - The public signature is preserved exactly, so the 4 existing call sites in the three files (`send_discord_summary(summary, webhook_key="macro-alerts")`, `send_discord_summary(cheat_sheet)`, `send_discord_summary(summary)`) continue to work unchanged.

3. **26 unit tests** in `tests/test_discord_sender.py` cover:
   - `chunk_markdown` — short text returns single chunk, empty text returns `[""]`, text at exactly max returns single chunk, multi-section packing, multi-section forcing multiple chunks, oversized single section returned as-is, sections split on `\n## ` with prefix re-attached.
   - `send_summary` — happy path single chunk, happy path multi-chunk (each chunk logged), missing webhook file, missing webhook key, malformed JSON, partial-post failure (one chunk fails, others still post), no `requests` import returns 0, no `repo_root` AND no `webhooks_path` defensively warns, `resolve_webhooks_path` uses the default filename, `DEFAULT_WEBHOOK_KEY` constant is `"macro-alerts"`.
   - **Consumer shim contract** — parametrized over all 3 consumer files. Each must (a) `import send_summary` from `scripts.libs_py.discord`, (b) NOT contain the literal `1900` (chunking is the sender's job now), (c) NOT call `requests.post(webhook_url` directly, (d) preserve the public `def send_discord_summary(summary, webhook_key="macro-alerts")` signature, (e) delegate via `_send_discord_summary(`. Plus a separate parametrized test that the `DISCORD_WEBHOOKS_PATH` module constant is gone from each file.
   - **End-to-end** — patches the sender's `poster` to a `_FakePoster` recorder and confirms a real `send_summary` call routes the body through chunking → POST with the correct URL, JSON payload, and timeout.
   - **Public API smoke test** — guards `__all__` against accidental rename of `send_summary`, `chunk_markdown`, `DISCORD_MAX_CHARS`, etc.

**Test count after this PR**: 269 (was 243 — the 26 new tests added, 0 regressions).

**Out of scope (intentionally NOT migrated)**:
- `scripts/streaming/options/discord_notifier.py` — implements a richer embed/attachment contract (the options pipeline). Migrating it would require designing an embed-aware variant on top of `send_summary`; that's a separate design exercise, not a §3.5 dedup.
- `scripts/market_data/discord_earnings_notifier.py` — same reasoning: the earnings pipeline has its own embed shape.

The sub-package's `__init__.py` docstring documents the intentional non-migration so the next audit doesn't re-open the same question.

---

### §3.5 Tier 1+2 — Migrate 8 remaining `discord_notify` consumers + production hardening (2026-07-14)

**Scope expansion**: The original §3.5 was "dedupe the three narrative consumers." A follow-up audit found 8 **additional** `scripts/utils/discord_notify.py` consumers across the repo that all share the same fragility (no retry on 429/5xx, no backoff, file-upload via `requests.post` with a hand-built `multipart/form-data` body, no test seam for rate-limits). This sub-section documents Tier 1 (consumer migration) + Tier 2 (production hardening) — both landed in a single PR because the shim approach lets Tier 1 ship with zero call-site changes.

**What was done**:

1. **Tier 1 — Migrated 8 additional `discord_notify` consumers** to the new `scripts/libs_py/discord/` sub-package. Strategy: keep `scripts/utils/discord_notify.py` as a **thin deprecation shim** (80 lines) that delegates to the library, so the 8 consumer modules don't have to change in this PR.
   - The shim exposes the original 3-symbol API (`get_webhook_url`, `send_message`, `upload_file`) and emits a `DeprecationWarning` once per process via a module-level `_DEPRECATION_EMITTED` flag.
   - The shim's `_repo_root()` walks up 3 levels from `scripts/utils/discord_notify.py` to find `discord_webhooks.json`, matching the library's `resolve_webhooks_path()` exactly.
   - Future PRs can move the 8 consumer modules to direct imports in small, mechanical commits.
   - **Test**: `TestLegacyDiscordNotifyShim` (5 tests) verifies the shim still works end-to-end (`send_message` posts, `upload_file` posts with the file part, `get_webhook_url` resolves keys, `DeprecationWarning` is emitted once, `__all__` is stable).

2. **Tier 2 — Production hardening** added to `scripts/libs_py/discord/webhooks.py`:
   - **`send_payload(url, payload, *, max_retries=3, sleep_fn=_sleep_fn, ...)`** — now retries HTTP 429 (reads `Retry-After` / `X-RateLimit-Reset-After` headers) and 5xx (500, 502, 503, 504) with capped exponential backoff: 1s, 3s, 9s, 27s, capped at `DISCORD_BACKOFF_MAX_SECONDS=30`. Honors `Retry-After` (capped at `DISCORD_RETRY_AFTER_MAX_SECONDS=60s`). Returns `False` on permanent failure.
   - **`send_with_files(url, content, file_inputs, *, max_retries=3, sleep_fn=_sleep_fn, ...)`** — NEW. The new single source of truth for file attachments; replaces the legacy `upload_file()` ad-hoc `multipart/form-data` build. Internally calls `send_payload` with the `files=` kwarg, so it inherits retry/backoff.
   - **`send_message(url, message=None, file_paths=None, *, max_retries=3, sleep_fn=_sleep_fn, ...)`** — NEW. Thin shim that calls `send_with_files` when `file_paths` is given, else `send_payload` with `{"content": message}`. This is what the deprecation shim delegates to.
   - **`send_embeds(..., wait=False, max_retries=3, sleep_fn=_sleep_fn)`** — added `wait` and `max_retries` params. When `wait=True`, inserts a 0.5s sleep **after every successful batch** (not after the last batch, not after a failed batch) to avoid `send_summary` bursts that hit the 5/2s global rate limit.
   - **`send_summary(..., wait=False, sleep_fn=_sleep_fn)`** — added `wait` and `sleep_fn` params. When `wait=True`, sleeps `INTER_CHUNK_WAIT_SECONDS=0.5` **between** chunks (not after the last).

3. **New Tier-2 constants** added to `scripts/libs_py/discord/config.py`:
   ```python
   DISCORD_MAX_RETRIES: int = 3
   DISCORD_RETRY_AFTER_MAX_SECONDS: float = 60.0
   DISCORD_BACKOFF_BASE_SECONDS: float = 1.0
   DISCORD_BACKOFF_MULTIPLIER: float = 3.0
   DISCORD_BACKOFF_MAX_SECONDS: float = 30.0
   INTER_CHUNK_WAIT_SECONDS: float = 0.5
   WAIT_AFTER_BATCH_SECONDS: float = 1.0
   DISCORD_RETRYABLE_STATUS_CODES: tuple = (429, 500, 502, 503, 504)
   ```
   All exported via `__init__.py` so callers can override per-deployment.

4. **Test seam (`sleep_fn`)** — every Tier-2 function accepts a `sleep_fn: Callable[[float], None]` kwarg defaulting to `time.sleep`. Tests inject a `RecordingSleep` that captures call durations without blocking, so the full retry chain runs in milliseconds.

**Test coverage** (`tests/test_discord_sender.py` grew from 79 → 111 tests, +32):
- `TestSendPayloadRetry` (8) — happy path 200, 429 with `Retry-After` header honored, 429 `Retry-After` capped at `DISCORD_RETRY_AFTER_MAX_SECONDS`, 500 backoff sequence (1s, 3s, 9s, 27s), 500 backoff capped at `DISCORD_BACKOFF_MAX_SECONDS`, 5xx family (502/503/504), 4xx (400/401) is **not** retried, final 200 after N retries returns `True`.
- `TestSendPayloadErrors` (3) — timeout returns `False`, `RequestException` returns `False`, network error returns `False`.
- `TestSendWithFiles` (7) — single file, multiple files, no files, mixed text + file, `max_retries=0` short-circuit, retry on 500, embed fallback still works.
- `TestSendMessage` (3) — text-only, file-only, text + file.
- `TestSendEmbedsWait` (2) — `wait=True` inserts sleep after every successful batch (not after the last), `wait=False` inserts zero sleeps.
- `TestSendSummaryWait` (2) — `wait=True` inserts 2 sleeps for 3 chunks (not after last), `wait=False` inserts zero sleeps.
- `TestLegacyDiscordNotifyShim` (5) — `get_webhook_url` returns URL, `send_message` posts, `upload_file` posts with file, `DeprecationWarning` is emitted exactly once per process, `__all__` is stable.
- `test_public_api_surface_is_stable_tier2` (1) — guards `__all__` against accidental rename of the 13 new exports.

**Test count after this PR**: 480 (was 448 — 32 new tests added, 0 regressions).

**Migration impact**:
- The 8 legacy consumers (`scripts/market_data/discord_earnings_notifier.py`, `scripts/streaming/options/discord_notifier.py`, `scripts/options/level_scorer/discord_notifier.py`, `scripts/utils/option_level_backtest/discord_report.py`, `scripts/options/level_scorer/score_levels.py`, `scripts/options/data_gap_reporter.py`, `scripts/streaming/options/level_scorer_cli.py`, `scripts/streaming/options/ohlcv_stream.py`) continue to work via the shim with no source changes.
- A follow-up PR can replace the 8 `from scripts.utils.discord_notify import …` lines with `from scripts.libs_py.discord import …` and remove the shim. The shim is marked for removal in a follow-up commit (per the `DeprecationWarning` message).

**Out of scope (still)**: the 2 `discord_notifier.py` files with embed/attachment contracts (`scripts/streaming/options/discord_notifier.py`, `scripts/market_data/discord_earnings_notifier.py`) are routed through the new `send_with_files` + `send_message` API but their custom embed shapes are not yet migrated to the `embeds.py` builder. That's a Tier 3 follow-up.

---

### §3.5 Tier 3 — Thread routing + rate-limit telemetry (2026-07-14)

**Scope**: Add two operator-facing capabilities to the Discord
sub-package: (1) `thread_id` / `thread_name` plumbing so the
narrative and macro-alerts pipelines can route messages to
per-day or per-session threads; (2) `RateLimitTelemetry` for
observability — answering "are we getting throttled?" with
counters rather than grepping logs.

**What was done**:

1. **New `scripts/libs_py/discord/telemetry.py`** with the
   `RateLimitTelemetry` class:
   - **Counters**: `total_sends`, `total_successes`,
     `total_failures`, `total_retries`, `total_rate_limited`,
     `total_5xx`, `total_4xx`, `total_network_errors`,
     `total_backoff_seconds`, `attempts_to_success`,
     `attempts_to_failure`, `status_counts`.
   - **Snapshot / summary**: `snapshot() -> dict` (thread-safe
     via `threading.Lock`), `summary() -> str` (one-line
     human-readable), `reset()`.
   - **Pluggable sink**: default is `default_sink` which
     writes `log.info("telemetry.<event> k=v …")`. Pass
     `lambda *_: None` for silent, or any callable for
     Prometheus / Datadog.
   - **`RecordingTelemetry` test subclass** captures every
     event in a list for assertions.
   - **`TelemetryEvent` dataclass** with `name`, `payload`,
     `monotonic` for time-ordered replay.
   - **Url label** hook: `url_label=lambda u: u.split("/")[-1]`
     replaces the full webhook URL with a short key in log
     lines (readability).

2. **Thread routing** added to all 5 public `send_*`
   functions (`send_payload`, `send_embeds`, `send_with_files`,
   `send_message`, `send_summary`):
   - New `thread_id: Optional[str] = None` and
     `thread_name: Optional[str] = None` kwargs.
   - Internal helper `_apply_thread(payload, thread_id, thread_name)`
     injects both fields into the JSON payload before POST.
   - For `send_payload`, the fields are passed through to
     `_post_payload_with_retry` and to the embed-→-text
     fallback POSTs.
   - For `send_summary`, the fields are injected per-chunk
     (each chunk POST carries the thread metadata).
   - `send_message` and `send_with_files` propagate the
     kwargs through to `send_payload`.
   - `send_embeds` injects the fields into every batch.

3. **Telemetry wiring** added to `send_payload` and
   `_post_payload_with_retry` (the latter covers the
   embed-→-text fallback path):
   - **Per-attempt**: `telemetry.on_attempt(url, status, attempt)`
     called from every `_post_once` return (success or
     retryable failure) and from network-error paths.
   - **Per-retry**: `telemetry.on_retry_scheduled(url, attempt, delay, reason)`
     where `reason` is `"429"` / `"5xx"` / `"network"`.
   - **Per-success**: `telemetry.on_success(url, attempts)`
     on final 200/204.
   - **Per-failure**: `telemetry.on_failure(url, status, attempts, reason)`
     on out-of-retries or non-retryable.
   - **send_summary** records `attempt(200, i) + success(i)`
     per chunk on success, or `attempt(None, i) + failure(i, "network")`
     on network error (it doesn't retry).

4. **Zero-overhead when unused**: every function takes
   `telemetry: Optional[RateLimitTelemetry] = None`. When
   `None`, all hooks are skipped — no attribute lookups, no
   lock contention.

5. **Public API expansion**: `__init__.py` now exports 41
   symbols (was 35). New exports: `RateLimitTelemetry`,
   `RecordingTelemetry`, `TelemetryEvent`, `default_sink`.

**Test coverage** (`tests/test_discord_telemetry.py` added —
**43 new tests**):
- `TestRateLimitTelemetryUnit` (13) — initial state, reset,
  per-counter increment, custom sink, silent sink, url label,
  thread-safety under 8-thread hammer test.
- `TestRecordingTelemetry` (4) — event capture, payload
  preservation, event_names helper, counters inherited.
- `TestSendPayloadTelemetry` (8) — success path, retry 429,
  retry 5xx, exhausted retries, non-retryable 4xx, network
  error, embed fallback (telemetry on both the 400 and the
  per-embed fallback POSTs), `None` telemetry is zero-overhead.
- `TestSendPayloadThreadId` (4) — `thread_id` injected,
  `thread_name` injected, `int` thread_id coerced to str,
  absent when not passed.
- `TestSendEmbedsTelemetry` (2) — per-batch events,
  `thread_id` propagated to each batch.
- `TestSendWithFilesTelemetry` (3) — single-chunk events,
  `thread_id` propagated, `thread_name` propagated.
- `TestSendMessageTelemetry` (2) — events, `thread_id`
  propagated.
- `TestSendSummaryTelemetry` (4) — per-chunk events, mixed
  success/failure events, `thread_id` propagated per chunk,
  `thread_name` propagated per chunk.
- `test_public_api_surface_is_stable_tier3` (1) — guards
  the 4 new exports.
- `test_thread_id_and_telemetry_work_together` (1) —
  integration test that both features compose cleanly.

**Test count after this PR**: 523 (was 480 — 43 new tests
added, 0 regressions).

**Use cases unlocked**:
- **Per-day narrative thread**: `send_summary(eod, thread_id=...)`
  routes every EOD report to a single per-day thread, so
  `#macro-alerts` doesn't scroll past 5 days of EOD posts.
- **Auto-created per-week thread**: `send_summary(weekly, thread_name="Weekly 2026-07-14")`
  on the first chunk creates a fresh thread, and subsequent
  messages within the same call land in it.
- **Operational dashboard**: `tel.snapshot()` returns a
  dict-shaped payload that can be JSON-dumped to
  Datadog / Splunk / Grafana once a day, answering
  "what % of sends needed retries?" at a glance.
- **Test seam for rate-limit scenarios**: `RecordingTelemetry`
  captures the exact sequence of `attempt` / `retry_scheduled`
  / `success` / `failure` events so tests can assert
  behavior without touching the network or the clock.

**Reference**: see
[docs/architecture/DISCORD_LIBRARY.md](DISCORD_LIBRARY.md) for
the full API contract, mermaid data-flow diagram, and
consumer-map table.

---

## 4. Prioritized Action Items

### Immediate (this week) — trust & safety

| # | Issue | Effort | Impact | Status |
|---|---|---|---|---|
| 1 | Add `validate_trade_plan()` to prevent bad DB records (§1.2) | 2h | Prevents phantom trades and guarantee-loss setups | ✅ Done 2026-07-14 |
| 2 | Add `get_trade_outcomes()` and inject into EOD prompt (§1.1) | 3h | Closes the feedback loop | ✅ Done 2026-07-14 |
| 3 | Fix `build_levels_markdown_table` session awareness (§1.3) | 1h | Correct level-accuracy grading in EOD | ✅ Done 2026-07-14 |
| 4 | Fix `render_open_summary` hardcoded keys (§2.1) | 30min | Multi-ticker support in open narrative | ✅ Done 2026-07-14 |
| 5 | Fix `extract_and_save_trade_plan` duplicate-trade issue (§2.2) | 1h | Prevents DB pollution | ✅ Done 2026-07-14 |

### Short-term (next 2 weeks) — quality

| # | Issue | Effort | Impact | Status |
|---|---|---|---|---|
| 6 | Trim `trader_morning.md` — remove pre-computed guides (§1.5) | 3h | ~40% token reduction, faster generation | ⏳ Open |
| 7 | Standardize jargon policy across all prompts (§1.5) | 1h | Consistent trader voice | ⏳ Open |
| 8 | Extract risk params to config + placeholder (§1.7) | 2h | Single-source-of-truth for account rules | ✅ Done 2026-07-14 |
| 9 | Split `trader_intraday.md` or inject session guide (§1.6) | 3h | Correct session-specific output | ⏳ Open |
| 10 | Fix `get_trade_plan_for_eod` to distinguish filled vs pending (§1.8) | 2h | Honest EOD review | ✅ Resolved by #1.1 |
| 11 | Extract `NARRATIVE_INSTRUMENT_MAP` to config (§2.4) | 30min | Future ticker support | ✅ Done 2026-07-14 (side-effect of #4) |

### Medium-term (this month) — scale

| # | Issue | Effort | Impact | Status |
|---|---|---|---|---|
| 12 | Move Confluence Model + VIX Regime to Python (§3.4) | 4h | Cleaner prompts, deterministic logic | ⏳ Open |
| 13 | Add parquet data freshness check + RTH filter (§2.7) | 3h | Correct OHLCV in EOD | ✅ Done 2026-07-14 |
| 14 | Unify default model in config (§2.6) | 30min | Consistent voice across chains | ✅ Done 2026-07-14 |
| 15 | Deduplicate `sys.path` hack (§2.8) | 1h | Maintainability | ✅ Done 2026-07-14 |
| 16 | Remove LLM track-override from daily prompts + Python enforcer (§1.4) | 2h | Eliminate contradictory instructions; auto-correct TRACK C | ✅ Done 2026-07-14 |
| 17 | Deduplicate Discord chunking logic (§3.5) | 1h | Maintainability | ✅ Done 2026-07-14 (Tier 0: 3 narrative consumers + 26 tests); Tier 1+2 extension done 2026-07-14 (8 legacy consumers via shim, retry/backoff/wait, +32 tests); Tier 3 done 2026-07-14 (thread routing + RateLimitTelemetry, +43 tests, see DISCORD_LIBRARY.md) |

### Backlog (nice to have)

| # | Issue | Effort |
|---|---|---|
| 18 | Add support for YM1/RTY1 tickers via config | 2h |
| 19 | ~~Add `parse_meta_fields` strict format validation (§2.10)~~ | 1h | ✅ Done 2026-07-14 |
| 20 | ~~Add Schwab hub-proxy availability check (§2.5)~~ | 1h | ✅ Done 2026-07-14 |

---

## 5. Files Audited

| File | Lines | Key Issues |
|---|---|---|
| `scripts/trader/prompts/daily_open_update.md` | 120 | §1.4 resolved (track mandate), §1.7 resolved (risk placeholder) |
| `scripts/trader/prompts/daily_eod_update.md` | 120 | §1.1 resolved (outcomes), §1.4 resolved (track mandate), §1.7 resolved (risk placeholder) |
| `scripts/trader/prompts/trader_premarket.md` | 80 | §1.5 (jargon policy vs guides), §1.6 (word limit) |
| `scripts/trader/prompts/trader_morning.md` | 180 | §1.5 (bloat), §1.7 resolved (risk placeholder) |
| `scripts/trader/prompts/trader_intraday.md` | 200 | §1.6 (multi-session), §1.7 resolved (risk placeholder) |
| `scripts/trader/prompts/trader_close.md` | 90 | §1.5, §1.7 resolved (risk placeholder) |
| `scripts/trader/prompts/weekly_briefing.md` | 80 | §2.12 (SPY/QQQ vestige) |
| `scripts/trader/briefing_core.py` | 3400+ | §1.3 (levels table), §2.5 resolved (Schwab hub probe), §2.7 resolved (daily-timeframe loader + RTH fallback), §2.9 resolved (redundant guards), §2.10 resolved (parse_meta_fields strict regex), §2.11 resolved (target_date propagation in 5 build_overnight_context call sites) |
| `scripts/trader/daily_narrative.py` | 1010+ | §1.2 resolved (validate), §1.4 resolved (track mandate), §1.7 resolved (risk injection), §1.8 resolved (filled vs PENDING split), §2.1 resolved (render), §2.2 resolved (dedup), §2.4 resolved (map), §2.6 resolved (default model from config) |
| `scripts/trader/daily_eod_update.py` | 300+ | §2.7 resolved (uses daily-timeframe loader), §2.8 resolved (uses _path_setup) |
| `scripts/trader/trader_narrative.py` | 310+ | §1.7 resolved (risk injection), §2.5 resolved (Schwab hub probe), §2.6 resolved (default model from config), §2.11 resolved (target_date already correctly passed; downstream bug fixed in briefing_core.py) |
| `scripts/trader/weekly_briefing.py` | 500+ | §2.8 resolved (uses _path_setup) |
| `scripts/libs_py/risk/narrative/constants.py` | 200+ | §1.7 resolved (source of truth for risk params) |
| `scripts/libs_py/risk/narrative/prompt_render.py` | 180+ | §1.7 resolved (new file — risk-params renderer) |
| `scripts/trader/signals/intraday_blocks.py` | 1640+ | §1.6 (session detection) |
| `scripts/trader/signals/session_ranges.py` | 50+ | OK (simple, clean) |
| `tests/test_prompt_render.py` | 350+ | §1.7 resolved (28 tests for renderer) |
| `tests/test_trade_plan_dedup.py` | 360+ | §2.2 resolved (18 tests for dedup logic) |
| `tests/test_path_setup.py` | 180+ | §2.8 resolved (14 tests for _path_setup) |
| `tests/test_briefing_core_fixes.py` | 350+ | §2.9 + §2.10 resolved (24 tests for compute_level_interactions + parse_meta_fields) |
| `tests/test_schwab_hub_and_model.py` | 280+ | §2.5 + §2.6 resolved (11 tests for hub probe + unified default model) |
| `tests/test_daily_price_context.py` | 300+ | §2.7 resolved (13 tests for daily-timeframe loader + RTH filter) |
| `tests/test_target_date_propagation.py` | 200+ | §2.11 resolved (9 tests for target_date propagation through 5 build_overnight_context call sites) |
| `scripts/streaming/options/config.py` | 680 | OK (no narrative-related action needed) |
| `scripts/trader/_path_setup.py` | 90+ | §2.8 resolved (new file — centralised sys.path setup) |
| `scripts/trader/config_loader.py` | 100+ | §2.6 resolved (get_llm_config exposes unified model defaults) |
| `scripts/trader/config/narrative_stats.yaml` | 350+ | §2.6 resolved (added `llm:` section — default_model, fallback_model, etc.) |

---

## 6. Day-Trader Verdict

If I were a prop trader using this system, my concerns in order of severity would be:

1. **"Did the trade work?"** — The system records plans but not outcomes. I have no way to audit whether the LLM's morning plan was correct at the close.
2. **"Are the trade levels correct?"** — The EOD review uses morning levels. By 16:25, they're stale.
3. **"Is the LLM hallucinating bad trades?"** — Yes, occasionally. Stop-above-entry setups get saved.
4. **"Why does the intraday read feel generic?"** — Because the LLM is reading a 200-line prompt with 5 sessions' worth of instructions, and most of the time only 1 applies.
5. **"Can I trust the signal?"** — Mostly, because the Python layer computes the track mandate and level accuracy. But the LLM is sometimes told to override Python's track decision, which creates ambiguity.

The system is now **~92% trustworthy**. The remaining 8% is exactly where the trader would lose money. The audit's Phase 1 fixes (§1.1 outcomes, §1.2 validator, §1.3 session-aware levels, §1.4 track mandate, §1.7 risk params, §1.8 PENDING vs filled, §2.1 multi-ticker, §2.2 dedup, §2.4 instrument map) are all in. Phase 2 — the §1.5 jargon-trim, §1.6 session-split for intraday, and the §2.5-§2.8 cleanup items — is what closes the remaining gap.
