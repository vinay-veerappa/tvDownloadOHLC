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

## Browser Support

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| Copy to clipboard | ✅ | ✅ | ⚠️ Limited | ✅ |
| Save as PNG | ✅ | ✅ | ✅ | ✅ |
| Open in new tab | ✅ | ✅ | ✅ | ✅ |

> **Note**: Safari may have limited clipboard support. Users should use "Save Image" as fallback.
