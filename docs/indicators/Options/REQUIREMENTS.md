# Options Pipeline Requirements

Version: 2026-05-09
Scope: `scripts/streaming/options/*` runtime and `data/options/*` outputs

## 1) Functional Requirements

### FR-1 Data Acquisition
| ID | Requirement |
|---|---|
| FR-1.1 | Fetch options chain data per configured ticker and DTE windows. |
| FR-1.2 | Fetch front-month futures quotes when ticker has a futures mapping. |
| FR-1.3 | If index chain is sparse/non-actionable, fallback to configured ETF proxy. |

### FR-2 Level Computation
| ID | Requirement |
|---|---|
| FR-2.1 | Compute intraday and macro dealer levels per ticker. |
| FR-2.2 | Compute multi-expiry expected moves (`expected_moves`). |
| FR-2.3 | Compute EM85 bounds (`straddle_85_upper`, `straddle_85_lower`) for each expected-move expiry. |
| FR-2.4 | Preserve EM85 fields through both rescale and translation paths. |
| FR-2.5 | Prioritize `zero_gamma_delta_adj` (delta-adjusted Zero Gamma) over standard Zero Gamma for core boundary checks and formatting exports. |

### FR-3 Translation and Normalization
| ID | Requirement |
|---|---|
| FR-3.1 | Support additive spread translation for same-scale products. |
| FR-3.2 | Support multiplicative ratio translation for cross-scale products. |
| FR-3.3 | Rescale ETF-derived fallback levels back into target cash index space before final output. |

### FR-4 Weekly EOD Scope Persistence
| ID | Requirement |
|---|---|
| FR-4.1 | On Friday EOD, capture weekly scope record (EM and EM85 bounds) per ticker. |
| FR-4.2 | Persist weekly scope cache to `data/options/weekly_em_scope.json`. |
| FR-4.3 | On subsequent Mon-Fri runs, attach valid cached weekly scope until expiry rollover. |
| FR-4.4 | Weekly scope must be available in both cash and futures-translated payloads. |

### FR-5 Persistent Runtime State
| ID | Requirement |
|---|---|
| FR-5.1 | Persist basis anchors in `data/options/basis_anchors.json` for translation stability. |
| FR-5.2 | Persist change-detection state in `data/options/pipeline_state.json`. |
| FR-5.3 | Per-run updates must not corrupt existing persistence files on partial failure. |

### FR-6 Output Files
| ID | Requirement |
|---|---|
| FR-6.1 | Write JSON and TXT outputs into `data/options/`. |
| FR-6.2 | Maintain intraday and macro JSON outputs (`daily_levels.json`, `intraday_levels.json`, `macro_levels.json`). |
| FR-6.3 | Produce copy-ready text outputs including EM and EM85 fields when present. |
| FR-6.4 | Produce unified outputs (`unified_levels.txt`, `unified_levels.json`) when enabled. |
| FR-6.5 | Format Zero Gamma copy-ready labels as `Zero Gamma (Δ-Adj)` to allow downstream chart routing of delta-adjusted levels. |

### FR-7 Notifications and Scheduling
| ID | Requirement |
|---|---|
| FR-7.1 | Support on-demand execution, `--schedule`, and `--loop` modes. |
| FR-7.2 | Discord updates must be controllable via config and CLI (`--discord`, `--no-discord`). |
| FR-7.3 | Discord delivery failure must not block file output completion. |
| FR-7.4 | Embed-size rejection must trigger compacting and/or text fallback attempts. |

## 2) Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Reliability | Per-ticker failure must not stop the full pipeline run. |
| NFR-2 | Observability | Log run stages, fallback choices, and output fingerprints. |
| NFR-3 | Robustness | Handle off-hours and sparse chains without emitting structurally empty output when valid fallback exists. |
| NFR-4 | Security | Never log API keys or secret material. |
| NFR-5 | Extensibility | Add new index families primarily via config mappings and ticker profiles. |

## 3) Constraints

- Schwab/API rate limits apply.
- TradingView Pine requires paste-based text ingestion (no direct file I/O).
- Scheduler is weekday-time based; exchange holiday filtering remains out of scope.

## 4) Acceptance Checks

- EM85 appears for futures instruments in generated outputs and Discord fields.
- Friday EOD weekly scope is persisted and reused on following weekday runs.
- Output generation succeeds even when Discord rejects one or more embed payloads.