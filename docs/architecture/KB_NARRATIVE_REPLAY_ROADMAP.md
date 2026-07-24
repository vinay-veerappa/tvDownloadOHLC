# KB-Narrative Integration & Historical Replay Roadmap

**Status:** Living document — tracks the effort to make the KB actually
matter in narratives, and to enable full historical-day replay with virtual
trade execution.
**Created:** 2026-07-23
**Owner:** Consumer repo (`tvDownloadOHLC`)
**Depends on:** `docs/architecture/KB_BRIDGE.md` (Phases 2-4, KB API, bridge
module), `scripts/knowledge_bridge/confluence_engine.py` (Phase 5)

---

## 1. The problem

`fetch_kb_context()` is wired into `briefing_core.build_premarket_context()`
and appends ~2,200 chars of grounded ICT KB units to the cheat sheet before
the LLM call. But the `--compare` test (2026-07-23) showed the narratives with
and without KB context are **nearly identical**:

| Mode | Without KB | With KB | Difference |
|------|-----------|---------|------------|
| premarket ES1 | 1,696 chars | 1,648 chars | cosmetic phrasing |
| open ES1 | 2,141 chars | 2,124 chars | cosmetic phrasing |
| close ES1 | 1,511 chars | 1,482 chars | cosmetic phrasing |
| intraday ES1 | 82 chars | 87 chars | session-closed stub |

**Root cause:** The prompt templates were written *before* the KB existed.
They say "trust the Python output" and "no jargon" — actively suppressing the
ICT-aware reasoning the KB would enable. The KB context is **present but not
instructed**. The LLM treats it as noise.

**Secondary gap:** There is no way to replay a historical day end-to-end.
The confluence engine and narrative pipeline only run against "now". There is
no harness that ties narrative → confluence → trade plan → virtual execution
→ outcome evaluation for a specific past date.

---

## 2. The end goal

Pick any historical trading day → the system:

1. Produces a **KB-augmented narrative** (premarket read with ICT grounding)
2. Runs the **confluence engine** → signals, direction, confidence, KB citations
3. Generates a **trade plan** (entry, stop, target, max exit time)
4. **Executes virtual trades** against actual 1m OHLCV bars for that day
5. **Evaluates outcomes** (win/loss, MFE/MAE, RR achieved, prop-firm viability)
6. Produces a **report** comparing what the LLM said vs what actually happened

This is a "real backtest of what is possible" — it closes the loop from
KB → narrative → confluence → trade plan → execution → evaluation.

---

## 3. What we already have (building blocks)

| Component | Location | Status | Notes |
|---|---|---|---|
| `load_fused_data(ticker, "1m")` | `scripts/utils/fused_data_loader.py` | ✅ | Live parquet covers ~1 year (2025-01-01 → now); historical parquet covers 2006-2024. Fused = both deduped. |
| `trader_narrative.py --sim-time` | `scripts/trader/trader_narrative.py` | ✅ | `--sim-time "2026-07-16 12:00"` simulates running at that ET timestamp. Filters data to ≤ sim_time, sets target_date. |
| `build_premarket_context(target_date=)` | `scripts/trader/briefing_core.py` | ✅ | Already accepts `target_date`; uses `load_fused_data` which covers historical dates. |
| `build_overnight_context(loader, ticker, target_date)` | `scripts/trader/briefing_core.py` | ✅ | Works for any historical date with 1m data. |
| `fetch_kb_context(cheat_sheet)` | `scripts/knowledge_bridge/kb_context.py` | ✅ | Scans cheat sheet for 34 ICT concept triggers → queries KB API → returns formatted block. Now wired into `build_premarket_context()`. |
| `ConfluenceEngine.run(ticker)` | `scripts/knowledge_bridge/confluence_engine.py` | ✅ | 6 signal providers (GEX, Herman, session, ICT features, structure, classification). Produces `ConfluenceResult` with `TradePlan`. |
| `VectorizedBacktester` | `scripts/trading_framework/core/backtest_engine.py` | ✅ | Takes standardized signals (signal_time, direction, entry, stop, target) → runs against 1m bars. |
| `PropFirmSimulator` | `scripts/trading_framework/ml/prop_firm_simulator.py` | ✅ | Evaluates trade results against prop-firm profiles (Apex, TopStep, FTMO). `FIRM_PROFILES` presets. |
| `compute_all_session_ranges(df, target_date, ET)` | `scripts/trader/signals/session_ranges.py` | ✅ | Computes session ranges (ASIA, LONDON, PRE_NY, RTH, etc.) from 1m parquet — works for any historical date. |
| `compute_herman_pre_ny_sweep(pre_ny, london_high, london_low)` | `scripts/libs_py/nqstats/classifiers.py` | ✅ | Herman sweep detection — works from session range data. |
| Prompt templates | `scripts/trader/prompts/trader_*.md` | ⚠️ | 4 templates (premarket, morning, intraday, close) — NOT KB-aware. This is the Phase A fix. |
| Confluence engine historical replay | — | ❌ | Engine calls `datetime.now()` internally; reads live GEX JSON. Needs a `sim_dt` pass-through. Phase B fix. |
| Historical GEX / ICT features JSON | — | ❌ | Only "latest" snapshots exist. For historical days, these signals must be skipped (graceful degradation) or reconstructed. Phase B limitation. |
| Day replay harness | — | ❌ | Nothing ties it together. Phase B/D. |
| Virtual trade evaluator | — | ❌ | Phase C. |

