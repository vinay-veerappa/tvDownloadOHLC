# Daily NY Levels — Product Requirements Document (PRD)

**Version:** 1.3  
**Created:** 2026-04-17  
**Updated:** 2026-04-19  
**Author:** Vinay  
**Status:** Active — Phase 2 Levels Implemented (Chart Validation Pending)  
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

The indicator supports **ten individual presets** plus a **Custom** mode. The three compound preset groups ("Overnight / 0300 Transfer", "Pre-Market / Q1", "Intraday Breakouts") were removed during Phase 1 implementation in favour of a flat single-dropdown with all 9 named presets individually selectable — more explicit and discoverable. The groupings below are retained as a logical catalogue reference.

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
| Magic Hour | 03:00 | 07:00 | 08:30 | Wide 4-hr pre-market range breakout (formerly "Q1 Break") |
| Market Open | 09:30 | 09:35 | 12:00 | First 5-minute opening range breakout |
| Q1 Break | 06:00 | 08:30 | 12:00 | European open / first trading quarter breakout (formerly "Magic Hour") |

#### Preset C — "Intraday Breakouts"

| Sub-Range | OR Start | OR End | Cutoff | Description |
|-----------|----------|--------|--------|-------------|
| 1100 BO | 11:00 | 11:15 | 12:30 | Midday breakout |
| Lunch Break | 08:30 | 12:00 | 16:00 | AM session OR — full pre-market run (formerly "Market Open Wide") |
| 1400 Break | 14:00 | 14:15 | 16:00 | Afternoon breakout |

#### Custom

| Field | Source |
|-------|--------|
| OR Start | User input (HHMM) |
| OR End | User input (HHMM) |
| Cutoff | User input (HHMM) |

### 3.2 Input UX

- **Single dropdown** (`input.string`) with 10 options: all 9 named presets + "Custom".
- When "Custom" is selected, HHMM text inputs become active.
- Compound groupings (Preset A/B/C above) are a logical reference only; the UI selects one preset at a time.
- Each preset activates its sub-range(s); MFE/MAE tracked independently per sub-range.

---

## 4. Phase Plan

### Phase 1 — Modularize & Generalize (Pine Script)  
**Status:** ✅ Complete — `DailyNYLevelsV5.pine` implemented and validated  
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
**Status:** 🟡 Implemented (major scope complete) — final visual validation pending  
**Design Doc:** [`PHASE2_DESIGN.md`](PHASE2_DESIGN.md)

**Goal:** Build a standalone analytics indicator that imports the Phase 1 libraries and provides **direction-aware breakout context** while preserving bilateral MFE visibility.

**Scope (locked):**
- Keep MFE context visible on both sides (bull and bear) as baseline distribution context.
- Activate **live directional bias using close-based logic only**:
    - Bull bias: candle close above OR midpoint.
    - Bear bias: candle close below OR midpoint.
- Breakout side selection uses the **first candle close outside the OR** as the key event.
- Add directional tactical lines (active side) with explicit formulas:
    - **BO Cashflow** = P20 MFE from breakout.
    - **BO Confirm** = P75 MFE of fakeouts.
    - **Pivot** = P50 MFE of fakeouts.
    - **Reversal Target Zone** = P20-P50 MAE of fakeouts.
    - **Max Reversal** = P90 MAE of fakeouts.
    - **PB Invalidation** = P80 MAE of breakout.
    - **BO Invalidation** = P80 MAE of breakout.
- Pullback activation starts at **P25 breakout MAE from breakout activation price** (breakout activation = first close outside OR).
- Mid probability metric = historical hit-rate % for touching OR midpoint.
- MAE histogram rendering remains **optional** (default OFF); Phase 2 default display is line/zone based.
- Phase 2 tactical calculations are **historical-only** (no current-session MAE/MFE injection into percentile distributions).
- Breakout and fake-move MAE/MFE families are now persisted historically in `StatsLib` for direct percentile usage.

**Display rules (locked):**
- PB Invalidation and BO Invalidation share one price level for now and are drawn as **one line with one shared merged label**.
- Stat and tactical labels are part of the **same label system**: same size token, same text color token, same offset token, same merge threshold, same right-edge label column.
- All displayed lines/zones must expose **independent color inputs** for user configuration.

