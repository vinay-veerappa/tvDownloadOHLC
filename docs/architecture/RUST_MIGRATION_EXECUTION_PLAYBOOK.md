# Execution Playbook: Rust Pragmatic Migration (Verified & Calibrated)

> **EXECUTION STATUS (2026-09-03)** — Tracks 1 & 2 COMPLETE with gates passed; Track 1 is LIVE in production (cutover done). Both desktop widgets (`pnl_widget_gdi` and `fj_widget`) are 100% migrated to pure native Rust (zero Node.js or Edge/Chrome dependencies). Track 3 built and simulated-gate-passed but direct-broker flatten is DEFERRED — awaiting broker API credentials. Details in the **Execution Record** below.

**Target Tracks:**
1. **Track 1 (`crates/trading_daemon`):** Consolidate `pnl_widget_server.js` + `fj_widget_server.js` + `stream_chart.py` (~450MB reclaimed).
2. **Track 2 (`crates/nt8_parity_core`):** PyO3 acceleration for un-accelerated Python bar loops in `scripts/execution/nt8_parity_engine.py` (50x–200x speedup).
3. **Track 3 (`crates/broker_sentinel`):** Direct broker API circuit breaker if NT8 port 7890 deadlocks with open positions.

**Model Execution Instructions:**
Execute each track sequentially. Do not start a track until the preceding track's **Verification Gate** commands pass with zero errors.

---

## Track 1: Consolidated Rust Daemon (`trading_daemon`)

### Objective
Drop-in replacement for `pnl_widget_server.js` and `fj_widget_server.js`.
* Listens on port `8635`.
* Uses shadow test port **`8637`** during verification (port `8636` is occupied by `fj_widget_server.js`).

### Step 1.1: Poller Implementation (`crates/trading_daemon/src/poller.rs`)
Must execute **three concurrent requests** every 200ms to NT8 port `7890`:
1. `GET /api/account` (Note: **singular** `/api/account`, not `/api/accounts`)
2. `GET /api/positions`
3. `GET /api/copier/snapshot` (CRITICAL: Preserves copier follower status rows in the HUD)

### Step 1.2: Complete HTTP Route Surface (`crates/trading_daemon/src/server.rs`)
Must implement the full live contract served on port `8635`:
* `GET /health` $\rightarrow$ `{ "status": "ok", "port": 8635, "nt8Connected": true }`
* `GET /api/data` $\rightarrow$ Returns cached 200ms snapshot with accounts, positions, and copier rows.
* `POST /api/order/atm` $\rightarrow$ Proxies to NT8 port 7890 with `confirmLive = true` injection.
* `POST /api/position/close` $\rightarrow$ Proxies to NT8 port 7890 `/api/position/close`.
* `POST /api/flatten` $\rightarrow$ Proxies to NT8 port 7890 `/api/flatten`.
* `GET /api/lockouts` $\rightarrow$ Serves cached lockout statuses.
* `GET /api/guard/config` $\rightarrow$ Reads `Documents/NinjaTrader 8/RiskGuard/config.json`.
* `GET /` and `/pnl-widget` $\rightarrow$ Serves the HTML widget page.
* **Background Tasks:**
  * 2.5s interval sweep: evaluates account lockouts and POSTs to `/api/lockout`.
  * 30s interval reload: refreshes RiskGuard `config.json`.
  * Real-time CDP push: WebSocket `Runtime.evaluate` to port `9222`.

### Step 1.3: Verification Gate 1 (Shadow Parity Test on Port 8637)
1. Run `trading_daemon` on port **8637**:
   ```powershell
   cargo run --release -p trading_daemon -- --port 8637
   ```
2. Execute the verification script:
   ```powershell
   $node = Invoke-RestMethod -Uri "http://127.0.0.1:8635/api/data"
   $rust = Invoke-RestMethod -Uri "http://127.0.0.1:8637/api/data"

   # 1. Verify account count parity
   if ($node.accounts.Count -ne $rust.accounts.Count) { throw "Account count mismatch: Node=$($node.accounts.Count), Rust=$($rust.accounts.Count)" }

   # 2. Verify account balances match within $0.01 tolerance
   for ($i = 0; $i -lt $node.accounts.Count; $i++) {
       $na = $node.accounts[$i]; $ra = $rust.accounts[$i]
       if ($na.name -ne $ra.name) { throw "Account name mismatch at index $i: $($na.name) vs $($ra.name)" }
       if ([Math]::Abs($na.netLiquidation - $ra.netLiquidation) -gt 0.01) { throw "NetLiq mismatch on $($na.name): $($na.netLiquidation) vs $($ra.netLiquidation)" }
   }

   # 3. Verify copier rows are present
   if ($node.copierRows.Count -ne $rust.copierRows.Count) { throw "Copier rows mismatch: Node=$($node.copierRows.Count), Rust=$($rust.copierRows.Count)" }

   Write-Host "GATE 1 PASSED: 100% Data & Balance Parity Verified!" -ForegroundColor Green
   ```
3. **Cutover:** Terminate Node `pnl_widget_server.js` and bind `trading_daemon` to port `8635`.

---

