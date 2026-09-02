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
14. `bar.value` values: `[ts_epoch_seconds, o, h, l, c, volume]`.
15. Live-storage parquet (`live_storage_-ROOT.parquet`) schema: `time` (int64 ms), `open/high/low/
    close/volume`, `timestamp` (str with +00:00). Always normalize to naive-UTC `dt` column before
    comparing (pandas 3 returns `datetime64[us, UTC]` from `timestamp`).
16. `pd.Timestamp.utcnow()` deprecated in pandas 3 — warns; use `pd.Timestamp.now('UTC').tz_localize(None)`.
17. Stale-process trap: after editing a Python module, KILL the old process — `Start-Process`
    silently spawns a second server or the old code keeps serving (cost us a 30-min debug loop).

## 6b. Round-2 API discoveries (2026-08-31)

### History paging (T1.4)
```js
series.requestMoreData(5000, true)   // loads 5000 more bars back
series.requestMoreDataAvailable()    // false = pager exhausted
series.isLoading()                   // true while paging
```
MYM1! 5m: 311 visible → 5311 after one page (back to Aug 3). `requestMoreDataAvailable:false`
confirms the provider's 5m ceiling. Repeatable to page deeper.

### Viewport control (T3.2)
```js
const ts = w.model().timeScale();
ts.barSpacing()          // px per bar (current)
ts.setBarSpacing(3)      // zoom out; ~2-40 valid
ts.rightOffset()         // bars of right margin
ts.setRightOffset(-20)   // pan left (negative shows more right history… actually future space)
ts.scrollToRealtime(); ts.scrollToFirstBar();
```

### Price-anchored overlays (T4.1) — the crown jewel
```js
const pane = w.model().panes()[0];
const ps = pane.defaultPriceScale();
const y = ps.priceToCoordinate(53862);   // price -> pixel Y in pane
ps.coordinateToPrice(yPx)                // inverse
// SVG: position:absolute inside .layout__area--center (chart container),
// pointer-events:none, redraw on timeScale changes (barSpacing/offset subscriptions exist there)
```
Proven: PDH/PDL/SESHI/SESLO drawn as SVG lines + labels matching the price axis exactly.

### Studies add/remove (T3.3)
- **Robust path:** MCP `chart_manage_indicator` (add → returns entity_id → remove).
- Internal `model.createStudyInserter().insert('RSI@tv-basicstudies')` returns a **Promise** and
  didn't land within 6s — prefer the MCP tool.

### Drawings (T3.4)
- **Robust path:** MCP `draw_shape` / `draw_list` / `draw_remove_one`.
- Read back via `w.model().dataSources()` → filter `title()==='horizontal line'` →
  `s.points()` → `[{price, index}]`. Class names are minified (`j` etc.) — match by `title()`.
- Internal `model.createLineTool({pane, linetool:'LineToolHorzLine', point:{index,price},
  properties:{}, actionSource:'ui'})` exists but fragile (`u.childs is not a function` without
  full registration args) — not worth it while MCP drawing tools exist.

### Churn stress (T5.2 partial)
20 rapid `setBarSpacing` flips + 10 `setRightOffset` pans → internals alive, bars intact,
view restorable. Injection survives viewport abuse.

## 9. ORDER INTERCEPTION — PROVEN (2026-08-31, live Tradovate) ⭐

The founding use case. Fully verified against a **live Tradovate account**.

### Order flow (complete, discovered end-to-end)
```
Panel click
→ TradingViewApi.trading()._checkAndPlaceOrder(order)        // logs order JSON
  → trading.brokerCommandsUI().placeOrder()
    → activeBroker()._placeOrder()                           // maintenance/telemetry gates
      → activeBroker()._brokerConnection.placeOrder()
        → _placeOrder(): customFields → digitalSignature → body merge
          → _fetchWithLatencyTrackingIfNeeded()
            → _restFetch → **window.fetch**  ← INTERCEPTION POINT
```
Key: the broker connection is plain REST over **window.fetch** — every order crosses a
patchable JS boundary. The API base observed: `https://tv-demo.tradovateapi.com`
(TV-mediated Tradovate connector; account id in the URL path).

