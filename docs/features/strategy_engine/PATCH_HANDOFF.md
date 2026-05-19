# 🤖 SYSTEM TASK BLUEPRINT: Strategy Engine Performance & Guardrail Optimization

**Context:** TCM Trading System — Options Strategy Engine

**Target Files:**
- `scripts/libs_py/strategy_engine/services/ict_service.py`
- `scripts/libs_py/strategy_engine/engine.py`
- `scripts/libs_py/strategy_engine/paper_exec.py`

---

## 🛑 MANDATORY PHASE 1: Pre-Flight Code Verification

Before writing, modifying, or refactoring any code, you must query the workspace files and verify the following architectural assumptions. If the existing codebase has already mitigated any of these issues via an undocumented pattern or alternative layer, output a `Verification Report` specifying how it was handled and stop execution until explicitly told to proceed.

### Check List:

1. **Asynchronous Blocking Check:** Inspect `ict_service.py`. Is the pandas/numpy vector math execution inside `get_context()` running directly inside the async loop, or is it already wrapped in a thread pool executor or multiprocessing daemon?
2. **Intraday Staleness Isolation Check:** Inspect `engine.py` and `_check_index_staleness()`. Is the `15-minute` staleness hard gate applied globally across all strategies, or does the code already feature a lower cadence toggle (e.g., $\le 30$ seconds) specifically for the `ZERO_DTE_PCS` category?
3. **Slippage Modeling Check:** Inspect `paper_exec.py`. Does the `open_signal()` or `close_trade()` function feature an option to accept or calculate a spread-based slippage factor, or is it strictly using raw `mid` calculations without modifiers?

---

## 🛠️ PHASE 2: Required Code Modifications

*Only proceed with this phase if Phase 1 reveals that these optimizations do not exist in the codebase.*

### Task A: Offload CPU-Bound ICT Computations to Thread Pool

* **Target:** `scripts/libs_py/strategy_engine/services/ict_service.py`
* **Issue:** Vectorized indicator parsing (FVG, OB, BPR) via numpy/pandas runs synchronously inside `index_tick()`, blocking the core asyncio event loop when multiple variants tick simultaneously.
* **Refactor Instructions:**
1. Separate the heavy pandas extraction math from the async wrapper.
2. Utilize `asyncio.get_running_loop()` and `loop.run_in_executor(None, ...)` to run the synchronous vector crunching in an isolated thread worker.

### Task B: Strategy-Specific Staleness Toggles

* **Target:** `scripts/libs_py/strategy_engine/engine.py`
* **Issue:** A global 15-minute data staleness allowance is highly dangerous for 0DTE option options where gamma risk expands exponentially in minutes.
* **Refactor Instructions:**
1. Modify `_check_index_staleness(self, ticker: str, now: datetime)` or the core ticking logic.
2. Accept or inspect the strategy type calling the routine. If the strategy is `ZERO_DTE_PCS`, enforce a hard data staleness gate of **30 seconds** maximum. Keep longer dated thresholds at 15 minutes.

### Task C: Anti-Optimism Slippage Adjuster

* **Target:** `scripts/libs_py/strategy_engine/paper_exec.py`
* **Issue:** Executing multi-leg index paper options strictly at the exact bid-ask midpoint yields an unrealistic performance baseline compared to real-world execution on the Schwab API.
* **Refactor Instructions:**
1. Inject a configurable `slippage_pct` (defaulting to a conservative 2% to 5% of the option leg's total bid-ask spread width) into `open_signal` and `close_trade` calculations.
2. Penalize credit entries and debit exits by this slippage value to ensure paper equity curves mirror real trading friction.

---

## 🔍 PHASE 3: Regression Test & Verification

Following any changes, confirm the system complies with these baseline guardrails:

* Verify that standard 45 DTE credit spread cycles do not fail execution due to the tight 30-second 0DTE staleness gate.
* Ensure SQLite database writes continue to track the exact `fill_assumption` string inside `Trade.metadata`.
* Double-check that your thread executor does not break connection pools linked to the primary Prisma SQLite instance.
