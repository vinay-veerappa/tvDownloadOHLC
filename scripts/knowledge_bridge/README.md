# Knowledge Bridge — Phase 3 Strategy Candidate Registry

Bridges KB setup units (prose descriptions of ICT trading setups from
transcripts/PDFs/charts) to executable detection functions in `ict_engine`
and strategy classes in `trading_framework`.

## Architecture

```
KB API (port 8900)
    │
    │  POST /search (knowledge_type="setup")
    ▼
CandidateGenerator.generate_batch()
    │
    │  1. Scan setup payload prose for ICT concept terms
    │  2. Map each concept → DetectionEntry (prose → function)
    │  3. Classify role (regime/bias/timing/trigger/entry/invalidation/target)
    │  4. Infer strategy_key, session_filter, direction
    ▼
StrategyCandidate[]
    │
    ├── export_candidates_json()  →  candidate JSON file
    ├── link_candidates_to_units()  →  unit_id → [candidate_id] mapping
    └── compute_unit_updates()  →  write-back payload for KB metadata
```

## Modules

### `detection_catalog.py`
The **prose → function** registry. 34 entries mapping ICT concept names
(as they appear in KB transcripts) to vectorized detection functions in
`scripts/libs_py/ict_engine/`.

```python
from scripts.knowledge_bridge import resolve_detection

entry = resolve_detection("FVG")
print(entry.qualified_name)  # scripts.libs_py.ict_engine.core.pa.detect_fvg
fn = entry.resolve()         # actual callable
```

### `strategy_candidates.py`
The `StrategyCandidate` dataclass + `CandidateGenerator` that converts KB
setup units into executable candidates.

```python
from scripts.knowledge_bridge import generate_candidates

candidates = generate_candidates(k=50)
for c in candidates:
    print(f"{c.candidate_id}: {c.name} [{c.status.value}]")
    for step in c.detection_steps:
        print(f"  {step.step_order}. {step.role}: {step.concept} → {step.function_ref}")
```

### `candidate_export.py`
JSON export/import + bidirectional linking helpers.

```python
from scripts.knowledge_bridge import export_candidates_json, link_candidates_to_units

export_candidates_json(candidates, "data/knowledge/candidates.json")
links = link_candidates_to_units(candidates)  # {unit_id: [candidate_id, ...]}
```

## ADR Compliance

| ADR | Rule | How |
|-----|------|-----|
| ADR-017 | Zero-Loop (vectorized) | All cataloged detection functions are vectorized NumPy/Pandas |
| ADR-020 | Prop Firm Liquidation | `max_exit_time="16:00 ET"` on every candidate |
| ADR-021 | Unified Simulator | Candidates designed for `PropFirmSimulator` |
| ADR-001 | Timezone | Detection functions use ET session windows; storage UTC epoch |
| ADR-002 | Normalization | Performance metrics as price %, not points |

## Detection Catalog Categories

| Category | Concepts |
|----------|----------|
| price_action | FVG, Volume Imbalance, Inversion FVG, BPR, Liquidity Void, First FVG, FVG Mitigation |
| structure | Swing High/Low, BOS/MSS, CISD (proxy), CISD (authoritative) |
| liquidity | Liquidity Pools (BSL/SSL/EQH/EQL), Order Block, Breaker Block |
| sessions | Killzone, ICT Macro, Silver Bullet |
| gaps | Opening Gaps (NWOG/NDOG), RTH Gap, Consequent Encroachment, Gap Fill |
| htf | HTF Levels (PDH/PDL/PWH/PWL/PMH/PML), IPDA Ranges (20/40/60) |
| retracements | Fibonacci Retracement, Dealing Range (Premium/Discount) |
| correlation | SMT Divergence |
| cycles | TTrades Fractal, Power of 3 (stub), Quarterly Theory (stub) |
| bias | MMXM Simple, TTrades Mechanical, Midnight Open Filter |
| projections | SD Projections |

## Phase 4 Integration (next)

- `backtest_loop.py`: candidate → `STRATEGY_FACTORY_REGISTRY` → backtest → results
- Write back: `candidate.epistemic_status`, `unit.metadata.linked_stat_ids`
- Integration with `PropFirmSimulator` (ADR-021)