# Product Requirements Document: GEX Visualization V3 (Brainstorm Draft)

## 1. Document Status
- Status: Final (Implemented)
- Owner: Trading Research + Web App
- Last Updated: 2026-04-05
- Scope: `/options-live` visualization and interaction model for GEX analytics

This is a living PRD. Requirements are expected to evolve quickly as we continue market-structure research and UI exploration.

## 2. Problem Statement
The current `/options-live` GEX visualization is useful but not yet optimal for rapid intraday decision making. Specifically:
- Strike filtering is percent-range based and can hide useful structure when volatility expands/contracts.
- Segmentation of GEX data is limited relative to the workflows used by active options traders.
- Users need faster drill-down from macro regime view to specific strike/expiry concentrations.

## 3. Product Goal
Create an operator-grade GEX visualization module that makes dealer positioning interpretable in under 5 seconds for intraday trading decisions.

## 4. In-Scope (Phase 1)
1. Replace or augment strike range filtering with strike count filtering (around ATM).
2. Add segmented visualization modes for:
- Daily Gamma Exposure (GEX)
- Gamma Exposure by Strike
- Gamma Exposure by Expiry
- Largest GEX by Strike and Expiry
3. Preserve existing options-live dashboard architecture and keep refresh behavior compatible with current data pipeline.

## 5. Out of Scope (Phase 1)
- Full backend data-source replacement
- Broker execution integration
- Major redesign of non-GEX panels
- Backtesting engine changes

## 6. Personas
1. Intraday index trader
- Needs immediate map of support/resistance pressure zones.
- Prioritizes speed and readability over exhaustive detail.

2. Volatility/flow analyst
- Needs concentration by expiry and strike to identify structural hedging pressure.
- Requires confidence in data freshness and source timestamping.

## 7. Core User Stories
1. As a trader, I want to choose "number of strikes" (for example 10, 20, 30) so I can normalize visual density regardless of price regime.
2. As a trader, I want to switch between strike and expiry segmentation quickly so I can diagnose whether pressure is local (single expiry) or broad (term structure).
3. As a trader, I want a "largest GEX by strike+expiry" table/heatmap so I can identify exact concentrations driving pinning or acceleration.
4. As a trader, I want all views synchronized to one active symbol and timestamp so interpretation is consistent.

## 8. Functional Requirements

### FR-1 Strike Count Filter
1. Add a control: "Strikes Around ATM" with discrete presets (5, 10, 15, 20, 30, 50) and custom numeric input.
2. Filter should return top N strikes above and below ATM (symmetrical when data available).
3. If one side has fewer strikes, use all available and display a subtle data-availability note.
4. Persist user selection in local storage per symbol.

### FR-2 Segmented GEX Modes
1. Add a segmented control/tabs for:
- Daily GEX
- By Strike
- By Expiry
- Largest by Strike+Expiry
2. Switching tabs must not reset symbol, strike-count, or selected session date.
3. Each tab must display source timestamp and refresh age.

### FR-3 Daily Gamma Exposure (GEX)
1. Show daily net/call/put GEX summary for active symbol.
2. Include trend context versus prior snapshots (delta since prior sample).
3. Include key regime labels aligned with existing dashboard language.

### FR-4 Gamma Exposure By Strike
1. Show strike-level bars with separate call/put and optional net overlay.
2. Add sorting toggle: strike order vs absolute magnitude.
3. Add ATM marker and current spot marker.

### FR-5 Gamma Exposure By Expiry
1. Aggregate GEX by expiry bucket.
2. Support toggles:
- Net only
- Net + call/put split
3. Allow expiry ranking by absolute GEX and by nearest expiry first.

### FR-6 Largest GEX By Strike And Expiry
1. Provide ranked table (default) and optional heatmap view.
2. Fields: expiry, strike, call GEX, put GEX, net GEX, abs net GEX, distance from spot.
3. Default row count: 25 (user configurable to 10/25/50/100).
4. Enable quick action: click row to highlight corresponding strike in strike chart.

### FR-7 Data Integrity and UX Guardrails
1. If data is stale beyond threshold (for example 2x refresh cadence), show stale indicator.
2. If values are partially missing, render chart with partial-data warning instead of blank state.
3. Always show clear units and sign conventions.

### FR-8 Live Gamma Exposure Levels
1. Add a dedicated mode called Live Gamma Exposure Levels for the active symbol.
2. Display a price-ordered ladder of gamma levels with at least these default level classes:
- Max Positive Gamma Level
- Max Negative Gamma Level
- Zero Gamma Level
- Call Wall
- Put Wall
3. Each level row must include:
- Level name
- Price
- Distance from spot (points and percent)
- Relative strength score (normalized 0-100)
4. Enable click-to-highlight behavior so selecting a level emphasizes it on all compatible charts.
5. Add optional proximity alerts when spot enters user-defined distance bands from key levels.