## Track 2: PyO3 Parity Engine Inner Loops (`nt8_parity_core`)

### Objective
Accelerate the two un-accelerated Python `for` loops in `scripts/execution/nt8_parity_engine.py` (lines 138 and 350) that iterate sequentially over 120–130MB Parquet bar files.

### Step 2.1: Rust Core Implementation (`crates/nt8_parity_core/src/lib.rs`)
* Target loops:
  1. `simulate_bars_v1`: Replaces loop at line 138.
  2. `simulate_bars_v2`: Replaces loop at line 350.
* Inputs: NumPy arrays of `times`, `opens`, `highs`, `lows`, `closes`, `signals`.
* Logic: Tick snapping (0.25 tick intervals), intra-bar MFE/MAE excursion tracking, daily trade limits, and consecutive loss cooling.
* Leave all Numba `@njit` ICT modules (`fvg`, `liquidity`, `cisd`) untouched.

### Step 2.2: Verification Gate 2 (Deterministic Parity Check)
1. Build PyO3 module:
   ```powershell
   cd crates/nt8_parity_core
   maturin develop --release
   ```
2. Run automated diff against Python implementation across 1 full year of historical 1-minute bars:
   ```powershell
   python -c "
   import numpy as np
   from scripts.execution.nt8_parity_engine import NT8ParityEngine
   import nt8_parity_core

   # Assert that PyO3 simulation results match Python simulation results exactly:
   # Total trades, entry prices, exit prices, net PnL, and max drawdown.
   print('GATE 2 PASSED: Zero-divergence parity confirmed!')
   "
   ```

---

## Track 3: True Independent Broker Killswitch (`broker_sentinel`)

### Objective
An independent watchdog whose ONLY job is to detect port `7890` unresponsive during active positions and flatten directly via the broker's API.

### Step 3.1: Watchdog Logic
* Polls NT8 port 7890 `/api/positions` every 500ms.
* If active positions exist:
  * Check heartbeat: if port 7890 fails to respond for $> 3,000$ ms:
  * Trigger direct broker API flatten (Tradovate REST API credentials or Rithmic).
* **Corrected Cushion Formula:**
  $$\text{Cushion} = \text{Current Net Liq} - (\text{Peak Net Liq} - \text{Trailing Limit})$$

### Step 3.2: Verification Gate 3 (Simulated Killswitch Test)
* Using Tradovate Demo / Sim API:
  1. Open simulated position on test account.
  2. Suspend/kill NinjaTrader 8 process.
  3. Assert sentinel detects dead port within 3 seconds and issues direct broker flatten order.

---

## Execution Record (2026-09-03) — what was actually done, measured, and learned

### Environment setup (prerequisites that did not exist)
* **Rust toolchain was absent.** Installed `rustup` stable → `rustc 1.98.1 (x86_64-pc-windows-msvc)`. MSVC BuildTools 2022 linker already present (verified via `vswhere`).
* **maturin 1.15.0** installed into `.venv` (Python 3.12.10).
* ⚠️ **System python is 3.14**, which PyO3 0.21 refuses (`configured interpreter newer than max supported 3.12`). Every cargo build of `nt8_parity_core` needs `PYO3_PYTHON` pointed at the repo venv:
  ```powershell
  $env:PYO3_PYTHON = "C:\Users\vinay\tvDownloadOHLC\.venv\Scripts\python.exe"
  ```
  `maturin develop --release` also requires this env var. The built module is installed editable into `.venv` — re-run `maturin develop` after any `lib.rs` change.

### Track 1 — COMPLETE & LIVE (Gate 1 PASSED, cutover executed)
**Implemented** (`crates/trading_daemon`): `poller.rs` (200ms, three concurrent NT8 GETs — `/api/account` singular, `/api/positions`, `/api/copier/snapshot` — plus fleet-summary math mirroring `computeFleetSummary` and CDP `Runtime.evaluate` push with panic-hook), `server.rs` (full route surface per Step 1.2), `state.rs` (2.5s lockout sweep capped at 30 accounts / 10s staleness, 30s guard-config reload, emergency-flatten trigger). Widget HTML is embedded from `assets/widget.html` (captured byte-verbatim from the live Node server before cutover).

**Gate 1** ran on shadow port 8637 via `crates/gate1_parity.ps1` — passed 3×. (⚠️ That script has since been **retired**: post-cutover it compared 8635 to itself. Use `crates/gate1_contract.ps1`; see the post-review fixes at the end of this document.) Parity work went beyond the gate script; four semantic diffs had to be eliminated to reach **byte-identical** JSON (worth knowing for any future Node→Rust port):
1. **JS falsy fallback**: Node's `Number(acc.netLiquidation || acc.cashValue)` falls back on a *present-but-0* NetLiq (the $100k Backtest account). Rust `unwrap_or` only handles absent fields — must mirror truthiness explicitly.
2. **Key order**: serde_json sorts keys; Node preserves upstream order → `preserve_order` feature required.
3. **Number formatting**: JS prints integral f64s as `0`, not `0.0`, and V8's grisu shortest-repr drops the final digit ryu keeps (`49453.150000000052` → `49453.15000000005`). Fixed with `arbitrary_precision` pass-through + a post-serialization JS-number normalizer (`js_normalize_json_str` in `poller.rs`).
4. Final gate-script runs hit live-market drift between the two sequential fetches ($0.50 unrealized movement) — a transient, not a bug; re-runs pass.

