# Daily NY Levels — Product Requirements Document (PRD)

**Version:** 1.0  
**Created:** 2026-04-17  
**Author:** Vinay  
**Status:** Active — Phase 1 In Design  
**Source Script:** `scripts/indicators/DailyNYLevelsV2.pine` (v4.1)

---

## 1. Vision

Rebuild the Daily NY Levels indicator into a **modular, multi-platform toolkit** that supports predefined institutional session ranges, custom ranges, MFE/MAE analytics, and eventually automated strategy execution on NinjaTrader. The system is designed around reusable libraries and a clean data model so that new ranges, analytics, and execution modes can be added with minimal friction.

---

## 2. Scope — Deliverables

| ID | Deliverable | Platform | Location |
|----|-------------|----------|----------|
| **S1** | Daily NY Levels V5 (Core Indicator) | Pine Script v6 | `scripts/indicators/daily-ny-levels/` |
| **S2** | Range Session Library | Pine Script v6 | `scripts/indicators/daily-ny-levels/lib/` |
| **S3** | Excursion Analytics Library | Pine Script v6 | `scripts/indicators/daily-ny-levels/lib/` |
| **S4** | MFE/MAE Analytics Indicator | Pine Script v6 | `scripts/indicators/daily-ny-levels/` |
| **S5** | Daily NY Levels Indicator | NinjaScript (C#) | `scripts/indicators/daily-ny-levels/ninja/` |
| **S6** | Daily NY Levels Strategy | NinjaScript (C#) | `scripts/indicators/daily-ny-levels/ninja/` |

---

## 3. Range Catalog

The indicator supports **three compound presets** (each containing multiple sub-ranges) plus a **Custom** mode.

### 3.1 Preset Definitions

Each preset is a named group of sub-ranges. A sub-range has: Opening Range window (OR), Data/Cutoff window, and an optional directional qualifier.

#### Preset A — "Overnight / 0300 Transfer"

| Sub-Range | OR Start | OR End | Cutoff | Description |
|-----------|----------|--------|--------|-------------|
| 1800 Break | 18:00 | 18:15 | 03:00 | Overnight opening range breakout |
| 0300 Break | 03:00 | 03:05 | 08:30 | London open micro-range breakout |
| 0300 Transfer | — | — | — | Directional alignment: 0300 continuation in the direction of 1800 break |

#### Preset B — "Pre-Market / Q1"

| Sub-Range | OR Start | OR End | Cutoff | Description |
|-----------|----------|--------|--------|-------------|
| Q1 Break | 03:00 | 07:00 | 08:30 | Wide pre-market range breakout |
| Market Open | 09:30 | 09:35 | 12:00 | First 5-minute opening range breakout |
| Magic Hour | 06:00 | 08:30 | 12:00 | Pre-open expansion range breakout |

#### Preset C — "Intraday Breakouts"

| Sub-Range | OR Start | OR End | Cutoff | Description |
|-----------|----------|--------|--------|-------------|
| 1100 BO | 11:00 | 11:15 | 12:30 | Midday breakout |
| Market Open Wide | 08:30 | 12:00 | 16:00 | Morning session full range breakout |
| 1400 Break | 14:00 | 14:15 | 16:00 | Afternoon breakout |

#### Custom

| Field | Source |
|-------|--------|
| OR Start | User input (HHMM) |
| OR End | User input (HHMM) |
| Cutoff | User input (HHMM) |

### 3.2 Input UX

- **Single dropdown** (`input.string`) to select a preset or "Custom".
- When "Custom" is selected, HHMM text inputs become active.
- Each preset activates its sub-ranges simultaneously; MFE/MAE tracked independently per sub-range.

---

## 4. Phase Plan

### Phase 1 — Modularize & Generalize (Pine Script)  
**Status:** 🔵 In Design  
**Design Doc:** [`PHASE1_DESIGN.md`](PHASE1_DESIGN.md)

**Goal:** Rewrite the current indicator as a clean, modular Pine v6 script using UDTs, Pine sessions, and extracted libraries. No new analytics features — functional parity with V4.1 custom mode, plus the preset dropdown wired up.

**Key deliverables:**
- `RangeSpec` UDT and `RangeState` UDT
- Range Session Library (reusable)
- Drawing Utilities Library (reusable)
- Statistics Utilities Library (reusable)
- Core indicator script with preset dropdown
- Identical visual output to V4.1 when using equivalent custom range settings

**Acceptance criteria:**
1. Custom mode reproduces V4.1 output bar-for-bar.
2. Each preset sub-range shows its own OR box, reference levels, and MFE distribution.
3. All utility functions live in importable libraries.
4. No hardcoded range values in the main script.

---

### Phase 2 — MFE/MAE Analytics Indicator (Pine Script)  
**Status:** ⚪ Not Started — Requires Phase 1 completion  
**Design Doc:** To be created before implementation

**Goal:** Build a standalone analytics indicator that imports the Phase 1 libraries and adds MAE tracking, joint MFE/MAE profiles, excursion efficiency ratios, and enhanced statistical tables.

**Scope (to be refined):**
- MAE distribution (mirror of MFE logic, tracking adverse excursion)
- Joint MFE/MAE scatter or heatmap overlay
- Excursion efficiency: `MFE / (MFE + MAE)` per session
- R-multiple distribution (MFE / MAE ratio)
- Enhanced data table with MAE columns
- Potential: pivot/retracement depth analysis

**Open items:**
- [ ] MAE reference: against OR levels only, or also against entry proxy (e.g., OR close)?
- [ ] Visual layout: separate histogram below MFE, or overlaid?
- [ ] Should this script share the same chart instance or be a separate pane?

---

### Phase 3 — NinjaScript Indicator Port  
**Status:** ⚪ Not Started — Requires Phase 1 completion  
**Design Doc:** To be created before implementation

**Goal:** Port the Daily NY Levels core indicator to NinjaScript (C#), achieving visual and statistical parity with the Pine Script version.

**Scope (to be refined):**
- 1:1 range engine: same UDT concepts mapped to C# classes
- Session detection using NinjaTrader's `SessionIterator` or custom logic
- MFE tracking engine with same percentile/distribution model
- Drawing: NinjaTrader `Draw.*` API equivalents for OR box, histogram bands, stat lines
- Data table equivalent (NinjaTrader `Draw.TextFixed` or custom panel)
- Data retention: revisit — NinjaTrader allows longer lookback, may expand history window

**Open items:**
- [ ] NinjaTrader session template mapping for overnight ranges (cross-midnight)
- [ ] Bar-for-bar parity vs statistical tolerance — aim for strict, accept tolerance if needed (collect comparison data first)
- [ ] NinjaTrader charting object limits vs Pine `max_lines_count` etc.
- [ ] Library equivalent: NinjaScript partial classes or shared assemblies for reuse

---

### Phase 4 — NinjaScript Strategy & Automation  
**Status:** ⚪ Not Started — Requires Phase 3 completion  
**Design Doc:** To be created before implementation

**Goal:** Build an automated strategy on NinjaTrader that uses the same range engine to generate and manage trades.

**Scope (to be refined):**
- Entry logic: breakout of OR high/low with confirmation rules
- Exit logic: MFE-based targets, time stops, MAE-based stops
- Risk model: fixed contracts, volatility-scaled, account risk %
- Session filters: no-trade windows, news blackout integration
- Position management: max trades/day, daily loss lockout, trailing drawdown
- Fill model: slippage, commission assumptions (per ADR-009 micro-contract sizing)
- Operational safeguards: disconnection handling, order rejection, restart recovery
- Backtesting harness with NinjaTrader Strategy Analyzer integration

**Open items:**
- [ ] Which range preset(s) to automate first?
- [ ] Paper trade validation period before live
- [ ] Alert/notification integration (Discord, email)
- [ ] Strategy parameter optimization approach (NinjaTrader optimizer vs external)

---

## 5. Cross-Cutting Decisions

| Decision | Resolution | Rationale |
|----------|-----------|-----------|
| Range selection UX | Single dropdown + custom fallback | Cleaner than 9 booleans; prevents invalid multi-select |
| Data retention | Unlimited history (Pine). Revisit for Ninja. | Pine arrays grow with available bars; Ninja has configurable `BarsRequired` |
| Normalization | Price percentage (per ADR-002) | Cross-ticker, cross-era comparability |
| Timezone | America/New_York / ET (per ADR-001/004) | **All times stated in EST.** All session math in ET. |
| Current script | Preserved as-is (`DailyNYLevelsV2.pine`) | New script in `daily-ny-levels/` subfolder |
| Library architecture | 3 private Pine libraries: `RangeSessionLib`, `DrawingLib`, `StatsLib` | `StatsLib` absorbs excursion analytics; code locally first, publish to TradingView manually |
| Multi-range rendering | All compound preset sub-ranges render simultaneously | Each sub-range gets its own OR box, stat lines, and table rows |
| Sub-range colors | Auto-generated hue offsets from global bull/bear colors per sub-range | Avoids proliferating per-range color inputs |
| MAE — Absolute | `mae_bull_abs` from OR_low; `mae_bear_abs` from OR_high (same refs as MFE) | Symmetric worst-case adverse excursion |
| MAE — Pullback | Bull: worst retrace **below OR_HIGH** before peak bull MFE. Bear: worst retrace **above OR_LOW** before peak bear MFE. | Measures heat taken on the breakout side before the move plays out |
| Post-peak give-back | Not captured in Phase 1 or 2 | Pullback + absolute MAE is sufficient |
| MAE histogram rendering | Deferred to Phase 2; data captured in Phase 1 | Phase 1 = data integrity, Phase 2 = analytics rendering |
| Win / EV target | Per-range `ev_target_pct` input (default 0.3%); win = MFE ≥ ev_target; zero-MFE days **excluded** from win rate | Expected-value threshold aligns with risk management |
| Named percentile levels | 4 levels: **Confirm (P20)**, **Target1 (P50)**, **Target2 (P75)**, **Stretch (P90)** — all UI-configurable | Used for BO confirmation, targets, and invalidation |
| Pullback invalidation | **P80 of pullback MAE distribution** → BO invalidated | Statistically-grounded invalidation level |
| Live stat lines (Phase 1) | Draw from today's OR anchor forward: **P20 "BO Cashflow"**, **Median**, **Avg**, **P90 "Max MFE"** + **Range Mid** (dashed, with hit% label) | Real-time reference during session |
| Cross-midnight date stamp | **Cutoff date** (e.g., Monday date for 18:00 Sun → 03:00 Mon session) | Conventional futures trade-date convention |
| 0300 Transfer | 5-min OR (0300–0305). Direction = **bull if 1800 open > 0300 close**, bear if 1800 open < 0300 close. Skip day if 1800 data unavailable. | Continuation toward the overnight opening level |
| 1800 Break session days | Pine days `1,2,3,4,5` (Sun–Thu evenings) | Captures Sunday 18:00 futures reopen |
| Data table | Toggle dropdown (MFE View / MAE View / DOW View); auto-focuses on sub-range currently in its OR or data window | Clean single-table UX with view switching |
| Abbreviated sessions | Include all sessions; analyst excludes outliers manually | No auto-filtering |
| Conditional probability | MFE View includes: given P(n) hit, % reaching P(n+1) | Complements raw hit rate |
| DOW stats | Summary rows per DOW in DOW View (hit rate, avg MFE, EV win%) | In-table; no separate DOW histogram |
| R-multiple | `r_multiple = MFE / abs_MAE` stored per direction per day | Trade quality metric; rendered in Phase 2 table |

---

## 6. Global Open Items

| ID | Item | Phase | Status |
|----|------|-------|--------|
| O-1 | Compound preset simultaneous rendering | 1 | ✅ Resolved: all sub-ranges render simultaneously |
| O-2 | MAE reference point | 1 | ✅ Resolved: abs from OR_low/high; pullback from OR_high/OR_low (breakout level) |
| O-3 | NinjaScript parity tolerance bands | 3 | ⚪ Before Phase 3 |
| O-4 | Strategy: which preset to automate first | 4 | ⚪ Before Phase 4 |
| O-5 | Pine library publishing approach | 1 | ✅ Resolved: code locally, publish manually |
| O-6 | 0300 Transfer directional logic | 1 | ✅ Resolved: bull if 1800 open > 0300 close |
| O-7 | Data retention cap for NinjaTrader | 3 | ⚪ Before Phase 3 |

---

## 7. File Structure

```
scripts/indicators/daily-ny-levels/
├── DailyNYLevelsV5.pine              # Phase 1: Core indicator
├── DailyNYLevelsAnalytics.pine       # Phase 2: MFE/MAE analytics
├── lib/
│   ├── RangeSessionLib.pine          # Phase 1: Session/range UDTs & resolver
│   ├── DrawingLib.pine               # Phase 1: Drawing helpers
│   └── StatsLib.pine                 # Phase 1: Statistical utilities
└── ninja/
    ├── DailyNYLevels.cs              # Phase 3: NinjaScript indicator
    ├── DailyNYLevelsStrategy.cs      # Phase 4: NinjaScript strategy
    └── Lib/
        ├── RangeEngine.cs            # Phase 3: Range/session engine
        └── ExcursionEngine.cs        # Phase 3: MFE/MAE engine

docs/indicators/DailyNYLevels/
├── PRD.md                            # This document
├── PHASE1_DESIGN.md                  # Phase 1 detailed design
├── PHASE2_DESIGN.md                  # (created before Phase 2 work)
├── PHASE3_DESIGN.md                  # (created before Phase 3 work)
└── PHASE4_DESIGN.md                  # (created before Phase 4 work)
```

---

## 8. Resumption Protocol

When picking up work on any phase:
1. Read this PRD to understand scope and decisions.
2. Check the phase-specific `PHASE<N>_DESIGN.md` for detailed design.
3. Review open items (Section 6) — some may have been resolved since last session.
4. Verify the current script state in `scripts/indicators/daily-ny-levels/`.
5. Synchronize with `docs/architecture/ADR.md` and `docs/SecondBrain_Trading.md` per ADR-015.

---

**Last Updated:** 2026-04-17 (Phase 1 design decisions finalized)
