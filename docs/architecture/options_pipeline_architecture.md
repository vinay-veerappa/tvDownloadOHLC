# Options Pipeline & Dashboard Architecture

## 1. Purpose
Translate PRD and design spec into an implementation-ready architecture for frontend, API, compute, and publishing.

## 2. System Overview
### 2.0 Entry Point and Namespace Boundaries
1. Greenfield UI route: `/options-live-v3`.
2. Greenfield API namespace: `/api/options-live/v3/*`.
3. Existing `/options-live` UI and existing `/api/options-live/*` contracts are preserved during V3 implementation.

### 2.1 Major Layers
1. Data ingestion layer (options chain, flow, derived metrics).
2. Snapshot computation layer (GEX/DEX/Charm/Vanna, levels, narrative factors).
3. API aggregation layer for UI modules.
4. Frontend rendering layer (tabs, charts, narrative, integrated view).
5. Publish layer (Discord image + metadata payload).

### 2.2 Core Design Constraints
1. Fast tab switching with cached snapshots.
2. Deterministic level and score logic.
3. Explainability and auditability for narrative output.
4. Graceful behavior with delayed or partial data.

## 3. Proposed API Surface
### 3.1 Read APIs
1. `GET /api/options-live/v3/summary?symbol=SPY`
2. `GET /api/options-live/v3/by-strike?symbol=SPY&strikes=20&expiryScope=all`
3. `GET /api/options-live/v3/by-expiry?symbol=SPY&strikes=20`
4. `GET /api/options-live/v3/largest?symbol=SPY&limit=25&sort=abs_net`
5. `GET /api/options-live/v3/levels?symbol=SPY`
6. `GET /api/options-live/v3/spot-gamma?symbol=SPY`
7. `GET /api/options-live/v3/heatmap?market=spx&mode=pcr&metric=net_gex`
8. `GET /api/options-live/v3/narrative?symbol=SPY`
9. `GET /api/options-live/v3/recent-flow?symbol=SPY&limit=50`
10. `GET /api/options-live/v3/explain?snapshotId=...`

### 3.2 Publish APIs
1. `POST /api/options-live/v3/publish/discord`
2. `POST /api/options-live/v3/publish/preview`
3. `POST /api/options-live/v3/publish/event-rule`

### 3.3 API Response Envelope
Use a shared envelope:
1. `success`
2. `data`
3. `meta`:
- `symbol`
- `asOf`
- `freshnessMs`
- `source`
- `computeVersion`
4. `warnings` (delayed/missing fields)

## 4. Data Model (Snapshot)
### 4.1 Required Core Fields
1. `symbol`
2. `spot`
3. `as_of_timestamp`
4. `by_strike[]`
5. `by_expiry[]`
6. `gex_total`, `dex_total`, `charm_total`, `vanna_total`
7. `open_interest_call`, `open_interest_put`, `oi_change_call`, `oi_change_put`
8. `gamma_flip`, `call_wall`, `put_wall`, `max_pos_gamma`, `max_neg_gamma`
9. `pcr_total`, `pcr_by_strike[]`, `pcr_by_expiry[]`

### 4.2 Narrative Fields
1. `signals[]`
2. `screener.primary`
3. `screener.alternate`
4. `screener.factors[]`
5. `setup_analysis[]`
6. `for_stronger_setup[]`
7. `trading_implication`

### 4.3 Flow Fields
1. `flow_delay_ms`
2. `flow_regime`
3. `recent_flow[]`

## 5. Compute Pipeline
### 5.1 Pipeline Steps
1. Normalize chain and flow data.
2. Compute exposures (Gamma, Delta, Charm, Vanna).
3. Derive levels (flip/walls/max nodes).
4. Build aggregate views (by strike, by expiry, largest).
5. Generate deterministic signals and screener factors.
6. Persist snapshot with version tags.