### FR-9 Spot Gamma
1. Add a dedicated Spot Gamma view for the active symbol.
2. Spot Gamma view should show:
- Current spot gamma value
- Intraday spot gamma trend
- Directional state badge (for example Positive, Neutral, Negative)
3. Add user-configurable smoothing for trend line (for example 1, 3, 5 sample smoothing).
4. Include contextual interpretation text generated from deterministic rules, not free-form model output.

### FR-10 Discord Publishing
1. Support publishing selected charts and summary panels to Discord.
2. User can choose publish scope:
- Active chart only
- Full tab summary card
- Multi-chart pack (up to 4 charts)
3. User can choose publish trigger:
- Manual publish button
- Scheduled interval
- Event-driven (state change, level touch, threshold breach)
4. Every publish payload must include metadata:
- Symbol
- Snapshot timestamp
- Data freshness age
- Filter state (strike count, tab, sort mode)
5. Add publish preview before send so users can verify layout and annotation.
6. Failed publish should show retry action and retain last payload for quick resend.

## 9. Suggested Requirements (Recommended)
1. Add sign-convention legend (what positive/negative net GEX implies for expected behavior).
2. Add one-click presets for common workflows:
- Scalper View (10 strikes)
- Intraday Structure (20 strikes)
- Swing Context (50 strikes)
3. Add optional normalization mode:
- Raw GEX
- % of total absolute GEX
4. Add optional threshold filter (hide values below magnitude cutoff) to reduce noise.
5. Add tooltips with exact values and timestamp.
6. Add screenshot/export for the active tab for journaling.
7. Add keyboard shortcuts for tab switching and strike count presets.

## 10. UX Requirements
1. Time-to-insight target: user can identify top 3 pressure zones within 5 seconds.
2. No layout shift when switching tabs.
3. Color and contrast must remain legible in dark-theme trading setup.
4. Controls should be operable with mouse and keyboard.

## 11. Non-Functional Requirements
1. Tab switch interaction response under 150ms (client-side cached data).
2. Incremental refresh should not block interaction.
3. Handle symbols with sparse chain data without runtime errors.
4. Maintain compatibility with current options-live data ingestion pipeline.
5. Discord publish flow should complete in under 2 seconds for single chart payload under normal network conditions.

## 12. Wireframes (Low-Fidelity)

### 12.1 Global Layout

```text
+--------------------------------------------------------------------------------------------------+
| Mission Control Header | Symbol | Spot | Last Sync | Strike Count | Publish                      |
+--------------------------------------------------------------------------------------------------+
| Left: Active Symbols              | Center: Main Visualization Panel     | Right: Tactical Panel      |
|-----------------------------------|--------------------------------------|----------------------------|
| SPY   523.11                      | [Segment Tabs]                       | Regime Summary             |
| QQQ   441.02                      | Daily GEX | By Strike | By Expiry    | Spot Gamma                 |
| IWM   208.44                      | Largest SxE | Levels | Spot Gamma    | Key Levels                 |
|                                   |                                      | Discord Queue              |
|                                   | Active chart area                    |                            |
|                                   |                                      |                            |
+--------------------------------------------------------------------------------------------------+
| Footer: stale indicator | data source | API health | publish status                                 |
+--------------------------------------------------------------------------------------------------+
```

### 12.2 By Strike + Strike Count Control

```text
+-------------------------------------------------------------------------------------------+
| By Strike | Strike Count: [ 5 ][ 10 ][ 15 ][ 20 ][ 30 ][ 50 ] [Custom: 24] [Apply]      |
+-------------------------------------------------------------------------------------------+
| Sort: Strike Order | Abs Magnitude      View: Net+Split      Normalize: Raw | %Total     |
+-------------------------------------------------------------------------------------------+
|         Call GEX (green) / Put GEX (red) / Net Overlay (white line)                      |
|                                                                                           |
|   515 | ████████                                                                          |
|   520 | ████████████                                                                      |
|   525 | ████████████████   <- Spot Marker                                                 |
|   530 | ███████████                                                                        |
|   535 | ███████                                                                            |
|                                                                                           |
+-------------------------------------------------------------------------------------------+
```

### 12.3 Live Gamma Exposure Levels

```text
+----------------------------------------------------------------------------------------------------+
| Live Gamma Exposure Levels - SPY                                                                   |
+----------------------------------------------------------------------------------------------------+
| Level                  | Price     | Dist (pts) | Dist (%) | Strength | Alert Band | Action        |
|------------------------|-----------|------------|----------|----------|------------|---------------|
| Max Positive Gamma     | 528.00    | +4.89      | +0.94%   | 92       | 1.00       | Highlight      |
| Zero Gamma             | 523.50    | +0.39      | +0.07%   | 88       | 0.50       | Highlight      |
| Spot                   | 523.11    | 0.00       | 0.00%    | --       | --         | Center Chart   |
| Put Wall               | 520.00    | -3.11      | -0.59%   | 84       | 1.00       | Highlight      |
| Max Negative Gamma     | 517.50    | -5.61      | -1.07%   | 78       | 1.50       | Highlight      |
+----------------------------------------------------------------------------------------------------+
```

### 12.4 Spot Gamma Panel

