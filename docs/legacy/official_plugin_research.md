# Official TradingView Plugin Examples Research

## Overview
The official [lightweight-charts](https://github.com/tradingview/lightweight-charts) repository contains well-structured TypeScript examples for plugins and indicators.

## Plugin Examples Inventory (28 plugins)

### ✅ Already Implemented (Ported)
| Plugin | Status | Our Implementation |
|--------|--------|-------------------|
| `anchored-text` | ✅ Done | `web/lib/charts/plugins/anchored-text.ts` |
| `delta-tooltip` | ✅ Done | `web/lib/charts/plugins/measuring-tool.ts` |

### 🎯 High Priority (Next)
| Plugin | Description | Complexity |
|--------|-------------|------------|
| **`session-highlighting`** | Background colored stripes for trading sessions | Medium |
| `volume-profile` | Horizontal volume histogram | Medium-High |
| `user-price-alerts` | Interactive price alert lines | Medium |
| `bands-indicator` | Bollinger/Donchian bands with fill | Medium |

### 📋 Other Available Plugins
- `background-shade-series` - Custom series for shaded backgrounds
- `box-whisker-series` - Statistical box plots
- `brushable-area-series` - Interactive area selection
- `dual-range-histogram-series` - Two-range histograms
- `expiring-price-alerts` - Alerts with expiration
- `grouped-bars-series` - Grouped bar charts
- `heatmap-series` - Heat map visualization
- `highlight-bar-crosshair` - Enhanced crosshair
- `hlc-area-series` - High-Low-Close area
- `image-watermark` - Logo/image overlay
- `lollipop-series` - Lollipop chart type
- `overlay-price-scale` - Additional price scales
- `partial-price-line` - Partial horizontal lines
- `pretty-histogram` - Styled histogram
- `rectangle-drawing-tool` - Rectangle primitives
- `rounded-candles-series` - Aesthetic candles
- `stacked-area-series` - Stacked areas
- `stacked-bars-series` - Stacked bars
- `tooltip` - Enhanced tooltips
- `trend-line` - Trend line primitives
- `user-price-lines` - Interactive price levels
- `vertical-line` - Vertical line primitives

---

## Key Patterns from Official Sources

### 1. PluginBase Abstract Class
```typescript
// Located: plugin-examples/src/plugins/plugin-base.ts
export abstract class PluginBase implements ISeriesPrimitive<Time> {
    private _chart: IChartApi | undefined;
    private _series: ISeriesApi<...> | undefined;
    private _requestUpdate?: () => void;

    // Lifecycle
    attached({ chart, series, requestUpdate }) { ... }
    detached() { ... }

    // Getters
    get chart(): IChartApi { return ensureDefined(this._chart); }
    get series(): ISeriesApi<...> { return ensureDefined(this._series); }

    // Data hook
    protected dataUpdated?(scope: DataChangedScope): void;
    protected requestUpdate(): void { ... }
}
```

### 2. Session Highlighting Pattern
```typescript
// Key concepts from session-highlighting.ts:
// 1. Constructor takes a "highlighter" callback: (time: Time) => string
// 2. On data update, maps data to {time, color} pairs
// 3. Renderer uses zOrder: 'bottom' to draw behind candles
// 4. Calculates bar width dynamically from data spacing
```

### 3. Recommended Architecture
For our implementation:
1. Create `web/lib/charts/plugins/plugin-base.ts` (matches official pattern)
2. Extend from `PluginBase` for new plugins
3. Use `dataUpdated` hook for reactive updates
4. Implement standard `paneViews()` → `renderer()` → `draw()` flow

---

## Recommendations for Session Highlighting

**Migration Steps:**
1. Copy `plugin-base.ts` pattern to our codebase
2. Port `session-highlighting.ts` with adaptations:
   - Accept session definitions: `{ name, start, end, color, timezone }`
   - Convert time ranges to bar indices
   - Handle timezone conversion for accurate session detection

**Example Session Definition:**
```typescript
interface SessionDefinition {
    name: string;          // "NY Session"
    startHour: number;     // 9 (9:00 AM)
    endHour: number;       // 16 (4:00 PM)
    color: string;         // "rgba(76, 175, 80, 0.1)"
    timezone: string;      // "America/New_York"
    daysOfWeek?: number[]; // [1,2,3,4,5] (Mon-Fri)
}
```

---

## Live Demo
Official examples can be previewed at:
https://tradingview.github.io/lightweight-charts/plugin-examples
