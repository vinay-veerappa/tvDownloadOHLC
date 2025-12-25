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
│      ├─ navigation.takeScreenshot() → Canvas                    │
│      ├─ if 'copy': canvas.toBlob() → ClipboardItem              │
│      ├─ if 'save': canvas.toDataURL() → Download                │
│      └─ if 'open': canvas.toDataURL() → window.open()           │
└────────────────────────────────────────────────────┬────────────┘
                                                     │
                                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ChartContainer                                │
│  Exposes via useImperativeHandle:                               │
│    takeScreenshot: () => chart.takeScreenshot()                 │
└────────────────────────────────────────────────────┬────────────┘
                                                     │
                                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Lightweight Charts API                           │
│  chart.takeScreenshot() → HTMLCanvasElement                     │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Role |
|------|------|
| `components/top-toolbar.tsx` | UI - Camera button with dropdown menu |
| `components/chart-page-client.tsx` | Logic - `handleTakeScreenshot()` handler |
| `components/chart-container.tsx` | Bridge - Exposes `takeScreenshot()` via ref |

### Code Flow

1. User clicks camera icon → selects action from dropdown
2. `onTakeScreenshot(action)` called from TopToolbar
3. `handleTakeScreenshot(action)` in ChartPageClient:
   - Calls `navigation.takeScreenshot()` to get canvas
   - Based on action:
     - **copy**: `canvas.toBlob()` → `ClipboardItem` → `navigator.clipboard.write()`
     - **save**: `canvas.toDataURL()` → create `<a>` element → trigger download
     - **open**: `canvas.toDataURL()` → `window.open()` → write `<img>` tag

---

## Database Integration (Future)

The Trade model includes a `chartSnapshot` field for storing chart images with trade records:

```prisma
model Trade {
  // ... other fields
  chartSnapshot String? // URL or path to snapshot
}
```

This enables:
- Automatic chart capture on trade entry/exit
- Trade journal with visual context
- Playbook documentation with examples

---

## Dependencies

- **Lightweight Charts v5**: Provides `chart.takeScreenshot()` API
- **Clipboard API**: For copy-to-clipboard functionality
- **Lucide React**: Camera, Copy, Download, ExternalLink icons

---

## Known Limitations

### Elements NOT Captured by `takeScreenshot()`

| Element | Reason | Status |
|---------|--------|--------|
| **OHLC Legend** | HTML overlay (`<div>` elements) - not part of canvas | ⚠️ Not captured |
| **Ticker/Timeframe Label** | HTML overlay | ⚠️ Not captured |
| **Drawing Handles** | May be HTML overlay during edit mode | ⚠️ Not captured |

### Elements SHOULD Be Captured

| Element | Implementation | Status |
|---------|---------------|--------|
| **Trend Lines** | `ISeriesPrimitive` canvas rendering | ✅ Should work |
| **Vertical Lines** | `ISeriesPrimitive` canvas rendering | ✅ Should work |
| **Text Drawings** | `ISeriesPrimitive` canvas rendering | ✅ Should work |
| **Profiler Lines** | `ISeriesPrimitive` canvas rendering | ✅ Should work |

### Root Cause

Lightweight Charts `chart.takeScreenshot()` only captures content rendered on the `<canvas>` element. Any HTML elements positioned over the chart (overlays) are not included.

**Current overlays in our app:**
- `components/chart/chart-legend.tsx` - OHLC values + ticker name (HTML `<div>`)
- Drawing handles/anchors during edit mode

---

## Future Enhancements

### Option 1: Composite Screenshot (Recommended)
Use `html2canvas` or similar library to capture the entire chart container (canvas + HTML overlays):

```typescript
import html2canvas from 'html2canvas';

const handleTakeScreenshot = async () => {
    const container = document.getElementById('chart-container');
    const canvas = await html2canvas(container);
    // ... rest of logic
}
```

### Option 2: Canvas-based Legend
Re-implement OHLC legend as a Lightweight Charts primitive that renders directly to canvas.

### Option 3: Pre-render Overlay
Before taking screenshot, copy overlay content to a temporary canvas layer, merge with chart canvas, then capture.

---

## Browser Support

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| Copy to clipboard | ✅ | ✅ | ⚠️ Limited | ✅ |
| Save as PNG | ✅ | ✅ | ✅ | ✅ |
| Open in new tab | ✅ | ✅ | ✅ | ✅ |

> **Note**: Safari may have limited clipboard support. Users should use "Save Image" as fallback.