```text
+-------------------------------------------------------------------------------------------+
| Spot Gamma - SPY                                                                          |
+-------------------------------------------------------------------------------------------+
| Current: +1.84M     Regime: Positive      Delta(15m): +0.22M      Smooth: [1|3|5]        |
+-------------------------------------------------------------------------------------------+
|   Intraday Spot Gamma Trend                                                                |
|   10:00   11:00   12:00   13:00   14:00   15:00                                           |
|    .        .       .       .       .       .                                             |
|     .      . .     . .     . .     . .     .                                              |
|      ......   .....   .....   .....   ......                                              |
+-------------------------------------------------------------------------------------------+
| Interpretation: Dealer positioning currently dampens large directional moves unless spot   |
| migrates below zero gamma.                                                                 |
+-------------------------------------------------------------------------------------------+
```

### 12.5 Largest GEX By Strike And Expiry

```text
+------------------------------------------------------------------------------------------------+
| Largest GEX By Strike And Expiry - SPY                                                         |
+------------------------------------------------------------------------------------------------+
| Rank | Expiry     | Strike | Call GEX | Put GEX | Net GEX | Abs Net | Dist Spot | Visual Link |
|------|------------|--------|----------|---------|---------|---------|-----------|-------------|
| 1    | 2026-04-05 | 525    | 2.10M    | -0.42M  | 1.68M   | 1.68M   | +1.89     | Highlight   |
| 2    | 2026-04-12 | 520    | 0.55M    | -1.82M  | -1.27M  | 1.27M   | -3.11     | Highlight   |
| 3    | 2026-04-19 | 530    | 1.40M    | -0.10M  | 1.30M   | 1.30M   | +6.89     | Highlight   |
+------------------------------------------------------------------------------------------------+
```

## 13. Analytics and Success Metrics
1. Usage rate of non-default tabs per session.
2. Average time spent in each segmentation view.
3. Frequency of strike count adjustments per session.
4. User-reported confidence score for "readability of GEX structure".
5. Discord publish count by chart type and trigger type.
6. Publish failure rate and median retry success time.

## 14. Data and Contracts (Draft)
1. Required snapshot fields for all views:
- symbol
- spot
- as_of_timestamp
- refresh_age_ms
- by_strike array
- by_expiry array
- derived levels (zero_gamma, call_wall, put_wall, max_pos_gamma, max_neg_gamma)
- spot_gamma_current and spot_gamma_series
2. Serialization requirement for Discord:
- image payload plus machine-readable metadata block
3. Publish payload schema should be versioned to avoid downstream parsing breaks.

## 15. Open Questions
1. Should strike count be strictly symmetric around ATM or allow directional bias selection?
2. Should expiry segmentation include only same-day/weekly/monthly grouping in addition to exact expiry dates?
3. Should largest GEX ranking prioritize absolute net only, or keep separate leaderboards for call and put?
4. Should spot/ATM references use snapshot-time value or real-time quote stream if available?
5. Should Discord publish support multiple channels by symbol and severity?
6. For Spot Gamma interpretation text, do we want short mode and detailed mode?

## 16. Proposed Delivery Plan (Draft)
1. Milestone A: Add strike-count filter + tab scaffold (no visual redesign).
2. Milestone B: Implement By Strike + By Expiry charts with shared state.
3. Milestone C: Implement Live Gamma Exposure Levels and Spot Gamma panels.
4. Milestone D: Implement Discord publishing controls, preview, and send pipeline.
5. Milestone E: polish, stale-data guardrails, and metrics instrumentation.

## 17. Initial Acceptance Criteria (Draft)
1. User can select strike count and immediately see filtered data update in By Strike and Largest views.
2. User can switch between all four GEX modes without losing context (symbol/date/filter).
3. Largest view correctly ranks entries by selected sort mode and supports row-to-chart highlight.
4. Daily GEX view displays net/call/put totals and snapshot delta.
5. All views show timestamp and stale-state indicator when applicable.
6. Live Gamma Exposure Levels panel shows at least 5 key levels with distance and strength.
7. Spot Gamma panel renders current value, trend, and state badge with configurable smoothing.
8. User can publish chart(s) to Discord manually with preview and metadata.
9. Event-driven publish can be enabled for at least one trigger type and can be disabled instantly.

## 18. Brainstorm Additions: S&P and Nasdaq Heatmaps

### 18.1 New Views Requested
1. S&P Put/Call Ratio Heatmap.
2. S&P Regular Heatmap (non-ratio exposure heatmap).
3. Nasdaq Put/Call Ratio Heatmap.
4. Nasdaq Regular Heatmap (non-ratio exposure heatmap).

