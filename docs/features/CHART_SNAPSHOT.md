# Chart Snapshot Feature

## Overview

The Chart Snapshot feature allows users to capture the current chart view as a PNG image for sharing, documentation, or archival purposes.

---

## User Interface

### Location
- **Top Toolbar** → Camera icon (right side, near settings)

### Actions
| Action | Description |
|--------|-------------|
| **Copy Image** | Copies the chart to clipboard (Ctrl+V to paste) |
| **Save Image** | Downloads as PNG file with auto-generated filename |
| **Open in New Tab** | Opens the chart image in a new browser tab |

### Filename Format
```
chart-{TICKER}-{TIMEFRAME}-{DATE}_{TIME}.png
```
Example: `chart-ES1-1D-2025-12-25_14-30-05.png`

---

## Technical Implementation

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TopToolbar                                │
│  ┌─────────┐                                                     │
│  │ Camera  │ ──→ onTakeScreenshot(action)                        │
│  └─────────┘                                                     │
└────────────────────────────────────────────────────┬────────────┘
                                                     │
                                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ChartPageClient                               │
│  handleTakeScreenshot(action: 'copy' | 'save' | 'open')         │
│      ├─ dynamic import('modern-screenshot')                     │
│      ├─ domToPng(captureArea)                                   │
│      ├─ if 'copy': fetch(dataUrl) → Blob → ClipboardItem        │
│      ├─ if 'save': link click → download                        │
│      └─ if 'open': window.open() → <img> tag                    │
└────────────────────────────────────────────────────┬────────────┘
                                                     │
                                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ChartContainer                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ OHLCLegend (Canvas Primitive)                             │  │
│  │ - Renders OHLC on canvas layer                            │  │
│  │ - Captured natively by LWC takeScreenshot()               │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Role |
|------|------|
| `components/top-toolbar.tsx` | UI - Camera button with dropdown menu |
| `components/chart-page-client.tsx` | Logic - `handleTakeScreenshot()` capturing `chart-capture-area` |
| `lib/charts/plugins/ohlc-legend.ts` | Canvas Plugin - Renders OHLCLegend directly on chart |
| `components/chart-container.tsx` | Integration - Attaches `OHLCLegend` to chart series |

### Code Flow

1. User clicks camera icon → selects action from dropdown
2. `handleTakeScreenshot` in `ChartPageClient` uses `modern-screenshot` to capture `#chart-capture-area`.
3. `modern-screenshot` clones the DOM, handles `oklch` colors (via bgcolor fallback), and properly captures multiple canvas layers.
4. The **OHLC Legend** is implemented as a canvas primitive (`ISeriesPrimitive`), ensuring it's always included in the canvas data.
5. High-DPI support is handled via `scale: window.devicePixelRatio`.

---

## Dependencies

- **modern-screenshot**: For robust DOM-to-image capture (handles CSS variables, SVGs, and nested canvases better than html2canvas).
- **Lightweight Charts v5**: Charting library.
- **Clipboard API**: For copy-to-clipboard functionality.

---

## Known Limitations

| Element | Status |
|---------|--------|
| **OHLC Legend** | ✅ Captured (Canvas Implementation) |
| **Ticker/Timeframe** | ✅ Captured (Canvas Implementation) |
| **Profiler Lines** | ✅ Captured (Canvas Layer) |
| **Axis Labels** | ✅ Captured (Canvas Layer) |
| **Context Menus** | ❌ Not Captured (Transient UI) |

### Troubleshooting

If a screenshot fails with `modern-screenshot`, the app automatically falls back to the native `chart.takeScreenshot()` method which captures only the main chart canvas (without legends).

---

## Browser Support

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| Copy to clipboard | ✅ | ✅ | ⚠️ Limited | ✅ |
| Save as PNG | ✅ | ✅ | ✅ | ✅ |
| Open in new tab | ✅ | ✅ | ✅ | ✅ |

> **Note**: Safari may have limited clipboard support. Users should use "Save Image" as fallback.
