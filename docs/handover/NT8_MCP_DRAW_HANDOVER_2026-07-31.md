# NT8 MCP Bridge `/api/chart/draw` — Handover (2026-07-31)

## Session outcome
First pass (earlier today) made code changes but could not verify them because the
AddOn assembly was assumed not to be reloading — that turned out to be a red herring
(the live AddOn had since advanced to `1.5.1-draw-fix`; the "stale `1.5.0`" claim was
wrong). Second pass **confirmed the real root cause** of the chart-discovery failure
in-process via `/api/dev/reflect`, **applied the fix** to the source (version →
`1.5.2-chart-discovery`), and synced it to the NT8 live folder. **Pending: live
verification** — NT8 was restarted to load the new source but the bridge port had not
returned when the session paused (NT8 maintenance window).

## ROOT CAUSE CONFIRMED (2026-07-31, second pass) — multi-thread dispatcher bug
The `/api/chart/list` "appDispatcher.Invoke timed out / chartWindowCount=0" failure has a
**confirmed** root cause, verified in-process via `/api/dev/reflect`:

1. **NT8 runs each Chart window on its own dedicated UI thread.** Probed live:
   - `Globals.AllWindows` has 5 windows, including **2 `NinjaTrader.Gui.Chart.Chart`** windows.
   - Chart window #1 dispatcher = thread **18**; Chart window #2 dispatcher = thread **19**.
   - `Application.Current.Dispatcher` = thread **1** (the main NT8 / Control Center thread).
   These are *different* threads. Reading `win.Title` from thread 1 throws:
   `"The calling thread cannot access this object because a different thread owns it."`

2. **The `appDispatcher.Invoke(..., TimeSpan)` timeout overload is the proximate bug.**
   `ListOpenCharts` / `FindChartControl` used `appDispatcher.Invoke(action,
   DispatcherPriority.Normal|Background, TimeSpan.FromSeconds(5/10/30))`.
   The 3-arg overload with a `TimeSpan` **returns without running the delegate** if the
   dispatcher is momentarily busy, so `enumRan` stays `false` → false "timed out / 0 charts".
   Proof: `/api/dev/reflect` with `"ui":true` uses the no-timeout `disp.Invoke((Action))`
   overload and completes the *same* enumeration in **0.02-0.03s**. Thread 1 is NOT busy.

**FIX APPLIED** (source `scripts/ninjatrader/addons/McpBridgeAddOn.cs`, version → `1.5.2-chart-discovery`):
- `ListOpenCharts`: replaced the timed `appDispatcher.Invoke(enumAction, priority, TimeSpan)`
  with the no-timeout `appDispatcher.Invoke((Action)(enumAction))`; added elapsed-ms reporting.
- `FindChartControl`: both invokes (the `appDispatcher` enumeration and the per-window
  `winDispatcher` inspection) switched from `Invoke(action, DispatcherPriority.Background,
  TimeSpan)` to the no-timeout `Invoke((Action))` overload.
- Per-window property reads (`Title`, `Instrument`, visual tree) already marshal to the
  chart window's OWN dispatcher (`winDispatcher`, thread 18/19) — correct. Only the
  timeout overload was wrong.
- Bumped `Version` to `1.5.2-chart-discovery` as the reload marker.
- File synced to the NT8 live folder (`[SYNCED] McpBridgeAddOn.cs content differed`).
- **Pending: live verification.** NT8 was restarted to load the new source, but the bridge
  port (7890) had not come back up when the session paused (NT8 maintenance window).
  When NT8 returns: confirm `/api/health` version = `1.5.2-chart-discovery`, then
  `/api/chart/list` should return the 2 open charts (threads 18/19).

### Probe evidence (in-process, via `/api/dev/reflect` ui:true)
- `getStatic NinjaTrader.Core.Globals.AllWindows` → count=5, items=[ControlCenter,
  NinjaScriptOutput, Chart, Chart, EditorView] (returns in 0.03s).
- `get_Item(2)` / `get_Item(3)` → two `NinjaTrader.Gui.Chart.Chart` handles.
- `chart.Dispatcher.Thread.ManagedThreadId` = **18** (chart1) / **19** (chart2).
- `Application.Current.Dispatcher.Thread.ManagedThreadId` = **1**.
- `getProp win.Title` from thread 1 → `InvalidOperationException: cross-thread access`.

## Goal
Fix `/api/chart/draw` so it can draw price levels on an open NT8 chart via the MCP bridge, then validate which drawing tools beyond `HorizontalLine` are worth supporting. Chart discovery (`/api/chart/list` + `FindChartControl`) is the prerequisite and is what the fix below addresses.

## Drawing-tool facts (verified earlier via `/api/dev/reflect`)
- Correct drawing-tool namespace: `NinjaTrader.NinjaScript.DrawingTools`
- Types that exist and can be instantiated:
  - `HorizontalLine`
  - `VerticalLine`
  - `Ray`
  - `Rectangle`
  - `ChartAnchor`
  - `DrawingTool` (base)