---

## 4. Phased plan

### Phase A — KB-aware prompt rewrite (quick win, ~30 min)

**Goal:** Make the KB context actually change the narrative.

**What changes:**
Rewrite the 4 prompt templates (`trader_premarket.md`, `trader_morning.md`,
`trader_intraday.md`, `trader_close.md`) to add:

1. **KB USAGE section** — tell the LLM the KB block exists at the bottom of the
   cheat sheet and how to use it:
   - "The cheat sheet may include a `# ICT KNOWLEDGE BASE CONTEXT` block at
     the end. These are grounded source units from ICT transcripts (with
     confidence scores and verbatim anchors). Use them to explain *why* a
     setup is relevant in current conditions, not just *what* the levels are."
2. **Relax the jargon policy when KB-grounded** — allow ICT terminology
   *when cited from the KB*, still translate for the reader:
   - "You may use ICT terminology (FVG, CSD, MSS, etc.) when explaining a
     setup, provided you cite the KB source and translate the term for the
     reader in the same sentence."
3. **Citation requirement** — "when you reference a setup pattern or
   methodology, cite the KB source: e.g. 'Per ICT 2024-08-29 transcript (conf
   0.80), a CSD after a liquidity sweep signals...'"
4. **Confluence-reading instruction** — "use KB units to connect the current
   market state to specific ICT setups. Don't just list levels — explain
   which setup is forming and what would confirm or invalidate it."

**Verification:**
Re-run `python -m scripts.knowledge_bridge.test_narrative --mode premarket
--ticker ES1 --compare` and confirm the KB-augmented narrative is now
meaningfully different (not just cosmetic phrasing).

**Success criteria:**
- The KB-augmented narrative references at least 2 specific KB source units
- The KB-augmented narrative uses at least 3 ICT terms (FVG, CSD, MSS, etc.)
  with citations
- The KB-augmented narrative explains *why* a setup is relevant, not just
  *what* the levels are

**Output:** Updated prompts in `scripts/trader/prompts/`, compare results
in `logs/kb_test/`.

---

### Phase B — Historical replay harness (~1-2 hours)

**Goal:** Run the full narrative + confluence pipeline for any historical day.

**What changes:**

#### B.1: Fix `confluence_engine.py` for historical replay

`ConfluenceEngine.build_context()` and signal providers currently call
`datetime.now()` and read "live" GEX/ICT JSON. Fix:

- Add `sim_dt: datetime | None` param to `build_context()` and `run()`
  (already has `now_et` param — just needs to be threaded through all
  providers consistently).
- GEX provider: when `sim_dt` is set, skip live JSON read (no historical
  GEX data) → signal provider returns `[]` (graceful degradation). The
  other 5 signals (Herman, session, ICT features, structure, classification)
  all work historically from 1m parquet.
- ICT features provider: when `sim_dt` is set, look for
  `data/derived/{ticker}_ict_features_{date}.json` instead of `_latest.json`.
  If not found → skip.