### The guard pattern (what was tested)
```js
window.fetch = function(...args) {
  const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
  const method = (args[1]?.method || 'GET').toUpperCase();
  if (ARMED && /tradovateapi\.com/.test(url) && method === 'POST' && /order/i.test(url)) {
    AUDIT.push({ url, body: args[1]?.body, at: Date.now() });        // full payload captured
    return Promise.resolve(new Response(JSON.stringify({
      errorText: 'WS-GUARD: order blocked', errorCode: 'WS_GUARD_DENY'
    }), { status: 403, headers: { 'Content-Type': 'application/json' } }));   // VETO
  }
  return origFetch.apply(this, args);                                 // allow
};
```
TV's UI surfaces the synthetic 403 as a normal order rejection — user sees an error, we
hold the full order body (the exact policy-engine input).

### Measured result (user placed orders by hand, guard armed)
6/6 vetoed pre-broker — `MNQU6` limits ×4, `MYMU6` limit ×1, `MYMU6` **market+bracket
(SL/TP)** ×1 — with full request bodies captured (`instrument, type, side, qty,
limitPrice, stopLoss, takeProfit`, account id from URL). Broker verified **0 orders /
0 positions** afterwards; 300 non-order requests passed untouched (session unharmed);
order-type and instrument-agnostic. Guard disarmed after the test.

### Read-only access (needed by any guard/policy engine)
```js
const b = window.__tvTrading.activeBroker();
b.currentAccount()        // 'D63705235' (a String observable — char-array if misread as array)
b.orders()/positions()    // observables (empty = flat)
window.__tvConn.orders()  // same via connection layer
```

### Boundaries (honest scope)
- Guards **TV-originated orders on this broker connection** — i.e. everything sent through
  the chart's Trading Panel / DOM / broker API on the patched `fetch`.
- Does NOT see orders placed outside TV Desktop (direct broker API/web, NT8).
- Guard lives in page memory: lost on TV reload → must be re-armed by the persistent
  daemon (see §9); re-assert guard on every `execUTION context` we touch.
- Deny-all also blocks session-refresh POSTs matching the order pattern → keep the URL
  match ORDER-SPECIFIC, or expect occasional panel reconnects while armed.

### Follow-up build plan
1. **Policy engine** in the wrapper: max qty per order, max daily loss (via account state
   observable), instrument allowlist, price sanity band (fat-finger), kill-switch flag,
   full audit JSONL (payload + decision + timestamp).
2. **Pass-through confirmation flow**: allowed orders proceed via `origFetch` unchanged.
3. **Persistent daemon** (`tv_pump_daemon` extension): re-injects + re-arms the guard on
   CDP reconnect and on TV relaunch; serves the audit log over the loopback API.
4. Escalation semantics mirror nt8-riskguard: warn → block → lockout, same audit shape.

---

## 10. TARGET ARCHITECTURE — DECIDED 2026-08-31 (user-directed)

> **"Everything funneled into the same RiskGuard / copy-trader infra we have already
> built so far. We are adding a few interception layers + a UI view."**

### Principle
TV Desktop = **button/UI layer only**. NT8 = execution + risk + copy layer. **No new
risk engine, no new copier** — everything rides the existing, hardened stack
(nt8-riskguard: 3170 tests; TradeCopierEngine: leader→follower ratios, quarantine,
shadow mode).

### The funnel
```
TV chart (any button/draw-on-chart trade)
  → ORDER GUARD (patched fetch, §9)         ← layers being added:
      1. INTERCEPT: capture full order intent (body parse: instrument/qty/side/price)
      2. DECIDE:
         a. mode=FUNNEL: block direct send (synthetic 403) + extract intent
            → daemon → nt_place_atm_order (ATM bracket strategy)
            → nt8-riskguard pre-trade checks (existing, hardened)
            → TradeCopierEngine replicates leader→followers (existing)
         b. mode=KILL-SWITCH: deny-all (panic/lockout)
      3. AUDIT: JSONL every payload+decision (same shape as RiskGuard ledger)
```

### Component inventory (all proven where noted)
| Component | Status |
|---|---|
| Fetch-layer interception + payload capture | ✅ T7.3 (6/6 live veto) |
| TV-native-buttons disable | design: deny-all already proven; CSS toggle optional |
| Order ticket — **floating widget + in-chart HUD** | To build — **ATM strategies are already server-side** in the NT8 bridge (AtrAdaptive, DrawdownShield, ScaledRunner…: stop, target, breakeven, trailing, partials → OCO for free). Both surfaces funnel into the same ORDER GUARD → daemon → `nt_place_atm_order` path (see §10.1) |
| Pre-trade risk enforcement | ✅ existing nt8-riskguard |
| Copy distribution | ✅ existing TradeCopierEngine |
| Latency harness (TV-direct vs NT8-funnel) | To build — decision gate before any per-path choice; TV-direct ≈50–150ms, NT8-funnel est +100–500ms (UNMEASURED) |
| Persistent daemon (pump + re-arm + audit server) | Pending — single daemon serves overlays, guard arm, audit API |