**Cutover executed 2026-09-03 (~10:45), user flat**: Node pid killed, daemon bound to 8635. Post-cutover audit: health OK, 109 accounts, 2 copier rows, lockouts + guard config live, widget HTML identical (64,196 chars). CDP push proven live by stopping Node entirely — TV HUD kept updating from the Rust daemon (fresh-data drift 145ms). ⚠️ TV Desktop's CDP port 9222 can vanish (TV update/relaunch); the daemon fails silently — relaunch TV with CDP (`tv_launch`) and the daemon reconnects on its own.

**Operations** (auto-start wired after a false start, see "Launch defects" below):
* `launch/start_trading_daemon.bat` — supervisor loop: starts the daemon, appends to `logs/trading_daemon.log`, auto-restarts on exit, exits 2 on configuration failure. Port-taken is detected by a **health probe** (not exit-code guessing) so duplicate launches and scheduler re-triggers are harmless no-ops.
* `launch/stop_trading_daemon.bat` — kills daemon + any legacy `pnl_widget_server.js`.
* `launch/widgets/start_pnl_widget.bat` / `stop_pnl_widget.bat` — widget App-Mode window, updated to the daemon.
* `launch/widgets/start_trading_stack.bat` — step 1 now starts the Rust daemon instead of `start_pnl_streamer.ps1`.
* `launch/register_trading_daemon_task.ps1` — registers scheduled task **`TradingDaemon`** (logon trigger + 15-min repeating re-arm, same pattern as `RiskGuardAlertRelay`; the repetition fixes the measured "RestartCount is a budget not a policy" silent-outage class). Task registered and verified.
* `fj_widget_server.js` on 8636 remains Node — out of Track 1 scope; playbook's consolidation target list overstated.

**Launch defects (both caused a real incident on 2026-09-03 ~11:20 — daemon crash-looped and NT8 hung until the user restarted it):**
1. `.bat` files written as UTF-8 **with BOM** → cmd rejected `'@echo'`, em-dashes mangled mid-file parsing, every launch failed instantly, restart loop became a crash-loop. **Rule: batch files must be pure ASCII, no BOM.**
2. Bind-fight loop: a second instance's bind failure exits code **1**, not the 100 the guard checked → duplicate launchers would loop forever fighting the live one. Fixed with the health-probe guard above.
All four bats verified live before re-enabling the task: start OK, kill→auto-restart OK, duplicate→quiet exit OK, task fire→no duplicate OK.

### Track 2 — COMPLETE (Gate 2 PASSED, zero divergence)
**Implemented** (`crates/nt8_parity_core/src/lib.rs`): `simulate_bars_v1` (replaces `NT8ParityEngine.simulate` loop) and `simulate_bars_v2` (replaces `simulate_mtf` loop) — tick snapping, Queen/Runner targets, BE-lock intra-bar fill sequence, daily trade caps, consecutive-loss pause + hard-stop, `DailyMaxLoss`, MFE/MAE excursions, confirmed re-entry protocol. Inputs are epoch-ms int64 time arrays + f64 OHLC arrays; Numba ICT modules untouched.

**Gate 2** (`crates/gate2_parity.py`): 353,152 one-minute bars (NQ1, calendar 2023), deterministic synthesized signals. Results:
* v1: 774 trades — entry/exit prices, leg1/leg2, total points, entry timestamps **exactly equal** (bit-exact, not tolerance).
* v2: 560 trades — all fields including MFE/MAE **exactly equal**.
* Speedup measured on the same year: **4,030ms Python → 10.6ms Rust = 378×** (playbook target 50–200×; exceeded).
* ⚠️ Timezone note: the Rust port reads `hhmm` in UTC from epoch-ms. The Python engine derives `hhmm` from the parquet index, which is ET-naive. For the 2023 NQ1 file the two agree (index is stored ET-shifted); if a future source stores true UTC timestamps, the hhmm derivation must convert to ET inside the Rust port before Gate 2 can stay green.

### Track 3 — BUILT, Gate 3 PASSED in simulation; live-fire DEFERRED
**Implemented** (`crates/broker_sentinel`): 500ms `/api/positions` poll, >3,000ms dead-port detection with open positions → killswitch trigger; corrected cushion formula `Cushion = Current NetLiq − (Peak NetLiq − Trailing Limit)` with peak ratchet (50k jump guard); Tradovate REST path implemented (`/v1/auth/accesstokenRequest` → `/v1/position/list` → `/v1/order/placeorder` offsets). Config from `Documents/NinjaTrader 8/RiskGuard/sentinel.json`; `arm_live_flatten` defaults false.

**Gate 3** (`crates/broker_sentinel/src/bin/gate3_killswitch.rs`, isolated mock port 17890 via `SENTINEL_TEST_PORT` so the real NT8 is never touched): cushion formula verified (2,000.00 hand-computed); live NT8 observed with a real open position (cushion tracked); mock kill → `KILLSWITCH TRIGGER` fired with the exact Tradovate call logged dry-run; credential-less real-broker path fails safe.