**Open items:**
- [ ] Future refinement: probability model to improve side-selection beyond first-close-outside-OR when statistically justified.

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
| Library architecture | 3 private Pine libraries: `RangeSessionLib`, `PineDrawingLib`, `StatsLib` | `PineDrawingLib` is intentionally Pine-specific; `StatsLib` absorbs excursion analytics; code locally first, publish to TradingView manually |
| Multi-range rendering | All compound preset sub-ranges render simultaneously | Each sub-range gets its own OR box, stat lines, and table rows |
| Sub-range colors | Auto-generated hue offsets from global bull/bear colors per sub-range | Avoids proliferating per-range color inputs |
| MAE — Absolute | `mae_bull_abs` from OR_low; `mae_bear_abs` from OR_high (same refs as MFE) | Symmetric worst-case adverse excursion |
| MAE — Pullback | Bull: worst retrace **below OR_HIGH** before peak bull MFE. Bear: worst retrace **above OR_LOW** before peak bear MFE. | Measures heat taken on the breakout side before the move plays out |
| Post-peak give-back | Not captured in Phase 1 or 2 | Pullback + absolute MAE is sufficient |
| MAE histogram rendering | Optional in Phase 2 (default OFF) | Preserve chart clarity; tactical levels are line/zone-first |
| MFE histogram visual layout | **Overlaid on the price chart (same pane)** — anchored at each range's `or_start_bar`, boxes extend rightward. Bull side above `bull_ref`; bear side below `bear_ref`. No separate pane. Resolved in Phase 1. | Keeps distribution visible alongside live price action; avoids pane management overhead |
| MFE histogram binning | Percentile-based bins: default P20→P90, step 5 pct pts (14 bins). Density = `count / band_span` (normalised for bin width). Width scaled to `density / max_density * max_profile_width`. Tail cap at P20 density prevents sparse tail bins from squashing the centre. Full spec in `PHASE1_DESIGN.md` §6.6. | Density-based width gives a true distribution shape; tail cap prevents visual distortion from extreme-movement sessions |
| Win / EV target | Per-range `ev_target_pct` input (default 0.3%); win = MFE ≥ ev_target; zero-MFE days **excluded** from win rate | Expected-value threshold aligns with risk management |
| Live bias activation | **Close-based only**: close above OR mid = bull, close below OR mid = bear | Prevents wick-based false activation; aligns with Phase 2 directional framing |
| Breakout side keying | **First candle close outside OR** selects breakout side | Deterministic trigger; extensible later if probability model improves |
| BO Cashflow | **P20 MFE from breakout** | Early continuation threshold |
| BO Confirm | **P75 MFE of fakeouts** | Breakout confirmation beyond typical fakeout range |
| Pivot | **P50 MFE of fakeouts** | Central fakeout excursion reference |
| Reversal target zone | **P20-P50 MAE of fakeouts** | Expected reversal destination band |
| Max reversal | **P90 MAE of fakeouts** | Adverse reversal extreme threshold |
| Pullback activation | **P25 breakout MAE from breakout activation price** (first close outside OR) | Activation uses historical breakout MAE drawdown profile |
| Pullback invalidation | **P80 MAE of breakout** | Breakout heat tolerance threshold |
| BO invalidation | **P80 MAE of breakout** (same line for now) | Shared invalidation definition pending later divergence |
| Invalidation line rendering | Single line with one merged label: "PB | BO Invalidation" | Avoid duplicate line clutter while keeping both semantic tags |
| Mid probability | OR-mid hit-rate % | Context metric for midpoint interaction propensity |
| Line/zone styling | All lines/zones have configurable color inputs | Required for workflow-specific visual tuning |
| Theme system | Global mode selector: `Custom`, `Dark`, `Light` with token-level palette resolution. See [VISUAL_SYSTEM.md](VISUAL_SYSTEM.md) for shared design tokens | Keeps visuals readable across chart backgrounds without forcing manual recolor each time |
| Theme coverage | Theme tokens apply to stat lines/labels, histograms, time distribution, phase-2 tactical lines/zones, data table, and debug labels. All modules share a single `i_label_size`, `i_label_text_color`, `i_line_width_primary/secondary`, `i_label_gap_bars`, and `i_label_merge_threshold_ticks` from the Visual System | Ensures color and geometry behavior is consistent across all rendered modules |
| Predictive purity | Historical-only percentiles for Phase 2 tactical lines | Prevents forward contamination from current session |
| Live stat lines (Phase 1) | Draw from today's OR anchor forward: **P20 "BO Cashflow"**, **Median**, **Avg**, **P90 "Max MFE"** + **Range Mid** (dashed, with hit% label) | Real-time reference during session |
| Cross-midnight date stamp | **Cutoff date** (e.g., Monday date for 18:00 Sun → 03:00 Mon session) | Conventional futures trade-date convention |
| 0300 Transfer | 5-min OR (0300–0305). Direction = **bull if 1800 open > 0300 close**, bear if 1800 open < 0300 close. Skip day if 1800 data unavailable. | Continuation toward the overnight opening level |
| 1800 Break session days | Pine days `1,2,3,4,5` (Sun–Thu evenings) | Captures Sunday 18:00 futures reopen |
| Data table | Toggle dropdown (MFE View / MAE View / DOW View / Fakeout View); auto-focuses on sub-range currently in its OR or data window. **Phase 1 implemented:** table is created as a local variable inside `i_show_table` guard (fully hidden when toggled off); dimensions are dynamic per view (DOW: 3×6, others: 6×3). Full column spec (Price, Hit%, Cond%, Streak, R-Multiple) is Phase 2 work. | Clean single-table UX with view switching |
| Session detection architecture | Dual-path: Pine session-string path + minutes-of-day parity path | Keeps Pine implementation simple while preserving a portable algorithm contract for NinjaScript |
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
| O-8 | Breakout side probability refinement beyond first-close-outside-OR | 2 | ⚪ Future enhancement |
| O-9 | TradingView chart-level visual regression pass for all Phase 2 lines/zones | 2 | 🟡 Pending |

