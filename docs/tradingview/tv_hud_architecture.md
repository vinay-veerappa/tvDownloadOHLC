# TradingView Desktop — Modular HUD Architecture & User Guide

## Overview

The **TradingView HUD Architecture** provides a modular, plug-and-play system for injecting and managing live Heads-Up Display (HUD) overlays directly inside TradingView Desktop via Chrome DevTools Protocol (CDP).

Each HUD is a self-contained module with its own DOM lifecycle, scoped styles, draggable headers, transparency controls, and collapse/minimize states. Overlays live outside TradingView's internal React component tree (`document.body` fixed coordinate space) to guarantee zero interference with chart rendering or symbol switching.

---

## Directory Structure & Organization

```
scripts/tradingview/
├── huds/                               # Modular HUD Plugins
│   ├── financialjuice.js               # FinancialJuice Live Squawk, News, Calendar & Flow
│   ├── nt8_positions.js                # NT8 Live Positions & P&L Card
│   └── template_hud.js                 # Boilerplate template for new HUDs
├── tv_hud_manager.ps1                  # Unified PowerShell CLI Manager
├── tv_hud_manager.py                   # Python CLI & Importable Module
├── tv_hud_manager.js                   # Node.js CDP Engine & Core Bridge
└── inject_financialjuice_hud.ps1       # 1-Click FinancialJuice Shortcut Script
```

---

## Quick Start Commands

### 1. PowerShell CLI (`tv_hud_manager.ps1`)

#### List all available & currently active HUDs:
```powershell
.\scripts\tradingview\tv_hud_manager.ps1 -Action list
```

#### Inject FinancialJuice HUD:
```powershell
.\scripts\tradingview\tv_hud_manager.ps1 -HUD financialjuice
# Or use the 1-click shortcut:
.\scripts\tradingview\inject_financialjuice_hud.ps1
```

#### Toggle FinancialJuice HUD on/off:
```powershell
.\scripts\tradingview\inject_financialjuice_hud.ps1 -Action toggle
```

#### Inject NT8 Positions HUD:
```powershell
.\scripts\tradingview\tv_hud_manager.ps1 -HUD nt8_positions
```

#### Remove a specific HUD:
```powershell
.\scripts\tradingview\tv_hud_manager.ps1 -HUD financialjuice -Action remove
```

#### Remove ALL HUDs (clean slate):
```powershell
.\scripts\tradingview\tv_hud_manager.ps1 -Action clear
```

---

### 2. Python CLI (`tv_hud_manager.py`)

```bash
# List HUDs
python scripts/tradingview/tv_hud_manager.py list

# Inject
python scripts/tradingview/tv_hud_manager.py inject financialjuice

# Toggle
python scripts/tradingview/tv_hud_manager.py toggle financialjuice

# Clear all
python scripts/tradingview/tv_hud_manager.py clear
```

---

## FinancialJuice HUD Features

1. **Live Squawk Headlines**: Live breaking news feed embedded directly in-chart (`https://feed.financialjuice.com/widgets/headlines.aspx`).
2. **Real-time Spoken Voice Squawk**: Dedicated audio player bar (`https://feed.financialjuice.com/voice-player.aspx`) with volume and stream controls. Can be toggled on/off with the **🔊 Squawk** button.
3. **Economic Calendar (EcoCal)**: Filtered high-impact macroeconomic event calendar.
4. **TickStrike Flow**: Live institutional tick and order flow sentiment widget.
5. **Draggable & Resizable**: Drag from the title bar to place anywhere across multiple monitors / panes; resize from the bottom-right grip.
6. **Transparency Toggle (`🌓`)**: Cycles opacity between **96%**, **85%**, and **70%** so underlying price action remains visible.
7. **Minimize (`🗕`)**: Collapses the HUD into a compact 38px title pill.

---

## Adding a New Custom HUD Module

To create a new HUD:
1. Copy `scripts/tradingview/huds/template_hud.js` to `scripts/tradingview/huds/my_new_hud.js`.
2. Define:
   - `id`: Unique identifier (e.g. `gex_zones`, `order_flow`).
   - `domId`: HTML element ID (e.g. `ws-gex-panel`).
   - `styleId`: Scoped CSS ID (e.g. `ws-gex-style`).
   - `getCss(options)`: Styling string.
   - `getHtml(options)`: HTML structure.
   - `initScript`: Client-side JavaScript for event listeners, drag handlers, and updates.
3. The HUD Manager automatically discovers and exposes it in `-Action list` and `inject`.