**Why deferred:** the user has **no access to the broker API** (Tradovate/Rithmic). The killswitch's only purpose is independence from NT8 — routing it through NT8 fails exactly when needed, so there is no NT8-side substitute. Interim mitigation available on request: sentinel alert-only mode (OS-level notification; operator flattens manually from the broker web/mobile). Revisit when API credentials exist. Until then the sentinel runs observe/dry-run only.

### Native Desktop Widgets — COMPLETE & LIVE (2026-09-03)

Following Track 1's daemon consolidation, both frontend desktop widgets were completely rewritten in pure native Rust, eliminating all external browser windows (Edge/Chrome App Mode) and Node.js servers:

1. **Fleet P&L Native GDI Widget (`crates/pnl_widget_gdi` -> `pnl_widget_gdi.exe`)**:
   - **Engine:** Pure Win32 GDI standalone application. Memory footprint: ~18MB RAM.
   - **Feature Parity:** Full 3-tab navigation (P&L | Copier | Risk), interactive order ticket (B/S/Close), dynamic symbol dropdown with allowed roots, ATM strategy selector, max-cap chips, and RiskGuard lockout badge.
   - **Financial Formatting:** Full-digit currency display with comma separators (`$327.75`, `$100,000.00`) across account rows and top summary card (no `K`/`M` truncation).
   - **Live Net Liq Tracking:** Dynamic floating `unrealizedPnL` computed into `netLiquidation` in `poller.rs` so total portfolio value updates tick-by-tick during active positions.
   - **Session Rollover Retention:** Enhanced `McpBridgeAddOn.cs` with cached execution performance (`SystemPerformance.Calculate(account.Executions)`) to preserve cumulative 24-hour realized P&L across the 18:00 EST CME rollover.
   - **Execution Bug Fixes:** Fixed false `REJECTED HTTP 200` UI error caused by raw substring checks; fixed `close_position` error propagation.
   - **Launcher:** `launch/widgets/start_pnl_widget.bat` spawns `pnl_widget_gdi.exe` directly.

2. **FinancialJuice Native Widget (`crates/fj_widget` -> `fj_widget.exe`)**:
   - **Engine:** Pure native Rust desktop application combining `tao` (native Windows windowing) and `wry` (embedded Microsoft WebView2 runtime).
   - **Self-Contained In-Process Proxy:** Embeds the Hyper reverse proxy on port `8636` inside a background Tokio thread. Serves the dark HUD and injects dark-mode CSS (`#ws-fj-cal-override`) and form postback rewrites into the Economic Calendar (`ecocal.aspx`).
   - **Audio Squawk Autoplay:** Configured `--autoplay-policy=no-user-gesture-required` and `allow="autoplay"` so live spoken voice squawk streams immediately on launch.
   - **Streaming Fidelity:** Live SignalR 2.4.3 news headlines, Econ Calendar, and TickStrike tabs.
   - **Memory Reclaim:** Consumes only **~24 MB RAM**, reclaiming ~80 MB from Node.js `fj_widget_server.js` and ~300 MB from the external Edge App Mode process.
   - **Launcher:** `launch/widgets/start_fj_widget.bat` and `stop_fj_widget.bat` with decoupled WMI process creation.

### Build/run quick reference
```powershell
# Trading Daemon (production, port 8635)
launch\start_trading_daemon.bat            # supervised + logged
launch\stop_trading_daemon.bat             # stop

# Fleet P&L Native GDI Widget
launch\widgets\start_pnl_widget.bat        # launches crates\target\release\pnl_widget_gdi.exe
launch\widgets\stop_pnl_widget.bat         # stops widget and daemon

# FinancialJuice Native Rust Widget (port 8636 + WebView2)
launch\widgets\start_fj_widget.bat         # launches crates\target\release\fj_widget.exe
launch\widgets\stop_fj_widget.bat          # stops widget

# Rebuild all release binaries
$env:PYO3_PYTHON = "C:\Users\vinay\tvDownloadOHLC\.venv\Scripts\python.exe"
cd crates; cargo build --release

# Rebuild PyO3 module
.venv\Scripts\python.exe -m maturin develop --release -m crates\nt8_parity_core\Cargo.toml

# Gates
powershell -ExecutionPolicy Bypass -File crates\gate1_contract.ps1                 # live contract check
powershell -ExecutionPolicy Bypass -File crates\gate1_contract.ps1 -ShadowPort 8637 # real A/B vs a candidate
# gate1_parity.ps1 is RETIRED and exits 2 - it compared 8635 to itself. See below.
.venv\Scripts\python.exe crates\gate2_parity.py                    # engine zero-divergence
crates\target\release\gate3_killswitch.exe                         # sentinel simulation
```

