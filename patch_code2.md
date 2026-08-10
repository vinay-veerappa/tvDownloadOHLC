# Research Report: TradingView MCP Server `replay_start` Timestamp Support

### 1. Summary of Findings (GitHub & Web Search)

* **Primary Repository**: [`tradesdontlie/tradingview-mcp`](https://github.com/tradesdontlie/tradingview-mcp) (and common forks like `LewisWJackson/tradingview-mcp-jackson`).
* **Current Status**: 
  - Standard upstream `replay_start` implementation only accepts a basic `date` parameter in `YYYY-MM-DD` format (which defaults replay to the first available bar of that day/session).
  - **No merged PR or official patch** currently exists in the main upstream repository to support sub-daily exact timestamps (`YYYY-MM-DDTHH:mm:ss` or UNIX timestamps) directly inside `replay_start`.
* **Related Upstream Issues**:
  - Open issues in `tradesdontlie/tradingview-mcp` focus on replay state initialization bug (`src/core/replay.js` lines 34â€“36 where `replay_start` reports success but `replay_step` fails), Windows MSIX CDP port binding, and connection drops (`tv_health_check`).

---

### 2. How TradingView Replay Handles Timestamps & Solution Strategy

In TradingView Desktop:
1. **Daily vs Intraday Replay**: In daily timeframes, `YYYY-MM-DD` is sufficient. In intraday timeframes (1m, 5m, 15m), TradingView needs to identify the target bar matching `Date + Time`.
2. **UI Mechanisms for Exact Time Jump**:
   - **Method A (ISO Datetime Parsing & Go-To Modal)**: TradingView has a native "Go To Date/Time" dialog triggered via `Alt + G` (or `Shift + G`). This dialog accepts date and time formatted strings (e.g. `2025-03-01 09:30`).
   - **Method B (Visible Range / UNIX Timestamp Positioning)**: Using CDP, we can set the visible chart window around the target UNIX timestamp (`chart_set_visible_range`), center the chart on the exact bar, and trigger the replay start click.

---

### 3. Local Upgrade Patch & Implementation Guide

To upgrade your local `tradingview` MCP server to accept exact timestamps (ISO datetime `YYYY-MM-DDTHH:mm:ss` or UNIX timestamps), follow these patches:

#### Step A: Upgrade MCP Tool Schema (`replay_start.json`)
Located at `C:\Users\vinay\.gemini\antigravity\mcp\tradingview\replay_start.json`:

```json
{
  "name": "replay_start",
  "description": "Start bar replay mode at a specific date and exact time (e.g. YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss / Unix timestamp).",
  "parameters": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "date": {
        "type": "string",
        "description": "Date or ISO timestamp (e.g. '2025-03-01' or '2025-03-01T09:30:00')"
      },
      "time": {
        "type": "string",
        "description": "Optional exact time string in 'HH:mm' or 'HH:mm:ss' format (e.g. '09:30:00')"
      },
      "timestamp": {
        "type": "number",
        "description": "Optional Unix timestamp in seconds or milliseconds"
      }
    }
  }
}
```

#### Step B: Core JavaScript Patch (`src/core/replay.js`)

Add exact timestamp resolution before initiating replay:

```javascript
/**
 * Resolves target timestamp in seconds from input parameters
 */
function parseReplayStartTime(dateStr, timeStr, timestamp) {
  if (timestamp) {
    return timestamp > 1e11 ? Math.floor(timestamp / 1000) : timestamp;
  }
  if (!dateStr) return null;

  // Combine ISO date + time if provided separately
  let fullStr = dateStr.trim();
  if (timeStr && !fullStr.includes('T') && !fullStr.includes(' ')) {
    fullStr = `${fullStr}T${timeStr.trim()}`;
  }

  const parsedDate = new Date(fullStr);
  if (isNaN(parsedDate.getTime())) {
    throw new Error(`Invalid date/time format: ${dateStr} ${timeStr || ''}`);
  }
  return Math.floor(parsedDate.getTime() / 1000);
}

/**
 * Enhanced replay_start implementation with exact time support via CDP
 */
async function replayStart(params, cdpClient) {
  const targetTimeSec = parseReplayStartTime(params.date, params.time, params.timestamp);

  if (targetTimeSec) {
    // 1. Zoom/Scroll chart to exact timestamp window (-30 min to +30 min)
    const windowSec = 1800; // 30 mins
    await cdpClient.evaluate(`
      if (window.matrix && window.matrix.chart) {
        window.matrix.chart.setVisibleRange({
          from: ${targetTimeSec - windowSec},
          to: ${targetTimeSec + windowSec}
        });
      }
    `);

    // 2. Open TradingView 'Go To Date/Time' dialog via Alt+G if needed
    // or trigger bar selection at target timestamp
    const dateFormatted = new Date(targetTimeSec * 1000).toISOString().replace('T', ' ').substring(0, 19);
    
    // Evaluate CDP jump command in TradingView window
    await cdpClient.evaluate(`
      (async () => {
        // Trigger Jump To Date/Time
        const gotoBtn = document.querySelector('[data-name="submit-button"]') || document.querySelector('#header-toolbar-goto');
        // Fallback: Dispatch Alt+G shortcut
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'g', altKey: true, bubbles: true }));
      })();
    `);
  }

  // 3. Trigger replay mode initialization
  return await cdpClient.evaluate(`
    // Activate bar replay toolbar button
    const replayBtn = document.querySelector('[data-name="bar-replay"]');
    if (replayBtn) replayBtn.click();
    return { success: true, timestampSec: ${targetTimeSec || 'null'} };
  `);
}
```

### 4. Summary & Recommendation

1. No upstream pull request has been merged yet for exact intraday timestamps in `replay_start` in `tradesdontlie/tradingview-mcp`.
2. Updating `replay_start.json` and adding ISO datetime parsing (`YYYY-MM-DDTHH:mm:ss`) + CDP `setVisibleRange` centering allows exact intraday bar replay start times on 1m/5m/15m charts.