### 18.2 Functional Requirements (Heatmaps)
1. Add a new Heatmaps tab group with market selector:
- S&P
- Nasdaq
2. For each market selector, provide two heatmap modes:
- P/C Ratio Heatmap
- Regular Heatmap
3. P/C Ratio Heatmap cells must represent put-call ratio intensity at strike/expiry intersections.
4. Regular Heatmap cells must represent absolute or net exposure intensity (configurable metric).
5. Add metric switch for Regular Heatmap:
- Net GEX
- Absolute GEX
- Volume
- Open Interest
6. Add expiry axis controls:
- Exact expiry
- Bucketed expiry (0DTE, 1-7D, 8-30D, 30D+)
7. Add strike axis controls:
- ATM-centered strike count (shared with global strike-count control)
- Strike step granularity (all, every 2nd, every 5th strike)
8. Add color scale controls:
- Diverging palette for signed metrics
- Sequential palette for non-negative metrics
- Auto and fixed range options
9. Hovering a cell must show full tooltip details:
- Market
- Expiry
- Strike
- Put value
- Call value
- Ratio or metric value
- Snapshot timestamp
10. Clicking a cell should drill into Largest GEX By Strike And Expiry view filtered to that context.

### 18.3 UX Requirements (Heatmaps)
1. Heatmap legends must always remain visible and clearly labeled.
2. Color normalization must be stable across refreshes within a session unless user selects auto-rescale.
3. Default view on tab open:
- S&P P/C Ratio Heatmap
4. Preserve separate UI state for S&P and Nasdaq (independent mode, palette, scaling preferences).

### 18.4 Discord Publishing Requirements (Heatmaps)
1. Allow direct publish from any heatmap view to Discord.
2. Discord payload caption should include:
- Market (S&P or Nasdaq)
- Heatmap mode (P/C Ratio or Regular)
- Selected metric
- Strike count and expiry mode
- Snapshot time
3. For multi-chart publish packs, allow pairing:
- P/C Ratio Heatmap + Regular Heatmap (same market)
4. Add optional threshold-based event publish for heatmaps (for example max cell exceeds configured threshold).

### 18.5 Wireframe: Heatmap Module (Low-Fidelity)

```text
+--------------------------------------------------------------------------------------------------+
| Heatmaps | Market: [S&P v]  Mode: [P/C Ratio v]  Metric: [Net GEX v]  Expiry: [Bucketed v]      |
| Strike Count: [10]  Step: [All v]  Palette: [Diverging v]  Scale: [Session Fixed v]             |
+--------------------------------------------------------------------------------------------------+
| Legend: Low -------------------------------------------------------------------------------- High |
|                                                                                                  |
| Expiry\Strike | 510 | 515 | 520 | 525 | 530 | 535 | 540                                         |
| 0DTE          |  .  | ..  | ... | ### | ##  |  .  |  .                                          |
| 1-7D          |  .  | ..  | ### | ####| ### | ..  |  .                                          |
| 8-30D         |  .  | .   | ##  | ### | ##  | .   |  .                                          |
| 30D+          |  .  | .   | .   | ##  | ##  | .   |  .                                          |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
| Tooltip on hover: Expiry, Strike, Put, Call, Ratio/Metric, Timestamp                            |
| Click cell: "Open detailed view"                                                                 |
+--------------------------------------------------------------------------------------------------+
```

### 18.6 Acceptance Criteria (Heatmaps)
1. User can switch between S&P and Nasdaq heatmaps without losing market-specific preferences.
2. User can toggle between P/C Ratio Heatmap and Regular Heatmap in one click.
3. Tooltip displays all required values on hover for both heatmap modes.
4. Clicking a heatmap cell opens a filtered detailed context view.
5. Heatmap views can be published to Discord with correct metadata.

### 18.7 Heatmap Image Reference (User-Provided)
The provided heatmap image should be treated as a primary style reference for the market-map view.

#### Visual Patterns To Preserve
1. Hierarchical treemap structure:
- Market
- Sector
- Industry
- Symbol tile
2. Tile size should represent relative importance (for example market cap or configured weighting).
3. Tile color should represent the selected metric direction and intensity.
4. Each major symbol tile should show:
- Ticker
- Metric value (for example P/C ratio or exposure value)
5. Sector headers should be persistent and readable at all zoom levels.

#### Color and Semantics Requirements
1. Green tones indicate supportive/bullish or positive metric regime.
2. Red tones indicate defensive/bearish or negative metric regime.
3. Neutral or mixed readings should use muted olive/gray transition colors.
4. Border contrast must remain high enough to separate adjacent sectors and tiles.

#### Interaction Requirements From Image Inspiration
1. Hover should highlight tile, sector, and industry lineage simultaneously.
2. Clicking a sector should zoom/filter into that sector while preserving market context breadcrumb.
3. Clicking a symbol tile should open detailed panel with:
- By Strike
- By Expiry
- Largest Strike+Expiry
- Spot Gamma
4. Add quick toggle between treemap mode and matrix heatmap mode.

#### Label Density Rules
1. Large tiles: show ticker + value.
2. Medium tiles: show ticker, value optional.
3. Small tiles: show ticker only on hover to avoid clutter.
4. Never render unreadable text; collapse labels before overlap occurs.

#### Discord Export Requirements For Treemap
1. Export should include a legend and visible timestamp.
2. Optional export modes:
- Full market map (S&P or Nasdaq)
- Sector-focused snapshot
- Top movers overlay
3. Export caption should include metric, normalization mode, and symbol count displayed.

