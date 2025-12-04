# Plugin Integration Workflow - Visual Guide

```
┌──────────────────────────────────────────────────────────────────┐
│                     PLUGIN INTEGRATION STATUS                     │
└──────────────────────────────────────────────────────────────────┘

                         ┌─────────────┐
                         │ PHASE 0     │
                         │ (Complete)  │
                         └──────┬──────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│ Copy Plugin  │       │  Configure   │       │   Wrap Chart │
│   Files ✅   │       │  ES6 Module  │       │     Init ✅  │
│              │       │    System ✅ │       │              │
│ 49 plugins   │       │              │       │  initChart() │
│ in plugins/  │       │ Import map   │       │  function    │
└──────────────┘       │ + Events     │       └──────────────┘
                       └──────────────┘

                         ┌─────────────┐
                         │ PHASE 1     │
                         │ (To Do)     │
                         └──────┬──────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Global     │       │    Plugin    │       │   Add UI     │
│  Exposure ❌ │       │   Loader ❌  │       │   Menus ❌   │
│              │       │              │       │              │
│ window.chart │       │ loadAndApply │       │  Plugins +   │
│ + series     │       │   Plugin()   │       │  Indicators  │
└──────────────┘       └──────────────┘       └──────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                         ┌──────▼──────┐
                         │  Add CSS ❌ │
                         │             │
                         │  Dropdown   │
                         │   Styles    │
                         └─────────────┘

                         ┌─────────────┐
                         │ PHASE 2     │
                         │ (Testing)   │
                         └──────┬──────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  Test Simple │       │     Test     │       │  Test All    │
│  Primitive   │       │  Indicator   │       │   Others     │
│              │       │              │       │              │
│  tooltip.js  │       │ moving-avg.js│       │ 45+ plugins  │
└──────────────┘       └──────────────┘       └──────────────┘
```

---

## File Edit Locations (Phase 1)

```
chart_ui.html (694 lines total)
├── Lines 1-111: Styles
│   └── ADD HERE: Dropdown menu CSS (Step 3)
│
├── Lines 116-193: Header/Toolbar HTML
│   └── ADD HERE: Plugin & Indicator menus (Step 4)
│
├── Lines 200-690: JavaScript
    ├── ADD HERE (before line 200): loadAndApplyPlugin() function (Step 2)
    │
    └── Inside initChart() function:
        ├── Line 224: Chart creation
        ├── Line 246: Series creation
        └── ADD HERE (after 246): window.chart & window.chartSeries (Step 1)
```

---

## Implementation Order

```
Step 1: Global Exposure (2 min)
   │
   ├─➤ Edit chart_ui.html line 246
   │   Add: window.chart = chart;
   │   Add: window.chartSeries = series;
   │
   └─➤ CHECKPOINT: Variables accessible globally
       Test: Open console, type "window.chart" (should not be undefined)

Step 2: Plugin Loader (5 min)
   │
   ├─➤ Edit chart_ui.html before line 200
   │   Add: loadAndApplyPlugin() function (~50 lines)
   │
   └─➤ CHECKPOINT: Function defined
       Test: Open console, type "typeof loadAndApplyPlugin" (should be "function")

Step 3: Dropdown CSS (2 min)
   │
   ├─➤ Edit chart_ui.html after line 111
   │   Add: .menu-dropdown and related styles (~50 lines)
   │
   └─➤ CHECKPOINT: Styles loaded
       Test: Inspect page, check <style> tag contains menu styles

Step 4: Plugin Menus (10 min)
   │
   ├─➤ Edit chart_ui.html after line 158
   │   Add: "Plugins" dropdown menu
   │   Add: "Indicators" dropdown menu (enhanced version)
   │
   └─➤ CHECKPOINT: Menus visible
       Test: Refresh page, see "Plugins" and "Indicators" buttons in toolbar

TOTAL TIME: ~20-30 minutes
```

---

## Testing Flow

```
Phase 1 Complete
    │
    ├─➤ Open chart in browser
    │   Open browser console (F12)
    │
    ├─➤ Test 1: Console Load
    │   │
    │   ├── Run: await loadAndApplyPlugin('tooltip', 'Tooltip', 'primitive')
    │   ├── Expected: Alert "Tooltip enabled!"
    │   └── Verify: Hover crosshair shows tooltip
    │
    ├─➤ Test 2: Menu Load
    │   │
    │   ├── Click: "Plugins" → "Tooltip"
    │   ├── Expected: Alert (already loaded or enabled)
    │   └── Verify: Menu interaction works
    │
    ├─➤ Test 3: Indicator
    │   │
    │   ├── Click: "Indicators" → "Moving Average"
    │   ├── Expected: MA line appears on chart
    │   └── Verify: Line updates with chart
    │
    └─➤ Test 4+: Try remaining plugins
        └── Document results in PLUGIN_INTEGRATION_GUIDE.md
```

---

## Plugin Categories Quick Reference

```
PRIMITIVES (attach to series)
├── tooltip.js ..................... Crosshair tooltip
├── delta-tooltip.js ............... Delta/change tooltip
├── vertical-line.js ............... Vertical line tool
├── volume-profile.js .............. Volume profile bars ⚠️ Special init
├── session-highlighting.js ........ Session backgrounds ⚠️ Needs config
└── [8 more]

INDICATORS (create new series)
├── moving-average.js .............. MA overlay
├── momentum.js .................... Momentum oscillator
├── correlation.js ................. Correlation indicator
└── [19 more]

SERIES TYPES (replace main series)
├── rounded-candles-series.js ...... Rounded candle style
├── hlc-area-series.js ............. HLC area chart
├── heatmap-series.js .............. Heatmap visualization
└── [11 more]
```

---

## Current vs Target State

### CURRENT (85% complete)
```
User clicks timeframe → Chart loads → Shows candles
                       ↓
                  Drawing tools work
                       ↓
                  Built-in indicators work
                       ↓
              ❌ NO plugin access ❌
```

### TARGET (After Phase 1)
```
User clicks timeframe → Chart loads → Shows candles
                       ↓
                  Drawing tools work
                       ↓
                  Built-in indicators work
                       ↓
              User clicks "Plugins" menu
                       ↓
              Selects plugin (e.g., Tooltip)
                       ↓
           loadAndApplyPlugin() executes
                       ↓
           Plugin attaches to chart/series
                       ↓
          ✅ Plugin active and working ✅
```

---

## Quick Checklist

### Before Starting
- [ ] Backup `chart_ui.html` (optional but recommended)
- [ ] Have `PLUGIN_INTEGRATION_GUIDE.md` open for reference
- [ ] Read through all 4 steps to understand flow

### During Implementation
- [ ] Step 1: Add global exposure (lines after 246)
- [ ] Step 2: Add plugin loader (lines before 200)
- [ ] Step 3: Add dropdown CSS (lines after 111)
- [ ] Step 4: Add plugin menus (lines after 158)

### After Implementation
- [ ] Save file
- [ ] Refresh browser
- [ ] Open console (F12)
- [ ] Run verification commands
- [ ] Test loading tooltip plugin
- [ ] Document results in guide

### If Issues Occur
- [ ] Check browser console for errors
- [ ] Verify window.chart exists
- [ ] Verify loadAndApplyPlugin is defined
- [ ] Check network tab for plugin file loading
- [ ] See DEBUGGING NOTES in main guide

---

For complete details, code snippets, and troubleshooting:
→ See `PLUGIN_INTEGRATION_GUIDE.md`
