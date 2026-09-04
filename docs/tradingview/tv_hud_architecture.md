# TradingView & Standalone Desktop HUD Architecture & User Guide

## Overview

The **Modular HUD Architecture** provides a unified system for live Heads-Up Display (HUD) overlays. It supports **two concurrent delivery modes**:

1. **In-Chart TradingView HUD**: Injected directly into TradingView Desktop via Chrome DevTools Protocol (CDP port 9222) with zero DOM interference or React conflicts. Real-time telemetry is pushed by `trading_daemon.exe`.
2. **Independent Floating Desktop Widgets (Pure Native Rust)**: Standalone, Always-on-Top native desktop applications that stay visible across all monitors and applications without requiring external browser processes:
   - **Fleet P&L Widget (`pnl_widget_gdi.exe`)**: Pure Win32 GDI desktop app (~18MB RAM) with full 3-tab layout (P&L | Copier | Risk), order entry, ATM strategies, full-digit formatting, and dynamic Net Liq tracking.
   - **FinancialJuice Widget (`fj_widget.exe`)**: Native Tao window with embedded Microsoft WebView2 (~24MB RAM) featuring audio squawk autoplay, dark-themed calendar proxying on port 8636, and live SignalR headlines.

---

## Directory Structure & Files

```
crates/
├── trading_daemon/                     # Rust backend daemon (port 8635, CDP pump, lockout sweep)
├── pnl_widget_gdi/                     # Pure native Win32 GDI Fleet P&L desktop widget
├── fj_widget/                          # Pure native Rust FinancialJuice widget (Tao + WebView2)
├── nt8_parity_core/                    # PyO3 parity execution engine (378x speedup)
└── broker_sentinel/                    # Independent broker killswitch

launch/widgets/
├── start_pnl_widget.bat                # 1-Click launcher for pnl_widget_gdi.exe (starts daemon if needed)
├── stop_pnl_widget.bat                 # Clean shutdown for P&L widget & daemon
├── start_fj_widget.bat                 # 1-Click launcher for fj_widget.exe (decoupled WMI launch)
└── stop_fj_widget.bat                  # Clean shutdown for FinancialJuice widget

scripts/tradingview/
├── huds/                               # Modular HUD Plugins (for in-chart TV injection)
│   ├── account_pnl.js                  # Fleet P&L & Copy-Trading Sync Monitor (v2.0)
│   ├── financialjuice.js               # FinancialJuice Live Squawk, News, Calendar & Flow
│   ├── nt8_positions.js                # NT8 Live Positions & P&L Card
│   └── template_hud.js                 # Boilerplate template for new HUDs
├── tv_hud_manager.ps1                  # Unified PowerShell CLI Manager
├── tv_hud_manager.py                   # Python CLI & Importable Module
└── inject_financialjuice_hud.ps1       # 1-Click FinancialJuice In-Chart Shortcut Script
```

---

## Quick Start Commands

### 1. Independent Floating Desktop Widgets (Recommended)

#### Launch Fleet P&L Native GDI Widget (Always-on-Top / Multi-Monitor):
```powershell
.\launch\widgets\start_pnl_widget.bat
```

#### Launch FinancialJuice Squawk & News Native Widget:
```powershell
.\launch\widgets\start_fj_widget.bat
```

#### Stop Desktop Widgets:
```powershell
.\launch\widgets\stop_pnl_widget.bat
.\launch\widgets\stop_fj_widget.bat
```

---

### 2. In-Chart TradingView HUD Mode (CDP Injection)

#### Push Live Fleet P&L into TradingView Desktop (Port 9222):
Handled automatically by the background `trading_daemon.exe` on port 8635. To supervise/start:
```powershell
.\launch\start_trading_daemon.bat
```

#### Inject FinancialJuice In-Chart HUD into TradingView:
```powershell
.\scripts\tradingview\inject_financialjuice_hud.ps1
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

---

## Order Ticket (RiskGuard-Integrated) — shipped 2026-09-01

Lives in the top bar of the P&L widget / HUD (shared module `account_pnl.js`).
Order submission works in the **standalone widget only** — TV's page sandbox blocks
fetch to `localhost:8635`, so the in-chart HUD shows the ticket bar with
non-functional B/S buttons (by design, see TV_INJECTION_API.md §10.2).

### Config-driven guard enforcement at entry
The RiskGuard config file (`Documents\NinjaTrader 8\RiskGuard\config.json`) is the
single source of truth, polled every 30s via `GET /api/guard/config`:
* **Symbol dropdown** is generated from `AllowedInstruments` — blocked full-size
  roots (ES/NQ/YM/RTY/CL/GC when configured so) never appear, so they cannot even
  be selected rather than being rejected after submission.
* **Qty cap** = `min(InstrumentLimits[root], Sizing.MaxContractsPerAccount)`;
  the input clamps and shows `max N`.
* **GUARD chip** shows the enforcement mode (`SHADOW` orange / `LIVE` green).

### Bracket entry
* Per-account **B / S** buttons fire `POST /api/order/atm` (proxied to the NT8
  bridge, idempotency key per click, busy state survives the 200ms re-render).
* ATM strategy selectable (AUTO + FixedTicks, AtrAdaptive, SwingPoint,
  DrawdownShield, ScaledRunner, VolatilityScaled, SessionAdaptive, KellyOptimal);
  SL/TP in ticks (default 40/80). Response bracket (`bracketId`, stop/target) is
  shown in the status line.
* **Lockout sweep**: `/api/lockouts` polls RiskGuard every 2.5s (30-account cap,
  10s cache). Locked rows get a `🔒LOCKED` badge and disabled B/S buttons.

### Rendering (stable-row pipeline, fixed 2026-09-02)
The table rows are **created once per account and reused**; the 200ms tick
updates cell values in place. Click events are **delegated at the tbody level**
(one listener, survives re-renders). Never rebuild DOM nodes a user can press —
an earlier full-`innerHTML`-every-200ms rebuild silently ate clicks (mousedown
and mouseup landing on different element generations) and strobed the busy
animation. Full rationale: TV_INJECTION_API.md §10.3.

### Panic flatten
* Single click (no confirm) → `POST /api/emergency-flatten` for all accounts.
* **⚠️ Side effect to know**: every flatten writes a 60-minute bridge-local lockout
  (`_lockoutExpiry`) for every account it touched. After a panic, the whole fleet
  reads `🔒LOCKED` in the widget while the RiskGuard window shows clean — the two
  readers differ (window = enforcer only; API = enforcer + bridge-local + state.json
  restore). Clear a false lockout with
  `POST /api/lockout {action:'unlock', account:X}` per account. Full semantics:
  TV_INJECTION_API.md §10.2.
