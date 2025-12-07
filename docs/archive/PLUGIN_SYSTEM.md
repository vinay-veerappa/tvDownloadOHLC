# Plugin System Master Guide

> ⚠️ **LEGACY DOCUMENTATION**
> 
> This document applies to the **legacy Vanilla JS chart viewer** (`legacy_chart_ui/`).
> The new Next.js platform (`web/`) uses a different architecture with built-in plugins.
> See [USER_GUIDE.md](USER_GUIDE.md) for current platform documentation.

---

**Last Updated**: 2025-12-04 12:45 PST

## 🔄 Current Status: Phase 1 Complete (UI Redesign) ✅ 

### 🚨 Major Milestone Achieved! (2025-12-04)
**Achievement**: Complete UI Redesign with TradingView-inspired layout.
**New Features**: Left Sidebar, Measure Tool, Alert Tool, Price Line Tool.
**Result**: Professional charting interface with integrated plugins.

### What's Working
- ✅ **Measure Tool** (Delta Tooltip) integrated in toolbar
- ✅ **Alert Tool** (User Price Alerts) integrated in toolbar
- ✅ **Price Line Tool** (User Price Lines) integrated in toolbar
- ✅ All 49 plugin files copied and served correctly
- ✅ ES6 module system fully configured
- ✅ Chart initialization wrapped and event-driven
- ✅ Chart UI with all existing features working
- ✅ **window.chart and window.chartSeries globally exposed**

### What's Missing (Phase 2 - Indicators Modal)
1. ❌ Indicators Modal Dialog (to replace dropdowns)
2. ❌ Chart Legend (for active plugins)
3. ❌ Drawing Selection/Deletion (partially implemented)

### Next Action
**Implement Phase 2** (Indicators Modal) to allow easy access to all 49 plugins.

---

## 📚 Plugin Inventory

### Primitives (13 files) - Attach to Series
| File | Description | Init Type | Status |
|------|-------------|-----------|--------|
| `tooltip.js` | Crosshair tooltip | Simple | Ready |
| `delta-tooltip.js` | Delta tooltip | Simple | ✅ Integrated (Toolbar) |
| `vertical-line.js` | Vertical line drawing | Simple | Ready |
| `anchored-text.js` | Text annotations | Simple | Ready |
| `volume-profile.js` | Volume profile | Special ⚠️ | Needs custom init |
| `session-highlighting.js` | Session highlighting | Special ⚠️ | Needs options |
| `user-price-alerts.js` | Price alerts | Simple | ✅ Integrated (Toolbar) |
| `user-price-lines.js` | Price lines | Simple | ✅ Integrated (Toolbar) |
| `trend-line.js` | Trend line | Simple | Ready |
| `expiring-price-alerts.js` | Expiring alerts | Simple | Ready |
| `highlight-bar-crosshair.js` | Bar highlighting | Simple | Ready |
| `image-watermark.js` | Image watermark | Simple | Ready |
| `partial-price-line.js` | Partial price line | Simple | Ready |

### Indicators (22 files) - Return New Series
| File | Description | Status |
|------|-------------|--------|
| `moving-average.js` | Moving average | Ready |
| `average-price.js` | Average price | Ready |
| `median-price.js` | Median price | Ready |
| `weighted-close.js` | Weighted close | Ready |
| `momentum.js` | Momentum | Ready |
| `percent-change.js` | Percent change | Ready |
| `correlation.js` | Correlation | Ready |
| `product.js` | Product | Ready |
| `ratio.js` | Ratio | Ready |
| `spread.js` | Spread | Ready |
| `sum.js` | Sum | Ready |
| `bands-indicator.js` | Bands | Ready |
| Plus 10 `-calculation.js` helpers | | Ready |