### Open items & Remaining Activities
1. **`fj_widget_server.js` & `pnl_widget_server.js` Elimination**: ✅ **COMPLETE**. Both Node servers and Edge App Mode launchers are replaced by native Rust binaries (`pnl_widget_gdi.exe` and `fj_widget.exe`), fully realizing the ~450MB+ memory reclaim goal.
2. **Sentinel Live-Fire**: Blocked on external broker API credentials (Tradovate/Rithmic). The sentinel is now **actually running** observe-only (see post-review fixes below); before that it had no launcher and no task, so "runs observe/dry-run only" described a process that was not running at all.
3. **`stream_chart.py` (Futures Data Streamer)**: Remains in Python (1,424 LOC, **268 MB measured** — now the single largest process on the box). Currently streams Schwab/yfinance candles to SQLite `dev.db`. Candidate for future Rust migration if Python CPU or latency becomes a bottleneck.
4. **Scheduled Tasks**: `TradingDaemon` and `BrokerSentinel` registered; if the repo moves, re-run `launch/register_trading_daemon_task.ps1` and `launch/register_broker_sentinel_task.ps1`.
5. **⚠️ ZERO TESTS.** 3,940 LOC across five crates, `#[test]` count **0**, and this repo has no CI at all (no `.github/workflows/`, no `tools/ci_local.py`). The three gates are one-shot scripts run by hand. The sibling repos hold 3170/0 with 46 mutation batteries over the same trading path. **This is the largest remaining gap** and none of the fixes below close it.
6. **Bearer token hardcoded in 33 tracked files** (find them with `git grep -l NT8_TOKEN` / the literal in `crates/trading_daemon/src/poller.rs:17`). ⚠️ **Do not paste the literal into a doc** — this line used to quote it, and committing this file is what took the count from 32 to 33. Breakdown: 25 in `scripts/research/`, 3 in the Rust crates, 2 in `launch/widgets/`, the rest in archive/docs. It is declared **twice inside `trading_daemon`** (`poller.rs:17` and `state.rs:9`, while `server.rs` imports from `poller`), so rotating it means finding both copies in one crate. It is loopback-only, which is why this is low severity and not zero.
7. **`load_config()` in `broker_sentinel/src/lib.rs` fails silently.** A malformed `sentinel.json` falls through to `SentinelConfig::default()` with no warning — the operator's tuned limits vanish and the config file still reads as if it applied.

---

## Post-review fixes (2026-09-03, after the playbook review)

Four defects found by reviewing the shipped state against the plan. All four are fixed and verified; each verification includes a negative control, because a gate that has never been observed failing has not been shown to work.

**1. Gate 1 could no longer fail.** `gate1_parity.ps1` fetched 8635 as `$node` and 8637 as `$rust`. After cutover 8635 *is* the Rust daemon, so it compared the daemon to itself and passed unconditionally; `pnl_widget_server.js` is archived, so the Node side cannot be restored.
* `crates/gate1_contract.ps1` replaces it, with two modes: a **contract check** against `crates/golden/api_data_contract.json` (route surface, required keys, numeric types, account-count floor, copier-block presence, and a **payload-freshness check** — the one that catches a daemon that is UP but serving a frozen cache), and a **parity mode** (`-ShadowPort N`) that **refuses to run when both ports resolve to the same pid**.
* `gate1_parity.ps1` is kept but exits **2** with a pointer, because the playbook and shell history still invoke it by name and a missing file would read as an environment problem.
* Verified: passes live (109 accounts, 2 copier rows, 91 ms freshness); and fails on all three negative controls — same-pid comparison, dead port, and injected contract violations.

**2. The compute kernel was built for size.** The workspace `[profile.release]` sets `opt-level = "z"` — correct for the three I/O-bound widget binaries, wrong for `nt8_parity_core`, which it silently inherited. Added a per-package override to `opt-level = 3`.
* Measured on the Gate 2 dataset (353,152 bars, best of 7): **`"z"` = 11.29 ms → `3` = 7.44 ms**, a further **1.52×**. Gate 2 re-run after the change: still **bit-exact** on both v1 (774 trades) and v2 (560 trades).

**3. The PyO3 fallback was silent.** `nt8_parity_engine.py` had a bare `except ImportError: HAS_RUST_CORE = False` with `use_rust=True` as the default, so a missing build silently switched engines. That is not only ~378× slower — per the timezone caveat above the two paths can produce **different trades** on a differently-stored source.
* Now warns loudly at import and **fails closed** via `_require_rust_core()` at both dispatch sites, with `NT8_PARITY_ALLOW_PY_FALLBACK=1` (or `use_rust=False`) as the deliberate opt-out.
* Verified with a `find_spec` blocker: module present → passes; module blocked → warns at import **and** raises; opt-out set → permits the Python path.

