# User Guide

**Version 0.3.0** - Next.js Trading Platform

## Overview
This application provides a professional TradingView-inspired charting interface for analyzing OHLC data. Built with Next.js, TypeScript, and Lightweight Charts v5.

---

## 🖥️ Interface Overview

### Layout Structure
- **Top Toolbar**: Ticker selector, timeframe buttons, style selector, indicators, theme toggle
- **Left Toolbar**: Drawing tools, trading panel toggle
- **Chart Area**: Main chart canvas with price/time scales
- **Right Sidebar**: Object tree (drawings, indicators), settings
- **Bottom Bar**: Navigation, replay controls, timezone, date jump

---

## 📊 Chart Controls

### Ticker Selection
- Click the ticker dropdown in the top toolbar
- Select from available tickers (ES1!, NQ1!, etc.)
- Chart automatically loads data for the selected ticker

### Timeframe Selection
- Available: 1m, 5m, 15m, 1h, 4h, D, W
- Click any timeframe button to switch
- Data is filtered based on available timeframes for each ticker

### Chart Styles
Click the style dropdown to choose:
- **Candles**: Standard candlestick chart (default)
- **Bars**: OHLC bars
- **Line**: Close price line
- **Area**: Filled area under close price
- **Heiken-Ashi**: Smoothed candlesticks

### Theme Toggle
- Click the sun/moon icon in the top toolbar
- Switches between Light and Dark mode
- Chart colors adapt automatically

---

## 🛠️ Drawing Tools

Access via the **Left Toolbar** (vertical buttons on left edge).

| Tool | Description | How to Use |
|------|-------------|------------|
| **Cursor** | Select/move drawings | Click to select, drag to move |
| **Line** | Trend line segment | Click start, click end |
| **Ray** | Infinite ray | Click start, click direction |
| **Rectangle** | Price range box | Click corner, click opposite corner |
| **Fibonacci** | Retracement levels | Click low, click high (or vice versa) |
| **Vertical** | Vertical time line | Click anywhere |
| **Horizontal** | Horizontal price line | Click at desired price |
| **Text** | Text annotation | Click to place, type text |

### Managing Drawings
- **Select**: Click on any drawing
- **Delete**: Press `Delete` or `Backspace` key
- **Edit**: Double-click to open properties
- **Right-Click Menu**: Delete, Settings options

### Right Sidebar Object Tree
- **Drawings Tab**: Lists all drawings with select/delete options
- **Indicators Tab**: Lists active indicators with settings/delete

---

## 📈 Indicators

Click **"📊 Indicators"** in the top toolbar.

### Built-in Indicators
| Indicator | Description |
|-----------|-------------|
| **Hourly Profiler** | Highlights hourly/3-hour blocks with alternating quarter shading. |
| SMA | Simple Moving Average (configurable period) |
| EMA | Exponential Moving Average (configurable period) |
| Sessions | Market session highlighting |
| Watermark | Chart watermark text |

### Hourly Profiler Guide
The Hourly Profiler visually organizes price action into time blocks.
- **Hourly Blocks**: 1-hour ranges (Low/High/Open/Close/Mid).
- **Alternating Quarters**:
    - **1st Quarter (0-15m)**: Bounded/Highlighted.
    - **2nd Quarter (15-30m)**: Transparent.
    - **3rd Quarter (30-45m)**: Bounded/Highlighted.
    - **4th Quarter (45-60m)**: Transparent.
- **3-Hour Blocks**: Larger aggregation (e.g., 09:30-12:30).
- **Settings**: fully configurable colors, opacity, and visibility via the "Indicators" settings menu.

### Managing Indicators
- **Add**: Click indicator name in dropdown
- **Settings**: Click gear icon in "Object Tree" or Legend
- **Remove**: Click "×" in Object Tree or legend

---

## 💹 Trading Panel

### Opening the Trading Panel
- Click the **$** button in the left toolbar
- Panel appears in the right sidebar