### Series Types (14 files) - Replace Main Series
| File | Description | Status |
|------|-------------|--------|
| `rounded-candles-series.js` | Rounded candles | Ready |
| `hlc-area-series.js` | HLC area | Ready |
| `box-whisker-series.js` | Box whisker | Ready |
| `lollipop-series.js` | Lollipop | Ready |
| `stacked-area-series.js` | Stacked area | Ready |
| `stacked-bars-series.js` | Stacked bars | Ready |
| `heatmap-series.js` | Heatmap | Ready |
| `background-shade-series.js` | Background shade | Ready |
| `brushable-area-series.js` | Brushable area | Ready |
| `dual-range-histogram-series.js` | Dual range histogram | Ready |
| `grouped-bars-series.js` | Grouped bars | Ready |
| `rectangle-drawing-tool.js` | Rectangle tool | Ready |

---

## 🛠️ Technical Integration Guide

## 📊 PLUGIN INVENTORY

### Primitives (13 files) - Attach to Series
| File | Description | Init Type | Status |
|------|-------------|-----------|--------|
| `tooltip.js` | Crosshair tooltip | Simple | Ready |
| `delta-tooltip.js` | Delta tooltip | Simple | ✅ Integrated (Toolbar) |
| `vertical-line.js` | Vertical line drawing | Simple | Ready |
| `anchored-text.js` | Text annotations | Simple | Ready |
| `volume-profile.js` | Volume profile | Special ⚠️ | Needs custom init |
| `session-highlighting.js` | Session highlighting | Special ⚠️ | Needs options |
| `user-price-alerts.js` | Price alerts | Simple | ✅ Integrated (Toolbar) |
| `user-price-lines.js` | Price lines | Simple | ✅ Integrated (Toolbar) |
| `trend-line.js` | Trend line | Simple | Ready |
| `expiring-price-alerts.js` | Expiring alerts | Simple | Ready |
| `highlight-bar-crosshair.js` | Bar highlighting | Simple | Ready |
| `image-watermark.js` | Image watermark | Simple | Ready |
| `partial-price-line.js` | Partial price line | Simple | Ready |

### Indicators (22 files) - Return New Series
| File | Description | Status |
|------|-------------|--------|
| `moving-average.js` | Moving average | Ready |
| `average-price.js` | Average price | Ready |
| `median-price.js` | Median price | Ready |
| `weighted-close.js` | Weighted close | Ready |
| `momentum.js` | Momentum | Ready |
| `percent-change.js` | Percent change | Ready |
| `correlation.js` | Correlation | Ready |
| `product.js` | Product | Ready |
| `ratio.js` | Ratio | Ready |
| `spread.js` | Spread | Ready |
| `sum.js` | Sum | Ready |
| `bands-indicator.js` | Bands | Ready |
| Plus 10 `-calculation.js` helpers | | Ready |

### Series Types (14 files) - Replace Main Series
| File | Description | Status |
|------|-------------|--------|
| `rounded-candles-series.js` | Rounded candles | Ready |
| `hlc-area-series.js` | HLC area | Ready |
| `box-whisker-series.js` | Box whisker | Ready |
| `lollipop-series.js` | Lollipop | Ready |
| `stacked-area-series.js` | Stacked area | Ready |
| `stacked-bars-series.js` | Stacked bars | Ready |
| `heatmap-series.js` | Heatmap | Ready |
| `background-shade-series.js` | Background shade | Ready |
| `brushable-area-series.js` | Brushable area | Ready |
| `dual-range-histogram-series.js` | Dual range histogram | Ready |
| `grouped-bars-series.js` | Grouped bars | Ready |
| `rectangle-drawing-tool.js` | Rectangle tool | Ready |

---

## 🚨 KNOWN ISSUES & CONSIDERATIONS

### Issue 1: Volume Profile Initialization
- **Problem**: Requires specific data format: `{ value: price, volume: vol }`
- **Solution**: TBD - may need to transform data or create custom loader
- **Priority**: Medium (can test other plugins first)

### Issue 2: Session Highlighting Configuration
- **Problem**: Requires options object with session times
- **Solution**: TBD - may need UI for configuration
- **Priority**: Medium (can test other plugins first)

### Issue 3: Plugin Parameters
- **Problem**: Some plugins may need initialization parameters
- **Current Solution**: Hard-coded defaults in `loadAndApplyPlugin()`
- **Future**: Add parameter UI or configuration system
- **Priority**: Low (can enhance later)

