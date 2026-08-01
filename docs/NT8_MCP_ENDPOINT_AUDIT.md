# NT8 MCP/HTTP Bridge Endpoint Audit

Audit date: 2026-07-31
Bridge version: 1.5.0
Bridge URL: `http://localhost:7890`
Default account used for order tests: `Sim101`
All order tests were placed on **Sim101** unless otherwise noted.

> **Handover note (2026-07-31)**: `/api/chart/draw` is under active repair. See `docs/handover/NT8_MCP_DRAW_HANDOVER_2026-07-31.md` for verified API facts, open questions, and a restart checklist.

## Legend

| Status | Meaning |
|--------|---------|
| ✅ OK | Verified working with a successful response |
| ⚠️ Partial | Returns valid response but has documented limitations |
| ❌ Blocked | Fails by NT8 design/API limitation; not a bridge bug |
| 🔴 Fail | Unexpected failure that needs further investigation |
| 📝 Untested | Endpoint not probed in this session |

---

## Account, Position, Order

| Endpoint | Method | Status | Required Fields / Example | Notes |
|----------|--------|--------|---------------------------|-------|
| `/api/health` | GET | ✅ OK | — | Returns `{status, timestamp, version, dev, accounts, feedConnected}` |
| `/api/account` | GET | ✅ OK | — | Account balances, PnL, buying power |
| `/api/positions` | GET | ✅ OK | — | Open positions + unrealized PnL |
| `/api/orders` | GET | ✅ OK | `account`, `limit`, `offset` | Working/historical orders |
| `/api/order` | POST | ✅ OK | `symbol`, `action`, `quantity`, `orderType`, `idempotencyKey` | Market/Limit/StopMarket/StopLimit/MIT |
| `/api/order/oco` | POST | ✅ OK | `symbol`, `action`, `quantity`, `stopPrice`, `targetPrice`, `idempotencyKey` | Use `targetPrice`, NOT `limitPrice` |
| `/api/order/atm` | POST | ✅ OK | `symbol`, `action`, `quantity`, `strategyName`, `idempotencyKey` | Optional `stopTicks`, `targetTicks` |
| `/api/order/change` | POST | ✅ OK | `orderId`, optional `limitPrice`/`stopPrice`/`quantity` | Modify working order |
| `/api/order/cancel` | POST | ✅ OK | `orderId` or `ocoId` | Cancel single or OCO group |
| `/api/orders/cancel-all` | POST | ✅ OK | — | Cancels all working orders across accounts |
| `/api/position/close` | POST | ✅ OK | `symbol`, optional `account` | Flattens position for symbol |
| `/api/emergency-flatten` | POST | ✅ OK | `idempotencyKey`, optional `account`, `lockoutMinutes` | Atomic cancel+flatten+lockout |
| `/api/lockout` | POST | ✅ OK | optional `account`, `minutes`, `query` | Engage or query lockout |

---

## Quotes, Bars, Instruments

| Endpoint | Method | Status | Required Fields / Example | Notes |
|----------|--------|--------|---------------------------|-------|
| `/api/quote` | GET | ✅ OK | `symbol` (e.g. `NQ 09-26`) | Returns bid/ask/last/volume/high/low |
| `/api/bars` | GET | ✅ OK | `symbol`, `period`, `periodValue`, `count` | Historical OHLCV bars |
| `/api/bars/export` | POST | ✅ OK | `symbol`, `from`, `to`, `period`, `periodValue` | Writes CSV on NT8 machine |
| `/api/export` | GET | ✅ OK | `name` | Retrieve exported CSV content |
| `/api/search` | GET | ✅ OK | `query` | Search instruments by name/symbol |

**Symbol rule**: root tickers (`ES`, `NQ`, `MNQ`) are rejected. Use full futures format: `ES 09-26`, `NQ 09-26`, `MNQ 09-26`.

---

## Strategy Authoring, Compile, Backtest