### Constraints & context
- TV's connected Tradovate account `D63705235` = **demo** pattern (`D` prefix, `tv-demo`
  host). Live accounts live on the NT8/Provider31 side (TAKEPROFIT/LFE/APEX…); they are
  addressed as copy followers — TV needs no Tradovate credentials at all.
- All Phase-1 work on Sim101. Live enablement only after the measured decision gate.
- Every aspect measured before final decisions (user requirement).

## 10.1 Order ticket surfaces — floating widget + in-chart HUD (user-directed 2026-09-01)

**DECIDED: the order ticket ships as TWO surfaces, not one.**

1. **Floating widget** — a standalone always-on-top window (Electron/Tauri or a pinned
   browser window). Lives **outside** TV Desktop entirely.
2. **In-chart HUD** — DOM overlay injected into TV via the proven CDP injection path
   (§1, §6 gotcha 6–8: fixed `id`, `position:fixed`, idempotent re-inject).

### Why both (the rationale)
- **Floating widget is TV-independent** — it works irrespective of whether TradingView is
  running, and survives every TV failure mode (reconnect shell death, restart, update,
  CDP drop — see §3 post-mortem, §6 gotcha 9). The HUD cannot outlive the page it is
  injected into; the widget can.
- **HUD is chart-contextual** — symbol/price anchoring (`priceToCoordinate`, §6b) and
  one-click placement next to the chart you are watching. The widget lacks chart context
  but is always reachable.
- **Both submit through the SAME funnel** — no per-surface logic. Each surface only
  produces an order *intent*; everything below the intent boundary is shared:

```
Floating widget ─┐
                 ├─→ order intent (instrument/qty/side/price/strategy)
In-chart HUD ────┘         │
                           ▼
              ORDER GUARD (patched fetch, §9)     [in-chart surface only;
                │                                  widget sends intent directly]
                ▼
              daemon (persistent, pump + re-arm + audit)
                ▼
              nt_place_atm_order → DynamicAtmManager (§10: brackets/OCO/breakeven/
                │                    trailing/partials for free)
                ▼
              nt8-riskguard pre-trade checks → TradeCopierEngine distribution
```

### Design consequences
- The in-chart HUD's order ticket is subject to the §9 interception layer (patched
  `fetch`), because its clicks originate inside TV's page sandbox. The floating widget
  **bypasses the interception layer by construction** — it never runs in TV's page — so
  its risk enforcement is entirely downstream (daemon-side + RiskGuard pre-trade). This
  is acceptable because RiskGuard is the enforcement layer of record either way.
- Both surfaces share one intent schema — the same payload ORDER GUARD captures from TV
  (`instrument, type, side, qty, limitPrice, stopLoss, takeProfit`) is what the widget
  and HUD emit directly. One schema, two emitters.