### Issue 4: Plugin Removal
- **Problem**: No way to remove/toggle plugins after adding
- **Current Solution**: Reload page to clear
- **Future**: Add plugin manager with remove capability
- **Priority**: Low (Phase 3 enhancement)

---

## 📝 TESTING LOG

### Session 1: 2025-12-04 09:00-09:07 PST ✅
**Goal**: Verify current state and begin Phase 1 implementation  
**Status**: COMPLETED (with critical bug fix)

**Actions Taken**:
1. Started chart server on http://localhost:8000
2. Opened chart UI in browser (loaded successfully with 20,000 bars)
3. Verified infrastructure via browser console:
   - ✅ `window.LightweightCharts` = object (library loaded)
   - ❌ `window.chart` = undefined (PROBLEM FOUND!)
   - ❌ `window.chartSeries` = undefined (PROBLEM FOUND!)
   - ❌ `typeof loadAndApplyPlugin` = undefined (expected)

**Critical Bug Discovered** 🚨:
- **Symptom**: All buttons unresponsive, clicking produced console errors
- **Console Errors**: "ReferenceError: changeTimeframe is not defined", "ReferenceError: setTool is not defined", etc.
- **Root Cause**: When chart init was wrapped in `initChart()` function, all functions became **local scope**. HTML `onclick` handlers expected global scope.
- **Functions Affected**: `changeTimeframe`, `setTool`, `clearDrawings`, `jumpToDate`, `toggleStrategy`, `addIndicatorFromMenu`, `addWatermark`

**Fix Applied**:
1. Added global exposure for chart objects (lines 248-250):
   ```javascript
   window.chart = chart;
   window.chartSeries = series;
   ```
2. Added global exposure for all interactive functions (lines 685-692):
   ```javascript
   window.changeTimeframe = changeTimeframe;
   window.setTool = setTool;
   // ... + 5 more functions
   ```

**Verification Testing**:
- ✅ Refreshed page, chart loaded normally
- ✅ Clicked "5m" timeframe button → Chart updated to 5m data, button highlighted
- ✅ Clicked "Line" drawing tool → Button activated, cursor changed to crosshair
- ✅ Console checked → No ReferenceError messages
- ✅ `window.chart` = object (verified in console)
- ✅ `window.chartSeries` = object (verified in console)  
- ✅ `typeof window.changeTimeframe` = "function" (verified in console)

**Results**:
- ✅ Critical bug FIXED
- ✅ All chart features working: timeframes, drawing tools, indicators
- ✅ Phase 1 Step 1 COMPLETE
- ✅ Ready for Steps 2-4
- ✅ Git commit: `46617f2` "Fix critical global scope issue"

**Lessons Learned**:
- When wrapping code in functions for async loading, must explicitly expose needed functions globally
- Always test button functionality, not just chart rendering
- Browser console errors are critical to check during testing
- Infrastructure testing alone isn't enough - need functional testing too

**Next Session Goal**: Implement Phase 1 Steps 2-4 (plugin loader, CSS, menus)

---

### Session 2: [Date TBD]
**Goal**: Complete Phase 1 Steps 2-4  
**Status**: NOT STARTED

---

## 🔍 DEBUGGING NOTES

### Common Issues
- **Module not found**: Check import path in `loadAndApplyPlugin()` - should be `./plugins/`
- **Chart not defined**: Ensure `window.chart` is set after chart creation
- **Series not defined**: Ensure `window.chartSeries` is set after series creation
- **Library not loaded**: Check that code runs after `lightweightChartsReady` event

### Verification Commands (Browser Console)
```javascript
// Check if library is loaded
console.log(window.LightweightCharts);

// Check if chart is exposed
console.log(window.chart);
console.log(window.chartSeries);

// Check if plugin loader exists
console.log(typeof loadAndApplyPlugin);

// Test loading a plugin
await loadAndApplyPlugin('tooltip', 'Tooltip', 'primitive');
```

