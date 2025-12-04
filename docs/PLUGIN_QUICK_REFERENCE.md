# Plugin Integration - Quick Reference Card

## STATUS: 90% Complete - Phase 1 Step 1 DONE! ✅

🎉 **Critical Bug Fixed!** All buttons working, chart/series exposed globally.

---

## PHASE 1 CHECKLIST (~17 min remaining)

### ☑ ~~Step 1: Global Exposure (2 min)~~ ✅ DONE
**Status**: COMPLETED 2025-12-04  
**Added**: `window.chart`, `window.chartSeries`, and all interactive functions  
**Result**: All buttons working, chart fully functional!

---

### ☐ Step 2: Plugin Loader (5 min)
**File**: `chart_ui/chart_ui.html`  
**Location**: After line 246  
**Code**:
```javascript
window.chart = chart;
window.chartSeries = series;
```
**Test**: Console → `window.chart` (should show object)

---

### ☐ Step 2: Plugin Loader (5 min)
**File**: `chart_ui/chart_ui.html`  
**Location**: Before line 200  
**Code**: See PLUGIN_INTEGRATION_GUIDE.md lines 109-148  
**Test**: Console → `typeof loadAndApplyPlugin` (should be "function")

---

### ☐ Step 3: Dropdown CSS (2 min)
**File**: `chart_ui/chart_ui.html`  
**Location**: After line 111 in `<style>` section  
**Code**: See PLUGIN_INTEGRATION_GUIDE.md lines 52-105  
**Test**: Inspect → Check styles in `<style>` tag

---

### ☐ Step 4: Plugin Menus (10 min)
**File**: `chart_ui/chart_ui.html`  
**Location**: After line 158 in header  
**Code**: See PLUGIN_INTEGRATION_GUIDE.md lines 156-189  
**Test**: Refresh → See "Plugins" button in toolbar

---

## VERIFICATION COMMANDS

```javascript
// 1. Check library loaded
console.log(window.LightweightCharts);

// 2. Check chart exposed
console.log(window.chart);
console.log(window.chartSeries);

// 3. Check loader exists
console.log(typeof loadAndApplyPlugin);

// 4. Test loading plugin
await loadAndApplyPlugin('tooltip', 'Tooltip', 'primitive');
```

---

## FILE LOCATIONS

- **Edit**: `c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html`
- **Plugins**: `c:\Users\vinay\tvDownloadOHLC\chart_ui\plugins\` (49 files)
- **Guide**: `c:\Users\vinay\tvDownloadOHLC\PLUGIN_INTEGRATION_GUIDE.md`

---

## PLUGIN QUICK LIST

**Primitives** (attach to series):
- tooltip, delta-tooltip, vertical-line, anchored-text
- volume-profile ⚠️, session-highlighting ⚠️
- user-price-alerts, user-price-lines, trend-line
- expiring-price-alerts, highlight-bar-crosshair
- image-watermark, partial-price-line

**Indicators** (create overlay):
- moving-average, average-price, median-price
- weighted-close, momentum, percent-change
- correlation, product, ratio, spread, sum
- bands-indicator + 10 calculation helpers

**Series Types** (replace main):
- rounded-candles, hlc-area, box-whisker
- lollipop, stacked-area, stacked-bars, heatmap
- background-shade, brushable-area
- dual-range-histogram, grouped-bars

---

## TROUBLESHOOTING

| Error | Check |
|-------|-------|
| "chart is not defined" | Added `window.chart = chart;`? |
| "loadAndApplyPlugin not defined" | Added function before initChart()? |
| "Module not found" | Path is `./plugins/` not `./`? |
| Plugin doesn't appear | Check console for errors |
| Library not loaded | Waiting for ready event? |

---

## NEXT ACTIONS

1. ✅ Phase 0: Infrastructure (DONE)
2. ⏳ Phase 1: Implementation (DO NOW - 30 min)
3. 🧪 Phase 2: Testing (AFTER Phase 1)

---

## TESTING ORDER

1. **Tooltip** - Simplest primitive
2. **Moving Average** - Basic indicator  
3. **Vertical Line** - Drawing tool
4. **Volume Profile** ⚠️ - Special init
5. **Session Highlighting** ⚠️ - Needs config
6. Test remaining 44 plugins

---

## IMPLEMENTATION TIME ESTIMATE

- Step 1: 2 minutes ⏱️
- Step 2: 5 minutes ⏱️⏱️
- Step 3: 2 minutes ⏱️
- Step 4: 10 minutes ⏱️⏱️⏱️
- Testing: 10 minutes ⏱️⏱️⏱️

**Total: ~30 minutes**

---

## SUCCESS = ALL TRUE

- [ ] `window.chart` exists
- [ ] `window.chartSeries` exists  
- [ ] `loadAndApplyPlugin` is a function
- [ ] "Plugins" menu visible in toolbar
- [ ] Tooltip loads without errors
- [ ] Tooltip shows on crosshair hover

---

**For Complete Details**: See PLUGIN_INTEGRATION_GUIDE.md  
**For Visual Workflow**: See PLUGIN_INTEGRATION_WORKFLOW.md  
**For Quick Status**: See PLUGIN_INTEGRATION_STATUS.md  
**For Navigation**: See PLUGIN_DOCS_README.md

**Last Updated**: 2025-12-04 08:51 PST
