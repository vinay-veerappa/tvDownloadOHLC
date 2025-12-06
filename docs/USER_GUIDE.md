# Chart UI User Guide

## Overview
This application provides a professional charting interface for analyzing OHLC data (ES1, NQ1). It features a TradingView-like interface with drawing tools, indicators, and plugins.

## 🛠️ Drawing Tools
The drawing toolbar is located on the left side of the screen.

| Icon | Tool | Description | Usage |
|------|------|-------------|-------|
| 📏 | **Line** | Draw a simple line segment | Click start point, click end point. |
| 📉 | **Ray** | Draw an infinite ray | Click start point, click second point to define direction. |
| ▭ | **Rectangle** | Draw a rectangle | Click top-left corner, click bottom-right corner. |
| 🔢 | **Fibonacci** | Fibonacci Retracement | Click start point (low/high), click end point (high/low). |
| │ | **Vertical Line** | Draw a vertical line | Click any point on the time axis. |
| ─ | **Price Line** | Draw a horizontal price line | Click any point on the price axis. |
| 🔔 | **Alert** | Add a price alert | Click to activate, then click on the chart near the price scale to set an alert. |
| 📐 | **Measure** | Measure price/time delta | Click and drag from one point to another to see the difference. |
| T | **Text** | Add text watermark | Click to add a text label (currently adds "Watermark"). |

### Managing Drawings
- **Select**: Click on any drawing to select it. It will appear thicker/highlighted.
- **Delete**: Press `Delete` or `Backspace` key to remove the selected drawing.
- **Clear All**: Click the trash can icon (🗑) at the bottom of the toolbar to remove all drawings.

- **Clear All**: Click the trash can icon (🗑) at the bottom of the toolbar to remove all drawings.

## 📑 Object Tree (Right Sidebar)
Access formatting and management tools via the **Right Sidebar** icon strip.

- **Layer Management**: Click the **Layers Icon** (top) to open the Object Tree.
  - **Drawings**: View, select, lock, or delete individual drawings.
  - **Indicators**: Manage active indicators (Settings, Visibility, Remove).
- **Collapsing**: Click the icon again or the Chevron (`>`) button to collapse the panel for a full-screen chart view.

## 📊 Indicators & Plugins
Access indicators and plugins via the **"📊 Indicators"** button in the top toolbar.

### Adding Indicators
1. Click **"📊 Indicators"**.
2. Browse the categories (Built-in, Primitives, Indicators).
3. Click on an item to add it to the chart.
   - **Built-in**: Standard indicators like SMA, EMA, RSI.
   - **Primitives**: Visual tools like Tooltips, Volume Profile.
   - **Plugin Indicators**: Custom indicators like Weighted Close, Momentum.

### Managing Active Indicators
- Active indicators are listed in the **Legend** (top-left corner).
- Click the **"×"** next to an indicator name in the legend to remove it.

## 🎮 Chart Controls
- **Ticker**: Switch between `ES1` and `NQ1` using the buttons in the top-left.
- **Timeframe**: Select timeframes (1m, 5m, 15m, 1h, 4h, 1D) from the top toolbar.
- **Date Navigation**: Use the "Go to" button to jump to a specific date.
- **Strategy**: Toggle the "Strategy" button to show/hide strategy signals (if available).
- **Timezone**: Switch between Exchange and Local timezones.

## ⏪ Replay Mode
Simulate live market conditions by playing back historical data.

- **Start Replay**: Click the `Replay` button in the top toolbar to open the menu.
  - **Select Bar**: Click anywhere on the chart start playback from that candle.
  - **Select Date**: Choose a specific start date from the calendar.
  - **First Available**: Start from the beginning of the loaded data.
- **Playback Controls**:
  - **Play/Pause**: Toggle automatic playback.
  - **Step**: Advance one candle at a time.
  - **Speed**: Adjust the playback speed (1x to 10x).
  - **Stop**: Exit replay mode and return to the live chart.

## ⌨️ Keyboard Shortcuts
- **Delete / Backspace**: Delete selected drawing.
- **Ctrl + Z**: Undo (Not yet implemented).
- **Ctrl + Y**: Redo (Not yet implemented).

## 🧩 Plugins
The application supports a modular plugin system.
- **Primitives**: Attach directly to the chart series (e.g., Tooltips).
- **Indicators**: Create new data series (e.g., Moving Averages).
- **Series Types**: Change the main chart visualization (e.g., Rounded Candles).

For more technical details on plugins, refer to `docs/PLUGIN_INTEGRATION_GUIDE.md`.
