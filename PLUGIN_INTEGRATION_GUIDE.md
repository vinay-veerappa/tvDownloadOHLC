# Plugin & Indicator Integration Guide

## 🔄 Current Integration Status (2024-12-03)

### ✅ Completed Steps
1. **Plugin Files Copied** - All 27 plugins and 22 indicators copied to `chart_ui/plugins/`
2. **Server Route Added** - `/plugins/{filename}.js` route added to `chart_server.py`
3. **Import Map Added** - ES6 module resolution configured in `chart_ui.html` (lines 7-13)
4. **ES Module Conversion** - LightweightCharts now loaded as ES module with global exposure (lines 14-19)
5. **Data Coverage Report Updated** - Shows NQ1 and ES1 data across multiple timeframes

### ⏸️ Next Steps (Resume Here)
1. **Add Plugin Loader Function** - Create `loadAndApplyPlugin()` in global scope
2. **Add Plugin/Indicator Menus** - Replace indicator dropdown with new menu structure
3. **Wrap Main Script** - Add `initChart()` function that waits for library ready event
4. **Expose Chart/Series Globally** - Set `window.chart` and `window.chartSeries`
5. **Test Plugins** - Start with Tooltip, then Volume Profile and Session Highlighting

### 📝 Notes
- Chart currently works with existing functionality (timeframes, indicators, drawing tools)
- ES module loads asynchronously - need to wait for `lightweightChartsReady` event
- Volume Profile needs: `new VolumeProfile(chart, series, vpData)`
- Session Highlighting needs: `new SessionHighlighting(highlighter, options)`

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