- `ChartAnchor` has a parameterless constructor and writable `Price`, `Time`, `BarsAgo`, `DrawingTool`, `StartAnchor`.
- `ChartControl.ChartObjects` is a `Collection<ChartObjects>` (`IList`) — add drawing objects there.
- `NinjaTrader.Gui.Chart.HorizontalLine` does **not** exist.
- `Stroke` exists in `NinjaTrader.Gui` with `Brush`, `DashStyleHelper`, `Width`.
- `DashStyleHelper` has fields: `Solid`, `Dash`, `DashDot`, `DashDotDot`, `Dot`.
- `SolidColorBrush` / `Color.FromArgb` / `Brushes` exist in `System.Windows.Media`.
- `DrawingTool` base has static helpers `GetNewDrawingToolInstance(Type, templateName)` and `SetDrawingToolCommonValues`.
- `Draw.*` static helpers require a `NinjaScriptBase` owner — `AddOnBase` is not enough.
- Raw JSON integers arrive as `Int64`; indexers expect `System.Int32`, so use `{"type":"System.Int32","value":N}`.
- `dev/reflect` handles persist across requests (field, not per-batch); use `$result`/`result` indices (batch-scoped) to chain within one batch rather than `ref`/`$ref` handle ids.

## Earlier-pass changes still in the source
These were applied in the first pass and remain in `McpBridgeAddOn.cs` (now version `1.5.2-chart-discovery`):
- `LogStatic(string)` helper writing to the NT8 Output tab via `NinjaTrader.Code.Output.Process`.
- `GetAllWindows()` helper resolving `Globals.AllWindows` with `BindingFlags.Public|NonPublic|Static` and an `Application.Current.Windows` fallback.
- Hardened `InvokeM`/`FindMethod` overload resolution with type-assignability scoring.
- Plain aliases in `Coerce` (`ref`/`result`/`type`) so Python `json.dumps` cannot strip RPC handle keys.
- `DrawChartLevel` dispatches on the discovered ChartControl's own dispatcher and returns `ListOpenCharts()` as `availableCharts` on failure.

## What still needs to be solved (after live verification)
1. **Color/width API.** `HorizontalLine`/`Ray`/`Rectangle`/`VerticalLine` may not expose public `Stroke`/`Brush` properties. Styling may require protected/internal base-class fields (`_stroke`, `OutlineStroke`, `LineStroke`, etc.) or `DrawingTool.GetNewDrawingToolInstance` + template.
2. **Anchor wiring.** Direct `ChartAnchor` creation may need `SetDrawingToolCommonValues` and per-anchor `DrawingTool`/`StartAnchor` references to fully wire.
3. **Tool-specific anchor counts.**
   - `HorizontalLine` / `VerticalLine`: single anchor
   - `Ray`: two anchors (start + end)
   - `Rectangle`: two anchors (top-left / bottom-right)

## Recommended next-session plan
1. Wait for NT8 to finish its maintenance/startup window and for port 7890 to listen.
2. Call `/api/health`; confirm `version` is `"1.5.2-chart-discovery"` (proves the fixed AddOn loaded).
3. Call `/api/chart/list`; expect the two open charts (dispatcher threads 18/19).
4. If discovery works, test `/api/chart/draw` end-to-end with a real open chart.
5. If discovery still fails, use `/api/dev/reflect` (`ui:true`) to enumerate `Globals.AllWindows` in-process and log the exact exception.
6. Fix styling/anchoring once a line actually appears.
7. Update this handover with results.

## Recommended tool priority
1. **HorizontalLine** — primary use case (support/resistance levels). Must work first.
2. **Rectangle** — zones (overnight range, killzones, opening range). High value.
3. **Ray** — trendlines / directional bias. Medium value.
4. **VerticalLine** — time markers (macros, killzone open/close). Medium value.
5. **Future scope**: `Text`, `FibonacciRetracements`, `ArrowUp`/`ArrowDown`, `Triangle`.

## Source-of-truth files
- `scripts/ninjatrader/addons/McpBridgeAddOn.cs` — repo source-of-truth (current version `1.5.2-chart-discovery`). Sync to the NT8 live folder via `scripts/utils/sync_nt8_strategies.py` (`--verify` reports `[OK]`; the dispatcher fix was `[SYNCED]` this session).
- `C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\AddOns\McpBridgeAddOn.cs` — live AddOn (NT8 compiles from this on startup).
- `mcp/ninjatrader-mcp/nt8-addon/McpBridgeAddOn.cs` — submodule copy (keep in sync).
- `docs/NT8_MCP_ENDPOINT_AUDIT.md` — endpoint status.
- This handover: `docs/handover/NT8_MCP_DRAW_HANDOVER_2026-07-31.md`

## Terminal / API notes
- NT8 bridge port: **7890** (not 51328). Requires `Authorization: Bearer <mcp_token.txt>` + `Host: localhost` headers.
- Always use MCP `nt_compile`; never raw HTTP `/api/compile` (it resets the connection because the compile runs on the HTTP listener thread, not the WPF UI thread).
- Avoid `/api/script/execute` for ad-hoc probing; failed compiles can crash the HTTP listener.
- `/api/dev/reflect` handle references work with both `$ref`/`$result` and the Python-safe aliases `ref`/`result`.
- When calling from Python, never use `requests(..., json=...)` for DevReflect if keys start with `$`; build the raw string body instead.
- `/api/dev/reflect` with `"ui":true` runs the op batch on `Application.Current.Dispatcher` (thread 1) and is the reliable in-process probe — but it CANNOT safely touch Chart-window properties, which live on each chart's own dispatcher thread (18/19).

## Key blocker summary
> Root cause found and fix applied (`1.5.2-chart-discovery`). The only remaining blocker is **live verification**: NT8 must finish its maintenance/startup window and load the new AddOn. Do not edit more drawing logic until `/api/health` returns `"1.5.2-chart-discovery"` and `/api/chart/list` returns the open charts.