## 19. Brainstorm Additions: Periscope-Style Integrated View

### 19.1 Goal
Create an integrated market-maker exposure workspace that ties live price action directly to options positioning data in a synchronized view.

### 19.2 Core Requirements
1. Add an Integrated View mode that renders:
- Left pane: live intraday price chart
- Right pane: price-level aligned options exposure bars and markers
2. Price and options pane must share a common price axis so level relationships are visually exact.
3. Add synchronized horizontal spot line across both panes.
4. Add configurable overlays in options pane:
- Net GEX by price level
- Call/Put split bars
- Trade flow dots/markers (if available)
- Prior-session context toggle
5. Add configurable data filters in header:
- Timeframe window (for example 5m, 15m, 1h)
- Expiry scope (All, 0DTE, weekly, custom)
- DTE filter
- Strike count filter

### 19.3 Interaction Requirements
1. Hover on chart candle highlights nearest options exposure row at matching price level.
2. Hover on options level highlights nearest candle/time context and shows detailed tooltip.
3. Click on a major exposure bar pins an annotation on both panes.
4. Add quick toggle between:
- Price-first layout (wider chart)
- Exposure-first layout (wider options pane)
5. Add playback controls for short lookback replay of synchronized chart + exposure states.

### 19.4 Visual Requirements
1. Maintain dark, high-contrast trading UI with minimal glare and clear focus cues.
2. Use a clearly differentiated palette for:
- Positive/supportive exposure
- Negative/resistive exposure
- Neutral or uncertain readings
3. Keep chart grid subtle and avoid visual noise that competes with exposure bars.
4. Major levels should be visually emphasized with thicker bars and optional badges.

### 19.5 Wireframe: Integrated Chart + Options Pane

```text
+----------------------------------------------------------------------------------------------------------------+
| Integrated View | Symbol: SPX | Timeframe: 12:50-13:00 | Expiry: All | DTE: [0-30] | Strikes: 20 | With Prev |
+----------------------------------------------------------------------------------------------------------------+
| Live Price Chart (Left)                                              | Options Exposure Pane (Right)         |
|----------------------------------------------------------------------|----------------------------------------|
|                                                                      | Price 6560 | --- red bars ---          |
|   candlesticks + trend                                                | Price 6540 | -- red bars --            |
|                                                                      | Price 6528 | ===== SPOT LINE =====      |
|   ===== synchronized spot line =====                                 | Price 6520 | +++++ green bars +++       |
|                                                                      | Price 6500 | -- red bars --             |
|                                                                      | Price 6480 | . flow markers .           |
|                                                                      | Price 6460 | + green bars +             |
|                                                                      | Price 6440 | . . .                      |
+----------------------------------------------------------------------------------------------------------------+
| Hover/Pin Details: price level, call gex, put gex, net gex, flow, timestamp                                   |
+----------------------------------------------------------------------------------------------------------------+
```

### 19.6 Discord Publish Requirements (Integrated View)
1. Allow one-click publish of the combined two-pane visualization.
2. Include optional annotation layer in export (pinned levels, highlighted bars, active filters).
3. Caption must include:
- Symbol
- Spot
- Time window
- Expiry scope
- Strike count
- Snapshot timestamp
4. Add auto-publish option when large exposure imbalance appears near spot (user configurable threshold).

### 19.7 Acceptance Criteria (Integrated View)
1. User can see synchronized spot line across both panes with aligned price coordinates.
2. User can change timeframe/expiry filters and both panes update consistently.
3. Hover and click interactions link chart and exposure context both directions.
4. Integrated view exports to Discord with visible metadata and optional annotations.

## 20. Representative Image Baseline (Living Reference)

The recently shared screenshots are representative references. They are not treated as fixed pixel-perfect mocks, but as canonical interaction patterns that should remain consistent as requirements expand.

### 20.0 Coverage Note (Partial Images)
1. Current screenshots are partial captures and do not represent the full product surface.
2. Any inferred interactions or hidden states are provisional until confirmed by additional captures.
3. Requirements extracted from unseen regions should be marked as `assumed` until validated.
4. During implementation planning, each assumed item must be tracked in a visual-gap checklist.

### 20.1 Canonical Patterns Extracted
1. Top-level metric family navigation:
- Spot
- Gamma
- Delta
- Charm
- Vanna
2. Reusable chart pair pattern per metric family:
- Net view (single aggregate curve/bars)
- Split view (call and put components)
3. Shared strike-axis interaction model across families:
- Expiry selector
- Strike-count selector
- Hover + crosshair with spot annotation
4. Summary details rail pattern:
- Symbol
- Date
- Last update
- Spot
- Metric breakdown blocks (OI, Volume, Directionalized Volume)