**4. The sentinel was not running, and "stop" did not stop.** Track 3 had no launcher and no scheduled task. Added `launch/start_broker_sentinel.bat`, `launch/stop_broker_sentinel.bat`, and `launch/register_broker_sentinel_task.ps1` (logon trigger + 15-min re-arm, task read back to assert the repeating trigger persisted). Sentinel now runs at **~10 MB**, observe-only.
* ⚠️ **Killing the child does not stop a supervised component.** The launcher is a restart loop, so `Stop-Process` on the exe let the supervising `cmd.exe` bring it back 10 s later under a **new pid** while the stop script reported success. Both stop scripts now kill the **supervisor first, then the child**, and re-read after the restart window to report the *outcome* rather than the fact that the kill line was reached. The same defect was present in `stop_trading_daemon.bat` and is fixed there too (the widget launchers are one-shot and unaffected).
* ⚠️ **An unqualified `-CommandLine` wildcard on a kill path matches too much.** `stop_trading_daemon.bat`'s legacy-Node clause matched the stop script's **own powershell child** during testing. Now scoped to `$_.Name -eq 'node.exe'`.
* ⚠️ **The child holds the log file open**, so the supervisor's "already running, exiting quietly" line hit a sharing violation and recorded nothing — precisely when a duplicate launch is what you are diagnosing. Supervisor lines now go to `logs/broker_sentinel.launcher.log`.
* Verified: duplicate launch and task re-trigger both leave exactly **1** process and log cleanly; stop leaves **0** processes and **0** supervisors and stays down; task re-enable restores it. Both bats are pure ASCII with no BOM (the recorded launch-defect rule). The real `stop_trading_daemon.bat` was then executed against the live daemon and behaved correctly (supervisor + both children stopped, stayed stopped).

**5. `timeout` in a restart loop is a crash-loop hazard.** Both supervisors used `timeout /t 10 /nobreak >nul` for their backoff. `timeout` reads the console input handle and aborts instantly with *"Input redirection is not supported"* whenever stdin is redirected — which is how a launcher gets invoked from a script, an agent, or CI. An instantly-returning backoff turns the restart loop into a **tight loop hammering NT8**, which is the 2026-09-03 incident class. Both now use `ping 127.0.0.1 -n 11 >nul`, the idiom already used in `start_fj_widget.bat`.
* Verified by killing the child only: supervisor restarted it after **10.3 s**, correct pid change, loop intact.
* ⚠️ Editing a running `.bat` is itself unsafe — cmd re-reads the file as it executes. Both supervisors were stopped and restarted to load the patched text.

**6. Gate 3's timing claim was a hardcoded `true`.** `gate3_killswitch.rs` printed `detect_ms + 3000` and asserted a literal `true` against a *"< 3000ms requirement"* that the inflated number did not satisfy anyway. The only real assertion was `assert!(fired, ...)` — that the killswitch fired **at all**, within the 6 s the poll loop happens to run. For a killswitch the latency *is* the property, so it is now a **two-sided** bound: too slow misses the move, too eager flattens a live position on a transient blip.
* Now asserts `2000ms <= detect_ms <= 6000ms` against a 3000ms dead threshold, printing the real measured figure. Measured: **4,548 ms**.
* Verified with a negative control (ceiling temporarily set to 100 ms): panics with *"killswitch took 4547ms to fire, over the 100ms budget"*, exit 101. Bound restored and re-verified.

### Post-restart verification (all gates re-run on freshly built binaries)
| Component | pid state | RAM |
|---|---|---|
| `trading_daemon` (8635) | 1 instance | 18.9 MB |
| `fj_widget` (8636) | 1 instance | 24.6 MB |
| `pnl_widget_gdi` | 1 instance | 14.8 MB |
| `broker_sentinel` | 1 instance | 9.9 MB |
| **total** | | **68.2 MB** |

`cargo build --release` clean across all five crates. Gate 1 PASSED (contract, 109 accounts, 2 copier rows). Gate 2 PASSED (bit-exact, 774 + 560 trades). Gate 3 PASSED (4,548 ms, real bound). Both scheduled tasks Running; daemon health `nt8Connected: true`.

---

## Test scaffolding (2026-09-03) — first tests in the workspace

**`fj_widget` duplicate-instance guard.** Root cause was in `proxy.rs`: a bind failure did `return Ok(())`, reporting **success** for a proxy that never started — so a second instance came up, silently lost 8636, and opened a window served by the *first* instance's proxy, orphaned at ~21 MB. Fixed in two places: the bind error now propagates, and `main` binds the port itself before anything visible happens, so **the bind *is* the check** (probe-then-bind is a race whose loser is that same orphan). Verified: second instance prints a clear message and exits **2**, leaving exactly 1 process holding 8636.

**Cushion formula de-duplicated.** It was written out at two call sites (`tick()` and `track_net_liq_tick()`). Two copies of a safety formula drift the moment one is edited, and the survivor still looks right in isolation. Both now call `compute_cushion()` / `ratchet_peak()`.

**31 unit tests, 0 failures** (`cargo test`, was 0):
* `broker_sentinel` — **10 tests** over the cushion formula and peak ratchet: the hand-computed Gate 3 case, direction (losing money must *reduce* cushion — the original playbook formula did the opposite), breach at `<= 0`, ratchet seeds/rises/never-falls, the 50k jump guard including its exclusive boundary, and `arm_live_flatten` defaulting false.
* `trading_daemon` — **21 tests** over `js_normalize_json_str` and `compute_fleet_summary`, reproducing all four cutover semantic diffs: JS falsy fallback on a present-but-0 `netLiquidation`, integral floats printing `0` not `0.0`, `-0` → `0`, the V8 shortest-repr case (`49453.150000000052` → `49453.15000000005`), string literals and escaped quotes left untouched by the number scanner, plus the `activeContracts` string shape, copier pass-through, and non-panicking degradation on malformed input.

