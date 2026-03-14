# Dealer Levels — Requirements Specification

**Feature**: Automated Dealer Positioning Levels via Options GEX  
**Status**: v2.0  
**Last Updated**: 2026-03-14

---

## 1) Goals

- Produce actionable ES/NQ intraday levels from index-family option dealer positioning.
- Keep output quality reliable across premarket, overnight, and weekend execution windows.
- Emit copy-ready strings and interpretation text for direct trader workflows.
- Keep Discord delivery optional and runtime-controllable.

---

## 2) Non-Goals

- Tick-level or streaming GEX recomputation
- Automated trade execution/routing
- Full market-holiday calendar integration (weekday filter only)
- Perfectly model-derived greeks for futures options directly from `/ES`/`/NQ` chains

---

## 3) User Stories

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-1 | Day trader | Get ES/NQ call/put walls, zero gamma, EM, and advanced flow levels | I can pre-plan key reaction zones |
| US-2 | Day trader | Receive a clean copy-ready ES/NQ line format | I can paste into my charting workflow quickly |
| US-3 | Day trader | Read interpretation/pre-open plan text | I can form a directional and risk framework before RTH |
| US-4 | Operator | Run in schedule mode and one-shot mode | I can support both automation and ad-hoc execution |
| US-5 | Operator | Enable/disable Discord at runtime | I can control alerting during validation or live ops |
| US-6 | Developer | Tolerate weak weekend/off-hours chains | Output remains usable instead of empty/broken |

---

## 4) Functional Requirements

### FR-1 Data ingestion and selection

| ID | Requirement |
|---|---|
| FR-1.1 | Authenticate using local `secrets.json` + `token.json` |
| FR-1.2 | Fetch option chains for primary index families (`SPX`, `NDX`) |
| FR-1.3 | Target front expirations from `DTE_TARGETS` using nearest-available expiry-key selection |
| FR-1.4 | Fetch futures quotes for mapped symbols (`/ES`, `/NQ`) |
| FR-1.5 | Reject ambiguous non-futures quote keys when requesting slash-prefixed futures symbols |
| FR-1.6 | Attempt yfinance quote fallback if Schwab futures quote is unavailable |

### FR-2 Chain quality fallback

| ID | Requirement |
|---|---|
| FR-2.1 | Treat a chain as non-actionable when non-zero OI contracts are below `MIN_NONZERO_OI_CONTRACTS` |
| FR-2.2 | On non-actionable SPX/NDX chain, fallback to mapped ETF (`SPY`/`QQQ`) |
| FR-2.3 | If fallback chain is used, rescale computed levels to target index spot before futures translation |

### FR-3 Level calculations

| ID | Requirement |
|---|---|
| FR-3.1 | Compute strike net GEX profile, cumulative profile, and regime (POSITIVE/NEGATIVE) |
| FR-3.2 | Compute gamma-flip zone bounds and derived zero-gamma midpoint |
| FR-3.3 | Compute absolute and secondary call/put walls (OI × |gamma| ranking, OI thresholded) |
| FR-3.4 | Compute local call/put nodes within ±1.5% spot window |
| FR-3.5 | Compute front-DTE call/put walls |
| FR-3.6 | Compute hedge wall and max pain |
| FR-3.7 | Compute expected move and EM envelope using straddle or IV mode |
| FR-3.8 | Compute advanced structure: vol-trigger bands, gamma cliffs, vanna/charm nodes, volume imbalance nodes, DEX nodes, liquidity vacuum bounds, 25-delta skew pivots |

### FR-4 Futures translation

| ID | Requirement |
|---|---|
| FR-4.1 | Compute basis spread = futures price − cash spot |
| FR-4.2 | Shift every computed cash level into futures space using the basis spread |
| FR-4.3 | Preserve regime, total GEX, and metadata in translated output |

### FR-5 Output files

| ID | Requirement |
|---|---|
| FR-5.1 | Overwrite `data/daily_levels.json` each run |
| FR-5.2 | Overwrite `data/daily_levels.txt` each run |
| FR-5.3 | JSON entries must include `{ level, type, asset, regime, cash_ticker, basis_spread }` |
| FR-5.4 | TXT must include copy-ready string block, interpretation/pre-open plan block, and detailed summary block |
| FR-5.5 | Copy-ready ordering must match operational template (Upper EM → Lower EM 10-level set) |

### FR-6 Notifications and scheduling

| ID | Requirement |
|---|---|
| FR-6.1 | Support on-demand execution and scheduler mode (`--schedule`) |
| FR-6.2 | Scheduler must run at configured weekday ET times |
| FR-6.3 | Discord updates must be optional and controllable via config and CLI (`--discord`, `--no-discord`) |
| FR-6.4 | Discord failure must not block file output |

---

## 5) Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Reliability | Per-ticker failure must not stop the full run |
| NFR-2 | Observability | Log all run stages and fallbacks to `data/dealer_levels.log` |
| NFR-3 | Robustness | Handle weekend/off-hours sparse data without producing structurally empty output when fallback data exists |
| NFR-4 | Security | Never log API keys/secrets |
| NFR-5 | Extensibility | New index family should be primarily configurable in `config.py` mappings |

---

## 6) Constraints

- Schwab rate limits apply.
- TradingView Pine has no direct file I/O; manual paste/input flow is required.
- Weekday-only scheduling is implemented; exchange holiday filtering is out of scope.