### 5.2 Determinism Requirements
1. All rule outputs must be reproducible from same inputs.
2. All derived values should include compute version and timestamp.

## 6. Frontend Module Architecture
### 6.1 Container Strategy
1. One global store for symbol and control state.
2. Module-local stores for view-specific preferences.
3. Shared query/cache layer keyed by symbol + controls.

### 6.2 Rendering Strategy
1. Preload summary + active tab data on symbol switch.
2. Keep previous data visible until new data arrives.
3. Use module-level stale indicators, plus global stale indicator.

## 7. Discord Publishing Design
### 7.1 Publish Workflow
1. Build export payload (image + metadata).
2. Render preview with annotation layer.
3. Submit to Discord webhook route.
4. Persist publish audit record.

### 7.2 Reliability Rules
1. Idempotency key required.
2. Retry with bounded backoff.
3. Do not duplicate posts on retry success.

## 8. SLOs and Observability
### 8.1 SLO Targets
1. Headline level freshness <= 120s under normal operations.
2. Tab switch interaction <= 150ms with cached data.
3. Discord single-chart publish <= 2s median.

### 8.2 Telemetry
1. API latency per endpoint.
2. Snapshot compute duration and freshness lag.
3. Publish success/failure metrics.
4. Signal outcome tracking metrics.

## 9. Security and Governance
1. Webhook secrets in secured config only.
2. Publish endpoints require internal auth guard.
3. Audit trail for publishes and model versions.
4. Clearly label delayed or inferred data.

## 10. Testing Strategy
### 10.1 Unit
1. Level derivation rules.
2. Screener factor scoring.
3. Field validation and envelope contracts.

### 10.2 Integration
1. End-to-end snapshot compute to API response.
2. API to UI rendering for core modules.
3. Publish preview and send pipeline.

### 10.3 Visual and UX
1. Golden snapshots for key views.
2. Regression checks for spot line alignment.
3. Heatmap/tile density readability checks.

## 11. Migration and Rollout
1. Introduce v3 endpoints in parallel with existing options-live API.
2. Roll out behind feature flags by module.
3. Enable Discord publishing last, after stability gates.

## 12. Done Criteria
1. API contracts implemented and versioned.
2. All major modules render from live snapshots.
3. Narrative outputs are explainable and deterministic.
4. Discord publish flow is reliable and auditable.

## 13. Legacy Pipeline and Pine Contract Compatibility

### 13.1 Existing Producer/Consumer Contract to Preserve
1. Producer script: `scripts/streaming/options/run_options_levels.py`.
2. Existing output artifacts that must remain valid:
- `data/daily_levels.json` (structured levels)
- `data/daily_levels.txt` (copy-ready text for Pine)
3. Existing Pine consumer that must continue to work unchanged:
- `scripts/indicators/options/DealerLevels.pine`

### 13.2 Compatibility Requirements
1. V3 APIs must be additive and must not break current file schemas consumed by Pine workflows.
2. If new derived fields are introduced, append them without removing or renaming legacy fields used by copy/paste flows.
3. Any schema evolution for file outputs requires versioned adapters and fallback behavior.
4. Keep symbol routing assumptions compatible with DealerLevels matching logic (index/ETF/futures families).

### 13.3 Adapter Strategy
1. Introduce a translation layer:
- `snapshot_v3 -> pine_level_payload`
- `snapshot_v3 -> dashboard_payload`
2. Keep one canonical compute graph, then project into multiple output contracts.
3. Record adapter version in metadata for traceability.

### 13.4 Regression and Contract Tests
1. Contract tests must verify expected fields in `daily_levels.json` and `daily_levels.txt` after V3 changes.
2. Golden fixtures should include representative SPX/NDX (and mapped futures) outputs.
3. Add a compatibility test that validates copy block formatting remains paste-safe for DealerLevels input.
4. Add a CI gate that fails when compatibility-critical keys are removed or renamed.

## 14. Architecture and Pattern Standards