### 20.2 Generalized Requirements From Representative Images
1. Every metric family (Gamma/Delta/Charm/Vanna) should support the same control skeleton for consistency.
2. Controls should be context-aware but visually stable (no reflow between tabs).
3. Spot marker line and value label should be consistently styled across all charts.
4. Net and split charts should be colocated or one-click switchable for rapid comparison.
5. Every chart panel should expose an Info action with metric definition and sign convention.

### 20.3 Multi-Metric Expansion Requirement
1. The architecture must support extending the same visualization framework beyond GEX into DEX, Charm, and Vanna without bespoke one-off components.
2. Add a common chart schema contract for all families:
- x domain (strike or date)
- y value(s)
- optional split series
- spot reference
- metadata block
3. Add a reusable rendering primitive library for:
- Horizontal split bars
- Net bars/lines
- Spot reference line
- Event markers

### 20.4 Discord Publishing Consistency Across Families
1. Discord export templates must be family-aware but layout-consistent.
2. Captions should include metric family and mode (net vs split).
3. Allow multi-image publish packs for one symbol:
- Gamma
- Delta
- Charm
- Vanna
4. Preserve shared metadata block in all exports (symbol, spot, expiry, strike count, timestamp).

### 20.5 Acceptance Criteria (Representative Baseline)
1. Switching between Spot/Gamma/Delta/Charm/Vanna keeps a consistent control and chart grammar.
2. Net and split representations are available for each supported family.
3. Details rail updates correctly for active family and mode.
4. Discord exports remain visually consistent across families while preserving family-specific labels.

### 20.6 Pending Visual Captures (To Confirm)
1. Full-width header states (all controls expanded and collapsed).
2. Mobile/narrow layout behavior for all major chart modules.
3. Hover tooltips and right-click/overflow actions.
4. Error, stale-data, and loading states for each panel.
5. Full recent-flow panel variants (real-time and delayed modes).

## 21. Narrative Intelligence Panel (Intraday ΔGEX)

### 21.1 Goal
Add a high-signal narrative panel that translates raw exposure metrics into actionable, auditable intraday context.

### 21.2 Core Modules
1. Intraday ΔGEX header block.
2. Signal cards list (volatility, resistance, support, breakout risk, etc.).
3. Gamma Squeeze Screener with probability score and factor breakdown.
4. Key Levels and Setup Analysis summary.
5. Alternate Setup card (opposite scenario).
6. Recent Flow feed with quality/timeliness disclosure.

### 21.3 Functional Requirements: Intraday ΔGEX Header
1. Display:
- Δ Session (absolute and percent)
- Δ Recent (short lookback delta)
- Snapshot count and session start time
2. Show `View All` action opening full session history timeline.
3. If insufficient snapshots exist, render explicit not-enough-data state instead of synthetic values.

### 21.4 Functional Requirements: Signals
1. Each signal card must include:
- Signal type (for example volatility, resistance)
- Severity badge (Weak, Moderate, Strong)
- One-line interpretation
- Price anchor (`@ price`)
- Distance from spot (percent)
2. Signals should be sorted by severity and proximity relevance.
3. Clicking a signal highlights its level in related charts.

### 21.5 Functional Requirements: Gamma Squeeze Screener
1. Screener should output:
- Primary setup label (for example Bullish Squeeze)
- Confidence bucket (Possible, Likely, Imminent)
- Probability score (0-100)
2. Show factor breakdown with configurable weighted components:
- Gamma Regime
- Call Wall Proximity
- Flow Alignment
- Volume Confirm
- DEX Bias
3. Display all factor values and total score contribution transparently.
4. Include alternate setup card with independent score (for example Bearish Squeeze 55/100).

### 21.6 Functional Requirements: Key Levels and Setup Analysis
1. Display key levels block:
- Current Price
- Call Wall
- Trigger Level
- Optional Put Wall
2. Setup analysis bullets should be deterministic rule outputs (not opaque generated text).
3. Add `For Stronger Setup` checklist showing missing confirmations.
4. Add `Trading Implication` summary sentence generated from fixed rule templates.

### 21.7 Functional Requirements: Recent Flow Feed
1. Show a compact tape of recent notable options prints with fields:
- Timestamp
- Symbol
- Premium/value
- Size x price
- Rating/grade
- Side/type (CALL SWEEP, PUT SWEEP, etc.)
- Heat score
- Expiry
- Strike
- Spot
- OTM percent
- Open interest
- Implied volatility
2. Provide flow regime badge (Bullish, Bearish, Neutral).
3. Support delayed data mode with clear disclosure.
4. Include source timestamp and delay amount in every flow card.

### 21.8 Data Quality and Disclosure Requirements
1. If flow is delayed (for example 30 minutes), display persistent disclosure banner.
2. Scores depending on delayed inputs must show confidence penalty or caution label.
3. Distinguish real-time vs delayed fields at the field level where applicable.
4. All narrative blocks must include `Last updated` timestamp.

### 21.9 Explainability Requirements
1. Add `Why this score?` interaction exposing scoring math.
2. Show normalized factor ranges and threshold cutoffs for severity buckets.
3. Track score drift across snapshots and expose trend direction.
4. Prevent black-box outputs by requiring visible component contribution totals.

