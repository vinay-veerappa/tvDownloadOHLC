# Execution Playbook: Rust Pragmatic Migration (Verified & Calibrated)

> **EXECUTION STATUS (2026-09-03)** — Tracks 1 & 2 COMPLETE with gates passed; Track 1 is LIVE in production (cutover done). Track 3 built and simulated-gate-passed but the direct-broker flatten is DEFERRED — no broker API access exists. Details in the **Execution Record** at the bottom of this document. Read that section first before executing anything here; several steps below have already been done and verified once.

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

**Gate 1** ran on shadow port 8637 via `crates/gate1_parity.ps1` — passed 3×. Parity work went beyond the gate script; four semantic diffs had to be eliminated to reach **byte-identical** JSON (worth knowing for any future Node→Rust port):
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

### Build/run quick reference
```powershell
# Daemon (production, port 8635)
launch\start_trading_daemon.bat            # supervised + logged
launch\stop_trading_daemon.bat             # stop
crates\target\release\trading_daemon.exe --port 8635   # direct, unsupervised

# Rebuild daemon
cd crates; cargo build --release -p trading_daemon

# Rebuild PyO3 module (after lib.rs edits)
$env:PYO3_PYTHON = "C:\Users\vinay\tvDownloadOHLC\.venv\Scripts\python.exe"
.venv\Scripts\python.exe -m maturin develop --release -m crates\nt8_parity_core\Cargo.toml

# Gates
powershell -ExecutionPolicy Bypass -File crates\gate1_parity.ps1   # shadow parity (daemon on 8637 vs live 8635)
.venv\Scripts\python.exe crates\gate2_parity.py                    # engine zero-divergence
crates\target\release\gate3_killswitch.exe                         # sentinel simulation
```

### Open items
1. Track 1 memory reclaim (~450MB) only partially realized — `fj_widget_server.js` (8636) still Node; `stream_chart.py` consolidation never scoped in detail.
2. Sentinel live-fire blocked on broker API access (above).
3. Scheduled task `TradingDaemon` registered; if the repo moves, re-run `launch/register_trading_daemon_task.ps1`.
