# Options Pipeline Overhaul — Handover Spec

**Date:** July 10, 2026  
**Branch:** `main`  
**Last commit:** `9d5f795f` — pandas 3.0.3 upgrade + inplace fixes  

---

## What Was Done This Session

### Critical Bug Fixes
- [x] **EOD close sync**: Both futures and SPX pinned to 16:14 ET (official SPX close publication time), eliminating the 5-minute basis mismatch
- [x] **interval_writer**: Added missing `put25dIv`, `call25dIv`, `volatilitySkewPremium` to DB payload (were silently dropped)
- [x] **validate_greeks**: Fixed wrong attribute name (`gex_by_strike` → `strike_gex`) and gamma extraction in hybrid_coordinator
- [x] **`_is_trading_day`**: Fixed docstring placement
- [x] **RTD-native EOD pinning**: NQ/ES now get parquet close-price override at 16:15 snapshot

### RTD-Native Path Parity (NQ/ES)
- [x] Separate intraday + macro DealerLevels computed from RTD chain
- [x] Weekly scope capture/attachment (matching Schwab path)
- [x] `cash_levels_by_ticker` + `macro_levels_by_ticker` populated for unified output
- [x] Full `TranslatedLevels` appended to `translated_levels`/`translated_macro_levels`
- [x] DealerLevels tagged with futures metadata for DB snapshot
- [x] Macro TranslatedLevels built from macro DealerLevels (not partial copy)
- [x] DB snapshot write with correct intraday dealer levels
- [x] Unified output now includes full structural + META_ tokens for NQ/ES

### Black-76 Pricing Model
- [x] Implemented `_black76_d1d2`, `_black76_gamma`, `_black76_delta`, `_black76_charm` in gex_calculator.py
- [x] `_compute_black76_greeks` in rtd_gex_calculator.py replaces BSM fallback for RTD path
- [x] `is_futures` flag on `OptionChainData` — `_calc_per_strike_exposures` uses Black-76 when True
- [x] Schwab path (SPX, SPY, QQQ, etc.) continues using BSM unchanged

### RTD GEX Fix (GEX=0 Issue)
- [x] BSM/Black-76 gamma fallback when RTD returns GAMMA=0 (uses IV which RTD provides reliably)
- [x] Multi-expiry support: `expiry_map` on `ChainSnapshot`, per-contract expiry tracking
- [x] 0DTE/daily expiry support: today added to expiry ladder if weekday
- [x] VEGA + THETA subscriptions added to RTD worker (then reduced to 5 critical types)

### RTD Optimizations
- [x] Schwab-discovered expiry list (tries `get_option_chain` then `get_quotes` fallback)
- [x] Expiry list cached with 1-hour TTL
- [x] Quote type reduction: 8 → 5 (GAMMA, OPEN_INT, VOLUME, IMPL_VOL, LAST)
- [x] Adaptive sleep in `calculate_rtd_gex` (polls for data instead of hardcoded sleep)
- [x] Configurable `num_expiries` per symbol (6 for /ES and /NQ, 4 for others)
- [x] Per-symbol `min_oi_floor` in `TOS_RTD_SYMBOL_CONFIG` (/ES=50, /NQ=25, etc.)

### Config Changes
- [x] NDX added to `ACTIVE_TICKERS`; NDX/RUT/DJX profiles and INDEX_TO_FUTURES entries added
- [x] `ETF_FALLBACK` emptied (ETF→index rescaling removed — mathematically wrong)
- [x] `rescale_levels_to_target_spot` usage removed from run_options_levels.py
- [x] EOD close times synced to 16:14 ET
- [x] RTH comment fixed (8:20 not 9:20)

### Output Cleanup
- [x] `daily_levels.json` write removed (was identical duplicate of `intraday_levels.json`)
- [x] Web interface updated to read `intraday_levels.json` (data.ts, route.ts)
- [x] `expected_move.py` updated to check `intraday_levels.json` first
- [x] API snapshot route updated to accept skew/IV fields