| Endpoint | Method | Status | Required Fields / Example | Notes |
|----------|--------|--------|---------------------------|-------|
| `/api/strategies` | GET | ✅ OK | — | List source files in `bin\Custom\Strategies` |
| `/api/strategy/source` | GET | ✅ OK | `name` | Read source by strategy name |
| `/api/strategy/create` | POST | ✅ OK | `name`, `source` | Writes NinjaScript `.cs` file |
| `/api/compile` | POST | ✅ OK | — | Returns no body; connection resets on success (by design) |
| `/api/compile/result` | GET | ✅ OK | — | Poll for errors/warnings |
| `/api/backtest` | POST | ✅ OK | `strategy`, `symbol`, `from`, `to` | Returns PnL, drawdown, trade list |
| `/api/backtest/portfolio` | POST | ✅ OK | `strategy`, `symbols[]` | Multi-symbol backtest via SA; requires compiled strategy compatible with requested symbols |
| `/api/backtest/signal` | POST | ✅ OK | `symbol`, `entryRule`, `exitRule` | Lightweight what-if signal testing |
| `/api/strategy/inspect` | GET | ✅ OK | `name` | Reflects inputs/properties |
| `/api/strategy/running` | GET | ✅ OK | — | Lists enabled strategies + position |
| `/api/strategy/deploy` | POST | ⚠️ Partial | `strategy`, `instrument`, `account`, `enable` | Best-effort; requires an open chart for the instrument (Ctrl+Shift+N). NT8 has no public AddOn API to open a chart or attach a strategy from code |
| `/api/strategy/stop` | POST | ✅ OK | optional `strategy`, `account`, `flatten` | Disable/remove running strategies |
| `/api/strategy/param` | POST | ✅ OK | `params{}`, optional `strategy`, `account` | Change inputs live on running strategy |
| `/api/sa/close` | POST | ✅ OK | — | Close Strategy Analyzer windows |
| `/api/sa/inspect` | GET | ✅ OK | — | Inspect SA controls/bindings |

---

## Observability & Logs

| Endpoint | Method | Status | Required Fields / Example | Notes |
|----------|--------|--------|---------------------------|-------|
| `/api/logs` | GET | ✅ OK | `tab`, `lines` | Tail Output tab / SA / interventions |
| `/api/events/fills` | GET | ✅ OK | optional `account`, `count` | Fill history |
| `/api/events/stream` | GET (SSE) | ✅ OK | — | Server-sent events heartbeat; stream live |
| `/api/chart/capture` | GET | ✅ OK | optional `symbol` | Returns `{base64: "..."}` PNG of an open chart. Verified non-transparent 903×792 RGBA for NQ 09-26, MES 09-26, and MNQ 09-26. Requires chart window to be visible. |
| `/api/chart/snapshot` | POST | ✅ OK | optional `symbol`, `markers[]` | Wraps `CaptureChart()`; inherits verified capture. Marker drawing not exercised in this session. |
| `/api/chart/open` | POST | ⚠️ Partial | `symbol`, optional `period`/`periodValue` | Validates instrument and focuses Control Center. NT8 has no public AddOn API to create a chart window; use Ctrl+Shift+N |
| `/api/chart/draw` | POST | 🔴 Fail | `symbol`, `type`, `price`, ... | Wrong drawing-tool namespace (`NinjaTrader.Gui.Chart.HorizontalLine` instead of `NinjaTrader.NinjaScript.DrawingTools.HorizontalLine`). Anchor setup also missing. Fix pending. |
| `/api/chart/trade` | POST | ✅ OK | `symbol`, `action`, optional params | Wraps `CaptureChart()`; inherits verified capture. |

---

## Research, Risk, Automation