---

## 7. File Structure

```
scripts/indicators/daily-ny-levels/
├── DailyNYLevelsV5.pine              # Phase 1: Core indicator
├── DailyNYLevelsAnalytics.pine       # Phase 2: MFE/MAE analytics
├── lib/
│   ├── RangeSessionLib.pine          # Phase 1: Session/range UDTs & resolver
│   ├── PineDrawingLib.pine           # Phase 1: Pine-only drawing helpers
│   └── StatsLib.pine                 # Phase 2: Extended historical breakout/fake MAE/MFE persistence
└── ninja/
    ├── DailyNYLevels.cs              # Phase 3: NinjaScript indicator
    ├── DailyNYLevelsStrategy.cs      # Phase 4: NinjaScript strategy
    └── Lib/
        ├── RangeEngine.cs            # Phase 3: Range/session engine
        └── ExcursionEngine.cs        # Phase 3: MFE/MAE engine

docs/indicators/DailyNYLevels/
├── PRD.md                            # This document
├── CORE_ENGINE_SPEC.md               # Platform-agnostic algorithm contracts + pseudocode
├── PHASE1_DESIGN.md                  # Phase 1 detailed design
├── PHASE2_DESIGN.md                  # Phase 2 detailed design + implementation status
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

## 9. Extensibility Checklist

| Scenario | Phase 1 Support | Effort | Notes |
|----------|------------------|--------|-------|
| Add new range preset/sub-range | ✅ Yes | Low | Add new `RangeSpec` rows in preset resolver; no core model changes |
| Add new derived stat (e.g., custom conditional metric) | ✅ Yes | Medium | Add to `StatsLib` and optionally extend `ExcursionHistory` |
| Add new table view | ✅ Yes | Medium | Add new rendering branch and columns in table module |
| Add new Pine visual overlays | ✅ Yes | Medium | Add in `PineDrawingLib`; no cross-platform assumptions |
| Port session/range logic to NinjaScript | ✅ Yes | Medium | Use minute-based session helper contract from `CORE_ENGINE_SPEC.md` |
| Reuse Pine drawing code in NinjaScript | ❌ No | N/A | `PineDrawingLib` is intentionally Pine-specific |
| Multi-timezone mixed operation in one indicator instance | ⚪ Deferred | High | Phase 1 assumes EST/ET normalization for all active ranges |

---

## 10. Strategy Automation Readiness (Phase 4)

Phase 1 design is sufficient as a data and signal foundation for strategy automation.

| Capability Needed by Strategy | Present in Phase 1 Design | Notes |
|-------------------------------|----------------------------|-------|
| OR boundaries and cutoff windows | ✅ | `RangeSpec` + `RangeState` provide deterministic session framing |
| Real-time excursion tracking (MFE/MAE) | ✅ | Includes absolute + pullback MAE |
| Confirmation/target levels | ✅ | Named percentile framework (P20/P50/P75/P90) |
| Move-failure/fakeout context | ✅ | Fakeout flags + reversal depth distributions |
| EV win and risk-quality metrics | ✅ | EV flags + R-multiple + efficiency inputs |
| DOW and continuation context | ✅ | Available for regime filtering in strategy rules |

**Note:** Phase 1 does not define executable entry/exit rules; that remains explicit Phase 4 strategy design scope.

---

## 11. Platform-Specific Notes

1. `PineDrawingLib` is Pine-only by design. NinjaScript will implement independent drawing/rendering adapters.
2. Session handling uses a dual-path model:
    - Pine-native path: session strings + `time()`
    - Portable path: minutes-of-day helper logic (used for NinjaScript parity)
3. All business logic timestamps are interpreted in EST/ET context before calculations.
4. `CORE_ENGINE_SPEC.md` is the single source of truth for cross-platform algorithm behavior; platform files are implementation adapters.

---

**Last Updated:** 2026-04-18 (Phase 2 documentation updated: historical-only tactical sourcing, breakout/fake persistence, and validation status)
