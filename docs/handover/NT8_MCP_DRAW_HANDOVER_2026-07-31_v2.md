# NT8 MCP Bridge — Draw API Handover v2 (2026-07-31)

> **STATUS: RESOLVED** (2026-08-01). All issues from this handover have been fixed.
> See `nt8-mcp-bridge/docs/NT8_MCP_ENDPOINT_AUDIT.md` for the current comprehensive audit.
>
> This handover is kept for historical reference only. The original issues (C# 7 `out var`
> compile failure, WPF dispatcher deadlock, indexer-safe GetP/SetP, chart discovery
> returning 0 charts) are all resolved. The bridge version is now `1.5.2-chart-discovery`
> with 31 total fixes across 4 review passes.

## Original session outcome (superseded)
Fixed the compilation errors blocking AddOn reload. Chart discovery still returned 0
charts due to a WPF dispatcher deadlock — the HTTP listener thread is not the UI thread,
and `Dispatcher.Invoke` with a timeout could not complete while the UI thread was blocked.

## What was fixed this session

### 1. C# 7 `out var` syntax (root cause of compile failure)
NT8's NinjaScript compiler uses **C# 5**, which does not support `out var` (C# 7.0+).
The bridge's `/api/compile` uses Roslyn (C# 7+) so it reported 0 errors, but NT8's
internal NinjaScript Editor compile failed with cascading parse errors:
- "')' expected", "Class member declaration expected", etc. starting at line 197

**Fix**: Replaced all 16 `out var` occurrences with explicit C# 5 type declarations:
```csharp
// Before (C# 7):
if (_idempotencyCache.TryGetValue(idempotencyKey, out var record))
// After (C# 5):
IdempotencyRecord record;
if (_idempotencyCache.TryGetValue(idempotencyKey, out record))
```

Types used: `IdempotencyRecord`, `object` (for _handles), `double` (for daily dicts),
`int` (for exitReasons, TryParse), `DateTime` (for TryParse).

### 2. Embedded statement error (CS1023)
One `int xc;` declaration was placed under a braceless `if`:
```csharp
if (!string.IsNullOrWhiteSpace(xname))
    int xc;  // CS1023: embedded statement cannot be a declaration
```
**Fix**: Added braces `{ }` around the declaration + assignment.

### 3. Indexer-safe GetP/SetP
`GetP`/`SetP` called `PropertyInfo.GetValue(obj)` without checking if the property
is an indexer (which requires index arguments). This threw uncaught
`TargetParameterCountException`.

**Fix**: Added `p.GetIndexParameters().Length == 0` guard + try-catch in both
`GetP` and `SetP`.

### 4. Version bump
Bumped `Version` from `"1.5.0"` to `"1.5.1-draw-fix"` as a reload marker.
Health now confirms `version: "1.5.1-draw-fix"` — AddOn successfully reloads.

### 5. Visual-tree-only chart discovery
Removed `ActiveChartControl`/`tabControl` property access from
`CollectChartControlsFromWindow` (they throw cross-thread exceptions).
Now uses only `VisualTreeHelper` walk.

## Current blocker: WPF dispatcher deadlock

### Verified facts (via `/api/dev/reflect`)
- `Globals.AllWindows` returns **5 windows** including 2 `NinjaTrader.Gui.Chart.Chart`.
- Chart windows live on **thread 18** (different from the app dispatcher thread 1).
- `ActiveChartControl` throws: "The calling thread cannot access this object because
  a different thread owns it."
- The HTTP listener thread reports `ManagedThreadId = 1` via reflect, BUT
  `appDispatcher.CheckAccess()` returns **False** during `/api/chart/list` calls
  (the HTTP listener may use thread-pool threads that share the ID but aren't
  the WPF UI thread).

### The deadlock
`ListOpenCharts` calls `appDispatcher.Invoke(action, ..., timeout)`. If
`CheckAccess()` is False, `Invoke` blocks the HTTP listener thread waiting for the
UI dispatcher to pump. But the UI dispatcher may be blocked by the HTTP request
itself (if NT8 pumps HTTP on the UI thread), causing a **timeout** with
`enumRan = false`.

The `/api/chart/diag` output confirms: `appDispatcher.Invoke timed out`.

### Attempted fixes (did NOT resolve)
1. `CheckAccess()` → run inline (still timed out, CheckAccess returns False)
2. `DispatcherPriority.Send` (highest) → same timeout
3. Increased timeout to 30s → same timeout

## What still needs to be solved

1. **Chart discovery thread issue.** The HTTP listener thread cannot synchronously
   `Invoke` on the WPF UI dispatcher. Options:
   - Use `BeginInvoke` (async) + poll a `ManualResetEvent` with timeout
   - Run the chart discovery on a `Task.Run` that marshals to the UI dispatcher
     via `Dispatcher.CurrentDispatcher` (if the HTTP listener has its own dispatcher)
   - Check if NT8's HTTP listener runs on the UI thread at all (it may be a
     separate `HttpListener` thread)
   - **Key question**: why does `appDispatcher.CheckAccess()` return False even
     though `Thread.CurrentThread.ManagedThreadId == 1`? The WPF Dispatcher
     tracks threads by `Thread` reference, not ID — thread-pool threads may
     share ID 1 but aren't the dispatcher's thread.

2. **Verify chart discovery works**, then test `/api/chart/draw` end-to-end.

3. **Drawing tool styling/anchoring** (once a chart is found):
   - `HorizontalLine`/`Ray`/`Rectangle` anchor wiring
   - `Stroke`/`Brush`/`DashStyleHelper` properties
   - `ChartAnchor` creation with `DrawingTool` reference

## Files changed
- `scripts/ninjatrader/addons/McpBridgeAddOn.cs` — source of truth
- `scripts/strategies/nt8/addons/McpBridgeAddOn.cs` — synced copy
- `mcp/ninjatrader-mcp/nt8-addon/McpBridgeAddOn.cs` — synced copy **[DELETED 2026-08-14: wrapper folded into nt8-mcp-bridge, stale fourth copy removed]**
- `C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\AddOns\McpBridgeAddOn.cs` — live NT8

## Compile state
- Bridge `/api/compile`: **0 errors**, `version: "1.5.1-draw-fix"` confirmed
- All `out var` removed, GetP/SetP indexer-safe, visual-tree-only discovery

## Recommended next-session plan
1. **Debug the dispatcher deadlock.** Add logging to `ListOpenCharts` that reports:
   - `Thread.CurrentThread.ManagedThreadId`
   - `Thread.CurrentThread.IsThreadPoolThread`
   - `appDispatcher.Thread.ManagedThreadId`
   - `appDispatcher.CheckAccess()`
   This will reveal whether the HTTP listener is a thread-pool thread.
2. If it IS a thread-pool thread, use `BeginInvoke` + `WaitHandle` instead of
   synchronous `Invoke`.
3. Once chart discovery returns the 2 open charts, test `/api/chart/draw`.
4. Fix drawing tool styling/anchoring.
5. Update this handover.

## Key insight
> The HTTP listener thread is NOT the WPF UI thread, despite reporting
> `ManagedThreadId == 1`. `Dispatcher.CheckAccess()` correctly returns False.
> Synchronous `Dispatcher.Invoke` deadlocks because the UI thread isn't pumping
> while the HTTP request is in flight. The fix is async dispatch (`BeginInvoke`)
> or finding the correct dispatcher for the HTTP listener thread.