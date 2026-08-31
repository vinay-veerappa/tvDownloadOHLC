# TradingView Desktop — JS Injection & DOM Overlay System

**Status:** VALIDATED WORKING (2026-08-30/31, TV Desktop 3.4.0, Electron 41, Chromium 146)
**Surface:** `tradingview_ui_evaluate` (requires devel profile + capability gate, see Setup)
**Test tab:** Tab 0 (MYM1! 5m). All findings reproduced in a fresh process.

---

## 1. Setup (one-time)

1. **Launch TV Desktop with CDP:** `tradingview_tv_launch` (port 9222, kills existing). The MCP
   auto-detects the MSIX install and re-attaches. ~15s round trip.
2. **Enable arbitrary JS** — the gate is fail-closed. In `~/.config/opencode/opencode.jsonc`,
   tradingview server entry:
   ```jsonc
   "tradingview": {
     "type": "local",
     "command": ["node", "c:\\Users\\vinay\\tvDownloadOHLC\\tradingview-mcp\\src\\server.js"],
     "environment": {
       "TRADINGVIEW_MCP_ALLOW_ARBITRARY_PAGE_JS": "I_UNDERSTAND_THIS_EXECUTES_ARBITRARY_JAVASCRIPT",
       "TRADINGVIEW_MCP_PROFILE": "devel"
     }
   }
   ```
3. **Restart opencode after editing config** — MCP env vars are read at opencode startup; toggling
   the MCP in the UI reuses the cached definition (env won't apply). `ui_evaluate` is DEV_ONLY:
   visible only under `devel` (`src/tools/_profiles.js:73`), NOT in control/pine/base.
4. `tradingview_system_status` must show `arbitrary_page_js: enabled: true` + 104 tools visible.

## 2. The API Map (proven entry points)

```js
// Chart widget (the golden key)
const w = window._exposed_chartWidgetCollection.activeChartWidget._value;
w.getSymbol()            // 'CBOT_MINI:MYM1!'
w.getResolution()        // '5' (minutes), '1D', etc
w.symbolInfo()           // {name, short_description, exchange, type, currency_code,
                         //  minmov, pricescale, session, root, pro_perm...}
w.setSymbol('CME_MINI:MNQ1!', cb)      // programmatic control, cb = completion callback
w.setResolution('1', cb)               // same for timeframe
w.model()                              // chart model

// Bars / price data
const bars = w.model().mainSeries().bars();
bars.size(); bars.firstIndex(); bars.lastIndex();      // METHODS
bars.valueAt(i)        // [ts_epoch_s, o, h, l, c, v]
bars.last()            // -> object with .value = [ts,o,h,l,c,v]   <-- .value is a PROPERTY
const series = w.model().mainSeries();

// Panes & studies
w.model().panes()                        // [mainPane, subPane...]
pane.studySources()                      // studies in that pane
pane.priceDataSources()                  // series objects
study.title(); study.id(); study.metaInfo()             // metaInfo.plots = [{id, type...}]
study._series.bars()                     // the study's INPUT series (OHLC of main)
study._valuesProvider.getValues(barIndex)               // plot display values (see caveats)
```

## 3. Proven Test Results

| Test | Result | Notes |
|---|---|---|
| T1.1 tick feed | ✅ | DOM MutationObserver on legend (see §4). `series.dataUpdated()` subscribe works but NEVER fires in this build — events silent even while bar ticks update |
| T1.2 symbol switch | ✅ | survives; **re-bind the legend observer after setSymbol** (legend DOM re-renders) |
| T1.3 timeframe switch | ✅ | 5m→1m (741 bars)→5m clean, injection intact |
| T3.1 programmatic control | ✅ | setSymbol/setResolution with callback |
| T1.5 indicator values | ✅ | `study._valuesProvider.getValues(idx)` returns `[{title, value, visible}]` per plot. **Candle/numeric plots populated; line-only plots return `value:""`** (legend formatter suppression). RSI test: Candle plots 55.27/52.02, Logit MA 37.22 |
| Toolbar teardown | ✅ immunity | full battery + stress (60 nodes, 20 timers, dup IDs) caused ZERO shell mutations (MutationObserver-verified) |

### Failure post-mortem (2026-08-30, first session)
Toolbar disappeared after TV threw a reconnect error. `viewMode: force-fullscreen` was a red
herring (fresh processes report it too, WITH toolbar). Real lesion: `layout__area--top` had 0
children — shell React subtree unmounted by the reconnect failure. **Not fixable by DOM injection;
only a process restart cures it.** Recovery: `tradingview_tv_launch(kill_existing=true)`.

## 4. Tick Feed (the winning pattern)

`series.dataUpdated` events are dead in this build. Use the OHLC legend as the tick source:

```js
const val = document.querySelector('.valueValue-quatTGAC');   // legend price cell
let root = val;
for (let i = 0; i < 8 && root; i++) {
  const r = root.getBoundingClientRect();
  if (r.width > 400 && /(legend|container)/i.test(root.className || '')) break;
  root = root.parentElement;
}
const obs = new MutationObserver(() => { /* tick handler */ });
obs.observe(root || val.parentElement, { childList: true, subtree: true, characterData: true });
```
Measured: 42 ticks/min (thin MYM overnight), 136/10s (MNQ). **Re-create the observer after any
symbol change** — the legend node is re-rendered.

## 5. ⚠️ Network isolation — the CDP Pump architecture

**TV Desktop's page sandbox BLOCKS in-page `fetch()` and `XMLHttpRequest` to localhost** (both
fail with "Failed to fetch" / onerror, regardless of CORS headers the local server sends; no meta
CSP is readable). This is enforced by headers at the Electron layer — do not burn time trying
CORS/other tricks from inside the page.