### Package Upgrades (Global Python 3.14)
- [x] fastapi 0.124→0.139 (fixed Hub crash)
- [x] pandas 2.3.3→3.0.3 (CoW default, 36% faster parquet read, 44% faster resample)
- [x] yfinance 1.2→1.5.1, TA-Lib 0.6.8→0.7.0
- [x] uvicorn, numpy, scipy, requests, pyarrow, pydantic, etc. upgraded
- [x] All `inplace=True` fixed in runtime paths (11 files, 24 fixes)

---

## TODO — Things Still To Do

### 🔴 High Priority

#### 1. Verify RTD GAMMA data when Hub + TOS are running
The BSM/Black-76 fallback was implemented because RTD returned GAMMA=0. But we couldn't verify if this is a permanent issue or just because the pipeline ran without the Hub. When TOS desktop is running during RTH:
- Check if GAMMA values come through natively from RTD
- If they do, the Black-76 fallback won't trigger and we'll have exchange-quality Greeks
- If GAMMA is still 0, the Black-76 fallback will compute gamma from IV (which works but is model-based, not exchange-native)

**How to test:** Start the Hub + TOS, run `python -m scripts.streaming.options.run_options_levels --tickers NQ,ES`, check `dealer_levels.log` for "Black-76 fallback" messages. If no fallback messages, RTD GAMMA is working.

#### 2. Verify Schwab `get_option_chain` works for futures symbols
- [x] **Status:** Verified — `get_option_chain` consistently returns 400 Bad Request for futures symbols.
- [x] **Resolution:** Removed the call from `hybrid_coordinator.py`. The system now proceeds directly to `get_quotes` (via `fetch_futures_option_chain_data`) for expiry discovery on futures.
- [ ] **Pending:** OI-based strike pruning (Item 4) is now deferred until a working high-OI discovery method is found, as `get_option_chain` was the intended source.

#### 3. Test the full pipeline end-to-end with Hub running
All changes were made and verified at the code level, but the full pipeline (Hub → Schwab chains → RTD Greeks → GEX calculation → unified output → DB write → web display) hasn't been tested end-to-end with all components running simultaneously.

**How to test:**
```bash
# Start Hub
python -m scripts.streaming.schwab_hub --port 8080

# In another terminal, run the pipeline
python -m scripts.streaming.options.run_options_levels --tickers SPX,SPY,NDX,QQQ,NQ,ES

# Verify outputs
# 1. Check unified_levels.txt has full NQ and ES entries with META_ tokens
# 2. Check GexSnapshot DB rows for /NQ and /ES have non-zero totalGex
# 3. Compare NQ levels vs QQQ×41.68 translated levels — should be in same ballpark
# 4. Compare ES levels vs SPX+42.61 translated levels — should be very close
```

### 🟡 Medium Priority

#### 4. OI-based strike pruning for RTD
If Schwab `get_option_chain` works for futures (item 2), we can extract strikes with OI > `min_oi_floor` and only subscribe to those via RTD. This would reduce COM topics by ~40-60% beyond the current optimizations.

**File:** `scripts/streaming/options/tos_rtd/hybrid_coordinator.py` — in the Schwab discovery block, also extract strike lists with OI > 0 and pass them to the adapter for symbol filtering.

#### 5. Fix remaining `inplace=True` in analysis/debug scripts
~175 `inplace=True` calls remain in analysis, debug, and data-processing scripts. These work with pandas 3.0 (CoW makes them safer) but should be migrated for consistency.

**How:** Run the PowerShell regex replacement (used for market_data scripts) across `scripts/analysis/`, `scripts/debug/`, `scripts/data_processing/`, `scripts/nqstats/`, `scripts/derived/`, `scripts/context/`, `scripts/edgeful/`.

#### 6. Web DB schema expansion for full dashboard replacement of JSON
The `GexSnapshot` table currently stores: totalGex, regime, spotPrice, gammaMagnet, pinStrike, centroids, vanna, skew/IV fields, futures translation fields. But the web v3 dashboard still reads from `intraday_levels.json` and `pipeline_state.json` for:
- `call_wall`, `put_wall`, `zero_gamma` (not in DB)
- `scored_analysis` (tagged levels — not in DB)
- `coach_note`, `tactical_plan` (not in DB)
- `expected_moves` (not in DB)

