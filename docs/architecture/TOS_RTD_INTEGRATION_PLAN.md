# TOS RTD Futures Options Integration Plan

**Date:** July 7, 2026
**Source Repo:** [2187Nick/tos-streamlit-dashboard](https://github.com/2187Nick/tos-streamlit-dashboard/tree/futures) (futures branch)
**Target System:** `tvDownloadOHLC` options streaming pipeline (`scripts/streaming/options/`)

---

## 1. Executive Summary

The `tos-streamlit-dashboard` (futures branch) is a Windows-only Python app that uses **ThinkorSwim's RTD (Real-Time Data) COM server** to stream live futures options Greeks (Gamma, Open Interest, Volume, Last price) directly from the TOS desktop application — no REST API, no rate limits, no auth tokens. It builds futures option symbols (e.g. `./NQH25C21000:XCME`) for `/ES`, `/NQ`, `/ZN`, `/CL`, `/GC`, `/SI` and subscribes to RTD topics for each.

Our current system (`run_options_levels.py`) pulls option chains from the **Schwab API** on a polling schedule (T1/T2 intervals), computes GEX/walls/zero-gamma via `gex_calculator.py`, translates cash→futures via `futures_translator.py`, and persists to Prisma + JSON + Discord.

**The integration opportunity:** Use TOS RTD as a **real-time supplementary feed** for futures options Greeks (Gamma, OI, Volume, Last) to complement our Schwab polling pipeline — giving us sub-second updates during RTH without API rate-limit constraints.

---

## 2. Architecture Comparison

```mermaid
flowchart LR
    subgraph CURRENT["Current System (Schwab API)"]
        SchwabAPI["Schwab REST API"] -->|Poll T1/T2 intervals| Fetcher["options_fetcher.py"]
        Fetcher --> GEX["gex_calculator.py"]
        GEX --> Scorer["level_scorer.py"]
        Scorer --> Translator["futures_translator.py"]
        Translator --> PrismaDB[("Prisma SQLite")]
        Translator --> JSON["daily_levels.json"]
        Translator --> Discord["Discord"]
    end

    subgraph TOS["TOS RTD System (New)"]
        TOSApp["TOS Desktop (COM RTD Server)"] -->|COM IRtdServer| RTDClient["RTDClient"]
        RTDClient -->|Queue| RTDWorker["RTDWorker"]
        RTDWorker -->|dict[symbol:quote_type]| Streamlit["Streamlit Dashboard"]
    end

    subgraph BRIDGE["Integration Bridge (New)"]
        RTDWorker -->|Normalized quotes| Adapter["tos_rtd_adapter.py"]
        Adapter -->|Greeks snapshot| GEX
        Adapter -->|Futures last price| Translator
    end
```

### Key Differences

| Aspect | Our Schwab Pipeline | TOS RTD Dashboard |
|---|---|---|
| **Data source** | Schwab REST API (HTTP polling) | TOS desktop COM RTD (push-based) |
| **Auth** | OAuth tokens, refresh cycles | None (TOS desktop must be running) |
| **Rate limits** | Yes (Schwab API limits) | None (local COM) |
| **Update latency** | T1/T2 interval (seconds–minutes) | ~50ms first data, ~1s steady state |
| **Platform** | Cross-platform | **Windows only** (COM/pythoncom) |
| **Futures options symbols** | Schwab API format | TOS RTD format (`./NQH25C21000:XCME`) |
| **Greeks available** | Computed via BSM in `gex_calculator.py` | **Native from TOS**: GAMMA, DELTA, OPEN_INT, VOLUME, LAST, MARK |
| **GEX calculation** | Full BSM analytical model | Dashboard does simple gamma exposure display |
| **Persistence** | Prisma + JSON + Discord | In-memory only (Streamlit session) |

---

## 3. What TOS RTD Provides That We Need

### A. Real-Time Futures Option Greeks (Native, No BSM Computation)

The RTD worker subscribes to these `QuoteType` fields per option symbol:

| QuoteType | Description | Our Current Source |
|---|---|---|
| `GAMMA` | Native gamma from TOS | Computed via BSM in `gex_calculator.py` |
| `OPEN_INT` | Open interest | From Schwab chain JSON |
| `VOLUME` | Volume | From Schwab chain JSON |
| `LAST` | Last traded price | From Schwab chain JSON |
| `MARK` | Mark price | From Schwab chain JSON |
| `DELTA` | Native delta from TOS | Computed via BSM |
| `IMPL_VOL` | Implied volatility | From Schwab chain JSON |

**Advantage:** TOS provides exchange-quality Greeks natively — no model drift from our BSM assumptions. This can serve as a **validation oracle** for our analytical Greeks.

### B. Futures Option Symbol Builder (Already Handles Complex Rules)

The `OptionSymbolBuilder` class handles the complex futures option symbology that we currently don't fully implement:

- **`/ES`**: Quarterly (AM-settled `ESH25` + PM-settled `EWH25`), weekly (`E1W25`, `EW1W25`), EOM (`EWM25`)
- **`/NQ`**: Quarterly (`NQH25` + `QN1H25`), weekly (`QN1W25`, `Q1WH25`), EOM (`QNEM25`)
- **`/ZN`**: Quarterly AM (`OZNH25`), weekly Mon (`VY1H25`), Wed (`WY1H25`), Fri (`ZN1H25`)
- **`/CL`, `/GC`, `/SI`**: Standard futures format (`CL1F25`, `GC1G25`)
- Exchange suffix mapping: `/ES→XCME`, `/NQ→XCME`, `/CL→XNYM`, `/GC→XCEC`, `/ZN→XCBT`

This is **more complete** than our current `futures_translator.py` which focuses on cash→futures basis translation but doesn't build futures option symbols.

---

## 4. Integration Plan

### Phase 1: Vendor the RTD Client Library (Week 1)

**Goal:** Extract the RTD COM client into our codebase as a reusable module, decoupled from Streamlit.

#### Files to Create

| File | Purpose |
|---|---|
| `scripts/streaming/options/tos_rtd/__init__.py` | Package init |
| `scripts/streaming/options/tos_rtd/client.py` | Port of `RTDClient` (COM client, `IRtdServer` interface) |
| `scripts/streaming/options/tos_rtd/interfaces.py` | Port of COM interface definitions (`IRtdServer`, `IRTDUpdateEvent`) |
| `scripts/streaming/options/tos_rtd/worker.py` | Port of `RTDWorker` — background thread that pumps COM messages and emits quotes to a queue |
| `scripts/streaming/options/tos_rtd/quote_types.py` | `QuoteType` enum (GAMMA, DELTA, OPEN_INT, VOLUME, LAST, MARK, IMPL_VOL) |
| `scripts/streaming/options/tos_rtd/symbol_builder.py` | Port of `OptionSymbolBuilder` — futures option symbol construction |
| `scripts/streaming/options/tos_rtd/settings.py` | RTD settings (GUIDs, heartbeat intervals, progid) |

#### Key Adaptations from Source → Our Codebase

1. **Remove Streamlit dependency**: The `RTDWorker` currently puts data into a `Queue` consumed by Streamlit. We keep the queue pattern but our consumer is the adapter (Phase 2).
2. **Add structured logging**: Replace `print()` calls with `logging.getLogger(__name__)` per our conventions.
3. **Add proper type hints**: Follow our `from __future__ import annotations` convention.
4. **Add `comtypes` to requirements**: Add `comtypes>=1.4` and `pywin32` to `requirements.txt` (Windows-only, guarded by `sys.platform`).

#### Dependencies

```
# requirements.txt (Windows-only section)
comtypes>=1.4.8; sys.platform == 'win32'
pywin32>=306; sys.platform == 'win32'
```

---

### Phase 2: Build the TOS→System Adapter (Week 2)

**Goal:** Create an adapter that consumes RTD quotes and feeds them into our existing GEX/level pipeline.

#### File: `scripts/streaming/options/tos_rtd/adapter.py`

```python
"""
TOS RTD → System Adapter
========================
Consumes real-time RTD quotes and produces normalized snapshots
compatible with our GEX calculator and futures translator.
"""
```

**Core class: `TOSRTDAdapter`**

| Method | Description |
|---|---|
| `__init__(config)` | Initializes RTD client, symbol builder, output queue |
| `start(symbols, expiry)` | Spawns RTD worker thread for given futures + option symbols |
| `stop()` | Clean shutdown (disconnect COM, join thread) |
| `get_snapshot() → dict` | Returns latest `{symbol: {GAMMA: ..., OPEN_INT: ..., VOLUME: ..., LAST: ...}}` |
| `get_futures_price(symbol) → float` | Returns latest futures LAST price (replaces Schwab `fetch_futures_quote`) |
| `build_chain_snapshot(symbol, expiry) → ChainData` | Converts RTD quotes into the `ChainData` format expected by `gex_calculator.py` |

#### Data Flow

```
TOS RTD Worker
    ↓ (Queue: {symbol: {GAMMA: 0.001, OPEN_INT: 5000, VOLUME: 200, LAST: 5.25, ...}})
TOSRTDAdapter
    ↓ (Normalizes to ChainData format)
    ↓ (Maps RTD symbols → strike/expiry/call-put)
gex_calculator.calculate_dealer_levels()
    ↓ (DealerLevels)
level_scorer.score_levels()
    ↓ (ScoredLevels)
futures_translator.translate_to_futures()
    ↓ (TranslatedLevels)
file_writer / Prisma / Discord
```

#### Symbol Mapping (RTD → Our Format)

The adapter must map TOS RTD option symbols back to strike/expiry/type:

| RTD Symbol | Parsed Fields |
|---|---|
| `./NQH25C21000:XCME` | Product: `NQH25`, Strike: `21000`, Type: `Call`, Exchange: `XCME` |
| `./EWH25P5950:XCME` | Product: `EWH25`, Strike: `5950`, Type: `Put`, Exchange: `XCME` |
| `./CL1G25C7500:XNYM` | Product: `CL1G25`, Strike: `7500`, Type: `Call`, Exchange: `XNYM` |

A `parse_rtd_option_symbol(symbol) → OptionContract` utility will be added to `symbol_builder.py`.

---

### Phase 3: Hybrid Data Mode (Week 3)

**Goal:** Run TOS RTD alongside Schwab API, using RTD for real-time updates and Schwab for full chain snapshots.

#### File: `scripts/streaming/options/tos_rtd/hybrid_coordinator.py`

**Strategy:**

1. **Schwab API (existing)**: Full chain snapshot at T1/T2 intervals (provides complete OI, volume, IV across all strikes). This remains the **primary source** for GEX/wall calculations.
2. **TOS RTD (new)**: Sub-second updates for subscribed strikes. Used for:
   - **Real-time futures LAST price** → feeds `futures_translator` basis calculation (replaces Schwab `fetch_futures_quote` polling)
   - **Real-time gamma/OI updates** → incremental GEX recalculation between Schwab snapshots
   - **Greeks validation** → compare TOS native gamma vs our BSM-computed gamma for model drift monitoring

#### Integration Point in `run_options_levels.py`

```python
# In the main pipeline loop, add RTD as an optional real-time source:

if config.ENABLE_TOS_RTD and sys.platform == 'win32':
    rtd_adapter = TOSRTDAdapter(config.TOS_RTD_CONFIG)
    rtd_adapter.start(symbols=[config.ES_FUTURES_SYMBOL, config.NQ_FUTURES_SYMBOL],
                       expiry=nearest_expiry)

    # In the loop, between Schwab snapshots:
    rtd_snapshot = rtd_adapter.get_snapshot()
    if rtd_snapshot:
        futures_price = rtd_adapter.get_futures_price('/ES')
        # Use RTD price for more accurate basis translation
        translated = translate_to_futures(dealer_levels, futures_price, ...)
```

#### Config Additions (`config.py`)

```python
# TOS RTD Configuration
ENABLE_TOS_RTD: bool = False  # Opt-in, Windows-only
TOS_RTD_HEARTBEAT_MS: int = 5000
TOS_RTD_POLL_INTERVAL_S: float = 1.0  # Steady-state poll rate
TOS_RTD_INIT_RETRIES: int = 3
TOS_RTD_STRIKE_RANGE: int = 20  # ± strikes from ATM
TOS_RTD_STRIKE_SPACING: float = 1.0
TOS_RTD_SYMBOLS: list[str] = ["/ES", "/NQ"]  # Futures to monitor via RTD
```

---

### Phase 4: Persistence & Monitoring (Week 4)

**Goal:** Persist RTD snapshots and add monitoring dashboards.

#### A. Prisma Schema Addition

```prisma
model TOSRTDSnapshot {
  id          String   @id @default(cuid())
  symbol      String   // e.g. "./NQH25C21000:XCME"
  quoteType   String   // GAMMA, OPEN_INT, VOLUME, LAST, etc.
  value       Float
  capturedAt  DateTime @default(now())

  @@index([symbol, capturedAt])
  @@index([capturedAt])
}
```

#### B. Greeks Drift Monitor

A new script `scripts/streaming/options/tos_rtd/greeks_drift_monitor.py` that:
- Compares TOS native gamma/delta vs our BSM-computed values
- Logs drift percentage: $\text{Drift}_\% = \frac{|\Gamma_{\text{TOS}} - \Gamma_{\text{BSM}}|}{\Gamma_{\text{TOS}}} \times 100$
- Alerts if drift exceeds threshold (e.g., >5%) — indicates our BSM model assumptions (rate, dividend yield) need recalibration

#### C. Health Dashboard

Add RTD connection status to the existing Discord/web dashboard:
- RTD connection state (CONNECTED/DISCONNECTED)
- Active topic count
- Last update timestamp
- Heartbeat interval

---

## 5. Risk Assessment & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Windows-only** (COM/pythoncom) | Can't run on Linux servers | Guard with `sys.platform == 'win32'`; Schwab API remains primary fallback. RTD runs as an optional sidecar on a Windows machine. |
| **TOS desktop must be running** | No data if TOS crashes/closes | Health monitor + auto-reconnect logic (already in `RTDWorker._init_com_with_retry`) |
| **Symbol format mismatch** | Wrong strikes/expiries parsed | Comprehensive `parse_rtd_option_symbol()` with unit tests covering all product code formats (quarterly, weekly, EOM) |
| **COM threading issues** | Deadlocks or stale data | RTD worker runs in dedicated thread with `pythoncom.CoInitialize()` per thread (already handled in source) |
| **Duplicate GEX calculations** | Conflicting levels | RTD is supplementary only; Schwab API remains the **source of truth** for persisted levels. RTD updates are tagged with `source: 'tos_rtd'` in the DB. |
| **Futures option symbology complexity** | Wrong symbols subscribed | Port the full `OptionSymbolBuilder` with all edge cases (quarterly AM/PM, weekly Mon/Wed/Fri, EOM). Add test coverage for each futures type. |

---

## 6. Testing Plan

### Unit Tests (`tests/test_tos_rtd/`)

| Test File | Coverage |
|---|---|
| `test_symbol_builder.py` | All futures symbol formats: `/ES` quarterly/weekly/EOM, `/NQ` quarterly/weekly/EOM, `/ZN` quarterly/weekly, `/CL` `/GC` `/SI` standard |
| `test_symbol_parser.py` | Reverse parsing: `./NQH25C21000:XCME` → `(product=NQH25, strike=21000, type=Call, exchange=XCME)` |
| `test_adapter.py` | Mock RTD queue data → verify `ChainData` output format matches `gex_calculator.py` expectations |
| `test_hybrid.py` | Mock both Schwab + RTD sources → verify coordinator picks RTD price for basis, Schwab for full chain |

### Integration Tests (Windows-only, marked `@pytest.mark.skipif`)

| Test | Description |
|---|---|
| `test_rtd_connection` | Connect to live TOS RTD, subscribe to `/ES:XCME` LAST, verify data arrives within 5s |
| `test_rtd_option_subscribe` | Subscribe to `./ESH25C5500:XCME` GAMMA + OPEN_INT, verify non-null values |
| `test_rtd_disconnect` | Verify clean disconnect, no COM leaks |

---

## 7. Implementation Checklist

### Phase 1: Vendor RTD Library
- [ ] Create `scripts/streaming/options/tos_rtd/` package
- [ ] Port `interfaces.py` (COM interface definitions)
- [ ] Port `client.py` (RTDClient with COM error handling)
- [ ] Port `worker.py` (RTDWorker background thread)
- [ ] Port `quote_types.py` (QuoteType enum)
- [ ] Port `symbol_builder.py` (OptionSymbolBuilder with all futures types)
- [ ] Port `settings.py` (RTD GUIDs, heartbeat config)
- [ ] Add `comtypes` to `requirements.txt` (Windows-guarded)
- [ ] Write unit tests for symbol builder

### Phase 2: Build Adapter
- [ ] Create `adapter.py` (TOSRTDAdapter)
- [ ] Implement `parse_rtd_option_symbol()` utility
- [ ] Implement `build_chain_snapshot()` → ChainData conversion
- [ ] Implement `get_futures_price()` → replaces Schwab polling for futures LAST
- [ ] Write adapter unit tests with mocked RTD data

### Phase 3: Hybrid Mode
- [ ] Create `hybrid_coordinator.py`
- [ ] Add `ENABLE_TOS_RTD` + config to `config.py`
- [ ] Integrate RTD price feed into `run_options_levels.py` loop
- [ ] Add RTD-sourced gamma as validation overlay in GEX calculation
- [ ] Test hybrid mode end-to-end on Windows

### Phase 4: Persistence & Monitoring
- [ ] Add `TOSRTDSnapshot` model to Prisma schema
- [ ] Run `npx prisma db push`
- [ ] Create `greeks_drift_monitor.py`
- [ ] Add RTD health status to Discord notifications
- [ ] Add RTD metrics to web dashboard

---

## 8. File Structure After Integration

```
scripts/streaming/options/
├── config.py                          # + TOS_RTD_* config keys
├── run_options_levels.py             # + optional RTD integration in loop
├── gex_calculator.py                  # unchanged (receives RTD data via adapter)
├── level_scorer.py                    # unchanged
├── futures_translator.py              # + accepts RTD-sourced futures price
├── options_fetcher.py                 # unchanged (Schwab remains primary)
├── ezoptionsschwab.py                 # unchanged
├── file_writer.py                     # + RTD source tagging
├── tos_rtd/                           # NEW PACKAGE
│   ├── __init__.py
│   ├── client.py                      # RTDClient (COM client)
│   ├── interfaces.py                   # IRtdServer, IRTDUpdateEvent
│   ├── worker.py                      # RTDWorker (background thread)
│   ├── quote_types.py                 # QuoteType enum
│   ├── symbol_builder.py              # OptionSymbolBuilder (futures symbols)
│   ├── settings.py                    # RTD COM settings
│   ├── adapter.py                     # TOSRTDAdapter (RTD → our format)
│   ├── hybrid_coordinator.py          # Schwab + RTD coordination
│   └── greeks_drift_monitor.py        # BSM vs TOS gamma validation
└── ...
```

---

## 9. Key Design Decisions

1. **RTD is supplementary, not primary.** Schwab API remains the source of truth for persisted dealer levels. RTD provides real-time price updates and Greeks validation between Schwab snapshots.

2. **Windows-only, opt-in.** The entire `tos_rtd/` package is guarded by `sys.platform == 'win32'` and `config.ENABLE_TOS_RTD`. On Linux, the system runs exactly as it does today.

3. **No BSM replacement.** We do NOT replace our analytical Greeks engine with TOS native Greeks. TOS Greeks are used as a **validation oracle** and for **real-time incremental updates** between full chain snapshots.

4. **Symbol builder is the most valuable immediate asset.** Even without RTD, porting `OptionSymbolBuilder` gives us proper futures option symbol construction for `/ES`, `/NQ`, `/ZN` — which we currently lack. This alone improves our `weekly_futures_em.py` and `options_fetcher.py` capabilities.

5. **Queue-based decoupling.** The RTD worker communicates via a `Queue` (same pattern as source repo), keeping the COM thread isolated from our async/pipeline code.

---

## 10. References

- **Source repo:** https://github.com/2187Nick/tos-streamlit-dashboard/tree/futures
- **pyrtdc (RTD COM library):** https://github.com/tifoji/pyrtdc/
- **Our current pipeline:** `scripts/streaming/options/run_options_levels.py`
- **Our GEX engine:** `scripts/streaming/options/gex_calculator.py`
- **Our futures translator:** `scripts/streaming/options/futures_translator.py`
- **Our options inventory:** `docs/OPTIONS_INVENTORY.md`