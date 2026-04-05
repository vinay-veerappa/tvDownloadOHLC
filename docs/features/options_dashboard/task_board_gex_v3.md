# Task Board: Options Live GEX V3

## 1. Working Mode
1. Greenfield UI entry points only.
2. Existing UI untouched until cutover gate.
3. Pine pipeline compatibility is mandatory in every milestone.

## 2. Milestone Backlog

## M0 Foundation and Contracts
1. ARCH-001 Define route map for new UI entry points.
2. BE-000 Create V3 API route stubs.
3. DATA-001 Generate compatibility fixtures from current levels pipeline.
4. QA-001 Add schema validation tests for snapshot and publish payloads.
5. OPS-001 Add baseline telemetry wiring.

## M1 Core GEX Views
1. FE-001 Build shell page for new entry route.
2. FE-002 Implement global control bar with persisted state.
3. FE-003 Implement Daily GEX and By Strike modules.
4. FE-004 Implement By Expiry and Largest table modules.
5. QA-002 Validate tab persistence and warm-cache switch latency.

## M2 Levels and Spot Gamma
1. BE-001 Implement levels endpoint with confidence metadata.
2. FE-005 Implement levels ladder and key-level chips.
3. FE-006 Implement spot gamma panel and smoothing options.
4. QA-003 Cross-module level consistency tests.

## M3 Heatmaps and Integrated View
1. FE-007 Implement S&P/Nasdaq heatmap container.
2. FE-008 Implement matrix heatmap mode and drilldown.
3. FE-009 Implement treemap mode and label density rules.
4. FE-010 Implement integrated chart and exposure split pane.
5. PERF-001 Validate render budgets in dense views.

## M4 Narrative Intelligence
1. BE-002 Implement narrative endpoint with deterministic rule output.
2. FE-011 Implement narrative rail and signal cards.
3. FE-012 Implement squeeze screener with factor breakdown.
4. FE-013 Implement recent flow tape with delay disclosure.
5. QA-004 Add explainability tests for score decomposition.

## M5 Discord Publishing
1. BE-003 Implement preview and publish routes.
2. FE-014 Implement publish drawer and preview flow.
3. OPS-002 Add idempotency, retry, and audit logs.
4. QA-005 Validate no duplicate posts under retries.

## M6 Validation and Hardening
1. PERF-002 Add performance dashboard and regression checks.
2. DATA-002 Add anomaly and freshness checks.
3. OPS-003 Add degraded-mode runbook.
4. QA-006 End-to-end release gate validation.

## 3. Definition of Ready
1. API contract and schema exist for task scope.
2. Performance budget for affected surfaces is defined.
3. Compatibility impact on Pine outputs is assessed.
4. Feature flag path is identified.

## 4. Definition of Done
1. Tests added and passing.
2. Performance budgets met.
3. Observability events added for new module.
4. No Pine compatibility regression.
5. Documentation updated.
