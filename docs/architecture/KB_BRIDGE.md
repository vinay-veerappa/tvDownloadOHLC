# KB Bridge — Connecting to the ICT Knowledge Base

**Status:** Knowledge Bridge fully built (Phases 2-4), tested, and committed. Narrative integration test script (`scripts/knowledge_bridge/test_narrative.py`) verified working — KB context retrieval adds grounded ICT setup knowledge to the cheat sheet. Not yet wired into `briefing_core.py` production path (next step).
**Owner:** This doc lives in the consumer repo (`tvDownloadOHLC`). The canonical
producer handover is `C:\Users\vinay\video2pdf\knowledge_ingest\HANDOVER.md` —
read it for full pipeline state, schema, and history. Do not edit it from here.

---

## 1. The split

| Role | Repo | Path |
|---|---|---|
| **Producer** (ingests transcripts/PDFs/charts → typed KnowledgeUnits → LanceDB; serves the KB API) | `video2pdf` | `C:\Users\vinay\video2pdf\knowledge_ingest\` |
| **Raw inputs** (transcripts, PDFs, chart renders — can live anywhere) | — | `C:\ICT_Videos\` (external) |
| **Produced KB data** (the LanceDB, units JSONL, mineru text) | `tvDownloadOHLC` (this repo) | `data/knowledge/` |
| **Consumer** (narrative engine; queries the KB API) | `tvDownloadOHLC` (this repo) | `scripts/trader/` |

**Architecture (revised 2026-07-23):** the consumer repo OWNS all produced KB
data. The producer (`knowledge_ingest`) is just the ingest tool — it should not
store anything beyond its own code. Raw inputs stay external (transcripts can
be anywhere). Everything the producer *produces* lives under
`tvDownloadOHLC/data/knowledge/` so the running services all read from one place.

## 2. Runtime contract

The only coupling between this repo and the producer is the KB API on
`http://127.0.0.1:8900`. Start the producer first, then run the consumer.

```powershell
# 1) Producer (one terminal) — KB_DATA_DIR points the producer at our data tree
$env:KB_DATA_DIR = "C:\Users\vinay\tvDownloadOHLC\data\knowledge"
cd C:\Users\vinay\video2pdf; .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python -m knowledge_ingest.serve --port 8900

# 2) Consumer (another terminal)
cd C:\Users\vinay\tvDownloadOHLC; .\.venv\Scripts\Activate.ps1
python -m scripts.trader.trader_narrative --mode premarket --ticker ES1
```

The launch script `launch/start_kb_bridge.bat` sets `KB_DATA_DIR` for you. The
producer's `knowledge_ingest/paths.py` resolves all DB/units paths from that env
var (defaulting to `data/knowledge/`), so the running server serves from our
tree without editing producer code.

## 3. KB API endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{status, db_path}` |
| GET | `/stats` | — | counts, type distribution, top sources |
| POST | `/search` | `{query, k, knowledge_type, min_confidence}` | raw units (no LLM) |
| POST | `/ask` | `{question, k, knowledge_type, min_confidence}` | `{answer, sources}` (RAG) |