### 14.1 Recommended Patterns
1. BFF aggregation pattern for UI-focused payload shaping.
2. Adapter pattern for format translation (`snapshot_v3 -> dashboard`, `snapshot_v3 -> pine`).
3. Strategy pattern for scoring logic variants and experimental factor sets.
4. Repository/service boundary for data retrieval and compute orchestration.
5. Feature flag pattern for progressive rollout by module.

### 14.2 Modularity Rules
1. Keep compute engine independent from transport and UI concerns.
2. Isolate metric-family implementations behind shared interfaces.
3. Enforce single-responsibility per API endpoint (one primary concern per route).
4. Prevent cross-module coupling by exposing typed contracts only.

### 14.3 Performance Engineering Requirements
1. Precompute heavy aggregations at snapshot time where possible.
2. Cache hot symbol payloads with freshness-aware invalidation.
3. Use incremental payload endpoints to avoid overfetching.
4. Support selective field projection for high-frequency views.
5. Prefer server-side aggregation for expensive joins/groupings.

### 14.4 Frontend Performance Tactics
1. Use request deduplication and stale-while-revalidate query strategy.
2. Memoize derived selectors and avoid repeated expensive transforms in render paths.
3. Offload heavy transforms to worker context when needed.
4. Apply list/table virtualization for large result sets.
5. Gate expensive visual effects behind device capability checks.

### 14.5 Observability and Enforcement
1. Add per-module render timing instrumentation.
2. Track cache hit/miss and payload size by endpoint.
3. Add regression budgets for p95 latency and client render cost.
4. Fail CI on severe performance budget regressions when benchmarks are available.


## 15. Futures Translation & Mapping Matrix

A critical component of the pipeline is ensuring that derivative cash vehicles (SPY, SPX, QQQ) are accurately represented in their futures equivalent spaces (/ES, /NQ) so traders have synchronized DOM levels.

### 15.1 Global Mapping Config (`config.py`)
Translation is exclusively driven by the `INDEX_TO_FUTURES` dictionary. If a ticker is not in this map, it remains in standard cash space.
```python
INDEX_TO_FUTURES: dict[str, str] = {
    "SPX": "/ES",
    "SPY": "/ES",
    "QQQ": "/NQ",
    "DIA": "/YM",
    "IWM": "/RTY",
}
```
*Note: Single stock equities (e.g., AAPL, NVDA) are intentionally omitted and do not undergo translation.*

### 15.2 Translation Math (`futures_translator.py`)
When a mapping is detected, the `DealerLevels` object is mutated to include translation metadata:
- **`futures_symbol`**: The target string (e.g., `"/ES"`).
- **`translation_mode`**: Either `additive` (basis spread, like SPX to /ES) or `multiplicative` (scaling ratio, like SPY to /ES).
- **`basis_spread`**: Absolute point difference (applied for `additive`).
- **`basis_ratio`**: Division ratio (e.g., ~10x for SPY to /ES).

### 15.3 Database Schema (Prisma)
The output of the translation is safely captured in the Prisma `GexSnapshot` table using `getattr` defaults to gracefully handle unmapped single stocks:
```prisma
model GexSnapshot {
  ...
  // Futures translation matrix
  futuresSymbol           String?
  futuresTranslationMode  String?
  futuresBasisSpread      Float?
  futuresBasisRatio       Float?
}
```

### 15.4 UI Layer Consumption
The Next.js Frontend consumes the `GexSnapshot` via the `/api/options-live/v3/*` endpoints. 
- **Container Level:** Global store maintains the active `symbol` state.
- **Rendering Level:** The presence of `futuresSymbol` and `futuresBasisRatio` dictates whether the charts render raw cash scales or the translated futures scale.
- **Preservation of Pine Compat:** The UI handles the scaled metrics seamlessly, whilst the backend continues to spit out unaltered `daily_levels.txt` for TradingView PineScript users.