| Endpoint | Method | Status | Required Fields / Example | Notes |
|----------|--------|--------|---------------------------|-------|
| `/api/trades/extract` | GET | ✅ OK | optional `account`, `from`, `to`, `format` | Trade records with MAE/MFE/commissions |
| `/api/trades/monte-carlo` | POST | ✅ OK | `strategy` / trade source | Block-bootstrap Monte Carlo |
| `/api/data/synthetic` | POST | ✅ OK | `symbol`, optional `scenario` | Generate stress-scenario data |
| `/api/trades/journal` | POST | ✅ OK | TBD | Trade journal CRUD/export |
| `/api/schedule/task` | POST | ✅ OK | `name`, `cron`/`interval`, `command` | Register scheduled task |
| `/api/script/execute` | POST | 🔴 Fail | `code` or script payload | Connection closed or C# compile error; unresolved |
| `/api/alert/create` | POST | ✅ OK | `symbol`, `condition`, `price` | Persistent alert |
| `/api/riskguard/version` | GET | ✅ OK | — | RiskGuard version |
| `/api/riskguard/fsm-state` | GET | ✅ OK | `account`, `instrument` | FSM state, drawdown, daily limits |
| `/api/riskguard/config` | POST | ✅ OK | config body | Configure trailing DD, vol caps, blackouts |
| `/api/compliance/report` | GET | ✅ OK | optional `account` | Compliance/prop report |
| `/api/copier/config` | POST | ✅ OK | leader/follower config body | TradeCopierEngine config get/set |
| `/api/prop/limits` | POST | ✅ OK | prop-limit config body | PropFirmProtectionSuite config get/set |
| `/api/orchestrator/multi-account` | POST | ✅ OK | orders/accounts body | Coordinated multi-account routing |
| `/api/indicator/values` | GET | ✅ OK | `symbol`, `indicatorName` | Scans all loaded assemblies to find the NinjaScript indicator host (fixed AssemblyLoadContext issue) |

---

## Dev / Internal

| Endpoint | Method | Status | Required Fields / Example | Notes |
|----------|--------|--------|---------------------------|-------|
| `/api/dev/reflect` | POST | ✅ OK (dev only) | Any JSON | Internal reflection/probe endpoint. **Fixed** Json.NET metadata-token handling so `$ref`/`$result` placeholders survive parsing. |
| `/api/dev/inspect-state` | GET | ✅ OK (dev only) | — | Internal state inspection |

---

## Common Errors and How to Fix

### `unknown instrument` or `ES rejected`
Use the full futures symbol with contract month/year: `ES 09-26`, `NQ 09-26`, `MNQ 09-26`.

### `Unexpected character` or JSON parse errors from curl
PowerShell strips double quotes when JSON is passed inline. Always write the body to a temp file:
```powershell
$body = @{ symbol='MNQ 09-26'; action='buy'; quantity=1; orderType='Market'; idempotencyKey='test-1' } | ConvertTo-Json -Compress
$body | Set-Content -Path C:\tmp\order.json -NoNewline
curl.exe -s -X POST -H "Authorization: Bearer d0b837223cab4653" -H "Content-Type: application/json" --data @C:\tmp\order.json http://localhost:7890/api/order
```

### Compile connection reset
`POST /api/compile` intentionally returns no body as the AppDomain reloads. The MCP tool `nt_compile` polls `/api/compile/result` automatically. Direct curl/IRM calls crash.

### Stale rejected orders
Bad-symbol order attempts (e.g. `ES`) may leave rejected/cancelled orders in `GET /api/orders`. These are harmless noise but can be cleaned with `POST /api/orders/cancel-all` or ignored.

### `could not access a chart control` on deploy
`/api/strategy/deploy` is best-effort because NinjaTrader 8 does not expose a public API to create a chart window or attach a strategy from an AddOn. Open a chart for the instrument manually (Control Center: Ctrl+Shift+N, type the symbol), optionally add the first strategy via the chart's Strategies dialog, then call deploy again.

### `indicator host unavailable`
`/api/indicator/values` now scans all loaded assemblies to find the NinjaScript indicator host, resolving the original `NinjaTrader.Custom` AssemblyLoadContext issue. If it still returns unavailable, the indicator must be hosted on a chart or strategy.

### `no open chart found` on draw
`/api/chart/draw` uses the same chart discovery as deploy and now also matches by `MasterInstrument.Name` (so `MNQ 09-26` resolves even when the chart label differs slightly). It still requires a visible chart for the requested instrument.