To fully replace JSON with DB, add these columns to `GexSnapshot`:
```prisma
callWall       Float?
putWall        Float?
zeroGamma      Float?
secondaryCallWall Float?
secondaryPutWall  Float?
callWall0dte   Float?
putWall0dte    Float?
hedgeWall      Float?
maxPain        Float?
wallSeparation Float?
directionalBias String?
```

Then update `interval_writer.py` to include them in the payload, and update the web API to read from DB instead of JSON.

#### 7. Prisma Python 3.14 compatibility
Prisma 0.15.0 emits a `UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater`. It still works but this warning may become an error in future prisma releases. Monitor for prisma-client-py updates that support Pydantic V2 natively on Python 3.14.

### 🟢 Low Priority

#### 8. Per-symbol quote type profiles
/ES options are very liquid and TOS reliably streams GAMMA. /NQ weekly options may not. Could subscribe to GAMMA only for /ES and rely on Black-76 for /NQ, further reducing NQ COM topics.

#### 9. Cache the Schwab expiry list to disk (not just in-memory)
The current 1-hour TTL cache is in-memory (`self._cached_expiries`). For the `--loop` mode, the coordinator persists across cycles so the cache works. But for `--schedule` mode (which creates a new process per run), the cache is lost. Consider writing to a temp file like `data/options/.rtd_expiry_cache.json`.

#### 10. Upgrade pandas in the `.venv` as well
The `.venv` still has pandas 2.3.3. If any scripts are run with the venv Python, they'll use 2.x. Either upgrade the venv too or document that all runtime scripts should use the global Python 3.14.

#### 11. Narrative Engine — test with new pipeline outputs
The trader narrative engine (`trader_narrative.py`) was updated to use `intraday_levels.json` instead of `daily_levels.json`, and to prefer `NQ`/`ES` keys over `QQQ`/`SPY` fallbacks. Test the full narrative chain:
```bash
python -m scripts.trader.trader_narrative --mode premarket --no-discord
python -m scripts.trader.trader_narrative --mode open --no-discord
python -m scripts.trader.trader_narrative --mode intraday --no-discord
python -m scripts.trader.trader_narrative --mode close --no-discord
```

---

## Architecture Notes

### Two Pricing Models
- **BSM (Black-Scholes-Merton)**: Used for Schwab path (SPX, SPY, QQQ, NDX, etc.) where the underlying is a spot price. Cost-of-carry $(r-q)$ is explicit in $d_1$.
- **Black-76**: Used for RTD-native path (NQ, ES) where the underlying is the futures price. No cost-of-carry drift in $d_1$ — the futures price already embeds the forward curve. This is the CME industry standard.

### Three Data Paths
1. **Schwab path** (SPX, SPY, QQQ, NDX, IWM, DIA, single stocks): Full option chain from Schwab API → BSM Greeks → additive/multiplicative futures translation
2. **RTD-native path** (NQ, ES): Futures options from TOS RTD COM → native Greeks (with Black-76 fallback) → direct futures levels (no translation needed)
3. **RTD cross-check** (in Schwab path for SPX→/ES, NDX→/NQ): RTD GEX computed alongside Schwab-translated levels for comparison. When `TOS_RTD_GEX_AS_PRIMARY=True`, RTD levels replace the translated ones.

### Key Config Locations
- `scripts/streaming/options/config.py` — all pipeline settings, ticker profiles, RTD config
- `scripts/streaming/options/tos_rtd/TOS_RTD_SYMBOL_CONFIG` — per-symbol RTD strike tiers, num_expiries, min_oi_floor
- `EOD_FUTURES_CLOSE_TIME` / `EOD_SPX_CLOSE_TIME` — both set to `time(16, 14)` (official SPX close)