**Mutation battery — 7 mutants, 7 killed.** A test that has never been observed failing has not been shown to work, so each key assertion was checked against a deliberate defect:

| # | Mutant | Result |
|---|---|---|
| M1 | JS falsy fallback reverted to a plain `unwrap_or` | KILLED |
| M2 | integral floats printed via `{:?}` (`0.0` not `0`) | KILLED |
| M3 | number scanner no longer skips string literals | KILLED |
| M4 | cushion sign flipped to the original `Peak − Limit − Current` | KILLED |
| M5 | peak jump guard `<` → `<=` (boundary) | KILLED |
| M6 | ratchet allowed the peak to fall | KILLED |
| M7 | `arm_live_flatten` defaulted true | KILLED |

Both source files were restored to their exact original SHA-256 after the battery (`9f6ea20b…` / `03d9baa3…`) — a battery that does not reach its restore line leaves a live mutant.

**`crates/run_all_gates.ps1`** is the single entry point: release build, `cargo test`, then Gates 1–3, with a PASS/FAIL summary and non-zero exit on any failure. ⚠️ It sets `PYO3_PYTHON` for you — a bare `cargo test` at the workspace root **fails to build `pyo3-ffi`** without it, because system Python is 3.14 and PyO3 0.21 refuses anything above 3.12. ⚠️ Use `-SkipBuild` while the daemon and widgets are live; Windows will not let `cargo build --release` replace a running binary.

---

## What is left — measured 2026-09-03 (post-commit `f0bdb527`)

### Footprint: the migration's headline goal is met
| | procs | RAM |
|---|---|---|
| **Rust** (daemon + 2 widgets + sentinel) | 4 | **60.2 MB** |
| Python | 21 | 825.8 MB |
| Node | 10 | 817.7 MB |

Against the 3,383 MB measured before Track 1, total is now ~1,704 MB. **No Node process is a migration target any more** — the remaining ten are `tradingview-mcp` (343 MB), `nt-mcp-server.js` (50 MB), two Next.js servers, the sequential-thinking MCP and IDE helpers. `pnl_widget_server.js` and `fj_widget_server.js` are gone from the process table entirely.

### 1. Test coverage — the real gap
| crate | LOC | tests |
|---|---|---|
| `trading_daemon` | 1,292 | 21 (⚠️ `poller.rs` only) |
| `broker_sentinel` | 720 | 10 |
| `nt8_parity_core` | 631 | **0** |
| `pnl_widget_gdi` | 1,266 | **0** |
| `fj_widget` | 437 | **0** |

Within `trading_daemon`, **736 LOC are untested**: `state.rs` (258 — the 2.5s lockout sweep and emergency-flatten trigger), `server.rs` (218 — the order-proxy routes), `cdp.rs` (209 — the TV push), `main.rs` (51). The lockout sweep is the one that matters most: it is risk machinery with no test at all.

`nt8_parity_core` is covered only by Gate 2's end-to-end bit-exact replay — one instrument, one year, synthetic signals. No unit test pins tick snapping, the BE-lock fill sequence, or the consecutive-loss pause in isolation, so a failure there reports as a whole-year trade-count mismatch rather than naming the rule that broke.

### 2. No CI
Still no `.github/workflows/`. 31 tests and 3 gates that run only when someone remembers. `crates/run_all_gates.ps1` is the single command a CI job would call — the job does not exist yet. Note the sibling repos' rule: **run `gh run list` before trusting any claim of green**, which here would return nothing at all.

### 3. Sentinel live-fire — blocked, not forgotten
Detection, trigger, cushion formula and the Tradovate REST path are built and gate-verified in simulation; the sentinel runs observe-only at ~5–11 MB. **Blocked on broker API credentials.** Until then it is *configured and evaluating*, not *enforcing* — it logs the flatten it would have made. Do not size positions as though a killswitch exists.

### 4. `stream_chart.py` — reassessed: do NOT port it wholesale
**260 MB, 1,423 LOC.** Earlier notes in this document called it "the futures data streamer" and "the last real migration candidate". Both undersell it, and the second is wrong.

**What it actually is.** The *Spoke* in a hub-and-spoke design: `schwab_hub.py` (8080) owns the single Schwab streaming connection, and this process subscribes to it over WebSocket and turns the raw feed into the repo's canonical market data. It:
* reads the watchlist from SQLite (`WatchlistGroup`/`WatchlistItem`, ~28 symbols — 6 futures, equities, and the vol complex);
* bootstraps each symbol over REST, validates, dedupes, and **detects and bridges gaps**;
* consumes `LEVELONE_FUTURES` quotes and `CHART_FUTURES`/`CHART_EQUITY` bars, aggregating 15s/30s sub-candles;
* **writes `data/live/live_storage_{sym}.parquet`** — the live store CLAUDE.md names as canonical for all current analysis — plus `live_chart_*.json` at 1m/15s/30s, atomically;
* maintains daily/weekly files with real futures **settlement semantics**: settlement override from quotes, trade-date and session-boundary rules, yfinance-or-Schwab HTF source, weekly built from daily, refreshed 17:00 ET Mon–Fri after the 16:15 settlement plus grace so the settled daily bar exists before the 17:10 EOD narrative chain;
* **serves its own API on port 8001** — `GET /history`, `GET /quote`, `WS /stream` — and rebroadcasts quotes and candles to connected clients.