Quick check from this repo:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8900/health"
$body = @{question="What is CSD?"; k=8} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8900/ask" -Method POST -Body $body -ContentType "application/json"
```

## 4. The bridge module

`knowledge_ingest/kb_bridge.py` lives in the **producer** repo. Three public
functions:

- `get_kb_context_for_narrative(cheat_sheet_text, k_per_concept=3, max_context_chars=2000)`
  Scans the cheat sheet for ICT concepts, retrieves matching KB units, returns a
  formatted context block to append to the cheat sheet before sending to the LLM.
- `answer_narrative_question(question, k=8)` — full RAG answer with sources.
- `verify_narrative_claim(claim, k=5)` — post-narrative fact-check.

**Concept triggers** (cheat-sheet keyword → KB search query): `FVG`, `CSD`,
`MSS`, `order block`, `liquidity sweep`, `Judas`, `Power of Three`, `Po3`,
`MMXM`, `Silver Bullet`, `OTE`, `killzone`, `overnight session`, `premium`,
`discount`, `PDH`, `PDL`, `midnight open`, `7 Rule`, `trendline`, `breaker`,
`turtle soup`. Extend `CONCEPT_TRIGGERS` in `kb_bridge.py` when new narrative
concepts are added.

## 5. How to import the bridge from this repo

Prefer importing via the producer path (avoids a stale copy):

```python
import sys
sys.path.insert(0, r"C:\Users\vinay\video2pdf")
from knowledge_ingest.kb_bridge import (
    get_kb_context_for_narrative,
    answer_narrative_question,
    verify_narrative_claim,
)
```

If a copy is ever needed inside this repo, place it at
`scripts/trader/kb_bridge.py` and keep it in sync with the producer. The HTTP
contract is the source of truth, not the file location.

## 6. Current KB state (as of 2026-07-23)

- **Unified LanceDB (canonical):** 4,168 units at
  `data/knowledge/unified_knowledge.lancedb` (table `knowledge`) —
  818 chart + 3,327 transcript + 23 PDF.
  Distribution: framework(1662), setup(904), contextual(703), tip(510),
  psychology(370), anecdote(19).
  Sources: LumiTrader book (435), Vinay_Models (119), ICTNotes (78),
  Flux_NY_Guide (67), MMXM (33), TCM 2023 transcripts, etc.
- **Units JSONL (produced, for re-merge):** `data/knowledge/units/tcm_2023/`
  (transcript ingest output — segments/, classified/, units/, notes/).
  TCM 2024 ingest output lands at `data/knowledge/units/tcm_2024/` when run.
- **Pending ingest:** TCM 2024 (75 transcripts) and 2025 (18 transcripts) —
  run with `--profile ict --no-skip` (see producer HANDOVER). Output units
  default to `data/knowledge/units/`; merge rebuilds the unified DB in place.
- The old `C:\ICT_Videos\Testing\unified_knowledge.lancedb` and
  `_v4_lancedb` are superseded by `data/knowledge/unified_knowledge.lancedb`.
  `KB_DATA_DIR` (default `data/knowledge/`) selects the active tree.

## 7. Knowledge Bridge package (`scripts/knowledge_bridge/`)

The consumer repo now has a full knowledge bridge package implementing
Phases 3-4 of the KB DESIGN.md roadmap:

| Module | Purpose | Status |
|--------|---------|--------|
| `detection_catalog.py` | 34 ICT concept → vectorized function mappings | ✅ Phase 3 |
| `strategy_candidates.py` | KB setup units → executable `StrategyCandidate` objects | ✅ Phase 3 |
| `candidate_export.py` | JSON export/import + bidirectional linking | ✅ Phase 3 |
| `backtest_loop.py` | Candidate → `PropFirmSimulator` → `BacktestResult` | ✅ Phase 4 |
| `kb_context.py` | Production KB context retriever (`fetch_kb_context`) | ✅ Phase 5 |
| `confluence_engine.py` | Runtime cross-domain confluence detection (6 signal providers) | ✅ Phase 5 |
| `test_narrative.py` | Narrative integration test + `--compare` mode harness | ✅ Tested |
| `test_suite.py` | 8-test unit suite (all passing) | ✅ 8/8 pass |

**Test results (2026-07-23):**
```
python -m scripts.knowledge_bridge.test_suite
=== KNOWLEDGE BRIDGE TEST SUITE ===
[PASS] test_detection_catalog
[PASS] test_strategy_candidate_generation (6 steps)
[PASS] test_candidate_export_import
[PASS] test_bidirectional_linking
[PASS] test_backtest_result_round_trip
[PASS] test_apply_backtest_results
[PASS] test_summary_stats
[PASS] test_kb_api_search (2171 chars)
=== RESULTS: 8 passed, 0 failed, 0 skipped ===
```

**Narrative integration test (2026-07-23):**
- Cheat sheet: 15,148 chars (premarket, ES1)
- KB context: 2,185 chars (9 units retrieved, concepts: FVG, Silver Bullet, OTE, killzone, premium, discount, PDH, PDL, IPDA, target)
- Augmented cheat sheet: 17,335 chars
- Output saved to `logs/kb_test/`

## 8. Integration status (updated 2026-07-23)

**Done:**
1. ✅ **KB context wired into `briefing_core.build_premarket_context()`** —
   calls `fetch_kb_context()` and appends the KB block to the cheat sheet
   before the LLM call. Graceful degradation (no block) if KB API is down.
2. ✅ **Phase 5: Confluence engine** (`confluence_engine.py`) — 6 signal
   providers (GEX, Herman, session timing, ICT features, market structure,
   daily classification). Produces `ConfluenceResult` with `TradePlan`, KB
   citations, confidence score. CLI: `python -m scripts.knowledge_bridge.confluence_engine --ticker ES1`.
3. ✅ **`--compare` mode tested** — premarket/open/close/intraday ES1
   narratives generated with and without KB context. See
   `logs/kb_test/` for outputs.

**Next (see [KB_NARRATIVE_REPLAY_ROADMAPAP.md](KB_NARRATIVE_REPLAY_ROADMAP.md)):**
- Phase A: Rewrite prompts to be KB-aware and evidence-enforced (COMPLETED 2026-08-06).
  Updated prompt set: `scripts/trader/prompts/trader_premarket.md`,
  `trader_morning.md`, `trader_intraday.md`, `trader_close.md`,
  `weekly_briefing.md`.
  New behavior: explicit KB detection rule, required KB evidence section,
  minimum citation threshold (`[KB:source_file|conf=X.XX]`), and mandatory
  fallback sentence when KB is unavailable.
- Phase B: Historical day replay harness (INITIAL IMPLEMENTATION COMPLETED 2026-08-06).
  Added `scripts/knowledge_bridge/historical_replay.py` with CLI:
  `python -m scripts.knowledge_bridge.historical_replay --date YYYY-MM-DD --ticker ES1`.
  Writes `cheatsheet.txt`, `kb_context.txt`, `narrative.md`,
  `confluence.json`, `trade_plan.json`, `session_1m.csv`, `replay_meta.json`
  under `logs/replay/{date}_{ticker}/`.
  Historical limitations currently documented in `replay_meta.json`
  (no dated historical GEX snapshots; dated ICT features optional).
- Phase C: Virtual trade execution + outcome evaluation
- Phase D: End-to-end day replay report

**Still open (lower priority):**
- (Optional) Add `verify_narrative_claim()` to `trader_narrative.py` as a
  post-generation fact-check pass.
- Build an eval set (20-30 Q&A pairs covering OPEX, CSD, killzones, 7 Rules)
  to measure retrieval quality before/after the bridge is wired in. Keep it
  at `tests/eval/kb_eval.jsonl`.

## 9. What NOT to do

- Do NOT edit the producer's `HANDOVER.md` from this repo — edit it there.
- Do NOT import `knowledge_ingest` as a package via `pip install -e` — use the
  `sys.path` insert or the HTTP API.
- If the KB API schema changes in the producer, update `kb_bridge.py` here
  (or the producer copy, depending on where the canonical lives).
- (REVISED 2026-07-23) LanceDB files, units JSONL, and mineru text outputs NOW
  live in this repo under `data/knowledge/` — the consumer owns produced data.
  The earlier "do not copy LanceDB into this repo" rule is REVERSED. Raw inputs
  (transcripts/PDFs/chart renders) still stay external; only *produced* artifacts
  move here. The producer learns the location via `KB_DATA_DIR` (see §2).

## 9. Related docs

- **Canonical producer handover:** `C:\Users\vinay\video2pdf\knowledge_ingest\HANDOVER.md`
  — sections 20 (RAG/API layer), 21 (OPEX validation), 22 (cross-repo data flow).
- **Producer KB API:** `C:\Users\vinay\video2pdf\knowledge_ingest\serve.py`
- **Producer bridge module:** `C:\Users\vinay\video2pdf\knowledge_ingest\kb_bridge.py`
- **This repo's narrative plan:** `docs/architecture/TRADER_NARRATIVE_PLAN.md`
- **This repo's trading domain rules:** `docs/SecondBrain_Trading.md`