### Key Files Modified This Session
| File | Changes |
|---|---|
| `config.py` | EOD times, NDX/RUT/DJX profiles, ETF_FALLBACK, RTD config (num_expiries, min_oi_floor) |
| `run_options_levels.py` | RTD-native path parity (separate macro levels, weekly scope, translated_levels, metadata dicts, EOD pinning, DB snapshot) |
| `gex_calculator.py` | Black-76 functions, `_calc_per_strike_exposures` use_black76 flag, `_build_strike_gex` is_futures flag |
| `futures_translator.py` | Multiplicative scaling preserved (kept as backup/perspective), comments updated |
| `file_writer.py` | Multiplicative branch in gex_profiles preserved, QQQ→NQ/SPY→ES token translation preserved |
| `interval_writer.py` | Added skew/IV fields to DB payload |
| `hybrid_coordinator.py` | Schwab expiry discovery + caching, adaptive sleep, configurable num_expiries, validate_greeks fix, min_oi_floor passthrough |
| `rtd_gex_calculator.py` | Black-76 Greek fallback, multi-expiry support, is_futures flag |
| `adapter.py` | expiry_map on ChainSnapshot, VEGA/THETA in greeks dict |
| `worker.py` | Quote type reduction (8→5) |
| `symbol_builder.py` | expiry field on OptionContract |
| `options_fetcher.py` | is_futures flag on OptionChainData |
| `web/lib/options-live-v3/data.ts` | Read intraday_levels.json |
| `web/app/api/options-live/route.ts` | Read intraday_levels.json |
| `web/app/api/options-live/snapshot/route.ts` | Accept skew/IV fields |
| 11 files | `inplace=True` → assignment form (pandas 3.0 CoW compatibility) |

---

## Package Versions (Global Python 3.14)

| Package | Version |
|---|---|
| Python | 3.14.0 |
| fastapi | 0.139.0 |
| starlette | 1.3.1 |
| uvicorn | 0.51.0 |
| pandas | 3.0.3 |
| numpy | 2.5.1 |
| scipy | 1.18.0 |
| pyarrow | 25.0.0 |
| pydantic | 2.13.4 |
| yfinance | 1.5.1 |
| TA-Lib | 0.7.0 |
| schwabdev | 3.0.5 |
| APScheduler | 3.11.3 |
| prisma | 0.15.0 (Pydantic V1 warning on 3.14) |
| comtypes | 1.4.16 |
| requests | 2.34.2 |
| urllib3 | 2.7.0 |

---

## Quick Start (After Hub + TOS Are Running)

```bash
# 1. Start the Hub
python -m scripts.streaming.schwab_hub --port 8080

# 2. Run a single pipeline cycle
python -m scripts.streaming.options.run_options_levels --tickers SPX,SPY,NDX,QQQ,NQ,ES

# 3. Or run in loop mode (2-tier priority scanner)
python -m scripts.streaming.options.run_options_levels --loop

# 4. Or run on schedule (APScheduler cron)
python -m scripts.streaming.options.run_options_levels --schedule
```

## Verification Checklist

- [ ] Hub starts without errors (`python -m scripts.streaming.schwab_hub --port 8080`)
- [ ] Pipeline runs end-to-end without crashes
- [ ] NQ and ES have non-zero `META_GEX_TOTAL` in unified_levels.txt
- [ ] NQ and ES have `MAGNET` token in unified output
- [ ] NQ and ES front EM shows `0d` (not `7d`) when running during RTH
- [ ] GexSnapshot DB rows for /NQ and /ES have non-null `put25dIv`, `call25dIv`
- [ ] GexSnapshot DB rows for /NQ and /ES have non-null `futuresSymbol`, `futuresTranslationMode`
- [ ] `intraday_levels.json` contains entries for NQ and ES in `market_structure`
- [ ] Web dashboard loads without errors at `localhost:3000`
- [ ] Trader narrative runs: `python -m scripts.trader.trader_narrative --mode open --no-discord`
- [ ] No `inplace=True` warnings in pipeline logs
- [ ] EOD 16:15 snapshot pins both futures and SPX to 16:14 ET close