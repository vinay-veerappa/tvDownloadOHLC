# KB Bridge — Connecting to the ICT Knowledge Base

**Status:** Bridge module built and tested; not yet wired into `briefing_core.py`.
**Owner:** This doc lives in the consumer repo (`tvDownloadOHLC`). The canonical
producer handover is `C:\Users\vinay\video2pdf\knowledge_ingest\HANDOVER.md` —
read it for full pipeline state, schema, and history. Do not edit it from here.

---

## 1. The split

| Role | Repo | Path |
|---|---|---|
| **Producer** (ingests transcripts/PDFs/charts → typed KnowledgeUnits → LanceDB; serves the KB API) | `video2pdf` | `C:\Users\vinay\video2pdf\knowledge_ingest\` |
| **Raw data** (transcripts, PDFs, chart renders, LanceDB stores) | — | `C:\ICT_Videos\` |
| **Consumer** (narrative engine; queries the KB API) | `tvDownloadOHLC` (this repo) | `scripts/trader/` |

**Data is NOT copied into this repo.** We call the producer's HTTP API.

## 2. Runtime contract

The only coupling between this repo and the producer is the KB API on
`http://127.0.0.1:8900`. Start the producer first, then run the consumer.

```powershell
# 1) Producer (one terminal)
cd C:\Users\vinay\video2pdf; .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python -m knowledge_ingest.serve --port 8900

# 2) Consumer (another terminal)
cd C:\Users\vinay\tvDownloadOHLC; .\.venv\Scripts\Activate.ps1
python -m scripts.trader.trader_narrative --mode premarket --ticker ES1
```

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

## 6. Current KB state (as of 2026-07-21)

- **Chart units:** 818 at `C:\ICT_Videos\Testing\_v4_lancedb` (table `knowledge`)
  — 415 framework, 403 setup. Sources: LumiTrader book (435), Vinay_Models (119),
  ICTNotes (78), Flux (67), etc.
- **Text units:** 11,206 from TCM 2023 transcripts at
  `C:\ICT_Videos\TCM\2023\ingest_output\units\*.jsonl` (ICT-aware prompts).
  Includes 132 OPEX-tagged units. Not yet built into a persistent LanceDB —
  re-run `build_lancedb` when a stable vector store is needed.
- **Pending ingest:** TCM 2024 (75 transcripts) and 2025 (18 transcripts) —
  run with `--ict-aware --no-skip` (see producer HANDOVER §19e).

## 7. Integration TODO (this repo)

1. Wire `get_kb_context_for_narrative()` into
   `scripts/trader/briefing_core.build_trader_cheat_sheet()` — append the
   returned context block to the cheat sheet before it goes to the narrative LLM.
2. (Optional) Add `verify_narrative_claim()` to `trader_narrative.py` as a
   post-generation fact-check pass.
3. Build an eval set (20-30 Q&A pairs covering OPEX, CSD, killzones, 7 Rules)
   to measure retrieval quality before/after the bridge is wired in. Keep it
   at `tests/eval/kb_eval.jsonl`.

## 8. What NOT to do

- Do NOT copy LanceDB files, transcript PDFs, or chart renders into this repo.
- Do NOT edit the producer's `HANDOVER.md` from this repo — edit it there.
- Do NOT import `knowledge_ingest` as a package via `pip install -e` — use the
  `sys.path` insert or the HTTP API.
- If the KB API schema changes in the producer, update `kb_bridge.py` here
  (or the producer copy, depending on where the canonical lives).

## 9. Related docs

- **Canonical producer handover:** `C:\Users\vinay\video2pdf\knowledge_ingest\HANDOVER.md`
  — sections 20 (RAG/API layer), 21 (OPEX validation), 22 (cross-repo data flow).
- **Producer KB API:** `C:\Users\vinay\video2pdf\knowledge_ingest\serve.py`
- **Producer bridge module:** `C:\Users\vinay\video2pdf\knowledge_ingest\kb_bridge.py`
- **This repo's narrative plan:** `docs/architecture/TRADER_NARRATIVE_PLAN.md`
- **This repo's trading domain rules:** `docs/SecondBrain_Trading.md`