- All `datetime.now()` calls in providers → use `ctx.now_et` (which is
  already on `LiveContext` but not consistently used).

#### B.2: Create `scripts/knowledge_bridge/historical_replay.py`

```
python -m scripts.knowledge_bridge.historical_replay \
    --date 2026-07-16 --ticker ES1
```

Flow:
1. Parse `--date` → `target_date`, set `sim_dt` to 09:30 ET that day
2. Call `build_premarket_context(loader, nq_ticker=ticker, target_date=date)`
   — this already works historically (uses `load_fused_data`)
3. KB context is already appended by `build_premarket_context()` (Phase A
   wiring) — but also call `fetch_kb_context()` separately to save it
4. Call `ConfluenceEngine.run(ticker, target_date=date, now_et=sim_dt)`
5. Feed the cheat sheet + KB context through the KB-aware prompt (Phase A)
   to the LLM
6. Save all outputs to `logs/replay/{date}_{ticker}/`:
   - `narrative.md` — the LLM narrative
   - `cheatsheet.txt` — the cheat sheet
   - `kb_context.txt` — the KB context block
   - `confluence.json` — the confluence result
   - `trade_plan.json` — the trade plan
   - `session_1m.csv` — the 1m bars for that day (for Phase C)

**Limitations (documented, not blocking):**
- No historical GEX data → GEX signal skipped for historical days
- ICT features only available if precomputed JSON exists for that date
- Calendar/earnings/news signals will show "today's" data (not historical)
  — these are lower-priority signals and can be skipped or flagged as
  "not available for historical replay"

**Verification:**
Run for 2-3 known historical days and confirm the confluence engine produces
a direction + trade plan. Compare the trade plan's predicted direction
against what actually happened that day (manual check).

---

### Phase C — Virtual trade execution + outcome evaluation (~1-2 hours)

**Goal:** Execute the trade plan against actual 1m bars and evaluate.

**What changes:**

#### C.1: Create `scripts/knowledge_bridge/virtual_trade_eval.py`

Takes the `TradePlan` from Phase B and:
1. Loads 1m bars for the replay date (`load_fused_data`, filtered to RTH
   09:30–16:00 ET)
2. Constructs a standardized signal DataFrame:
   ```
   signal_time: 09:30 ET
   direction: plan.direction (long/short)
   entry_price: plan.entry
   stop_price: plan.stop
   target1_price: plan.target
   ```
3. Runs `VectorizedBacktester` with this single signal
4. Records: fill time/price, MFE, MAE, outcome (target hit / stop hit /
   time exit at 16:00), RR achieved, P&L in price % (ADR-002)
5. Runs `PropFirmSimulator` on the single trade (or batch if we replay
   multiple days) for prop-firm viability
6. Returns a `TradeOutcome` dataclass with all metrics

#### C.2: Outcome evaluation

Compare:
- **Narrative accuracy:** Did the "What I'm watching" levels from the
  narrative get tested? Did the predicted direction play out?
- **Confluence accuracy:** Did the confluence engine's direction match the
  actual close vs open? Did confidence correlate with outcome?
- **Trade result:** Win/loss, P&L %, MFE/MAE, RR achieved vs planned
- **Level accuracy:** Which GEX walls / ICT levels / session range H/L
  held or broke?

---

### Phase D — End-to-end day replay report (~30 min)

**Goal:** One command that runs the full pipeline for a historical day.

```
python -m scripts.knowledge_bridge.replay_day --date 2026-07-16 --ticker ES1
```

Outputs a single Markdown report at
`logs/replay/{date}_{ticker}_replay.md` containing:

1. **The premarket narrative** (KB-augmented, from Phase A prompt)
2. **The confluence engine result** (signals, direction, confidence, KB
   citations, trade plan)
3. **The virtual trade execution** (entry, stop, target, price path, outcome)
4. **The outcome evaluation** (narrative accuracy, confluence accuracy,
   trade result, level accuracy)
5. **A scorecard** summarizing:
   - Narrative direction call vs actual
   - Confluence direction vs actual
   - Confluence confidence vs trade outcome
   - Key level hits/misses
   - Trade P&L and RR

This is the "real backtest of what is possible" — it closes the loop.