Instead: **pump data through ui_evaluate**:
```
python API (localhost:PORT) ──── agent reads JSON ────> ui_evaluate injects values into DOM
```
- The overlay is dumb DOM; the agent session is the network layer.
- Update latency ≈ one tool roundtrip (~1-2s). Fine for levels/HUD; not for tick-by-tick.
- `scripts/streamer/tv_levels_api.py` (port 8630) is the reference feed: `/levels?ticker=MYM1`
  returns PDH/PDL/session OHLC/last/range% from `data/live/live_storage_-YM.parquet`.

## 6. Gotcha Ledger (learn the hard way, keep this list)

1. `bar.value` is a **property** (array), NOT a method — `lb.value` not `lb.value()`
2. `bars.size()` is a **method**; `bars.length` is not a function
3. `series.dataUpdated()` is a factory — call it, then `.subscribe(fn, ctx)` on the returned event …
   but it never fires in this build (§4)
4. Pane observables are `{_listeners, _value, _readonlyInstance}` wrappers — `._value` may be
   `null`; use `.value()` (method) on the readonly instance
5. `viewMode: 'force-fullscreen'` is NORMAL for this build (not a defect state)
6. Inject into `document.body` with `position:fixed` — never inside TV's own containers
   (React re-render will eat them)
7. Every injected element: fixed `id` (e.g. `ws-*`) + idempotent `remove()` of prior instance
   before re-inject
8. Always `clearInterval` + `delete window.X` on teardown; MutationObserver needs `.disconnect()`
9. `layout__area--top` children.length is the toolbar health probe (1 = healthy, 0 = shell dead → restart)
10. Screenshots: `capture_screenshot` CAN time out under load — retry once; tool also can't grab
    while a modal is up
11. Async `ui_evaluate`: promise results come back `{}` — kick work off, stash to `window.X`,
    read `window.X` on the next call
12. `model.dataSources()` returns 39 objects for 26 studies — extras are per-plot series; filter
    by `s.metaInfo && typeof s.metaInfo === 'function'` for studies
13. Weekend session math: Sunday ≥18:00 ET belongs to MONDAY's logical session (Globex reopen);
    Sat / Sun-before-18:00 belong to Friday's. Handled in `tv_levels_api._et_bounds`.

## 7. File Inventory

| File | Purpose |
|---|---|
| `scripts/streamer/tv_levels_api.py` | FastAPI feed: session levels from live parquet (port 8630) |
| `tradingview-mcp/` | The MCP server (submodule) — profiles, gates, `ui_evaluate` |
| `~/.config/opencode/opencode.jsonc` | MCP registration + capability gates (§1) |

## 8. Outstanding Test Matrix (from the validated baseline)

- T1.4 full history depth beyond chart-visible count
- T1.6 DOM depth ladder vs `depth_get`
- T2.2 NT8 bridge → DOM (positions/P&L via CDP pump)
- T2.3 Trading Brain states as chart badges (via pump)
- T2.4 GEX/CBOE vendor levels as overlay zones
- T2.5 bidirectional alerting (TV alert → webhook → stack)
- T3.2 pan/zoom control; T3.3 add/remove studies; T3.4 internal drawings; T3.5-3.6 multi-tab/layout
- T4.x rich UI (SVG/canvas, drag, themes)
- T5.1 long soak; T5.2 resize; T5.4 CDP reconnect; T5.5 post-update probe
- T6.x MCP read tools (session_snapshot diffing, draw/alerts, replay read-only, paper status)