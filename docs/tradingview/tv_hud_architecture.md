# TradingView & Standalone Desktop HUD Architecture & User Guide

## Overview

The **Modular HUD Architecture** provides a unified system for live Heads-Up Display (HUD) overlays. It supports **two concurrent delivery modes**:

1. **In-Chart TradingView HUD**: Injected directly into TradingView Desktop via Chrome DevTools Protocol (CDP port 9222) with zero DOM interference or React conflicts.
2. **Independent Floating Desktop Widget**: A standalone, frameless, Always-on-Top desktop window (via Edge/Chrome App Mode on port 8635) that stays visible across all monitors, applications (NinjaTrader, TradingView, Discord, Bookmap), and restarts.

---

## Directory Structure & Files

```
scripts/tradingview/
├── huds/                               # Modular HUD Plugins
│   ├── account_pnl.js                  # Fleet P&L & Copy-Trading Sync Monitor (v2.0)
│   ├── financialjuice.js               # FinancialJuice Live Squawk, News, Calendar & Flow
│   ├── nt8_positions.js                # NT8 Live Positions & P&L Card
│   └── template_hud.js                 # Boilerplate template for new HUDs
├── start_pnl_streamer.ps1              # High-frequency (250ms) P&L & Copier Streamer controller
├── launch_pnl_widget.ps1               # 1-Click Floating Desktop Widget Launcher (Edge App Mode)
├── pnl_widget_server.js                # Standalone HTTP/WebSocket server (port 8635)
├── tv_pnl_streamer.js                  # CDP real-time data pump engine
├── tv_hud_manager.ps1                  # Unified PowerShell CLI Manager
├── tv_hud_manager.py                   # Python CLI & Importable Module
├── tv_hud_manager.js                   # Node.js CDP Engine & Core Bridge
└── inject_financialjuice_hud.ps1       # 1-Click FinancialJuice Shortcut Script
```

---

## Quick Start Commands

### 1. In-Chart TradingView HUD Mode (`tv_hud_manager.ps1` & `start_pnl_streamer.ps1`)

#### Start Real-Time P&L & Copier Streamer into TradingView (250ms refresh):
```powershell
# Starts high-speed background streamer and injects account_pnl HUD into TradingView
.\scripts\tradingview\start_pnl_streamer.ps1 -Background

# Or run in foreground console to view live tick telemetry:
.\scripts\tradingview\start_pnl_streamer.ps1
```

#### Stop background streamer:
```powershell
.\scripts\tradingview\start_pnl_streamer.ps1 -Stop
```

#### Inject FinancialJuice News & Voice Squawk:
```powershell
.\scripts\tradingview\inject_financialjuice_hud.ps1
```

---

### 2. Independent Floating Desktop Widget Mode (`launch_pnl_widget.ps1`)

#### Launch Standalone Floating Desktop Window (Always-on-Top / Multi-Monitor):
```powershell
# Launches native frameless window (independent of TradingView):
.\scripts\tradingview\launch_pnl_widget.ps1
```

#### Stop standalone widget server:
```powershell
.\scripts\tradingview\launch_pnl_widget.ps1 -Stop
```

---

## Fleet P&L & Copy-Trading Verification Engine

### 1. Copy Trading Sync Grid
* **Leader vs. Follower Expected / Actual Matching**: Automatically pairs the leader account (`Sim101`) with all follower accounts (`Sim-ORB`, `SimCopy2`, Prop accounts).
* **Sync Status Badges**:
  * `🟢 SYNCED`: Follower matches leader's exact target quantity and side.
  * `⏳ IN-FLIGHT`: Order replication in progress.
  * `🚨 DESYNC`: Follower order failed/rejected while Leader has an open position.
  * `🔒 QUARANTINE`: RiskGuard protection engaged.
* **Orphan Position Alert**: When the Leader closes/flattens, continuously verifies that all followers reach `Flat (0)`. Flags any stuck positions with an alert banner.
* **Emergency Panic Flatten**: Direct one-click execution to `/api/emergency-flatten` with a 2-click safety confirmation.

### 2. Fleet P&L Metrics
* **Total Fleet Net Liquidation**: Sum of cash/net liq across all active accounts.
* **Open Unrealized Floating P&L**: Live instantaneous profit/loss ticks.
* **Realized Today**: Daily closed P&L across all accounts.
* **Fleet Exposure**: Aggregate active contracts (e.g. `+2 NQ, -1 ES`).
