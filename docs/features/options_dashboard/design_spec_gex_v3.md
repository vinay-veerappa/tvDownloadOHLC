# Design Spec: Options Live GEX V3

## 1. Purpose
This document converts the approved PRD into concrete UX and interaction design guidance for implementation.

Primary source: `prd_gex_visualization_v3.md`.

## 2. Experience Principles
1. Time to insight first: trader should identify top pressure zones in under 5 seconds.
2. Preserve context: symbol, strike count, expiry mode, and timestamp should persist across view changes.
3. Explainability over magic: every score and signal should expose deterministic factor contributions.
4. Shared visual grammar: Spot, Gamma, Delta, Charm, and Vanna should feel like one system.

## 3. Information Architecture
### 3.0 Greenfield Entry Points
1. New primary UI route: `/options-live-v3`.
2. Existing `/options-live` remains untouched during V3 build-out.
3. V3 modules are introduced only behind the new route until cutover criteria are met.

### 3.1 Primary Navigation
1. Options Live
2. Heatmaps
3. Integrated View
4. Narrative Intelligence
5. Exports

### 3.2 Secondary Metric Family Navigation
1. Spot
2. Gamma
3. Delta
4. Charm
5. Vanna

### 3.3 Core View Modes
1. Daily GEX
2. By Strike
3. By Expiry
4. Largest by Strike and Expiry
5. Live Gamma Exposure Levels
6. Spot Gamma
7. Heatmaps (S&P, Nasdaq)
8. Integrated Chart + Exposure

## 4. Layout Blueprint
### 4.1 Desktop
1. Left rail: active symbols and fast context.
2. Center panel: active chart/heatmap module.
3. Right rail: narrative, details, scorecards, and key levels.
4. Header: controls (symbol, timeframe, expiry scope, DTE, strike count, publish).

### 4.2 Mobile/Narrow
1. Stack modules vertically with sticky controls.
2. Collapse right rail into tabbed drawer.
3. Keep spot line/value and key levels pinned.

## 5. Global Control Model
### 5.1 Persistent Controls
1. Symbol selector.
2. Strike count around ATM (preset + custom).
3. Expiry scope (All, 0DTE, weekly, custom).
4. DTE range.
5. Refresh/freshness status.
6. Publish action.

### 5.2 State Persistence
1. Persist per-user and per-symbol preferences.
2. Preserve independent preferences for S&P and Nasdaq heatmap views.

## 6. Core Component Inventory
1. `GlobalControlBar`
2. `MetricFamilyTabs`
3. `GexModeTabs`
4. `StrikeCountControl`
5. `SpotReferenceLine`
6. `ByStrikeSplitBars`
7. `ByExpiryAggregationChart`
8. `LargestByStrikeExpiryTable`
9. `LiveLevelsLadder`
10. `SpotGammaPanel`
11. `TreemapHeatmap`
12. `MatrixHeatmap`
13. `IntegratedViewPane`
14. `NarrativeSignalsPanel`
15. `SqueezeScreenerCard`
16. `RecentFlowTape`
17. `DetailsRail`
18. `DiscordPublishDrawer`

## 7. Interaction Design
### 7.1 Cross-Module Interaction Rules
1. Hover on price levels highlights matching level in all compatible modules.
2. Click on a key level pins level across charts and narrative cards.
3. Clicking heatmap cells opens filtered Largest by Strike and Expiry context.
4. Switching metric family keeps global controls stable unless unsupported.

### 7.2 Narrative Interaction Rules
1. Signal card click highlights relevant chart region.
2. `Why this score?` opens factor math panel.
3. Delayed-flow disclaimer remains persistent when applicable.

### 7.3 Integrated View Rules
1. Left live chart and right exposure pane must share price axis.
2. Synchronized spot line on both panes.
3. Hovering either pane links to the counterpart pane.

## 8. Visual System Tokens (Initial)
### 8.1 Color Semantics
1. Positive/supportive: green family.
2. Negative/resistive: red family.
3. Neutral/transition: olive/gray family.
4. Highlight/reference (spot): cyan family.

### 8.2 Typography and Density
1. High-priority values use strong numeric hierarchy.
2. Small tiles use ticker-only rules to avoid text overlap.
3. Labels collapse before overlap; no unreadable text.

### 8.3 Chart Semantics
1. Net values: center-anchored bars/lines.
2. Split values: call and put as separate color channels.
3. Spot line and key-level markers always visible in compatible modules.

## 9. Error, Stale, and Loading States
1. Loading: skeleton with retained layout footprint.
2. Stale: explicit age label and subdued caution banner.
3. Missing data: explain why data is unavailable and what fallback is shown.
4. Degraded mode: show last-known-good data with clear timestamp.

## 10. Accessibility and Operability
1. Keyboard navigation for tabs, controls, and publish flow.
2. Color semantics should be paired with shape/label cues.
3. Tooltips and status text must be screen-reader readable.

## 11. Export UX
### 11.1 Export Types
1. Single chart.
2. Full module card.
3. Multi-chart pack.

### 11.2 Required Metadata on Export
1. Symbol.
2. Spot.
3. Time window.
4. Expiry scope.
5. Strike count.
6. Data freshness/timestamp.
7. Metric family and mode.

## 12. Acceptance Checklist for Design Sign-Off
1. All core modes have a mapped component and interaction model.
2. State persistence and context-preservation behavior are defined.
3. Visual semantics are consistent across families and modules.
4. Narrative and scoring explainability interactions are defined.
5. Export/publish workflow includes metadata and delay caveats.

## 13. Pine Indicator Compatibility (Design Guardrails)
1. Existing Pine workflow remains first-class:
- `run_options_levels.py` produces copy-ready and structured level outputs.
- TradingView users can continue pasting level strings into `scripts/indicators/options/DealerLevels.pine`.
2. Dashboard UX should expose a clear `Pine Copy` affordance for any view that maps to dealer levels.
3. Level naming in UI should remain aligned with Pine-facing terminology wherever practical:
- Spot
- Gamma Flip / Zero Gamma
- Call Wall
- Put Wall
4. Any V3-only metric labels must include a stable mapping to existing Pine labels to avoid user confusion.
5. Design changes must not assume Pine users migrate to web-only workflows.

## 14. Modularity and Performance Design Standards

### 14.1 Modularity Principles
1. Feature-first module boundaries: each major view mode owns its container, state adapter, and presentation components.
2. Shared primitives first: axes, spot lines, split bars, legends, and status badges must be reusable primitives, not duplicated per view.
3. Strict separation:
- Data adapters and selectors in module logic layer.
- Rendering in pure presentational components.
- Side effects in service hooks.
4. Inversion of dependencies: high-level modules depend on interfaces/contracts, not concrete transport or chart libraries.

### 14.2 UI Pattern Standards
1. Use composition over inheritance for chart modules.
2. Keep components pure and memo-friendly.
3. Minimize prop surface area using typed view models.
4. Prefer declarative state transitions with explicit loading/stale/error states.

### 14.3 Performance Budgets (UX)
1. Control interaction response: <= 100ms perceived.
2. Tab/view switch with warm cache: <= 150ms.
3. Initial render for active symbol shell: <= 1.2s on standard dev machine.
4. No long main-thread blocks > 50ms during normal interaction.

### 14.4 Rendering Efficiency Requirements
1. Virtualize large tables and long lists.
2. Avoid full-chart rerender when only overlays change.
3. Batch state updates during refresh cycles.
4. Use adaptive detail level for dense heatmaps and small tiles.

### 14.5 Design Review Gate
1. Every new module PR must include:
- component boundary diagram
- reusable primitive inventory
- expected render/update path
- performance impact note