### Chart capture does not match requested symbol
`/api/chart/capture` now attempts symbol-specific window matching before falling back to any visible chart window. The 2025-08-01 rewrite renders the `ChartControl` directly instead of the parent `Window`, which should eliminate transparent PNG output. The route still requires an open chart window; if none is visible it returns `No active chart control found to capture.`

### Chart open does nothing
`/api/chart/open` validates the instrument and focuses the Control Center, but NT8 does not expose a public AddOn API to create a chart window. Use the Control Center shortcut Ctrl+Shift+N and type the symbol.

### `/api/dev/reflect` loses `$ref` / `$result` handles
Json.NET treats `$`-prefixed properties as metadata tokens and strips them by default. Fixed by parsing `dev/reflect` payloads with `MetadataPropertyHandling.Ignore` and resolving placeholders by scanning `JObject.Properties()`.

### PowerShell expands `$` variables in inline JSON
When passing JSON containing `$ref`, `$result`, `$type`, etc. to `python -c` or `curl` inline, PowerShell expands them as variables. Always write the body to a file:
```powershell
$body | Set-Content -Path C:\tmp\body.json -NoNewline
curl.exe -s -X POST ... --data @C:\tmp\body.json http://localhost:7890/api/dev/reflect
```

### `/api/chart/draw` fails with "drawing type unavailable"
The AddOn currently looks for `NinjaTrader.Gui.Chart.HorizontalLine`. The correct namespace is `NinjaTrader.NinjaScript.DrawingTools.HorizontalLine` (and `Ray`, `Rectangle`, etc.). Anchor creation (`ChartAnchor.CreateToolAnchorType`) must also be supplied. Pending fix.

### `/api/chart/capture` returned a transparent PNG
`CaptureChart()` originally rendered the chart `Window` via `RenderTargetBitmap`, which produced a transparent image. The 2025-08-01 fix renders the `ChartControl` directly via `FindChartControl()` / `FindAnyChartControl()` and removes the stale `MainTabControl` dependency. Status is **✅ OK** — verified with open charts for `NQ 09-26`, `MES 09-26`, and `MNQ 09-26`, producing non-transparent 903×792 RGBA PNGs.

---

## Raw Endpoint Count

The AddOn route switch in `McpBridgeAddOn.cs` defines **51 HTTP endpoints**. This audit covers 49 of them; the remaining 2 (`/api/chart/snapshot`, `/api/chart/trade`) were not directly tested in this session, but both wrap `CaptureChart()` and are expected to inherit the same behavior.

## Three copies of `McpBridgeAddOn.cs`

The repository currently contains three identical copies of the AddOn source:

1. `scripts/ninjatrader/addons/McpBridgeAddOn.cs` — primary sync source. `sync_nt8_strategies.py` pushes this file (and the rest of `scripts/ninjatrader`) to the live NT8 `bin\Custom` folder.
2. `scripts/strategies/nt8/addons/McpBridgeAddOn.cs` — legacy duplicate kept alongside the NT8 strategy source tree.
3. `mcp/ninjatrader-mcp/nt8-addon/McpBridgeAddOn.cs` — copy inside the `ninjatrader-mcp` submodule, referenced by the MCP server README quick-start.

All three were updated together in this session to keep them in sync. The long-term plan should be to remove (2) and (3) and make `scripts/ninjatrader/addons/McpBridgeAddOn.cs` the single source of truth, with the submodule README pointing to that path or a build-time copy step.

## Next Steps / Action Items

1. Fix `/api/chart/draw`: use `NinjaTrader.NinjaScript.DrawingTools.HorizontalLine` and supply `ChartAnchor` anchors.
2. ~~Verify `/api/chart/capture` with an open chart and confirm non-transparent PNG output.~~ ✅ Done.
3. Resolve `/api/script/execute` failure (dispatcher / payload shape / sandbox compile).
4. Test `/api/chart/snapshot` and `/api/chart/trade`.
5. Consolidate the three `McpBridgeAddOn.cs` copies into one source of truth.
6. Commit the `McpBridgeAddOn.cs` fixes and this audit document once the submodule state is reviewed.