### Placing Trades
1. Enter **Quantity** (lot size)
2. Click **Buy** or **Sell** button
3. Position appears with real-time P&L

### Position Management
- **Stop Loss / Take Profit**: Enter values before placing trade
- **Visual SL/TP**: Drag the lines on chart to adjust
- **Close Position**: Click "Close" button in bottom panel
- **Reverse Position**: Place opposite trade to flip direction

### Trade Reversals
- If you have a LONG position and place a SELL, it will:
  1. Close the LONG position
  2. Open a new SHORT position
- Same applies in reverse (SHORT → BUY → LONG)

---

## ⏪ Replay Mode

Simulate live market conditions by playing back historical data.

### Starting Replay
1. Click **Replay** button in bottom bar
2. Choose start option:
   - **Select Bar**: Click on chart to start from that bar
   - **Select Date**: Pick specific date from calendar
   - **First Available**: Start from beginning

### Replay Controls
| Control | Action |
|---------|--------|
| ▶️ Play | Auto-advance bars |
| ⏸️ Pause | Stop auto-advance |
| ⏭️ Step | Advance one bar |
| ⏮️ Back | Go back one bar |
| ⏹️ Stop | Exit replay mode |
| Speed | 1x to 10x playback speed |

### Timeframe Sync
- When you change timeframe in replay mode, the view stays synchronized
- The chart jumps to the same point in time in the new timeframe

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Delete / Backspace | Delete selected drawing |
| Left/Right Arrow | Scroll chart (in replay: step back/forward) |

---

## 🤖 Backtesting Platform

Access via the generic URL `/backtest` (Navigation link pending). This dedicated page allows automated strategy testing.

### 1. Configuration
- **Ticker**: Input the symbol (e.g., `ES1`, `NQ1`).
- **Timeframe**: Select resolution (e.g., `1h`, `15m`).
- **Parameters**: Configure strategy-specific inputs (e.g., Fast SMA: 9, Slow SMA: 21).

### 2. Execution
- Click **"Run Backtest"**.
- The system processes historical data and simulates trades based on the strategy.

### 3. Results Dashboard
- **Metrics**: Total Trades, Win Rate %, Profit Factor, Net P&L.
- **Visuals**: Chart with Buy (Up Arrow) and Sell (Down Arrow) markers.
- **Trade List**: Scrollable table of every trade execution with Entry/Exit prices and PnL.

---

## 🧭 Navigation

### Bottom Bar Controls
- **« / »**: Jump to start/end of data
- **< / >**: Scroll by bars
- **Go to Date**: Jump to specific date

### Date Range Info
- Bottom bar shows available data range
- Current bar count and position in replay mode

---

## 📝 Trading Journal (Bottom Panel)

### Opening the Journal Panel
- Click **Open Positions** or **Orders** tab in bottom panel
- Toggle panel with the expand/collapse button

### Views
- **Open Positions**: Current active trades with live P&L
- **Orders**: Pending limit/stop orders
- **Trade History**: Closed trades with metrics

### Trade Metrics (Captured Automatically)
- **MAE**: Max Adverse Excursion (worst drawdown)
- **MFE**: Max Favorable Excursion (best unrealized profit)
- **Duration**: Time position was held
- **P&L**: Final profit/loss

---

## 🔧 Settings

### Session Settings (Right Sidebar)
- Configure timezone for display
- Adjust chart preferences

### Magnet Mode (Top Toolbar)
- **Off**: Free drawing
- **Weak**: Snaps to OHLC prices nearby
- **Strong**: Always snaps to nearest price

---

## 💡 Tips

1. **Use Replay for Practice**: Paper trade with historical data
2. **Set SL/TP Before Entry**: Protect your positions
3. **Right-Click for Options**: Context menu on drawings
4. **Object Tree**: Quickly manage all chart objects
5. **Timeframe Sync**: Works in both normal and replay mode