---

## 📚 REFERENCE - Implementation Details

## Overview
This guide explains how to integrate all 27 compiled plugins and 22 indicator modules into the chart interface.

## Plugin Structure Analysis

### 1. Plugin Types

After examining the compiled files, I found they export different types:

**Primitives (attach to series)**:
- `tooltip.js` - exports `TooltipPrimitive`  
- `vertical-line.js` - exports `VertLine`
- `anchored-text.js` - exports `AnchoredText`

**Indicator Functions**:
- `moving-average.js` - exports `applyMovingAverageIndicator(series, options)`
- `average-price.js` - exports similar pattern
- All other indicators follow this pattern

**Series Types**:
- `rounded-candles-series.js` - custom series type
- `hlc-area-series.js` - custom series type

## Integration Approach

### Option 1: Simple Dropdown Menus (Recommended for Now)

Add CSS for dropdown menus at line 35 in chart_ui.html:

```css
/* Dropdown Menu Styles */
.menu-dropdown {
    position: relative;
    display: inline-block;
}
.menu-content {
    display: none;
    position: absolute;
    background-color: #2a2e39;
    min-width: 220px;
    box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.5);
    z-index: 1000;
    border-radius: 4px;
    border: 1px solid #4a4e59;
    max-height: 450px;
    overflow-y: auto;
}
.menu-content a {
    color: #d1d4dc;
    padding: 10px 16px;
    text-decoration: none;
    display: block;
    font-size: 13px;
}
.menu-content a:hover {
    background-color: #3a3e49;
}
.menu-dropdown:hover .menu-content {
    display: block;
}
.menu-category {
    color: #888;
    padding: 8px 16px;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    border-top: 1px solid #363c4e;
}
.menu-category:first-child {
    border-top: none;
}
.plugin-badge {
    display: inline-block;
    background: #2962FF;
    color: white;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 10px;
    margin-left: 8px;
}
```

### Option 2: Module Loading System

Create a plugin loader in the JavaScript section:

```javascript
// Plugin/Module Registry
window.pluginModules = new Map();
window.activePlugins = [];

// Dynamic module loader
async function loadAndApplyPlugin(moduleName, displayName, type = 'primitive') {
    if (window.pluginModules.has(moduleName)) {
        alert(`${displayName} already loaded`);
        return;
    }
    
    try {
        const module = await import('./' + moduleName + '.js');
        window.pluginModules.set(moduleName, module);
        
        // Apply based on type
        if (type === 'primitive') {
            // For TooltipPrimitive, VertLine, etc.
            const PrimitiveClass = module[Object.keys(module)[0]];
            const primitive = new PrimitiveClass();
            series.attachPrimitive(primitive);
            window.activePlugins.push({ name: moduleName, instance: primitive });
            alert(`${displayName} enabled!`);
        }
        else if (type === 'indicator') {
            // For moving-average, etc.
            const indicatorFn = module[Object.keys(module)[0]];
            const indicatorSeries = indicatorFn(series, { length: 20 });
            window.activePlugins.push({ name: moduleName, series: indicatorSeries });
            alert(`${displayName} added!`);
        }
        
    } catch (error) {
        console.error(`Failed to load ${displayName}:`, error);
        alert(`Error loading ${displayName}: ${error.message}`);
    }
}
```

## HTML Structure Update

Replace the indicator dropdown (around line 67) with:

