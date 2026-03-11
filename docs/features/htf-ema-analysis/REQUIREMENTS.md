# HTF EMA Analysis - Requirements Specification

## Goal
Build a Pine Script v6 overlay indicator named **HTF EMA Analysis** that replicates the chart and input behavior shown in the reference screenshots, centered on percentage-distance analysis from weekly EMA(5), with weekly/day-of-week statistics, configurable EMA zones, and level dashboards.

## Scope
- Platform: TradingView Pine Script v6.
- Type: Overlay indicator.
- Primary market use: intraday decision support using weekly EMA context.
- Version target: v1 full screenshot parity, implemented in phases.

## Core Definitions

### 1) Base Metric
All core statistics use percentage distance from weekly EMA(5):

`pctDistance = ((price - weeklyEMA5) / weeklyEMA5) * 100`

### 2) Weekly Statistical Window
- Default lookback: `52` completed weeks.
- Outputs: `mean`, `median`, `mode` of weekly percentage move distribution.

### 3) Analysis Zone
- Fixed probability analysis zone: **2% to 3% above weekly EMA(5)**.
- Zone hit is determined by overlap/touch of weekly price range with this band.

### 4) Configurable EMA Zones
- Upper zone and lower zone are user-configurable percentage bands from weekly EMA(5).
- Inputs define high/low bounds for both upper and lower zones.

### 5) Status Classification
Status labels are hit-rate based and split by thirds:
- `Good`: top third (`>= 66.67%`)
- `Fair`: middle third (`>= 33.33% and < 66.67%`)
- `Rare`: bottom third (`< 33.33%`)

### 6) Mode Tie Handling
If multiple bins share max frequency, select a single mode using:
- **Nearest-to-mean tie-breaker**.

### 7) NFP Detection and Holiday Handling
- Baseline NFP day: first Friday of the month.
- If first Friday is non-trading, roll forward to next Friday with valid bars.
- Search horizon: up to month-end Friday.
- If no valid Friday exists in month, mark NFP as missing.
- NFP levels use full-day range (high/low and derived levels).

### 8) Sunday and Tuesday Anchors
- Sunday anchor: first `18:00` candle hour.
- Tuesday anchor:
  - `< 60m`: first `09:30` candle.
  - `>= 60m`: hour bar containing `09:30`.

## Feature Modules

### A) Core Settings
- EMA length (default `5`).
- Show/hide EMA line.
- Configurable upper/lower EMA zone percentages.

### B) Weekly Levels
- Show EMA zones.
- Current week only toggle.

### C) Monthly Levels
- Toggles for previous month high/low/mid.
- Toggle for current month 30% level.
- Toggle for historical month levels.

### D) Previous Week Levels
- Master toggle.
- Individual toggles for:
  - High
  - Low
  - 50%
  - 25%
  - 75%
- Independent colors and line style/width.

### E) Session and Event Context
- Session boxes.
- Sunday and Tuesday anchors/boxes.
- NFP levels with current month filter option.

### F) Display Options
- Labels toggle.
- Label size.
- % distance table.
- Position table.

### G) Probability Analysis
- Master enable toggle.
- Lookback weeks input (default `52`).
- Show optimal zones.
- Zone start/end (default `2` to `3`).
- Day-of-week stats toggle.
- All-levels table toggle.
- Optional time filter with start/end and timezone.

### H) Range Analysis
- Master enable toggle.
- Start/end hour/minute and timezone.
- Measurement type.
- Analysis method.
- Day-of-week filter.
- Daily close hour.
- Zone band (for example `0.5` to `1.0`).
- Optional range probability table.
- Optional range levels table.
- Optional day-limit with day count.
- Optional debug boundary rendering.

### I) Styling
- Color controls for EMA, zones, Sunday, Tuesday, NFP, month levels.
- Line style controls for active and historical lines.
- Light-theme-safe text/line defaults.

## Tables and Dashboard Requirements

### 1) Weekly Analysis Panel
- Statistical summary (mean/median/mode).
- Zone-entry and completion-style metrics.
- Opening position impact.
- Day-of-week breakdown rows.

### 2) All Levels Analysis Panel
- Level grid (for example `0.5%` to `5.0%`).
- Hit-rate values.
- Good/Fair/Rare status from thirds.
- Summary rows including best level.

### 3) Optional Tables
- % distance table.
- Position table.
- Range probability and range levels tables (if enabled).

## Data and Time Rules
- Use completed periods for statistics when required (avoid polluting with incomplete week/month in summary metrics).
- Handle timezone explicitly in all session/day anchors and time filters.
- Keep first-Friday NFP logic data-driven from available bars.

## Performance Requirements
- Avoid unnecessary redraw churn for tables and drawing objects.
- Keep historical lines where expected by design.
- Cap object arrays and clean oldest objects safely when limits are approached.
- Keep per-bar loops bounded by lookback inputs.

## Implementation Phases
1. Core calculations and statistical engine.
2. Levels/zones and event anchors.
3. Dashboards/tables and chart visuals.
4. Range/time filters and debug options.
5. Validation and tuning for parity.

## Acceptance Criteria
- Indicator compiles in Pine Script v6 with no runtime object-limit issues.
- Inputs appear in grouped sections matching screenshot intent.
- Weekly stats, mode tie handling, and status thirds follow defined rules.
- NFP rollover behaves as specified on holiday/non-trading first Friday months.
- Tuesday anchor logic follows timeframe-dependent rule.
- Dashboards and key lines render with expected values and toggles.
