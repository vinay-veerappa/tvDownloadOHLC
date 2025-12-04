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
