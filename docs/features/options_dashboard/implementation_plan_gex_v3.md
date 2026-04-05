# Implementation Plan: Options Live GEX V3

## 1. Objective
Deliver GEX V3 in sequenced milestones with clear scope, owners, dependencies, and acceptance gates.

## 2. Delivery Strategy
1. Build in vertical slices by capability.
2. Stabilize data contracts before broad UI expansion.
3. Add narrative and publish workflows after core market-structure views are stable.

## 3. Milestone Plan

### M0 - Foundation and Contracts (Week 1)
Scope:
1. Freeze v3 API schemas and shared response envelope.
2. Implement snapshot metadata (`asOf`, freshness, compute version).
3. Add feature flags for v3 modules.
4. Baseline and lock compatibility with existing Pine output contracts (`daily_levels.json`, `daily_levels.txt`).

Deliverables:
1. API contract docs and schema validators.
2. Stub endpoints returning typed payloads.
3. Base telemetry instrumentation.
4. Compatibility fixture set sourced from current `run_options_levels.py` outputs.

Exit Criteria:
1. Contract tests pass.
2. Feature flags control module visibility.
3. Pine output compatibility tests pass.

### M1 - Core GEX Views (Weeks 2-3)
Scope:
1. Daily GEX view.
2. By Strike view with strike-count control.
3. By Expiry view.
4. Largest by Strike and Expiry table.

Deliverables:
1. Shared control bar and state persistence.
2. Spot line and key-level overlays.
3. Cross-view linking (level click highlight).

Exit Criteria:
1. All four views render live data.
2. Tab switches preserve context and remain performant.

### M2 - Levels and Spot Gamma (Week 4)
Scope:
1. Live Gamma Exposure Levels ladder.
2. Spot Gamma panel with trend and smoothing.
3. Header level chips (spot, flip, walls).

Deliverables:
1. Deterministic level engine integration.
2. Level confidence and timestamps.

Exit Criteria:
1. Level values are consistent across all modules.
2. Spot gamma updates and state badges are correct.

### M3 - Heatmaps and Integrated View (Weeks 5-6)
Scope:
1. S&P and Nasdaq heatmaps (P/C ratio + regular).
2. Treemap and matrix modes.
3. Periscope-style integrated chart + exposure pane.

Deliverables:
1. Shared-axis synchronized integrated view.
2. Heatmap cell drilldown into detailed context.

Exit Criteria:
1. Heatmap interactions and integrated view link behavior pass QA.
2. S&P and Nasdaq state preferences are preserved independently.

### M4 - Narrative Intelligence (Weeks 7-8)
Scope:
1. Intraday Delta GEX narrative rail.
2. Signals card stack.
3. Squeeze screener with factor breakdown.
4. Recent flow feed and delayed-data disclaimer handling.

Deliverables:
1. Explain-score panel (`Why this score?`).
2. Deterministic setup analysis templates.

Exit Criteria:
1. Narrative outputs are reproducible for identical inputs.
2. Delayed-data caveats are visible everywhere required.

### M5 - Discord Publishing and Ops (Week 9)
Scope:
1. Preview + publish workflow.
2. Manual, scheduled, and event-driven publish rules.
3. Publish audit log and idempotent retries.

Deliverables:
1. Full and compact export templates.
2. Routing and throttling policies.

Exit Criteria:
1. Publish success rate meets threshold in staging.
2. No duplicate posts under retry scenarios.

### M6 - Validation and Hardening (Week 10)
Scope:
1. Signal quality metrics and post-session validation.
2. SLO dashboards.
3. Degraded mode and fallback behavior.

Deliverables:
1. Validation reports.
2. Runbook for data outages and publish failures.

Exit Criteria:
1. SLOs and error budgets defined and measurable.
2. Release readiness checklist signed off.

## 4. Workstream Breakdown
### 4.1 Frontend
1. Shared controls and state model.
2. Chart modules and interaction wiring.
3. Narrative rail and details rail.

### 4.2 Backend/API
1. Snapshot aggregation endpoints.
2. Level and screener compute APIs.
3. Publish orchestration endpoints.

### 4.3 Data/Compute
1. Exposure and level derivation pipeline.
2. Factor scoring for narrative and screener.
3. Data freshness and anomaly checks.

### 4.4 Platform/Operations
1. Telemetry and alerting.
2. Secret management for webhooks.
3. Release gates and rollback plan.