### 21.10 Wireframe: Narrative Rail (Low-Fidelity)

```text
+--------------------------------------------------------------------------------------------------+
| Intraday ΔGEX                                                                                   |
| Δ Session: $X (+Y%)     Δ Recent: $Z     Session: N snapshots since HH:MM                      |
| [View All]                                                                                      |
+--------------------------------------------------------------------------------------------------+
| Signals                                                                                         |
| [STRONG] Volatility    Price movements likely amplified                 @ 655.87   0.00%       |
| [MODERATE] Resistance  Dynamics change if breached                      @ 666.36  +1.60%       |
| [STRONG] Volatility    Increased volatility below level                 @ 630.00  -3.94%       |
+--------------------------------------------------------------------------------------------------+
| Gamma Squeeze Screener                                                                          |
| Bullish Squeeze [POSSIBLE]                     Probability: 45/100                              |
| Factors: Gamma Regime 25 | Call Wall 5 | Flow 10 | Volume 5 | DEX 0                            |
| Key Levels: Current 655.87 | Call Wall 700.00 | Trigger 666.36                                 |
| Setup Analysis: ...                                                                             |
| For Stronger Setup: ...                                                                         |
| Trading Implication: ...                                                                        |
| Alternate Setup: Bearish Squeeze 55/100 [LIKELY]                                                |
+--------------------------------------------------------------------------------------------------+
| Recent Flow (Delayed 30m)                                                                       |
| 1:13 PM SPY CALL SWEEP 951 @ 0.79 Heat 22 Exp 2026-04-02 Strike 655 OTM 0% IV 34%             |
| 1:12 PM SPY PUT SWEEP 1000 @ 2.66 Heat 33 Exp 2026-04-17 Strike 622 OTM 5% IV 26%              |
+--------------------------------------------------------------------------------------------------+
```

### 21.11 Discord Export Requirements (Narrative)
1. Support export of full narrative card as image.
2. Support compact export (signals + screener only).
3. Export caption should include:
- Primary setup
- Probability score
- Top 2 key levels
- Flow timeliness status (real-time or delayed)
- Timestamp
4. Include optional `confidence caveat` line when delayed flow materially influences score.

### 21.12 Acceptance Criteria (Narrative)
1. User can view Δ Session, Δ Recent, and snapshot context at a glance.
2. Signal cards show severity, interpretation, level, and distance from spot.
3. Squeeze screener score is decomposed into visible factor contributions.
4. Key levels and setup analysis are generated from deterministic rules.
5. Delayed flow status is always visible when applicable.
6. Narrative panel can be exported to Discord in full and compact modes.

## 22. Comprehensive Coverage Addendum (Missed/Uncaptured Features)

This section ensures core dealer-positioning and options-structure concepts are covered even when not visible in screenshots.

### 22.1 Must-Have Metric Families
1. Open Interest (OI)
2. Volume
3. Gamma Exposure (GEX)
4. Delta Exposure (DEX)
5. Charm Exposure
6. Vanna Exposure
7. Put/Call Ratio (aggregate and strike/expiry segmented)

### 22.2 Must-Have Derived Levels and Structure
1. Gamma Flip (Zero Gamma) level
2. Call Wall level
3. Put Wall level
4. Max Positive Gamma level
5. Max Negative Gamma level
6. Magnet/Pinning level
7. Optional volatility trigger bands around key levels

### 22.3 Open Interest Requirements
1. OI must be available in:
- Aggregate symbol summary
- By strike
- By expiry
- Call/put split
2. OI change over time (ΔOI) should be available when historical snapshots exist.
3. OI visualization should support:
- Net OI
- Call OI vs Put OI
- OI concentration ranking
4. OI-based signals should be integrated into narrative scoring as an optional factor.

### 22.4 Gamma Flip and Wall Logic Requirements
1. Gamma Flip must be computed and exposed with timestamp and confidence metadata.
2. Call/Put wall identification method must be deterministic and documented.
3. Each level should include:
- Price
- Distance from spot (points and percent)
- Strength/confidence score
- Last updated timestamp
4. If multiple candidate walls exist, top-N list should be available with ranking criteria.

### 22.5 Signal and Screener Expansion Requirements
1. Signals engine must be extensible to include:
- Gamma Flip proximity
- Wall proximity (call/put)
- OI concentration shifts
- Put/Call ratio regime changes
2. Squeeze screener factors should support additional optional contributors:
- OI build-up at trigger levels
- Gamma Flip drift velocity
- Wall migration over session
3. Each factor must be togglable for experimentation without code changes (config-driven).

### 22.6 Data Contract Requirements (Extended)
1. Required fields for comprehensive support:
- open_interest_call
- open_interest_put
- oi_change_call
- oi_change_put
- gamma_flip
- call_wall
- put_wall
- max_pos_gamma
- max_neg_gamma
- pcr_total
- pcr_by_strike
- pcr_by_expiry
2. Every derived field must include provenance metadata:
- source
- computation version
- as_of_timestamp