```html
<!-- Enhanced Plugins Menu -->
<div class="menu-dropdown">
    <button>🧩 Plugins</button>
    <div class="menu-content">
        <div class="menu-category">Tooltips</div>
        <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('tooltip', 'Tooltip', 'primitive');">Crosshair Tooltip</a>
        <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('delta-tooltip', 'Delta Tooltip', 'primitive');">Delta Tooltip</a>
        
        <div class="menu-category">Visual</div>
        <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('volume-profile', 'Volume Profile', 'primitive');">Volume Profile</a>
        <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('session-highlighting', 'Session Highlighting', 'primitive');">Session Highlighting</a>
    </div>
</div>

<!-- Enhanced Indicators Menu -->
<div class="menu-dropdown">
    <button>📊 Indicators</button>
    <div class="menu-content">
        <div class="menu-category">Built-in</div>
        <a href="#" onclick="event.preventDefault(); addIndicatorFromMenu('sma');">SMA (20)</a>
        <a href="#" onclick="event.preventDefault(); addIndicatorFromMenu('ema');">EMA (50)</a>
        <a href="#" onclick="event.preventDefault(); addIndicatorFromMenu('vwap');">VWAP</a>
        <a href="#" onclick="event.preventDefault(); addIndicatorFromMenu('bb');">Bollinger Bands</a>
        <a href="#" onclick="event.preventDefault(); addIndicatorFromMenu('rsi');">RSI (14)</a>
        <a href="#" onclick="event.preventDefault(); addIndicatorFromMenu('macd');">MACD</a>
        <a href="#" onclick="event.preventDefault(); addIndicatorFromMenu('atr');">ATR (14)</a>
        
        <div class="menu-category">New Indicators</div>
        <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('moving-average', 'Moving Average', 'indicator');">Moving Average</a>
        <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('average-price', 'Average Price', 'indicator');">Average Price</a>
        <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('median-price', 'Median Price', 'indicator');">Median Price</a>
        <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('momentum', 'Momentum', 'indicator');">Momentum</a>
    </div>
</div>
```

## Plugin Reference

### Primitives (Attach to Series)
1. `tooltip.js` - TooltipPrimitive
2. `delta-tooltip.js` - DeltaTooltipPrimitive
3. `vertical-line.js` - VertLine
4. `anchored-text.js` - AnchoredText
5. `volume-profile.js` - VolumeProfilePrimitive
6. `session-highlighting.js` - SessionHighlightingPrimitive
7. `user-price-alerts.js` - PriceAlertsPrimitive
8. `user-price-lines.js` - PriceLinesPrimitive

### Indicators (Return New Series)
1. `moving-average.js` - applyMovingAverageIndicator()
2. `average-price.js` - applyAveragePriceIndicator()
3. `median-price.js` - applyMedianPriceIndicator()
4. `weighted-close.js` - applyWeightedCloseIndicator()
5. `momentum.js` - applyMomentumIndicator()
6. `percent-change.js` - applyPercentChangeIndicator()
7. `correlation.js` - applyCorrelationIndicator()
8. `product.js` - applyProductIndicator()
9. `ratio.js` - applyRatioIndicator()
10. `spread.js` - applySpreadIndicator()
11. `sum.js` - applySumIndicator()

### Series Types (Replace Main Series)
1. `rounded-candles-series.js` - RoundedCandlestickSeries
2. `hlc-area-series.js` - HLCAreaSeries
3. `box-whisker-series.js` - BoxWhiskerSeries
4. `lollipop-series.js` - LollipopSeries
5. `stacked-area-series.js` - StackedAreaSeries
6. `stacked-bars-series.js` - StackedBarsSeries
7. `heatmap-series.js` - HeatmapSeries

## Implementation Steps

1. **Add CSS** for dropdown menus (lines 35-88 in chart_ui.html)
2. **Add Plugin Loader** function to JavaScript section
3. **Replace Indicator Dropdown** with new enhanced menus
4. **Test** one plugin at a time

## Example Usage

```javascript
// Load tooltip plugin
await loadAndApplyPlugin('tooltip', 'Tooltip', 'primitive');

// Load moving average indicator
await loadAndApplyPlugin('moving-average', 'Moving Average', 'indicator');
```

## Limitations

- ES6 modules require `import` statements
- Cannot load modules with regular `<script>` tags
- Need proper MIME types from server
- Some plugins may require initialization options

## Recommended Next Step

Start with a minimal integration:
1. Add CSS for dropdown menus only
2. Keep existing indicator dropdown working
3. Add one "Test Plugin" button that loads tooltip.js
4. Once that works, expand to full menu system

This approach reduces risk of breaking the existing working chart.