## 5. Dependency Map
1. M1 depends on M0 contract freeze.
2. M2 depends on stable level compute in M1/M0.
3. M3 depends on M1 chart primitives.
4. M4 depends on M1-M2 data and scoring foundations.
5. M5 depends on stable module rendering from M1-M4.
6. M6 depends on all previous milestone outputs.

## 6. Risks and Mitigations
1. Risk: data lag causes misleading narratives.
Mitigation: strong stale-state labeling and confidence penalties.

2. Risk: chart clutter from high-density data.
Mitigation: strike-count, threshold filters, and adaptive label density.

3. Risk: overfit scoring in squeeze screener.
Mitigation: calibration tracking and factor transparency.

4. Risk: publish spam in volatile sessions.
Mitigation: dedupe keys, cool-down windows, severity routing.

## 7. Suggested Ticket Seeding
1. FE-001 Shared controls and persistence.
2. FE-002 By Strike and By Expiry modules.
3. FE-003 Levels ladder and spot gamma panel.
4. FE-004 Heatmap modules (treemap + matrix).
5. FE-005 Integrated chart + exposure pane.
6. FE-006 Narrative rail and screener cards.
7. BE-001 v3 summary and by-strike endpoints.
8. BE-002 level derivation and explain endpoint.
9. BE-003 narrative and flow endpoints.
10. BE-004 publish preview/send endpoints.
11. OPS-001 telemetry dashboard and SLO monitors.
12. OPS-002 publish audit and retry safety.
13. DATA-001 Pine compatibility fixture generation from `run_options_levels.py`.
14. DATA-002 Adapter: v3 snapshot to legacy Pine level payload.
15. QA-001 Contract regression tests for `daily_levels.json` and `daily_levels.txt`.
16. QA-002 Paste-format validation tests for `scripts/indicators/options/DealerLevels.pine` workflow.

## 8. Release Gates
1. Gate A: Contract integrity and typed responses.
2. Gate B: Core view stability and performance.
3. Gate C: Narrative explainability and delayed-data handling.
4. Gate D: Publish reliability and auditability.
5. Gate E: Production SLO monitoring active.

## 9. Immediate Next 5 Actions
1. Approve this milestone sequence and scope boundaries.
2. Freeze v3 payload schema draft.
3. Create initial ticket board from seeded tickets.
4. Implement M0 endpoint stubs and schema validation.
5. Start M1 frontend shell using shared control bar.

### 9.1 Scaffold Status (Current)
1. Greenfield UI entry route created: `/options-live-v3`.
2. V3 API stub namespace created: `/api/options-live/v3/*`.
3. Shared V3 HTTP envelope helper created for consistent responses.
4. Full endpoint index and publish route stubs are in place for parallel backend/frontend work.

## 10. Pine Compatibility Workstream (Mandatory)
1. Capture current baseline outputs from `run_options_levels.py` for representative symbols.
2. Define compatibility-critical keys and text formatting invariants.
3. Implement adapter layer where V3 internal schema diverges from legacy Pine contract.
4. Add CI checks preventing accidental breaking changes to Pine-facing outputs.
5. Require compatibility sign-off before enabling V3 by default.

## 11. Performance and Modularity Workstream (Mandatory)

### 11.1 Non-Negotiable Engineering Gates
1. Define and publish performance budgets before M1 implementation starts.
2. Require architecture review for each major module boundary.
3. Require reusable primitive check before introducing new chart component types.
4. Block merge when new code duplicates existing core primitives without justification.

### 11.2 Required Benchmarks
1. API p50/p95 latency by endpoint.
2. Payload size distribution by endpoint and mode.
3. Client render and tab-switch timings by module.
4. Publish latency and retry behavior under simulated failures.

### 11.3 Ticket Additions (Performance/Architecture)
1. ARCH-001 Define module boundary map and dependency rules.
2. ARCH-002 Build shared chart primitive library (spot line, split bars, legends, status layers).
3. PERF-001 Add endpoint payload-size and latency telemetry.
4. PERF-002 Add client render instrumentation and performance dashboard.
5. PERF-003 Implement virtualization for large tables and flow lists.
6. PERF-004 Add cache strategy and freshness invalidation policy.
7. PERF-005 Establish CI performance regression checks.

### 11.4 Exit Criteria
1. Performance budgets are met in staging for critical paths.
2. Module dependency graph remains acyclic and documented.
3. Shared primitives cover all core views without major duplication.
4. Observability dashboards are active before production rollout.