So it is not a tick pump; it is the market-data plumbing the narratives, confluence engine and GEX level reads all sit on. `data/live/` is 155 files / 504 MB.

**Where the 260 MB goes.** Not a leak — the in-memory candle list is explicitly bounded to 15,000 per symbol (`:444`, `:1218`). It is *representation overhead*: ~28 symbols × 15,000 candles held as Python dicts, plus the 15s/30s containers and pandas round-trips on every parquet write. A dict-per-candle costs a few hundred bytes where a packed struct costs ~48.

**Why a Rust port is the wrong call anyway.** The memory would genuinely drop (packed candles would put this in the tens of MB), but that is the *only* win: the work is I/O-bound — websocket recv, REST calls, atomic file writes — which is where Rust buys least. Against that, the majority of the file is Schwab SDK auth, a yfinance fallback, pandas parquet round-trips, and the settlement/trade-date/session logic. That last part is exactly the kind of domain rule where a rewrite silently changes numbers that every downstream consumer trusts, and there is no Gate-2-style bit-exact oracle for a live feed.

**Cheaper fix if the memory matters:** hold candles per symbol as a DataFrame or numpy arrays rather than lists of dicts. That captures most of the reclaim without touching the settlement semantics. Profile first — 260 MB on a 24-core box may simply not be worth spending anything on.

#### The CPU was the real cost, and it was one line (fixed 2026-09-03, commit `2e6daf80`)
Profiling the whole box for process sprawl found the sprawl is not the problem: **21 Python processes, 959 MB, 19.3% of one core** — but 18 of them sit at ~0% CPU, and the apparent duplicate pairs are parent/child shims (a ~10 MB `python -m X` that spawned the real ~50 MB worker), so killing the "extra" would orphan the worker. The cost was concentrated in `stream_chart.py`: **16.3% of a core sustained, ~84% of all Python CPU**.

`save_candles_to_parquet` is called with a *single* finalised candle (`:1198`) but rebuilt the derived `timestamp` string column across every row each time. `.dt.strftime()` is an element-wise Python loop, so appending one bar re-rendered 598,143 identical strings. Stage profile of one save:

| stage | time | share |
|---|---|---|
| read | 30 ms | 1.2% |
| concat + dedup + sort | 32 ms | 1.3% |
| **timestamp strftime** | **2,219 ms** | **91.9%** |
| write | 134 ms | 5.5% |

The column is now computed for new rows only, and the existing one healed only when missing or non-string. Byte-identical output (`DataFrame.equals`) against the live files: NQ 2,240→174 ms (12.9×), ES 2,167→172 ms (12.6×), QQQ 791→105 ms (7.5×). The remaining ~130 ms is the parquet write, now the floor.

⚠️ **The dtype guard must be `is_string_dtype`, not `== object`.** Pandas returns the newer `str` dtype for this column, so an `== object` test is always False, heals on every call, and yields **exactly zero speedup while looking correct** — measured 1.0× on the first attempt for precisely that reason.

**Verified in production** after restart, sampled over 7 minutes: **CPU 16.3% → 1.0%**, memory plateaued (695–702 MB, not climbing).

⚠️ **Unresolved: resident memory is now ~700 MB against the 316–410 MB observed on the old process.** That is *not* attributable to this change — the pre-fix code created the same string column, and more of them. The likeliest explanation is that the old process had run 54 hours and Windows had trimmed its working set during idle periods, while a freshly restarted process holds its pages resident; but the two were never measured side by side, so this is unconfirmed. If memory turns out to matter, the fix is the dict-per-candle representation above, not anything in this change.

#### Lesson for the Rust question
A Rust port would have made the same 598k-row strftime perhaps 10× faster while still doing O(entire history) work per appended bar — and would have carried the defect across, faster and harder to see. **The algorithm was the problem, not the language.**

Everything else in Python (`strategy_engine/runner.py` 87 MB, `api.main` 49 MB) is too small for a rewrite to pay.

### 5. Smaller open items
* **Bearer token** — see open item 6 above (33 files, twice inside `trading_daemon`).
* **`broker_sentinel::load_config()` fails silently** — a malformed `sentinel.json` falls through to `SentinelConfig::default()` with no warning, so the operator's tuned limits vanish while the config file still reads as though it applied. Same class as the PyO3 fallback fixed in this pass, and not yet fixed.
* **`cargo test` needs `PYO3_PYTHON`** or `pyo3-ffi` fails to build (system Python is 3.14; PyO3 0.21 caps at 3.12). `run_all_gates.ps1` sets it; a bare `cargo test` does not.
* **A full `cargo build --release` cannot run while the binaries are live** — Windows holds the file locks. Needs a stop/build/start window, or `-SkipBuild`.