- The widget needs its own account/symbol context (it cannot read TV's chart state); the
  HUD can pre-fill symbol/price from the chart. Keep the schema identical and let each
  surface populate fields from its own context source.
- Overlay lifetime asymmetry is the point of the dual approach: HUD re-injection after TV
  restart stays a daemon responsibility (§6c note); the floating widget simply persists
  across TV restarts.

### 10.2 Shipped implementation — RiskGuard-integrated ticket (2026-09-01, live-verified)

Built into `scripts/tradingview/huds/account_pnl.js` (shared module, v2.4.0) +
`scripts/tradingview/pnl_widget_server.js` (port 8635). Widget-only order path
(see caveat below).

- **Endpoints added to the widget server** (bearer token to NT8 bridge `localhost:7890`):
  - `GET /api/guard/config` — reads the guard's `config.json`
    (`Documents\NinjaTrader 8\RiskGuard\config.json`), re-read every 30s. Drives the
    ticket UI: symbol dropdown = `AllowedInstruments` × front/next quarterly codes,
    qty cap = `min(InstrumentLimits[root], Sizing.MaxContractsPerAccount)`.
  - `GET /api/lockouts` — sweep every 2.5s (cap 30 accounts, 10s TTL) via
    `POST /api/lockout {action:'status',account}`.
  - `POST /api/order/atm` — proxy to NT8 `POST /api/order/atm` (idempotencyKey required).
- **Ticket UI**: symbol `<select>` (allowed roots + quarterly codes, position symbols
  merged in), qty (capped, shows `max N`), ATM strategy select (AUTO + 8: FixedTicks,
  AtrAdaptive, SwingPoint, DrawdownShield, ScaledRunner, VolatilityScaled,
  SessionAdaptive, KellyOptimal), SL/TP ticks (default 40/80), `GUARD: SHADOW/LIVE`
  chip, status line for bracket response (`bracketId`, stop/target prices).
- **Per-row B/S buttons**: busy state keyed `account|side`, re-applied on every
  200ms re-render; locked accounts get `🔒LOCKED` badge + disabled buttons.
- **Panic flatten**: single click (2-click confirm removed, user-directed) →
  `POST /api/emergency-flatten` with reason `Operator Panic Flatten (Standalone
  Desktop Widget)`.
- **⚠️ Constraint (hit twice)**: `initScript` is embedded into the page template as
  `(${initScript})(panel)` — NO backticks or `${}` inside `initScript`; use string
  concatenation.
- **⚠️ TV HUD caveat**: the in-chart HUD shares `account_pnl.js`, but TV's page
  sandbox cannot fetch `localhost:8635` — the order path works in the standalone
  widget only. HUD renders the ticket bar but B/S buttons are non-functional there
  (deprioritized, user-directed).

#### Lockout semantics — what `/api/lockout` actually reports (learned 2026-09-02)

`RiskGuardAddOn.IsAccountLocked` (bridge view) has **three OR-ed sources**; the
RiskGuard UI window shows only the first, so the two can legitimately disagree:

1. `LockoutBinds()` — the enforcer's live predicate: `state.IsLockedOut` OR
   `state.LockoutUntil > now`, **suppressed when `LockoutWasShadowOnly` is true**.
   A shadow-mode lockout still records state (window may show clean) but the
   bridge's `IsAccountLocked` ALSO consults sources 2–3 below without that
   suppression, so accounts can read locked via the API while the window shows
   nothing.
2. `_lockoutExpiry` — bridge-local `ConcurrentDictionary` written by EVERY
   `/api/emergency-flatten` call (default 60 min, `lockoutMinutes` param) for
   **every account the flatten touched**, not just those that breached. The widget
   panic button and repeated manual flattens therefore lock out the whole touched
   fleet for an hour on the bridge side only.
3. `LockedOutAccounts` in `state.json` — restored as `state.IsLockedOut = true` on
   every add-on start (P2-92) with **no expiry**; only `UnlockAccount` clears it.

Practical consequence: a fleet-wide panic flatten (our widget's normal panic path)
poisons the lockout sweep for up to 60 minutes across every touched account — the
widget shows `🔒LOCKED` on all rows, the RiskGuard window shows nothing, and
`/api/order/atm` refuses everything non-reducing. Remedy if it is a false lockout:
`POST /api/lockout {action:'unlock',account:X}` per account (calls
`RiskGuardAddOn.UnlockAccount` + clears the bridge-local entry), or restart the
bridge with `state.json`'s `LockedOutAccounts` cleaned.

### 10.3 Render pipeline — stable rows (defect fixed 2026-09-02)

**Defect (measured):** `renderAccountsView()` rebuilt the whole table via
`tbody.innerHTML = html` every 200ms. Two symptoms, one cause:

1. **Clicks silently eaten.** The browser fires `click` only when mousedown and
   mouseup land on the SAME element. With a full innerHTML rebuild every 200ms,
   mousedown landed on the old button node, the rebuild replaced it, and mouseup
   landed on the new node → no click event, no order, no rejection, no log.
   This presented as "the sell did not work" with an empty bridge event stream.
2. **Flashing/strobing.** Hover state reset every rebuild, and the `.busy`
   opacity animation (`ws-pnl-flash`) restarted on every re-render → strobe.

**Fix (in `huds/account_pnl.js`, shared by widget + TV HUD):**
- **Stable rows**: rows are created once per account (keyed by a build key =
  view + account order). Each 200ms tick only updates volatile cell values
  (`textContent`/`className`) in place — buttons never move or vanish.
- **Event delegation**: ONE click listener on `tbody` (set once, flagged by
  `tbodyDelegated`) replaces per-button listeners; it survives any rebuild.
- **Flash removed** from `.busy` (opacity dim only); `ws-pnl-flash` remains on
  the DESYNC banner where it belongs.
- Relationship badges moved from the per-render HTML string to an in-place
  `otApplyRelBadges()` layer per row.

**⚠️ Any HUD that polls must follow this pattern: never rebuild DOM nodes a
user can press; update values in place and delegate events at the container.**

### 10.4 Trade copier findings (2026-09-02, live on Sim101 → Sim-ORB)

1. **Fixed (config)**: `AutoSymbolConversion` table is bidirectional mini↔micro,
   so a leader `MNQ SEP26` fill was translated to `NQ SEP26` — a
   BlockedInstruments root — and every copy refused
   (`COPY_BLOCKED_FOLLOWER_LOCKED: ... locked for NQ SEP26`). Also the
   relationship was `ArmedForLive:false` (shadow). Fix: set
   `AutoSymbolConversion:false` + arm. ⚠️ Bridge trap (P1-74): the request key
   `autoConversion` is SILENTLY DROPPED by `NormalizeRequest`; only the
   canonical `AutoSymbolConversion` applies.
2. **Open (core defect, ticketed)**: entry-vs-exit classification reads the
   OrderAction label (`Sell` = exit), so a market SELL on a flat account — a
   short ENTRY — is skipped (`COPY_SKIPPED_NO_POSITION_TO_EXIT`), and a short
   cover (Buy on short) would classify as ENTRY on a flat follower.
   **Short entries are never copied.** Ticket:
   `nt8-riskguard/agent/tickets_copier_classification.json` (CM0, position-delta
   classification spec + 6-case battery). Verified live: long entry + exit copy
   correctly; short entry does not.

## 6c. Financial Juice news/squawk panel (2026-08-31) — verified live

**Goal:** replicate the "FinancialJuice Widget" Chrome extension inside TV Desktop.

**Findings:**
1. TV Desktop (Electron) does **not** load user Chrome extensions — no `--load-extension`
   path via CDP, no extension session API reachable. Loading the `.crx` natively is a dead end.
2. The official extension (`hjdgbneibikfcollclifhpdhaljfklbk`, v2.0.2, 102KiB) is just a
   **content script that injects iframes** to FinancialJuice's public embed hosts:
   - `https://feed.financialjuice.com/widgets/headlines.aspx` (live text squawk)
   - `https://feed.financialjuice.com/voice-player.aspx` (voice squawk)
   - `https://feed.financialjuice.com/widgets/ecocal.aspx` (econ calendar)
   - `https://www.financialjuice.com/widgets/ts.aspx` (TickStrike order flow)
   No API keys, no chrome.* dependencies beyond runtime.getURL for icons.
   All hosts allow embedding (verified: no X-Frame-Options/CSP frame-ancestors).

**Implementation (in-chart overlay `#ws-fj-panel`):**
- Draggable (title-bar mousedown) + resizable (CSS resize)
- Tab bar: 📰 Headlines / 📅 Econ Calendar (lazy-loaded iframe on first click)
- Persistent voice-player bar (52px) across tabs — audio controls inside the iframe
- Dark theme, TV-integrated styling
- Verified rendering live headlines + calendar in-session (screenshots
  `ws_fj_news_panel.png`, `ws_fj_econcal_tab.png`)

**Note:** overlay lives in page memory — dies on TV restart until the pump daemon
(pending task) re-injects it at startup. Panel id `ws-fj-panel`; teardown =
`document.getElementById('ws-fj-panel').remove()`.
Reference screenshots: `screenshots/ws_fj_news_panel.png`,
`screenshots/ws_fj_econcal_tab.png` (this directory).

## 7. File Inventory

| File | Purpose |
|---|---|
| `scripts/streamer/tv_levels_api.py` | FastAPI feed: session levels from live parquet (port 8630) |
| `tradingview-mcp/` | The MCP server (submodule) — profiles, gates, `ui_evaluate` |
| `~/.config/opencode/opencode.jsonc` | MCP registration + capability gates (§1) |

## 8. Test Matrix — Status Board

**L1 — Live Data & Subscriptions**
- [x] T1.1 tick feed — DOM legend MutationObserver (events dead) — 42/min measured
- [x] T1.2 symbol change survival (+ observer re-bind requirement)
- [x] T1.3 timeframe change survival
- [x] T1.4 full history depth — `requestMoreData` paging (311→5311, ceiling verified)
- [x] T1.5 indicator series reads — RSI sub-pane values via `_valuesProvider.getValues`
- [ ] T1.6 DOM depth-ladder vs `depth_get`

**L2 — Stack ↔ TV Integration (the real goal)**
- [x] T2.1 Python → HUD (levels card, CDP pump) — **arch decision: page sandbox blocks fetch/XHR**
- [x] T2.2 NT8 bridge → HUD — **DONE 2026-08-31**: `/positions` endpoint + live card verified
  (Sim101 Long 1 MNQ @29,317.50 rendered bottom-right; symbol-mismatch guard: entry line only
  drawn when position symbol matches chart, else card shows ⚠)
- [ ] T2.3 Trading Brain governance badges (via pump)
- [ ] T2.4 GEX/CBOE vendor levels as overlay zones (SVG ready via T4.1)
- [ ] T2.5 bidirectional alerting (TV alert → webhook → stack)

**L7 — Order Interception (see §9)**
- [x] T7.1 order-path discovery (full funnel to window.fetch)
- [x] T7.2 log-only tap (93 calls / 8s; all TV↔Tradovate REST visible)
- [x] T7.3 VETO proof — 6/6 orders blocked pre-broker on live account
  (limit + market + bracket, 2 instruments, 0 leaked, session unharmed)
- [ ] T7.4 policy engine (qty/loss/allowlist/fat-finger/kill-switch + JSONL audit)
- [ ] T7.5 persistent arm (daemon re-arms on reload/reconnect)
- [ ] T7.6 escalation semantics (warn → block → lockout)

**L3 — Chart Control via Injection**
- [x] T3.1 `setSymbol`/`setResolution` programmatic
- [x] T3.2 pan/zoom (`timeScale` full control)
- [x] T3.3 add/remove studies (MCP tool; internal = promise-based)
- [x] T3.4 drawings (MCP draw_*; read-back via `dataSources()` title-matching)
- [ ] T3.5 multi-tab overlays & survival
- [ ] T3.6 multi-pane layout (2x2), per-pane targeting

**L4 — Rich UI**
- [x] T4.1 SVG price-anchored overlay (`priceToCoordinate`)
- [ ] T4.2 CSS animations (event pulses)
- [ ] T4.3 drag-moveable panels
- [ ] T4.4 custom fonts/icons
- [ ] T4.5 theme adaptation (TV CSS vars)

**L5 — Robustness & Longevity**
- [~] T5.2 churn stress (zoom/pan x30) — PASS; window resize untested (OS-level)
- [ ] T5.1 hours-long soak
- [ ] T5.3 theme switch / fullscreen survival
- [ ] T5.4 CDP disconnect-reconnect mid-session
- [ ] T5.5 post-TV-update API drift probe
- [ ] T5.6 error boundary (internals throwing)

**L6 — MCP Tool Surface**
- [x] T6.1 `session_snapshot` / `chart_changes` — hash-diff works (`since:` prior hashes →
  changed/unchanged lists); `include:` narrows sections; compact mode returns hashes only
- [x] T6.2 alerts — `alert_create` (crossing price) → `alert_list` (62-alert inventory with
  conditions) → `alert_delete`; alert IDs returned; created at 1m resolution by default
- [x] T6.4 `data_get_pine_*` — your EV Ladder fully readable: `pine_tables` returns the complete
  rung table (12 rows), `pine_lines` returns 505 horizontal levels, `pine_boxes` 504 zones.
  **`study_filter` needs the full indicator TITLE** ('EV Ladder' short title returned 0; use
  'Expected Volatility — Percentile Ladder')
- [x] T6.5 replay read-only — `replay_start(date,time)` → `replay_step` ×3 → `replay_status`
  (position/pnl null when no trades) → `replay_stop`. Gotcha: TV shows 'Continue your last
  replay?' modal on re-entry — dismiss via `ui_click` 'Continue' before status reads
- [~] T6.6 watchlist ✅ (51 symbols w/ prices, "Futures" list) · batch_run ❌ **tool bug**:
  0-byte screenshot files (colon in `CME_MINI:MES1!` breaks filename) and chart left on last
  batch symbol — use single `chart_set_symbol` + `capture_screenshot` loops instead
- [x] T6.7 paper status (read-only) — `paper_get_status` reports provider TRADOVATE
  (connected, D63705235), `safe_for_paper_mutation:false` correctly fail-closed for
  non-Paper broker. Mutations properly refused outside Paper broker id.

**Recommended next:** T2.2 (NT8 positions on chart — combines proven pump + SVG anchor),
then T2.4 (GEX zones), then T3.6 (multi-pane), then T5.1 soak.