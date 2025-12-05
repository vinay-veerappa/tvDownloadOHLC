# Usable Legacy Plugins Inventory

The following plugins were found in `legacy_chart_ui` and are suitable for migration to the new TypeScript/React architecture.

## ✅ Completed

### 1. Delta Tooltip (Measuring Tool)
*   **Source:** `legacy_chart_ui/delta-tooltip.js`
*   **Ported To:** `web/lib/charts/plugins/measuring-tool.ts`
*   **Status:** ✅ **COMPLETE** - TradingView-style UI with dashed guides, color-coded labels.

### 2. Anchored Text (Watermark)
*   **Source:** `legacy_chart_ui/anchored_text_plugin.js`
*   **Ported To:** `web/lib/charts/plugins/anchored-text.ts`
*   **Status:** ✅ **COMPLETE** - Fixed screen positioning, editable via PropertiesModal.

### 3. Session Highlighting
*   **Source:** `legacy_chart_ui/session-highlighting.js`
*   **Ported To:** `web/lib/charts/plugins/session-highlighting.ts`
*   **Status:** ✅ **COMPLETE** - Timezone-aware sessions (Tokyo/London/NY), extends PluginBase.

## 🌟 High Priority (Remaining)

### 1. Volume Profile
*   **Source:** `legacy_chart_ui/session-highlighting.js`
*   **Functionality:** Draws background colored stripes for specific time ranges (e.g., NY Session, London Session).
*   **Migration:** Medium Complexity. Logic is self-contained. Needs to be adapted to receive session definition objects (Timezone aware).
*   **Recommendation:** Port as `SessionHighlighter` plugin.

### 4. Volume Profile (Fixed Range)
*   **Source:** `legacy_chart_ui/volume-profile.js`
*   **Functionality:** Renders horizontal volume histograms.
*   **Dependency:** Requires pre-calculated `vpData` (price levels and volume). The drawing logic is ready, but the *calculation* logic (binning trades/ticks) is backend-dependent or needs to be written in TS.
*   **Recommendation:** Port drawing logic now; connect to data source later.

## 📊 Indicators & Series Types

### 1. Bands Indicator (Bollinger/Donchian)
*   **Source:** `legacy_chart_ui/bands-indicator.js`
*   **Functionality:** Renders a filled area between an Upper and Lower line.
*   **Migration:** Medium. Uses `Path2D` for fill. Standard "Band" series type.

### 2. Custom Series Types
Found several custom series implementions that extend standard candle/line capabilities:
*   `box-whisker-series.js`: Box plots.
*   `heatmap-series.js`: Heatmap grid.
*   `rounded-candles-series.js`: Aesthetic alternative to standard candles.
*   `stacked-area-series.js` / `stacked-bars-series.js`.

## 🛠 Utilities

### 1. Expiring Price Alerts
*   **Source:** `legacy_chart_ui/expiring-price-alerts.js`
*   **Functionality:** Renders lines for price alerts that might have an expiry time.
*   **Migration:** Medium. Useful for the "Alerts" feature.

### 2. Image Watermark
*   **Source:** `legacy_chart_ui/image-watermark.js`
*   **Functionality:** Draws an image (logo) in the chart background.
*   **Migration:** Low.

## Migration Strategy

1.  **Measuring Tool (`delta-tooltip.js`)**: Port first to solve the "Measure" tool requirement.
2.  **Session Highlighting**: Port second for "Sessions" feature.
3.  **Anchored Text**: Port third as a quick win for "Watermarks".

## 📂 Archive Repository (`archive/temp_repo`)

This directory appears to be a partial clone of the core `lightweight-charts` library.

### Indicator Examples (`archive/temp_repo/indicator-examples`)
Contains **compiled** JavaScript (ESM/UMD) for several standard indicators. The TypeScript source (`src`) is missing, but the compiled files can be used as references or reverse-engineered.

*   `average-price`
*   `correlation`
*   `median-price`
*   `momentum`
*   `moving-average` (Key for our "Indicators" feature)
*   `percent-change`
*   `product`
*   `ratio`
*   `spread`
*   `sum`
*   `weighted-close`

**Strategy:** Since these are compiled, it is better to prioritize the **uncompiled** source files found in `legacy_chart_ui` where available. For example, `legacy_chart_ui/moving-average.js` seems to be an uncompiled source file, which is much better for migration.

## 📚 Official TypeScript References

The official TradingView `lightweight-charts` repository contains TypeScript source examples:

- **Indicators**: [github.com/tradingview/lightweight-charts/tree/master/indicator-examples](https://github.com/tradingview/lightweight-charts/tree/master/indicator-examples)
- **Plugins**: [github.com/tradingview/lightweight-charts/tree/master/plugin-examples](https://github.com/tradingview/lightweight-charts/tree/master/plugin-examples)

These are valuable references for implementing new features with proper TypeScript patterns.