**Future extension (Phase E — not in scope yet):**
Batch-replay 20-50 days → aggregate statistics → prop-firm viability
evaluation → confidence calibration curve. This is the full backtest loop
from DESIGN §5.3, but for the narrative-driven path (not just candidate-
driven).

---

## 5. Dependency graph

```
Phase A (prompts) ──────┐
                        ├──► Phase B (replay harness) ──► Phase D (report)
                        │                                      ▲
                        │                                      │
                        └──► Phase C (trade eval) ─────────────┘
```

- Phase A is independent and is the highest-leverage fix.
- Phase B depends on A (the replay should use KB-aware prompts).
- Phase C depends on B (needs the trade plan from the replay).
- Phase D depends on B + C (needs both to assemble the report).

---

## 6. Testing strategy

### Per-phase verification

| Phase | Test | Pass criteria |
|---|---|---|
| A | `--compare` premarket + open + close | KB narrative references ≥2 KB sources, uses ≥3 ICT terms with citations, explains setup relevance |
| B | Replay 3 known historical days | Confluence engine produces direction + trade plan for each; trade plan direction is plausible (not random) |
| C | Virtual trade on 3 replayed days | Backtester fills the trade, records MFE/MAE, outcome is one of {target, stop, time-exit} |
| D | Full report for 1 day | Report contains all 5 sections; scorecard is populated; no crashes |

### End-to-end validation

Pick 5 trading days with known outcomes (e.g., big trend day, reversal day,
chop day, gap day, FOMC day). Run the full replay for each. Check:
- Does the narrative direction call match the actual day type?
- Does confluence confidence correlate with how clean the day was?
- Do the trade plans have positive expectancy across the 5 days?

---

## 7. File map (what gets created/modified)

| File | Phase | Action |
|---|---|---|
| `scripts/trader/prompts/trader_premarket.md` | A | Modify — add KB usage section |
| `scripts/trader/prompts/trader_morning.md` | A | Modify — add KB usage section |
| `scripts/trader/prompts/trader_intraday.md` | A | Modify — add KB usage section |
| `scripts/trader/prompts/trader_close.md` | A | Modify — add KB usage section |
| `scripts/knowledge_bridge/confluence_engine.py` | B | Modify — thread `sim_dt` through all providers |
| `scripts/knowledge_bridge/historical_replay.py` | B | **Create** — replay harness |
| `scripts/knowledge_bridge/virtual_trade_eval.py` | C | **Create** — trade execution + outcome eval |
| `scripts/knowledge_bridge/replay_day.py` | D | **Create** — end-to-end CLI |
| `logs/replay/{date}_{ticker}/` | B-D | Output directory for replay artifacts |

---

## 8. What this is NOT

- **Not a replacement for the candidate backtest loop** (Phase 4 in
  `backtest_loop.py`). That loop tests structured strategy candidates against
  20y data. This roadmap tests the *narrative-driven* path — does the LLM
  + KB + confluence produce a good trade plan for a specific day?
- **Not a full prop-firm evaluation.** Phase C runs `PropFirmSimulator` on
  the trade, but a proper evaluation needs 20+ trades (Phase E, future).
- **Not historical GEX reconstruction.** We skip GEX for historical days
  unless precomputed JSON exists. Reconstructing historical GEX is a
  separate project (options data pipeline).

---

## 9. Related docs

- [KB_BRIDGE.md](KB_BRIDGE.md) — Phases 2-4 (KB API, bridge module, candidate
  registry, backtest loop). The foundation this roadmap builds on.
- [TRADER_NARRATIVE_PLAN.md](TRADER_NARRATIVE_PLAN.md) — Original narrative
  engine design (session-adaptive, cheat sheet architecture).
- [NARRATIVE_ENGINE_V2_PLAN.md](NARRATIVE_ENGINE_V2_PLAN.md) — V2 design
  (12-block cheat sheet, confluence bias model, two-tier data).
- `C:\Users\vinay\video2pdf\knowledge_ingest\DESIGN.md` — Producer KB design
  (Layer 3 §5: strategy → execution, confluence engine, backtest loop).
- `C:\Users\vinay\video2pdf\knowledge_ingest\HANDOVER.md` — Canonical
  producer state log.