### 22.7 UX Requirements (Extended)
1. Key level chips for Gamma Flip, Call Wall, Put Wall, and Spot must be visible in global header or right rail.
2. One-click "center around gamma flip" interaction should be available in strike-based charts.
3. User can toggle OI overlays on all applicable strike/expiry visualizations.
4. Any metric hidden due to missing data should display explicit unavailable-state reason.

### 22.8 Discord Publishing Requirements (Extended)
1. Exports should support dedicated level card:
- Spot
- Gamma Flip
- Call Wall
- Put Wall
- Distances from spot
2. Optional OI summary card should include:
- Call OI
- Put OI
- Net OI
- Put/Call ratio
3. When key levels shift materially, optional event-based Discord alert should trigger.

### 22.9 Acceptance Criteria (Comprehensive Coverage)
1. Dashboard exposes Open Interest, Gamma Flip, Call Wall, and Put Wall in both summary and drill-down contexts.
2. Gamma Flip and wall levels are timestamped, explainable, and consistently rendered across modules.
3. OI and Put/Call ratio are available in aggregate and segmented views.
4. Narrative and screener modules can optionally incorporate OI and flip/wall proximity factors.
5. Discord exports can include key-level and OI summary cards without manual editing.

### 22.10 Backlog Safety Net (Not Yet Captured Visually)
1. Dealer inventory imbalance indicators.
2. Term-structure stress flags (near vs far expiry divergence).
3. Level migration tracker (how flip/walls move intraday).
4. Confidence decay when data freshness worsens.
5. Cross-asset context hooks (SPX vs ES, NDX vs NQ) for later phase.

## 23. Recommended Additions (High-Leverage)

These are additional requirements that will reduce false confidence, improve operator trust, and make the system easier to run day-to-day.

### 23.1 Signal Quality and Validation
1. Add post-session signal outcome tracking (did projected level hold/break/reverse).
2. Add precision metrics for each signal class (hit rate, false-positive rate, median reaction magnitude).
3. Add confidence score calibration checks (predicted probability vs observed outcome buckets).

### 23.2 Replay and What-If Mode
1. Add intraday replay mode for chart + exposure + narrative at each snapshot.
2. Add what-if slider for spot movement to inspect projected changes in key levels and squeeze score.
3. Add side-by-side comparison for two timestamps (for example open vs now).

### 23.3 Alerting and Notification Hygiene
1. Add alert deduplication and cool-down windows to avoid alert spam.
2. Add severity-based routing rules for Discord channels.
3. Add acknowledgement workflow so critical alerts can be marked handled.

### 23.4 Performance and Reliability SLOs
1. Define data freshness SLO by module (for example <= 120s for headline levels).
2. Define render latency SLO per major visualization.
3. Add degraded-mode behavior when data sources fail (serve last-known-good with explicit stale banner).
4. Add health dashboard for ingestion, compute, and publish pipelines.

### 23.5 Versioning and Auditability
1. Version all scoring models and level derivation logic.
2. Persist audit trail for each published narrative/score payload.
3. Add `explain snapshot` endpoint returning all inputs and intermediate computed values.

### 23.6 User Profiles and Workspace Presets
1. Save per-user layouts, filters, and watchlists.
2. Add one-click presets:
- Opening Drive
- Midday Compression
- Power Hour
3. Allow symbol-group presets (index, tech-heavy, broad market).

### 23.7 Risk and Execution Context
1. Add optional risk panel with scenario-based stop/target context around key levels.
2. Add event calendar overlays (Fed/CPI/earnings clusters) to contextualize expected volatility.
3. Add pre-flight checklist before auto-publishing actionable narratives.

### 23.8 Data Governance
1. Track source provenance for all displayed and published values.
2. Add data anomaly detection (sudden outlier jumps in OI/GEX/flow).
3. Add reconciliation checks between independent data feeds when available.

### 23.9 API and Integration Readiness
1. Define stable internal API contracts for all chart modules.
2. Expose webhook endpoint for external automations (for example journaling system).
3. Add idempotent publish keys to avoid duplicate Discord posts in retry scenarios.

### 23.10 Prioritization Suggestion
1. Must: validation metrics, SLOs, degraded mode, model/version audit trail.
2. Should: replay mode, alert dedupe/routing, user presets.
3. Could: what-if simulator, reconciliation against secondary feeds, external webhooks.

## 24. Artifact Index (Execution Package)
1. Product design spec: `docs/features/options_dashboard/design_spec_gex_v3.md`
2. Technical architecture and API design: `docs/features/options_dashboard/technical_design_gex_v3.md`
3. Phased implementation plan: `docs/features/options_dashboard/implementation_plan_gex_v3.md`
4. API contract (V3): `docs/features/options_dashboard/contracts/api_contract_v3.md`
5. Snapshot schema (V3): `docs/features/options_dashboard/contracts/snapshot_v3.schema.json`
6. Publish request schema (V3): `docs/features/options_dashboard/contracts/publish_request_v3.schema.json`
7. Milestone task board: `docs/features/options_dashboard/task_board_gex_v3.md`
